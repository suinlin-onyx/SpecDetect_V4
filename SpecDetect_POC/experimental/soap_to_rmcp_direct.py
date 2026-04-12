# -*- coding: utf-8 -*-
"""
实验性功能: 直接 SOAP → RMCP 发送到真实设备

功能:
1. 将 SOAP XML 转换为 RMCP Action XML 格式
2. 构建 RMCP 二进制帧
3. 直接发送到设备 (绕过 Atom)
4. 接收设备响应

用途:
- 验证 SOAP → RMCP 转换是否与 Atom 生成的一致
- 绕过 Atom 直接控制设备进行测试

注意: 这是实验性代码，不要影响现有功能
"""

import socket
import struct
import time
from datetime import datetime, timezone, timedelta
from typing import Tuple, Optional
import xml.etree.ElementTree as ET


# ============================================
# RMCP 协议常量
# ============================================

RMCP_HOST = '100.72.95.36'  # 设备IP (从 capture 确定)
RMCP_PORT = 1449            # 设备端口

# RMCP 消息类型
RMCP_MSGTYPE_REQUEST = 90
RMCP_MSGTYPE_RESPONSE = 6
RMCP_MSGTYPE_DATA = 0


# ============================================
# SOAP → Action XML 转换 (复用 soap_to_rmcp_converter 逻辑)
# ============================================

SOAP_TO_ACTION_PARAM_MAP = {
    'gain': 'gainctrl',
}

SOAP_FUNCID_MAP = {
    'B_FScan': 15,
    'B_FScanDF': 21,
    'B_MScan': 14,
    'B_MScanDF': 16,
    'B_PScan': 13,
    'B_SglFreqDF': 11,
    'B_SglFreqMeas': 12,
    'B_StopMeas': 32,
    'B_WBDF': 25,  # 注意：设备实际使用 funcid=25，不是 17
    'B_QueryDeviceInfo': 10,
    'B_QueryFaciDevStat': 10,  # 与 B_QueryDeviceInfo 同 funcid
}


def parse_soap_items(soap_xml: str) -> Tuple[list, str, str, bool, bool]:
    """
    解析 SOAP XML，提取参数

    Returns:
        (action_items, mfid, equid, is_nil, has_taskid)
    """
    root = ET.fromstring(soap_xml)
    ns = {'srrc': 'http://www.srrc.org.cn'}

    # 查找 requestbody
    requestbody = root.find('.//srrc:requestbody', ns)
    if requestbody is None:
        requestbody = root.find('.//requestbody')

    # 获取 mfid
    mfid = ''
    equid = ''
    if requestbody is not None:
        mfid_elem = requestbody.find('srrc:mfid', ns)
        if mfid_elem is None:
            mfid_elem = requestbody.find('mfid')
        if mfid_elem is not None:
            mfid = mfid_elem.text or ''

        equid_elem = requestbody.find('srrc:equid', ns)
        if equid_elem is None:
            equid_elem = requestbody.find('equid')
        if equid_elem is not None:
            equid = equid_elem.text or ''

    # 查找 equpara
    equpara = root.find('.//srrc:equpara', ns)
    if equpara is None:
        equpara = root.find('.//equpara')

    # 检查 xsi:nil
    is_nil = equpara is None or equpara.get('xsi:nil') == 'true'

    # 检查 taskid
    has_taskid = False
    if requestbody is not None:
        if requestbody.find('srrc:taskid', ns) is not None:
            has_taskid = True
        elif requestbody.find('taskid') is not None:
            has_taskid = True

    # 提取参数
    action_items = []
    if not is_nil and equpara is not None:
        # 尝试 groupitems
        groupitems_elem = equpara.find('.//srrc:groupitems', ns)
        if groupitems_elem is None:
            groupitems_elem = equpara.find('.//groupitems')

        if groupitems_elem is not None:
            for groupitem in groupitems_elem:
                if groupitem.tag.endswith('groupitem'):
                    items_elem = groupitem.find('.//srrc:items', ns)
                    if items_elem is None:
                        items_elem = groupitem.find('.//items')
                    if items_elem is not None:
                        _parse_items(items_elem, action_items, ns)
        else:
            # 单层 items
            items_elem = equpara.find('.//srrc:items', ns)
            if items_elem is None:
                items_elem = equpara.find('.//items')
            if items_elem is not None:
                _parse_items(items_elem, action_items, ns)

    return action_items, mfid, equid, is_nil, has_taskid


