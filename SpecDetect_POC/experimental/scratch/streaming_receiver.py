# -*- coding: utf-8 -*-
"""
Streaming接口数据接收脚本

功能:
1. 发送Streaming请求到设备
2. 持续接收设备推送的DATA帧
3. 解析FSCAN数据格式
4. 保存到本地CSV文件
"""

import socket
import struct
import time
import csv
import os
import json
from datetime import datetime
from typing import List, Tuple, Optional

# Atom 数据整理器
from atom_data_formatter import AtomDataFormatter, format_streaming_frame

# SOAP to RMCP converter
from soap_to_rmcp_direct import build_rmcp_frame

# RMCP常量
RMCP_HOST = '100.72.95.36'
RMCP_PORT = 1449


def parse_fscan_data(frame_data: bytes) -> Optional[dict]:
    """解析FSCAN数据帧

    Returns:
        dict: 包含解析结果，或None如果解析失败
    """
    if len(frame_data) < 18:
        return None

    try:
        # RMCPTP帧头 (18字节)
        dwLength = struct.unpack('<I', frame_data[0:4])[0]
        tmStamp = struct.unpack('<Q', frame_data[4:12])[0]
        nVersion = frame_data[13]
        nMsgType = frame_data[14]
        nFlags = frame_data[15]
        nCheckSum = struct.unpack('<H', frame_data[16:18])[0]

        result = {
            'dwLength': dwLength,
            'tmStamp': tmStamp,
            'nVersion': nVersion,
            'nMsgType': nMsgType,
            'nFlags': nFlags,
            'nCheckSum': nCheckSum,
            'levels': [],
            'frame_channels': 0,
            'band_no': 0,
            'start_freq': 0.0,
            'end_freq': 0.0,
            'step': 0.0,
            'total_channels': 0
        }

        payload = frame_data[18:]

        # 检查是否为FSCAN格式 (LEADER=0xEEEE1DE6)
        # 注意：有符号整数-286331154的十六进制是0xEEEE1DE6
        is_fscan = False
        if len(payload) >= 23:
            leader_le = struct.unpack('<I', payload[0:4])[0]
            leader_be = struct.unpack('>I', payload[0:4])[0]
            if leader_le == 0xEEEE1DE6 or leader_le == 4007718438 or leader_be == 0xEEEE1DE6:
                is_fscan = True

        if is_fscan:
            # FSCAN格式解析
            # FSCAN头: LEADER(4) + VER(1) + STC(4) + TS(8) + PL(4) + EL(2) = 23 bytes
            leader = struct.unpack('<i', payload[0:4])[0]  # 有符号整数
            result['leader'] = leader
            result['version'] = payload[4]
            result['stc'] = struct.unpack('<I', payload[5:9])[0]
            result['ts'] = struct.unpack('<Q', payload[9:17])[0]
            result['pl'] = struct.unpack('<I', payload[17:21])[0]
            result['el'] = struct.unpack('<H', payload[21:23])[0]

            offset = 23

            # DT(1) + DL(4)
            if len(payload) - offset >= 5:
                result['dt'] = payload[offset]
                offset += 1
                result['dl'] = struct.unpack('<I', payload[offset:offset+4])[0]
                offset += 4

            # 频段信息 (28 bytes)
            if len(payload) - offset >= 28:
                result['band_no'] = struct.unpack('<I', payload[offset:offset+4])[0]
                offset += 4
                result['total_channels'] = struct.unpack('<I', payload[offset:offset+4])[0]
                offset += 4
                result['start_freq'] = struct.unpack('<d', payload[offset:offset+8])[0]
                offset += 8
                result['end_freq'] = struct.unpack('<d', payload[offset:offset+8])[0]
                offset += 8
                result['start_index'] = struct.unpack('<I', payload[offset:offset+4])[0]
                offset += 4
                result['step'] = struct.unpack('<d', payload[offset:offset+8])[0]
                offset += 8

            # 帧信道数量 (4 bytes)
            if len(payload) - offset >= 4:
                result['frame_channels'] = struct.unpack('<I', payload[offset:offset+4])[0]
                offset += 4

            # 电平数据: FSCAN格式中电平是直接dBm值，不需要除以256
            levels = []
            while offset + 2 <= len(payload):
                level = struct.unpack('<h', payload[offset:offset+2])[0]
                levels.append(level)
                offset += 2

            result['levels'] = levels
            result['level_count'] = len(levels)
            result['data_format'] = 'fscan'
        else:
            # 直连数据格式: 从payload偏移11开始，每2字节是有符号整数
            # 需要除以10得到dBm值 (原始数据是dBm×10)
            if len(payload) > 11:
                levels = []
                offset = 11
                while offset + 1 < len(payload):
                    val = struct.unpack('<h', payload[offset:offset+2])[0]
                    # 转换为dBm (原值除以10)
                    dbm = round(val / 10.0, 1)
                    levels.append(dbm)
                    offset += 2
                result['levels'] = levels
                result['level_count'] = len(levels)
                result['data_format'] = 'direct'

        return result

    except Exception as e:
        return {'error': str(e)}


