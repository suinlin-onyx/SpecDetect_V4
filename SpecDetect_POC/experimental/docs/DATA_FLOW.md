# Emulated Atom 与 test_fscan529 数据流说明

## 概述

```
test_fscan529.py (客户端)                emulated_atom.py (服务端)
        |                                        |
        |--- B_FScan (SOAP HTTP) -------------->|
        |<-- SOAP 响应 (含 taskid) --------------|
        |                                        |
        |--- TCP 连接 streamsrc 18013 ---------->|
        |                                        |
        |                          [B_FScan 已处理，session 已创建]
        |                          [从 rmcp_proxy 或 capture 获取频谱]
        |                          [构建 streamsrc 帧]
        |<-- streamsrc FSCAN-529 帧 (1086B) ----|
        |                                        |
        |--- B_StopMeas (SOAP) ---------------->|
        |<-- SOAP 响应 --------------------------|
```

## 数据流各阶段详解

### 1. B_FScan 请求 (test → emulated_atom)

**端口**: SOAP 8283

**test_fscan529.py 发送**:
```http
POST /B_FScan HTTP/1.1
Host: 127.0.0.1:8283
Content-Type: text/xml; charset=utf-8
SOAPAction: B_FScan
Content-Length: ...

<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope ...>
  <srrc:requestbody>
    <srrc:appid>123456</srrc:appid>
    <srrc:mfid>53090001140012</srrc:mfid>
    <srrc:equid>51cd8dfe-...</srrc:equid>
    <srrc:equpara>
      <srrc:groupitems>
        <srrc:item><srrc:paraname>startfreq</srrc:paraname><srrc:paravalue>137000000</srrc:paravalue></srrc:item>
        <srrc:item><srrc:paraname>stopfreq</srrc:paraname><srrc:paravalue>173000000</srrc:paravalue></srrc:item>
        <srrc:item><srrc:paraname>step</srrc:paraname><srrc:paravalue>25000</srrc:paravalue></srrc:item>
        ...
      </srrc:groupitems>
    </srrc:equpara>
    <srrc:outputchannel>...</srrc:outputchannel>
  </srrc:requestbody>
</soapenv:Envelope>
```

**emulated_atom.py 处理** (`_handle_fscan`):
1. 解析 SOAP XML，提取 startfreq/stopfreq/step
2. 生成 taskid (格式: `EA-{timestamp}`)
3. 发送 SOAP 响应 (HTTP 200)
4. 创建 `StreamSession` 加入 `pending_sessions` (等待 streamsrc 客户端连接)
5. 调用 `_get_fscan_spectrum()` 获取频谱数据
6. 调用 `build_streamsrc_frame()` 构建 streamsrc 帧
7. 调用 `streamsrc_server.push_frame()` 推送给已连接的客户端

### 2. streamsrc 连接 (test → emulated_atom)

**端口**: TCP 18013

**test_fscan529.py**:
```python
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
sock.connect(('127.0.0.1', 18013))
```

**emulated_atom.py 处理** (`StreamSrcServer._accept_loop`):
1. 接受客户端连接
2. 调用 `_try_match_pending_session()` 将新客户端关联到最早的 pending_session
3. 从 `pending_sessions` 移到 `sessions`

### 3. 频谱数据获取 (emulated_atom → rmcp_proxy)

**emulated_atom.py `_get_fscan_spectrum`**:

```
优先尝试:
1. _get_fscan_from_capture() - 从 rmcp_proxy capture JSON 读取
2. _get_fscan_from_rmcp_proxy() - 直接连接 rmcp_proxy
3. fallback: _get_mock_spectrum() - 生成模拟数据
```

**rmcp_proxy 数据格式** (RMCPTP over TCP 1449):
```
RMCP 帧头 (18 bytes):
  offset 0-3:   dwLength (little-endian uint32)
  offset 4-11:  tmStamp (8 bytes FILETIME)
  offset 12-13: nVersion (uint16)
  offset 14:    nMsgType (uint8, 0=MSG_TYPE_DATA)
  offset 15:    nFlags (uint8)
  offset 16-17: nCheckSum (uint16)

FSCAN Payload (dwLength bytes):
  offset 0:     nBdType (0x0F = 15 = FSCAN)
  offset 1-2:   reserved
  offset 3-10:  counters[4] (4 x int16 little-endian, counters[0] = nArrays)
  offset 11+:    levels (int16 little-endian, 每帧通常 512 点, dBm×10)
```

### 4. streamsrc 帧推送 (emulated_atom → test)

**端口**: TCP 18013

**帧格式** (1086 bytes):

```
Offset 0-3:   Sync        = 0xEEEEEEEE (4 bytes, little-endian)
Offset 4-5:   VER         = 0x0100 (2 bytes, big-endian) → 256
Offset 6-9:   STC         = 同步通道号 (4 bytes, little-endian)
Offset 10-17:  TS          = FILETIME 时间戳 (8 bytes)
Offset 18:     FrameSeq    = 帧序列号 (1 byte)
Offset 19:     Indicator   = 0x26 (FSCAN-529) 或 0x68 (FSCAN-434)
Offset 20-47:  Reserved    = 0x00
Offset 48-61:  Metadata[7] = 7 x int16 little-endian
                        [16801, 0, 0, 20480, 18115, 512, 0]
Offset 62+:    Spectrum    = 交替字节模式
                        [dBm_byte][0xFF][dBm_byte][0xFF]...
                        共 1024 bytes = 512 points
```

