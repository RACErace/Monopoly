import random
from typing import List, Optional, Dict, Any

class Player:
    def __init__(self, name: str):
        self.name = name
        self.money = 1500
        self.position = 0
        self.properties = []

    def get_mortgageable_properties(self):
        """获取可抵押的地块"""
        return [prop for prop in self.properties if not prop.is_mortgaged]

    def get_redeemable_properties(self):
        """获取可赎回的地块"""
        return [prop for prop in self.properties if prop.is_mortgaged]

    def get_total_asset_value(self):
        """获取总资产价值（包括现金、地块和房屋）"""
        total = self.money
        for prop in self.properties:
            if prop.is_mortgaged:
                # 不计算已抵押地块的价值
                pass
            else:
                # 未抵押的地块算出售价值
                total += prop.selling_price
        return total

    def can_pay_debt(self, amount: int):
        """检查是否能通过抵押或出售地块来偿还债务"""
        return self.get_total_asset_value() >= amount

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "money": self.money,
            "position": self.position,
            "properties": [prop.name for prop in self.properties],
            "total_asset_value": self.get_total_asset_value(),
            "mortgageable_properties": [prop.name for prop in self.get_mortgageable_properties()],
            "redeemable_properties": [prop.name for prop in self.get_redeemable_properties()]
        }

class Property:
    def __init__(self, name: str, cost: list[int], rent: List[int], mortgage_value: int, selling_price: int):
        self.name = name
        self.cost = cost
        self.rent = rent
        self.mortgage_value = mortgage_value
        self.selling_price = selling_price
        self.owner: Optional[Player] = None
        self.houses = 0
        self.max_houses = 3
        self.is_mortgaged = False

    def get_rent(self):
        if self.is_mortgaged:
            return 0
        return self.rent[self.houses]

    def can_upgrade(self):
        return self.owner is not None and self.houses < self.max_houses and not self.is_mortgaged

    def upgrade(self):
        if self.can_upgrade() and self.owner.money >= self.cost[self.houses + 1]:
            self.owner.money -= self.cost[self.houses + 1]
            self.houses += 1
            return True
        return False

    def mortgage(self):
        """抵押地块，保留房屋"""
        if self.owner and not self.is_mortgaged:
            self.owner.money += self.mortgage_value
            self.is_mortgaged = True
            return True
        return False

    def redeem(self):
        """赎回地块"""
        if self.owner and self.is_mortgaged and self.owner.money >= self.mortgage_value:
            self.owner.money -= self.mortgage_value
            self.is_mortgaged = False
            return True
        return False

    def sell(self):
        """出售地块，不保留房屋"""
        if self.owner:
            self.owner.money += self.selling_price
            self.owner.properties.remove(self)
            self.owner = None
            self.houses = 0
            self.is_mortgaged = False
            return True
        return False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "name": self.name,
            "cost": self.cost,
            "owner": self.owner.name if self.owner else None,
            "houses": self.houses,
            "max_houses": self.max_houses,
            "is_mortgaged": self.is_mortgaged,
            "mortgage_value": self.mortgage_value,
            "sell_value": self.selling_price
        }