def stop_streaming(sock: socket.socket) -> bool:
    """发送停止测量请求 (B_StopMeas)

    Args:
        sock: 已连接的socket

    Returns:
        是否成功
    """
    import sys
    sys.path.insert(0, 'experimental')
    from soap_to_rmcp_direct import build_action_xml

    print("  发送停止测量请求...")

    # B_StopMeas SOAP
    stop_soap = '''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
<soapenv:Body>
<srrc:requestbody xmlns:srrc="http://www.srrc.org.cn">
<srrc:mfid>53090001150015</srrc:mfid>
<srrc:equid>51cd8dfe-e543-40c9-bdc3-a292766fee7f</srrc:equid>
<srrc:equpara>
<srrc:items>
</srrc:items>
</srrc:equpara>
</srrc:requestbody>
</soapenv:Body>
</soapenv:Envelope>'''

    try:
        # 构建 RMCP 帧
        action_xml = build_action_xml(stop_soap, 'B_StopMeas')
        frame = build_rmcp_frame(action_xml)

        # 发送停止请求
        sock.send(frame)
        print("  停止请求已发送")

        # 等待响应
        sock.settimeout(5.0)
        response = b''
        try:
            while True:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
                if len(response) >= 18:
                    dwLen = struct.unpack('<I', response[0:4])[0]
                    if len(response) >= dwLen:
                        break
        except socket.timeout:
            pass

        if response:
            print(f"  收到停止响应: {len(response)} bytes")
            return True
        else:
            print("  未收到停止响应")
            return False

    except Exception as e:
        print(f"  停止请求失败: {e}")
        return False


def receive_streaming_data(sock: socket.socket, timeout: float = 60.0,
                          request_params: dict = None) -> List[dict]:
    """持续接收streaming数据

    Args:
        sock: 已连接的socket
        timeout: 接收超时时间(秒)
        request_params: 请求参数，用于 AtomDataFormatter 填充元数据

    Returns:
        数据帧列表
    """
    frames = []
    all_data = b''  # 保存原始数据用于调试
    start_time = time.time()
    sock.settimeout(2.0)  # 每2秒检查一次是否超时

    print(f"  开始接收数据 (超时: {timeout}秒)...")

    # 检查socket状态
    print(f"  Socket状态: {sock.fileno()}")

    try:
        recv_buffer = b''  # 接收缓冲区，处理跨包帧
        while time.time() - start_time < timeout:
            try:
                chunk = sock.recv(8192)
                if not chunk:
                    print("  设备断开连接")
                    break
                recv_buffer += chunk

                # 解析接收缓冲区中的所有完整帧
                while len(recv_buffer) >= 18:  # 至少要有帧头
                    # 读取dwLength
                    dwLength = struct.unpack('<I', recv_buffer[0:4])[0]

                    # 检查是否收到完整帧
                    if len(recv_buffer) < dwLength:
                        # 等待更多数据
                        break

                    # 提取完整帧
                    frame_data = recv_buffer[:dwLength]
                    recv_buffer = recv_buffer[dwLength:]

                    # 解析帧
                    nMsgType = frame_data[14] if len(frame_data) > 14 else 0

                    if nMsgType == 0:  # DATA frame
                        if request_params:
                            # 使用 AtomDataFormatter 进行解析
                            tmstamp = struct.unpack('<Q', frame_data[4:12])[0]
                            fscan_result = format_streaming_frame(frame_data, tmstamp, request_params)
                            fscan_result['dwLength'] = dwLength
                            fscan_result['nMsgType'] = nMsgType
                        else:
                            fscan_result = parse_fscan_data(frame_data)

                        if fscan_result and 'error' not in fscan_result:
                            frames.append(fscan_result)
                            elapsed = time.time() - start_time
                            print(f"  [{elapsed:.1f}s] 收到DATA帧: {len(fscan_result.get('levels', []))} 电平")
                    elif nMsgType == 6:  # RESPONSE
                        elapsed = time.time() - start_time
                        print(f"  [{elapsed:.1f}s] 收到RESPONSE帧")
            except socket.timeout:
                # 检查是否超时
                if time.time() - start_time >= timeout:
                    print("  接收超时")
                    break
                continue

    except Exception as e:
        print(f"  接收异常: {e}")

    return frames


