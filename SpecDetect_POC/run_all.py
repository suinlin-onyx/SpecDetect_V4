"""一键启动所有服务

支持模式:
    python run_all.py           # 单Proxy模式 (原有链路)
    python run_all.py --dual    # 双Proxy模式 (新增Proxy-B指向Real Atom)
"""
import sys
import os
import subprocess
import time
import signal
import re
import argparse

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.logger import setup_logger

logger = setup_logger('run_all')

# 服务进程
processes = []

# 需要清理的端口
PORTS_TO_CHECK = [9000, 9090, 8080, 8081, 19000]  # 添加 8081 用于 Proxy-B


def cleanup_residual_processes():
    """清理可能占用端口的残留进程"""
    logger.info("检查端口占用情况...")

    for port in PORTS_TO_CHECK:
        try:
            # 使用 netstat 查找占用端口的进程
            result = subprocess.run(
                ['netstat', '-ano'],
                capture_output=True,
                text=True
            )

            for line in result.stdout.split('\n'):
                if f':{port}' in line and 'LISTENING' in line:
                    # 提取 PID
                    parts = line.split()
                    if parts[-1] == 'LISTENING':
                        continue
                    pid = parts[-1]

                    try:
                        pid_int = int(pid)
                        # 终止进程
                        logger.info(f"发现残留进程 PID={pid} 占用端口 {port}，正在终止...")
                        subprocess.run(['taskkill', '/F', '/PID', pid],
                                      capture_output=True)
                    except (ValueError, subprocess.CalledProcessError):
                        pass

        except Exception as e:
            logger.warning(f"检查端口 {port} 时出错: {e}")

    # 额外检查：查找可能残留的 python main_*.py 进程
    try:
        result = subprocess.run(
            ['tasklist', '/FI', 'IMAGENAME eq python.exe', '/FO', 'LIST'],
            capture_output=True,
            text=True
        )
        logger.debug(f"当前 Python 进程: {result.stdout}")
    except Exception:
        pass


def start_service(script_name: str, service_name: str, port: int, env: dict = None):
    """启动单个服务

    注意：不再捕获stdout/stderr到管道，因为管道缓冲区满会导致服务阻塞。
    输出重定向到日志文件。

    Args:
        script_name: 脚本文件名
        service_name: 服务名称
        port: 端口号
        env: 额外的环境变量字典
    """
    logger.info(f"启动{service_name}...")

    # 创建日志文件
    log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'logs')
    os.makedirs(log_dir, exist_ok=True)
    log_file = os.path.join(log_dir, f'service_{port}.log')

    # 准备环境变量
    process_env = os.environ.copy()
    if env:
        process_env.update(env)

    # 重定向输出到文件，不再使用管道
    with open(log_file, 'w', encoding='utf-8') as f:
        process = subprocess.Popen(
            [sys.executable, script_name],
            cwd=os.path.dirname(os.path.abspath(__file__)),
            stdout=f,
            stderr=subprocess.STDOUT,
            bufsize=1,
            text=True,
            env=process_env
        )

    processes.append((service_name, process, log_file))
    logger.info(f"{service_name} 输出日志: {log_file}")
    return process


def stop_all():
    """停止所有服务"""
    logger.info("停止所有服务...")
    for item in processes:
        if len(item) == 3:
            name, proc, log_file = item
        else:
            name, proc = item
            log_file = None
        try:
            proc.terminate()
            proc.wait(timeout=5)
            logger.info(f"{name} 已停止")
        except subprocess.TimeoutExpired:
            proc.kill()
            logger.info(f"{name} 已强制终止")
        except Exception as e:
            logger.error(f"停止{name}失败: {e}")


def main():
    """主函数"""
    # 解析命令行参数
    parser = argparse.ArgumentParser(description='频谱探测系统快速验证')
    parser.add_argument('--dual', action='store_true',
                        help='双Proxy模式：同时启动 Proxy-A(8080) 和 Proxy-B(8081)')
    args = parser.parse_args()

    logger.info("=" + "=" * 49)
    logger.info("  频谱探测系统 - Python快速验证")
    if args.dual:
        logger.info("  模式: 双Proxy并行")
    else:
        logger.info("  模式: 单Proxy")
    logger.info("=" + "=" * 49)

    # 启动前先清理残留进程
    cleanup_residual_processes()

    # 等待端口释放
    time.sleep(1)

    # 启动顺序: Mock Device -> Atom Service -> Proxy Service(s)
    try:
        # 启动虚拟设备
        start_service('main_mock.py', '虚拟设备', 9000)

        # 等待虚拟设备启动
        time.sleep(2)

        # 启动原子服务
        start_service('main_atom.py', '原子服务', 9090)

        # 等待原子服务启动
        time.sleep(2)

        # 启动代理服务
        start_service('main_proxy.py', '代理服务', 8080)

        logger.info("-" * 50)

        # 如果是双Proxy模式，启动 Proxy-B
        if args.dual:
            logger.info("启动 Proxy-B (Real Atom 链路)...")
            start_service('main_proxy_b.py', '代理服务-B', 8081, env={'PROXY_MODE': 'B'})
            logger.info("  Proxy-B: 0.0.0.0:8081 -> Real Atom (PROXY_MODE=B)")

        logger.info("=" + "=" * 49)
        logger.info("所有服务已启动!")
        logger.info("  - 虚拟设备: 127.0.0.1:9000")
        logger.info("  - 原子服务: 127.0.0.1:9090")
        logger.info("  - 代理服务: 0.0.0.0:8080 (Mock Atom)")
        if args.dual:
            logger.info("  - 代理服务-B: 0.0.0.0:8081 (Real Atom)")
        logger.info("=" + "=" * 49)
        logger.info("向量数据库(Qdrant): Docker运行中（端口6333）")
        logger.info("打开聚合页面:")
        logger.info("  - Mock Atom链路: http://localhost:8080/dashboard")
        if args.dual:
            logger.info("  - Real Atom链路: http://localhost:8081/dashboard")
        logger.info("日志文件: logs/service_*.log")
        logger.info("按 Ctrl+C 停止所有服务")

        # 等待中断信号
        while True:
            time.sleep(1)

            # 检查进程状态
            for item in processes:
                if len(item) == 3:
                    name, proc, log_file = item
                else:
                    name, proc = item
                if proc.poll() is not None:
                    logger.error(f"{name}意外退出!")
                    stop_all()
                    sys.exit(1)

    except KeyboardInterrupt:
        logger.info("收到停止信号")
    finally:
        stop_all()
        logger.info("所有服务已停止")


if __name__ == '__main__':
    main()
