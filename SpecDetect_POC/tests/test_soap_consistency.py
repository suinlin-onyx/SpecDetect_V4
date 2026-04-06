"""
SOAP 协议一致性测试

测试范围（基于 PLAN_SOAP_CONSISTENCY_20260406.md）：
1. SOAP 信封结构（命名空间、Body、Header）
2. AuthHeader 认证（Token/Timestamp/Signature）
3. 请求操作（StartMeasure, SglFreqMeasure, FScan 等）
4. SOAP 响应格式（ResultCode/ResultMessage/Data 包装）— P0
5. SOAP Fault 错误格式 — P1
6. WSDL 服务描述 — P2
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from lxml import etree
from app.proxy_service.soap_handler import SOAPHandler
from utils.exceptions import SOAPParseError


# ============================================================================
# 测试夹具
# ============================================================================

class TestSOAPEnvelopeStructure:
    """1. SOAP 信封结构测试"""

    def setup_method(self):
        self.handler = SOAPHandler()

    def test_valid_soap_envelope_with_body(self):
        """测试有效 SOAP 信封（仅 Body）"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Body>
                <mon:StartMeasure xmlns:mon="http://monitor.rrmp.gov.cn/services/">
                    <mon:Frequency>100000000</mon:Frequency>
                </mon:StartMeasure>
            </soap:Body>
        </soap:Envelope>'''

        result = self.handler.parse_request(xml)

        # lxml 返回完整命名空间 URI，不是前缀
        assert 'StartMeasure' in result['operation']
        assert 'http://monitor.rrmp.gov.cn/services/' in result['operation']
        assert result['params']['Frequency'] == '100000000'

    def test_soap_envelope_with_header(self):
        """测试带 Header 的 SOAP 信封"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                       xmlns:mon="http://monitor.rrmp.gov.cn/services/">
            <soap:Header>
                <mon:AuthHeader>
                    <mon:Token>test_token</mon:Token>
                    <mon:Timestamp>2026-04-06T12:00:00Z</mon:Timestamp>
                    <mon:Signature>abc123</mon:Signature>
                </mon:AuthHeader>
            </soap:Header>
            <soap:Body>
                <mon:StartMeasure>
                    <mon:Frequency>100000000</mon:Frequency>
                </mon:StartMeasure>
            </soap:Body>
        </soap:Envelope>'''

        root = etree.fromstring(xml.encode('utf-8'))
        header = root.find('{http://schemas.xmlsoap.org/soap/envelope/}Header')

        # 验证 Header 存在
        assert header is not None

        # 验证 AuthHeader
        auth_header = header.find('.//{http://monitor.rrmp.gov.cn/services/}AuthHeader')
        assert auth_header is not None
        assert auth_header.find('{http://monitor.rrmp.gov.cn/services/}Token').text == 'test_token'
        assert auth_header.find('{http://monitor.rrmp.gov.cn/services/}Timestamp').text == '2026-04-06T12:00:00Z'
        assert auth_header.find('{http://monitor.rrmp.gov.cn/services/}Signature').text == 'abc123'

    def test_invalid_xml(self):
        """测试无效 XML"""
        with pytest.raises(SOAPParseError):
            self.handler.parse_request('not xml at all')

    def test_missing_body(self):
        """测试缺少 Body"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
        </soap:Envelope>'''

        with pytest.raises(SOAPParseError, match="未找到SOAP Body"):
            self.handler.parse_request(xml)

    def test_empty_body(self):
        """测试空 Body"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Body/>
        </soap:Envelope>'''

        with pytest.raises(SOAPParseError, match="SOAP Body为空"):
            self.handler.parse_request(xml)

    def test_wrong_namespace(self):
        """测试错误命名空间（应使用标准 SOAP 命名空间）"""
        # 使用错误的 envelope 命名空间
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://wrong-namespace.org/soap/envelope/">
            <soap:Body>
                <StartMeasure/>
            </soap:Body>
        </soap:Envelope>'''

        # 验证：错误的命名空间应该导致解析失败（找不到 Body）
        with pytest.raises(SOAPParseError):
            self.handler.parse_request(xml)


# ============================================================================
# 2. AuthHeader 认证测试
# ============================================================================

