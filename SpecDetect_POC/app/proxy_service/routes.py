"""代理服务路由

处理SOAP请求，转发到原子服务
"""
import requests
from flask import Blueprint, request, jsonify
from .soap_handler import SOAPHandler
from config.settings import SERVICES
from utils.logger import get_logger

logger = get_logger('proxy.routes')

proxy_bp = Blueprint('proxy', __name__)
soap_handler = SOAPHandler()

# 原子服务地址
ATOM_SERVICE_URL = SERVICES['atom']
ATOM_BASE_URL = f"http://{ATOM_SERVICE_URL['host']}:{ATOM_SERVICE_URL['port']}"


@proxy_bp.route('/soap', methods=['POST'])
def handle_soap():
    """处理SOAP请求

    支持的操作:
    - StartMeasure: 开始单频测量
    - StartScan: 开始频段扫描
    - StartDirection: 开始测向
    """
    xml_data = request.data.decode('utf-8')
    logger.info(f"收到SOAP请求")

    try:
        parsed = soap_handler.parse_request(xml_data)
        operation = parsed['operation']
        params = parsed['params']

        logger.info(f"SOAP操作: {operation}, 参数: {params}")

        # 根据操作类型调用原子服务
        result = dispatch_to_atom_service(operation, params)

        # 构建SOAP响应
        soap_response = soap_handler.build_response(
            success=result.get('success', True),
            data=result
        )

        return soap_response, 200, {'Content-Type': 'text/xml; charset=utf-8'}

    except Exception as e:
        logger.error(f"处理SOAP请求失败: {e}")
        soap_response = soap_handler.build_response(success=False, error=str(e))
        return soap_response, 500, {'Content-Type': 'text/xml; charset=utf-8'}


def build_soap_request_to_atom(operation: str, params: dict) -> str:
    """
    构建发送到原子服务的SOAP请求

    Args:
        operation: SOAP操作名
        params: 参数字典

    Returns:
        SOAP XML字符串
    """
    from lxml import etree

    # SOAP命名空间
    SOAP_NS = 'http://schemas.xmlsoap.org/soap/envelope/'
    MON_NS = 'http://monitor.rrmp.gov.cn/services/'

    root = etree.Element(
        f'{{{SOAP_NS}}}Envelope',
        nsmap={'soap': SOAP_NS, 'mon': MON_NS}
    )
    body = etree.SubElement(root, f'{{{SOAP_NS}}}Body')

    # 根据操作类型构建不同的请求体
    if operation == 'StartMeasure' or operation.endswith('StartMeasure'):
        # 单频测量
        frequency = int(params.get('Frequency', params.get('frequency', 100_000_000)))
        bandwidth = int(params.get('Bandwidth', params.get('bandwidth', 120000)))

        req = etree.SubElement(body, f'{{{MON_NS}}}StartMeasure')
        freq_elem = etree.SubElement(req, f'{{{MON_NS}}}Frequency')
        freq_elem.text = str(frequency)
        bw_elem = etree.SubElement(req, f'{{{MON_NS}}}Bandwidth')
        bw_elem.text = str(bandwidth)

    elif operation == 'StartScan' or operation.endswith('StartScan'):
        # 频段扫描
        start_freq = int(params.get('StartFreq', params.get('StartFreq', 100_000_000)))
        end_freq = int(params.get('EndFreq', params.get('EndFreq', 200_000_000)))
        step = int(params.get('Step', params.get('Step', 1_000_000)))

        req = etree.SubElement(body, f'{{{MON_NS}}}StartScan')
        sf_elem = etree.SubElement(req, f'{{{MON_NS}}}StartFreq')
        sf_elem.text = str(start_freq)
        ef_elem = etree.SubElement(req, f'{{{MON_NS}}}EndFreq')
        ef_elem.text = str(end_freq)
        step_elem = etree.SubElement(req, f'{{{MON_NS}}}Step')
        step_elem.text = str(step)

    elif operation == 'StartDirection' or operation.endswith('StartDirection'):
        # 单频测向
        frequency = int(params.get('Frequency', params.get('frequency', 100_000_000)))
        bandwidth = int(params.get('Bandwidth', params.get('bandwidth', 120000)))

        req = etree.SubElement(body, f'{{{MON_NS}}}StartDirection')
        freq_elem = etree.SubElement(req, f'{{{MON_NS}}}Frequency')
        freq_elem.text = str(frequency)
        bw_elem = etree.SubElement(req, f'{{{MON_NS}}}Bandwidth')
        bw_elem.text = str(bandwidth)

    elif operation == 'StartIFAnalysis' or operation.endswith('StartIFAnalysis'):
        # 中频分析
        frequency = int(params.get('Frequency', params.get('frequency', 100_000_000)))
        span = int(params.get('Span', params.get('span', 1_000_000)))
        ifbw = int(params.get('IFBW', params.get('ifbw', 100000)))

        req = etree.SubElement(body, f'{{{MON_NS}}}StartIFAnalysis')
        freq_elem = etree.SubElement(req, f'{{{MON_NS}}}Frequency')
        freq_elem.text = str(frequency)
        span_elem = etree.SubElement(req, f'{{{MON_NS}}}Span')
        span_elem.text = str(span)
        ifbw_elem = etree.SubElement(req, f'{{{MON_NS}}}IFBW')
        ifbw_elem.text = str(ifbw)

    elif operation == 'StartIFDirection' or operation.endswith('StartIFDirection'):
        # 中频测向
        frequency = int(params.get('Frequency', params.get('frequency', 100_000_000)))
        span = int(params.get('Span', params.get('span', 1_000_000)))
        ifbw = int(params.get('IFBW', params.get('ifbw', 100000)))

        req = etree.SubElement(body, f'{{{MON_NS}}}StartIFDirection')
        freq_elem = etree.SubElement(req, f'{{{MON_NS}}}Frequency')
        freq_elem.text = str(frequency)
        span_elem = etree.SubElement(req, f'{{{MON_NS}}}Span')
        span_elem.text = str(span)
        ifbw_elem = etree.SubElement(req, f'{{{MON_NS}}}IFBW')
        ifbw_elem.text = str(ifbw)

    elif operation == 'Connect' or operation.endswith('Connect'):
        # 连接设备
        req = etree.SubElement(body, f'{{{MON_NS}}}Connect')

    elif operation == 'Disconnect' or operation.endswith('Disconnect'):
        # 断开设备
        req = etree.SubElement(body, f'{{{MON_NS}}}Disconnect')

    else:
        # 未知操作，发送原始参数
        req = etree.SubElement(body, f'{{{MON_NS}}}{operation}')
        for key, value in params.items():
            child = etree.SubElement(req, f'{{{MON_NS}}}{key}')
            child.text = str(value)

    return etree.tostring(root, pretty_print=True, encoding='utf-8', xml_declaration=True).decode('utf-8')


