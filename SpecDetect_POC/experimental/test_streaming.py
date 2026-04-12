# -*- coding: utf-8 -*-
"""
Streaming 接口测试脚本
支持接收持续数据流
"""

import socket
import struct
import time
import sys
sys.path.insert(0, 'experimental')
from soap_to_rmcp_direct import build_rmcp_frame

RMCP_HOST = '100.72.95.36'
RMCP_PORT = 1449


def test_streaming_interface(soap_xml: str, soap_action: str, timeout: float = 3.0) -> dict:
    """测试 streaming 接口"""

    # 从 soap_to_rmcp_direct 导入必要函数
    from soap_to_rmcp_direct import build_action_xml, add_device_params, parse_soap_items

    # 转换 SOAP → Action XML
    action_items, mfid, _, is_nil, has_taskid = parse_soap_items(soap_xml)

    from soap_to_rmcp_direct import infer_funcid, SOAP_FUNCID_MAP
    if soap_action:
        funcid = SOAP_FUNCID_MAP.get(soap_action.strip('"'), 15)
    else:
        funcid = infer_funcid(action_items, is_nil, has_taskid)

    from soap_to_rmcp_direct import map_param_names, adjust_params_by_funcid, format_action_items
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

    print(f'  Action XML:')
    for line in action_xml.split('\n'):
        print(f'    {line}')

    frame = build_rmcp_frame(action_xml)
    print(f'  帧大小: {len(frame)} bytes')

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    sock.connect((RMCP_HOST, RMCP_PORT))
    sock.send(frame)

    print('  等待响应...')

    # 接收响应
    packets = []
    start_time = time.time()

    try:
        while time.time() - start_time < timeout:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                packets.append(chunk)
            except socket.timeout:
                break
    finally:
        sock.close()

    all_data = b''.join(packets)
    print(f'  收到: {len(packets)} 个数据包, 共 {len(all_data)} bytes')

    # 解析帧
    frames = []
    offset = 0
    while offset < len(all_data):
        if offset + 4 > len(all_data):
            break
        dwLength = struct.unpack('<I', all_data[offset:offset+4])[0]
        if offset + dwLength > len(all_data):
            break
        frame_data = all_data[offset:offset+dwLength]
        nMsgType = frame_data[14] if len(frame_data) > 14 else 0
        msg_names = {0: 'DATA', 6: 'RESPONSE', 90: 'REQUEST'}
        frames.append({
            'dwLength': dwLength,
            'nMsgType': nMsgType,
            'type': msg_names.get(nMsgType, f'UNKNOWN({nMsgType})')
        })
        offset += dwLength

    print(f'  帧数量: {len(frames)}')
    for i, f in enumerate(frames[:5]):
        print(f'    帧{i+1}: {f["dwLength"]} bytes, {f["type"]}')
    if len(frames) > 5:
        print(f'    ...')

    return {
        'success': len(frames) > 0,
        'frames': frames,
        'total_bytes': len(all_data)
    }


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        print('用法: python test_streaming.py <soap_xml> <soap_action>')
        sys.exit(1)

    test_streaming_interface(sys.argv[1], sys.argv[2])