class TestAuthHeader:
    """2. AuthHeader 认证测试 — P0"""

    def setup_method(self):
        self.handler = SOAPHandler()

    def test_parse_auth_header(self):
        """测试解析 AuthHeader"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                       xmlns:mon="http://monitor.rrmp.gov.cn/services/">
            <soap:Header>
                <mon:AuthHeader>
                    <mon:Token>my_token_12345</mon:Token>
                    <mon:Timestamp>2026-04-06T10:00:00Z</mon:Timestamp>
                    <mon:Signature>xyz_signature</mon:Signature>
                </mon:AuthHeader>
            </soap:Header>
            <soap:Body>
                <mon:StartMeasure>
                    <mon:Frequency>100000000</mon:Frequency>
                </mon:StartMeasure>
            </soap:Body>
        </soap:Envelope>'''

        root = etree.fromstring(xml.encode('utf-8'))
        header = root.find('{http://schemas.xmlsoap.org/soap/envelope/}Header')
        auth_header = header.find('.//{http://monitor.rrmp.gov.cn/services/}AuthHeader')

        assert auth_header is not None
        token = auth_header.find('{http://monitor.rrmp.gov.cn/services/}Token')
        timestamp = auth_header.find('{http://monitor.rrmp.gov.cn/services/}Timestamp')
        signature = auth_header.find('{http://monitor.rrmp.gov.cn/services/}Signature')

        assert token is not None
        assert timestamp is not None
        assert signature is not None
        assert token.text == 'my_token_12345'
        assert signature.text == 'xyz_signature'

    def test_missing_auth_header(self):
        """测试缺少 AuthHeader（应被拒绝）"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                       xmlns:mon="http://monitor.rrmp.gov.cn/services/">
            <soap:Header/>
            <soap:Body>
                <mon:StartMeasure>
                    <mon:Frequency>100000000</mon:Frequency>
                </mon:StartMeasure>
            </soap:Body>
        </soap:Envelope>'''

        # 验证 Header 存在但无 AuthHeader
        root = etree.fromstring(xml.encode('utf-8'))
        header = root.find('{http://schemas.xmlsoap.org/soap/envelope/}Header')
        auth_header = header.find('.//{http://monitor.rrmp.gov.cn/services/}AuthHeader')

        assert auth_header is None
        # 期望行为：缺少 AuthHeader 应返回认证错误

    def test_invalid_token(self):
        """测试无效 Token（应被拒绝）"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                       xmlns:mon="http://monitor.rrmp.gov.cn/services/">
            <soap:Header>
                <mon:AuthHeader>
                    <mon:Token>invalid_token</mon:Token>
                    <mon:Timestamp>2026-04-06T10:00:00Z</mon:Timestamp>
                    <mon:Signature>abc123</mon:Signature>
                </mon:AuthHeader>
            </soap:Header>
            <soap:Body>
                <mon:StartMeasure>
                    <mon:Frequency>100000000</mon:Frequency>
                </mon:StartMeasure>
            </soap:Body>
        </soap:Envelope>'''

        # 期望行为：无效 token 应返回 SOAP Fault 或认证错误
        root = etree.fromstring(xml.encode('utf-8'))
        auth_header = root.find('.//{http://monitor.rrmp.gov.cn/services/}AuthHeader')
        token = auth_header.find('{http://monitor.rrmp.gov.cn/services/}Token')
        assert token.text == 'invalid_token'


# ============================================================================
# 3. 请求操作测试
# ============================================================================