class EventCard:
    def __init__(self, card_type: str, board_size: int = 28):
        self.card_type = card_type  # "机遇" or "命运"
        self.name = card_type
        self.cost = [0]
        self.board_size = board_size

    def trigger(self, player: Player):
        # 在触发时动态选择一张卡片
        if self.card_type == "机遇":
            return self._trigger_chance_card(player)
        elif self.card_type == "命运":
            return self._trigger_community_card(player)
        
    def _trigger_chance_card(self, player: Player):
        """触发机遇卡片效果"""
        def move_to_start(p):
            p.position = 0
            p.money += 200
        
        def move_to_nearest_railroad(p):
            # 假设铁路站的位置（需要根据实际游戏板调整）
            railroad_positions = [4, 5, 12, 20, 26]
            current_pos = p.position
            min_distance = float('inf')
            nearest_railroad = 0
            for railroad_pos in railroad_positions:
                distance = (railroad_pos - current_pos) % self.board_size
                if distance < min_distance:
                    min_distance = distance
                    nearest_railroad = railroad_pos
            p.position = nearest_railroad
        
        def pay_building_maintenance(p):
            total_houses = sum(prop.houses for prop in p.properties if isinstance(prop, Property))
            total_cost = total_houses * 25
            p.money = max(0, p.money - total_cost)

        chance_cards = [
            ("获得银行股息 $50", lambda p: setattr(p, 'money', p.money + 50)),
            ("前往起点，领取 $200", move_to_start),
            ("银行错误，您获得 $200", lambda p: setattr(p, 'money', p.money + 200)),
            ("医生费用 $50", lambda p: setattr(p, 'money', max(0, p.money - 50))),
            ("所得税退税 $20", lambda p: setattr(p, 'money', p.money + 20)),
            ("马路维修费用，每栋房屋 $25", pay_building_maintenance),
            ("慈善捐款 $100", lambda p: setattr(p, 'money', max(0, p.money - 100))),
            ("前往最近的铁路站", move_to_nearest_railroad),
        ]
        
        # 随机选择一张卡片
        description, effect = random.choice(chance_cards)
        effect(player)
        return f"{self.card_type}: {description}"
    
    def _trigger_community_card(self, player: Player):
        """触发命运卡片效果"""
        def pay_building_maintenance_40(p):
            total_houses = sum(prop.houses for prop in p.properties if isinstance(prop, Property))
            total_cost = total_houses * 40
            p.money = max(0, p.money - total_cost)

        community_cards = [
            ("人寿保险到期，收取 $100", lambda p: setattr(p, 'money', p.money + 100)),
            ("假期基金到期，收取 $100", lambda p: setattr(p, 'money', p.money + 100)),
            ("您中了二等奖，收取 $10", lambda p: setattr(p, 'money', p.money + 10)),
            ("您已被选为主席，向每位玩家支付 $50", lambda p: setattr(p, 'money', max(0, p.money - 150))),  # 简化处理
            ("从银行错误中收取 $200", lambda p: setattr(p, 'money', p.money + 200)),
            ("医生费用，支付 $50", lambda p: setattr(p, 'money', max(0, p.money - 50))),
            ("学校税 $150", lambda p: setattr(p, 'money', max(0, p.money - 150))),
            ("房屋维修，每栋房屋 $40", pay_building_maintenance_40),
        ]
        
        # 随机选择一张卡片
        description, effect = random.choice(community_cards)
        effect(player)
        return f"{self.card_type}: {description}"

    def to_dict(self):
        return {
            "name": self.name,
            "cost": self.cost,
            "owner": None,
            "houses": 0,
            "max_houses": 0
        }

