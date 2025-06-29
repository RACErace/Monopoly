from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, FileResponse
from game import Game, Board
from typing import Dict
import os
import asyncio
import time
from datetime import datetime

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

connections: Dict[str, WebSocket] = {}
player_ips: Dict[str, str] = {}  # 记录每个玩家的IP地址
ip_connections: Dict[str, int] = {}  # 记录每个IP的连接数
player_colors: Dict[str, str] = {}  # 记录每个玩家选择的颜色
available_colors = ['#ff6b6b', '#4ecdc4', '#45b7d1', '#96ceb4', '#ffeaa7', '#dda0dd']  # 可选颜色
game: Game = None
host_player = None  # 记录房主
game_started = False  # 记录游戏是否已开始
MAX_CONNECTIONS_PER_IP = 1  # 每个IP最大连接数

# 连接历史记录
connection_history = []
MAX_HISTORY_SIZE = 100

def log_connection_event(event_type: str, player_name: str, details: str = "", client_ip: str = ""):
    """记录连接事件到历史记录"""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    event = {
        "timestamp": timestamp,
        "type": event_type,
        "player": player_name,
        "details": details,
        "client_ip": client_ip,
        "total_connections": len(connections)
    }
    
    connection_history.append(event)
    
    # 限制历史记录大小
    if len(connection_history) > MAX_HISTORY_SIZE:
        connection_history.pop(0)
    
    # 打印到控制台
    print(f"[{timestamp}] {event_type}: {player_name} | {details} | 连接数: {len(connections)}")

@app.get("/api/board-data")
async def get_board_data():
    """获取游戏棋盘数据"""
    board = Board()
    board_data = []
    
    for i, tile_name in enumerate(board.game_map):
        if tile_name == "起点":
            board_data.append({
                "name": tile_name,
                "price": 0,
                "special": True
            })
        elif tile_name in ["机遇", "命运"]:
            board_data.append({
                "name": tile_name,
                "price": 0,
                "special": False
            })
        else:
            # 从countries字典获取地块信息
            country_data = board.countries.get(tile_name, {})
            cost = country_data.get("cost", [0])
            board_data.append({
                "name": tile_name,
                "price": cost[0] if cost else 0,
                "special": False
            })
    
    return {"board_data": board_data}

@app.get("/")
async def read_root():
    """提供客户端 HTML 文件"""
    if os.path.exists("client.html"):
        return FileResponse("client.html")
    else:
        return HTMLResponse(f"""
        <html>
            <head><title>大富翁游戏</title></head>
            <body>
                <h1>大富翁游戏服务器</h1>
                <p>服务器正在运行中...</p>
                <p>局域网访问地址: http://[服务器IP]:8000</p>
                <p>WebSocket 端点: ws://[服务器IP]:8000/ws/{{player_name}}</p>
                <p>请确保 client.html 文件存在以访问游戏客户端。</p>
            </body>
        </html>
        """)

@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {"status": "ok", "message": "大富翁游戏服务器运行正常"}

