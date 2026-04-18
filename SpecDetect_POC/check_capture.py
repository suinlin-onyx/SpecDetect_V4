#!/usr/bin/env python
"""检查最新捕获的请求"""
import json
from pathlib import Path

capture_file = Path(r"D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC\rmcp_proxy\capture\capture_20260416_164739.json")
with open(capture_file, 'r', encoding='utf-8') as f:
    data = json.load(f)

print(f"总记录数: {len(data)}")

# 找所有 C->S 的请求
for i, entry in enumerate(data):
    if entry.get('direction') == 'C->S':
        print(f"\n=== C->S 请求 (第{i+1}条) ===")
        print(f"时间: {entry.get('timestamp')}")
        print(f"大小: {entry.get('size')} bytes")
        print(f"数据类型: {entry.get('data_type')}")

        hex_str = entry.get('hex', '')
        if hex_str:
            raw_bytes = bytes.fromhex(hex_str)
            print(f"RMCPTP头: {raw_bytes[:18].hex()}")
            # 解析 XML
            xml_start = hex_str.find('3c3f786d6c')  # 找 <?xml
            if xml_start >= 0:
                xml_hex = hex_str[xml_start:]
                xml_bytes = bytes.fromhex(xml_hex)
                try:
                    xml_content = xml_bytes.decode('gb2312')
                    print(f"XML内容:\n{xml_content}")
                except:
                    pass
        print()

# 统计方向
directions = {}
for entry in data:
    d = entry.get('direction', 'unknown')
    directions[d] = directions.get(d, 0) + 1
print(f"\n方向统计: {directions}")