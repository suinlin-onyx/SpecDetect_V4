#!/usr/bin/env python
"""检查多个抓包文件中 counters 是否固定"""
import json
import sys
from pathlib import Path

def check_counters(capture_dir):
    capture_dir = Path(capture_dir)
    counters_sets = {}

    for json_file in sorted(capture_dir.glob("capture_*.json")):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            for entry in data:
                if entry.get('direction') == 'S->C' and entry.get('data_type') == 'SIMPLE_FSCAN':
                    fscan = entry.get('fscan', {})
                    counters_key = str(fscan.get('counters', []))
                    n_arrays = fscan.get('nArrays', 0)
                    n_bd_type = fscan.get('nBdType', 0)

                    key = f"nBdType={n_bd_type}, nArrays={n_arrays}, counters={counters_key}"
                    counters_sets[key] = counters_sets.get(key, 0) + 1

        except Exception as e:
            print(f"Error reading {json_file}: {e}", file=sys.stderr)

    print("=== Counters 统计 ===")
    for k, v in counters_sets.items():
        print(f"  {k}: 出现 {v} 次")

if __name__ == '__main__':
    check_counters(r"D:\arvin\claude_workspace\SpecDetect_V4\SpecDetect_POC\rmcp_proxy\capture")