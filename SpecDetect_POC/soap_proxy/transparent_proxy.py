"""SOAP 透明代理 - 仅转发请求，不做任何修改"""
import socket
import threading
import logging
import os
import re
from datetime import datetime

# 日志配置
LOG_DIR = "D:/arvin/claude_workspace/SpecDetect_V4/SpecDetect_POC/soap_proxy/logs"
os.makedirs(LOG_DIR, exist_ok=True)
LOG_FILE = os.path.join(LOG_DIR, f"transparent_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log")

# 配置日志同时输出到控制台和文件
logging.basicConfig(
    level=logging.INFO,
    format='[%(asctime)s] %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(LOG_FILE, encoding='utf-8')
    ]
)

# 动态 streamsrc 端口映射（运行时更新）
# 代理监听端口 -> Real Atom streamsrc 端口
stream_proxy_ports = {}  # {proxy_port: target_port}
stream_proxy_lock = threading.Lock()


def handle_http_client(client_socket, target_host, target_port, client_addr):
    """处理 HTTP/SOAP 客户端连接 - 基于 Content-Length 判断"""
    log_id = datetime.now().strftime("%H%M%S_%f")

    try:
        # 接收客户端请求
        request_data = b''
        while True:
            chunk = client_socket.recv(4096)
            if not chunk:
                break
            request_data += chunk
            # 简单判断是否读完（Content-Length）
            if b'Content-Length:' in request_data:
                # 提取 Content-Length
                for line in request_data.decode('utf-8', errors='replace').split('\r\n'):
                    if line.startswith('Content-Length:'):
                        content_length = int(line.split(':')[1].strip())
                        # 检查是否接收完整
                        header_end = request_data.find(b'\r\n\r\n') + 4
                        body_received = len(request_data) - header_end
                        if body_received >= content_length:
                            break
                else:
                    continue
                break
            elif b'\r\n\r\n' in request_data and b'Content-Length:' not in request_data:
                # 没有 body 的请求
                break

        # 记录请求日志
        logging.info(f"[{log_id}] >>> {client_addr} -> {len(request_data)} bytes")

        # 保存请求内容到文件
        req_file = os.path.join(LOG_DIR, f"{log_id}_req.bin")
        with open(req_file, 'wb') as f:
            f.write(request_data)
        logging.info(f"[{log_id}] Request saved: {req_file}")

        # 直接转发到目标服务器
        with socket.create_connection((target_host, target_port), timeout=10) as target_socket:
            target_socket.sendall(request_data)

            # 接收响应
            response_data = b''
            while True:
                chunk = target_socket.recv(4096)
                if not chunk:
                    break
                response_data += chunk
                # 检查是否读完
                if b'Content-Length:' in response_data:
                    for line in response_data.decode('utf-8', errors='replace').split('\r\n'):
                        if line.startswith('Content-Length:'):
                            content_length = int(line.split(':')[1].strip())
                            header_end = response_data.find(b'\r\n\r\n') + 4
                            body_received = len(response_data) - header_end
                            if body_received >= content_length:
                                break
                    else:
                        continue
                    break
                elif b'\r\n\r\n' in response_data and b'Content-Length:' not in response_data:
                    break

        # 检查是否是 B_FScan 响应，解析 port 并设置代理
        if b'B_FScan' in request_data or b'<srrc:port>' in response_data:
            original_port = parse_b_fscan_port(response_data)
            if original_port:
                proxy_port = original_port + 1
                ensure_stream_proxy(proxy_port, original_port)
                response_data = modify_b_fscan_response(response_data, proxy_port)

        # 记录响应日志
        logging.info(f"[{log_id}] <<< {client_addr} <- {len(response_data)} bytes")

        # 保存响应内容到文件
        res_file = os.path.join(LOG_DIR, f"{log_id}_res.bin")
        with open(res_file, 'wb') as f:
            f.write(response_data)
        logging.info(f"[{log_id}] Response saved: {res_file}")

        # 透传响应给客户端
        client_socket.sendall(response_data)

    except Exception as e:
        logging.error(f"[{log_id}] ERROR {client_addr}: {e}")
    finally:
        client_socket.close()


def handle_stream_client(client_socket, target_host, target_port, client_addr):
    """处理 streamsrc 等流式客户端连接 - 透传所有数据"""
    log_id = datetime.now().strftime("%H%M%S_%f")
    logging.info(f"[{log_id}] [STREAM] >>> {client_addr} -> (stream connection)")

    try:
        # 保存原始连接用于日志
        req_file = os.path.join(LOG_DIR, f"{log_id}_stream_req.bin")

        # 直接转发到目标服务器（流式透传）
        with socket.create_connection((target_host, target_port), timeout=10) as target_socket:
            # 双向转发
            def forward(source, dest, direction):
                try:
                    while True:
                        data = source.recv(8192)
                        if not data:
                            break
                        dest.sendall(data)
                        # 保存数据
                        with open(req_file, 'ab') as f:
                            f.write(data)
                except Exception:
                    pass

            # 启动双向转发线程
            t1 = threading.Thread(target=forward, args=(client_socket, target_socket, "C->S"))
            t2 = threading.Thread(target=forward, args=(target_socket, client_socket, "S->C"))
            t1.daemon = True
            t2.daemon = True
            t1.start()
            t2.start()
            t1.join()
            t2.join()

        logging.info(f"[{log_id}] [STREAM] <<< {client_addr} <- (stream closed)")

    except Exception as e:
        logging.error(f"[{log_id}] [STREAM] ERROR {client_addr}: {e}")
    finally:
        client_socket.close()


