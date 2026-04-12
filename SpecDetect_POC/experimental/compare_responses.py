# -*- coding: utf-8 -*-
"""
对比测试: 直连设备 vs 通过 rmcp_proxy 设备的响应差异

目标:
1. 发送相同请求到设备
2. 对比直连响应 vs 代理响应的差异
3. 分析设备拒绝直连的原因
"""

import socket
import struct
import time
import json
from datetime import datetime, timezone, timedelta

# 复用 soap_to_rmcp_direct 的帧构建函数
from soap_to_rmcp_direct import (
    build_action_xml,
    build_rmcp_frame,
    RMCP_HOST,
    RMCP_PORT,
    create_filetime,
    calculate_checksum
)


def send_raw_frame(host, port, frame, timeout=10):
    """发送原始 RMCP 帧并接收响应"""
    start_time = time.time()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.send(frame)

        # 接收所有数据 (设备可能返回多个包)
        response = b''
        while True:
            try:
                chunk = sock.recv(8192)
                if not chunk:
                    break
                response += chunk
                # 如果收到完整响应，停止
                if len(response) >= 19:
                    # 对于短响应(错误)，可能一次就收完
                    if response.startswith(b'RMTP') or len(response) >= 100:
                        break
                if time.time() - start_time > timeout:
                    break
            except socket.timeout:
                break

        elapsed = time.time() - start_time
        return response, elapsed


def analyze_response(response):
    """分析响应类型"""
    if not response:
        return {'type': 'EMPTY', 'hex': ''}

    if response.startswith(b'RMTP'):
        return {
            'type': 'RMTP_ERROR',
            'hex': response.hex(),
            'ascii': response.decode('ascii', errors='replace')
        }

    if len(response) >= 19:
        try:
            dwLength = struct.unpack('<I', response[0:4])[0]
            nVersion = response[13]
            nMsgType = response[14]

            return {
                'type': 'RMCP',
                'dwLength': dwLength,
                'nVersion': nVersion,
                'nMsgType': nMsgType,
                'hex': response.hex()
            }
        except:
            pass

    return {'type': 'UNKNOWN', 'hex': response.hex()}


def test_direct_connection():
    """测试直连设备"""
    print("\n" + "="*60)
    print("测试: 直连设备")
    print("="*60)

    # B_FScan SOAP 请求
    soap = '''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody><srrc:mfid>53090001140012</srrc:mfid>
<srrc:equpara><srrc:groupitems><srrc:groupitem><srrc:groupid>1</srrc:groupid>
<srrc:items><srrc:item><srrc:paraname>startfreq</srrc:paraname><srrc:paravalue>137000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>stopfreq</srrc:paraname><srrc:paravalue>173000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>step</srrc:paraname><srrc:paravalue>25000</srrc:paravalue></srrc:item>
</srrc:items></srrc:groupitem></srrc:groupitems></srrc:equpara>
</srrc:requestbody></soapenv:Body></soapenv:Envelope>'''

    action_xml = build_action_xml(soap)
    frame = build_rmcp_frame(action_xml)

    print(f"Sending frame: {len(frame)} bytes")
    print(f"Frame header: {frame[:19].hex()}")

    response, elapsed = send_raw_frame(RMCP_HOST, RMCP_PORT, frame)

    print(f"Received: {len(response)} bytes in {elapsed:.3f}s")
    analysis = analyze_response(response)
    print(f"Response type: {analysis.get('type')}")

    if analysis.get('type') == 'RMTP_ERROR':
        ascii_msg = analysis.get('ascii', '')[:50].encode('ascii', errors='replace').decode('ascii')
        print(f"RMTP Error (ASCII): {ascii_msg}")
    elif analysis.get('type') == 'RMCP':
        print(f"RMCP: nMsgType={analysis.get('nMsgType')}")

    print(f"Response hex (first 100 chars): {response.hex()[:100]}...")

    return {
        'method': 'direct',
        'frame_size': len(frame),
        'response_size': len(response),
        'response_type': analysis.get('type'),
        'response_hex': response.hex(),
        'analysis': analysis
    }


def test_via_proxy():
    """Test via rmcp_proxy (need manual trigger)"""
    print("\n" + "="*60)
    print("Test: Via rmcp_proxy")
    print("="*60)
    print("Hint: Send request via TestTool, rmcp_proxy will capture")
    print("Response data: see rmcp_proxy/capture/ directory")
    return None


def main():
    """Main test flow"""
    print("="*60)
    print("Direct Connection vs Proxy Response Comparison")
    print("="*60)

    results = {}

    # 1. Test direct connection
    try:
        results['direct'] = test_direct_connection()
    except Exception as e:
        print(f"Direct test failed: {e}")
        results['direct'] = {'error': str(e)}

    # 2. 保存结果
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    result_file = f'comparison_{timestamp}.json'

    # Convert bytes to hex for JSON serialization
    def convert_for_json(obj):
        if isinstance(obj, dict):
            return {k: convert_for_json(v) for k, v in obj.items()}
        elif isinstance(obj, bytes):
            return obj.hex()
        else:
            return obj

    with open(result_file, 'w', encoding='utf-8') as f:
        json.dump(convert_for_json(results), f, indent=2, ensure_ascii=False)

    print(f"\nResults saved to: {result_file}")

    # 3. Comparison analysis
    print("\n" + "="*60)
    print("Comparison Analysis")
    print("="*60)

    if 'direct' in results:
        r = results['direct']
        print(f"Direct response type: {r.get('response_type')}")
        print(f"Direct response size: {r.get('response_size')} bytes")

    print("\nNote: For rmcp_proxy responses, see capture directory")


if __name__ == '__main__':
    main()
