#!/usr/bin/env python3
"""
分析 streamsrc FSCAN-529 帧的前17个元数据值
"""
import socket
import struct
import time
import requests
import re
import subprocess

ATOM_HOST = '127.0.0.1'
ATOM_PORT = 8282
STREAMSRC_PORT = 18012
HEADERS = {'Content-Type': 'text/xml; charset=utf-8'}

REG_FRAME_TEMPLATE = bytes.fromhex('eeeeeeee010000000000ea07040d1735065f002900000000c92400000044433642303336432d333735302d313146312d383030302d303044383631324637354238')


def send_soap(interface_name, url, body):
    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": f'"{interface_name}"'
    }
    for attempt in range(2):
        try:
            resp = requests.post(url, data=body.encode('utf-8'), headers=headers,
                               timeout=10, proxies={"http": None, "https": None})
            return resp
        except (requests.exceptions.ConnectionError, requests.exceptions.ReadTimeout) as e:
            if attempt < 1:
                print(f"    [!] {interface_name} 连接失败，重试...")
                time.sleep(1)
    raise


OUTPUT_CHANNEL = """<srrc:outputchannel>
<srrc:mode>source</srrc:mode>
<srrc:datachannel>stream</srrc:datachannel>
</srrc:outputchannel>"""

BASE_FIELDS = """<srrc:appid>123456</srrc:appid>
<srrc:userid>RX_admin</srrc:userid>
<srrc:priority>9</srrc:priority>
<srrc:executetime>0</srrc:executetime>
<srrc:mfid>53090001140012</srrc:mfid>
<srrc:equid>51cd8dfe-e543-40c9-bdc3-a292766fee7f</srrc:equid>"""


def get_device_info():
    """获取设备信息"""
    body = f'''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody>
{BASE_FIELDS}
<srrc:equpara><srrc:paraname>DeviceInfo</srrc:paraname></srrc:equpara>
{OUTPUT_CHANNEL}
</srrc:requestbody></soapenv:Body></soapenv:Envelope>'''
    resp = send_soap('B_QueryDeviceInfo', f'http://{ATOM_HOST}:{ATOM_PORT}/', body)
    return resp


def send_fscan():
    """发送B_FScan"""
    body = f'''<?xml version="1.0" encoding="UTF-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/" xmlns:srrc="http://www.srrc.org.cn">
<soapenv:Body><srrc:requestbody>
{BASE_FIELDS}
<srrc:equpara>
<item name="startfreq"><srrc:paraname>137000000</srrc:paraname></item>
<item name="stopfreq"><srrc:paraname>173000000</srrc:paraname></item>
<item name="step"><srrc:paraname>25000</srrc:paraname></item>
<item name="gain"><srrc:paraname>AGC</srrc:paraname></item>
<item name="rfworkmode"><srrc:paraname>0</srrc:paraname></item>
<item name="scanmode"><srrc:paraname>0</srrc:paraname></item>
</srrc:equpara>
{OUTPUT_CHANNEL}
</srrc:requestbody></soapenv:Body></soapenv:Envelope>'''
    resp = send_soap('B_FScan', f'http://{ATOM_HOST}:{ATOM_PORT}/', body)
    return resp


def check_services():
    """检查 AtomSvcV3 和 rmcp_proxy 是否运行"""
    print("\n[0] 检查服务状态...")

    # 检查 AtomSvcV3
    atom_running = False
    try:
        result = subprocess.run(['tasklist'], capture_output=True, text=True)
        for line in result.stdout.split('\n'):
            if 'AtomSvcV3' in line:
                atom_running = True
                print(f"    [OK] AtomSvcV3 运行中")
                break
    except Exception as e:
        print(f"    [!] 检查 AtomSvcV3 失败: {e}")

    if not atom_running:
        print(f"    [!] AtomSvcV3 未运行")
        return False

    # 检查 rmcp_proxy (python进程)
    rmcp_running = False
    try:
        result = subprocess.run(['tasklist'], capture_output=True, text=True)
        python_count = 0
        for line in result.stdout.split('\n'):
            if 'python' in line.lower():
                python_count += 1
        if python_count >= 2:  # 至少2个python进程（rmcp_proxy + 可能的其他）
            rmcp_running = True
            print(f"    [OK] rmcp_proxy 运行中 (python进程数: {python_count})")
        else:
            print(f"    [!] rmcp_proxy 可能未运行 (python进程数: {python_count})")
    except Exception as e:
        print(f"    [!] 检查 rmcp_proxy 失败: {e}")

    return atom_running


