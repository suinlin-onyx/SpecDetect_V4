"""TCP 数据包捕获脚本

监听指定端口，接收并打印原始十六进制数据
用于分析 Real Atom 发送的 RMCPTP 帧格式
"""
import socket
import struct
import sys
import threading

def capture_port(port, output_file=None):
    """监听端口并打印接收到的原始数据"""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(('0.0.0.0', port))
    server.listen(5)

    print(f"[+] 监听端口 {port}，等待连接...")

    if output_file:
        f = open(output_file, 'w')
        f.write(f"监听端口: {port}\n")
        f.write("=" * 80 + "\n")

    while True:
        client, addr = server.accept()
        print(f"\n[+] 收到连接: {addr}")

        if output_file:
            f.write(f"\n[+] 收到连接: {addr}\n")

        try:
            # 读取 18 字节帧头
            header = client.recv(18)
            if len(header) < 18:
                print(f"[-] 数据不完整，只收到 {len(header)} 字节")
                continue

            # 解析帧头
            dw_length, tm_stamp, n_version, n_data_type, n_flags, n_checksum = \
                struct.unpack('!IQHBBH', header)

            print(f"\n[*] 帧头信息:")
            print(f"    dwLength:   {dw_length}")
            print(f"    tmStamp:    {tm_stamp}")
            print(f"    nVersion:   0x{n_version:04X}")
            print(f"    nDataType:  0x{n_data_type:02X}")
            print(f"    nFlags:     0x{n_flags:02X}")
            print(f"    nCheckSum:  0x{n_checksum:04X}")

            print(f"\n[*] 帧头原始字节: {header.hex()}")

            if output_file:
                f.write(f"\n[*] 帧头信息:\n")
                f.write(f"    dwLength:   {dw_length}\n")
                f.write(f"    tmStamp:    {tm_stamp}\n")
                f.write(f"    nVersion:   0x{n_version:04X}\n")
                f.write(f"    nDataType:  0x{n_data_type:02X}\n")
                f.write(f"    nFlags:     0x{n_flags:02X}\n")
                f.write(f"    nCheckSum:  0x{n_checksum:04X}\n")
                f.write(f"    帧头原始字节: {header.hex()}\n")

            # 计算校验和 (用 Mock Device 的算法)
            length_val = struct.unpack('!I', header[0:4])[0]
            time_val = struct.unpack('!Q', header[4:12])[0]
            version_type_flags = struct.unpack('!HBB', header[12:16])[0]

            total = (length_val & 0xFFFF) + (length_val >> 16)
            total += (time_val & 0xFFFF) + (time_val >> 16)
            total += (version_type_flags & 0xFFFF) + (version_type_flags >> 16)
            for _ in range(2):
                total = (total >> 1) + (total & 0x7FFF)
            calculated_checksum = (~total) & 0xFFFF

            print(f"\n[*] 校验和验证:")
            print(f"    计算值: 0x{calculated_checksum:04X}")
            print(f"    实际值: 0x{n_checksum:04X}")
            print(f"    匹配: {'是' if calculated_checksum == n_checksum else '否'}")

            if output_file:
                f.write(f"\n[*] 校验和验证:\n")
                f.write(f"    计算值: 0x{calculated_checksum:04X}\n")
                f.write(f"    实际值: 0x{n_checksum:04X}\n")
                f.write(f"    匹配: {'是' if calculated_checksum == n_checksum else '否'}\n")

            # 读取业务数据
            if dw_length > 0:
                payload = b''
                while len(payload) < dw_length:
                    chunk = client.recv(min(1024, dw_length - len(payload)))
                    if not chunk:
                        break
                    payload += chunk

                print(f"\n[*] 业务数据 ({len(payload)} 字节):")
                print(f"    {payload.hex()}")

                if output_file:
                    f.write(f"\n[*] 业务数据 ({len(payload)} 字节):\n")
                    f.write(f"    {payload.hex()}\n")

            # 发送简单响应
            client.send(b'\x00' * 18)

        except Exception as e:
            print(f"[-] 错误: {e}")
            if output_file:
                f.write(f"[-] 错误: {e}\n")
        finally:
            client.close()
            print(f"[-] 连接已关闭")

if __name__ == '__main__':
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 9001
    output = sys.argv[2] if len(sys.argv) > 2 else None
    capture_port(port, output)
