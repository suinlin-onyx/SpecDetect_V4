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
                       error: Optional[str] = None, error_code: Optional[int] = None) -> str:
        """
        构建SOAP响应（Real Atom格式）

        Args:
            success: 是否成功
            data: 响应数据
            error: 错误信息
            error_code: 错误码

        Returns:
            SOAP XML字符串
        """
        # 错误时使用 SOAP Fault 格式
        if not success:
            return self.build_fault(
                faultstring=error or 'Error',
                error_code=error_code or 1,
                error_message=error or 'Error'
            )

        # SOAP 信封
        root = etree.Element(
            '{http://schemas.xmlsoap.org/soap/envelope/}Envelope',
            nsmap=self.SOAP_NS
        )

        # SOAP Header with bizResCd
        header = etree.SubElement(root, '{http://schemas.xmlsoap.org/soap/envelope/}Header')
        SRRC_NS = 'http://www.srrc.org.cn'
        provider_response = etree.SubElement(header, f'{{{SRRC_NS}}}ProviderResponse')
        biz_res_cd = etree.SubElement(provider_response, f'{{{SRRC_NS}}}bizResCd')
        biz_res_cd.text = 'BIZ-000001' if success else 'BIZ-000002'
        biz_res_text = etree.SubElement(provider_response, f'{{{SRRC_NS}}}bizResText')
        biz_res_text.text = '调用成功' if success else str(error)

        # SOAP Body
        body = etree.SubElement(root, '{http://schemas.xmlsoap.org/soap/envelope/}Body')

        # srrc:responsebody
        SRRC_NS = 'http://www.srrc.org.cn'
        response_body = etree.SubElement(body, f'{{{SRRC_NS}}}responsebody')

        if data:
            result = etree.SubElement(response_body, f'{{{SRRC_NS}}}result')
            for key, value in data.items():
                if isinstance(value, dict):
                    item = etree.SubElement(result, f'{{{SRRC_NS}}}{key}')
                    for k, v in value.items():
                        child = etree.SubElement(item, f'{{{SRRC_NS}}}{k}')
                        if isinstance(v, list):
                            child.text = str(v)
                        else:
                            child.text = str(v) if v is not None else ''
                elif isinstance(value, list):
                    item = etree.SubElement(result, f'{{{SRRC_NS}}}{key}')
                    item.text = str(value)
                else:
                    child = etree.SubElement(result, f'{{{SRRC_NS}}}{key}')
                    child.text = str(value) if value is not None else ''

        return etree.tostring(root, pretty_print=True, encoding='utf-8').decode('utf-8')

    def build_fault(self, faultstring: str = 'Service error',
                    error_code: Optional[int] = None,
                    error_message: Optional[str] = None,
                    error_code_name: Optional[str] = None,
                    device_id: Optional[str] = None) -> str:
        """
        构建SOAP Fault错误响应（符合文档规范）

        文档示例（05_API_接口文档.md 第139-157行, 第805-823行）:
        <soap:Envelope xmlns:soap="http://schemas.xmlsoap.org/soap/envelope/">
            <soap:Body>
                <soap:Fault>
                    <faultcode>soap:Server</faultcode>
                    <faultstring>Service error message</faultstring>
                    <detail>
                        <mon:ErrorDetail xmlns:mon="http://monitor.rrmp.gov.cn/services/">
                            <mon:ErrorCode>ERR_001</mon:ErrorCode>
                            <mon:ErrorMessage>设备连接失败</mon:ErrorMessage>
                        </mon:ErrorDetail>
                    </detail>
                </soap:Fault>
            </soap:Body>
        </soap:Envelope>

        Args:
            faultstring: SOAP Fault 错误描述
            error_code: 错误码（数字）
            error_message: 详细错误信息
            error_code_name: 错误码名称（如 ERR_DEVICE_OFFLINE）
            device_id: 设备ID

        Returns:
            SOAP XML字符串
        """
        MON_NS = 'http://monitor.rrmp.gov.cn/services/'

        root = etree.Element(
            '{http://schemas.xmlsoap.org/soap/envelope/}Envelope',
            nsmap=self.SOAP_NS
        )

        body = etree.SubElement(root, '{http://schemas.xmlsoap.org/soap/envelope/}Body')

        fault = etree.SubElement(body, '{http://schemas.xmlsoap.org/soap/envelope/}Fault')

        # faultcode
        faultcode = etree.SubElement(fault, 'faultcode')
        faultcode.text = 'soap:Server'

        # faultstring
        fs = etree.SubElement(fault, 'faultstring')
        fs.text = faultstring

        # detail
        detail = etree.SubElement(fault, 'detail')

        # mon:ErrorDetail
        error_detail = etree.SubElement(detail, f'{{{MON_NS}}}ErrorDetail')

        # mon:ErrorCode
        if error_code is not None:
            ec = etree.SubElement(error_detail, f'{{{MON_NS}}}ErrorCode')
            ec.text = str(error_code)

        # mon:ErrorCodeName
        if error_code_name is not None:
            ecn = etree.SubElement(error_detail, f'{{{MON_NS}}}ErrorCodeName')
            ecn.text = error_code_name

        # mon:ErrorMessage
        if error_message is not None:
            em = etree.SubElement(error_detail, f'{{{MON_NS}}}ErrorMessage')
            em.text = error_message

        # mon:DeviceID
        if device_id is not None:
            did = etree.SubElement(error_detail, f'{{{MON_NS}}}DeviceID')
            did.text = device_id

        return etree.tostring(root, pretty_print=True, encoding='utf-8').decode('utf-8')