@app.websocket("/ws/{player_name}")
async def websocket_endpoint(websocket: WebSocket, player_name: str):
    global host_player, game, game_started
    
    # 获取客户端IP地址
    client_ip = websocket.client.host
    log_connection_event("连接尝试", player_name, f"来自IP: {client_ip}", client_ip)
    
    # 检查游戏是否已开始，如果已开始则检查是否为现有玩家重连
    if game_started:
        # 检查是否是游戏中的现有玩家尝试重连
        is_existing_player = game and any(p.name == player_name for p in game.players)
        
        if not is_existing_player:
            log_connection_event("连接拒绝", player_name, "游戏已开始，不允许新玩家加入", client_ip)
            await websocket.close(code=4003, reason="游戏已开始，不允许新玩家加入")
            return
        else:
            log_connection_event("玩家重连", player_name, "游戏中玩家重新连接", client_ip)
    
    # 检查IP连接限制（对重连的现有玩家放宽限制）
    current_ip_connections = ip_connections.get(client_ip, 0)
    is_existing_player_reconnect = game_started and game and any(p.name == player_name for p in game.players)
    
    if current_ip_connections >= MAX_CONNECTIONS_PER_IP and not is_existing_player_reconnect:
        log_connection_event("连接拒绝", player_name, f"IP {client_ip} 已达到最大连接数", client_ip)
        await websocket.close(code=4001, reason="同一设备只能连接一个角色")
        return
    
    # 检查玩家名是否已存在
    if player_name in connections:
        log_connection_event("连接拒绝", player_name, "玩家名已存在", client_ip)
        await websocket.close(code=4002, reason="玩家名已存在")
        return
    
    await websocket.accept()
    connections[player_name] = websocket
    player_ips[player_name] = client_ip
    ip_connections[client_ip] = current_ip_connections + 1
    
    log_connection_event("连接成功", player_name, f"IP: {client_ip}, 总连接数: {len(connections)}", client_ip)
    
    # 设置房主（第一个连接的玩家）
    if host_player is None:
        host_player = player_name
        log_connection_event("设置房主", player_name, "", client_ip)
    
    # 如果是游戏中玩家重连，发送当前游戏状态
    if game_started and game:
        try:
            game_state = game.get_game_state()
            game_state["type"] = "game_reconnect"
            game_state["message"] = f"欢迎回来，{player_name}！游戏正在进行中"
            await websocket.send_json(game_state)
            log_connection_event("游戏状态发送", player_name, "已发送当前游戏状态", client_ip)
        except Exception as e:
            log_connection_event("状态发送失败", player_name, f"发送游戏状态失败: {e}", client_ip)
    else:
        # 广播玩家列表更新（仅在游戏未开始时）
        await broadcast_player_list()
    
    try:
        while True:
            # 设置超时时间，避免无限等待
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=60.0)
            except asyncio.TimeoutError:
                # 60秒内没有收到消息，发送ping检查连接
                log_connection_event("超时检测", player_name, "60秒无消息，发送ping检查", client_ip)
                try:
                    await websocket.send_json({"type": "ping"})
                    continue
                except Exception as ping_error:
                    # 发送失败，连接已断开
                    log_connection_event("ping失败", player_name, f"ping发送失败: {ping_error}", client_ip)
                    await handle_player_disconnect(player_name, f"ping发送失败: {ping_error}")
                    break
            except Exception as receive_error:
                log_connection_event("接收异常", player_name, f"接收消息异常: {receive_error}", client_ip)
                await handle_player_disconnect(player_name, f"接收消息异常: {receive_error}")
                break
            
            action = data.get("action")

            # 心跳检测
            if action == "ping":
                await websocket.send_json({"type": "pong"})
                continue

            if action == "start_game":
                # 只有房主可以开始游戏
                if player_name != host_player:
                    await websocket.send_json({"type": "error", "message": "只有房主可以开始游戏"})
                    continue
                    
                players = list(connections.keys())
                if len(players) < 2:
                    await websocket.send_json({"type": "error", "message": "至少需要2名玩家才能开始游戏"})
                    continue
                    
                game = Game(players=players)
                game_started = True  # 设置游戏已开始标志
                
                # 发送游戏开始消息，包含初始游戏状态
                initial_state = game.get_game_state()
                initial_state["type"] = "game_started"
                await broadcast(initial_state)

            elif action == "roll_dice":
                if game and game.get_current_player().name == player_name:
                    # 检查是否已经掷过骰子
                    if game.has_rolled_this_turn:
                        await websocket.send_json({
                            "type": "error",
                            "message": "本回合已经掷过骰子，请完成当前操作或结束回合"
                        })
                        continue
                    
                    d1, d2 = game.roll_dice()
                    result = game.play_turn_network(1)
                    
                    # 检查是否有错误
                    if "error" in result:
                        await websocket.send_json({
                            "type": "error",
                            "message": result["error"]
                        })
                        continue
                    
                    result["type"] = "turn_result"
                    result["dice_values"] = [d1, d2]  # 添加单独的骰子值
                    await broadcast(result)
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": "不是您的回合"
                    })

            elif action == "buy_property":
                if game and game.get_current_player().name == player_name:
                    result = game.buy_property()
                    result["type"] = "buy_result"
                    # 添加当前玩家信息，因为购买后会切换到下一位玩家
                    result["current_player"] = game.get_current_player().name
                    result["has_rolled_this_turn"] = game.has_rolled_this_turn
                    await broadcast(result)

            elif action == "upgrade_property":
                if game and game.get_current_player().name == player_name:
                    result = game.upgrade_property()
                    result["type"] = "upgrade_result"
                    # 添加当前玩家信息，因为升级后会切换到下一位玩家
                    result["current_player"] = game.get_current_player().name
                    result["has_rolled_this_turn"] = game.has_rolled_this_turn
                    await broadcast(result)

            elif action == "mortgage_property":
                if game and game.get_current_player().name == player_name:
                    property_name = data.get("property_name")
                    if property_name:
                        result = game.mortgage_property(property_name)
                        result["type"] = "mortgage_result"
                        await broadcast(result)

            elif action == "redeem_property":
                if game and game.get_current_player().name == player_name:
                    property_name = data.get("property_name")
                    if property_name:
                        result = game.redeem_property(property_name)
                        result["type"] = "redeem_result"
                        await broadcast(result)

            elif action == "sell_property":
                if game and game.get_current_player().name == player_name:
                    property_name = data.get("property_name")
                    if property_name:
                        result = game.sell_property(property_name)
                        result["type"] = "sell_result"
                        await broadcast(result)

            elif action == "get_financial_options":
                if game:
                    result = game.get_financial_options(player_name)
                    result["type"] = "financial_options"
                    await websocket.send_json(result)

            elif action == "end_turn":
                if game:
                    # 检查是否是当前玩家
                    current_player = game.get_current_player()
                    if current_player.name == player_name:
                        game.next_player()  # next_player 方法已经包含重置掷骰子状态
                        new_current_player = game.get_current_player()
                        result = {
                            "type": "turn_ended",
                            "player": player_name,
                            "current_player": new_current_player.name,
                            "has_rolled_this_turn": game.has_rolled_this_turn,
                            "events": [f"{player_name} 主动结束了回合，轮到 {new_current_player.name}"],
                            "players": [p.to_dict() for p in game.players],
                            "properties": [t.to_dict() for t in game.board.tiles if hasattr(t, 'to_dict')]
                        }
                        game.pending_action = None  # 清除待处理动作
                        
                        if game.is_game_over():
                            result["game_over"] = True
                            result["winner"] = game.get_winner().name
                        
                        await broadcast(result)
                    else:
                        await websocket.send_json({
                            "type": "error",
                            "message": "不是您的回合，无法结束回合"
                        })

            elif action == "choose_color":
                # 处理玩家选择颜色
                selected_color = data.get("color")
                if selected_color in available_colors:
                    # 检查颜色是否已被占用
                    if selected_color not in player_colors.values():
                        player_colors[player_name] = selected_color
                        await websocket.send_json({
                            "type": "color_selected", 
                            "color": selected_color,
                            "message": f"成功选择颜色"
                        })
                        # 广播玩家列表更新
                        await broadcast_player_list()
                    else:
                        await websocket.send_json({
                            "type": "error", 
                            "message": "该颜色已被其他玩家选择"
                        })
                else:
                    await websocket.send_json({
                        "type": "error", 
                        "message": "无效的颜色选择"
                    })

            elif action == "leave_room":
                # 主动退出房间
                log_connection_event("主动退出", player_name, "玩家主动退出房间", client_ip)
                await handle_player_disconnect(player_name, "主动退出房间")
                await websocket.close(code=1000, reason="玩家主动退出房间")
                break

    except WebSocketDisconnect as e:
        disconnect_reason = f"WebSocket正常断开 - code: {getattr(e, 'code', 'unknown')}, reason: {getattr(e, 'reason', 'unknown')}"
        log_connection_event("WebSocket断开", player_name, disconnect_reason, client_ip)
        await handle_player_disconnect(player_name, disconnect_reason)
    except ConnectionResetError as e:
        disconnect_reason = f"连接被重置: {e}"
        log_connection_event("连接重置", player_name, disconnect_reason, client_ip)
        await handle_player_disconnect(player_name, disconnect_reason)
    except Exception as e:
        disconnect_reason = f"未知异常: {type(e).__name__}: {e}"
        log_connection_event("未知异常", player_name, disconnect_reason, client_ip)
        await handle_player_disconnect(player_name, disconnect_reason)

