"""SOAP消息处理器"""
from typing import Optional, Dict, Any
from lxml import etree
from utils.exceptions import SOAPParseError
from utils.logger import get_logger

logger = get_logger('proxy.soap')


class SOAPHandler:
    """SOAP消息处理器"""

    SOAP_NS = {
        'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
        'xsd': 'http://www.w3.org/2001/XMLSchema',
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
    }

    def __init__(self):
        pass

    def parse_request(self, xml_data: str) -> Dict[str, Any]:
        """
        解析SOAP请求

        Args:
            xml_data: SOAP XML字符串

        Returns:
            解析后的请求数据字典
        """
        try:
            root = etree.fromstring(xml_data.encode('utf-8'))
        except etree.XMLSyntaxError as e:
            raise SOAPParseError(f"SOAP XML解析失败: {e}")

        # 提取Body内容
        body = root.find('soap:Body', namespaces=self.SOAP_NS)
        if body is None:
            raise SOAPParseError("未找到SOAP Body")

        # 获取第一个子元素作为操作
        if len(body) == 0:
            raise SOAPParseError("SOAP Body为空")

        operation = body[0]
        result = {
            'operation': operation.tag,
            'namespace': operation.tag.split('}')[0] if '}' in operation.tag else '',
            'params': {}
        }

        # 提取参数
        for child in operation:
            tag_name = child.tag.split('}')[1] if '}' in child.tag else child.tag
            result['params'][tag_name] = child.text

        logger.info(f"解析SOAP请求: {result['operation']}")
        return result

    def build_response(self, success: bool = True, data: Optional[Dict] = None,
                       error: Optional[str] = None) -> str:
        """
        构建SOAP响应

        Args:
            success: 是否成功
            data: 响应数据
            error: 错误信息

        Returns:
            SOAP XML字符串
        """
        root = etree.Element(
            '{http://schemas.xmlsoap.org/soap/envelope/}Envelope',
            nsmap=self.SOAP_NS
        )

        body = etree.SubElement(root, '{http://schemas.xmlsoap.org/soap/envelope/}Body')

        response = etree.SubElement(body, 'Response')
        response.set('success', 'true' if success else 'false')

        if success and data:
            for key, value in data.items():
                child = etree.SubElement(response, key)
                child.text = str(value)
        elif not success and error:
            child = etree.SubElement(response, 'Error')
            child.text = error

        return etree.tostring(root, pretty_print=True, encoding='utf-8').decode('utf-8')