def _parse_items(items_elem, action_items, ns):
    """解析 items 元素"""
    for item in items_elem:
        paraname = None
        paravalue = None
        for child in item:
            if child.tag.endswith('paraname'):
                paraname = child.text
            elif child.tag.endswith('paravalue'):
                paravalue = child.text
        if paraname and paravalue is not None:
            action_items.append((paraname, paravalue))


def infer_funcid(action_items: list, is_nil: bool, has_taskid: bool) -> int:
    """根据参数推断 funcid"""
    names = {name for name, _ in action_items}

    if is_nil:
        return 32 if has_taskid else 10

    if 'frequency' in names and 'dfmode' in names:
        return 11  # B_SglFreqDF
    elif 'frequency' in names and 'ifbw' in names:
        return 25  # B_WBDF (设备实际使用)
    elif 'frequency' in names:
        return 12  # B_SglFreqMeas

    if 'startfreq' in names and 'stopfreq' in names and 'step' in names and 'dfmode' in names:
        return 21
    elif 'startfreq' in names and 'stopfreq' in names and 'step' in names:
        return 15
    elif 'startfreq' in names and 'stopfreq' in names:
        return 17
    elif 'startfreq' in names or 'stopfreq' in names:
        return 13

    return 15


def map_param_names(action_items: list):
    """映射参数名"""
    for i, (name, value) in enumerate(action_items):
        if name in SOAP_TO_ACTION_PARAM_MAP:
            action_items[i] = (SOAP_TO_ACTION_PARAM_MAP[name], value)


def adjust_params_by_funcid(action_items: list, funcid: int):
    """根据 funcid 调整参数"""
    names = {name for name, _ in action_items}

    if funcid == 11 and 'dfmode' in names:
        action_items[:] = [(n, v) for n, v in action_items if n != 'dfmode']