class Board:
    def __init__(self):
        self.countries = {"country1":{"cost": [1, 2, 3, 4], "rent": [1, 2, 3, 4], "mortgage_value": 1, "selling_price": 2},
                 "country2":{"cost": [2, 3, 4, 5], "rent": [2, 3, 4, 5], "mortgage_value": 1, "selling_price": 2},
                 "country3":{"cost": [3, 4, 5, 6], "rent": [3, 4, 5, 6], "mortgage_value": 1, "selling_price": 2},
                 "country4":{"cost": [4, 5, 6, 7], "rent": [4, 5, 6, 7], "mortgage_value": 1, "selling_price": 2},
                 "country5":{"cost": [5, 6, 7, 8], "rent": [5, 6, 7, 8], "mortgage_value": 1, "selling_price": 2},
                 "country6":{"cost": [6, 7, 8, 9], "rent": [6, 7, 8, 9], "mortgage_value": 1, "selling_price": 2},
                 "country7":{"cost": [7, 8, 9, 10], "rent": [7, 8, 9, 10], "mortgage_value": 1, "selling_price": 2},
                 "country8":{"cost": [8, 9, 10, 11], "rent": [8, 9, 10, 11], "mortgage_value": 1, "selling_price": 2},
                 "country9":{"cost": [9, 10, 11, 12], "rent": [9, 10, 11, 12], "mortgage_value": 1, "selling_price": 2},
                 "country10":{"cost": [10, 11, 12, 13], "rent": [10, 11, 12, 13], "mortgage_value": 1, "selling_price": 2},
                 "country11":{"cost": [11, 12, 13, 14], "rent": [11, 12, 13, 14], "mortgage_value": 1, "selling_price": 2},
                 "country12":{"cost": [12, 13, 14, 15], "rent": [12, 13, 14, 15], "mortgage_value": 1, "selling_price": 2},
                 "country13":{"cost": [13, 14, 15, 16], "rent": [13, 14, 15, 16], "mortgage_value": 1, "selling_price": 2},
                 "country14":{"cost": [14, 15, 16, 17], "rent": [14, 15, 16, 17], "mortgage_value": 1, "selling_price": 2},
                 "country15":{"cost": [15, 16, 17, 18], "rent": [15, 16, 17, 18], "mortgage_value": 1, "selling_price": 2},
                 "country16":{"cost": [16, 17, 18, 19], "rent": [16, 17, 18, 19], "mortgage_value": 1, "selling_price": 2},
                 "country17":{"cost": [17, 18, 19, 20], "rent": [17, 18, 19, 20], "mortgage_value": 1, "selling_price": 2},
                 "country18":{"cost": [18, 19, 20, 21], "rent": [18, 19, 20, 21], "mortgage_value": 1, "selling_price": 2},
                 "country19":{"cost": [19, 20, 21, 22], "rent": [19, 20, 21, 22], "mortgage_value": 1, "selling_price": 2},
                 "country20":{"cost": [20, 21, 22, 23], "rent": [20, 21, 22, 23], "mortgage_value": 1, "selling_price": 2},
                 "country21":{"cost": [21, 22, 23, 24], "rent": [21, 22, 23, 24], "mortgage_value": 1, "selling_price": 2},
                 "country22":{"cost": [22, 23, 24, 25], "rent": [22, 23, 24, 25], "mortgage_value": 1, "selling_price": 2},
                 "country23":{"cost": [23, 24, 25, 26], "rent": [23, 24, 25, 26], "mortgage_value": 1, "selling_price": 2},
                 "country24":{"cost": [24, 25, 26, 27], "rent": [24, 25, 26, 27], "mortgage_value": 1, "selling_price": 2},
                 "country25":{"cost": [25, 26, 27, 28], "rent": [25, 26, 27, 28], "mortgage_value": 1, "selling_price": 2},
                 "country26":{"cost": [26, 27, 28, 29], "rent": [26, 27, 28, 29], "mortgage_value": 1, "selling_price": 2},
                 "country27":{"cost": [27, 28, 29, 30], "rent": [27, 28, 29, 30], "mortgage_value": 1, "selling_price": 2},
                 "country28":{"cost": [28, 29, 30, 31], "rent": [28, 29, 30, 31], "mortgage_value": 1, "selling_price": 2},
                 "country29":{"cost": [29, 30, 31, 32], "rent": [29, 30, 31, 32], "mortgage_value": 1, "selling_price": 2},
                 "country30":{"cost": [30, 31, 32, 33], "rent": [30, 31, 32, 33], "mortgage_value": 1, "selling_price": 2},
                 "country31":{"cost": [31, 32, 33, 34], "rent": [31, 32, 33, 34], "mortgage_value": 1, "selling_price": 2},
                 "country32":{"cost": [32, 33, 34, 35], "rent": [32, 33, 34, 35], "mortgage_value": 1, "selling_price": 2},
                 "country33":{"cost": [33, 34, 35, 36], "rent": [33, 34, 35, 36], "mortgage_value": 1, "selling_price": 2},
                 "country34":{"cost": [34, 35, 36, 37], "rent": [34, 35, 36, 37], "mortgage_value": 1, "selling_price": 2}}
        self.game_map = ["起点", "country1", "country2", "country3", "country4",
                "机遇", "country5", "命运", "country6", "country7",
                "country8", "机遇", "country9", "country10", "country11",
                "country12", "country13", "country14", "country15",
                "country16", "country17", "country18", "country19",
                "country20", "country21", "country22", "country23","命运"]
        self.tiles = []
        for tile_name in self.game_map:
            if tile_name != "起点" and tile_name != "机遇" and tile_name != "命运":
                cost = self.countries[tile_name]["cost"]
                rent = self.countries[tile_name]["rent"]
                mortgage_value = self.countries[tile_name]["mortgage_value"]
                selling_price = self.countries[tile_name]["selling_price"]
                self.tiles.append(Property(tile_name, cost, rent, mortgage_value, selling_price))
            elif tile_name == "起点":
                self.tiles.append(Property("起点", [0], [0], 0, 0))
            elif tile_name == "机遇":
                self.tiles.append(EventCard("机遇", len(self.game_map)))
            elif tile_name == "命运":
                self.tiles.append(EventCard("命运", len(self.game_map)))
        self.size = len(self.tiles)

    def move(self, player: Player, steps: int):
        player.position = (player.position + steps) % self.size
        return self.tiles[player.position]

