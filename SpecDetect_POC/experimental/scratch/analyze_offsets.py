#!/usr/bin/env python3
"""V1: 逐 offset 分析 streamsrc 帧的变化模式，找疑似 STC/常量/帧号字段"""
import sys, glob, os
from collections import Counter

def parse(path):
    frames = []
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        hx = None
        for line in f:
            line = line.strip()
            if line.startswith('frame_hex='):
                hx = line[10:]
                frames.append(bytes.fromhex(hx))
    return frames

def classify_offset(col):
    """返回字段类别: const / incr / cycle / random"""
    uniq = set(col)
    if len(uniq) == 1:
        return 'CONST', f"=0x{col[0]:02x}"
    if len(uniq) == len(col):
        return 'UNIQUE', f"{len(uniq)} vals"
    if len(uniq) < 10:
        cnt = Counter(col)
        top = cnt.most_common(5)
        return 'ENUM', ','.join(f"0x{v:02x}×{c}" for v,c in top)
    # check monotonic
    diffs = [col[i+1]-col[i] for i in range(len(col)-1)]
    if all(d == diffs[0] for d in diffs):
        return 'LINEAR', f"step={diffs[0]}"
    return 'VARY', f"{len(uniq)} uniq"

def main(path):
    frames = parse(path)
    if not frames:
        print('no frames'); return
    n = len(frames)
    L = len(frames[0])
    print(f"file: {path}")
    print(f"frames: {n}, frame len: {L}")
    print()
    print(f"{'off':>3} {'hex':>6} {'class':<8} detail")
    print('-'*70)
    for off in range(min(L, 30)):
        col = [f[off] for f in frames]
        cls, detail = classify_offset(col)
        sample = ' '.join(f"{f[off]:02x}" for f in frames[:8])
        print(f"{off:3d}  {sample[:17]:17s} {cls:<8} {detail}")

    # FSCAN type split
    print("\n=== 按 offset 19 (FSCAN type) 分组 ===")
    by_t19 = {}
    for f in frames:
        by_t19.setdefault(f[19], []).append(f)
    for t19, grp in sorted(by_t19.items()):
        print(f"\n-- offset 19 = 0x{t19:02x} ({len(grp)} frames) --")
        for off in [12,13,14,15,16,17,18,20,21,22,23,24,25,26,27]:
            col = [f[off] for f in grp]
            cls, detail = classify_offset(col)
            print(f"  off {off:2d}: {cls:<8} {detail}")

if __name__ == '__main__':
    path = sys.argv[1] if len(sys.argv) > 1 else sorted(glob.glob('logs/streamsrc_raw_*.log'))[-1]
    main(path)
