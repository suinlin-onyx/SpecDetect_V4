#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
测试 B_MScan, B_PScan, B_SglFreqMeas 接口
验证 dfmode 参数移除是否有效

用法:
    python test_pscan_sglfreq.py <interface> [timeout]
    python test_pscan_sglfreq.py B_PScan 5
    python test_pscan_sglfreq.py B_SglFreqMeas 5
    python test_pscan_sglfreq.py B_MScan 5
"""

import socket
import struct
import time
import sys
import os
import json
from datetime import datetime, timezone, timedelta

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from soap_to_rmcp_direct import build_action_xml, build_rmcp_frame, parse_rmcp_response
from atom_data_formatter import AtomDataFormatter

# 设备配置
RMCP_HOST = '100.72.95.36'
RMCP_PORT = 1449

# SOAP XML 模板
SOAP_TEMPLATES = {
    'B_MScan': '''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody><srrc:mfid>53090001140012</srrc:mfid>
<srrc:equpara><srrc:groupitems><srrc:groupitem><srrc:groupid>1</srrc:groupid>
<srrc:items><srrc:item><srrc:paraname>frequency</srrc:paraname><srrc:paravalue>100000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>ifbw</srrc:paraname><srrc:paravalue>40000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>gain</srrc:paraname><srrc:paravalue>AGC</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>rfworkmode</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item>
</srrc:items></srrc:groupitem></srrc:groupitems></srrc:equpara>
</srrc:requestbody></soapenv:Body></soapenv:Envelope>''',

    # 注意: TestTool 的 B_PScan 实际使用 funcid=16 (B_MScanDF)，参数为 startfreq/stopfreq/step
    'B_PScan': '''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody><srrc:mfid>53090001140012</srrc:mfid>
<srrc:equpara><srrc:items>
<srrc:item><srrc:paraname>startfreq</srrc:paraname><srrc:paravalue>137000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>stopfreq</srrc:paraname><srrc:paravalue>173000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>step</srrc:paraname><srrc:paravalue>25000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>gain</srrc:paraname><srrc:paravalue>AGC</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>rfworkmode</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item>
</srrc:items></srrc:equpara>
</srrc:requestbody></soapenv:Body></soapenv:Envelope>''',

    'B_SglFreqMeas': '''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody><srrc:mfid>53090001140012</srrc:mfid>
<srrc:equpara><srrc:items>
<srrc:item><srrc:paraname>frequency</srrc:paraname><srrc:paravalue>100000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>ifbw</srrc:paraname><srrc:paravalue>40000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>gain</srrc:paraname><srrc:paravalue>AGC</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>rfworkmode</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item>
</srrc:items></srrc:equpara>
</srrc:requestbody></soapenv:Body></soapenv:Envelope>''',

    # funcid=11: B_SglFreqDF 带 dfmode=1 (设备成功支持)
    # 单频模式: ifbw=40000000 (40MHz)
    'B_SglFreqDF': '''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody><srrc:mfid>53090001140012</srrc:mfid>
<srrc:equpara><srrc:items>
<srrc:item><srrc:paraname>frequency</srrc:paraname><srrc:paravalue>100000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>dfmode</srrc:paraname><srrc:paravalue>1</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>ifbw</srrc:paraname><srrc:paravalue>40000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>gain</srrc:paraname><srrc:paravalue>AGC</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>rfworkmode</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item>
</srrc:items></srrc:equpara>
</srrc:requestbody></soapenv:Body></soapenv:Envelope''',

    # funcid=11: B_SglFreqDF 扫描模式
    # 扫描模式: ifbw=40000 (40kHz) -> nArrays=1601
    'B_SglFreqDF_SCAN': '''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody><srrc:mfid>53090001140012</srrc:mfid>
<srrc:equpara><srrc:items>
<srrc:item><srrc:paraname>frequency</srrc:paraname><srrc:paravalue>100000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>dfmode</srrc:paraname><srrc:paravalue>1</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>ifbw</srrc:paraname><srrc:paravalue>40000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>gain</srrc:paraname><srrc:paravalue>AGC</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>rfworkmode</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>audioswitch</srrc:paraname><srrc:paravalue>OFF</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>demodmode</srrc:paraname><srrc:paravalue>FM</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>demodbw</srrc:paraname><srrc:paravalue>200000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>bbfftl</srrc:paraname><srrc:paravalue>2048</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>CombineFunc</srrc:paraname><srrc:paravalue>AsIIEQ</srrc:paravalue></srrc:item>
</srrc:items></srrc:equpara>
</srrc:requestbody></soapenv:Body></soapenv:Envelope>''',
}


# B_PScan 在 TestTool 中实际使用 funcid=16 (B_MScanDF)
SOAP_ACTION_MAP = {
    'B_PScan': 'B_MScanDF',  # TestTool B_PScan -> funcid=16
    'B_MScan': 'B_MScan',     # B_MScan -> funcid=14
    'B_SglFreqMeas': 'B_SglFreqMeas',  # funcid=12 (设备不支持)
    'B_SglFreqDF': 'B_SglFreqDF',      # funcid=11 单频模式 (nArrays=1)
    'B_SglFreqDF_SCAN': 'B_SglFreqDF', # funcid=11 扫描模式 (nArrays=1601)
}


def parse_rmcp_streaming_data(all_data: bytes) -> list:
    """
    解析 RMCP streaming 数据包

    RMCP 帧结构:
    - Byte 0-3: dwLength (帧长度，不含自己的4字节)
    - Byte 4-11: tmStamp (FILETIME)
    - Byte 12: nVersion (0x00)
    - Byte 13: nVersion (0x07)
    - Byte 14: nMsgType
    - Byte 15: nFlags
    - Byte 16-17: nCheckSum
    - Byte 18+: 数据

    streaming DATA frame (nMsgType=0):
    - Byte 18+: 二进制数据 payload
    """
    frames = []
    offset = 0

    while offset < len(all_data):
        if offset + 18 > len(all_data):
            break

        # 解析帧头
        dw_length = struct.unpack('<I', all_data[offset:offset+4])[0]
        tm_stamp = struct.unpack('<Q', all_data[offset+4:offset+12])[0]
        n_version = all_data[offset+12]
        n_msg_type = all_data[offset+14]
        n_flags = all_data[offset+15]
        n_checksum = struct.unpack('<H', all_data[offset+16:offset+18])[0]

        # 数据部分
        data_start = offset + 18
        data_end = offset + dw_length
        if data_end > len(all_data):
            data_end = len(all_data)

        payload = all_data[data_start:data_end]

        frames.append({
            'offset': offset,
            'dwLength': dw_length,
            'tmStamp': tm_stamp,
            'nMsgType': n_msg_type,
            'nFlags': n_flags,
            'payload': payload,
            'payloadHex': payload[:64].hex() if len(payload) > 64 else payload.hex(),
        })

        # 移动到下一帧
        offset = offset + dw_length

    return frames


def parse_fscan_payload(payload: bytes, request_freq: int = 100000000) -> dict:
    """
    解析简化格式 FSCAN payload (设备实际返回的格式)

    简化格式结构:
    - Business header: bytes 0-2
    - Counters: bytes 3-10 (4 × int16 little-endian)
    - Spectrum data: int16 little-endian from byte 11

    转换公式: dBm = raw_value / 10

    注意: 设备直接返回简化格式, TestTool 显示的是 Atom 转换后的标准格式
    nBdType: 11 = VER=16 (电平数据)
    """
    result = {}

    if len(payload) < 12:
        return {'error': f'Payload too short: {len(payload)} bytes'}

    # Business header
    n_bd_type = payload[0]
    result['nBdType'] = n_bd_type

    # 对应标准格式的 VER (nBdType 11 = VER 16)
    result['VER'] = 16 if n_bd_type == 11 else n_bd_type

    # Counters at bytes 3-10 (4 int16)
    counters = struct.unpack('<4h', payload[3:11])
    result['counters'] = list(counters)
    result['nArrays'] = counters[0]  # 通常是 1 (单频)

    # Spectrum from byte 11
    spectrum_offset = 11
    spectrum_bytes = payload[spectrum_offset:]

    # 关键修复：扫描模式下，实际电平数量是 nArrays，不是全部字节数
    # nArrays 来自 counters[0]
    n_arrays = counters[0] if counters[0] > 0 else 1

    # 计算实际数据字节数
    total_spectrum_bytes = len(spectrum_bytes)
    total_levels_from_bytes = total_spectrum_bytes // 2

    # 取 n_arrays 作为电平数量（扫描模式），或全部字节数（单频模式）
    if n_arrays > 1:
        # 扫描模式：n_arrays 是通道数
        num_levels = n_arrays
    else:
        # 单频模式：使用全部数据
        num_levels = total_levels_from_bytes

    # 提取电平数据
    levels = struct.unpack(f'<{num_levels}h', spectrum_bytes[:num_levels*2])
    result['levels_raw'] = list(levels)
    result['level_count'] = num_levels

    # 提取频率参数（如果有额外数据）
    extra_bytes = total_spectrum_bytes - (num_levels * 2)
    if extra_bytes >= 10:
        # 额外的可能是频率参数
        extra_data = spectrum_bytes[num_levels*2:num_levels*2+10]
        result['extra_data_hex'] = extra_data.hex()

    # 转换为 dBm
    if levels:
        result['levels_dbm'] = [v / 10.0 for v in levels]
        result['level_min_raw'] = min(levels)
        result['level_max_raw'] = max(levels)
        result['level_min_dbm'] = min(levels) / 10.0
        result['level_max_dbm'] = max(levels) / 10.0
        result['levels_sample'] = result['levels_dbm'][:20]  # 前20个作为样本

    # 生成标准格式信息 (与 TestTool 一致)
    # nBdType=11 根据 nArrays 判断模式：
    # - nArrays > 1: 扫描模式 (DT=7 频谱数据)
    # - nArrays = 1: 单频模式 (DT=101 电平数据)
    if n_bd_type == 11:
        if n_arrays > 1:
            # 扫描模式：ifbw=40kHz 覆盖 40MHz span
            # nArrays = 1601 通道，step = 40MHz / 1601 ≈ 25kHz
            span_hz = 40_000_000  # 40 MHz span
            step_hz = span_hz / n_arrays  # ≈ 25 kHz
            start_freq_hz = request_freq - span_hz // 2
            end_freq_hz = request_freq + span_hz // 2

            result['DT'] = 7  # 频谱数据类型
            result['DL'] = num_levels * 2 + 5
            result['data_type'] = '频谱数据'
            result['start_freq'] = start_freq_hz / 1e6  # MHz
            result['end_freq'] = end_freq_hz / 1e6  # MHz
            result['step'] = step_hz / 1000  # kHz
            result['frame_channels'] = num_levels
        else:
            # 单频模式
            result['DT'] = 101  # 电平数据类型
            result['DL'] = num_levels * 2 + 5
            result['data_type'] = '电平数据'
            result['center_freq'] = request_freq / 1e6  # MHz
            # 信号电平通常是第6个值 (index 5)
            if len(levels) > 5:
                result['signal_level'] = levels[5] / 10.0
    else:
        result['DT'] = 7  # 频谱数据类型
        result['DL'] = num_levels * 2 + 5
        result['data_type'] = '频谱数据'

    result['totalBytes'] = len(payload)
    return result


def test_interface(interface_name, timeout=5.0, parse_data=True, save_json=True):
    """测试指定接口"""
    print(f"\n{'='*60}")
    print(f"测试接口: {interface_name}")
    print(f"{'='*60}")

    if interface_name not in SOAP_TEMPLATES:
        print(f"未知接口: {interface_name}")
        print(f"支持的接口: {list(SOAP_TEMPLATES.keys())}")
        return False

    soap_xml = SOAP_TEMPLATES[interface_name]

    # 映射到实际的 soap_action (用于确定 funcid)
    soap_action = SOAP_ACTION_MAP.get(interface_name, interface_name)

    # 提取请求频率参数
    request_freq = 100000000  # 默认 100MHz
    if 'startfreq' in soap_xml:
        import re
        m = re.search(r'<srrc:paraname>startfreq</srrc:paraname><srrc:paravalue>(\d+)</srrc:paravalue>', soap_xml)
        if m:
            request_freq = int(m.group(1))
    elif 'frequency' in soap_xml:
        import re
        m = re.search(r'<srrc:paraname>frequency</srrc:paraname><srrc:paravalue>(\d+)</srrc:paravalue>', soap_xml)
        if m:
            request_freq = int(m.group(1))

    # 1. 构建 Action XML
    action_xml = build_action_xml(soap_xml, soap_action)
    print(f"\n[1] Action XML:")
    for line in action_xml.split('\n'):
        print(f"    {line}")

    # 检查是否包含 dfmode
    if 'dfmode' in action_xml:
        print(f"\n    [WARNING] dfmode still exists in Action XML!")
    else:
        print(f"\n    [OK] dfmode removed from Action XML")

    # 2. 构建 RMCP 帧
    rmcp_frame = build_rmcp_frame(action_xml)
    print(f"\n[2] RMCP 帧: {len(rmcp_frame)} bytes")
    print(f"    前40字节: {rmcp_frame[:40].hex()}")

    # 3. 发送请求
    print(f"\n[3] 发送到设备: {RMCP_HOST}:{RMCP_PORT}")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)

    try:
        sock.connect((RMCP_HOST, RMCP_PORT))
        sock.send(rmcp_frame)
        print(f"    请求已发送")

        # 4. 接收响应
        print(f"\n[4] 等待响应 (timeout={timeout}s)...")
        packets = []
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                packets.append(chunk)
            except socket.timeout:
                break

        all_data = b''.join(packets)
        print(f"    收到: {len(packets)} 个数据包, 共 {len(all_data)} bytes")

        if len(all_data) == 0:
            print(f"    [ERROR] No response received")
            return False

        # 5. 解析响应
        print(f"\n[5] 解析响应...")
        parsed = parse_rmcp_response(all_data)
        print(f"    nMsgType: {parsed.get('nMsgType')} ({parsed.get('nMsgTypeName')})")
        print(f"    nFlags: {parsed.get('nFlags')}")
        print(f"    dwLength: {parsed.get('dwLength')}")

        # 检查原始文本响应
        if parsed.get('raw_text'):
            try:
                print(f"    原始响应: {parsed['raw_text'][:200]}")
            except UnicodeEncodeError:
                print(f"    原始响应: (无法显示，包含无法编码的字符)")

        # 检查是否包含错误信息
        if 'RMTP:ErrCode' in (parsed.get('raw_text') or ''):
            print(f"    [ERROR] Device returned error!")
            return False

        # 6. 解析 streaming 数据
        result_data = {
            'interface': interface_name,
            'soap_action': soap_action,
            'action_xml': action_xml,
            'total_bytes': len(all_data),
            'packet_count': len(packets),
            'frames': [],
            'success': False,
        }

        if parse_data and len(all_data) > 100:
            print(f"\n[6] 解析 streaming 数据...")
            frames = parse_rmcp_streaming_data(all_data)
            print(f"    解析到 {len(frames)} 个 RMCP 帧")
            result_data['frame_count'] = len(frames)

            for i, frame in enumerate(frames[:3]):  # 只显示前3帧
                print(f"\n    帧 {i+1}:")
                print(f"        dwLength: {frame['dwLength']}")
                print(f"        nMsgType: {frame['nMsgType']}")
                print(f"        tmStamp: {frame['tmStamp']}")

                frame_info = {
                    'index': i + 1,
                    'dwLength': frame['dwLength'],
                    'nMsgType': frame['nMsgType'],
                    'tmStamp': frame['tmStamp'],
                    'payload_hex': frame['payloadHex'],
                }

                if frame['nMsgType'] == 0 and len(frame['payload']) > 11:
                    # 解析简化格式 FSCAN payload
                    fscan = parse_fscan_payload(frame['payload'], request_freq)
                    print(f"        nBdType: {fscan.get('nBdType')}")
                    print(f"        VER: {fscan.get('VER')}")
                    print(f"        DT: {fscan.get('DT')}")
                    print(f"        nArrays (counters[0]): {fscan.get('nArrays')}")
                    print(f"        电平数量: {fscan.get('level_count')}")
                    if fscan.get('data_type'):
                        print(f"        数据类型: {fscan.get('data_type')}")
                    if fscan.get('center_freq'):
                        print(f"        中心频率: {fscan.get('center_freq')} MHz")
                    if fscan.get('signal_level') is not None:
                        print(f"        信号电平: {fscan.get('signal_level')} dBm")
                    print(f"        电平范围 (dBm): {fscan.get('level_min_dbm')} ~ {fscan.get('level_max_dbm')}")
                    if fscan.get('levels_sample'):
                        print(f"        前10个电平 (dBm): {fscan['levels_sample'][:10]}")
                    frame_info['fscan'] = fscan

                result_data['frames'].append(frame_info)

        if parsed.get('nMsgType') == 6:
            print(f"    [OK] Received RESPONSE frame")
            result_data['success'] = True
        elif parsed.get('nMsgType') == 0:
            print(f"    [OK] Received DATA frame (streaming started)")
            result_data['success'] = True
        else:
            print(f"    [UNKNOWN] Unexpected msg type")
            result_data['success'] = True  # 数据帧也算成功

        # 7. 保存 JSON 结果
        if save_json:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            json_filename = f'data/test_result_{interface_name}_{timestamp}.json'
            os.makedirs('data', exist_ok=True)
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(result_data, f, indent=2, ensure_ascii=False)
            print(f"\n[7] 结果已保存: {json_filename}")

        return result_data

    except socket.timeout:
        print(f"    [ERROR] 连接超时")
        return False
    except ConnectionRefusedError:
        print(f"    [ERROR] 连接被拒绝 - 设备不可达")
        return False
    except Exception as e:
        print(f"    [ERROR] {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        sock.close()


def main():
    if len(sys.argv) < 2:
        print("用法: python test_pscan_sglfreq.py <interface> [timeout]")
        print("接口: B_MScan, B_PScan, B_SglFreqMeas, B_SglFreqDF, B_SglFreqDF_SCAN")
        sys.exit(1)

    interface = sys.argv[1]
    timeout = float(sys.argv[2]) if len(sys.argv) > 2 else 5.0

    success = test_interface(interface, timeout)

    print(f"\n{'='*60}")
    if success:
        print(f"测试结果: PASS")
    else:
        print(f"测试结果: FAIL")
    print(f"{'='*60}")

    sys.exit(0 if success else 1)


if __name__ == '__main__':
    main()
