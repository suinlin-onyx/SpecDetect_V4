#!/usr/bin/env python3
import requests
import re
import time

ATOM_HOST = '127.0.0.1'
ATOM_PORT = 8282
HEADERS = {'Content-Type': 'text/xml; charset=utf-8'}

# B_QueryDeviceInfo
body = '''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody>
<srrc:appid>123456</srrc:appid>
<srrc:userid>RX_admin</srrc:userid>
<srrc:priority>9</srrc:priority>
<srrc:executetime>0</srrc:executetime>
<srrc:mfid>53090001140012</srrc:mfid>
<srrc:equid>51cd8dfe-e543-40c9-bdc3-a292766fee7f</srrc:equid>
<srrc:equpara><srrc:paraname>DeviceInfo</srrc:paraname></srrc:equpara>
</srrc:requestbody></soapenv:Body></soapenv:Envelope>'''

resp = requests.post(f'http://{ATOM_HOST}:{ATOM_PORT}/', data=body.encode(), headers=HEADERS, proxies={'http': None, 'https': None})
print(f'B_QueryDeviceInfo: {resp.status_code}')
print(f'Response length: {len(resp.content)}')

# 查找所有 taskid
taskids = re.findall(r'<srrc:taskid>([^<]+)</srrc:taskid>', resp.text)
print(f'Found taskids: {taskids}')

if taskids:
    taskid = taskids[0]
    print(f'Stopping task: {taskid}')

    # B_StopMeas
    stop_body = f'''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody>
<srrc:appid>123456</srrc:appid>
<srrc:userid>RX_admin</srrc:userid>
<srrc:mfid>53090001140012</srrc:mfid>
<srrc:equid>51cd8dfe-e543-40c9-bdc3-a292766fee7f</srrc:equid>
<srrc:equpara xsi:nil="true" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"/>
<srrc:taskid>{taskid}</srrc:taskid>
</srrc:requestbody></soapenv:Body></soapenv:Envelope>'''

    resp = requests.post(f'http://{ATOM_HOST}:{ATOM_PORT}/', data=stop_body.encode(), headers=HEADERS, proxies={'http': None, 'https': None})
    print(f'B_StopMeas: {resp.status_code}')
    time.sleep(2)
    print('Task stopped')
else:
    print('No taskid found in device info')