def parse_b_fscan_port(response_data: bytes) -> int:
    """从 B_FScan 响应中解析 outputchannel port

    Args:
        response_data: 响应数据

    Returns:
        port 值，如果未找到返回 None
    """
    try:
        text = response_data.decode('utf-8', errors='replace')
        match = re.search(r'<srrc:port>(\d+)</srrc:port>', text)
        if match:
            return int(match.group(1))
    except Exception as e:
        logging.error(f"[HTTP] Failed to parse port: {e}")
    return None


def modify_b_fscan_response(response_data: bytes, new_port: int) -> bytes:
    """修改 B_FScan 响应中的 outputchannel port

    Args:
        response_data: 原始响应数据
        new_port: 新的 port 值

    Returns:
        修改后的响应数据
    """
    try:
        text = response_data.decode('utf-8', errors='replace')
        # 替换 <srrc:port>XXX</srrc:port> 为新端口
        modified = re.sub(
            r'(<srrc:port>)(\d+)(</srrc:port>)',
            rf'\g<1>{new_port}\g<3>',
            text
        )
        if modified != text:
            logging.info(f"[HTTP] B_FScan response port modified: -> {new_port}")
        return modified.encode('utf-8')
    except Exception as e:
        logging.error(f"[HTTP] Failed to modify port: {e}")
        return response_data


def start_stream_proxy(listen_port, target_port):
    """启动 streamsrc 透明代理（单个端口）"""
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_socket.bind(('127.0.0.1', listen_port))
        server_socket.listen(5)
        logging.info(f"[STREAM] Proxy started: 127.0.0.1:{listen_port} -> 127.0.0.1:{target_port}")

        # 保存 streamsrc 数据
        log_id = datetime.now().strftime("%H%M%S_%f")
        stream_log_file = os.path.join(LOG_DIR, f"stream_{listen_port}_{log_id}.bin")
        stream_file = open(stream_log_file, 'wb')

        while True:
            client_socket, client_addr = server_socket.accept()
            try:
                target_socket = socket.create_connection(('127.0.0.1', target_port), timeout=5)
                logging.info(f"[STREAM] >>> {client_addr} -> {listen_port}")

                def forward(src, dst, direction):
                    try:
                        while True:
                            data = src.recv(8192)
                            if not data:
                                break
                            dst.sendall(data)
                            # 保存数据
                            stream_file.write(data)
                            stream_file.flush()
                    except Exception:
                        pass
                    finally:
                        src.close()
                        dst.close()

                t1 = threading.Thread(target=forward, args=(client_socket, target_socket, "C->S"))
                t2 = threading.Thread(target=forward, args=(target_socket, client_socket, "S->C"))
                t1.daemon = True
                t2.daemon = True
                t1.start()
                t2.start()
            except Exception as e:
                logging.error(f"[STREAM] Forward error: {e}")
                client_socket.close()
    except Exception as e:
        logging.error(f"[STREAM] Proxy failed: {e}")
    finally:
        stream_file.close()
        server_socket.close()


def ensure_stream_proxy(proxy_port, target_port):
    """确保 streamsrc 代理已启动"""
    with stream_proxy_lock:
        if proxy_port not in stream_proxy_ports:
            stream_proxy_ports[proxy_port] = target_port
            thread = threading.Thread(target=start_stream_proxy, args=(proxy_port, target_port))
            thread.daemon = True
            thread.start()
            logging.info(f"[STREAM] Proxy registered: {proxy_port} -> {target_port}")


def start_proxy(listen_port, target_host, target_port, is_stream=False):
    """启动透明代理"""
    proxy_type = "STREAM" if is_stream else "HTTP"
    logging.info(f"[{proxy_type}] Listen: 127.0.0.1:{listen_port} -> {target_host}:{target_port}")

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('127.0.0.1', listen_port))
    server_socket.listen(5)

    logging.info(f"[{proxy_type}] Listening on 127.0.0.1:{listen_port}...")

    try:
        while True:
            client_socket, client_addr = server_socket.accept()
            handler = handle_stream_client if is_stream else handle_http_client
            thread = threading.Thread(
                target=handler,
                args=(client_socket, target_host, target_port, client_addr)
            )
            thread.daemon = True
            thread.start()
    except KeyboardInterrupt:
        logging.info("Shutting down...")
    finally:
        server_socket.close()


if __name__ == '__main__':
    logging.info(f"=" * 60)
    logging.info(f"SOAP Transparent Proxy (Dynamic streamsrc)")
    logging.info(f"=" * 60)

    # SOAP 请求转发: 8284 -> 8282
    threading.Thread(
        target=start_proxy,
        args=(8284, '127.0.0.1', 8282, False),
        daemon=True
    ).start()

    logging.info(f"=" * 60)
    logging.info(f"Proxy started:")
    logging.info(f"  8284 (SOAP) -> 127.0.0.1:8282")
    logging.info(f"  streamsrc: dynamic (port+1 of B_FScan response)")
    logging.info(f"=" * 60)

    try:
        while True:
            threading.Event().wait(1)
    except KeyboardInterrupt:
        logging.info("Shutting down...")
