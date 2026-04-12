# -*- coding: utf-8 -*-
"""
RMCP 帧对比工具

功能:
1. 从 predicted_rmcp.bin 提取 XML
2. 从 capture_*.raw 中查找匹配的帧
3. 对比两者的结构和内容

魔数参考值: 03CADC01
"""

import os
import struct
import re
from pathlib import Path


def extract_xml_from_rmcp(frame_bytes: bytes) -> str:
    """从 RMCP 帧提取 XML 内容"""
    # RMCP 头部长度固定 19 字节
    header_len = 19
    if len(frame_bytes) <= header_len:
        return None

    xml_bytes = frame_bytes[header_len:]
    # 去掉 null 终止符
    if xml_bytes.endswith(b'\x00'):
        xml_bytes = xml_bytes[:-1]

    try:
        return xml_bytes.decode('gb2312')
    except:
        try:
            return xml_bytes.decode('utf-8')
        except:
            return None


def parse_rmcp_header(frame_bytes: bytes) -> dict:
    """解析 RMCP 帧头"""
    if len(frame_bytes) < 18:
        return None

    header = {
        'dwLength': struct.unpack('<I', frame_bytes[0:4])[0],
        'seq': frame_bytes[4:8].hex(),
        'magic': frame_bytes[8:12].hex(),
        'b0': frame_bytes[12],
        'nVersion': frame_bytes[13],
        'nMsgType': frame_bytes[14],
        'nFlags': frame_bytes[15],
        'nCheckSum': struct.unpack('<H', frame_bytes[16:18])[0],
    }
    return header


def extract_params_from_xml(xml_content: str) -> dict:
    """从 XML 提取关键业务参数"""
    params = {}

    # 提取 funcid
    match = re.search(r'funcid="(\d+)"', xml_content)
    if match:
        params['funcid'] = int(match.group(1))

    # 提取 startfreq
    match = re.search(r'<item name="startfreq" value="([^"]+)"', xml_content)
    if match:
        params['startfreq'] = match.group(1)

    # 提取 stopfreq
    match = re.search(r'<item name="stopfreq" value="([^"]+)"', xml_content)
    if match:
        params['stopfreq'] = match.group(1)

    # 提取 step
    match = re.search(r'<item name="step" value="([^"]+)"', xml_content)
    if match:
        params['step'] = match.group(1)

    # 提取 stationid
    match = re.search(r'stationid="([^"]+)"', xml_content)
    if match:
        params['stationid'] = match.group(1)

    # 提取 deviceid
    match = re.search(r'deviceid="([^"]+)"', xml_content)
    if match:
        params['deviceid'] = match.group(1)

    return params


def find_matching_frame_in_raw(predicted_xml: str, raw_file: str) -> list:
    """在 capture_*.raw 中查找匹配 predicted_xml 的帧"""
    matches = []

    with open(raw_file, 'rb') as f:
        data = f.read()

    offset = 0
    frame_num = 0

    while offset < len(data):
        if offset + 18 > len(data):
            break

        # 解析帧头获取长度
        dwLength = struct.unpack('<I', data[offset:offset+4])[0]

        # 检查长度合理性
        if dwLength < 18 or dwLength > 100000:
            offset += 1
            continue

        if offset + dwLength > len(data):
            offset += 1
            continue

        frame_bytes = data[offset:offset + dwLength]
        header = parse_rmcp_header(frame_bytes)

        # 跳过魔数检查，因为 soap_proxy 和 Atom 可能用不同魔数
        # 只检查帧长度合理性
        if header and 50 < header['dwLength'] < 10000:
            xml_content = extract_xml_from_rmcp(frame_bytes)
            if xml_content and len(xml_content) > 50:  # XML 内容要足够长
                params = extract_params_from_xml(xml_content)
                matches.append({
                    'frame_num': frame_num,
                    'offset': offset,
                    'header': header,
                    'xml': xml_content,
                    'params': params,
                    'xml_hash': hash(xml_content),
                })

        offset += dwLength
        frame_num += 1

    return matches


