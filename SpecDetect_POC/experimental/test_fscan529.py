#!/usr/bin/env python3
"""
分析 streamsrc FSCAN-529 帧的前17个元数据值
"""
import socket
import struct
import time
import re
import os
import sys

ATOM_HOST = '127.0.0.1'
ATOM_PORT = 8283
STREAMSRC_PORT = 18013

# 日志目录
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs', 'test')
os.makedirs(LOG_DIR, exist_ok=True)

# 日志文件
LOG_FILE = os.path.join(LOG_DIR, f'test_fscan529_{time.strftime("%Y%m%d_%H%M%S")}.log')
log_f = None

def log_print(*args, **kwargs):
    """同时打印到 stdout 和日志文件"""
    msg = ' '.join(str(a) for a in args)
    print(*args, **kwargs)
    if log_f:
        print(msg, file=log_f, flush=True)


def send_soap_raw(action, body_xml, desc):
    """直接走 socket 发 SOAP,对齐 atom_streamsrc_listener.py"""
    log_print(f"  [SOAP] {desc}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(30)
        sock.connect((ATOM_HOST, ATOM_PORT))
        body_bytes = body_xml.encode('gb2312')
        req = (
            f"POST /{action} HTTP/1.1\r\n"
            f"Host: {ATOM_HOST}:{ATOM_PORT}\r\n"
            f"Content-Type: text/xml; charset=gb2312\r\n"
            f"SOAPAction: {action}\r\n"
            f"Content-Length: {len(body_bytes)}\r\n\r\n"
        ).encode('utf-8') + body_bytes
        sock.sendall(req)
        resp = b''
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                resp += chunk
                if b'</soapenv:Envelope>' in resp:
                    break
            except socket.timeout:
                break
        sock.close()
        text = resp.decode('utf-8', errors='replace')
        log_print(f"  [OK] 响应长度 {len(resp)}")
        return text
    except Exception as e:
        log_print(f"  [ERROR] {e}")
        return None


def b_fscan():
    """B_FScan - 结构对齐 atom_streamsrc_listener.py"""
    body = '''<?xml version="1.0" encoding="gb2312"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody>
<srrc:appid>123456</srrc:appid>
<srrc:userid>RX_admin</srrc:userid>
<srrc:priority>9</srrc:priority>
<srrc:executetime>0</srrc:executetime>
<srrc:mfid>53090001140012</srrc:mfid>
<srrc:equid>51cd8dfe-e543-40c9-bdc3-a292766fee7f</srrc:equid>
<srrc:equpara><srrc:groupitems><srrc:groupitem><srrc:groupid>1</srrc:groupid>
<srrc:items><srrc:item><srrc:paraname>startfreq</srrc:paraname><srrc:paravalue>137000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>stopfreq</srrc:paraname><srrc:paravalue>173000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>step</srrc:paraname><srrc:paravalue>25000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>gain</srrc:paraname><srrc:paravalue>AGC</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>rfworkmode</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>scanmode</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item>
</srrc:items></srrc:groupitem></srrc:groupitems></srrc:equpara>
<srrc:outputchannel><srrc:mode>source</srrc:mode><srrc:datachannel>stream</srrc:datachannel></srrc:outputchannel>
</srrc:requestbody></soapenv:Body></soapenv:Envelope>'''
    return send_soap_raw("B_FScan", body, "B_FScan")


def b_stop_meas(taskid):
    body = f'''<?xml version="1.0" encoding="gb2312"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody>
<srrc:appid>123456</srrc:appid><srrc:userid>RX_admin</srrc:userid>
<srrc:priority>9</srrc:priority><srrc:executetime>0</srrc:executetime>
<srrc:mfid>53090001140012</srrc:mfid>
<srrc:equid>51cd8dfe-e543-40c9-bdc3-a292766fee7f</srrc:equid>
<srrc:taskid>{taskid}</srrc:taskid>
</srrc:requestbody></soapenv:Body></soapenv:Envelope>'''
    return send_soap_raw("B_StopMeas", body, "B_StopMeas")


def connect_streamsrc(taskid):
    """连接 streamsrc（不对齐 atom_streamsrc_listener: 不发注册帧）"""
    log_print(f"  [TCP] 连接 streamsrc {ATOM_HOST}:{STREAMSRC_PORT}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ATOM_HOST, STREAMSRC_PORT))
        log_print(f"  [OK] 连接成功")
        return sock
    except Exception as e:
        log_print(f"  [ERROR] {e}")
        return None


def parse_atom_frame(data):
    """解析 Atom streamsrc 帧

    帧结构:
    - Offset 0-3:   0xEEEEEEEE (sync)
    - Offset 4-5:   VER (2 bytes, big-endian)
    - Offset 6-9:   STC (4 bytes, little-endian)
    - Offset 10-17: TS (8 bytes, FILETIME)
    - Offset 18:    FrameSeq (1 byte)
    - Offset 19:    Indicator (0x26=FSCAN-529, 0x68=FSCAN-434)
    - Offset 20-47: Reserved
    - Offset 48-61: Metadata (7 x int16 little-endian)
    - Offset 62+:   频谱数据 (交替字节模式 [dBm][0xFF][dBm][0xFF]...)
    """
    if len(data) < 4 or data[:4] != bytes.fromhex('eeeeeeee'):
        return None

    # TASKID 帧检测
    if len(data) >= 64:
        if 32 <= data[29] <= 126:
            return {'type': 'TASKID', 'taskid': data[29:64].decode('ascii', errors='replace').strip('\x00')}

    fscan_type = data[19]

    # FSCAN 帧
    if fscan_type in (0x26, 0x68):
        frame_type = 'FSCAN-529' if fscan_type == 0x26 else 'FSCAN-434'

        # 完整性检查
        if fscan_type == 0x26 and len(data) != 1086:
            return None
        if fscan_type == 0x68 and len(data) != 896:
            return None

        # 解析帧头字段
        ver = struct.unpack('>H', data[4:6])[0]  # big-endian
        stc = struct.unpack('<I', data[6:10])[0]  # little-endian
        ts = struct.unpack('<Q', data[10:18])[0]  # FILETIME
        frame_seq = data[18]
        indicator = data[19]
        metadata = list(struct.unpack('<7h', data[48:62]))

        # 解析频谱数据 (交替字节模式，从 offset 62 开始)
        spectrum = []
        spectrum_data = data[62:]

        # 交替字节模式: [dBm][0xFF][dBm][0xFF]...
        for i in range(0, len(spectrum_data) - 1, 2):
            value = spectrum_data[i]
            marker = spectrum_data[i + 1]
            if marker == 0xFF:
                if value > 127:
                    dbm = -(256 - value)
                else:
                    dbm = value
                spectrum.append(dbm)

        if len(spectrum) > 0:
            return {
                'type': frame_type,
                'size': len(data),
                'ver': ver,
                'stc': stc,
                'ts': ts,
                'frame_seq': frame_seq,
                'indicator': indicator,
                'metadata': metadata,
                'level_count': len(spectrum),
                'levels': spectrum,
                'dbm_min': min(spectrum),
                'dbm_max': max(spectrum),
                'dbm_avg': sum(spectrum) / len(spectrum)
            }
    return None


def filetime_to_datetime(ft: int):
    """FILETIME (100-nanosecond intervals since 1601-01-01) -> datetime string"""
    import datetime
    try:
        us = ft // 10  # 100ns -> us
        dt = datetime.datetime(1601, 1, 1) + datetime.timedelta(microseconds=us)
        return dt.strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
    except:
        return str(ft)


def receive_fscan_frames(sock, count=5, timeout=30):
    """接收 FSCAN 帧 - 解析并显示帧信息"""
    log_print(f"  [TCP] 等待接收 FSCAN 帧 (超时 {timeout}s)...")
    recv_buffer = b''
    frame_count = 0
    fscan_529_count = 0
    fscan_434_count = 0
    start_time = time.time()
    interrupted = False

    while time.time() - start_time < timeout and not interrupted:
        try:
            sock.settimeout(2)  # 短超时以便响应Ctrl+C
            chunk = sock.recv(65536)
            if not chunk:
                elapsed = time.time() - start_time
                log_print(f"  [WARN] 连接关闭 (FSCAN-529:{fscan_529_count}帧, FSCAN-434:{fscan_434_count}帧, 耗时 {elapsed:.1f}s)")
                break

            recv_buffer += chunk

            # 从 buffer 中提取完整帧
            while len(recv_buffer) >= 28:
                if recv_buffer[:4] != bytes.fromhex('eeeeeeee'):
                    recv_buffer = recv_buffer[1:]
                    continue

                fscan_type = recv_buffer[19]
                frame_len = 1086 if fscan_type == 0x26 else (896 if fscan_type == 0x68 else 0)

                if frame_len == 0 or len(recv_buffer) < frame_len:
                    break

                frame_data = recv_buffer[:frame_len]
                recv_buffer = recv_buffer[frame_len:]

                result = parse_atom_frame(frame_data)
                if not result:
                    continue
                if 'level_count' not in result:
                    continue

                frame_count += 1
                elapsed = time.time() - start_time
                if result['type'] == 'FSCAN-529':
                    fscan_529_count += 1
                else:
                    fscan_434_count += 1

                # 打印结构化日志
                import datetime
                now_str = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                sample_levels = result['levels'][:20]
                log_print(f"Time: {now_str}:18013")
                log_print(f"Direction: S->C")
                log_print(f"Source: 127.0.0.1:18013")
                log_print(f"Size: {result['size']} bytes")
                log_print(f"Frame Header:")
                log_print(f"  Sync: 0xEEEEEEEE")
                log_print(f"  VER: {result['ver']}")
                log_print(f"  STC: {result['stc']}")
                log_print(f"  TS: {filetime_to_datetime(result['ts'])}")
                log_print(f"  FrameSeq: {result['frame_seq']}")
                log_print(f"  Indicator: 0x{result['indicator']:02x} ({result['type']})")
                log_print(f"  Metadata[0-6]: {result['metadata']}")
                log_print(f"FSCAN Data:")
                log_print(f"  电平数量: {result['level_count']}")
                log_print(f"  dBm范围: {result['dbm_min']:.1f} ~ {result['dbm_max']:.1f} (avg: {result['dbm_avg']:.1f})")
                log_print(f"  dBm样本: {[round(x, 1) for x in sample_levels]}")
                log_print()

        except socket.timeout:
            continue
        except KeyboardInterrupt:
            elapsed = time.time() - start_time
            log_print(f"\n  [INFO] Ctrl+C 中断 (FSCAN-529:{fscan_529_count}帧, FSCAN-434:{fscan_434_count}帧, 耗时 {elapsed:.1f}s)")
            interrupted = True
            break

    return []


def main():
    global log_f
    log_f = open(LOG_FILE, 'w', encoding='utf-8')
    log_print(f"日志文件: {LOG_FILE}")

    log_print("=" * 60)
    log_print("分析 streamsrc FSCAN-529 帧的前17个元数据值")
    log_print("=" * 60)

    try:
        # Step 1: B_FScan
        log_print("\n[Step 1] B_FScan")
        resp = b_fscan()
        if not resp:
            log_print("[ERROR] B_FScan 失败")
            return

        # 解析 taskid
        taskid_match = re.search(r'<srrc:taskid>([^<]+)</srrc:taskid>', resp)
        if not taskid_match:
            log_print("[ERROR] 未找到 taskid")
            log_print(f"响应全文:\n{resp}")
            return

        taskid = taskid_match.group(1)
        log_print(f"  [OK] TaskID: {taskid}")
        time.sleep(1)

        # Step 3: 连接 streamsrc
        log_print("\n[Step 3] 连接 streamsrc")
        sock = connect_streamsrc(taskid)
        if not sock:
            return

        # Step 4: 接收 FSCAN-529 帧
        log_print("\n[Step 4] 接收 FSCAN-529 帧")
        try:
            metadata_frames = receive_fscan_frames(sock, count=5)
        finally:
            sock.close()
            # 必须发 B_StopMeas 避免 Atom 僵死
            log_print("\n[Step 5] B_StopMeas")
            b_stop_meas(taskid)

        # Step 5: 分析元数据
        log_print("\n" + "=" * 60)
        log_print("元数据值分析 (前17个值)")
        log_print("=" * 60)

        for i in range(17):
            vals = [m[i] for m in metadata_frames]
            unique = set(vals)
            stable = len(unique) == 1
            log_print(f"  Metadata[{i:2d}]: values={vals[:3]}... unique={len(unique)} {'STABLE' if stable else 'VARIES'}")
    finally:
        log_f.close()


if __name__ == '__main__':
    main()