async def handle_player_disconnect(player_name: str, reason: str = "未知原因"):
    """处理玩家断开连接的清理工作"""
    global host_player, game, game_started
    
    # 记录断开事件
    client_ip = player_ips.get(player_name, "unknown")
    log_connection_event("连接断开", player_name, reason, client_ip)
    
    # 记录连接前状态
    before_count = len(connections)
    
    # 清理连接记录
    if player_name in connections:
        del connections[player_name]
        log_connection_event("清理连接", player_name, "移除连接记录", client_ip)
    else:
        log_connection_event("警告", player_name, "玩家不在连接列表中", client_ip)
    
    # 清理玩家颜色记录
    if player_name in player_colors:
        released_color = player_colors[player_name]
        del player_colors[player_name]
        log_connection_event("清理颜色", player_name, f"释放颜色: {released_color}", client_ip)
    
    if player_name in player_ips:
        client_ip = player_ips[player_name]
        del player_ips[player_name]
        
        # 减少IP连接计数
        if client_ip in ip_connections:
            ip_connections[client_ip] -= 1
            if ip_connections[client_ip] <= 0:
                del ip_connections[client_ip]
                log_connection_event("清理IP", player_name, f"清除IP连接记录: {client_ip}", client_ip)
            else:
                log_connection_event("IP更新", player_name, f"IP {client_ip} 剩余连接数: {ip_connections[client_ip]}", client_ip)
    
    # 如果离开的是房主，将房主转移给下一个玩家
    if player_name == host_player:
        if connections:
            new_host = list(connections.keys())[0]
            log_connection_event("房主转移", new_host, f"从 {player_name} 转移到 {new_host}", client_ip)
            host_player = new_host
        else:
            host_player = None
            game = None  # 如果没有玩家了，重置游戏状态
            game_started = False  # 重置游戏开始标志
            player_colors.clear()  # 清空所有颜色记录
            log_connection_event("重置游戏", player_name, "所有玩家离开，重置游戏状态", client_ip)
    
    # 如果游戏进行中且玩家离开，可能需要暂停游戏或做其他处理
    if game and player_name in [p.name for p in game.players]:
        log_connection_event("游戏影响", player_name, "游戏中玩家离开，可能影响游戏进程", client_ip)
    
    # 广播玩家离开消息
    remaining_players = list(connections.keys())
    leave_message = {
        "type": "player_left", 
        "player": player_name,
        "remaining_players": remaining_players,
        "new_host": host_player,
        "disconnect_reason": reason
    }
    
    # 尝试广播，如果失败记录详细信息
    try:
        await broadcast(leave_message)
        log_connection_event("广播成功", player_name, "已广播玩家离开消息", client_ip)
    except Exception as broadcast_error:
        log_connection_event("广播失败", player_name, f"广播玩家离开消息失败: {broadcast_error}", client_ip)
    
    # 广播更新后的玩家列表
    try:
        await broadcast_player_list()
        log_connection_event("列表更新", player_name, "已广播更新后的玩家列表", client_ip)
    except Exception as list_error:
        log_connection_event("列表失败", player_name, f"广播玩家列表失败: {list_error}", client_ip)
    
    after_count = len(connections)
    final_stats = f"连接数变化: {before_count}→{after_count}, 在线: {list(connections.keys())}, 房主: {host_player}"
    log_connection_event("断开完成", player_name, final_stats, client_ip)