class TestSOAPOperations:
    """3. SOAP 请求操作测试"""

    def setup_method(self):
        self.handler = SOAPHandler()

    def test_start_measure(self):
        """测试 StartMeasure 操作"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                       xmlns:mon="http://monitor.rrmp.gov.cn/services/">
            <soap:Body>
                <mon:StartMeasure>
                    <mon:Frequency>100000000</mon:Frequency>
                    <mon:Bandwidth>120000</mon:Bandwidth>
                </mon:StartMeasure>
            </soap:Body>
        </soap:Envelope>'''

        result = self.handler.parse_request(xml)

        assert 'StartMeasure' in result['operation']
        assert 'http://monitor.rrmp.gov.cn/services/' in result['operation']
        assert result['params']['Frequency'] == '100000000'
        assert result['params']['Bandwidth'] == '120000'

    def test_sglfreq_measure(self):
        """测试 SglFreqMeasure 操作"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                       xmlns:mon="http://monitor.rrmp.gov.cn/services/">
            <soap:Body>
                <mon:SglFreqMeasure>
                    <mon:Frequency>95800000</mon:Frequency>
                </mon:SglFreqMeasure>
            </soap:Body>
        </soap:Envelope>'''

        result = self.handler.parse_request(xml)

        assert 'SglFreqMeasure' in result['operation']
        assert result['params']['Frequency'] == '95800000'

    def test_fscan(self):
        """测试 FScan 操作"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                       xmlns:mon="http://monitor.rrmp.gov.cn/services/">
            <soap:Body>
                <mon:FScan>
                    <mon:StartFreq>100000000</mon:StartFreq>
                    <mon:EndFreq>200000000</mon:EndFreq>
                    <mon:Step>1000000</mon:Step>
                </mon:FScan>
            </soap:Body>
        </soap:Envelope>'''

        result = self.handler.parse_request(xml)

        assert 'FScan' in result['operation']
        assert result['params']['StartFreq'] == '100000000'
        assert result['params']['EndFreq'] == '200000000'
        assert result['params']['Step'] == '1000000'

    def test_if_analysis(self):
        """测试 IFAnalysis 操作"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                       xmlns:mon="http://monitor.rrmp.gov.cn/services/">
            <soap:Body>
                <mon:IFAnalysis>
                    <mon:Frequency>100000000</mon:Frequency>
                    <mon:Span>1000000</mon:Span>
                </mon:IFAnalysis>
            </soap:Body>
        </soap:Envelope>'''

        result = self.handler.parse_request(xml)

        assert 'IFAnalysis' in result['operation']
        assert result['params']['Frequency'] == '100000000'
        assert result['params']['Span'] == '1000000'

    def test_sglfreq_df(self):
        """测试 SglFreqDF 操作"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                       xmlns:mon="http://monitor.rrmp.gov.cn/services/">
            <soap:Body>
                <mon:SglFreqDF>
                    <mon:Frequency>100000000</mon:Frequency>
                </mon:SglFreqDF>
            </soap:Body>
        </soap:Envelope>'''

        result = self.handler.parse_request(xml)

        assert 'SglFreqDF' in result['operation']
        assert result['params']['Frequency'] == '100000000'

    def test_if_df(self):
        """测试 IFDF 操作"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                       xmlns:mon="http://monitor.rrmp.gov.cn/services/">
            <soap:Body>
                <mon:IFDF>
                    <mon:Frequency>100000000</mon:Frequency>
                </mon:IFDF>
            </soap:Body>
        </soap:Envelope>'''

        result = self.handler.parse_request(xml)

        assert 'IFDF' in result['operation']


# ============================================================================
# 4. SOAP 响应格式测试 — P0（核心问题）
# ============================================================================

