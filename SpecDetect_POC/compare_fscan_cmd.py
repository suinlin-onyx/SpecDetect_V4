#!/usr/bin/env python
"""对比真实 FSCAN 命令 vs 我们构建的命令"""
import json
import struct
from pathlib import Path

def analyze_real_fscan_command():
    """分析抓包中的真实 FSCAN 命令"""
    capture_file = Path(r"D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC\rmcp_proxy\capture\capture_20260416_151146.json")

    with open(capture_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    for entry in data:
        if entry.get('direction') == 'C->S' and entry.get('data_type') == 'XML_REQUEST':
            hex_str = entry.get('hex', '')
            if not hex_str:
                continue

            raw_bytes = bytes.fromhex(hex_str)
            print(f"=== 真实 FSCAN 请求 (C->S) ===")
            print(f"总长度: {len(raw_bytes)} bytes")

            # RMCPTP 头 (18 bytes)
            if len(raw_bytes) >= 18:
                dw_length = struct.unpack('<I', raw_bytes[0:4])[0]
                print(f"\nRMCPTP 头:")
                print(f"  dwLength: {dw_length}")
                print(f"  前18字节 hex: {raw_bytes[:18].hex()}")

            # XML 内容
            xml_content = entry.get('xml_content', '')
            print(f"\nXML 内容 (部分):")
            print(f"  {xml_content[:200]}...")

            # 找到 FSCAN 参数
            import re
            startfreq = re.search(r'startfreq[^>]*value="([^"]+)"', xml_content)
            stopfreq = re.search(r'stopfreq[^>]*value="([^"]+)"', xml_content)
            step = re.search(r'step[^>]*value="([^"]+)"', xml_content)

            if startfreq:
                print(f"\nXML 中的参数:")
                print(f"  startfreq: {startfreq.group(1)}")
                print(f"  stopfreq: {stopfreq.group(1) if stopfreq else 'N/A'}")
                print(f"  step: {step.group(1) if step else 'N/A'}")

            break

def analyze_our_fscan_command():
    """分析我们构建的 FSCAN 命令"""
    from app.atom_service.protocol_builder import RMCPTPBuilder

    builder = RMCPTPBuilder()
    cmd = builder.build_fscan_command(137000000, 173000000, 25000)

    print(f"\n=== 我们构建的 FSCAN 命令 ===")
    print(f"总长度: {len(cmd)} bytes")
    print(f"前18字节 hex: {cmd[:18].hex()}")

    # 解析我们构建的命令
    if len(cmd) >= 18:
        dw_length = struct.unpack('<I', cmd[0:4])[0]
        print(f"\nRMCPTP 头:")
        print(f"  dwLength: {dw_length}")

    # 业务数据部分
    payload_start = 18
    if len(cmd) > payload_start:
        payload = cmd[payload_start:]
        print(f"\n业务数据 ({len(payload)} bytes):")
        print(f"  hex: {payload.hex()}")

        # 解析业务数据头
        if len(payload) >= 5:
            n_bd_type = payload[0]
            n_arrays = struct.unpack('!I', payload[1:5])[0]
            print(f"  nBdType: 0x{n_bd_type:02X}")
            print(f"  nArrays: {n_arrays}")

        if len(payload) >= 25:
            start_freq = struct.unpack('!Q', payload[5:13])[0]
            end_freq = struct.unpack('!Q', payload[13:21])[0]
            step = struct.unpack('!Q', payload[21:29])[0]
            n_points = struct.unpack('!I', payload[29:33])[0]
            print(f"  start_freq: {start_freq}")
            print(f"  end_freq: {end_freq}")
            print(f"  step: {step}")
            print(f"  n_points: {n_points}")

if __name__ == '__main__':
    analyze_real_fscan_command()
    analyze_our_fscan_command()