#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GWJ004 完整频谱数据获取 - Task #6

正确顺序:
1. B_QueryDeviceInfo  (查询设备信息)
2. B_QueryFaciDevStat (查询设备状态)
3. [如果设备忙] B_StopMeas (停止现有任务)
4. B_FScan            (启动频段扫描)
5. 连接 streamsrc 接收数据
"""

import socket
import struct
import time
import re
import os
import sys
import requests
from datetime import datetime
from collections import defaultdict

# Atom 地址
ATOM_HOST = '127.0.0.1'
ATOM_PORT = 8282
STREAMSRC_PORT = 18012
ATOM_URL = f"http://{ATOM_HOST}:{ATOM_PORT}/"

# 通用请求头
HEADERS = {
    "Content-Type": "text/xml; charset=utf-8",
}

# 通用基础字段
BASE_FIELDS = """<srrc:appid>123456</srrc:appid>
<srrc:userid>RX_admin</srrc:userid>
<srrc:priority>9</srrc:priority>
<srrc:executetime>0</srrc:executetime>
<srrc:mfid>53090001140012</srrc:mfid>
<srrc:equid>51cd8dfe-e543-40c9-bdc3-a292766fee7f</srrc:equid>"""

OUTPUT_CHANNEL = """<srrc:outputchannel>
<srrc:mode>source</srrc:mode>
<srrc:datachannel>stream</srrc:datachannel>
</srrc:outputchannel>"""


def build_request(interface_name, equpara_xml=None):
    """构建 SOAP 请求"""
    if equpara_xml is None:
        equpara = '<srrc:equpara xsi:nil="true" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"/>'
    else:
        equpara = f'<srrc:equpara>{equpara_xml}</srrc:equpara>'

    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody>
{BASE_FIELDS}
{equpara}
{OUTPUT_CHANNEL}
</srrc:requestbody></soapenv:Body></soapenv:Envelope>"""
    return body


def send_soap(interface_name, body, retries=2):
    """发送 SOAP 请求，带重试"""
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f'"{interface_name}"'
    }
    for attempt in range(retries):
        try:
            # 禁用代理，直接连接，每次请求新建连接
            resp = requests.post(ATOM_URL, data=body.encode('utf-8'), headers=headers,
                               timeout=10, proxies={"http": None, "https": None})
            return resp
        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as e:
            if attempt < retries - 1:
                print(f"    [!] {interface_name} 连接失败，重试 ({attempt+1}/{retries})...")
                time.sleep(1)
            else:
                raise
    return None


def wait_callback(resp, operation_name, timeout=10):
    """等待 SOAP 请求回调完成"""
    if resp.status_code != 200:
        print(f"    [!] {operation_name} HTTP错误: {resp.status_code}")
        return False

    text = resp.content.decode('utf-8', errors='replace')

    # 检查业务错误码
    if 'BIZ-000001' in text or 'success' in text.lower():
        print(f"    [OK] {operation_name} 回调成功")
        return True
    elif 'BIZ-000002' in text or 'conflict' in text.lower():
        print(f"    [!] {operation_name} 回调: 冲突")
        return False
    else:
        # 检查是否有错误信息
        err_match = re.search(r'<srrc:errcode>([^<]+)</srrc:errcode>', text)
        if err_match:
            print(f"    [!] {operation_name} 错误码: {err_match.group(1)}")
            return False
        print(f"    [?] {operation_name} 响应未知: {text[:200]}")
        return True  # 继续尝试


def query_device_info():
    """查询设备信息"""
    print("\n[0] B_QueryDeviceInfo - 查询设备信息")
    body = build_request('B_QueryDeviceInfo', None)
    resp = send_soap('B_QueryDeviceInfo', body)
    print(f"    HTTP响应: {resp.status_code}, {len(resp.content)} bytes")

    if not wait_callback(resp, "B_QueryDeviceInfo"):
        return False
    return True


def query_device_status():
    """查询设备状态 (已废弃)"""
    return 'idle'


