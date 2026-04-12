# -*- coding: utf-8 -*-
"""
SOAP ↔ RMCP 转换器

用于解析和转换 SOAP XML 与 RMCP 二进制帧

验证数据:
- SOAP: soap_proxy/logs/requests_20260411_1910/8ce334c8_req.xml
- RMCP: rmcp_proxy/capture/capture_20260411_191028.json (frame 0)

转换对应关系:
- SOAP funcid -> RMCP nMsgType=90 REQUEST
- 参数通过 SOAP XML 传递，直接嵌入 RMCP 帧
"""

import struct
import xml.etree.ElementTree as ET
from typing import Dict, Any, Optional, Tuple
import json


# ============================================
# 常量定义
# ============================================

# SOAP 操作 ↔ funcid 映射表
SOAP_FUNCID_MAP = {
    'B_FScan': 15,
    'B_FScanDF': 21,
    'B_MScan': 14,
    'B_MScanDF': 16,
    'B_PScan': 13,
    'B_SglFreqDF': 11,
    'B_SglFreqMeas': 12,
    'B_StopMeas': 32,
    'B_WBDF': 17,
    'B_QueryDeviceInfo': 10,
    'B_QueryFaciDevStat': 10,  # 与 B_QueryDeviceInfo 同 funcid
}

FUNCID_SOAP_MAP = {v: k for k, v in SOAP_FUNCID_MAP.items()}

# RMCP 消息类型
RMCP_MSGTYPE_REQUEST = 90
RMCP_MSGTYPE_RESPONSE = 6
RMCP_MSGTYPE_DATA = 0


# ============================================
# SOAP XML 解析
# ============================================

def parse_freq_value(value_str: str) -> int:
    """解析频率字符串 (如 '137MHz', '25kHz') 返回 Hz"""
    value_str = value_str.strip()
    if value_str.endswith('MHz'):
        return int(float(value_str[:-3]) * 1e6)
    elif value_str.endswith('kHz'):
        return int(float(value_str[:-3]) * 1e3)
    elif value_str.endswith('Hz'):
        return int(value_str[:-2])
    else:
        return int(value_str)


def format_freq_value(hz: int) -> str:
    """将 Hz 格式化为可读字符串"""
    if hz >= 1e6:
        return f"{hz/1e6}MHz"
    elif hz >= 1e3:
        return f"{hz/1e3}kHz"
    else:
        return f"{hz}Hz"


def parse_soap_request(xml_content: str) -> Dict[str, Any]:
    """
    解析 SOAP 请求 XML，提取参数

    Args:
        xml_content: SOAP XML 字符串

    Returns:
        参数字典，包含:
        - funcid: int
        - stationid: str
        - deviceid: str
        - devicename: str
        - startfreq: int (Hz)
        - stopfreq: int (Hz)
        - step: int (Hz)
        - gainctrl: str
        - rfworkmode: str
        - scanmode: str
        - 以及其他 item 元素
    """
    root = ET.fromstring(xml_content)

    # 提取 parameter 属性
    param = root.find('.//parameter')
    if param is None:
        raise ValueError("No <parameter> element found in SOAP XML")

    funcid = int(param.get('funcid', '0'))
    stationid = param.get('stationid', '')
    deviceid = param.get('deviceid', '')
    devicename = param.get('devicename', '')

    # 提取所有 item
    items = {}
    for item in root.findall('.//item'):
        name = item.get('name')
        value = item.get('value', '')
        items[name] = value

    # 构建结果字典
    result = {
        'funcid': funcid,
        'stationid': stationid,
        'deviceid': deviceid,
        'devicename': devicename,
        'operation': FUNCID_SOAP_MAP.get(funcid, f'UNKNOWN({funcid})'),
    }

    # 解析频率相关参数
    if 'startfreq' in items:
        result['startfreq'] = parse_freq_value(items['startfreq'])
    if 'stopfreq' in items:
        result['stopfreq'] = parse_freq_value(items['stopfreq'])
    if 'step' in items:
        result['step'] = parse_freq_value(items['step'])
    if 'frequency' in items:
        result['frequency'] = parse_freq_value(items['frequency'])

    # 其他参数直接复制
    for key in ['gainctrl', 'rfworkmode', 'scanmode', 'antpol', 'antetype',
                'ifatt', 'ifbw', 'keepmode', 'audioswitch', 'demodmode']:
        if key in items:
            result[key] = items[key]

    # taskid (如果存在)
    taskid_elem = root.find('.//taskid')
    if taskid_elem is not None:
        result['taskid'] = taskid_elem.text

    return result