def parse_soap_response_from_atom(xml_response: str) -> dict:
    """
    解析从原子服务返回的SOAP响应

    Args:
        xml_response: SOAP XML响应字符串

    Returns:
        解析后的数据字典
    """
    from lxml import etree

    SOAP_NS = 'http://schemas.xmlsoap.org/soap/envelope/'
    MON_NS = 'http://monitor.rrmp.gov.cn/services/'

    try:
        root = etree.fromstring(xml_response.encode('utf-8'))
    except etree.XMLSyntaxError as e:
        raise Exception(f"SOAP响应解析失败: {e}")

    # 提取Body内容
    body = root.find(f'{{{SOAP_NS}}}Body')
    if body is None:
        raise Exception("未找到SOAP Body")

    # 获取Response元素
    response = body.find(f'{{{MON_NS}}}Response')
    if response is None:
        # 尝试查找任意Response元素
        for child in body:
            if child.tag.endswith('}Response') or child.tag == 'Response':
                response = child
                break
        else:
            raise Exception("未找到Response元素")

    # 检查success属性
    success = response.get('success', 'true').lower() == 'true'

    result = {}
    for child in response:
        tag_name = child.tag.split('}')[1] if '}' in child.tag else child.tag
        # 跳过Error元素
        if tag_name == 'Error':
            continue
        # 尝试转换数值
        try:
            if child.text:
                if tag_name in ('Frequency', 'StartFreq', 'EndFreq', 'Span', 'IFBW',
                               'Bandwidth', 'Step', 'Amplitude', 'SignalLevel', 'Azimuth',
                               'Elevation', 'Level', 'Quality', 'PointCount', 'NArrays'):
                    result[tag_name] = int(child.text) if '.' not in child.text else float(child.text)
                elif tag_name in ('Success', 'ResultCode'):
                    result[tag_name] = child.text
                else:
                    # 尝试作为数值或保留原值
                    try:
                        result[tag_name] = float(child.text)
                    except (ValueError, TypeError):
                        result[tag_name] = child.text
            else:
                result[tag_name] = None
        except Exception:
            result[tag_name] = child.text

    result['success'] = success
    return result


def dispatch_to_atom_service(operation: str, params: dict) -> dict:
    """
    将SOAP操作分发到原子服务（使用SOAP/XML协议）

    Args:
        operation: SOAP操作名
        params: 参数字典

    Returns:
        原子服务返回的结果
    """
    try:
        # 构建发送到原子服务的SOAP请求
        soap_request = build_soap_request_to_atom(operation, params)

        logger.info(f"发送SOAP请求到原子服务: {operation}")
        logger.debug(f"SOAP请求内容:\n{soap_request}")

        # 发送SOAP请求到原子服务的 /services 端点
        response = requests.post(
            f"{ATOM_BASE_URL}/services",
            data=soap_request,
            headers={'Content-Type': 'text/xml; charset=utf-8'},
            timeout=30
        )

        logger.info(f"收到原子服务响应: HTTP {response.status_code}")

        # 解析SOAP响应
        result = parse_soap_response_from_atom(response.text)

        logger.info(f"解析结果: success={result.get('success')}")

        return result

    except requests.RequestException as e:
        logger.error(f"调用原子服务失败: {e}")
        return {
            'success': False,
            'error': f'原子服务调用失败: {str(e)}'
        }
    except Exception as e:
        logger.error(f"分发请求失败: {e}")
        return {
            'success': False,
            'error': str(e)
        }


@proxy_bp.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({'status': 'ok', 'service': 'proxy'}), 200


@proxy_bp.route('/atom/health', methods=['GET'])
def atom_health_check():
    """检查原子服务健康状态"""
    try:
        response = requests.get(f"{ATOM_BASE_URL}/health", timeout=5)
        return jsonify(response.json()), response.status_code
    except requests.RequestException as e:
        return jsonify({
            'status': 'error',
            'message': f'原子服务不可达: {str(e)}'
        }), 503
