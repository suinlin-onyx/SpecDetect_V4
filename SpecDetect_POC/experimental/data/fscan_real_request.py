# -*- coding: utf-8 -*-
"""
FSCAN 真实请求格式

从 pcap 20260416_171917_9996.pcap 提取的真实请求格式
"""

# 设备信息
DEVICE_INFO = {
    'stationid': '53090001',
    'deviceid': '00106',
    'devicename': 'MS845',
    'funcid': 15,  # B_FScan
    'mfid': '53090001140012',
    'equid': '51cd8dfe-e543-40c9-bdc3-a292766fee7f',
}

def build_fscan_xml(start_freq: int, end_freq: int, step: int,
                    gainctrl: str = 'AGC',
                    rfworkmode: str = '0',
                    scanmode: str = '0',
                    antpol: str = '垂直',
                    antetype: str = 'OFF',
                    ifatt: str = '0') -> str:
    """
    构建 FSCAN 请求 XML (真实设备接受的格式)

    关键: 频率使用可读格式 (MHz/kHz), 不是 Hz

    Args:
        start_freq: 起始频率 (Hz), e.g., 137000000
        end_freq: 终止频率 (Hz), e.g., 173000000
        step: 步进 (Hz), e.g., 25000
        gainctrl: 增益模式 ('AGC' or 'MGC')
        rfworkmode: 射频模式 ('0', '1', '2')
        scanmode: 扫描模式 ('0', '1')
        antpol: 天线极化 ('垂直' or '水平')
        antetype: 天线类型 ('OFF' or other)
        ifatt: 中频衰减 ('0' or other)

    Returns:
        SOAP XML 字符串
    """
    # 转换频率为可读格式 (整数不带小数)
    def fmt_freq(hz):
        if hz >= 1_000_000:
            val = hz / 1_000_000
            return f"{int(val)}MHz" if val == int(val) else f"{val}MHz"
        elif hz >= 1_000:
            val = hz / 1_000
            return f"{int(val)}kHz" if val == int(val) else f"{val}kHz"
        else:
            return f"{hz}Hz"

    start_freq_str = fmt_freq(start_freq)
    end_freq_str = fmt_freq(end_freq)
    step_str = fmt_freq(step)

    soap_xml = f'''<?xml version="1.0" encoding="gb2312" ?>
<action id="1">
    <parameter groups="1" stationid="{DEVICE_INFO['stationid']}" deviceid="{DEVICE_INFO['deviceid']}" devicename="{DEVICE_INFO['devicename']}" funcid="{DEVICE_INFO['funcid']}">
        <group index="0">
            <item name="startfreq" value="{start_freq_str}" />
            <item name="stopfreq" value="{end_freq_str}" />
            <item name="step" value="{step_str}" />
            <item name="gainctrl" value="{gainctrl}" />
            <item name="rfworkmode" value="{rfworkmode}" />
            <item name="scanmode" value="{scanmode}" />
            <item name="antpol" value="{antpol}" />
            <item name="antetype" value="{antetype}" />
            <item name="ifatt" value="{ifatt}" />
        </group>
    </parameter>
    <other_param />
</action>'''

    return soap_xml


def build_rmcp_request_frame(soap_xml: str, funcid: int = 15) -> bytes:
    """
    构建 RMCP REQUEST 帧 (用于发送 SOAP XML 到 rmcp_proxy)

    RMCPTP 帧头结构 (18字节):
    - dwLength: 4 bytes (little-endian)
    - tmStamp: 8 bytes (FILETIME)
    - nVersion: 2 bytes (big-endian，值为 0x0007)
    - nMsgType: 1 byte
    - nFlags: 1 byte
    - nCheckSum: 2 bytes (little-endian)

    Args:
        soap_xml: SOAP XML 字符串
        funcid: 功能 ID (默认 15 = B_FScan)

    Returns:
        完整的 RMCP 二进制帧
    """
    import struct
    import time

    # SOAP XML 编码为 GB2312
    xml_bytes = soap_xml.encode('gb2312')

    # 计算 FILETIME 时间戳
    FILETIME_EPOCH = 116444736000000000  # 100纳秒间隔
    filetime = int(time.time() * 10000000) + FILETIME_EPOCH

    # 计算总长度 = 帧头(18) + XML 长度 + 1 (null)
    xml_length = len(xml_bytes) + 1  # XML + null terminator
    total_length = 18 + xml_length  # header(18) + payload

    # 构建帧头 (18字节)
    # 关键: nVersion 用 '>H' (big-endian) 存储，这样才能被 rmcp_proxy 正确解析
    # 注意: dwLength 应该包含整个帧 (header + payload)
    header = struct.pack(
        '<IQ',        # dwLength(4) + tmStamp(8)
        total_length,
        filetime
    )
    # nVersion 单独用 big-endian 存储
    header += struct.pack('>H', 7)  # nVersion = 7
    # nMsgType + nFlags + nCheckSum
    header += struct.pack('BBH', 90, 1, 0)  # nMsgType, nFlags, nCheckSum

    # 组合帧
    frame = header + xml_bytes + b'\x00'

    # 计算校验和 (RMCP 协议标准算法)
    checksum = _calculate_rmcp_checksum(frame)
    frame = frame[:16] + struct.pack('<H', checksum) + frame[18:]

    return frame


def _calculate_rmcp_checksum(frame: bytes) -> int:
    """
    RMCP 帧头校验和算法:
    1. length + timestamp (64位)
    2. 第一次折半移位: 高32位 + 低32位
    3. 第二次折半移位: 高16位 + 低16位 (循环直到 <= 0xFFFF)
    4. 取反码 (~result)
    """
    import struct

    length = struct.unpack('<I', frame[0:4])[0]
    timestamp = struct.unpack('<Q', frame[4:12])[0]

    total = timestamp + length

    # 第一次折半移位
    high = (total >> 32) & 0xFFFFFFFF
    low = total & 0xFFFFFFFF
    result1 = high + low

    # 第二次折半移位 (循环处理溢出)
    result2 = (result1 >> 16) + (result1 & 0xFFFF)
    while result2 > 0xFFFF:
        result2 = ((result2 >> 16) & 0xFFFF) + (result2 & 0xFFFF)

    # 取反码
    return (~result2) & 0xFFFF


if __name__ == '__main__':
    # 测试构建
    xml = build_fscan_xml(137000000, 173000000, 25000)
    print("=== FSCAN XML ===")
    print(xml)

    frame = build_rmcp_request_frame(xml)
    print(f"\n=== RMCP Frame ({len(frame)} bytes) ===")
    print(f"前50字节 hex: {frame[:50].hex()}")
