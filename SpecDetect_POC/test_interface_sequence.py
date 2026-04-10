#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Real Atom 接口测试脚本
基于抓包数据验证的正确请求格式

测试流程: 发送请求 -> 等待回调 -> B_StopMeas -> 等待停止回调
"""

import requests
import xml.etree.ElementTree as ET
import time

# 配置
ATOM_URL = "http://127.0.0.1:8282/"
TIMEOUT = 30

# 通用请求头
HEADERS = {
    "Content-Type": "text/xml; charset=utf-8",
}

# 通用基础字段
BASE_FIELDS = """<srrc:appid>123456</srrc:appid>
<srrc:userid>RX_admin</srrc:userid>
<srrc:priority>9</srrc:priority>
<srrc:executetime>0</srrc:executetime>
<srrc:mfid>53090001140012</srrc:mfid>
<srrc:equid>51cd8dfe-e543-40c9-bdc3-a292766fee7f</srrc:equid>"""

OUTPUT_CHANNEL = """<srrc:outputchannel>
<srrc:mode>source</srrc:mode>
<srrc:datachannel>stream</srrc:datachannel>
</srrc:outputchannel>"""

# 接口定义
INTERFACES = {
    # 查询接口（无需 equpara）
    'B_QueryDeviceInfo': {
        'description': '监测功能查询',
        'equpara': None,  # 无需参数
    },
    'B_QueryFaciDevStat': {
        'description': '设备状态查询',
        'equpara': None,  # 无需参数
    },
    # 执行接口
    'B_SglFreqMeas': {
        'description': '单频测量',
        'equpara': """<srrc:items>
<srrc:item><srrc:paraname>frequency</srrc:paraname><srrc:paravalue>100000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>ifbw</srrc:paraname><srrc:paravalue>40000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>gain</srrc:paraname><srrc:paravalue>AGC</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>rfworkmode</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>audiotype</srrc:paraname><srrc:paravalue>off</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>demodmode</srrc:paraname><srrc:paravalue>FM</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>demodbw</srrc:paraname><srrc:paravalue>200000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>spectrumswitch</srrc:paraname><srrc:paravalue>on</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>ITUSwitch</srrc:paraname><srrc:paravalue>on</srrc:paravalue></srrc:item>
</srrc:items>"""
    },
    'B_SglFreqDF': {
        'description': '单频测向',
        'equpara': """<srrc:items>
<srrc:item><srrc:paraname>frequency</srrc:paraname><srrc:paravalue>100000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>dfmode</srrc:paraname><srrc:paravalue>1</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>ifbw</srrc:paraname><srrc:paravalue>40000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>gain</srrc:paraname><srrc:paravalue>AGC</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>rfworkmode</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>dftype</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>spectrumswitch</srrc:paraname><srrc:paravalue>on</srrc:paravalue></srrc:item>
</srrc:items>"""
    },
    'B_FScan': {
        'description': '频段扫描',
        'equpara': """<srrc:groupitems>
<srrc:groupitem><srrc:groupid>1</srrc:groupid>
<srrc:items>
<srrc:item><srrc:paraname>startfreq</srrc:paraname><srrc:paravalue>137000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>stopfreq</srrc:paraname><srrc:paravalue>173000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>step</srrc:paraname><srrc:paravalue>25000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>gain</srrc:paraname><srrc:paravalue>AGC</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>rfworkmode</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>scanmode</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item>
</srrc:items>
</srrc:groupitem></srrc:groupitems>"""
    },
    'B_PScan': {
        'description': '频谱扫描',
        'equpara': """<srrc:items>
<srrc:item><srrc:paraname>startfreq</srrc:paraname><srrc:paravalue>137000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>stopfreq</srrc:paraname><srrc:paravalue>173000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>step</srrc:paraname><srrc:paravalue>25000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>gain</srrc:paraname><srrc:paravalue>AGC</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>rfworkmode</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>keepmode</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item>
</srrc:items>"""
    },
    'B_WBDF': {
        'description': '宽带测向',
        'equpara': """<srrc:items>
<srrc:item><srrc:paraname>frequency</srrc:paraname><srrc:paravalue>100000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>ifbw</srrc:paraname><srrc:paravalue>40000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>gain</srrc:paraname><srrc:paravalue>AGC</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>rfworkmode</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item>
</srrc:items>"""
    },
    'B_MScan': {
        'description': '多信道扫描',
        'equpara': """<srrc:groupitems>
<srrc:groupitem><srrc:groupid>1</srrc:groupid>
<srrc:items>
<srrc:item><srrc:paraname>frequency</srrc:paraname><srrc:paravalue>100000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>ifbw</srrc:paraname><srrc:paravalue>40000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>gain</srrc:paraname><srrc:paravalue>AGC</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>rfworkmode</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item>
</srrc:items>
</srrc:groupitem></srrc:groupitems>"""
    },
    'B_MScanDF': {
        'description': '多信道扫描测向',
        'equpara': """<srrc:items>