def build_soap_request(operation: str, params: Dict[str, Any]) -> str:
    """
    构建 SOAP 请求 XML

    Args:
        operation: SOAP 操作名 (如 'B_FScan')
        params: 参数字典

    Returns:
        SOAP XML 字符串
    """
    funcid = SOAP_FUNCID_MAP.get(operation, 0)

    # 构建 item 元素
    items_xml = []
    for key, value in params.items():
        if key in ['startfreq', 'stopfreq', 'step', 'frequency']:
            value_str = format_freq_value(value)
        else:
            value_str = str(value)
        items_xml.append(f'<item name="{key}" value="{value_str}" />')

    items_str = '\n            '.join(items_xml)

    xml = f'''<?xml version="1.0" encoding="gb2312" ?>
<action id="1">
    <parameter groups="1" stationid="53090001" deviceid="00106" devicename="MS845" funcid="{funcid}">
        <group index="0">
            {items_str}
        </group>
    </parameter>
</action>'''

    return xml


# ============================================
# RMCP 帧解析
# ============================================

def parse_rmcp_header(hex_str: str) -> Dict[str, Any]:
    """
    解析 RMCP 帧头

    Args:
        hex_str: 16 进制字符串

    Returns:
        帧头信息字典
    """
    if len(hex_str) < 32:
        raise ValueError("Hex string too short for RMCP header (need 16 bytes = 32 hex chars)")

    header_bytes = bytes.fromhex(hex_str[:32])

    return {
        'dwLength': struct.unpack('<I', header_bytes[0:4])[0],
        'nVersion': header_bytes[4],
        'nMsgType': header_bytes[5],
        'nFlags': header_bytes[6],
        'nCheckSum': struct.unpack('<H', header_bytes[7:9])[0],
        'unknown': header_bytes[9:16].hex(),
    }


def parse_rmcp_request_frame(hex_str: str) -> Dict[str, Any]:
    """
    解析 RMCP REQUEST 帧

    Args:
        hex_str: 完整帧的 16 进制字符串

    Returns:
        帧信息字典
    """
    header = parse_rmcp_header(hex_str)

    # 查找 SOAP XML 开始位置
    # SOAP XML 通常以 '<?xml' 开头，对应 hex: '3c3f786d6c'
    xml_marker = '3c3f786d6c'
    xml_start_pos = hex_str.find(xml_marker)

    if xml_start_pos < 0:
        return {
            **header,
            'has_xml': False,
            'xml_content': None,
        }

    # 提取 XML 部分
    xml_hex = hex_str[xml_start_pos:]
    xml_bytes = bytes.fromhex(xml_hex)

    # 查找 null 终止符
    null_pos = xml_bytes.find(b'\x00')
    if null_pos > 0:
        xml_bytes = xml_bytes[:null_pos]

    # 解码 (GB2312)
    try:
        xml_content = xml_bytes.decode('gb2312')
    except UnicodeDecodeError:
        xml_content = xml_bytes.decode('utf-8', errors='replace')

    # 解析 SOAP 参数
    soap_params = None
    try:
        soap_params = parse_soap_request(xml_content)
    except Exception as e:
        pass

    return {
        **header,
        'has_xml': True,
        'xml_content': xml_content,
        'xml_start_byte_offset': xml_start_pos // 2,
        'soap_params': soap_params,
    }


def parse_rmcp_data_frame(hex_str: str, startfreq: float = 0, step: float = 0) -> Dict[str, Any]:
    """
    解析 RMCP DATA 帧 (频谱数据)

    Args:
        hex_str: DATA 帧的 16 进制字符串
        startfreq: 起始频率 (Hz)
        step: 频率步进 (Hz)

    Returns:
        帧信息字典，包含频谱数据列表
    """
    header = parse_rmcp_header(hex_str)

    # DATA 帧结构 (实测验证):
    # - RMCP header: 16 bytes (32 hex chars)
    # - Business header: 5 bytes (10 hex chars)
    # - Header counters: 4 int16 values (8 bytes) = 512, 0, 0, 0
    # - Spectrum data: 512 or 417 int16 values

    # 跳过头部: 16 bytes RMCP header + 5 bytes business header = 21 bytes = 42 hex chars
    payload_hex = hex_str[42:]
    payload_bytes = bytes.fromhex(payload_hex)

    # 解析所有 int16 值
    num_int16 = len(payload_bytes) // 2
    values = struct.unpack(f'<{num_int16}h', payload_bytes)

    # 前 4 个 int16 是 header counter (512, 0, 0, 0)
    # 实际频谱数据从索引 4 开始
    spectrum = values[4:]

    # 转换: raw / 10 = dBm
    dbm_values = [v / 10.0 for v in spectrum]

    # 计算频率
    if step > 0:
        frequencies = [startfreq + i * step for i in range(len(spectrum))]
    else:
        frequencies = list(range(len(spectrum)))

    return {
        **header,
        'header_counters': list(values[:4]),
        'point_count': len(spectrum),
        'frequencies': frequencies,
        'raw_values': list(spectrum),
        'dbm_values': dbm_values,
    }


