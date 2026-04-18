#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
HTTP代理监听脚本
用于捕获HTTP请求的URL路径和完整报文

使用方法：
1. 设置系统代理指向本脚本端口 (127.0.0.1:8888)
2. 运行本脚本
3. 操作目标工具发送请求
4. 查看控制台输出的完整URL
5. 完整请求和响应保存到文件
"""

import http.server
import socketserver
import urllib.request
import urllib.parse
import json
import sys
import os
from datetime import datetime

# 配置
LISTEN_PORT = 8888
TARGET_HOST = "113.90.244.216"
TARGET_PORT = 8282

# 保存目录
SAVE_DIR = "D:/arvin/claude_workspace/SpecDetect_V4/docs/REAL_ATOM_INTEGRATION/captured"

class ProxyHandler(http.server.BaseHTTPRequestHandler):
    """代理处理器"""

    def get_soap_action(self, headers, body=None):
        """从请求头或请求体中提取SOAPAction"""
        soap_action = headers.get('SOAPAction', '')
        if soap_action:
            # 去掉引号
            soap_action = soap_action.strip('"')
        if not soap_action and body:
            try:
                body_str = body.decode('utf-8', errors='replace')
                # 尝试从请求体中提取
                if 'B_' in body_str:
                    start = body_str.find('B_')
                    end = body_str.find('"', start)
                    if end > start:
                        soap_action = body_str[start:end]
            except:
                pass
        return soap_action or 'unknown'

    def save_to_file(self, soap_action, request_data, response_data, status_code):
        """保存请求和响应到文件"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        safe_action = soap_action.replace('/', '_').replace('"', '')

        # 创建保存目录
        os.makedirs(SAVE_DIR, exist_ok=True)

        # 生成文件名
        request_file = os.path.join(SAVE_DIR, f"{safe_action}_request_{timestamp}.txt")
        response_file = os.path.join(SAVE_DIR, f"{safe_action}_response_{timestamp}.txt")

        # 保存请求
        with open(request_file, 'w', encoding='utf-8') as f:
            f.write(f"=== HTTP Request ===\n")
            f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"SOAPAction: {soap_action}\n")
            f.write(f"完整URL: http://{TARGET_HOST}:{TARGET_PORT}{self.path}\n")
            f.write(f"路径: {self.path}\n")
            f.write(f"\n=== 请求头 ===\n")
            for key, value in dict(self.headers).items():
                f.write(f"{key}: {value}\n")
            f.write(f"\n=== 请求体 ===\n")
            if request_data:
                f.write(request_data.decode('utf-8', errors='replace'))

        # 保存响应
        with open(response_file, 'w', encoding='utf-8') as f:
            f.write(f"=== HTTP Response ===\n")
            f.write(f"时间: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"状态码: {status_code}\n")
            f.write(f"\n=== 响应体 ===\n")
            if response_data:
                f.write(response_data.decode('utf-8', errors='replace'))

        print(f"\n[已保存] 请求: {request_file}")
        print(f"[已保存] 响应: {response_file}")

        return request_file, response_file

    def log_request_info(self, method, path, headers, body=None):
        """打印请求信息"""
        soap_action = self.get_soap_action(headers, body)
        print("\n" + "="*60)
        print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}]")
        print(f"方法: {method}")
        print(f"完整URL: http://{TARGET_HOST}:{TARGET_PORT}{path}")
        print(f"路径: {path}")
        print(f"SOAPAction: {soap_action}")
        print(f"请求头:")
        for h in headers:
            print(f"  {h}: {headers[h]}")
        if body:
            print(f"请求体长度: {len(body)} bytes")
            # 尝试解析SOAP XML
            if b'<?xml' in body or b'<soap' in body.lower():
                print(f"SOAP请求体:")
                try:
                    print(body.decode('utf-8', errors='replace')[:500])
                except:
                    pass
        print("="*60)
        return soap_action

    def do_GET(self):
        self.handle_request("GET")

    def do_POST(self):
        # 读取请求体
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length) if content_length > 0 else None

        # 打印请求信息
        soap_action = self.log_request_info("POST", self.path, dict(self.headers), body)

        # 转发请求到目标服务器
        self.proxy_request(body, soap_action)

    def proxy_request(self, body=None, soap_action=None):
        """转发请求到目标服务器"""
        try:
            # 构建目标URL
            target_url = f"http://{TARGET_HOST}:{TARGET_PORT}{self.path}"

            # 构建请求
            req = urllib.request.Request(
                target_url,
                data=body,
                headers=dict(self.headers),
                method=self.command
            )

            # 发送请求
            with urllib.request.urlopen(req, timeout=30) as response:
                response_body = response.read()
                response_headers = dict(response.headers)

                # 打印响应信息
                print(f"\n响应状态: {response.status}")
                print(f"响应头: {response_headers}")
                print(f"响应体长度: {len(response_body)} bytes")

                # 保存到文件
                self.save_to_file(soap_action or 'unknown', body, response_body, response.status)

                # 返回响应给客户端
                self.send_response(response.status)
                for key, value in response_headers.items():
                    if key.lower() not in ['transfer-encoding', 'connection']:
                        self.send_header(key, value)
                self.end_headers()
                self.wfile.write(response_body)

        except urllib.error.HTTPError as e:
            print(f"\n目标服务器返回错误: {e.code} {e.reason}")
            error_body = e.read() if e.fp else None
            # 保存错误响应
            if error_body and soap_action:
                self.save_to_file(soap_action, body, error_body, e.code)
            self.send_response(e.code)
            self.end_headers()
            if error_body:
                self.wfile.write(error_body)

        except Exception as e:
            print(f"\n转发请求失败: {e}")
            self.send_error(502, str(e))

    def log_message(self, format, *args):
        """抑制默认的日志输出"""
        pass

def main():
    """主函数"""
    print("="*60)
    print("HTTP代理监听脚本")
    print("="*60)
    print(f"监听端口: {LISTEN_PORT}")
    print(f"目标服务器: {TARGET_HOST}:{TARGET_PORT}")
    print(f"保存目录: {SAVE_DIR}")
    print()
    print("请将代理设置为: 127.0.0.1:8888")
    print("按 Ctrl+C 停止")
    print("="*60)

    # 设置端口复用
    socketserver.TCPServer.allow_reuse_address = True

    with socketserver.TCPServer(("", LISTEN_PORT), ProxyHandler) as httpd:
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n停止监听")
            sys.exit(0)

if __name__ == "__main__":
    main()
