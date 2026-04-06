"""快速连续请求压力测试"""
import requests
import time
import json

BASE_URL = "http://127.0.0.1:9090"

def check_health():
    """检查服务健康状态"""
    try:
        resp = requests.get(f"{BASE_URL}/health", timeout=5)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def connect_device():
    """连接设备"""
    try:
        resp = requests.post(f"{BASE_URL}/device/connect", timeout=5)
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def test_sglfreq():
    """单频测量"""
    try:
        resp = requests.post(
            f"{BASE_URL}/monitor/sglfreq",
            json={"frequency": 100_000_000},
            timeout=10
        )
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def test_fscan():
    """频段扫描"""
    try:
        resp = requests.post(
            f"{BASE_URL}/monitor/fscan",
            json={"start_freq": 100_000_000, "end_freq": 200_000_000},
            timeout=10
        )
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def test_ifanalysis():
    """中频分析"""
    try:
        resp = requests.post(
            f"{BASE_URL}/monitor/ifanalysis",
            json={"frequency": 100_000_000, "span": 1_000_000},
            timeout=10
        )
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def test_df():
    """单频测向"""
    try:
        resp = requests.post(
            f"{BASE_URL}/direction/df",
            json={"frequency": 100_000_000},
            timeout=10
        )
        return resp.json()
    except Exception as e:
        return {"error": str(e)}

def run_stress_test():
    """压力测试"""
    print("=" * 60)
    print("频谱探测系统 - 快速连续请求压力测试")
    print("=" * 60)

    # 1. 检查服务状态
    print("\n[1] 检查服务状态...")
    health = check_health()
    print(f"    原子服务: {health}")

    # 2. 连接设备
    print("\n[2] 连接设备...")
    result = connect_device()
    print(f"    {result}")

    # 3. 单次请求测试
    print("\n[3] 单次请求测试...")
    print("    SGLFREQ:", test_sglfreq().get("success"))
    print("    FSCAN:", test_fscan().get("success"))
    print("    IFANALYSIS:", test_ifanalysis().get("success"))

    # 4. 快速连续10次SGLFREQ
    print("\n[4] 快速连续10次SGLFREQ请求...")
    start = time.time()
    results = []
    for i in range(10):
        result = test_sglfreq()
        results.append(result.get("success"))
    elapsed = time.time() - start
    print(f"    成功: {sum(results)}/10, 耗时: {elapsed:.2f}s")

    # 5. 快速连续20次混合请求
    print("\n[5] 快速连续20次混合请求 (5轮 x 4种业务)...")
    start = time.time()
    results = {"sglfreq": [], "fscan": [], "ifanalysis": [], "df": []}
    for i in range(5):
        results["sglfreq"].append(test_sglfreq().get("success"))
        results["fscan"].append(test_fscan().get("success"))
        results["ifanalysis"].append(test_ifanalysis().get("success"))
        results["df"].append(test_df().get("success"))
    elapsed = time.time() - start
    print(f"    SGLFREQ成功: {sum(results['sglfreq'])}/5")
    print(f"    FSCAN成功: {sum(results['fscan'])}/5")
    print(f"    IFANALYSIS成功: {sum(results['ifanalysis'])}/5")
    print(f"    DF成功: {sum(results['df'])}/5")
    print(f"    总耗时: {elapsed:.2f}s")

    # 6. 压力测试 - 50次连续请求
    print("\n[6] 压力测试 - 50次连续SGLFREQ请求...")
    start = time.time()
    results = []
    for i in range(50):
        result = test_sglfreq()
        results.append(result.get("success"))
        if (i + 1) % 10 == 0:
            print(f"    完成 {i+1}/50...")
    elapsed = time.time() - start
    print(f"    成功: {sum(results)}/50, 耗时: {elapsed:.2f}s")

    # 7. 最终健康检查
    print("\n[7] 最终健康检查...")
    health = check_health()
    print(f"    原子服务: {health}")

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)

if __name__ == "__main__":
    run_stress_test()