class Game:
    def __init__(self, players: List[str]):
        if not (2 <= len(players) <= 6):
            raise ValueError("Game must have 2 to 6 players.")
        self.players = [Player(name) for name in players]
        self.board = Board()
        self.current_player_index = 0
        self.last_roll = 0
        self.pending_action = None

    def roll_dice(self):
        d1, d2 = random.randint(1, 6), random.randint(1, 6)
        self.last_roll = d1 + d2
        return d1, d2

    def get_current_player(self) -> Player:
        return self.players[self.current_player_index]

    def play_turn_network(self, dice_total: int) -> Dict[str, Any]:
        player = self.get_current_player()

        result = {"player": player.name, "dice_total": dice_total, "events": []}
        tile = self.board.move(player, dice_total)
        result["landed_on"] = tile.name

        if isinstance(tile, Property):
            if tile.owner is None and tile.cost[0] > 0:
                self.pending_action = {"action": "prompt_buy", "property": tile.name}
                result["pending"] = self.pending_action
            elif tile.owner and tile.owner != player:
                # 检查地块是否被抵押
                if not tile.is_mortgaged:
                    rent = tile.get_rent()
                    player.money -= rent
                    tile.owner.money += rent
                    result["events"].append(f"{player.name} paid ${rent} rent to {tile.owner.name}")
                    self.check_bankrupt(player, result)
                else:
                    result["events"].append(f"{tile.name} is mortgaged, no rent charged")
                self.next_player()
            elif tile.owner == player:
                if tile.can_upgrade():
                    self.pending_action = {"action": "prompt_upgrade", "property": tile.name}
                    result["pending"] = self.pending_action
                else:
                    self.next_player()
        elif isinstance(tile, EventCard):
            desc = tile.trigger(player)
            result["events"].append(desc)
            # 处理特殊的全体玩家支付效果
            if "向每位玩家支付" in desc:
                amount = 50  # 从描述中提取金额
                for other_player in self.players:
                    if other_player != player:
                        other_player.money += amount
            self.check_bankrupt(player, result)
            self.next_player()

        result["players"] = [p.to_dict() for p in self.players]
        result["properties"] = [t.to_dict() for t in self.board.tiles if hasattr(t, 'to_dict')]
        result["current_player"] = self.get_current_player().name  # 添加当前玩家信息
        if self.is_game_over():
            result["game_over"] = True
            result["winner"] = self.get_winner().name
        return result

    def buy_property(self) -> Dict[str, Any]:
        player = self.get_current_player()
        tile = self.board.tiles[player.position]
        if isinstance(tile, Property) and tile.owner is None and tile.cost[0] > 0 and player.money >= tile.cost[0]:
            tile.owner = player
            player.money -= tile.cost[0]
            player.properties.append(tile)
            result = {
                "player": player.name, 
                "events": [f"{player.name} bought {tile.name}"], 
                "players": [p.to_dict() for p in self.players],
                "properties": [t.to_dict() for t in self.board.tiles if hasattr(t, 'to_dict')]
            }
            self.pending_action = None
            self.next_player()
            return result
        return {"error": "Invalid purchase"}

    def upgrade_property(self) -> Dict[str, Any]:
        player = self.get_current_player()
        tile = self.board.tiles[player.position]
        if isinstance(tile, Property) and tile.owner == player and tile.can_upgrade():
            if tile.upgrade():
                result = {
                    "player": player.name, 
                    "events": [f"{player.name} upgraded {tile.name} to {tile.houses} houses"], 
                    "players": [p.to_dict() for p in self.players],
                    "properties": [t.to_dict() for t in self.board.tiles if hasattr(t, 'to_dict')]
                }
                self.pending_action = None
                self.next_player()
                return result
        return {"error": "Cannot upgrade"}

    def mortgage_property(self, property_name: str) -> Dict[str, Any]:
        """抵押地块"""
        player = self.get_current_player()
        property_obj = None
        
        for prop in player.properties:
            if prop.name == property_name:
                property_obj = prop
                break
        
        if property_obj and property_obj.mortgage():
            return {
                "player": player.name,
                "events": [f"{player.name} mortgaged {property_name} for ${property_obj.mortgage_value}"],
                "players": [p.to_dict() for p in self.players]
            }
        return {"error": "Cannot mortgage property"}

    def redeem_property(self, property_name: str) -> Dict[str, Any]:
        """赎回地块"""
        player = self.get_current_player()
        property_obj = None
        
        for prop in player.properties:
            if prop.name == property_name:
                property_obj = prop
                break
        
        if property_obj and property_obj.redeem():
            return {
                "player": player.name,
                "events": [f"{player.name} redeemed {property_name} for ${property_obj.mortgage_value}"],
                "players": [p.to_dict() for p in self.players]
            }
        return {"error": "Cannot redeem property"}

    def sell_property(self, property_name: str) -> Dict[str, Any]:
        """出售地块"""
        player = self.get_current_player()
        property_obj = None
        
        for prop in player.properties:
            if prop.name == property_name:
                property_obj = prop
                break
        
        if property_obj:
            sell_value = property_obj.selling_price
            if property_obj.sell():
                return {
                    "player": player.name,
                    "events": [f"{player.name} sold {property_name} for ${sell_value}"],
                    "players": [p.to_dict() for p in self.players]
                }
        return {"error": "Cannot sell property"}

    def get_financial_options(self, player_name: str) -> Dict[str, Any]:
        """获取玩家的财务选项（可抵押、可赎回、可出售的地块）"""
        player = None
        for p in self.players:
            if p.name == player_name:
                player = p
                break
        
        if not player:
            return {"error": "Player not found"}
        
        return {
            "player": player.name,
            "money": player.money,
            "total_asset_value": player.get_total_asset_value(),
            "mortgageable_properties": [
                {"name": prop.name, "mortgage_value": prop.mortgage_value} 
                for prop in player.get_mortgageable_properties()
            ],
            "redeemable_properties": [
                {"name": prop.name, "redeem_cost": prop.mortgage_value} 
                for prop in player.get_redeemable_properties()
            ],
            "sellable_properties": [
                {"name": prop.name, "sell_value": prop.selling_price} 
                for prop in player.properties
            ]
        }

    def check_bankrupt(self, player: Player, result: Dict[str, Any]):
        """检查玩家是否破产"""
        if player.money < 0:
            debt = abs(player.money)
            if player.can_pay_debt(debt):
                # 玩家有资产可以抵押或出售
                result["events"].append(f"{player.name} has insufficient funds (${player.money}), needs to mortgage/sell properties")
                result["debt_situation"] = {
                    "player": player.name,
                    "debt": debt,
                    "can_recover": True,
                    "financial_options": self.get_financial_options(player.name)
                }
            else:
                # 玩家真正破产
                result["events"].append(f"{player.name} has gone bankrupt!")
                # 将所有地块归还银行
                for prop in player.properties[:]:  # 使用副本避免修改列表时的问题
                    prop.owner = None
                    prop.houses = 0
                    prop.is_mortgaged = False
                player.properties.clear()
                player.money = 0
                result["debt_situation"] = {
                    "player": player.name,
                    "debt": debt,
                    "can_recover": False
                }

    def next_player(self):
        """切换到下一个玩家"""
        self.current_player_index = (self.current_player_index + 1) % len(self.players)
        # 跳过已破产的玩家（money <= 0 且没有资产）
        attempts = 0
        while attempts < len(self.players):
            current_player = self.players[self.current_player_index]
            if current_player.money > 0 or len(current_player.properties) > 0:
                break
            self.current_player_index = (self.current_player_index + 1) % len(self.players)
            attempts += 1

    def is_game_over(self):
        """检查游戏是否结束"""
        active_players = [p for p in self.players if p.money > 0 or len(p.properties) > 0]
        return len(active_players) <= 1

    def get_winner(self):
        """获取胜利者"""
        active_players = [p for p in self.players if p.money > 0 or len(p.properties) > 0]
        if len(active_players) == 1:
            return active_players[0]
        return max(self.players, key=lambda p: p.get_total_asset_value())
