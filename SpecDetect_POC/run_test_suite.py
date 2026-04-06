"""频谱探测系统 - 自动化测试套件（SOAP协议版）

运行方式:
    python run_test_suite.py

测试范围:
    - SOAP 协议层测试
    - SOAP 一致性测试（响应格式、AuthHeader、SOAP Fault）
    - 完整链路测试（Proxy → Atom）
    - 错误码测试
"""
import pytest
import requests
import time
import sys
import os

# 配置
PROXY_URL = "http://127.0.0.1:8080"
ATOM_URL = "http://127.0.0.1:9090"
MOCK_URL = "http://127.0.0.1:9000"

# SOAP 请求模板
SOAP_NS = "http://monitor.rrmp.gov.cn/services/"


def make_soap_request(operation, params, auth_header=None):
    """构造 SOAP 请求"""
    header_xml = ""
    if auth_header:
        header_xml = f"""
            <soap:Header>
                <mon:AuthHeader xmlns:mon="{SOAP_NS}">
                    <mon:Token>{auth_header['token']}</mon:Token>
                    <mon:Timestamp>{auth_header['timestamp']}</mon:Timestamp>
                    <mon:Signature>{auth_header['signature']}</mon:Signature>
                </mon:AuthHeader>
            </soap:Header>"""

    params_xml = ""
    for key, value in params.items():
        params_xml += f"<mon:{key}>{value}</mon:{key}>"

    xml = f'''<?xml version="1.0" encoding="UTF-8"?>
<soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
               xmlns:mon="{SOAP_NS}">
    {header_xml}
    <soap:Body>
        <mon:{operation}>
            {params_xml}
        </mon:{operation}>
    </soap:Body>
</soap:Envelope>'''
    return xml.encode('utf-8')


class TestResult:
    """测试结果记录"""
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.skipped = 0
        self.errors = []

    def record(self, name, success, message="", skip=False):
        if skip:
            self.skipped += 1
            print(f"  [SKIP] {name} - {message}")
        elif success:
            self.passed += 1
            print(f"  [PASS] {name}")
        else:
            self.failed += 1
            self.errors.append(f"{name}: {message}")
            print(f"  [FAIL] {name} - {message}")

    def summary(self):
        print("\n" + "=" * 60)
        print(f"测试结果: 通过={self.passed}, 失败={self.failed}, 跳过={self.skipped}")
        if self.errors:
            print("\n失败项:")
            for e in self.errors:
                print(f"  - {e}")
        print("=" * 60)
        return self.failed == 0


def check_services():
    """检查服务状态"""
    print("\n[0] 检查服务状态...")
    result = TestResult()

    services = [
        ("Atom Service", f"{ATOM_URL}/health"),
        ("Mock Device", f"{MOCK_URL}/health"),
        ("Proxy Service", f"{PROXY_URL}/health"),
    ]

    for name, url in services:
        try:
            resp = requests.get(url, timeout=3)
            if resp.status_code == 200:
                result.record(name, True)
            else:
                result.record(name, False, f"状态码={resp.status_code}")
        except Exception as e:
            result.record(name, False, str(e))

    return result