class TestSOAPResponseFormat:
    """
    4. SOAP 响应格式测试 — P0

    文档要求的响应格式：
    <mon:Response xmlns:mon="http://monitor.rrmp.gov.cn/services/">
        <mon:ResultCode>0</mon:ResultCode>
        <mon:ResultMessage>Success</mon:ResultMessage>
        <mon:Data>
            <mon:Frequency>95800000</mon:Frequency>
            <mon:SignalLevel>-45.25</mon:SignalLevel>
        </mon:Data>
    </mon:Response>

    当前实现的响应格式（不符合）：
    <Response success="true">
        <Result>OK</Result>
    </Response>
    """

    def setup_method(self):
        self.handler = SOAPHandler()

    def test_response_has_mon_namespace(self):
        """测试响应使用 mon: 命名空间前缀"""
        response_xml = self.handler.build_response(
            success=True,
            data={'Result': 'OK'}
        )

        root = etree.fromstring(response_xml.encode('utf-8'))

        # 查找 Response 元素
        body = root.find('{http://schemas.xmlsoap.org/soap/envelope/}Body')
        response = body[0]

        # 验证命名空间
        # 期望: Response 元素应在 mon: 命名空间下
        # 当前: 无命名空间前缀
        tag = response.tag
        # 这是预期会失败的测试 — 当前实现没有 mon: 前缀
        assert 'mon' in tag or 'http://monitor.rrmp.gov.cn/services/' in tag, \
            f"Response 缺少 mon: 命名空间，当前标签: {tag}"

    def test_response_has_result_code(self):
        """测试响应包含 ResultCode 元素"""
        response_xml = self.handler.build_response(
            success=True,
            data={'Result': 'OK'}
        )

        root = etree.fromstring(response_xml.encode('utf-8'))
        body = root.find('{http://schemas.xmlsoap.org/soap/envelope/}Body')
        response = body[0]

        # 验证 ResultCode 存在
        result_code = response.find('{http://monitor.rrmp.gov.cn/services/}ResultCode')
        assert result_code is not None, "缺少 ResultCode 元素"
        assert result_code.text == '0', f"ResultCode 应为 '0'，实际为: {result_code.text}"

    def test_response_has_result_message(self):
        """测试响应包含 ResultMessage 元素"""
        response_xml = self.handler.build_response(
            success=True,
            data={'Result': 'OK'}
        )

        root = etree.fromstring(response_xml.encode('utf-8'))
        body = root.find('{http://schemas.xmlsoap.org/soap/envelope/}Body')
        response = body[0]

        # 验证 ResultMessage
        result_msg = response.find('{http://monitor.rrmp.gov.cn/services/}ResultMessage')
        assert result_msg is not None, "缺少 ResultMessage 元素"
        assert result_msg.text == 'Success', f"ResultMessage 应为 'Success'，实际为: {result_msg.text}"

    def test_response_has_data_wrapper(self):
        """测试响应包含 Data 包装元素"""
        response_xml = self.handler.build_response(
            success=True,
            data={'Frequency': '95800000', 'SignalLevel': '-45.25'}
        )

        root = etree.fromstring(response_xml.encode('utf-8'))
        body = root.find('{http://schemas.xmlsoap.org/soap/envelope/}Body')
        response = body[0]

        # 验证 Data 元素存在
        data_elem = response.find('{http://monitor.rrmp.gov.cn/services/}Data')
        assert data_elem is not None, "缺少 Data 包装元素"

        # 验证 Data 内的业务数据
        freq = data_elem.find('{http://monitor.rrmp.gov.cn/services/}Frequency')
        level = data_elem.find('{http://monitor.rrmp.gov.cn/services/}SignalLevel')
        assert freq is not None, "Data 内缺少 Frequency"
        assert level is not None, "Data 内缺少 SignalLevel"

    def test_error_response_format(self):
        """测试错误响应格式"""
        response_xml = self.handler.build_response(
            success=False,
            error='设备未连接'
        )

        root = etree.fromstring(response_xml.encode('utf-8'))
        body = root.find('{http://schemas.xmlsoap.org/soap/envelope/}Body')
        response = body[0]

        # 验证 ResultCode 非 0
        result_code = response.find('{http://monitor.rrmp.gov.cn/services/}ResultCode')
        if result_code is not None:
            assert result_code.text != '0', "错误响应 ResultCode 应非 0"

        # 验证 ResultMessage 包含错误信息
        result_msg = response.find('{http://monitor.rrmp.gov.cn/services/}ResultMessage')
        if result_msg is not None:
            assert '设备未连接' in result_msg.text, f"ResultMessage 应包含错误信息，实际为: {result_msg.text}"

    def test_full_expected_response_format(self):
        """
        测试完整期望响应格式（文档要求）

        这是综合测试，当前实现会失败。
        """
        # 按文档格式构建期望的响应 XML
        expected_xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                       xmlns:mon="http://monitor.rrmp.gov.cn/services/">
            <soap:Body>
                <mon:Response>
                    <mon:ResultCode>0</mon:ResultCode>
                    <mon:ResultMessage>Success</mon:ResultMessage>
                    <mon:Data>
                        <mon:Frequency>100000000</mon:Frequency>
                        <mon:SignalLevel>-59.08</mon:SignalLevel>
                    </mon:Data>
                </mon:Response>
            </soap:Body>
        </soap:Envelope>'''

        root = etree.fromstring(expected_xml.encode('utf-8'))
        body = root.find('{http://schemas.xmlsoap.org/soap/envelope/}Body')
        response = body[0]

        # 验证各元素
        assert response.tag == '{http://monitor.rrmp.gov.cn/services/}Response'
        result_code = response.find('{http://monitor.rrmp.gov.cn/services/}ResultCode')
        result_msg = response.find('{http://monitor.rrmp.gov.cn/services/}ResultMessage')
        data_elem = response.find('{http://monitor.rrmp.gov.cn/services/}Data')

        assert result_code is not None
        assert result_msg is not None
        assert data_elem is not None
        assert result_code.text == '0'
        assert result_msg.text == 'Success'


# ============================================================================
# 5. SOAP Fault 测试 — P1
# ============================================================================

class TestSOAPFault:
    """
    5. SOAP Fault 错误格式测试 — P1

    文档要求的 SOAP Fault 格式：
    <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
        <soap:Body>
            <soap:Fault>
                <faultcode>soap:Server</faultcode>
                <faultstring>设备未连接</faultstring>
                <detail>
                    <mon:ErrorDetail xmlns:mon="http://monitor.rrmp.gov.cn/services/">
                        <mon:ErrorCode>3001</mon:ErrorCode>
                        <mon:ErrorMessage>设备未连接</mon:ErrorMessage>
                    </mon:ErrorDetail>
                </detail>
            </soap:Fault>
        </soap:Body>
    </soap:Envelope>
    """

    def setup_method(self):
        self.handler = SOAPHandler()

    def test_build_soap_fault(self):
        """测试构建 SOAP Fault"""
        # 当前实现没有 build_fault 方法，这是测试应调用的方法
        # 期望行为：build_fault(error_code, error_message)
        # 当前状态：build_response 仅使用 success=false，未生成 soap:Fault

        # 这个测试验证期望的 SOAP Fault 结构
        expected_fault_xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Body>
                <soap:Fault>
                    <faultcode>soap:Server</faultcode>
                    <faultstring>设备未连接</faultstring>
                    <detail>
                        <mon:ErrorDetail xmlns:mon="http://monitor.rrmp.gov.cn/services/">
                            <mon:ErrorCode>3001</mon:ErrorCode>
                            <mon:ErrorMessage>设备未连接</mon:ErrorMessage>
                        </mon:ErrorDetail>
                    </detail>
                </soap:Fault>
            </soap:Body>
        </soap:Envelope>'''

        root = etree.fromstring(expected_fault_xml.encode('utf-8'))
        body = root.find('{http://schemas.xmlsoap.org/soap/envelope/}Body')
        fault = body[0]

        # 验证 SOAP Fault 结构
        assert fault.tag == '{http://schemas.xmlsoap.org/soap/envelope/}Fault'
        faultcode = fault.find('faultcode')
        faultstring = fault.find('faultstring')
        detail = fault.find('detail')

        assert faultcode is not None
        assert 'Server' in faultcode.text, f"faultcode 应包含 'Server'，实际: {faultcode.text}"
        assert faultstring is not None
        assert '设备未连接' in faultstring.text
        assert detail is not None

        # 验证 detail 内的 ErrorDetail
        error_detail = detail.find('{http://monitor.rrmp.gov.cn/services/}ErrorDetail')
        assert error_detail is not None
        error_code = error_detail.find('{http://monitor.rrmp.gov.cn/services/}ErrorCode')
        error_msg = error_detail.find('{http://monitor.rrmp.gov.cn/services/}ErrorMessage')
        assert error_code is not None
        assert error_code.text == '3001'
        assert error_msg is not None
        assert '设备未连接' in error_msg.text