# ============================================
# RMCP 帧构建
# ============================================

def build_rmcp_request_frame(soap_xml: str, funcid: int = 15) -> bytes:
    """
    构建 RMCP REQUEST 帧

    Args:
        soap_xml: SOAP XML 字符串
        funcid: 功能 ID (默认 15 = B_FScan)

    Returns:
        完整的 RMCP 二进制帧
    """
    # SOAP XML 编码为 GB2312
    xml_bytes = soap_xml.encode('gb2312')

    # RMCP 帧头 = 16 字节
    # 计算总长度 = 帧头(16) + XML 长度 + 1 (null)
    total_len = 16 + len(xml_bytes) + 1

    # 构建帧头
    header = struct.pack('<IBBIH',  # dwLength(4) + nVersion(1) + nMsgType(1) + nFlags(1) + nCheckSum(2)
                        total_len,  # dwLength
                        7,          # nVersion
                        90,         # nMsgType = REQUEST
                        1,          # nFlags
                        0)          # nCheckSum (占位，后面计算)

    # 未知字段 (8 bytes) - 需要根据实际抓包填充
    unknown = bytes([0x00, 0xc1, 0xed, 0xe4, 0xe6, 0xc9, 0xdc, 0x01])

    # 组合帧
    frame = header + unknown + xml_bytes + b'\x00'

    # 计算校验和 (简单求和)
    checksum = sum(frame) & 0xFFFF
    frame = frame[:15] + struct.pack('<H', checksum) + frame[17:]

    return frame


# ============================================
# 主函数：验证转换
# ============================================

def verify_soap_to_rmcp():
    """验证 SOAP XML -> RMCP 帧的转换"""

    # 原始 SOAP XML (从抓包提取)
    soap_xml = '''<?xml version="1.0" encoding="gb2312" ?>
<action id="1">
    <parameter groups="1" stationid="53090001" deviceid="00106" devicename="MS845" funcid="15">
        <group index="0">
            <item name="startfreq" value="137MHz" />
            <item name="stopfreq" value="173MHz" />
            <item name="step" value="25kHz" />
            <item name="gainctrl" value="AGC" />
            <item name="rfworkmode" value="0" />
            <item name="scanmode" value="0" />
        </group>
    </parameter>
</action>'''

    # 解析 SOAP 参数
    params = parse_soap_request(soap_xml)
    print("=== SOAP 参数解析结果 ===")
    for k, v in params.items():
        print(f"  {k}: {v}")
    print()

    # 从抓包数据验证
    json_path = 'D:/arvin/claude_workspace/SpecDetect_V4/SpecDetect_POC/rmcp_proxy/capture/capture_20260411_191028.json'
    with open(json_path, 'r') as f:
        data = json.load(f)

    # 分析 REQUEST 帧
    print("=== RMCP REQUEST 帧解析 ===")
    frame = data[0]
    parsed = parse_rmcp_request_frame(frame['hex'])

    print(f"  dwLength: {parsed['dwLength']}")
    print(f"  nVersion: {parsed['nVersion']}")
    print(f"  nMsgType: {parsed['nMsgType']} ({'REQUEST' if parsed['nMsgType'] == 90 else 'OTHER'})")
    print(f"  nFlags: {parsed['nFlags']}")
    print(f"  has_xml: {parsed['has_xml']}")
    print(f"  xml_offset: byte {parsed.get('xml_start_byte_offset', 'N/A')}")
    print()

    if parsed['soap_params']:
        print("  SOAP 参数对比:")
        for k in ['funcid', 'startfreq', 'stopfreq', 'step', 'gainctrl']:
            if k in parsed['soap_params']:
                match = parsed['soap_params'][k] == params.get(k)
                print(f"    {k}: {parsed['soap_params'][k]} (expected: {params.get(k)}) {'OK' if match else 'DIFF'}")

    print()

    # 分析 DATA 帧
    print("=== RMCP DATA 帧解析 ===")
    for i, frame in enumerate(data[2:5]):  # 前3个 DATA 帧
        parsed = parse_rmcp_data_frame(frame['hex'],
                                       startfreq=137e6,
                                       step=25e3)
        print(f"  Frame {i}: {len(parsed['dbm_values'])} points")
        if parsed['dbm_values']:
            print(f"    First 5 dBm: {parsed['dbm_values'][:5]}")


if __name__ == '__main__':
    verify_soap_to_rmcp()