def test_soap_sglfreq():
    """SOAP 测试: SglFreqMeasure"""
    print("\n[1] SOAP 测试: SglFreqMeasure...")
    result = TestResult()

    soap_request = make_soap_request("SglFreqMeasure", {"Frequency": "100000000"})

    try:
        resp = requests.post(
            f"{PROXY_URL}/soap",
            data=soap_request,
            headers={'Content-Type': 'text/xml; charset=utf-8'},
            timeout=10
        )

        if resp.status_code != 200:
            result.record("SglFreqMeasure 请求", False, f"HTTP {resp.status_code}")
            return result

        result.record("SglFreqMeasure 请求", True)

        # 解析响应 XML
        from lxml import etree
        root = etree.fromstring(resp.content)
        body = root.find('.//{http://schemas.xmlsoap.org/soap/envelope/}Body')
        response = body[0]

        # 验证 SOAP 响应格式（P0 问题）
        response_tag = response.tag
        if 'Response' in response_tag or 'mon:' in response_tag:
            result.record("响应使用 mon: 命名空间", True)
        else:
            result.record("响应使用 mon: 命名空间", False,
                         f"当前标签: {response_tag}")

        # 验证 ResultCode
        result_code = response.find('.//{http://monitor.rrmp.gov.cn/services/}ResultCode')
        if result_code is not None:
            result.record("响应包含 ResultCode", True)
            if result_code.text == '0':
                result.record("ResultCode=0 (成功)", True)
            else:
                result.record("ResultCode=0 (成功)", False, f"实际: {result_code.text}")
        else:
            result.record("响应包含 ResultCode", False, "未找到 ResultCode 元素")

        # 验证 ResultMessage
        result_msg = response.find('.//{http://monitor.rrmp.gov.cn/services/}ResultMessage')
        if result_msg is not None:
            result.record("响应包含 ResultMessage", True)
        else:
            result.record("响应包含 ResultMessage", False, "未找到 ResultMessage 元素")

        # 验证 Data 包装
        data_elem = response.find('.//{http://monitor.rrmp.gov.cn/services/}Data')
        if data_elem is not None:
            result.record("响应包含 Data 包装", True)
        else:
            result.record("响应包含 Data 包装", False, "未找到 Data 元素")

    except requests.exceptions.ConnectionError:
        result.record("SglFreqMeasure 请求", False, "服务未连接")
    except Exception as e:
        result.record("SglFreqMeasure 请求", False, str(e))

    return result


def test_soap_fscan():
    """SOAP 测试: FScan"""
    print("\n[2] SOAP 测试: FScan...")
    result = TestResult()

    soap_request = make_soap_request("FScan", {
        "StartFreq": "100000000",
        "EndFreq": "200000000",
        "Step": "1000000"
    })

    try:
        resp = requests.post(
            f"{PROXY_URL}/soap",
            data=soap_request,
            headers={'Content-Type': 'text/xml; charset=utf-8'},
            timeout=10
        )

        if resp.status_code != 200:
            result.record("FScan 请求", False, f"HTTP {resp.status_code}")
            return result

        result.record("FScan 请求", True)

        from lxml import etree
        root = etree.fromstring(resp.content)
        body = root.find('.//{http://schemas.xmlsoap.org/soap/envelope/}Body')
        response = body[0]

        # 验证格式
        result_code = response.find('.//{http://monitor.rrmp.gov.cn/services/}ResultCode')
        if result_code is not None and result_code.text == '0':
            result.record("FScan ResultCode=0", True)
        else:
            result.record("FScan ResultCode=0", False,
                         f"ResultCode: {result_code.text if result_code else 'N/A'}")

    except requests.exceptions.ConnectionError:
        result.record("FScan 请求", False, "服务未连接")
    except Exception as e:
        result.record("FScan 请求", False, str(e))

    return result


def test_soap_ifanalysis():
    """SOAP 测试: IFAnalysis"""
    print("\n[3] SOAP 测试: IFAnalysis...")
    result = TestResult()

    soap_request = make_soap_request("IFAnalysis", {
        "Frequency": "100000000",
        "Span": "1000000"
    })

    try:
        resp = requests.post(
            f"{PROXY_URL}/soap",
            data=soap_request,
            headers={'Content-Type': 'text/xml; charset=utf-8'},
            timeout=10
        )

        if resp.status_code != 200:
            result.record("IFAnalysis 请求", False, f"HTTP {resp.status_code}")
            return result

        result.record("IFAnalysis 请求", True)

    except requests.exceptions.ConnectionError:
        result.record("IFAnalysis 请求", False, "服务未连接")
    except Exception as e:
        result.record("IFAnalysis 请求", False, str(e))

    return result