def save_to_csv(frames: List[dict], output_file: str):
    """保存数据到CSV文件

    Args:
        frames: 数据帧列表
        output_file: 输出文件路径
    """
    if not frames:
        print("  没有数据可保存")
        return

    os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)

        # 写入表头
        first = frames[0]
        freq_count = first.get('frame_channels', 0) or len(first.get('levels', []))

        header = ['timestamp', 'frame_channels', 'band_no', 'total_channels',
                  'start_freq_MHz', 'end_freq_MHz', 'step_kHz']
        for i in range(freq_count):
            header.append(f'freq_{i}')
        writer.writerow(header)

        # 写入数据
        for i, frame in enumerate(frames):
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
            row = [
                timestamp,
                frame.get('frame_channels', 0),
                frame.get('band_no', 0),
                frame.get('total_channels', 0),
                frame.get('start_freq', 0) / 1e6,
                frame.get('end_freq', 0) / 1e6,
                frame.get('step', 0) / 1e3
            ]
            levels = frame.get('levels', [])
            row.extend(levels[:freq_count])
            writer.writerow(row)

    print(f"  已保存 {len(frames)} 帧数据到: {output_file}")


def save_to_json(frames: List[dict], output_file: str):
    """保存数据到JSON文件

    Args:
        frames: 数据帧列表
        output_file: 输出文件路径
    """
    if not frames:
        print("  没有数据可保存")
        return

    os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)

    output_data = {
        'timestamp': datetime.now().isoformat(),
        'frame_count': len(frames),
        'frames': []
    }

    for i, frame in enumerate(frames):
        frame_data = {
            '帧索引': i,
            '帧长度': frame.get('dwLength', 0),
            '时间戳': frame.get('tmStamp', 0),
            '消息类型': frame.get('nMsgType', 0),
            '数据格式': frame.get('data_format', 'unknown'),
            'LEADER': frame.get('LEADER', 0),
            'VER': frame.get('version', 0),
            'STC': frame.get('stc', 0),
            'TS': frame.get('ts', ''),
            'PL': frame.get('pl', 0),
            'EL': frame.get('el', 0),
            'DT': frame.get('dt', 0),
            'DL': frame.get('dl', 0),
            '频段序号': frame.get('band_no', 0),
            '信道总数': frame.get('total_channels', 0),
            '起始频率': frame.get('start_freq', 0.0),
            '结束频率': frame.get('end_freq', 0.0),
            '起始频率序号': frame.get('start_index', 0),
            '步长': frame.get('step', 0.0),
            '帧信道数量': frame.get('frame_channels', 0),
            '电平数量': len(frame.get('levels', [])),
            '电平': frame.get('levels', [])
        }
        output_data['frames'].append(frame_data)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)

    print(f"  已保存 {len(frames)} 帧数据到: {output_file}")