def add_device_params(action_items: list, funcid: int):
    """
    根据接口类型添加设备配置参数

    这些参数由 Atom 从设备配置中获取并添加到 RMCP 请求中
    """
    names = {name for name, _ in action_items}

    # B_FScan (15): 频率扫描
    if funcid == 15:
        if 'gainctrl' not in names:
            action_items.append(('gainctrl', 'AGC'))
        if 'rfworkmode' not in names:
            action_items.append(('rfworkmode', '0'))
        if 'scanmode' not in names:
            action_items.append(('scanmode', '0'))
        if 'antpol' not in names:
            action_items.append(('antpol', '垂直'))
        if 'antetype' not in names:
            action_items.append(('antetype', 'OFF'))
        if 'ifatt' not in names:
            action_items.append(('ifatt', '0'))

    # B_FScanDF (21): 频率扫描测向 - 需要 antpol
    elif funcid == 21:
        if 'gainctrl' not in names:
            action_items.append(('gainctrl', 'AGC'))
        if 'antpol' not in names:
            action_items.append(('antpol', '垂直'))
        if 'rfworkmode' not in names:
            action_items.append(('rfworkmode', '0'))
        if 'antetype' not in names:
            action_items.append(('antetype', 'OFF'))
        if 'ifatt' not in names:
            action_items.append(('ifatt', '0'))
        if 'antezoom' not in names:
            action_items.append(('antezoom', 'OFF'))
        if 'levelthreshold' not in names:
            action_items.append(('levelthreshold', '0'))

    # B_PScan (13): 频谱扫描 - 需要 dfmode, dftype
    elif funcid == 13:
        if 'dfmode' not in names:
            action_items.append(('dfmode', '0'))
        if 'dftype' not in names:
            action_items.append(('dftype', '0'))
        if 'rfworkmode' not in names:
            action_items.append(('rfworkmode', '0'))
        if 'antpol' not in names:
            action_items.append(('antpol', '垂直'))
        if 'antetype' not in names:
            action_items.append(('antetype', 'OFF'))
        if 'ifatt' not in names:
            action_items.append(('ifatt', '0'))
        if 'ifbw' not in names:
            action_items.append(('ifbw', '40000kHz'))
        if 'gainctrl' not in names:
            action_items.append(('gainctrl', 'AGC'))
        if 'levelthreshold' not in names:
            action_items.append(('levelthreshold', '0'))
        if 'antezoom' not in names:
            action_items.append(('antezoom', 'OFF'))
        if 'antArryChoose' not in names:
            action_items.append(('antArryChoose', '1'))
        if 'calibSwitch' not in names:
            action_items.append(('calibSwitch', 'OFF'))

    # B_MScan (14): 多信道扫描
    elif funcid == 14:
        if 'antpol' not in names:
            action_items.append(('antpol', '垂直'))
        if 'antetype' not in names:
            action_items.append(('antetype', 'OFF'))
        if 'rfworkmode' not in names:
            action_items.append(('rfworkmode', '0'))

    # B_MScanDF (16): 多信道扫描测向
    elif funcid == 16:
        if 'gainctrl' not in names:
            action_items.append(('gainctrl', 'AGC'))
        if 'antpol' not in names:
            action_items.append(('antpol', '垂直'))
        if 'keepmode' not in names:
            action_items.append(('keepmode', '0'))
        if 'rfworkmode' not in names:
            action_items.append(('rfworkmode', '0'))
        if 'antetype' not in names:
            action_items.append(('antetype', 'OFF'))
        if 'ifatt' not in names:
            action_items.append(('ifatt', '0'))

    # B_WBDF (25): 宽带测向 - 设备实际使用 funcid=25
    elif funcid == 25:
        if 'gainctrl' not in names:
            action_items.append(('gainctrl', 'AGC'))
        if 'rfworkmode' not in names:
            action_items.append(('rfworkmode', '0'))
        if 'antpol' not in names:
            action_items.append(('antpol', '垂直'))
        if 'antetype' not in names:
            action_items.append(('antetype', 'OFF'))
        if 'resolution' not in names:
            action_items.append(('resolution', '25kHz'))
        if 'ifatt' not in names:
            action_items.append(('ifatt', '0'))
        if 'antezoom' not in names:
            action_items.append(('antezoom', 'OFF'))
        if 'antArryChoose' not in names:
            action_items.append(('antArryChoose', '1'))

    # B_SglFreqDF (11): 单频测向 - 需要 dfmode
    elif funcid == 11:
        if 'dfmode' not in names:
            action_items.append(('dfmode', '0'))
        if 'antpol' not in names:
            action_items.append(('antpol', '垂直'))
        if 'antetype' not in names:
            action_items.append(('antetype', 'OFF'))
        if 'rfworkmode' not in names:
            action_items.append(('rfworkmode', '0'))
        if 'ifatt' not in names:
            action_items.append(('ifatt', '0'))


def format_action_items(action_items: list):
    """格式化参数值"""
    for i, (name, value) in enumerate(action_items):
        try:
            val = int(value)
            if name in ('startfreq', 'stopfreq', 'frequency'):
                action_items[i] = (name, f"{val // 1000000}MHz")
            elif name == 'step':
                action_items[i] = (name, f"{val // 1000}kHz")
            elif name == 'ifbw':
                # ifbw 值已经是 kHz 单位，直接附加 kHz
                action_items[i] = (name, f"{val}kHz")
        except (ValueError, TypeError):
            pass


def build_action_xml(soap_xml: str, soap_action: str = None) -> str:
    """将 SOAP XML 转换为 RMCP Action XML 格式"""
    action_items, mfid, _, is_nil, has_taskid = parse_soap_items(soap_xml)

    # 从 SOAPAction 确定 funcid
    if soap_action:
        funcid = SOAP_FUNCID_MAP.get(soap_action.strip('"'), 15)
    else:
        funcid = infer_funcid(action_items, is_nil, has_taskid)

    map_param_names(action_items)
    adjust_params_by_funcid(action_items, funcid)
    format_action_items(action_items)

    # 添加设备配置参数 (Atom 自动添加的)
    add_device_params(action_items, funcid)

    # stationid/deviceid
    if len(mfid) >= 8:
        stationid = mfid[:8]
    else:
        stationid = '53090001'
    deviceid = '00106'

    # 构建 Action XML
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

    return action_xml


