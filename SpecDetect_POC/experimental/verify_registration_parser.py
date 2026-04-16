#!/usr/bin/env python3
"""
验证 streamsrc 注册帧解析逻辑

测试从 streamsrc_raw_20260415_232120.log 中解析65字节注册帧
"""

import re
import sys
sys.path.insert(0, '..')

from streamsrc_parser import StreamsrcParser


def parse_log_file(log_path: str):
    """从日志文件解析streamsrc帧"""
    parser = StreamsrcParser()

    # 读取日志文件
    with open(log_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # 解析帧: =timestamp=\nsrc=ip:port\nsize=N bytes\nframe_hex=HEX\n\n
    pattern = r'=(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d+)=\nsrc=([\d.:]+)\nsize=(\d+) bytes\nframe_hex=([0-9a-f]+)'

    matches = re.findall(pattern, content)

    print(f"解析文件: {log_path}")
    print(f"总帧数: {len(matches)}")
    print("=" * 60)

    reg_count = 0
    spec_count = 0
    unknown_count = 0

    for timestamp, src, size, hex_data in matches[:10]:  # 只显示前10帧
        size = int(size)
        data = bytes.fromhex(hex_data)

        frame_type = parser.get_frame_type_name(data)

        print(f"\n时间: {timestamp}")
        print(f"来源: {src}")
        print(f"大小: {size} bytes")
        print(f"类型: {frame_type}")

        if parser.is_registration_frame(data):
            reg_count += 1
            reg_info = parser.parse_registration_frame(data)
            print(f"  SYNC: 0x{reg_info['sync']:08X}")
            print(f"  元数据: {reg_info['metadata']}")
            print(f"  频谱样本(前5): {reg_info['spectrum_sample'][:5]}")

            # 验证元数据固定值
            expected_meta = [256, 1441, 0, 0, -32768]
            if reg_info['metadata'] == expected_meta:
                print(f"  [OK] 元数据验证通过 [256, 1441, 0, 0, -32768]")
            else:
                print(f"  [FAIL] 元数据不匹配! 期望 {expected_meta}")

        elif parser.is_spectrum_frame(data):
            spec_count += 1
            spectrum = parser.parse_spectrum(data)
            print(f"  频谱点数: {len(spectrum)}")
            print(f"  dBm范围: {min(spectrum)} ~ {max(spectrum)}")

        else:
            unknown_count += 1

    # 统计
    print("\n" + "=" * 60)
    print(f"帧类型统计 (共 {len(matches)} 帧):")
    print(f"  注册帧 (65B): {reg_count}")
    print(f"  频谱帧 (1086B): {spec_count}")
    print(f"  未知帧: {unknown_count}")

    return len(matches)


if __name__ == "__main__":
    import os
    # 根据脚本位置确定路径
    script_dir = os.path.dirname(os.path.abspath(__file__))
    log_file = os.path.join(script_dir, "logs", "streamsrc_raw_20260415_232120.log")
    total = parse_log_file(log_file)
    print(f"\n验证完成: 成功解析 {total} 帧")