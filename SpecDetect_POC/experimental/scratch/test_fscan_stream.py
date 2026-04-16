# -*- coding: utf-8 -*-
"""
测试 B_FScan 发起后设备是否持续发送数据流
"""

import socket
import struct
import time
import sys
sys.path.insert(0, 'experimental')
from soap_to_rmcp_direct import build_rmcp_frame, create_filetime, calculate_checksum

RMCP_HOST = '100.72.95.36'
RMCP_PORT = 1449


def test_fscan_data_stream():
    """测试 B_FScan 是否产生持续数据流"""

    # B_FScan Action XML
    action_xml = '''<?xml version="1.0" encoding="gb2312" ?>
<action id="1">
    <parameter groups="1" stationid="53090001" deviceid="00106" devicename="MS845" funcid="15">
        <group index="0">
            <item name="startfreq" value="137MHz" />
            <item name="stopfreq" value="173MHz" />
            <item name="step" value="25kHz" />
            <item name="gainctrl" value="AGC" />
            <item name="rfworkmode" value="0" />
            <item name="scanmode" value="0" />
            <item name="antpol" value="垂直" />
            <item name="antetype" value="OFF" />
            <item name="ifatt" value="0" />
        </group>
    </parameter>
    <other_param />
</action>'''

    frame = build_rmcp_frame(action_xml)
    print(f'发送帧: {len(frame)} bytes')

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect((RMCP_HOST, RMCP_PORT))
    sock.send(frame)

    print('等待响应...')

    # 读取所有响应数据 (最多10秒或100个包)
    packets = []
    start_time = time.time()
    packet_count = 0

    while time.time() - start_time < 5:  # 最多5秒
        try:
            # 每次读取 2048 字节
            chunk = sock.recv(2048)
            if not chunk:
                break
            packets.append(chunk)
            packet_count += 1
            print(f'  收到数据包 #{packet_count}: {len(chunk)} bytes')

            # 如果已经收到多个包，可能已经收到足够数据
            if packet_count >= 10:
                break
        except socket.timeout:
            print('  接收超时')
            break

    sock.close()

    total_bytes = sum(len(p) for p in packets)
    print(f'\n总计: {packet_count} 个数据包, {total_bytes} bytes')

    # 分析收到的帧
    all_data = b''.join(packets)
    offset = 0

    print('\n帧分析:')
    frame_num = 0
    while offset < len(all_data):
        if offset + 4 > len(all_data):
            break
        dwLength = struct.unpack('<I', all_data[offset:offset+4])[0]

        if offset + dwLength > len(all_data):
            # 可能数据不完整
            print(f'  帧 {frame_num+1}: dwLength={dwLength}, 但剩余数据不足')
            break

        frame_data = all_data[offset:offset+dwLength]
        nMsgType = frame_data[14] if len(frame_data) > 14 else 0

        msg_type_names = {0: 'DATA', 6: 'RESPONSE', 90: 'REQUEST'}
        type_name = msg_type_names.get(nMsgType, f'UNKNOWN({nMsgType})')

        print(f'  帧 {frame_num+1}: {dwLength} bytes, nMsgType={nMsgType} ({type_name})')

        offset += dwLength
        frame_num += 1

        if frame_num >= 20:  # 最多显示20帧
            print('  ... (更多帧)')
            break

    return len(packets) > 1


if __name__ == '__main__':
    print('='*60)
    print('测试 B_FScan 持续数据流')
    print('='*60)
    print()

    try:
        has_stream = test_fscan_data_stream()
        print()
        if has_stream:
            print('结果: 设备持续发送数据流 ✓')
        else:
            print('结果: 未检测到持续数据流')
    except Exception as e:
        print(f'测试失败: {e}')
