#!/usr/bin/env python3
"""
本地代理脚本：监听8282端口，转发到目标地址，记录请求和响应
"""
import socket
import threading
import time
import datetime

TARGET_HOST = "113.90.244.216"
TARGET_PORT = 8282
LISTEN_PORT = 8282
LOG_FILE = r"D:\arvin\claude_workspace\soap_capture.log"

def log(msg):
    """打印并记录日志"""
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

def handle_client(client_socket, client_addr):
    """处理客户端连接"""
    log(f"=== 新连接 from {client_addr} ===")

    request_data = b""
    try:
        # 接收请求数据
        client_socket.settimeout(5)
        while True:
            try:
                chunk = client_socket.recv(4096)
                if not chunk:
                    break
                request_data += chunk
                # 如果已经收到完整HTTP包，可以提前结束
                if b"\r\n\r\n" in request_data:
                    # 检查Content-Length
                    header_end = request_data.find(b"\r\n\r\n")
                    headers = request_data[:header_end].decode('utf-8', errors='replace')
                    if "Content-Length:" in headers:
                        for line in headers.split("\r\n"):
                            if line.startswith("Content-Length:"):
                                content_length = int(line.split(":")[1].strip())
                                body_start = header_end + 4
                                body_received = len(request_data) - body_start
                                if body_received >= content_length:
                                    break
                    else:
                        break
            except socket.timeout:
                break
    except Exception as e:
        log(f"接收数据异常: {e}")

    if request_data:
        # 记录请求
        try:
            request_str = request_data.decode('utf-8', errors='replace')
        except:
            request_str = str(request_data)

        log("=== 请求内容 ===")
        log(request_str[:8000])  # 限制长度
        log("=== 请求结束 ===\n")

        # 保存原始请求数据
        with open(r"D:\arvin\claude_workspace\request_raw.bin", "wb") as f:
            f.write(request_data)
        log(f"原始请求已保存: {len(request_data)} bytes\n")

    # 转发到目标
    response_data = b""
    try:
        target_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        target_socket.settimeout(10)
        target_socket.connect((TARGET_HOST, TARGET_PORT))
        log(f"已连接到目标 {TARGET_HOST}:{TARGET_PORT}")

        # 发送原始请求
        target_socket.sendall(request_data)
        log("请求已转发")

        # 接收响应
        target_socket.settimeout(10)
        while True:
            try:
                chunk = target_socket.recv(4096)
                if not chunk:
                    break
                response_data += chunk
            except socket.timeout:
                break

        # 记录响应
        if response_data:
            try:
                response_str = response_data.decode('utf-8', errors='replace')
            except:
                response_str = str(response_data)

            log("=== 响应内容 ===")
            log(response_str[:8000])
            log("=== 响应结束 ===\n")

            # 保存原始响应
            with open(r"D:\arvin\claude_workspace\response_raw.bin", "wb") as f:
                f.write(response_data)
            log(f"原始响应已保存: {len(response_data)} bytes\n")

            # 转发响应给客户端
            client_socket.sendall(response_data)
            log("响应已转发回客户端")

        target_socket.close()

    except Exception as e:
        log(f"转发/响应异常: {e}")
        if response_data:
            client_socket.sendall(response_data)

    client_socket.close()
    log(f"=== 连接关闭 from {client_addr} ===\n")

def start_server():
    """启动监听服务"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)

    try:
        server.bind(("0.0.0.0", LISTEN_PORT))
        server.listen(5)
        log(f"=== 代理服务启动，监听 0.0.0.0:{LISTEN_PORT} ===")
        log(f"转发目标: {TARGET_HOST}:{TARGET_PORT}")
        log(f"日志文件: {LOG_FILE}")
        log("等待连接...\n")

        while True:
            client_socket, client_addr = server.accept()
            # 每个连接一个线程
            thread = threading.Thread(target=handle_client, args=(client_socket, client_addr))
            thread.daemon = True
            thread.start()
    except Exception as e:
        log(f"服务器异常: {e}")
    finally:
        server.close()

if __name__ == "__main__":
    # 清空日志
    open(LOG_FILE, "w", encoding="utf-8").close()
    start_server()
