#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试监测功能查询 (B_QueryDeviceInfo)

使用抓包获取的完整报文格式进行测试
"""

import requests
import xml.etree.ElementTree as ET

# 配置
ATOM_URL = "http://113.90.244.216:8282/"
TIMEOUT = 30

# 完整的请求报文（抓包获取）
SOAP_REQUEST = '''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:SOAP-ENC="http://schemas.xmlsoap.org/soap/encoding/" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" xmlns:xsd="http://www.w3.org/2001/XMLSchema" xmlns:ns1="base" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody>
<srrc:mfid>53090001140012</srrc:mfid>
<srrc:equid>51cd8dfe-e543-40c9-bdc3-a292766fee7f</srrc:equid>
<srrc:equpara xsi:nil="true"/>
</srrc:requestbody></soapenv:Body>
</soapenv:Envelope>'''

def test_monitoring_query():
    """测试监测功能查询"""
    print("="*60)
    print("测试: 监测功能查询 (B_QueryDeviceInfo)")
    print("="*60)
    print(f"URL: {ATOM_URL}")
    print()

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": '"B_QueryDeviceInfo"'
    }

    try:
        print("发送请求...")
        response = requests.post(
            ATOM_URL,
            data=SOAP_REQUEST.encode('utf-8'),
            headers=headers,
            timeout=TIMEOUT
        )

        print(f"响应状态: {response.status_code}")
        print(f"响应头: {dict(response.headers)}")
        print()

        if response.status_code == 200:
            # 解析XML响应
            root = ET.fromstring(response.content)

            # 定义命名空间
            ns = {
                'soapenv': 'http://schemas.xmlsoap.org/soap/envelope/',
                'srrc': 'http://www.srrc.org.cn'
            }

            # 查找ProviderResponse
            provider = root.find('.//srrc:bizResCd', ns) or root.find('.//srrc:ProviderResponse/srrc:bizResCd', ns)
            if provider is None:
                # 尝试不带命名空间
                for elem in root.iter():
                    if 'bizResCd' in elem.tag:
                        provider = elem
                        break

            if provider is not None:
                print(f"业务响应码: {provider.text}")

            # 查找设备信息
            equimanu = root.find('.//srrc:equimanu', ns)
            equmodel = root.find('.//srrc:equmodel', ns)
            equname = root.find('.//srrc:equname', ns)
            equsn = root.find('.//srrc:equsn', ns)
            equstatus = root.find('.//srrc:equstatus', ns)

            print()
            print("设备信息:")
            if equimanu is not None:
                print(f"  厂商: {equimanu.text}")
            if equmodel is not None:
                print(f"  型号: {equmodel.text}")
            if equname is not None:
                print(f"  名称: {equname.text}")
            if equsn is not None:
                print(f"  序列号: {equsn.text}")
            if equstatus is not None:
                print(f"  状态: {equstatus.text}")

            # 统计feature数量
            features = root.findall('.//srrc:feature', ns)
            if features:
                print(f"\n功能列表 ({len(features)} 个):")
                for f in features:
                    code = f.find('srrc:code', ns)
                    if code is not None:
                        print(f"  - {code.text}")

            print()
            print("✅ 测试成功!")

            # 保存完整响应
            with open('test_monitoring_query_response.xml', 'w', encoding='utf-8') as f:
                f.write(response.text)
            print("响应已保存到: test_monitoring_query_response.xml")

        else:
            print("❌ 测试失败")
            print(response.text[:500])

    except requests.exceptions.Timeout:
        print("❌ 请求超时")
    except Exception as e:
        print(f"❌ 请求失败: {e}")

if __name__ == "__main__":
    test_monitoring_query()