**dBm 编码**:
- 负值 dBm: `byte = 256 + dBm` (例如 -84 → 172)
- 正值 dBm: `byte = dBm`
- Marker: 始终 `0xFF`

**emulated_atom.py** (`build_streamsrc_frame`):
```python
frame = bytearray(1086)
struct.pack_into('<I', frame, 0, 0xEEEEEEEE)  # Sync
struct.pack_into('>H', frame, 4, 256)          # VER
struct.pack_into('<I', frame, 6, stc)           # STC
struct.pack_into('<Q', frame, 10, ts)          # TS
frame[18] = 0x00                                # FrameSeq
frame[19] = 0x26                               # Indicator
# Metadata at 48-61
struct.pack_into('<7h', frame, 48, *metadata)
# Spectrum at 62+
for dbm in spectrum_dbm:
    byte_val = 256 + dbm if dbm < 0 else int(dbm)
    frame[spectrum_offset] = byte_val
    frame[spectrum_offset + 1] = 0xFF
    spectrum_offset += 2
```

### 5. FSCAN 帧解析 (test_fscan529.py)

**parse_atom_frame**:
```python
def parse_atom_frame(data):
    # Offset 0-3: sync check
    if data[:4] != bytes.fromhex('eeeeeeee'):
        return None

    # TASKID 帧检测 (非 FSCAN 帧)
    if 32 <= data[29] <= 126:
        return {'type': 'TASKID', 'taskid': data[29:64].decode('ascii')}

    fscan_type = data[19]
    if fscan_type == 0x26:
        # 完整性检查: len(data) == 1086

        # 帧头解析
        ver = struct.unpack('>H', data[4:6])[0]   # 256
        stc = struct.unpack('<I', data[6:10])[0]   # STC
        ts = struct.unpack('<Q', data[10:18])[0]   # FILETIME
        frame_seq = data[18]
        indicator = data[19]
        metadata = list(struct.unpack('<7h', data[48:62]))

        # 频谱解析 (交替字节模式)
        spectrum = []
        for i in range(62, len(data)-1, 2):
            value = data[i]
            marker = data[i+1]
            if marker == 0xFF:
                dbm = -(256 - value) if value > 127 else value
                spectrum.append(dbm)

        return {
            'type': 'FSCAN-529',
            'ver': ver, 'stc': stc, 'ts': ts,
            'frame_seq': frame_seq, 'indicator': indicator,
            'metadata': metadata,
            'level_count': len(spectrum),
            'levels': spectrum,
            'dbm_min': min(spectrum), 'dbm_max': max(spectrum),
            'dbm_avg': sum(spectrum)/len(spectrum)
        }
```

### 6. B_StopMeas (test → emulated_atom)

**test_fscan529.py**:
```http
POST /B_StopMeas HTTP/1.1
...
<srrc:taskid>EA-1776421652</srrc:taskid>
```

**emulated_atom.py** (`_handle_stopmeas`):
1. 解析 taskid
2. 查找对应 session
3. 发送 B_StopMeas 到 rmcp_proxy
4. 清理 session

## 日志输出

| 文件 | 路径 | 内容 |
|------|------|------|
| emulated_atom debug | `logs/emulated_atom/emulated_debug.log` | 所有调试信息 |
| rmcp_proxy capture | `logs/rmcp_capture/capture_1449_*.log` | RMCP 帧日志 |
| test_fscan529 | `logs/test/test_fscan529_*.log` | FSCAN 帧结构化日志 |

## 关键常量

```python
# emulated_atom.py
SOAP_PORT = 8283
STREAMSRC_PORT = 18013
RMCP_PROXY_HOST = '100.72.95.36'
RMCP_PROXY_PORT = 1449

STREAMSRC_LEADER = 0xEEEEEEEE
STREAMSRC_VER = 0x0100  # big-endian = 256
DT_FSCAN = 12

# streamsrc 帧
FRAME_SIZE_529 = 1086  # FSCAN-529
FRAME_SIZE_434 = 896   # FSCAN-434
INDICATOR_529 = 0x26
INDICATOR_434 = 0x68

# RMCP 帧头
RMCP_HEADER_SIZE = 18
MSG_TYPE_DATA = 0
NBDTYPE_FSCAN = 15
```

## 数据流图

```
test_fscan529                    emulated_atom                  rmcp_proxy/device
    |                                |                                |
    |-------- B_FScan (8283) ------>|                                |
    |<------ SOAP 200 OK -----------|                                |
    |      (含 taskid)              |                                |
    |                                |                                |
    |========= TCP 18013 ===========|                                |
    |                                |                                |
    |                                |--- RMCP Request (1449) ------>|
    |                                |<-- RMCP FSCAN Response --------|
    |                                |    (多个帧, 流式)              |
    |                                |                                |
    |<----- streamsrc 帧 (18013) ----|                                |
    |     (1086B, 512点, 交替字节)   |                                |
    |                                |                                |
    |-------- B_StopMeas (8283) --->|                                |
    |<------ SOAP 200 OK ------------|                                |
    |                                |--- B_StopMeas (1449) --------->|
    |                                |                                |
```