def stop_task(taskid):
    """停止指定任务"""
    print(f"\n[0c] B_StopMeas - 停止任务 {taskid}")
    body = f"""<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody>
<srrc:appid>123456</srrc:appid>
<srrc:userid>RX_admin</srrc:userid>
<srrc:mfid>53090001140012</srrc:mfid>
<srrc:equid>51cd8dfe-e543-40c9-bdc3-a292766fee7f</srrc:equid>
<srrc:equpara xsi:nil="true"/>
<srrc:taskid>{taskid}</srrc:taskid>
</srrc:requestbody></soapenv:Body></soapenv:Envelope>"""
    resp = send_soap('B_StopMeas', body)
    print(f"    HTTP响应: {resp.status_code}")

    if not wait_callback(resp, "B_StopMeas"):
        return False
    return True


def send_fscan_and_get_channel():
    """发送 B_FScan 并获取 outputchannel"""
    print("\n[1] B_FScan - 启动频段扫描")

    equpara = """<srrc:groupitems><srrc:groupitem><srrc:groupid>1</srrc:groupid>
<srrc:items><srrc:item><srrc:paraname>startfreq</srrc:paraname><srrc:paravalue>137000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>stopfreq</srrc:paraname><srrc:paravalue>173000000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>step</srrc:paraname><srrc:paravalue>25000</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>gain</srrc:paraname><srrc:paravalue>AGC</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>rfworkmode</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item>
<srrc:item><srrc:paraname>scanmode</srrc:paraname><srrc:paravalue>0</srrc:paravalue></srrc:item>
</srrc:items></srrc:groupitem></srrc:groupitems>"""

    body = build_request('B_FScan', equpara)
    resp = send_soap('B_FScan', body)

    if resp.status_code != 200:
        print(f"    [!] HTTP响应错误: {resp.status_code}")
        return None, None, None

    text = resp.content.decode('utf-8', errors='replace')
    print(f"    HTTP响应: {len(resp.content)} bytes")

    # 解析 outputchannel
    host_match = re.search(r'<srrc:host>([^<]+)</srrc:host>', text)
    port_match = re.search(r'<srrc:port>(\d+)</srrc:port>', text)
    stc_match = re.search(r'<srrc:stc>(\d+)</srrc:stc>', text)
    taskid_match = re.search(r'<srrc:taskid>([^<]+)</srrc:taskid>', text)

    if host_match and port_match:
        host = host_match.group(1)
        port = int(port_match.group(1))
        stc = int(stc_match.group(1)) if stc_match else 0
        taskid = taskid_match.group(1) if taskid_match else ""
        print(f"    [OK] outputchannel: {host}:{port}, stc={stc}, taskid={taskid}")
        return host, port, stc, taskid

    # 检查冲突
    if 'conflict' in text.lower():
        print("    [!] 设备使用冲突")
        # 提取冲突的 taskid
        conflict_taskid = re.search(r'<srrc:taskid>([^<]+)</srrc:taskid>', text)
        if conflict_taskid:
            print(f"    [!] 冲突任务ID: {conflict_taskid.group(1)}")
            return 'conflict', conflict_taskid.group(1), None, None

    print("    [!] 未找到 outputchannel")
    return None, None, None, None