def test_streaming(soap_xml: str, soap_action: str, duration: float = 30.0,
                   output_file: str = None) -> dict:
    """测试streaming接口

    Args:
        soap_xml: SOAP请求XML
        soap_action: SOAPAction (如 "B_FScan")
        duration: 接收时长(秒)
        output_file: 输出文件路径

    Returns:
        测试结果
    """
    import sys
    sys.path.insert(0, 'experimental')
    from soap_to_rmcp_direct import (
        build_action_xml, build_rmcp_frame, parse_soap_items,
        infer_funcid, SOAP_FUNCID_MAP, map_param_names,
        adjust_params_by_funcid, format_action_items, add_device_params
    )

    print(f"=" * 60)
    print(f"Streaming接口测试: {soap_action}")
    print(f"=" * 60)

    # 转换SOAP → Action XML
    action_items, mfid, _, is_nil, has_taskid = parse_soap_items(soap_xml)

    if soap_action:
        funcid = SOAP_FUNCID_MAP.get(soap_action.strip('"'), 15)
    else:
        funcid = infer_funcid(action_items, is_nil, has_taskid)

    map_param_names(action_items)
    adjust_params_by_funcid(action_items, funcid)
    format_action_items(action_items)
    add_device_params(action_items, funcid)

    # stationid/deviceid
    if len(mfid) >= 8:
        stationid = mfid[:8]
    else:
        stationid = '53090001'
    deviceid = '00106'

    items_xml = [f'<item name="{name}" value="{value}" />' for name, value in action_items]
    items_str = '\n            '.join(items_xml)

    action_xml = f'''<?xml version="1.0" encoding="gb2312" ?>
<action id="1">
    <parameter groups="1" stationid="{stationid}" deviceid="{deviceid}" devicename="MS845" funcid="{funcid}">
        <group index="0">
            {items_str}
        </group>
    </parameter>
    <other_param />
</action>'''

    print(f"  funcid: {funcid}")
    print(f"  参数数量: {len(action_items)}")

    # 构建RMCP帧
    frame = build_rmcp_frame(action_xml)
    print(f"  帧大小: {len(frame)} bytes")

    # 连接设备
    print(f"  连接设备 {RMCP_HOST}:{RMCP_PORT}...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((RMCP_HOST, RMCP_PORT))
    print("  连接成功")

    # 发送请求
    sock.send(frame)
    print("  请求已发送")

    # 先接收初始响应(短超时)
    print("  等待设备响应...")
    sock.settimeout(5.0)
    initial_data = b''
    try:
        while True:
            chunk = sock.recv(4096)
            if not chunk:
                break
            initial_data += chunk
            # 尝试找到完整的帧
            if len(initial_data) >= 4:
                dwLen = struct.unpack('<I', initial_data[0:4])[0]
                if len(initial_data) >= dwLen:
                    break
    except socket.timeout:
        pass

    print(f"  收到初始响应: {len(initial_data)} bytes")

    # 打印响应内容(如果是错误)
    if initial_data:
        print(f"  响应内容(hex): {initial_data[:100].hex()}")
        if b'RMTP' in initial_data or b'ErrCode' in initial_data:
            try:
                text = initial_data.decode('gb2312', errors='replace')
                print(f"  错误响应: {text[:200]}")
            except:
                print(f"  错误响应(hex): {initial_data[:100].hex()}")
        else:
            # 解析帧头 - 格式是 <dwLength + tmStamp + zero + version + msgType + flags + checksum
            # = 4 + 8 + 1 + 1 + 1 + 1 + 2 = 18 bytes
            if len(initial_data) >= 18:
                dwLen = struct.unpack('<I', initial_data[0:4])[0]
                msgType = initial_data[14]
                flags = initial_data[15]
                print(f"  帧头解析: dwLength={dwLen}, nMsgType={msgType}, nFlags={flags}")

                # 打印RESPONSE payload
                if msgType == 6 and len(initial_data) > 18:
                    payload = initial_data[18:]
                    print(f"  RESPONSE payload (hex): {payload.hex()}")
                    # 尝试解析为文本
                    try:
                        text = payload.decode('gb2312', errors='replace')
                        print(f"  RESPONSE payload (text): {text}")
                    except:
                        pass

    # 继续接收数据
    print(f"  继续等待DATA帧 (最多{duration}秒)...")
    sock.settimeout(2.0)  # 重置socket超时

    # 构建 request_params 用于 AtomDataFormatter
    # 根据接口类型提取不同参数
    request_params = {'action': soap_action}

    # B_FScan: startfreq, stopfreq, step
    # B_PScan: frequency (单频点), dfmode, dftype
    # B_MScan: startfreq, stopfreq, step
    # B_SglFreqMeas: frequency (单频点), ifbw, measuretime
    for name, value in action_items:
        if name in ('startfreq', 'stopfreq', 'step', 'frequency', 'dfmode', 'dftype', 'ifbw', 'measuretime'):
            request_params[name] = value

    frames = receive_streaming_data(sock, timeout=duration, request_params=request_params)

    sock.close()
    print("  连接已关闭")

    # 打印原始响应(用于调试)
    print("\n  调试: 检查设备响应")

    # 保存数据
    if frames and output_file:
        save_to_json(frames, output_file)

    return {
        'success': len(frames) > 0,
        'frame_count': len(frames),
        'total_bytes': sum(f.get('dwLength', 0) for f in frames)
    }


if __name__ == '__main__':
    import sys

    # 测试B_FScan (funcid=15) - 频率扫描
    # 使用与capture相同的频率范围
    test_soap = '''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/">
<soapenv:Body>
<srrc:requestbody xmlns:srrc="http://www.srrc.org.cn">
<srrc:mfid>53090001150015</srrc:mfid>
<srrc:equid>51cd8dfe-e543-40c9-bdc3-a292766fee7f</srrc:equid>
<srrc:equpara>
<srrc:items>
<srrc:item><srrc:paraname>startfreq</srrc:paraname><srrc:paravalue>137000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>stopfreq</srrc:paraname><srrc:paravalue>173000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>step</srrc:paraname><srrc:paravalue>25000</srrc:paravalue></srrc:item>
</srrc:items>
</srrc:equpara>
</srrc:requestbody>
</soapenv:Body>
</soapenv:Envelope>'''

    output = f"data/streaming_fscan_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    result = test_streaming(test_soap, "B_FScan", duration=30.0, output_file=output)

    print(f"\n测试结果: {'成功' if result['success'] else '失败'}")
    print(f"  收到帧数: {result['frame_count']}")
    print(f"  总字节数: {result['total_bytes']}")