def compare_frames(predicted_file: str, raw_file: str):
    """
    对比 predicted_rmcp.bin 和 capture_*.raw 中的帧
    """
    print(f"=" * 80)
    print(f"对比工具")
    print(f"=" * 80)

    # 1. 读取 predicted_rmcp
    print(f"\n[1] 读取预测帧: {predicted_file}")
    with open(predicted_file, 'rb') as f:
        predicted_data = f.read()

    predicted_header = parse_rmcp_header(predicted_data)
    predicted_xml = extract_xml_from_rmcp(predicted_data)
    predicted_params = extract_params_from_xml(predicted_xml) if predicted_xml else {}

    print(f"    帧长度: {predicted_header['dwLength']}")
    print(f"    序列号: {predicted_header['seq']}")
    print(f"    魔数: {predicted_header['magic']}")
    print(f"    消息类型: {predicted_header['nMsgType']} (90=REQUEST)")
    print(f"    校验和: {predicted_header['nCheckSum']:#x}")
    print(f"    XML参数: {predicted_params}")

    # 2. 在 raw 文件中搜索匹配帧
    print(f"\n[2] 在 capture 文件中搜索: {raw_file}")
    matches = find_matching_frame_in_raw(predicted_xml, raw_file)

    print(f"    找到 {len(matches)} 个帧")

    if not matches:
        print(f"\n    未找到匹配帧!")
        print(f"    提示: 检查 capture 文件是否包含 B_FScan 请求")
        return

    # 3. 对比每个匹配帧
    print(f"\n[3] 对比结果:")
    print(f"-" * 80)

    for i, match in enumerate(matches[:5]):  # 最多显示5个
        print(f"\n匹配帧 #{i+1} (frame #{match['frame_num']}, offset={match['offset']}):")
        print(f"  帧长度: {match['header']['dwLength']}")
        print(f"  序列号: {match['header']['seq']}")
        print(f"  魔数: {match['header']['magic']}")
        print(f"  消息类型: {match['header']['nMsgType']}")
        print(f"  校验和: {match['header']['nCheckSum']:#x}")
        print(f"  XML参数: {match['params']}")

        # 对比关键字段
        print(f"\n  结构对比:")
        print(f"    魔数: {'SAME' if predicted_header['magic'] == match['header']['magic'] else 'DIFF'} ({predicted_header['magic']} vs {match['header']['magic']})")
        print(f"    消息类型: {'SAME' if predicted_header['nMsgType'] == match['header']['nMsgType'] else 'DIFF'}")
        print(f"    nFlags: {'SAME' if predicted_header['nFlags'] == match['header']['nFlags'] else 'DIFF'}")
        print(f"    XML内容: {'SAME' if hash(predicted_xml) == match['xml_hash'] else 'DIFF'}")

        if predicted_params:
            param_match = all(
                predicted_params.get(k) == match['params'].get(k)
                for k in predicted_params.keys()
            )
            print(f"    业务参数: {'SAME' if param_match else 'DIFF'}")

        # 显示 XML 前100字符
        xml_preview = match['xml'][:150].replace('\n', ' ')
        print(f"    XML预览: {xml_preview}...")

    print(f"\n{'=' * 80}")


if __name__ == '__main__':
    import sys

    if len(sys.argv) < 3:
        print("用法: python compare_frames.py <predicted_rmcp.bin> <capture.raw>")
        print("示例: python compare_frames.py conversion_output/.../20260411_220541__predicted_rmcp.bin rmcp_proxy/capture/capture_20260411_220513.raw")
        sys.exit(1)

    predicted_file = sys.argv[1]
    raw_file = sys.argv[2]

    if not os.path.exists(predicted_file):
        print(f"错误: 找不到文件 {predicted_file}")
        sys.exit(1)

    if not os.path.exists(raw_file):
        print(f"错误: 找不到文件 {raw_file}")
        sys.exit(1)

    compare_frames(predicted_file, raw_file)
