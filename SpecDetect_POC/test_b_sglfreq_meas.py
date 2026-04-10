#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 B_SglFreqMeas (单频测量)

测试流程: 发送请求 -> 等待回调 -> B_StopMeas -> 等待停止回调
"""

import requests
import xml.etree.ElementTree as ET
import time
import json

# 配置
ATOM_URL = "http://113.90.244.216:8282/"
TIMEOUT = 30

# B_SglFreqMeas 请求报文
SOAP_REQUEST = '''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:ns1="base" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody>
<srrc:mfid>53090001140012</srrc:mfid>
<srrc:equid>51cd8dfe-e543-40c9-bdc3-a292766fee7f</srrc:equid>
<srrc:equpara>
<srrc:items>
<srrc:item><srrc:paraname>frequency</srrc:paraname><srrc:paravalue>100000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>ifbw</srrc:paraname><srrc:paravalue>40000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>gain</srrc:paraname><srrc:paravalue>AGC</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>rfworkmode</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>audiotype</srrc:paraname><srrc:paravalue>off</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>demodmode</srrc:paraname><srrc:paravalue>FM</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>demodbw</srrc:paraname><srrc:paravalue>200000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>spectrumswitch</srrc:paraname><srrc:paravalue>on</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>ITUSwitch</srrc:paraname><srrc:paravalue>on</srrc:paravalue></srrc:item>
</srrc:items>
</srrc:equpara>
<srrc:resulttype>ITU,Audio</srrc:resulttype>
</srrc:requestbody></soapenv:Body>
</soapenv:Envelope>'''

# B_StopMeas 请求报文
STOP_REQUEST = '''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:ns1="base" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody>
<srrc:mfid>53090001140012</srrc:mfid>
<srrc:equid>51cd8dfe-e543-40c9-bdc3-a292766fee7f</srrc:equid>
</srrc:requestbody></soapenv:Body>
</soapenv:Envelope>'''


def send_request(url, soap_action, body, description):
    """发送SOAP请求"""
    print(f"\n{'='*60}")
    print(f"发送: {description}")
    print(f"{'='*60}")

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f'"{soap_action}"'
    }

    try:
        response = requests.post(
            url,
            data=body.encode('utf-8'),
            headers=headers,
            timeout=TIMEOUT
        )

        print(f"响应状态: {response.status_code}")

        if response.status_code == 200:
            # 解析响应
            root = ET.fromstring(response.content)

            ns = {
                'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/',
                'srrc': 'http://www.srrc.org.cn'
            }

            # 查找业务响应码
            biz_res_cd = None
            biz_res_text = None
            for elem in root.iter():
                if 'bizResCd' in elem.tag:
                    biz_res_cd = elem.text
                if 'bizResText' in elem.tag:
                    biz_res_text = elem.text

            if biz_res_cd:
                print(f"业务响应码: {biz_res_cd}")
            if biz_res_text:
                print(f"业务响应文本: {biz_res_text}")

            # 查找错误信息
            error = root.find('.//srrc:error', ns)
            if error is not None:
                err_type = error.find('srrc:type', ns)
                err_code = error.find('srrc:code', ns)
                err_text = error.find('srrc:text', ns)
                print(f"错误: {err_type.text if err_type is not None else ''} - {err_code.text if err_code is not None else ''} - {err_text.text if err_text is not None else ''}")

            # 保存响应
            filename = f"response_{description.replace(' ', '_')}_{int(time.time())}.xml"
            with open(filename, 'w', encoding='utf-8') as f:
                f.write(response.text)
            print(f"响应已保存: {filename}")

            return True, response

        return False, response

    except requests.exceptions.Timeout:
        print("请求超时")
        return False, None
    except Exception as e:
        print(f"请求失败: {e}")
        return False, None


def test_sglfreq_meas():
    """测试B_SglFreqMeas"""
    print("="*60)
    print("测试: B_SglFreqMeas (单频测量)")
    print("="*60)
    print(f"URL: {ATOM_URL}")
    print()

    # 步骤1: 发送B_SglFreqMeas请求
    success, response = send_request(
        ATOM_URL,
        "B_SglFreqMeas",
        SOAP_REQUEST,
        "B_SglFreqMeas"
    )

    if not success:
        print("\nB_SglFreqMeas 请求失败")
        return False

    # 等待回调 (20秒)
    print("\n等待回调 (20秒)...")
    time.sleep(20)

    # 步骤2: 发送B_StopMeas停止请求
    success, response = send_request(
        ATOM_URL,
        "B_StopMeas",
        STOP_REQUEST,
        "B_StopMeas"
    )

    if not success:
        print("\nB_StopMeas 请求失败")
        return False

    # 等待停止回调 (10秒)
    print("\n等待停止回调 (10秒)...")
    time.sleep(10)

    print("\n" + "="*60)
    print("测试流程完成")
    print("="*60)

    return True


if __name__ == "__main__":
    test_sglfreq_meas()
