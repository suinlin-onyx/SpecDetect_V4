# FSCAN Frame Structure Analysis

**PCAP Source:** `D:\arvin\claude_workspace\RXAtomSvcV3\2026-4\20260416_190539_8282_18012_9996.pcap`
**Analysis Date:** 2026-04-17
**Session Seq:** 59911

## Overview

The PCAP contains **13 FSCAN frames** from Real Atom streamsrc (port 18012 TCP):
- **9 FSCAN-529 frames** (1086 bytes, indicator `0x26`)
- **4 FSCAN-434 frames** (896 bytes, indicator `0x68`)

These frames are interleaved and represent spectrum sweep data with varying frequency ranges.

---

## Frame Structure

### FSCAN-529 (1086 bytes, offset19=0x26)

| Field | Offset | Size | Example Value |
|-------|--------|------|---------------|
| Magic | 0 | 4 | `eeeeeeee` |
| Version | 4 | 2 | `0100` (big-endian 1) |
| Session ID | 6 | 4 | `99c2e069` |
| Sequence | 10 | 2 | `59911` |
| Channel | 12 | 2 | `0410` |
| FreqLow | 14 | 2 | `1306` (4870 MHz) |
| FreqHigh | 16 | 2 | `04b7` (varies) |
| FrameType | 18 | 1 | `00` |
| Indicator | 19 | 1 | `26` (FSCAN-529 identifier) |
| Length | 20 | 2 | `0400` (1024) |
| Reserved | 22 | 2 | `0000` |
| Metadata | 24 | 8 | `0c2104000001a105` |
| Extra Metadata | 32 | 30 | calibration/frequency markers |
| Spectrum Data | 62 | 1004 | 502 dBm values (alternating with 0xFF) |
| Footer | 1066 | 20 | dBm values with 0xFF padding |

### FSCAN-434 (896 bytes, offset19=0x68)

| Field | Offset | Size | Example Value |
|-------|--------|------|---------------|
| Magic | 0 | 4 | `eeeeeeee` |
| Version | 4 | 2 | `0100` |
| Session ID | 6 | 4 | `99c2e069` |
| Sequence | 10 | 2 | `59911` |
| Channel | 12 | 2 | `0410` |
| FreqLow | 14 | 2 | `1306` (4870 MHz) |
| FreqHigh | 16 | 2 | `04b1` (varies) |
| FrameType | 18 | 1 | `01` |
| Indicator | 19 | 1 | `68` (FSCAN-434 identifier) |
| Length | 20 | 2 | `0300` (768) |
| Reserved | 22 | 2 | `0000` |
| Metadata | 24 | 8 | `0c6303000001a105` |
| Extra Metadata | 32 | 30 | calibration/frequency markers |
| Spectrum Data | 62 | 814 | 407 dBm values (alternating with 0xFF) |
| Footer | 876 | 20 | dBm values with 0xFF padding |

---

## Key Findings

### 1. Spectrum Data Encoding

The spectrum data uses an alternating byte pattern:
- **Even indices (0, 2, 4, ...)**: Actual dBm values (unsigned 0-255)
- **Odd indices (1, 3, 5, ...)**: Always `0xFF` (padding/marker)

**Example (first 16 bytes of spectrum):**
```
Byte:     [172] [255] [186] [255] [185] [255] [192] [255] ...
dBm:        -84   N/A    -70   N/A    -71   N/A    -64   N/A ...
```

**dBm conversion:** `dBm = -(256 - value)` for values > 127

- FSCAN-529: **502 spectrum points** (1004 bytes / 2)
- FSCAN-434: **407 spectrum points** (814 bytes / 2)

### 2. Frequency Coverage

| Parameter | Value |
|-----------|-------|
| FreqLow | 4870 MHz (fixed) |
| FreqHigh | 1048-1462 MHz (varies by frame) |
| Span | 3408-3822 MHz (varies) |

The varying FreqHigh suggests the device sweeps through different center frequencies.

### 3. Frame Combination Rules

FSCAN-529 and FSCAN-434 are **NOT simple upper/lower halves** of a complete spectrum:

1. **Different frequency spans** when consecutive:
   - FSCAN-529: 4870-1061 (3809 MHz)
   - FSCAN-434: 4870-1201 (3669 MHz)

2. **Ratio**: FSCAN-529 appears ~2.25x more frequently than FSCAN-434

3. **Possible relationship**: They may represent:
   - Different FFT modes (wideband vs narrowband)
   - Calibration sweep vs normal sweep
   - Different resolution settings

### 4. Frame Type Byte (offset 18)

The byte at offset 18 cycles through `00`, `01`, `02`, `03` across frames, suggesting an internal frame counter within a sweep sequence.

---

## Data Organization Summary

```
Frame Layout (both FSCAN-529 and FSCAN-434):

+---------+--------+--------+----------+---------+--------+
| Header  | Meta   | Extra  | Spectrum | Footer  |
| (24 B)  | (8 B)  | (30 B) | (N B)    | (20 B)  |
+---------+--------+--------+----------+---------+--------+

Spectrum is stored as: [dBm][0xFF][dBm][0xFF]...
```

---

## Consecutive Frame Sequence Observed

| Packet | Type | Length | FreqHigh | Span | Notes |
|--------|------|--------|----------|------|-------|
| 33 | FSCAN-529 | 1086 | 1207 | 3663 | First frame |
| 37 | FSCAN-529 | 1086 | 1061 | 3809 | Type=1 |
| 41 | FSCAN-434 | 896 | 1201 | 3669 | |
| 45 | FSCAN-529 | 1086 | 1054 | 3816 | |
| 49 | FSCAN-529 | 1086 | 1195 | 3675 | |
| 53 | FSCAN-434 | 896 | 1048 | 3822 | |
| 57 | FSCAN-529 | 1086 | 1188 | 3682 | |
| 61 | FSCAN-529 | 1086 | 1462 | 3408 | Type=0 (new cycle?) |
| 65 | FSCAN-434 | 896 | 1315 | 3555 | |
| ... | | | | | |

---

## Interpretation for SpecDetect Integration

1. **Do NOT assume FSCAN-529 + FSCAN-434 = complete spectrum** - They cover different spans
2. **Filter by indicator byte**: `0x26` for FSCAN-529, `0x68` for FSCAN-434
3. **Extract dBm values** by taking every other byte starting at offset 62
4. **Frequency mapping**: Use FreqLow/FreqHigh with span / point_count

---

## Reference

- Real Atom streamsrc protocol
- Sequence number: 59911 (consistent across all frames)
- Source: TCP port 18012 responses