def test_soap_auth_header():
    """SOAP 测试: AuthHeader 认证"""
    print("\n[4] SOAP 测试: AuthHeader 认证...")
    result = TestResult()

    # 测试有效 AuthHeader
    soap_request = make_soap_request(
        "SglFreqMeasure",
        {"Frequency": "100000000"},
        auth_header={
            "token": "valid_token",
            "timestamp": "2026-04-06T12:00:00Z",
            "signature": "valid_sig"
        }
    )

    try:
        resp = requests.post(
            f"{PROXY_URL}/soap",
            data=soap_request,
            headers={'Content-Type': 'text/xml; charset=utf-8'},
            timeout=10
        )

        if resp.status_code == 200:
            result.record("有效 AuthHeader 请求", True)
        else:
            result.record("有效 AuthHeader 请求", False, f"HTTP {resp.status_code}")

    except requests.exceptions.ConnectionError:
        result.record("有效 AuthHeader 请求", False, "服务未连接")

    # 测试无效 AuthHeader（期望拒绝）
    invalid_soap = make_soap_request(
        "SglFreqMeasure",
        {"Frequency": "100000000"},
        auth_header={
            "token": "invalid_token",
            "timestamp": "2026-04-06T12:00:00Z",
            "signature": "bad_sig"
        }
    )

    try:
        resp = requests.post(
            f"{PROXY_URL}/soap",
            data=invalid_soap,
            headers={'Content-Type': 'text/xml; charset=utf-8'},
            timeout=10
        )

        # 期望行为：无效 token 应返回错误（SOAP Fault 或 ResultCode != 0）
        # 当前实现：忽略 AuthHeader，因此仍返回成功
        if resp.status_code == 200:
            result.record("无效 AuthHeader 处理", False, "当前忽略 AuthHeader（应拒绝）")
        else:
            result.record("无效 AuthHeader 处理", True, f"HTTP {resp.status_code}")

    except requests.exceptions.ConnectionError:
        result.record("无效 AuthHeader 处理", False, "服务未连接")

    return result


def test_soap_fault():
    """SOAP 测试: SOAP Fault 错误格式"""
    print("\n[5] SOAP 测试: SOAP Fault 错误格式...")
    result = TestResult()

    # 触发设备未连接错误
    soap_request = make_soap_request("SglFreqMeasure", {"Frequency": "100000000"})

    try:
        resp = requests.post(
            f"{PROXY_URL}/soap",
            data=soap_request,
            headers={'Content-Type': 'text/xml; charset=utf-8'},
            timeout=10
        )

        from lxml import etree
        root = etree.fromstring(resp.content)
        body = root.find('.//{http://schemas.xmlsoap.org/soap/envelope/}Body')
        first_child = body[0]

        # 检查是否为 SOAP Fault
        if 'Fault' in first_child.tag:
            result.record("返回 SOAP Fault", True)
            fault_code = first_child.find('faultcode')
            fault_string = first_child.find('faultstring')
            if fault_code is not None:
                result.record("Fault 包含 faultcode", True, f"值: {fault_code.text}")
            if fault_string is not None:
                result.record("Fault 包含 faultstring", True, f"值: {fault_string.text}")
        else:
            result.record("返回 SOAP Fault", False,
                         f"当前返回: {first_child.tag}")

    except requests.exceptions.ConnectionError:
        result.record("SOAP Fault 测试", False, "服务未连接")
    except Exception as e:
        result.record("SOAP Fault 测试", False, str(e))

    return result


