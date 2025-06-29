import subprocess
import sys

def start_server():
    """启动FastAPI服务器"""
    try:
        subprocess.run([
            sys.executable, "-m", "uvicorn", 
            "server:app", 
            "--reload",
            "--host", "0.0.0.0",  # 允许所有IP访问
            "--port", "8000"      # 明确指定端口
        ], check=True)
    except subprocess.CalledProcessError as e:
        print(f"服务器启动失败: {e}")
    except KeyboardInterrupt:
        print("\n服务器已停止")

if __name__ == "__main__":
    start_server()