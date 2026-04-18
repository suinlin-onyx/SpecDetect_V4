"""
RMCPTP 流量抓包工具
使用 NPcap 抓取发往目标地址的 TCP 流量

依赖:
    pip install scapy pyshark

用法:
    python capture.py                              # 交互式选择网卡
    python capture.py --interface 1               # 指定网卡序号
    python capture.py --filter "tcp port 9999"   # 指定过滤条件
"""

import sys
import os
import signal
import argparse

# 尝试导入 scapy
try:
    from scapy.all import *
except ImportError:
    print("错误: 需要安装 scapy")
    print("运行: pip install scapy")
    sys.exit(1)

# 目标配置
TARGET_IP = "172.18.114.231"
TARGET_PORT = 9999
OUTPUT_FILE = "rmcp_capture.pcap"


def list_interfaces():
    """列出所有网卡"""
    print("可用网卡列表:")
    print("-" * 60)
    interfaces = get_if_list()
    for i, iface in enumerate(interfaces):
        try:
            ip = get_if_addr(iface)
            print(f"  [{i}] {iface} - {ip}")
        except:
            print(f"  [{i}] {iface}")
    print("-" * 60)
    return interfaces


def packet_handler(pkt, target_ip, target_port):
    """处理每个数据包"""
    if pkt.haslayer(IP):
        ip_layer = pkt[IP]
        # 检查是否是目标地址
        if ip_layer.dst == target_ip or ip_layer.src == target_ip:
            if pkt.haslayer(TCP):
                tcp_layer = pkt[TCP]
                if tcp_layer.dport == target_port or tcp_layer.sport == target_port:
                    direction = ">>>" if tcp_layer.dport == target_port else "<<<"
                    print(f"{direction} {ip_layer.src}:{tcp_layer.sport} -> {ip_layer.dst}:{tcp_layer.dport} len={len(pkt)}")
                    return pkt
    return None


def start_capture(interface=None, filter_str=None, count=0, output_file=OUTPUT_FILE):
    """开始抓包"""
    print(f"目标: {TARGET_IP}:{TARGET_PORT}")
    print(f"输出文件: {output_file}")
    print(f"过滤条件: {filter_str or 'tcp port 9999'}")
    print("-" * 60)

    # 构建 BPF 过滤表达式
    bpf_filter = filter_str or f"tcp port {TARGET_PORT}"
    if TARGET_IP:
        bpf_filter = f"host {TARGET_IP} and {bpf_filter}"

    def custom_handler(pkt):
        result = packet_handler(pkt, TARGET_IP, TARGET_PORT)
        if result:
            wrpcap(output_file, result, append=True)

    # 开始抓包
    print("开始抓包... 按 Ctrl+C 停止")
    print("-" * 60)

    try:
        sniff(
            iface=interface,
            filter=bpf_filter,
            count=count,
            prn=custom_handler,
            store=False
        )
    except KeyboardInterrupt:
        print("\n抓包已停止")
    except Exception as e:
        print(f"抓包错误: {e}")
        print("\n提示: 如果是权限问题，尝试以管理员权限运行 Python")


def main():
    parser = argparse.ArgumentParser(description='RMCPTP 流量抓包工具')
    parser.add_argument('-i', '--interface', help='网卡序号或名称')
    parser.add_argument('-f', '--filter', help='BPF 过滤表达式')
    parser.add_argument('-c', '--count', type=int, default=0, help='抓包数量 (0=无限)')
    parser.add_argument('-o', '--output', help='输出文件路径')
    parser.add_argument('--list', action='store_true', help='列出可用网卡')
    parser.add_argument('--target-ip', help='目标IP')
    parser.add_argument('--target-port', type=int, help='目标端口')

    args = parser.parse_args()

    # 更新全局变量
    global TARGET_IP, TARGET_PORT, OUTPUT_FILE
    if args.target_ip:
        TARGET_IP = args.target_ip
    if args.target_port:
        TARGET_PORT = args.target_port
    if args.output:
        OUTPUT_FILE = args.output
    else:
        OUTPUT_FILE = "rmcp_capture.pcap"

    if args.list:
        list_interfaces()
        return

    interface = args.interface

    # 如果未指定网卡，列出并让用户选择
    if not interface:
        interfaces = list_interfaces()
        try:
            choice = input("选择网卡序号 [0]: ").strip() or "0"
            idx = int(choice)
            if idx < len(interfaces):
                interface = interfaces[idx]
            else:
                print(f"无效序号，使用默认网卡")
                interface = None
        except ValueError:
            print("无效输入，使用默认网卡")
            interface = None

    # 删除旧文件
    if os.path.exists(OUTPUT_FILE):
        os.remove(OUTPUT_FILE)

    start_capture(
        interface=interface,
        filter_str=args.filter,
        count=args.count,
        output_file=OUTPUT_FILE
    )

    print(f"\n抓包数据已保存到: {OUTPUT_FILE}")
    print("使用 rmcp_parser.py 分析抓包数据")


if __name__ == '__main__':
    main()