async def broadcast(message: dict):
    """广播消息到所有连接的客户端，自动清理失效连接"""
    if not connections:
        return
    
    failed_connections = []
    success_count = 0
    
    for player_name, ws in connections.items():
        try:
            await ws.send_json(message)
            success_count += 1
        except Exception as e:
            error_type = type(e).__name__
            print(f"向玩家 {player_name} 发送消息失败 ({error_type}): {e}")
            failed_connections.append((player_name, f"广播失败: {error_type}: {e}"))
    
    print(f"广播结果: 成功 {success_count}/{len(connections)}, 失败 {len(failed_connections)}")
    
    # 清理失效的连接
    for player_name, failure_reason in failed_connections:
        print(f"清理失效连接: {player_name}, 原因: {failure_reason}")
        # 注意：这里不能直接调用handle_player_disconnect，会导致递归
        # 直接清理连接记录
        if player_name in connections:
            del connections[player_name]
        if player_name in player_ips:
            client_ip = player_ips[player_name]
            del player_ips[player_name]
            if client_ip in ip_connections:
                ip_connections[client_ip] -= 1
                if ip_connections[client_ip] <= 0:
                    del ip_connections[client_ip]

async def broadcast_player_list():
    """广播当前玩家列表，包含颜色信息"""
    if connections:
        message = {
            "type": "player_list",
            "players": list(connections.keys()),
            "host": host_player,
            "player_colors": dict(player_colors),
            "available_colors": [color for color in available_colors if color not in player_colors.values()]
        }
        await broadcast(message)

