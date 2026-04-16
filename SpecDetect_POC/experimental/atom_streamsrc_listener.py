#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Atom streamsrc 监听器
连接 Atom 18012 端口，接收并解析 streaming 数据帧

基于抓包分析 (loopback.pcap) 实现
"""

import socket
import struct
import time
import re
import os
from datetime import datetime
import sys

# 设置输出为 UTF-8
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

ATOM_HOST = '127.0.0.1'
ATOM_PORT = 8282
STREAMSRC_PORT = 18012

# 日志目录
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')

# 抓包确认的注册帧模板 (65字节)
REG_FRAME_TEMPLATE = bytes.fromhex('eeeeeeee010000000000ea07040d1735065f002900000000c92400000044433642303336432d333735302d313146312d383030302d303044383631324637354238')


def ensure_log_dir():
    """确保日志目录存在"""
    if not os.path.exists(LOG_DIR):
        os.makedirs(LOG_DIR)
    return LOG_DIR


# streamsrc 值转换参数
# streamsrc 数据单位是 dBuV，需要转换为 dBm
# 换算关系: dBuV = dBm + 107.6  =>  dBm = dBuV - 107.6
SS_MIN = -32768  # streamsrc 无效值标记
SS_MAX = 24933   # streamsrc 最大值 (对应约 78.9 dBuV)

# dBuV 范围 (由 rmcp dBm 范围推导: dBm + 107.6)
# rmcp dBm 范围约 [-107.6, -30.9]，对应 dBuV 范围 [0, 76.7]
DBUV_MIN = 0.0   # dBuV 最小值 (对应 rmcp 噪声底 -107.6 dBm)
DBUV_MAX = 78.9  # dBuV 最大值 (对应 rmcp 最大值约 -30.9 dBm)


def streamsrc_to_dbm(value):
    """
    将 streamsrc 原始值转换为 dBm

    streamsrc 数据来自 Atom 的 18012 端口 streaming 输出
    数据单位是 dBuV，转换为 dBm 需要减去 107.6

    转换公式:
    1. 归一化: norm = (value - SS_MIN) / (SS_MAX - SS_MIN)
    2. dBuV = DBUV_MIN + norm * (DBUV_MAX - DBUV_MIN)
    3. dBm = dBuV - 107.6

    Args:
        value: streamsrc 原始值 (signed short, dBuV)

    Returns:
        转换后的 dBm 值 (float)，如果是无效值则返回 None
    """
    if value == SS_MIN:
        return None  # 无效值

    # 归一化到 [0, 1]
    norm = (value - SS_MIN) / (SS_MAX - SS_MIN)
    norm = max(0, min(1, norm))  # 限制在 [0, 1]

    # 映射到 dBuV 范围
    dbuv = DBUV_MIN + norm * (DBUV_MAX - DBUV_MIN)

    # dBuV 转 dBm: dBm = dBuV - 107.6
    dbm = dbuv - 107.6
    return round(dbm, 1)


def send_fscan_soap_request():
    """发送 B_FScan SOAP 请求，获取 streamsrc 连接信息"""
    print("=" * 60)
    print("Step 1: 发送 B_FScan SOAP 请求")
    print("=" * 60)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(15)

    try:
        sock.connect((ATOM_HOST, ATOM_PORT))
        print(f"[+] 已连接到 Atom {ATOM_HOST}:{ATOM_PORT}")

        soap_request = b'''POST /B_FScan HTTP/1.1\r
Host: 127.0.0.1:8282\r
Content-Type: text/xml; charset=utf-8\r
SOAPAction: B_FScan\r
Content-Length: 1047\r
\r
<?xml version="1.0" encoding="UTF-8"?>
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

        sock.send(soap_request)
        print("[+] SOAP 请求已发送")

        response = b''
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
                if b'</soapenv:Envelope>' in response:
                    break
            except socket.timeout:
                break

        print(f"[+] 收到响应: {len(response)} bytes")

        # 解析 outputchannel
        host_match = re.search(r'<srrc:host>([^<]+)</srrc:host>', response.decode('utf-8', errors='replace'))
        port_match = re.search(r'<srrc:port>(\d+)</srrc:port>', response.decode('utf-8', errors='replace'))
        taskid_match = re.search(r'<srrc:taskid>([^<]+)</srrc:taskid>', response.decode('utf-8', errors='replace'))

        if host_match and port_match:
            host = host_match.group(1)
            port = int(port_match.group(1))
            taskid = taskid_match.group(1) if taskid_match else None
            print(f"[+] outputchannel: {host}:{port}")
            if taskid:
                print(f"[+] taskid: {taskid}")
            return host, port, taskid

        print("[-] 未找到 outputchannel")
        return None, None, None

    except Exception as e:
        print(f"[-] SOAP 请求失败: {e}")
        return None, None, None
    finally:
        sock.close()


def parse_atom_frame(data):
    """
    解析 Atom 18012 端口数据帧

    帧格式:
    Offset 0:   0xEEEEEEEE (4字节) - 帧开始标记
    Offset 4-27: 24字节头
    Offset 28+: 电平数据 (N×2字节) - signed short little-endian

    帧类型判断:
    - offset 29 是可打印 ASCII (0x20-0x7E) -> taskid 帧
    - offset 20 == 0, 65字节 -> 状态帧 (18电平)
    - offset 20 == 3, 896字节 -> FSCAN-434 帧 (434电平)
    - offset 20 == 4, 1086字节 -> FSCAN-529 帧 (529电平)
    """
    if len(data) < 4:
        return None

    if data[:4] != bytes.fromhex('eeeeeeee'):
        return None

    # 判断帧类型
    # 1. taskid 帧: offset 29 是可打印 ASCII
    if len(data) >= 30:
        offset29 = data[29]
        if 32 <= offset29 <= 126:  # 可打印 ASCII
            taskid_bytes = data[29:64]
            taskid = taskid_bytes.decode('ascii', errors='replace').strip('\x00')
            return {
                'type': 'TASKID',
                'length': len(data),
                'taskid': taskid,
            }

    # 2. 帧头验证
    if data[:4] != bytes.fromhex('eeeeeeee'):
        return None

    if len(data) < 28:
        return None

    # 3. offset 16-17: 帧编号 (uint16, little-endian)
    # 4. offset 18: 帧计数器 (递增)
    # 5. offset 19: FSCAN 类型 (0x00=STATUS, 0x26=FSCAN-529, 0x68=FSCAN-434)
    seq_num = struct.unpack('<H', data[16:18])[0]
    fscan_type = data[19]  # byte at offset 19

    # 状态帧: offset 19 == 0, 65字节
    if fscan_type == 0 and len(data) == 65:
        payload = data[28:]
        if len(payload) % 2 != 0:
            payload = payload[:-1]
        num_levels = len(payload) // 2
        if num_levels > 0:
            levels = struct.unpack(f'<{num_levels}h', payload)
            return {
                'type': 'STATUS',
                'length': len(data),
                'level_count': num_levels,
                'levels': levels,
                'level_min': min(levels),
                'level_max': max(levels),
            }

    # FSCAN 帧: offset 19 == 0x26 (529) 或 0x68 (434)
    if fscan_type in (0x26, 0x68):
        frame_type = 'FSCAN-434' if fscan_type == 0x68 else 'FSCAN-529'
        payload = data[28:]
        if len(payload) % 2 != 0:
            payload = payload[:-1]
        num_levels = len(payload) // 2
        if num_levels > 0:
            try:
                levels = struct.unpack(f'<{num_levels}h', payload)
                return {
                    'type': frame_type,
                    'length': len(data),
                    'level_count': num_levels,
                    'levels': levels,
                    'level_min': min(levels),
                    'level_max': max(levels),
                }
            except struct.error:
                return None

    return None


def connect_and_receive(host, port, taskid=None, timeout=30):
    """连接 streamsrc 并接收数据"""
    print("\n" + "=" * 60)
    print(f"Step 2: 连接 streamsrc {host}:{port}")
    print("=" * 60)

    # 创建日志文件
    log_dir = ensure_log_dir()
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_file = os.path.join(log_dir, f'spectrum_{timestamp}.log')
    log_fp = open(log_file, 'w', encoding='utf-8')
    log_fp.write(f"Atom streamsrc 频谱日志 - {timestamp}\n")
    log_fp.write(f"Host: {host}:{port}, TaskID: {taskid}\n")
    log_fp.write("=" * 60 + "\n\n")

    # 创建原始帧日志文件
    raw_log_file = os.path.join(log_dir, f'streamsrc_raw_{timestamp}.log')
    raw_log_fp = open(raw_log_file, 'wb')

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2.0)

    # FSCAN 分片缓冲
    TARGET_LEVELS = {'FSCAN-434': 434, 'FSCAN-529': 529}
    buffer_434 = []
    buffer_529 = []
    spectrum_output_count = 0

    def output_spectrum(frame_type, levels, elapsed):
        """输出完整频谱"""
        nonlocal spectrum_output_count
        spectrum_output_count += 1

        # 获取当前时间戳
        timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]

        # 计算原始值范围
        valid_levels = [v for v in levels if v != SS_MIN]
        if valid_levels:
            raw_min, raw_max = min(valid_levels), max(valid_levels)
            # 计算 dBm 范围
            dbm_values = [streamsrc_to_dbm(v) for v in valid_levels]
            dbm_min = min(v for v in dbm_values if v is not None)
            dbm_max = max(v for v in dbm_values if v is not None)

            msg = f"[{timestamp}] 频谱 #{spectrum_output_count}: {frame_type} levels={len(levels)}"
            print(msg)
            log_fp.write(msg + "\n")

            # 前17个元数据值
            meta = levels[:17]
            print(f"  [元数据] 前17个值 = {list(meta)}")
            log_fp.write(f"  [元数据] 前17个值 = {list(meta)}\n")

            # 原始值范围
            range_msg = f"  原始值范围: [{raw_min}, {raw_max}]"
            print(range_msg)
            log_fp.write(range_msg + "\n")

            # dBm 范围
            dbm_range_msg = f"  dBm范围: [{dbm_min:.1f}, {dbm_max:.1f}]"
            print(dbm_range_msg)
            log_fp.write(dbm_range_msg + "\n")

            # 前100个电平样本 (原始值和 dBm)
            sample = levels[:100]
            sample_parts = []
            dbm_parts = []
            for v in sample:
                sample_parts.append(str(v))
                dbm = streamsrc_to_dbm(v)
                dbm_parts.append(f"{dbm:.1f}" if dbm is not None else "N/A")

            # 输出原始值
            log_fp.write(f"  原始值(前100): [{', '.join(sample_parts)}]\n")
            # 输出 dBm 值
            log_fp.write(f"  dBm(前100): [{', '.join(dbm_parts)}]\n")
            print(f"  dBm(前100): [{', '.join(dbm_parts)}]")
        else:
            msg = f"[{timestamp}] 频谱 #{spectrum_output_count}: {frame_type} levels={len(levels)} (全部无效)"
            print(msg)
            log_fp.write(msg + "\n")

        log_fp.flush()

    try:
        sock.connect((host, port))
        print(f"[+] streamsrc 连接成功!")

        # 发送注册帧
        if taskid:
            print(f"[*] 发送注册帧 (taskid={taskid})...")
            reg_frame = REG_FRAME_TEMPLATE[:29] + taskid.encode('ascii')
            print(f"[*] 注册帧 ({len(reg_frame)} bytes)")
            sock.send(reg_frame)
            print(f"[+] 注册帧已发送")

        print(f"\n[+] 等待数据回调 (超时 {timeout} 秒)...")
        print("-" * 60)

        start_time = time.time()
        frame_count = 0
        recv_buffer = b''
        size_tracker = {}  # 记录所有收到的帧大小

        while time.time() - start_time < timeout:
            try:
                chunk = sock.recv(65536)
                if not chunk:
                    elapsed = time.time() - start_time
                    print(f"\n[!] 连接关闭 (收到 {frame_count} 帧, 耗时 {elapsed:.1f}s)")
                    break

                recv_buffer += chunk

                # 解析所有完整帧
                while len(recv_buffer) >= 28:
                    if recv_buffer[:4] != bytes.fromhex('eeeeeeee'):
                        recv_buffer = recv_buffer[1:]
                        continue

                    if len(recv_buffer) >= 65 and recv_buffer[4] == 0x01:
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

                    frame_count += 1
                    result = parse_atom_frame(frame_data)
                    # 追踪所有帧大小
                    sz = len(frame_data)
                    size_tracker[sz] = size_tracker.get(sz, 0) + 1

                    # 写入原始帧数据到日志
                    try:
                        ts = datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f')[:-3]
                        raw_log_fp.write(f"={ts}=\n".encode('utf-8'))
                        raw_log_fp.write(f"src={host}:{port}\n".encode('utf-8'))
                        raw_log_fp.write(f"size={len(frame_data)} bytes\n".encode('utf-8'))
                        raw_log_fp.write(f"frame_hex={frame_data.hex()}\n".encode('utf-8'))
                        raw_log_fp.write(b"\n")
                        raw_log_fp.flush()
                    except:
                        pass

                    elapsed = time.time() - start_time
                    if result and result['type'] == 'TASKID':
                        print(f"[{elapsed:.1f}s] 帧 #{frame_count}: TASKID = {result['taskid']}")
                    elif result and result['type'] == 'STATUS':
                        print(f"[{elapsed:.1f}s] 帧 #{frame_count}: STATUS levels={result['level_count']} range=[{result['level_min']}, {result['level_max']}]")
                    elif result and result['type'] == 'FSCAN-434':
                        # 收集 FSCAN-434 分片
                        buffer_434.extend(result['levels'])
                        # 检查是否足够
                        while len(buffer_434) >= TARGET_LEVELS['FSCAN-434']:
                            spectrum = buffer_434[:TARGET_LEVELS['FSCAN-434']]
                            buffer_434 = buffer_434[TARGET_LEVELS['FSCAN-434']:]
                            output_spectrum('FSCAN-434', spectrum, elapsed)
                    elif result and result['type'] == 'FSCAN-529':
                        # 收集 FSCAN-529 分片
                        buffer_529.extend(result['levels'])
                        # 检查是否足够
                        while len(buffer_529) >= TARGET_LEVELS['FSCAN-529']:
                            spectrum = buffer_529[:TARGET_LEVELS['FSCAN-529']]
                            buffer_529 = buffer_529[TARGET_LEVELS['FSCAN-529']:]
                            output_spectrum('FSCAN-529', spectrum, elapsed)
                    elif result and result['type'] in ('STATUS', 'SPECTRUM'):
                        msg = f"[{elapsed:.1}s] 帧 #{frame_count}: {result['type']} levels={result['level_count']} range=[{result['level_min']}, {result['level_max']}]"
                        print(msg)
                        log_fp.write(msg + "\n")
                    else:
                        if frame_count <= 5 or result is None:
                            ftype19 = frame_data[19] if len(frame_data) > 19 else -1
                            ftype20 = frame_data[20] if len(frame_data) > 20 else -1
                            print(f"[{elapsed:.1f}s] 帧 #{frame_count}: {result['type'] if result else 'None'} "
                                  f"len={len(frame_data)} type19=0x{ftype19:02x} type20=0x{ftype20:02x}")

            except socket.timeout:
                continue
            except Exception as e:
                print(f"\n[!] 接收异常: {e}")
                break

        # 输出剩余缓冲数据
        elapsed = time.time() - start_time
        if buffer_434:
            print(f"[{elapsed:.1f}s] 剩余 FSCAN-434: {len(buffer_434)} 电平")
        if buffer_529:
            print(f"[{elapsed:.1f}s] 剩余 FSCAN-529: {len(buffer_529)} 电平")

        print(f"\n[+] 总计: {frame_count} 原始帧, {spectrum_output_count} 完整频谱")
        print(f"[+] 帧大小分布: {dict(sorted(size_tracker.items()))}")
        log_fp.write(f"\n总计: {frame_count} 原始帧, {spectrum_output_count} 完整频谱\n")
        log_fp.write(f"帧大小分布: {dict(sorted(size_tracker.items()))}\n")
        log_fp.write(f"日志结束: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log_fp.close()
        raw_log_fp.close()
        print(f"[+] 原始帧日志: {raw_log_file}")
        return frame_count, spectrum_output_count

    except Exception as e:
        print(f"[-] streamsrc 连接失败: {e}")
        log_fp.close()
        raw_log_fp.close()
        return 0, 0
    finally:
        sock.close()
        print("[+] 连接已关闭")


def send_bstopmeas_request(taskid=None):
    """发送 B_StopMeas SOAP 请求，停止当前测量任务"""
    print("\n" + "=" * 60)
    print("Step 3: 发送 B_StopMeas 请求")
    print("=" * 60)

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(15)

    try:
        sock.connect((ATOM_HOST, ATOM_PORT))
        print(f"[+] 已连接到 Atom {ATOM_HOST}:{ATOM_PORT}")

        # B_StopMeas SOAP 请求
        # taskid 必需，用于指定停止特定任务
        if taskid:
            taskid_xml = f"<srrc:taskid>{taskid}</srrc:taskid>"
        else:
            taskid_xml = ""

        soap_body = f'''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody>
<srrc:appid>123456</srrc:appid>
<srrc:userid>RX_admin</srrc:userid>
<srrc:priority>9</srrc:priority>
<srrc:executetime>0</srrc:executetime>
<srrc:mfid>53090001140012</srrc:mfid>
<srrc:equid>51cd8dfe-e543-40c9-bdc3-a292766fee7f</srrc:equid>
{taskid_xml}
<srrc:outputchannel><srrc:mode>source</srrc:mode><srrc:datachannel>stream</srrc:datachannel></srrc:outputchannel>
</srrc:requestbody></soapenv:Body></soapenv:Envelope>'''

        soap_request = f'''POST /B_StopMeas HTTP/1.1\r
Host: 127.0.0.1:8282\r
Content-Type: text/xml; charset=utf-8\r
SOAPAction: B_StopMeas\r
Content-Length: {len(soap_body)}\r
\r
{soap_body}'''.encode('utf-8')

        sock.send(soap_request)
        print("[+] B_StopMeas 请求已发送")

        response = b''
        while True:
            try:
                chunk = sock.recv(4096)
                if not chunk:
                    break
                response += chunk
                if b'</soapenv:Envelope>' in response:
                    break
            except socket.timeout:
                break

        print(f"[+] 收到响应: {len(response)} bytes")
        return True

    except Exception as e:
        print(f"[-] B_StopMeas 请求失败: {e}")
        return False
    finally:
        sock.close()


def main():
    print("=" * 60)
    print("Atom streamsrc 监听器")
    print("基于 loopback.pcap 抓包分析实现")
    print("=" * 60)

    max_retries = 3
    retry_count = 0
    data_received = False
    total_spectrum_count = 0

    while retry_count < max_retries:
        # Step 1: 发送 SOAP 请求
        host, port, taskid = send_fscan_soap_request()

        if not host:
            print("\n[-] 获取 streamsrc 信息失败，退出")
            return 1

        # Step 2: 连接 streamsrc 并接收数据
        # 接收 30 秒后自动停止 (足够收集多个完整频谱)
        result = connect_and_receive(host, port, taskid, timeout=90)
        frame_count, spectrum_count = result if isinstance(result, tuple) else (result, 0)

        if frame_count > 0:
            data_received = True
            total_spectrum_count += spectrum_count
            print(f"\n[+] 收到 {frame_count} 原始帧, {spectrum_count} 完整频谱，数据充足，停止测量")
            break
        else:
            retry_count += 1
            print(f"\n[!] 未收到数据 (尝试 {retry_count}/{max_retries})")
            if retry_count < max_retries:
                print("[*] 发送 B_StopMeas 后重试...")
                send_bstopmeas_request(taskid)
                time.sleep(1)

    # Step 3: 发送 B_StopMeas 停止测量
    send_bstopmeas_request(taskid)

    print("\n" + "=" * 60)
    if data_received:
        print(f"[+] 测试成功: 收到 {total_spectrum_count} 完整频谱")
        return 0
    else:
        print(f"[-] 测试失败: 未收到数据")
        return 1


if __name__ == '__main__':
    import sys
    sys.exit(main())
