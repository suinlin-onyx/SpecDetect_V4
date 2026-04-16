#!/usr/bin/env python3
"""
分析 streamsrc FSCAN-529 帧的前17个元数据值
"""
import socket
import struct
import time
import re

ATOM_HOST = '127.0.0.1'
ATOM_PORT = 8282
STREAMSRC_PORT = 18012


def send_soap_raw(action, body_xml, desc):
    """直接走 socket 发 SOAP,对齐 atom_streamsrc_listener.py"""
    print(f"  [SOAP] {desc}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(30)
        sock.connect((ATOM_HOST, ATOM_PORT))
        body_bytes = body_xml.encode('utf-8')
        req = (
            f"POST /{action} HTTP/1.1\r\n"
            f"Host: {ATOM_HOST}:{ATOM_PORT}\r\n"
            f"Content-Type: text/xml; charset=utf-8\r\n"
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
        print(f"  [OK] 响应长度 {len(resp)}")
        return text
    except Exception as e:
        print(f"  [ERROR] {e}")
        return None


def b_fscan():
    """B_FScan - 结构对齐 atom_streamsrc_listener.py"""
    body = '''<?xml version="1.0" encoding="UTF-8"?>
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
    body = f'''<?xml version="1.0" encoding="UTF-8"?>
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
    print(f"  [TCP] 连接 streamsrc {ATOM_HOST}:{STREAMSRC_PORT}...")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((ATOM_HOST, STREAMSRC_PORT))
        print(f"  [OK] 连接成功")
        return sock
    except Exception as e:
        print(f"  [ERROR] {e}")
        return None


def parse_atom_frame(data):
    """解析 Atom streamsrc 帧，对齐 atom_streamsrc_listener.py"""
    if len(data) < 4 or data[:4] != bytes.fromhex('eeeeeeee'):
        return None
    if len(data) >= 30:
        # TASKID 帧: offset 29 是可打印 ASCII
        if 32 <= data[29] <= 126:
            return {'type': 'TASKID', 'taskid': data[29:64].decode('ascii', errors='replace').strip('\x00')}
    if len(data) < 28:
        return None
    fscan_type = data[19]
    # STATUS 帧: 65 字节, offset 19 == 0
    if fscan_type == 0 and len(data) == 65:
        return {'type': 'STATUS', 'levels': struct.unpack(f'<{18}h', data[28:])}
    # FSCAN 帧: offset 19 == 0x26(529) 或 0x68(434)
    if fscan_type in (0x26, 0x68):
        frame_type = 'FSCAN-529' if fscan_type == 0x26 else 'FSCAN-434'
        payload = data[28:]
        if len(payload) % 2 != 0:
            payload = payload[:-1]
        num_levels = len(payload) // 2
        if num_levels > 0:
            levels = struct.unpack(f'<{num_levels}h', payload)
            return {'type': frame_type, 'level_count': num_levels, 'levels': list(levels)}
    return None


def receive_fscan_frames(sock, count=5, timeout=30):
    """接收 FSCAN-529 帧 - 对齐 atom_streamsrc_listener.py 的帧解析"""
    print(f"  [TCP] 等待接收 {count} 帧 (超时 {timeout}s)...")
    metadata_frames = []
    recv_buffer = b''

    start_time = time.time()
    while time.time() - start_time < timeout:
        try:
            chunk = sock.recv(65536)
            if not chunk:
                elapsed = time.time() - start_time
                print(f"  [WARN] 连接关闭 (收到 {len(metadata_frames)} 帧, 耗时 {elapsed:.1f}s)")
                break
        except socket.timeout:
            elapsed = time.time() - start_time
            print(f"  [WARN] 接收超时 (buffer={len(recv_buffer)}, 耗时 {elapsed:.1f}s)")
            break

        recv_buffer += chunk

        # 对齐 atom_streamsrc_listener.py 的帧解析逻辑
        while len(recv_buffer) >= 28:
            if recv_buffer[:4] != bytes.fromhex('eeeeeeee'):
                recv_buffer = recv_buffer[1:]
                continue

            if len(recv_buffer) >= 65 and recv_buffer[4] == 0x01:
                # 65 字节帧: TASKID / STATUS / FSCAN 分片
                frame_data = recv_buffer[:65]
                recv_buffer = recv_buffer[65:]
            elif len(recv_buffer) >= 1086:
                frame_data = recv_buffer[:1086]
                recv_buffer = recv_buffer[1086:]
            elif len(recv_buffer) >= 896:
                frame_data = recv_buffer[:896]
                recv_buffer = recv_buffer[896:]
            else:
                break

            result = parse_atom_frame(frame_data)
            if result is None:
                continue

            ftype = result.get('type', '')
            if ftype == 'FSCAN-529':
                levels = result['levels']
                metadata = levels[:17]
                spectrum = levels[17:]
                metadata_frames.append(metadata)
                elapsed = time.time() - start_time
                print(f"  [OK] FSCAN-529 #{len(metadata_frames)}: 前17={list(metadata)} ({elapsed:.1f}s)")
            elif ftype == 'TASKID':
                print(f"  [DBG] TASKID 帧: {result['taskid']}")
            elif ftype == 'STATUS':
                print(f"  [DBG] STATUS 帧: levels={list(result['levels'])}")
            elif ftype == 'FSCAN-434':
                print(f"  [DBG] FSCAN-434 帧")

    return metadata_frames


def main():
    print("=" * 60)
    print("分析 streamsrc FSCAN-529 帧的前17个元数据值")
    print("=" * 60)

    # Step 1: B_FScan
    print("\n[Step 1] B_FScan")
    resp = b_fscan()
    if not resp:
        print("[ERROR] B_FScan 失败")
        return

    # 解析 taskid
    taskid_match = re.search(r'<srrc:taskid>([^<]+)</srrc:taskid>', resp)
    if not taskid_match:
        print("[ERROR] 未找到 taskid")
        print(f"响应全文:\n{resp}")
        return

    taskid = taskid_match.group(1)
    print(f"  [OK] TaskID: {taskid}")
    time.sleep(1)

    # Step 3: 连接 streamsrc
    print("\n[Step 3] 连接 streamsrc")
    sock = connect_streamsrc(taskid)
    if not sock:
        return

    # Step 4: 接收 FSCAN-529 帧
    print("\n[Step 4] 接收 FSCAN-529 帧")
    try:
        metadata_frames = receive_fscan_frames(sock, count=5)
    finally:
        sock.close()
        # 必须发 B_StopMeas 避免 Atom 僵死
        print("\n[Step 5] B_StopMeas")
        b_stop_meas(taskid)

    # Step 5: 分析元数据
    print("\n" + "=" * 60)
    print("元数据值分析 (前17个值)")
    print("=" * 60)

    for i in range(17):
        vals = [m[i] for m in metadata_frames]
        unique = set(vals)
        stable = len(unique) == 1
        print(f"  Metadata[{i:2d}]: values={vals[:3]}... unique={len(unique)} {'STABLE' if stable else 'VARIES'}")


if __name__ == '__main__':
    main()