def parse_atom_frame(data):
    """
    解析 Atom streamsrc 18012 端口数据帧

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

    # taskid 帧: offset 29 是可打印 ASCII
    if len(data) >= 30:
        offset29 = data[29]
        if 32 <= offset29 <= 126:
            taskid_bytes = data[29:64]
            taskid = taskid_bytes.decode('ascii', errors='replace').strip('\x00')
            return {'type': 'TASKID', 'length': len(data), 'taskid': taskid}

    if len(data) < 28:
        return None

    seq_num = struct.unpack('<H', data[16:18])[0]
    fscan_type = data[19]

    # 状态帧: offset 19 == 0, 65字节
    if fscan_type == 0 and len(data) == 65:
        payload = data[28:]
        if len(payload) % 2 != 0:
            payload = payload[:-1]
        num_levels = len(payload) // 2
        if num_levels > 0:
            levels = struct.unpack(f'<{num_levels}h', payload)
            return {
                'type': 'STATUS', 'length': len(data),
                'level_count': num_levels, 'levels': list(levels),
                'level_min': min(levels), 'level_max': max(levels),
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
                    'type': frame_type, 'length': len(data),
                    'level_count': num_levels, 'levels': list(levels),
                    'level_min': min(levels), 'level_max': max(levels),
                }
            except struct.error:
                return None

    return None


# streamsrc 值转换参数
SS_MIN = -32768  # streamsrc 无效值标记
SS_MAX = 24933   # 最大值
DBUV_MIN = 0.0
DBUV_MAX = 78.9


def streamsrc_to_dbm(val):
    """streamsrc 原始值转换为 dBm"""
    if val == SS_MIN:
        return None
    norm = (val - SS_MIN) / (SS_MAX - SS_MIN)
    dbuv = DBUV_MIN + norm * (DBUV_MAX - DBUV_MIN)
    dbm = dbuv - 107.6
    return round(dbm, 1)


def parse_gwij_frame(data):
    """解析 GWJ004 帧"""
    if len(data) < 32:
        return None

    leader = struct.unpack('<I', data[0:4])[0]
    if leader != 0xEEEEEEEE:
        return None

    ver = struct.unpack('<H', data[4:6])[0]
    stc = struct.unpack('<I', data[6:10])[0]

    ts_year = struct.unpack('<H', data[10:12])[0]
    ts_month = data[12]
    ts_day = data[13]
    ts_hour = data[14]
    ts_min = data[15]
    ts_sec = data[16]
    ts_ms = struct.unpack('<H', data[17:19])[0]
    ts = f"{ts_year}-{ts_month:02d}-{ts_day:02d} {ts_hour:02d}:{ts_min:02d}:{ts_sec:02d}.{ts_ms:03d}"

    pl = struct.unpack('<I', data[19:23])[0]
    el = data[23]

    if len(data) < 32 + pl:
        return None

    dt = data[32]
    dl = struct.unpack('<I', data[33:37])[0]
    payload = data[37:37+dl]

    return {
        'ts': ts, 'stc': stc, 'ver': ver, 'pl': pl, 'el': el,
        'dt': dt, 'dl': dl, 'payload': payload
    }


def parse_spectrum_data(payload):
    """解析频谱数据"""
    if len(payload) < 24:
        return None

    total_points = struct.unpack('<I', payload[0:4])[0]
    start_freq = struct.unpack('<d', payload[4:12])[0]
    step = struct.unpack('<f', payload[12:16])[0]
    seq_offset = struct.unpack('<I', payload[16:20])[0]
    seq_count = struct.unpack('<I', payload[20:24])[0]

    levels_data = payload[24:]
    levels = []
    for i in range(0, len(levels_data) - 1, 2):
        val = struct.unpack('<h', levels_data[i:i+2])[0]
        if val == 0xEFFF:
            levels.append(None)
        else:
            dbm = val / 10.0 - 107.6
            levels.append(dbm)

    return {
        'total_points': total_points, 'start_freq': start_freq,
        'step': step, 'seq_offset': seq_offset, 'seq_count': seq_count, 'levels': levels
    }


# 抓包确认的注册帧模板 (65字节) - 前29字节固定 + taskid 35字节
REG_FRAME_TEMPLATE = bytes.fromhex('eeeeeeee010000000000ea07040d1735065f002900000000c92400000044433642303336432d333735302d313146312d383030302d303044383631324637354238')


def connect_and_verify(taskid, verify_timeout=5):
    """
    连接 streamsrc 18012 端口，验证是否有数据回调
    返回: (success, frames_collected)
    - success=True 表示验证成功，收到了FSCAN数据
    - success=False 表示验证失败，没有收到FSCAN数据
    """
    print(f"\n[2a] 连接 streamsrc {ATOM_HOST}:{STREAMSRC_PORT} (验证模式: 等{verify_timeout}s)")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2.0)

    frames_collected = []
    fscan_received = False

    try:
        sock.connect((ATOM_HOST, STREAMSRC_PORT))
        print("[3a] streamsrc 连接成功!")

        # 发送注册帧
        if taskid:
            reg_frame = REG_FRAME_TEMPLATE[:29] + taskid.encode('ascii')
            print(f"[*] 注册帧 ({len(reg_frame)} bytes): taskid={taskid}")
            sock.send(reg_frame)
            print("[4a] 已发送注册帧")

        # 等待注册确认
        time.sleep(0.5)

        print(f"\n[5a] 等待数据回调 (验证超时 {verify_timeout}s)...")
        start_time = time.time()
        frame_count = 0
        recv_buffer = b''
        last_recv_time = start_time

        while time.time() - start_time < verify_timeout:
            try:
                chunk = sock.recv(8192)
                if not chunk:
                    elapsed = time.time() - start_time
                    print(f"[6a] 连接关闭 (收到 {frame_count} 帧, 耗时 {elapsed:.1f}s)")
                    break

                recv_buffer += chunk
                last_recv_time = time.time()
                elapsed = last_recv_time - start_time
                print(f"  [debug] 收到 {len(chunk)} 字节, buffer累计 {len(recv_buffer)} 字节")

                # 处理接收到的数据
                while len(recv_buffer) >= 4:
                    eeee_pos = recv_buffer.find(bytes.fromhex('eeeeeeee'))
                    if eeee_pos == -1:
                        print(f"  [debug] 没有找到0xEEEEEEEE, buffer剩余{len(recv_buffer)}字节")
                        break
                    if eeee_pos > 0:
                        print(f"  [debug] 跳过前{eeee_pos}字节")
                        recv_buffer = recv_buffer[eeee_pos:]
                    if len(recv_buffer) < 21:
                        print(f"  [debug] buffer不足21字节, 等待更多数据")
                        break

                    frame_type_byte = recv_buffer[19]
                    if frame_type_byte == 0:
                        frame_len = 65
                    elif frame_type_byte == 0x26:
                        frame_len = 1086
                    elif frame_type_byte == 0x68:
                        frame_len = 896
                    else:
                        print(f"  [debug] 未知帧类型0x{frame_type_byte:02x}, 跳过4字节")
                        recv_buffer = recv_buffer[4:]
                        continue

                    if len(recv_buffer) < frame_len:
                        print(f"  [debug] buffer不足{frame_len}字节, 需要{ frame_len - len(recv_buffer)}更多")
                        break

                    frame_data = recv_buffer[:frame_len]
                    recv_buffer = recv_buffer[frame_len:]

                    result = parse_atom_frame(frame_data)
                    if result:
                        frame_count += 1
                        elapsed = time.time() - start_time
                        if result['type'] == 'FSCAN-529':
                            print(f"  [{elapsed:.1f}s] 帧#{frame_count}: FSCAN-529 levels={result['level_count']}")
                            frames_collected.append(result)
                            fscan_received = True  # 收到FSCAN数据，验证成功
                        elif result['type'] == 'STATUS':
                            print(f"  [{elapsed:.1f}s] 帧#{frame_count}: STATUS levels={result['level_count']}")
                        elif result['type'] == 'TASKID':
                            print(f"  [{elapsed:.1f}s] 帧#{frame_count}: TASKID={result['taskid']}")

            except socket.timeout:
                continue
            except Exception as e:
                print(f"[!] 接收异常: {e}")
                break

    except Exception as e:
        print(f"[!] 连接失败: {e}")
    finally:
        sock.close()
        print(f"[7a] 连接已关闭 (验证结果: FSCAN收到={fscan_received})")

    return fscan_received, frames_collected


def connect_and_receive(stc, taskid, timeout=30):
    """连接 streamsrc 接收数据 (全量接收模式)"""
    print(f"\n[2b] 连接 streamsrc {ATOM_HOST}:{STREAMSRC_PORT} (接收模式: 等{timeout}s)")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2.0)

    frames_collected = []

    try:
        sock.connect((ATOM_HOST, STREAMSRC_PORT))
        print("[3b] streamsrc 连接成功!")

        # 发送注册帧
        if taskid:
            reg_frame = REG_FRAME_TEMPLATE[:29] + taskid.encode('ascii')
            print(f"[*] 注册帧 ({len(reg_frame)} bytes): taskid={taskid}")
            sock.send(reg_frame)
            print("[4b] 已发送注册帧")

        # 等待注册确认
        time.sleep(0.5)

        print(f"\n[5b] 等待数据回调 (超时 {timeout} 秒)...")
        start_time = time.time()
        frame_count = 0
        recv_buffer = b''

        while time.time() - start_time < timeout:
            try:
                chunk = sock.recv(8192)
                if not chunk:
                    elapsed = time.time() - start_time
                    print(f"[6b] 连接关闭 (收到 {frame_count} 帧, 耗时 {elapsed:.1f}s)")
                    break

                recv_buffer += chunk

                while len(recv_buffer) >= 4:
                    eeee_pos = recv_buffer.find(bytes.fromhex('eeeeeeee'))
                    if eeee_pos == -1:
                        break
                    if eeee_pos > 0:
                        recv_buffer = recv_buffer[eeee_pos:]
                    if len(recv_buffer) < 21:
                        break

                    frame_type_byte = recv_buffer[19]
                    if frame_type_byte == 0:
                        frame_len = 65
                    elif frame_type_byte == 0x26:
                        frame_len = 1086
                    elif frame_type_byte == 0x68:
                        frame_len = 896
                    else:
                        recv_buffer = recv_buffer[4:]
                        continue

                    if len(recv_buffer) < frame_len:
                        break

                    frame_data = recv_buffer[:frame_len]
                    recv_buffer = recv_buffer[frame_len:]

                    result = parse_atom_frame(frame_data)
                    if result:
                        frame_count += 1
                        elapsed = time.time() - start_time
                        if result['type'] == 'FSCAN-529':
                            print(f"  [{elapsed:.1f}s] 帧#{frame_count}: FSCAN-529 "
                                  f"levels={result['level_count']} range=[{result['level_min']}, {result['level_max']}]")
                            frames_collected.append(result)
                        elif result['type'] == 'STATUS':
                            print(f"  [{elapsed:.1f}s] 帧#{frame_count}: STATUS levels={result['level_count']}")
                        elif result['type'] == 'TASKID':
                            print(f"  [{elapsed:.1f}s] 帧#{frame_count}: TASKID={result['taskid']}")

            except socket.timeout:
                continue
            except Exception as e:
                print(f"[!] 接收异常: {e}")
                break

    except Exception as e:
        print(f"[!] 连接失败: {e}")
    finally:
        sock.close()
        print("[7b] 连接已关闭")

    return frames_collected


def reassemble_spectra(spectra):
    """将分片频谱重组为完整频谱"""
    by_time = defaultdict(list)
    for ts, spec in spectra:
        by_time[ts].append(spec)

    results = []
    for ts, specs in sorted(by_time.items()):
        specs.sort(key=lambda x: x['seq_offset'])
        full_levels = []
        for spec in specs:
            full_levels.extend(spec['levels'])
        if full_levels:
            results.append((ts, full_levels))
    return results


def main():
    print("=" * 60)
    print("GWJ004 完整频谱数据获取 - Task #6")
    print("=" * 60)

    # Step 0: B_QueryDeviceInfo - 必须先完成
    print("\n>>> 步骤0: B_QueryDeviceInfo")
    if not query_device_info():
        print("[!] B_QueryDeviceInfo 失败，退出")
        return 1
    time.sleep(1)  # 等待回调处理完成

    # Step 1: B_FScan + 验证18012数据回调
    print("\n>>> 步骤1: B_FScan + 验证数据回调")

    verify_retry_count = 0
    max_verify_retries = 3

    while verify_retry_count < max_verify_retries:
        result = send_fscan_and_get_channel()

        if result[0] is None:
            print("[!] B_FScan 失败，退出")
            return 1

        if isinstance(result[0], str) and result[0] == 'conflict':
            # 设备冲突，先停止再重试
            conflict_taskid = result[1]
            print(f"\n[!] 设备冲突，停止任务 {conflict_taskid}...")
            if stop_task(conflict_taskid):
                print("[OK] 停止成功，等待2秒后重试...")
                time.sleep(2)
                verify_retry_count += 1
                continue
            else:
                print("[!] 停止失败，等待5秒后重试...")
                time.sleep(5)
                verify_retry_count += 1
                continue

        host, port, stc, taskid = result
        print(f"    [INFO] stc={stc}, taskid={taskid}")

        # 连接18012端口验证是否有数据回调（等5秒）
        print("\n    [验证] 连接18012验证数据回调...")
        fscan_ok, verify_frames = connect_and_verify(taskid, verify_timeout=5)

        if fscan_ok:
            print("[OK] 验证成功，收到FSCAN数据回调！")
            # 继续全量接收
            print("\n    [接收] 开始全量接收数据...")
            frames = connect_and_receive(stc, taskid, timeout=30)

            if frames:
                print(f"\n[OK] 共收到 {len(frames)} 帧数据")
                break
            else:
                print("\n[!] 全量接收超时，未收到数据")
                verify_retry_count += 1
                continue
        else:
            # 验证失败，没有收到FSCAN数据
            print("[!] 验证失败，未收到FSCAN数据")
            print(f"    重试 ({verify_retry_count + 1}/{max_verify_retries})")

            # 停止当前任务
            print(f"    [停止] 停止任务 {taskid}...")
            stop_task(taskid)
            time.sleep(2)
            verify_retry_count += 1

    if verify_retry_count >= max_verify_retries:
        print("\n[!] 验证重试次数用完，无法获取有效数据，退出")
        return 1

    # 收集所有 FSCAN-529 帧
    fscan_frames = [f for f in frames if f['type'] == 'FSCAN-529']
    print(f"\n[8] 共收到 {len(frames)} 帧, 其中 FSCAN-529: {len(fscan_frames)} 帧")

    if not fscan_frames:
        print("[!] 未收到 FSCAN-529 数据")
        return 1

    # Step 4: 保存数据
    base_dir = os.path.dirname(os.path.abspath(__file__))
    log_dir = os.path.join(base_dir, 'logs')
    os.makedirs(log_dir, exist_ok=True)

    ts_str = datetime.now().strftime('%Y%m%d_%H%M%S')
    log_path = os.path.join(log_dir, f'gwij_full_{ts_str}.log')

    with open(log_path, 'w', encoding='utf-8') as f:
        f.write(f"streamsrc Spectrum Log - {ts_str}\n")
        f.write(f"Host: {ATOM_HOST}:{STREAMSRC_PORT}, STC: {stc}, TaskID: {taskid}\n")
        f.write(f"Total frames: {len(frames)}, FSCAN-529 frames: {len(fscan_frames)}\n")
        f.write("=" * 60 + "\n\n")
        for i, frame in enumerate(fscan_frames[:5]):  # 只保存前5帧
            levels = frame['levels']
            # 转换为 dBm
            dbm_levels = [streamsrc_to_dbm(v) for v in levels]
            valid_levels = [v for v in dbm_levels if v is not None]
            if valid_levels:
                f.write(f"Frame {i+1}: {len(levels)} levels\n")
                f.write(f"  raw range: [{frame['level_min']}, {frame['level_max']}]\n")
                f.write(f"  dBm range: [{min(valid_levels):.1f}, {max(valid_levels):.1f}]\n")
                f.write(f"  dBm: [{', '.join(f'{v:.1f}' for v in dbm_levels[:20] if v is not None)}...]\n\n")

    print(f"\n[9] 数据已保存: {log_path}")

    # Step 5: 可视化
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt

        if fscan_frames:
            fig, ax = plt.subplots(figsize=(16, 6))
            # 使用第一帧数据
            levels = fscan_frames[0]['levels']
            dbm_levels = [streamsrc_to_dbm(v) for v in levels]
            ax.plot(dbm_levels, 'b-', linewidth=0.5)
            ax.set_title(f'streamsrc Spectrum ({len(levels)} points)', fontsize=12)
            ax.set_xlabel('Frequency Index')
            ax.set_ylabel('dBm')
            ax.grid(True, alpha=0.3)
            ax.set_ylim(-80, -20)

            img_path = os.path.join(base_dir, f'gwij_spectrum_{ts_str}.png')
            plt.savefig(img_path, dpi=150)
            print(f"[10] 频谱图已保存: {img_path}")
    except ImportError:
        pass

    print("\n" + "=" * 60)
    print("完成!")
    print("=" * 60)
    return 0


if __name__ == '__main__':
    sys.exit(main())
