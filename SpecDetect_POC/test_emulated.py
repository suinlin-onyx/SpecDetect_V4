#!/usr/bin/env python
"""测试 emulated_atom 的 streamsrc 推送功能"""
import socket
import time
import threading
import sys

def log(msg):
    ts = time.strftime('%H:%M:%S')
    print(f"[{ts}] {msg}", flush=True)

def test_streamsrc_push():
    """测试 streamsrc 推送"""
    received = []

    def recv_thread():
        log("接收线程开始")
        ss = socket.socket()
        ss.settimeout(5)
        try:
            ss.connect(('127.0.0.1', 18013))
            log("已连接 streamsrc 18013")
            data = b''
            while len(data) < 1086:
                chunk = ss.recv(4096)
                if not chunk:
                    log("连接断开")
                    break
                data += chunk
                log(f"已接收 {len(data)} bytes")
            received.append(data)
            log(f"接收完成: {len(data)} bytes")
        except Exception as e:
            log(f"接收错误: {e}")
        finally:
            ss.close()

    # 启动接收线程
    t = threading.Thread(target=recv_thread)
    t.start()

    # 等待连接建立
    time.sleep(0.5)

    # 发送 SOAP 请求
    log("发送 SOAP 请求...")
    soap = socket.socket()
    soap.settimeout(5)
    try:
        soap.connect(('127.0.0.1', 8283))
        log("已连接 SOAP 8283")

        soap_xml = '<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn"><soapenv:Body><srrc:requestbody><srrc:equpara><srrc:groupitems><srrc:groupitem><srrc:items><srrc:item><srrc:paraname>startfreq</srrc:paraname><srrc:paravalue>137000000</srrc:paravalue></srrc:item></srrc:items></srrc:groupitem></srrc:groupitems></srrc:equpara></srrc:requestbody></soapenv:Body></soapenv:Envelope>'

        req = f'POST /B_FScan HTTP/1.1\r\nHost: 127.0.0.1:8283\r\nContent-Type: text/xml\r\nSOAPAction: B_FScan\r\nContent-Length: {len(soap_xml)}\r\n\r\n{soap_xml}'

        soap.sendall(req.encode('utf-8'))
        log(f"SOAP 请求已发送: {len(req)} bytes")

        # 接收响应
        resp = b''
        while b'</soapenv:Envelope>' not in resp:
            chunk = soap.recv(4096)
            if not chunk:
                log("SOAP 连接断开")
                break
            resp += chunk
        log(f"SOAP 响应: {len(resp)} bytes")
    except Exception as e:
        log(f"SOAP 错误: {e}")
    finally:
        soap.close()

    # 等待接收完成
    t.join(timeout=10)

    # 验证结果
    log("=" * 40)
    if received and len(received[0]) >= 1086:
        log("SUCCESS: streamsrc 帧接收成功!")
        log(f"帧 sync: {received[0][:4].hex()}")
        return True
    else:
        log(f"FAIL: streamsrc 帧未接收 (received: {len(received[0]) if received else 0} bytes)")
        return False

if __name__ == '__main__':
    test_streamsrc_push()