@app.get("/admin/status")
async def admin_status():
    """管理员查看当前连接状态"""
    status = {
        "total_connections": len(connections),
        "players": list(connections.keys()),
        "host_player": host_player,
        "ip_connections": dict(ip_connections),
        "player_ips": dict(player_ips),
        "game_started": game_started
    }
    return status

@app.post("/admin/kick/{player_name}")
async def admin_kick_player(player_name: str):
    """管理员踢出指定玩家"""
    if player_name in connections:
        ws = connections[player_name]
        await ws.close(code=4003, reason="被管理员踢出")
        return {"message": f"玩家 {player_name} 已被踢出"}
    return {"error": "玩家不存在"}

@app.post("/admin/reset")
async def admin_reset():
    """管理员重置游戏状态"""
    global game, host_player, game_started
    
    # 关闭所有连接
    for ws in connections.values():
        await ws.close(code=4004, reason="管理员重置游戏")
    
    # 清空所有状态
    connections.clear()
    player_ips.clear()
    ip_connections.clear()
    game = None
    host_player = None
    game_started = False
    
    return {"message": "游戏状态已重置"}

@app.get("/admin/connections")
async def admin_connections():
    """管理员查看连接历史和详细状态"""
    return {
        "current_connections": {
            "total": len(connections),
            "players": list(connections.keys()),
            "host_player": host_player,
            "ip_connections": dict(ip_connections),
            "player_ips": dict(player_ips),
            "game_started": game_started
        },
        "connection_history": connection_history[-50:],  # 最近50条记录
        "statistics": {
            "total_events": len(connection_history),
            "recent_disconnects": len([h for h in connection_history[-20:] if "断开" in h["type"]]),
            "recent_connects": len([h for h in connection_history[-20:] if "连接成功" in h["type"]]),
            "active_ips": list(set(player_ips.values()))
        }
    }

@app.get("/admin/connections/live")
async def admin_connections_live():
    """实时连接状态 - 轻量级接口"""
    return {
        "timestamp": datetime.now().isoformat(),
        "total_connections": len(connections),
        "players": list(connections.keys()),
        "host": host_player,
        "ip_count": len(ip_connections),
        "game_active": game_started
    }

@app.get("/monitor")
async def monitor_page():
    """提供连接监控页面"""
    if os.path.exists("monitor.html"):
        return FileResponse("monitor.html")
    else:
        return HTMLResponse("<h1>监控页面文件不存在</h1><p>请确保 monitor.html 文件存在。</p>")