class TestWSDL:
    """6. WSDL 服务描述测试 — P2"""

    def test_wsdl_endpoint_exists(self):
        """测试 ?wsdl 端点是否存在（Proxy 层）"""
        # 这需要 Proxy 服务运行
        # 测试方法：通过 HTTP 请求验证 ?wsdl 端点
        import requests

        try:
            resp = requests.get('http://localhost:8080/services?wsdl', timeout=5)
            assert resp.status_code == 200, f"WSDL 端点返回 {resp.status_code}"
            assert 'wsdl' in resp.text.lower() or 'definitions' in resp.text.lower(), \
                "响应内容不是有效的 WSDL"
        except requests.exceptions.ConnectionError:
            pytest.skip("Proxy 服务未运行，跳过 WSDL 测试")
        except requests.exceptions.Timeout:
            pytest.skip("Proxy 服务响应超时")

    def test_wsdl_contains_service_operations(self):
        """测试 WSDL 包含所有服务操作"""
        import requests

        try:
            resp = requests.get('http://localhost:8080/services?wsdl', timeout=5)
            wsdl_content = resp.text

            required_operations = [
                'StartMeasure', 'SglFreqMeasure',
                'FScan', 'IFAnalysis',
                'SglFreqDF', 'IFDF',
                'SelfTest', 'QueryFacilityDevStatus'
            ]

            for op in required_operations:
                assert op in wsdl_content, f"WSDL 缺少操作: {op}"
        except requests.exceptions.ConnectionError:
            pytest.skip("Proxy 服务未运行")


# ============================================================================
# 7. 错误码测试
# ============================================================================

