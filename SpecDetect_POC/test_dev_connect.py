"""测试：让 Mock Device 连接 Real Atom 的 streamsrc 端口"""
import socket
import time

STREAMSRC_HOST = "127.0.0.1"
STREAMSRC_PORT = 18012

def connect_to_streamsrc():
    """作为客户端连接 Real Atom 的 streamsrc 端口"""
    print(f"[测试] 连接到 streamsrc: {STREAMSRC_HOST}:{STREAMSRC_PORT}")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        result = sock.connect_ex((STREAMSRC_HOST, STREAMSRC_PORT))
        if result == 0:
            print(f"[测试] 连接成功!")
            # 保持连接一段时间
            sock.send(b"ping")  # 发送测试数据
            time.sleep(3)
            sock.close()
            return True
        else:
            print(f"[测试] 连接失败，错误码: {result}")
            return False
    except Exception as e:
        print(f"[测试] 连接异常: {e}")
        return False

if __name__ == "__main__":
    connect_to_streamsrc()