# ============================================
# RMCP 帧构建
# ============================================

def create_filetime() -> bytes:
    """创建当前 UTC 时间的 FILETIME"""
    now_utc = datetime.now(timezone.utc)
    ft_epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
    ft_value = int((now_utc - ft_epoch) / timedelta(microseconds=1)) * 10
    return struct.pack('<Q', ft_value)


def calculate_checksum(frame_header: bytes) -> int:
    """计算 RMCP 帧头校验和"""
    length = struct.unpack('<I', frame_header[0:4])[0]
    timestamp = struct.unpack('<Q', frame_header[4:12])[0]

    total = timestamp + length

    high = (total >> 32) & 0xFFFFFFFF
    low = total & 0xFFFFFFFF
    result1 = high + low

    result2 = (result1 >> 16) + (result1 & 0xFFFF)
    while result2 > 0xFFFF:
        result2 = ((result2 >> 16) & 0xFFFF) + (result2 & 0xFFFF)

    return (~result2) & 0xFFFF


def build_rmcp_frame(action_xml: str) -> bytes:
    """构建 RMCP REQUEST 帧"""
    xml_bytes = action_xml.encode('gb2312')

    # RMCP 帧头结构 (18字节)
    # Bytes 0-3: dwLength
    # Bytes 4-11: FILETIME
    # Byte 12: 0x00
    # Byte 13: nVersion (=7)
    # Byte 14: nMsgType (=90)
    # Byte 15: nFlags (=1)
    # Bytes 16-17: nCheckSum
    # Byte 18+: XML (no null byte between header and XML)

    # Total: 18 bytes header + XML + 1 trailing null
    total_len = 18 + len(xml_bytes) + 1

    frame = bytearray()

    # dwLength
    frame.extend(struct.pack('<I', total_len))

    # FILETIME
    frame.extend(create_filetime())

    # Byte 12: 0x00
    frame.append(0x00)

    # Byte 13: nVersion = 7
    frame.append(0x07)

    # Byte 14: nMsgType = 90
    frame.append(0x5A)

    # Byte 15: nFlags = 1
    frame.append(0x01)

    # Bytes 16-17: nCheckSum (placeholder)
    checksum_pos = len(frame)
    frame.extend(bytes([0xCC, 0xCC]))

    # SOAP XML
    frame.extend(xml_bytes)

    # Trailing null (Atom frame has this at the end of XML)
    frame.append(0x00)

    # Calculate and update checksum (over 18-byte header)
    header_for_checksum = bytes(frame[:18])
    calculated_checksum = calculate_checksum(header_for_checksum)
    frame[checksum_pos:checksum_pos+2] = struct.pack('<H', calculated_checksum)

    return bytes(frame)


# ============================================
# TCP 通信
# ============================================

def send_rmcp_frame(host: str, port: int, frame: bytes, timeout: float = 5.0) -> Tuple[bytes, float]:
    """
    发送 RMCP 帧到设备并接收响应

    Returns:
        (response_bytes, elapsed_time)
    """
    start_time = time.time()

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.settimeout(timeout)
        sock.connect((host, port))
        sock.send(frame)

        # 接收响应
        # RMCP 响应帧头 = 19 字节，先读取头获取长度
        header = b''
        while len(header) < 19:
            chunk = sock.recv(19 - len(header))
            if not chunk:
                break
            header += chunk

        if len(header) >= 4:
            dwLength = struct.unpack('<I', header[0:4])[0]
            remaining = dwLength - len(header)
            body = b''
            while len(body) < remaining:
                chunk = sock.recv(remaining - len(body))
                if not chunk:
                    break
                body += chunk
            response = header + body
        else:
            response = header

        elapsed = time.time() - start_time
        return response, elapsed


