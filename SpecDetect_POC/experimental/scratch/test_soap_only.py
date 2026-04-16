#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""简单 SOAP 请求测试"""
import socket

# 创建 socket 连接
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.settimeout(10)

try:
    sock.connect(('127.0.0.1', 8282))

    soap_request = b'''POST /B_FScan HTTP/1.1\r
Host: 127.0.0.1:8282\r
Content-Type: text/xml; charset=utf-8\r
SOAPAction: B_FScan\r
Content-Length: 1047\r
\r
<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody>
<srrc:appid>123456</srrc:appid>
<srrc:userid>RX_admin</srrc:userid>
<srrc:priority>9</srrc:priority>
<srrc:executetime>0</srrc:executetime>
<srrc:mfid>53090001140012</srrc:mfid>
<srrc:equid>51cd8dfe-e543-40c9-bdc3-a292766fee7f</srrc:equid>
<srrc:equpara><srrc:groupitems><srrc:groupitem><srrc:groupid>1</srrc:groupid>
<srrc:items><srrc:item><srrc:paraname>startfreq</srrc:paraname><srrc:paravalue>137000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>stopfreq</srrc:paraname><srrc:paravalue>173000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>step</srrc:paraname><srrc:paravalue>25000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>gain</srrc:paraname><srrc:paravalue>AGC</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>rfworkmode</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>scanmode</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item>
</srrc:items></srrc:groupitem></srrc:groupitems></srrc:equpara>
<srrc:outputchannel><srrc:mode>source</srrc:mode><srrc:datachannel>stream</srrc:datachannel></srrc:outputchannel>
</srrc:requestbody></soapenv:Body></soapenv:Envelope>'''

    sock.send(soap_request)
    print("请求已发送")

    # 接收响应
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
    print(response.decode('utf-8', errors='replace')[:1000])

except Exception as e:
    print(f"错误: {e}")
finally:
    sock.close()