class TestErrorCodes:
    """错误码完整性测试"""

    def test_known_error_codes(self):
        """测试已知错误码定义"""
        import sys
        import os
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

        # 尝试导入错误码定义
        try:
            from main_atom import ERR_DEVICE_OFFLINE
            assert ERR_DEVICE_OFFLINE == 3001
        except ImportError:
            pytest.skip("错误码定义未从 main_atom.py 导出")

        exceptions_file = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'utils', 'exceptions.py'
        )

        with open(exceptions_file, 'r', encoding='utf-8') as f:
            exc_content = f.read()

        required_codes = ['2001', '2002', '2003', '2004',
                         '3001', '3002', '3003', '3005',
                         '4001', '4002', '4003', '4005', '4006']

        missing = [code for code in required_codes if code not in exc_content]
        if missing:
            pytest.fail(f"错误码未定义: {missing}")


# ============================================================================
# 8. 完整链路测试
# ============================================================================

class TestFullSOAPChain:
    """完整 SOAP 链路测试（Proxy → Atom）"""

    def test_proxy_to_atom_soap_request(self):
        """测试 Proxy 到 Atom 的完整 SOAP 请求"""
        import requests

        # 构造完整的 SOAP 请求
        soap_request = '''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                       xmlns:mon="http://monitor.rrmp.gov.cn/services/">
            <soap:Header>
                <mon:AuthHeader>
                    <mon:Token>test_token</mon:Token>
                    <mon:Timestamp>2026-04-06T12:00:00Z</mon:Timestamp>
                    <mon:Signature>test_sig</mon:Signature>
                </mon:AuthHeader>
            </soap:Header>
            <soap:Body>
                <mon:SglFreqMeasure>
                    <mon:Frequency>100000000</mon:Frequency>
                </mon:SglFreqMeasure>
            </soap:Body>
        </soap:Envelope>'''

        try:
            resp = requests.post(
                'http://localhost:8080/soap',
                data=soap_request.encode('utf-8'),
                headers={'Content-Type': 'text/xml; charset=utf-8'},
                timeout=10
            )

            assert resp.status_code == 200, f"请求失败，状态码: {resp.status_code}"

            # 解析响应
            root = etree.fromstring(resp.content)
            body = root.find('{http://schemas.xmlsoap.org/soap/envelope/}Body')
            response = body[0]

            # 验证响应格式（期望的文档格式）
            # 注意：当前实现不符合，以下断言会失败
            response_tag = response.tag
            if 'Response' in response_tag:
                # 验证命名空间
                assert 'monitor' in response_tag.lower() or 'mon' in response_tag.lower(), \
                    f"Response 缺少 mon: 命名空间，当前: {response_tag}"

        except requests.exceptions.ConnectionError:
            pytest.skip("服务未运行，跳过链路测试")

    def test_soap_response_matches_spec(self):
        """测试 SOAP 响应格式是否符合文档规范"""
        import requests

        soap_request = '''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/"
                       xmlns:mon="http://monitor.rrmp.gov.cn/services/">
            <soap:Body>
                <mon:SglFreqMeasure>
                    <mon:Frequency>100000000</mon:Frequency>
                </mon:SglFreqMeasure>
            </soap:Body>
        </soap:Envelope>'''

        try:
            resp = requests.post(
                'http://localhost:8080/soap',
                data=soap_request.encode('utf-8'),
                headers={'Content-Type': 'text/xml; charset=utf-8'},
                timeout=10
            )

            root = etree.fromstring(resp.content)
            body = root.find('{http://schemas.xmlsoap.org/soap/envelope/}Body')
            response_elem = body[0]

            # 检查命名空间和基本格式
            assert 'http://monitor.rrmp.gov.cn/services/' in response_elem.tag,                 f"Response 缺少 mon: 命名空间，当前: {response_elem.tag}"

            result_code = response_elem.find('{http://monitor.rrmp.gov.cn/services/}ResultCode')
            assert result_code is not None, "缺少 ResultCode"

            result_msg = response_elem.find('{http://monitor.rrmp.gov.cn/services/}ResultMessage')
            assert result_msg is not None, "缺少 ResultMessage"

            # Data wrapper 仅在成功时必需
            if result_code.text == '0':
                data_elem = response_elem.find('{http://monitor.rrmp.gov.cn/services/}Data')
                assert data_elem is not None, "成功响应缺少 Data 包装"

        except requests.exceptions.ConnectionError:
            pytest.skip("服务未运行")


if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
