#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""停止之前的 B_FScan 任务"""
import socket

sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(10)

try:
    sock.connect(('127.0.0.1', 8282))

    soap_request = b'''POST /B_StopMeas HTTP/1.1\r
Host: 127.0.0.1:8282\r
Content-Type: text/xml; charset=utf-8\r
SOAPAction: B_StopMeas\r
Content-Length: 502\r
\r
<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody>
<srrc:appid>123456</srrc:appid>
<srrc:userid>RX_admin</srrc:userid>
<srrc:mfid>53090001140012</srrc:mfid>
<srrc:equid>51cd8dfe-e543-40c9-bdc3-a292766fee7f</srrc:equid>
<srrc:equpara xsi:nil="true" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"/>
<srrc:taskid>365E652C-3741-11F1-8000-00D8612F75B8</srrc:taskid>
</srrc:requestbody></soapenv:Body></soapenv:Envelope>'''

    sock.send(soap_request)
    print("停止请求已发送")

    response = b''
    while True:
        try:
            chunk = sock.recv(4096)
            if not chunk:
                break
            response += chunk
            if b'</soapenv:Envelope>' in response:
                break
        except socket.timeout:
            break

    print(f"收到响应: {len(response)} bytes")
    if b'BIZ-000001' in response:
        print("停止成功!")
    else:
        print("响应内容:")
        print(response.decode('utf-8', errors='replace')[:500])

except Exception as e:
    print(f"错误: {e}")
finally:
    sock.close()