def test_soap_response_format():
    """SOAP 测试: 响应格式一致性"""
    print("\n[6] SOAP 测试: 响应格式 (ResultCode/ResultMessage/Data)...")
    result = TestResult()

    soap_request = make_soap_request("SglFreqMeasure", {"Frequency": "100000000"})

    try:
        resp = requests.post(
            f"{PROXY_URL}/soap",
            data=soap_request,
            headers={'Content-Type': 'text/xml; charset=utf-8'},
            timeout=10
        )

        from lxml import etree
        root = etree.fromstring(resp.content)
        body = root.find('.//{http://schemas.xmlsoap.org/soap/envelope/}Body')
        response = body[0]

        # 检查 4 个关键问题
        checks = []

        # 1. mon: 命名空间
        tag = response.tag
        checks.append(('mon: 命名空间',
                      'mon:' in tag or 'http://monitor.rrmp.gov.cn/services/' in tag))

        # 2. ResultCode
        rc = response.find('.//{http://monitor.rrmp.gov.cn/services/}ResultCode')
        checks.append(('ResultCode', rc is not None))

        # 3. ResultMessage
        rm = response.find('.//{http://monitor.rrmp.gov.cn/services/}ResultMessage')
        checks.append(('ResultMessage', rm is not None))

        # 4. Data 包装
        de = response.find('.//{http://monitor.rrmp.gov.cn/services/}Data')
        checks.append(('Data 包装', de is not None))

        for name, passed in checks:
            result.record(f"响应格式 - {name}", passed)

    except requests.exceptions.ConnectionError:
        result.record("响应格式测试", False, "服务未连接")
    except Exception as e:
        result.record("响应格式测试", False, str(e))

    return result


def run_soap_unit_tests():
    """运行 SOAP 单元测试"""
    print("\n[7] SOAP 单元测试 (pytest)...")
    result = TestResult()

    try:
        exit_code = pytest.main([
            "tests/test_soap_consistency.py",
            "-v",
            "--tb=short",
        ], plugins=[])

        result.record("test_soap_consistency.py", exit_code == 0,
                     f"exit_code={exit_code}")
    except Exception as e:
        result.record("test_soap_consistency.py", False, str(e))

    return result


def run_protocol_unit_tests():
    """运行协议单元测试（RMCPTP 解析器，与传输层无关）"""
    print("\n[8] 协议单元测试 (pytest)...")
    result = TestResult()

    try:
        exit_code = pytest.main([
            "tests/test_atom.py",
            "tests/test_mock.py",
            "-v",
            "--tb=short",
        ], plugins=[])

        result.record("test_atom.py + test_mock.py", exit_code == 0,
                     f"exit_code={exit_code}")
    except Exception as e:
        result.record("test_atom.py + test_mock.py", False, str(e))

    return result


def main():
    """主测试流程"""
    print("=" * 60)
    print("频谱探测系统 - 自动化测试套件 (SOAP版)")
    print("=" * 60)
    print(f"测试时间: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"测试环境: Proxy={PROXY_URL}, Atom={ATOM_URL}, Mock={MOCK_URL}")

    all_results = []

    # 0. 检查服务状态
    status_result = check_services()
    all_results.append(("服务状态检查", status_result))

    # 1-3. SOAP 业务测试
    all_results.append(("SglFreqMeasure", test_soap_sglfreq()))
    all_results.append(("FScan", test_soap_fscan()))
    all_results.append(("IFAnalysis", test_soap_ifanalysis()))

    # 4-6. SOAP 协议层测试
    all_results.append(("AuthHeader 认证", test_soap_auth_header()))
    all_results.append(("SOAP Fault", test_soap_fault()))
    all_results.append(("响应格式一致性", test_soap_response_format()))

    # 7-8. 单元测试
    all_results.append(("SOAP 单元测试", run_soap_unit_tests()))
    all_results.append(("协议单元测试", run_protocol_unit_tests()))

    # 汇总
    print("\n" + "=" * 60)
    print("测试汇总")
    print("=" * 60)

    total_passed = 0
    total_failed = 0
    total_skipped = 0
    for name, result in all_results:
        print(f"\n{name}:")
        print(f"  通过={result.passed}, 失败={result.failed}, 跳过={result.skipped}")
        total_passed += result.passed
        total_failed += result.failed
        total_skipped += result.skipped

    print("\n" + "=" * 60)
    print(f"总计: 通过={total_passed}, 失败={total_failed}, 跳过={total_skipped}")
    print("=" * 60)

    return total_failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