def main():
    print("=" * 60)
    print("分析 streamsrc FSCAN-529 帧的前17个元数据值")
    print("=" * 60)

    # Step 0: 检查服务状态
    if not check_services():
        print("\n[!] 服务未就绪，请先启动 AtomSvcV3 和 rmcp_proxy")
        return

    # Step 1: B_QueryDeviceInfo
    print("\n[1] B_QueryDeviceInfo...")
    resp = get_device_info()
    print(f"    Response: {resp.status_code}")
    time.sleep(1)

    # Step 2: B_FScan
    print("\n[2] B_FScan...")
    resp = send_fscan()
    print(f"    Response: {resp.status_code}")

    # 解析 taskid
    taskid_match = re.search(r'<srrc:taskid>([^<]+)</srrc:taskid>', resp.text)
    taskid = taskid_match.group(1) if taskid_match else None
    if not taskid:
        print("    [!] 未找到 taskid")
        return
    print(f"    TaskID: {taskid}")
    time.sleep(1)

    # Step 3: 连接 streamsrc
    print("\n[3] 连接 streamsrc 18012...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.connect((ATOM_HOST, STREAMSRC_PORT))
    print("    连接成功")

    # 发送注册帧
    reg_frame = REG_FRAME_TEMPLATE[:29] + taskid.encode('ascii')
    sock.send(reg_frame)
    print(f"    注册帧已发送: {len(reg_frame)} bytes")

    # 等待并接收数据
    print("\n[4] 等待 FSCAN-529 帧...")
    metadata_frames = []
    frame_count = 0
    recv_buffer = b''

    while frame_count < 5:
        chunk = sock.recv(8192)
        if not chunk:
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
            if frame_type_byte == 0x26:
                frame_len = 1086
            else:
                recv_buffer = recv_buffer[4:]
                continue

            if len(recv_buffer) < frame_len:
                break

            frame_data = recv_buffer[:frame_len]
            recv_buffer = recv_buffer[frame_len:]

            # 解析电平数据 (从 offset 28 开始)
            levels_data = frame_data[28:28+1058]  # 529 * 2 = 1058 bytes
            levels = struct.unpack(f'<{529}h', levels_data)

            # 分离前17个元数据和后512个电平
            metadata = levels[:17]
            spectrum = levels[17:]

            frame_count += 1
            print(f"\n=== FSCAN-529 Frame #{frame_count} ===")
            print(f"Metadata (前17个原始值):")
            for i, v in enumerate(metadata):
                print(f"  [{i:2d}]: {v:6d} (0x{v:04x})")

            # 转换为有意义的值
            print(f"\nSpectrum (后512个值):")
            print(f"  范围: [{min(spectrum)}, {max(spectrum)}]")
            print(f"  前10个: {list(spectrum[:10])}")

            metadata_frames.append(metadata)

    sock.close()

    # 分析元数据规律
    print("\n" + "=" * 60)
    print("元数据值分析")
    print("=" * 60)

    for i in range(17):
        vals = [m[i] for m in metadata_frames]
        unique = set(vals)
        stable = len(unique) == 1
        print(f"Metadata[{i:2d}]: values={vals[:3]}... unique={len(unique)} {'STABLE' if stable else 'VARIES'}")


if __name__ == '__main__':
    main()