<srrc:item><srrc:paraname>frequency</srrc:paraname><srrc:paravalue>100000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>dfmode</srrc:paraname><srrc:paravalue>1</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>ifbw</srrc:paraname><srrc:paravalue>40000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>gain</srrc:paraname><srrc:paravalue>AGC</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>rfworkmode</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item>
</srrc:items>"""
    },
    'B_FScanDF': {
        'description': '频段扫描测向',
        'equpara': """<srrc:items>
<srrc:item><srrc:paraname>startfreq</srrc:paraname><srrc:paravalue>137000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>stopfreq</srrc:paraname><srrc:paravalue>173000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>step</srrc:paraname><srrc:paravalue>25000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>rfworkmode</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>gain</srrc:paraname><srrc:paravalue>AGC</srrc:paravalue></srrc:item>
</srrc:items>"""
    },
}


def build_request(interface_name):
    """构建接口请求"""
    interface = INTERFACES.get(interface_name)
    if not interface:
        print(f"未知的接口: {interface_name}")
        return None

    # 查询接口（无 equpara）
    if interface['equpara'] is None:
        soap_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:ns1="base" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody>
{BASE_FIELDS}
<srrc:equpara xsi:nil="true"/>
</srrc:requestbody></soapenv:Body>
</soapenv:Envelope>"""
    else:
        # 执行接口（有 equpara）
        soap_body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:ns1="base" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody>
{BASE_FIELDS}
<srrc:equpara>{interface['equpara']}</srrc:equpara>
{OUTPUT_CHANNEL}
</srrc:requestbody></soapenv:Body>
</soapenv:Envelope>"""
    return soap_body


def build_stop_request(task_id):
    """构建停止请求"""
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:ns1="base" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody>
<srrc:appid>123456</srrc:appid>
<srrc:userid>RX_admin</srrc:userid>
<srrc:mfid>53090001140012</srrc:mfid>
<srrc:equid>51cd8dfe-e543-40c9-bdc3-a292766fee7f</srrc:equid>
<srrc:equpara xsi:nil="true"/>
<srrc:taskid>{task_id}</srrc:taskid>
</srrc:requestbody></soapenv:Body>
</soapenv:Envelope>"""


def send_request(interface_name, soap_action, body):
    """发送SOAP请求"""
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f'"{soap_action}"'
    }

    try:
        response = requests.post(
            ATOM_URL,
            data=body.encode('utf-8'),
            headers=headers,
            timeout=TIMEOUT
        )
        return response
    except Exception as e:
        print(f"请求失败: {e}")
        return None


def extract_task_id(response):
    """从响应中提取taskid"""
    if not response or response.status_code != 200:
        return None

    try:
        root = ET.fromstring(response.content)
        for elem in root.iter():
            if 'taskid' in elem.tag.lower():
                return elem.text
    except:
        pass
    return None


def test_interface(interface_name):
    """测试单个接口"""
    print("\n" + "="*60)
    print(f"测试: {interface_name} ({INTERFACES[interface_name]['description']})")
    print("="*60)

    # 构建请求
    request_body = build_request(interface_name)
    if not request_body:
        return False

    # 发送请求
    print("\n[1] 发送执行请求...")
    response = send_request(interface_name, interface_name, request_body)

    if not response:
        print("请求失败")
        return False

    print(f"响应状态: {response.status_code}")

    # 提取taskid
    task_id = extract_task_id(response)
    if task_id:
        print(f"获取到taskid: {task_id}")
    else:
        print("未获取到taskid，跳过停止步骤")
        return response.status_code == 200

    # 等待回调
    print("\n[2] 等待回调 (20秒)...")
    time.sleep(20)

    # 发送停止请求
    print("\n[3] 发送停止请求...")
    stop_body = build_stop_request(task_id)
    stop_response = send_request('B_StopMeas', 'B_StopMeas', stop_body)

    if stop_response:
        print(f"停止响应状态: {stop_response.status_code}")
    else:
        print("停止请求失败")

    # 等待停止回调
    print("\n[4] 等待停止回调 (10秒)...")
    time.sleep(10)

    return True


def main():
    """主函数"""
    print("="*60)
    print("Real Atom 接口测试")
    print("="*60)
    print(f"URL: {ATOM_URL}")
    print("="*60)

    # 测试顺序
    # 测试顺序（按文档标准顺序）
    test_order = [
        'B_QueryDeviceInfo',  # 查询接口（无需停止）
        'B_QueryFaciDevStat',  # 查询接口（无需停止）
        'B_FScan',             # 执行接口
        'B_FScanDF',
        'B_MScan',
        'B_MScanDF',
        'B_PScan',
        'B_SglFreqDF',
        'B_SglFreqMeas',
        'B_WBDF',
    ]

    for interface in test_order:
        result = test_interface(interface)
        if result:
            print(f"\n{interface} 测试完成")
        else:
            print(f"\n{interface} 测试失败")

    print("\n" + "="*60)
    print("全部测试完成")
    print("="*60)


if __name__ == "__main__":
    main()
