"""SOAP Proxy 核心转发逻辑 - 最小透明版本"""
import uuid
import threading
import queue
from flask import Flask, request, Response
import requests


class SOAPProxy:
    """SOAP 透明代理"""

    def __init__(self, atom_host: str, atom_port: int, log_dir: str):
        self.atom_host = atom_host
        self.atom_port = atom_port
        self.log_dir = log_dir

        # 线程安全的日志队列
        self.log_queue = queue.Queue()

        # 启动日志写入线程
        self.log_thread = threading.Thread(target=self._log_worker, daemon=True)
        self.log_thread.start()

    def _log_worker(self):
        """日志写入线程 (守护线程)"""
        while True:
            try:
                item = self.log_queue.get(timeout=1)
                if item is None:
                    break
                self._write_log(**item)
            except queue.Empty:
                continue

    def _write_log(self, request_id: str, direction: str, xml_data: bytes, status_code: int = None):
        """原子化写入日志"""
        import os
        from datetime import datetime

        date_str = datetime.now().strftime("%Y%m%d_%H%M")
        req_dir = os.path.join(self.log_dir, f"requests_{date_str}")
        os.makedirs(req_dir, exist_ok=True)

        filename = f"{request_id}_{direction}.xml"
        filepath = os.path.join(req_dir, filename)

        with open(filepath, "wb") as f:
            f.write(xml_data)

    def handle_soap(self):
        """处理 SOAP 请求"""
        # 生成请求ID
        request_id = str(uuid.uuid4())[:8]

        # 打印请求信息
        soap_action = request.headers.get("SOAPAction", "").strip('"')
        xml_len = len(request.data)
        print(f"[SOAP Proxy] >>> {request_id} | SOAPAction: {soap_action} | {xml_len} bytes")

        # 记录请求到日志队列 (非阻塞)
        self.log_queue.put({
            "request_id": request_id,
            "direction": "req",
            "xml_data": request.data
        })

        try:
            # 透明转发到 Real Atom
            url = f"http://{self.atom_host}:{self.atom_port}/"
            resp = requests.post(
                url,
                data=request.data,
                headers=dict(request.headers),
                timeout=30
            )

            # 记录响应到日志队列 (非阻塞)
            self.log_queue.put({
                "request_id": request_id,
                "direction": "res",
                "xml_data": resp.content,
                "status_code": resp.status_code
            })

            print(f"[SOAP Proxy] <<< {request_id} | HTTP {resp.status_code} | {len(resp.content)} bytes")

            return Response(
                resp.content,
                status=resp.status_code,
                content_type=resp.headers.get("Content-Type", "text/xml")
            )

        except requests.exceptions.Timeout:
            error_xml = b'<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body><soap:Fault><faultcode>soap:Server</faultcode><faultstring>Gateway Timeout</faultstring></soap:Fault></soap:Body></soap:Envelope>'
            print(f"[SOAP Proxy] !!! {request_id} | Timeout")
            return Response(error_xml, status=504, content_type="text/xml")

        except Exception as e:
            error_xml = f'<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body><soap:Fault><faultcode>soap:Server</faultcode><faultstring>{str(e)}</faultstring></soap:Fault></soap:Body></soap:Envelope>'.encode()
            print(f"[SOAP Proxy] !!! {request_id} | Error: {e}")
            return Response(error_xml, status=500, content_type="text/xml")


def create_proxy_app(atom_host: str, atom_port: int, log_dir: str) -> Flask:
    """创建 Flask 应用"""
    app = Flask(__name__)
    proxy = SOAPProxy(atom_host, atom_port, log_dir)

    @app.route('/', methods=['POST'])
    def handle_soap():
        return proxy.handle_soap()

    @app.route('/health', methods=['GET'])
    def health():
        return {'status': 'ok', 'service': 'soap_proxy'}

    return app