def parse_rmcp_response(response: bytes) -> dict:
    """解析 RMCP 响应"""
    if len(response) < 19:
        return {'error': 'Response too short', 'hex': response.hex(), 'raw_text': response.decode('ascii', errors='replace') if response.startswith(b'RMTP') else None}

    dwLength = struct.unpack('<I', response[0:4])[0]
    nVersion = response[13]
    nMsgType = response[14]
    nFlags = response[15]
    nCheckSum = struct.unpack('<H', response[16:18])[0]

    msg_type_names = {0: 'DATA', 6: 'RESPONSE', 90: 'REQUEST'}
    nMsgTypeName = msg_type_names.get(nMsgType, f'UNKNOWN({nMsgType})')

    return {
        'dwLength': dwLength,
        'nVersion': nVersion,
        'nMsgType': nMsgType,
        'nMsgTypeName': nMsgTypeName,
        'nFlags': nFlags,
        'nCheckSum': nCheckSum,
        'hex': response.hex(),
        'raw_text': response.decode('ascii', errors='replace') if response.startswith(b'RMTP') else None
    }


# ============================================
# 主函数
# ============================================

def send_soap_to_device(soap_xml: str, host: str = RMCP_HOST, port: int = RMCP_PORT, soap_action: str = None) -> dict:
    """
    直接发送 SOAP 请求到设备 (绕过 Atom)

    Args:
        soap_xml: SOAP XML 字符串
        host: 设备 IP
        port: 设备端口
        soap_action: SOAPAction header (如 "B_FScan")

    Returns:
        {
            'success': bool,
            'action_xml': str,
            'rmcp_frame_hex': str,
            'response': dict,
            'elapsed': float,
            'error': str (如果有)
        }
    """
    try:
        # 1. 转换 SOAP → Action XML (传递 soap_action 以添加设备参数)
        action_xml = build_action_xml(soap_xml, soap_action)

        # 2. 构建 RMCP 帧
        rmcp_frame = build_rmcp_frame(action_xml)

        # 3. 发送到设备
        response_bytes, elapsed = send_rmcp_frame(host, port, rmcp_frame)

        # 4. 解析响应
        response_info = parse_rmcp_response(response_bytes)

        return {
            'success': True,
            'action_xml': action_xml,
            'rmcp_frame_hex': rmcp_frame.hex(),
            'response': response_info,
            'response_hex': response_bytes.hex(),
            'elapsed': elapsed,
        }

    except Exception as e:
        return {
            'success': False,
            'error': str(e),
        }


def test_interface(interface_name: str, soap_xml: str) -> dict:
    """测试指定接口"""
    print(f"\n{'='*60}")
    print(f"Testing: {interface_name}")
    print(f"{'='*60}")

    result = send_soap_to_device(soap_xml)

    if result['success']:
        print(f"Action XML:\n{result['action_xml']}")
        print(f"\nRMCP Frame: {result['rmcp_frame_hex'][:80]}...")
        print(f"\nResponse: {result['response']}")
        print(f"Elapsed: {result['elapsed']:.3f}s")
    else:
        print(f"Error: {result['error']}")

    return result


if __name__ == '__main__':
    # 测试 B_FScan
    soap_fscan = '''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody><srrc:mfid>53090001140012</srrc:mfid>
<srrc:equpara><srrc:groupitems><srrc:groupitem><srrc:groupid>1</srrc:groupid>
<srrc:items><srrc:item><srrc:paraname>startfreq</srrc:paraname><srrc:paravalue>137000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>stopfreq</srrc:paraname><srrc:paravalue>173000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>step</srrc:paraname><srrc:paravalue>25000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>gain</srrc:paraname><srrc:paravalue>AGC</srrc:paravalue></srrc:item>
</srrc:items></srrc:groupitem></srrc:groupitems></srrc:equpara>
</srrc:requestbody></soapenv:Body></soapenv:Envelope>'''

    test_interface('B_FScan', soap_fscan)