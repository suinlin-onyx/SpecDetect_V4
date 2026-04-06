"""频谱探测系统 - 独立窗口启动脚本

每个服务在独立的终端窗口中运行，避免输出管道阻塞问题
"""
import subprocess
import sys
import os
import time
import signal

# 服务配置
SERVICES = [
    {
        'name': 'Mock Device',
        'script': 'main_mock.py',
        'port': 9000,
        'color': '32',  # 绿色
    },
    {
        'name': 'Atom Service',
        'script': 'main_atom.py',
        'port': 9090,
        'color': '33',  # 黄色
    },
    {
        'name': 'Proxy Service',
        'script': 'main_proxy.py',
        'port': 8080,
        'color': '36',  # 青色
    },
]

def cleanup_ports():
    """清理占用端口的进程"""
    import socket

    print("\033[1;36m检查端口占用...\033[0m")

    for svc in SERVICES:
        port = svc['port']
        try:
            # 检查端口是否被占用
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(1)
                result = s.connect_ex(('127.0.0.1', port))
                if result == 0:
                    print(f"\033[1;33m  端口 {port} 已被占用，正在查找进程...\033[0m")
                    # 查找并终止进程
                    result = subprocess.run(
                        ['netstat', '-ano'],
                        capture_output=True,
                        text=True
                    )
                    for line in result.stdout.split('\n'):
                        if f':{port}' in line and 'LISTENING' in line:
                            parts = line.split()
                            pid = parts[-1]
                            if pid.isdigit():
                                print(f"\033[1;33m  终止 PID={pid}\033[0m")
                                subprocess.run(['taskkill', '/F', '/PID', pid],
                                             capture_output=True)
                    time.sleep(0.5)
        except Exception as e:
            print(f"  检查端口 {port} 时出错: {e}")

    print()

def start_service_in_new_window(svc):
    """在新窗口中启动服务"""
    name = svc['name']
    script = svc['script']
    port = svc['port']
    color = svc['color']

    print(f"\033[1;{color}m启动 {name} (端口 {port})...\033[0m")

    # 使用 start 命令在新窗口中启动
    cmd = f'start "SpecDetect_{name}" cmd /k "cd /d {os.path.dirname(os.path.abspath(__file__))} && python {script}"'

    subprocess.run(cmd, shell=True)

def main():
    """主函数"""
    os.system('cls' if os.name == 'nt' else 'clear')

    print("\033[1;32m" + "=" * 50 + "\033[0m")
    print("\033[1;32m  频谱探测系统 - 独立窗口启动\033[0m")
    print("\033[1;32m" + "=" * 50 + "\033[0m")
    print()

    # 清理端口
    cleanup_ports()

    # 等待端口释放
    time.sleep(1)

    # 启动每个服务
    for i, svc in enumerate(SERVICES, 1):
        start_service_in_new_window(svc)
        time.sleep(2)  # 等待服务启动

    print("\033[1;32m" + "=" * 50 + "\033[0m")
    print("\033[1;32m  所有服务已启动!\033[0m")
    print("\033[1;32m" + "=" * 50 + "\033[0m")
    print()
    print("\033[1;37m  虚拟设备: \033[0m127.0.0.1:9000 (仅TCP)")
    print("\033[1;37m  原子服务: \033[0m127.0.0.1:9090")
    print("\033[1;37m  代理服务: \033[0m127.0.0.1:8080")
    print()
    print("\033[1;37m  聚合页面: \033[0mhttp://localhost:8080/dashboard")
    print()
    print("\033[1;90m  请检查各个终端窗口的服务启动状态\033[0m")
    print("\033[1;90m  按 Ctrl+C 停止所有服务\033[0m")
    print()

    # 等待中断
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\033[1;31m停止所有服务...\033[0m")
        # 终止所有 Python 进程
        subprocess.run('taskkill /F /IM python.exe', shell=True, capture_output=True)

if __name__ == '__main__':
    main()
