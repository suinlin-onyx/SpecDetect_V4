"""代理服务测试"""
import pytest
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.proxy_service.soap_handler import SOAPHandler
from utils.exceptions import SOAPParseError


class TestSOAPHandler:
    """SOAP处理器测试"""

    def setup_method(self):
        self.handler = SOAPHandler()

    def test_parse_simple_request(self):
        """测试解析简单SOAP请求"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Body>
                <StartMeasure>
                    <Frequency>100000000</Frequency>
                    <Bandwidth>120000</Bandwidth>
                </StartMeasure>
            </soap:Body>
        </soap:Envelope>'''

        result = self.handler.parse_request(xml)

        assert result['operation'] == 'StartMeasure'
        assert result['params']['Frequency'] == '100000000'
        assert result['params']['Bandwidth'] == '120000'

    def test_build_response(self):
        """测试构建SOAP响应（符合文档规范）"""
        response = self.handler.build_response(
            success=True,
            data={'Result': 'OK', 'TaskID': '001'}
        )

        assert 'soap:Envelope' in response
        assert 'mon:Response' in response or 'http://monitor.rrmp.gov.cn/services/' in response
        assert 'ResultCode>0</mon:ResultCode>' in response or 'ResultCode>0<' in response
        assert 'ResultMessage>Success</mon:ResultMessage>' in response or 'ResultMessage>Success<' in response

    def test_build_error_response(self):
        """测试构建错误响应（SOAP Fault 格式）"""
        response = self.handler.build_response(
            success=False,
            error='Invalid frequency',
            error_code=4001
        )

        assert 'soap:Envelope' in response
        assert 'soap:Fault' in response
        assert 'faultcode>soap:Server' in response
        assert 'Invalid frequency' in response
        # ErrorCode 在 SOAP Fault detail 中，命名空间前缀可能是 ns0 或 mon
        assert 'ErrorCode' in response and '4001' in response

    def test_parse_invalid_xml(self):
        """测试解析无效XML"""
        with pytest.raises(SOAPParseError):
            self.handler.parse_request('not xml')

    def test_parse_empty_body(self):
        """测试解析空Body"""
        xml = '''<?xml version="1.0" encoding="UTF-8"?>
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Body/>
        </soap:Envelope>'''

        with pytest.raises(SOAPParseError):
            self.handler.parse_request(xml)
