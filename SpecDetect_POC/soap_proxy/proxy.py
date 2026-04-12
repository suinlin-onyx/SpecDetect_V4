"""SOAP Proxy 核心转发逻辑 - 最小透明版本"""
import uuid
from flask import Flask, request, Response
import requests

from soap_proxy.logger import SOAPProxyLogger
from soap_proxy.soap_to_rmcp_converter import SOAPToRMCPConverter


class SOAPProxy:
    """SOAP 透明代理"""

    def __init__(self, atom_host: str, atom_port: int, log_dir: str, conversion_output_dir: str = None):
        self.atom_host = atom_host
        self.atom_port = atom_port
        self.log_dir = log_dir

        # 初始化 SOAPProxyLogger (统一管理所有日志)
        self.logger = SOAPProxyLogger(log_dir)

        # 初始化 SOAP→RMCP 转换器
        if conversion_output_dir:
            self.converter = SOAPToRMCPConverter(conversion_output_dir)
        else:
            self.converter = None

    def handle_soap(self):
        """处理 SOAP 请求"""
        # 生成请求ID
        request_id = str(uuid.uuid4())[:8]

        # 提取 SOAP 操作名称
        soap_action = request.headers.get("SOAPAction", "").strip('"')
        xml_data = request.data.decode('utf-8', errors='replace')
        operation = self.logger.extract_operation(xml_data)

        # 打印请求信息
        xml_len = len(request.data)
        print(f"[SOAP Proxy] >>> {request_id} | {operation} | SOAPAction: {soap_action} | {xml_len} bytes")

        # 使用 SOAPProxyLogger 记录请求 (包含汇总日志 + req xml)
        self.logger.log_request(request_id, operation, xml_data, dict(request.headers))

        # SOAP → RMCP 转换并保存 (用于验证)
        if self.converter:
            try:
                self.converter.convert_and_save(xml_data, soap_action)
            except Exception as e:
                print(f"[SOAP→RMCP] Convert error: {e}")

        try:
            # 透明转发到 Real Atom
            url = f"http://{self.atom_host}:{self.atom_port}/"
            resp = requests.post(
                url,
                data=request.data,
                headers=dict(request.headers),
                timeout=30
            )

            # 使用 SOAPProxyLogger 记录响应 (包含汇总日志 + res xml)
            resp_xml = resp.content.decode('utf-8', errors='replace')
            self.logger.log_response(request_id, operation, resp_xml, resp.status_code)

            print(f"[SOAP Proxy] <<< {request_id} | HTTP {resp.status_code} | {len(resp.content)} bytes")

            return Response(
                resp.content,
                status=resp.status_code,
                content_type=resp.headers.get("Content-Type", "text/xml")
            )

        except requests.exceptions.Timeout:
            error_xml = b'<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body><soap:Fault><faultcode>soap:Server</faultcode><faultstring>Gateway Timeout</faultstring></soap:Fault></soap:Body></soap:Envelope>'
            print(f"[SOAP Proxy] !!! {request_id} | Timeout")
            self.logger.log_error(request_id, operation, "Gateway Timeout")
            return Response(error_xml, status=504, content_type="text/xml")

        except Exception as e:
            error_xml = f'<?xml version="1.0" encoding="utf-8"?><soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"><soap:Body><soap:Fault><faultcode>soap:Server</faultcode><faultstring>{str(e)}</faultstring></soap:Fault></soap:Body></soap:Envelope>'.encode()
            print(f"[SOAP Proxy] !!! {request_id} | Error: {e}")
            self.logger.log_error(request_id, operation, str(e))
            return Response(error_xml, status=500, content_type="text/xml")


def create_proxy_app(atom_host: str, atom_port: int, log_dir: str, conversion_output_dir: str = None) -> Flask:
    """创建 Flask 应用"""
    app = Flask(__name__)
    proxy = SOAPProxy(atom_host, atom_port, log_dir, conversion_output_dir)

    @app.route('/', methods=['POST'])
    def handle_soap():
        return proxy.handle_soap()

    @app.route('/health', methods=['GET'])
    def health():
        return {'status': 'ok', 'service': 'soap_proxy'}

    return app
