"""代理服务路由

处理SOAP请求，转发到原子服务
"""
import os
import requests
from flask import Blueprint, request, jsonify
from lxml import etree
from .soap_handler import SOAPHandler
from utils.logger import get_logger

logger = get_logger('proxy.routes')

proxy_bp = Blueprint('proxy', __name__)
soap_handler = SOAPHandler()

# 命名空间
SOAP_NS = 'http://schemas.xmlsoap.org/soap/envelope/'
MON_NS = 'http://monitor.rrmp.gov.cn/services/'
SRRC_NS = 'http://www.srrc.org.cn'

# 内部操作名到 Real Atom 端点名 的映射
# 注意: Real Atom 使用 gSOAP 框架，端点路径为 /B_XXX 格式（如 /B_SglFreqMeas）
# Real Atom 所有接口都使用根路径 "/" (2026-04-08 实测)
OPERATION_TO_REAL_ATOM = {
    # 查询接口
    'B_QueryDeviceInfo': '',              # 设备信息查询 - 根路径
    'B_QueryFaciDevStat': '',             # 设备状态查询 - 根路径

    # 控制接口
    'B_StopMeas': '',                     # 停止测量 - 根路径
    'B_TaskModification': '',             # 任务修改 - 根路径

    # 执行接口
    'StartMeasure': 'B_SglFreqMeas',      # 单频测量
    'B_SglFreqMeas': 'B_SglFreqMeas',    # 单频测量
    'B_SglFreqDF': 'B_SglFreqDF',        # 单频测向
    'StartScan': 'B_FScan',               # 频段扫描
    'B_FScan': 'B_FScan',                 # 频段扫描
    'B_FScanDF': 'B_FScanDF',            # 频段扫描测向
    'B_MScan': 'B_MScan',                 # 多信道扫描
    'B_MScanDF': 'B_MScanDF',            # 多信道扫描测向
    'B_PScan': 'B_PScan',                 # 频谱扫描
    'B_WBDF': 'B_WBDF',                  # 宽带测向

    # 兼容旧名称
    'StartDirection': 'B_SglFreqDF',       # 单频测向
    'StartIFAnalysis': 'B_IFAnalysis',     # 中频分析
    'StartIFDirection': 'B_IFDirection',   # 中频测向
}


def is_real_atom() -> bool:
    """检测是否连接到 Real Atom"""
    return os.environ.get('PROXY_MODE') == 'B'


def get_atom_base_url() -> str:
    """获取原子服务基础URL

    通过环境变量 PROXY_MODE 检测运行模式:
    - 'B': 使用 settings_proxy_b (Proxy-B 模式，连接 Real Atom)
    - 其他: 使用 settings (默认，连接 Mock Atom)

    在 main_proxy_b.py 启动前会设置 PROXY_MODE=B
    """
    if is_real_atom():
        try:
            from config import settings_proxy_b
            atom_config = settings_proxy_b.SERVICES.get('atom', {})
            host = atom_config.get('host', '127.0.0.1')
            port = atom_config.get('port', 9090)
            logger.info(f"使用 Proxy-B 配置: {host}:{port}")
            return f"http://{host}:{port}"
        except ImportError:
            logger.warning("无法导入 settings_proxy_b，回退到默认配置")

    # 默认从 settings 获取
    from config import settings
    atom_config = settings.SERVICES.get('atom', {})
    host = atom_config.get('host', '127.0.0.1')
    port = atom_config.get('port', 9090)
    return f"http://{host}:{port}"


def get_real_atom_endpoint(operation: str) -> str:
    """获取 Real Atom 的端点路径

    Args:
        operation: 内部操作名（如 StartMeasure）

    Returns:
        Real Atom 端点路径（如 B_SglFreqMeas）
    """
    return OPERATION_TO_REAL_ATOM.get(operation, operation)


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


def build_real_atom_request(operation: str, params: dict) -> str:
    """
    构建发送到 Real Atom 的 SOAP 请求（符合实测格式）

    Args:
        operation: SOAP操作名（如 B_SglFreqMeas）
        params: 参数字典

    Returns:
        SOAP XML字符串
    """
    from lxml import etree

    root = etree.Element(
        f'{{{SOAP_NS}}}Envelope',
        nsmap={'soapenv': SOAP_NS, 'srrc': SRRC_NS}
    )
    body = etree.SubElement(root, f'{{{SOAP_NS}}}Body')

    # 构建 requestbody
    request_body = etree.SubElement(body, f'{{{SRRC_NS}}}requestbody')

    # 设备ID (Real Atom 配置)
    etree.SubElement(request_body, f'{{{SRRC_NS}}}mfid').text = '53090001140012'
    etree.SubElement(request_body, f'{{{SRRC_NS}}}equid').text = '51cd8dfe-e543-40c9-bdc3-a292766fee7f'

    # 根据操作类型处理 equpara 和其他字段
    # 查询接口和停止接口：equpara 使用 xsi:nil="true"
    if operation in ('B_QueryDeviceInfo', 'B_QueryFaciDevStat'):
        # equpara 空
        equpara = etree.SubElement(request_body, f'{{{SRRC_NS}}}equpara')
        equpara.set('{http://www.w3.org/2001/XMLSchema-instance}nil', 'true')

    elif operation == 'B_StopMeas':
        # 停止测量：equpara 空 + taskid
        equpara = etree.SubElement(request_body, f'{{{SRRC_NS}}}equpara')
        equpara.set('{http://www.w3.org/2001/XMLSchema-instance}nil', 'true')
        taskid = params.get('taskid', '')
        etree.SubElement(request_body, f'{{{SRRC_NS}}}taskid').text = taskid

    elif operation == 'B_TaskModification':
        # 任务修改：equpara 空
        equpara = etree.SubElement(request_body, f'{{{SRRC_NS}}}equpara')
        equpara.set('{http://www.w3.org/2001/XMLSchema-instance}nil', 'true')

    elif operation in ('B_SglFreqMeas', 'B_SglFreqDF', 'B_WBDF'):
        # 单频测量/单频测向/宽带测向：使用 items 结构
        equpara = etree.SubElement(request_body, f'{{{SRRC_NS}}}equpara')
        item_list = etree.SubElement(equpara, f'{{{SRRC_NS}}}items')

        if operation == 'B_SglFreqMeas':
            frequency = int(params.get('frequency', 100_000_000))
            add_equpara_item(item_list, 'frequency', frequency)
            add_equpara_item(item_list, 'ifbw', 40000000)
            add_equpara_item(item_list, 'gain', 'AGC')
            add_equpara_item(item_list, 'rfworkmode', '0')
            add_equpara_item(item_list, 'audiotype', 'off')
            add_equpara_item(item_list, 'demodmode', 'FM')
            add_equpara_item(item_list, 'demodbw', 200000)
            add_equpara_item(item_list, 'spectrumswitch', 'on')
            add_equpara_item(item_list, 'ITUSwitch', 'on')

        elif operation == 'B_SglFreqDF':
            frequency = int(params.get('frequency', 100_000_000))
            add_equpara_item(item_list, 'frequency', frequency)
            add_equpara_item(item_list, 'dfmode', 1)
            add_equpara_item(item_list, 'ifbw', 40000000)
            add_equpara_item(item_list, 'gain', 'AGC')
            add_equpara_item(item_list, 'rfworkmode', '0')
            add_equpara_item(item_list, 'dftype', 0)
            add_equpara_item(item_list, 'spectrumswitch', 'on')

        elif operation == 'B_WBDF':
            frequency = int(params.get('frequency', 100_000_000))
            add_equpara_item(item_list, 'frequency', frequency)
            add_equpara_item(item_list, 'ifbw', 40000000)
            add_equpara_item(item_list, 'gain', 'AGC')
            add_equpara_item(item_list, 'rfworkmode', '0')

        # outputchannel (执行接口需要)
        outputchannel = etree.SubElement(request_body, f'{{{SRRC_NS}}}outputchannel')
        etree.SubElement(outputchannel, f'{{{SRRC_NS}}}mode').text = 'source'
        etree.SubElement(outputchannel, f'{{{SRRC_NS}}}datachannel').text = 'stream'

    elif operation in ('B_FScan', 'B_FScanDF', 'B_MScan', 'B_MScanDF'):
        # 频段扫描/频段扫描测向/多信道扫描：使用 groupitems 结构
        equpara = etree.SubElement(request_body, f'{{{SRRC_NS}}}equpara')
        groupitems = etree.SubElement(equpara, f'{{{SRRC_NS}}}groupitems')
        groupitem = etree.SubElement(groupitems, f'{{{SRRC_NS}}}groupitem')
        etree.SubElement(groupitem, f'{{{SRRC_NS}}}groupid').text = '1'
        group_item_list = etree.SubElement(groupitem, f'{{{SRRC_NS}}}items')

        if operation == 'B_FScan':
            start_freq = int(params.get('startfreq', 137_000_000))
            stop_freq = int(params.get('stopfreq', 173_000_000))
            add_equpara_item(group_item_list, 'startfreq', start_freq)
            add_equpara_item(group_item_list, 'stopfreq', stop_freq)
            add_equpara_item(group_item_list, 'step', 25000)
            add_equpara_item(group_item_list, 'gain', 'AGC')
            add_equpara_item(group_item_list, 'rfworkmode', '0')
            add_equpara_item(group_item_list, 'scanmode', 0)

        elif operation == 'B_FScanDF':
            start_freq = int(params.get('startfreq', 137_000_000))
            stop_freq = int(params.get('stopfreq', 173_000_000))
            add_equpara_item(group_item_list, 'startfreq', start_freq)
            add_equpara_item(group_item_list, 'stopfreq', stop_freq)
            add_equpara_item(group_item_list, 'step', 25000)
            add_equpara_item(group_item_list, 'rfworkmode', '0')
            add_equpara_item(group_item_list, 'gain', 'AGC')

        elif operation == 'B_MScan':
            frequency = int(params.get('frequency', 100_000_000))
            ifbw = int(params.get('ifbw', 40000000))
            add_equpara_item(group_item_list, 'frequency', frequency)
            add_equpara_item(group_item_list, 'ifbw', ifbw)
            add_equpara_item(group_item_list, 'gain', 'AGC')
            add_equpara_item(group_item_list, 'rfworkmode', '0')

        elif operation == 'B_MScanDF':
            frequency = int(params.get('frequency', 100_000_000))
            ifbw = int(params.get('ifbw', 40000000))
            add_equpara_item(group_item_list, 'frequency', frequency)
            add_equpara_item(group_item_list, 'dfmode', 1)
            add_equpara_item(group_item_list, 'ifbw', ifbw)
            add_equpara_item(group_item_list, 'gain', 'AGC')
            add_equpara_item(group_item_list, 'rfworkmode', '0')

        # outputchannel
        outputchannel = etree.SubElement(request_body, f'{{{SRRC_NS}}}outputchannel')
        etree.SubElement(outputchannel, f'{{{SRRC_NS}}}mode').text = 'source'
        etree.SubElement(outputchannel, f'{{{SRRC_NS}}}datachannel').text = 'stream'

    elif operation == 'B_PScan':
        # 频谱扫描：使用 items 结构
        equpara = etree.SubElement(request_body, f'{{{SRRC_NS}}}equpara')
        item_list = etree.SubElement(equpara, f'{{{SRRC_NS}}}items')
        start_freq = int(params.get('startfreq', 137_000_000))
        stop_freq = int(params.get('stopfreq', 173_000_000))
        add_equpara_item(item_list, 'startfreq', start_freq)
        add_equpara_item(item_list, 'stopfreq', stop_freq)
        add_equpara_item(item_list, 'step', 25000)
        add_equpara_item(item_list, 'gain', 'AGC')
        add_equpara_item(item_list, 'rfworkmode', '0')
        add_equpara_item(item_list, 'keepmode', 0)

        # outputchannel
        outputchannel = etree.SubElement(request_body, f'{{{SRRC_NS}}}outputchannel')
        etree.SubElement(outputchannel, f'{{{SRRC_NS}}}mode').text = 'source'
        etree.SubElement(outputchannel, f'{{{SRRC_NS}}}datachannel').text = 'stream'

    # 基础字段（所有接口都需要）
    etree.SubElement(request_body, f'{{{SRRC_NS}}}appid').text = '123456'
    etree.SubElement(request_body, f'{{{SRRC_NS}}}userid').text = 'RX_admin'
    etree.SubElement(request_body, f'{{{SRRC_NS}}}priority').text = '9'
    etree.SubElement(request_body, f'{{{SRRC_NS}}}executetime').text = '0'

    return etree.tostring(root, pretty_print=True, encoding='utf-8', xml_declaration=True).decode('utf-8')


def add_equpara_item(parent: etree._Element, paraname: str, paravalue) -> None:
    """向 equpara.items 添加一个参数项"""
    item = etree.SubElement(parent, f'{{{SRRC_NS}}}item')
    etree.SubElement(item, f'{{{SRRC_NS}}}paraname').text = paraname
    etree.SubElement(item, f'{{{SRRC_NS}}}paravalue').text = str(paravalue)


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


def parse_soap_response_from_atom(xml_response: str, is_real: bool = False) -> dict:
    """
    解析从原子服务返回的SOAP响应

    Args:
        xml_response: SOAP XML响应字符串
        is_real: 是否为 Real Atom 的响应（默认 False）

    Returns:
        解析后的数据字典
    """
    from lxml import etree

    try:
        root = etree.fromstring(xml_response.encode('utf-8'))
    except etree.XMLSyntaxError as e:
        raise Exception(f"SOAP响应解析失败: {e}")

    # 提取Body内容
    body = root.find(f'{{{SOAP_NS}}}Body')
    if body is None:
        raise Exception("未找到SOAP Body")

    if is_real:
        # Real Atom 响应格式
        return _parse_real_atom_response(body)
    else:
        # Mock Atom 响应格式
        return _parse_mock_atom_response(body)


def _parse_real_atom_response(body) -> dict:
    """解析 Real Atom 的响应格式

    Real Atom 响应结构:
    <soapenv:Body>
        <srrc:responsebody>
            <srrc:error>...</srrc:error>
            或
            <srrc:result>
                <srrc:frequency>...</srrc:frequency>
                ...
            </srrc:result>
        </srrc:responsebody>
    </soapenv:Body>

    可能的 Header 中还有 bizResCd 信息
    """
    result = {}

    # 查找 responsebody
    responsebody = body.find(f'{{{SRRC_NS}}}responsebody')
    if responsebody is None:
        # 尝试其他命名空间
        for child in body:
            if 'responsebody' in child.tag.lower():
                responsebody = child
                break

    if responsebody is None:
        return {'success': False, 'error': '未找到 responsebody'}

    # 检查是否有错误
    error = responsebody.find(f'{{{SRRC_NS}}}error')
    if error is not None:
        error_code = error.find(f'{{{SRRC_NS}}}code')
        error_text = error.find(f'{{{SRRC_NS}}}text')
        result['success'] = False
        result['error_code'] = error_code.text if error_code is not None else None
        result['error'] = error_text.text if error_text is not None else 'Unknown error'
        return result

    # 解析 result 数据
    result_elem = responsebody.find(f'{{{SRRC_NS}}}result')
    if result_elem is not None:
        _extract_fields_from_element(result_elem, result)

    # 检查 Header 中的 bizResCd
    envelope = body.getparent().getparent()  # envelope -> body 的父级
    header = envelope.find(f'{{{SOAP_NS}}}Header') if envelope is not None else None
    if header is not None:
        provider_response = header.find(f'{{{SRRC_NS}}}ProviderResponse')
        if provider_response is not None:
            biz_res_cd = provider_response.find(f'{{{SRRC_NS}}}bizResCd')
            biz_res_text = provider_response.find(f'{{{SRRC_NS}}}bizResText')
            if biz_res_cd is not None:
                result['bizResCd'] = biz_res_cd.text
                # BIZ-000001 表示成功
                result['success'] = biz_res_cd.text == 'BIZ-000001'
            if biz_res_text is not None:
                result['bizResText'] = biz_res_text.text

    return result


def _parse_mock_atom_response(body) -> dict:
    """解析 Mock Atom 的响应格式"""
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
    _extract_fields_from_element(response, result)

    result['success'] = success
    return result


def _extract_fields_from_element(element, result: dict) -> None:
    """从 XML 元素中提取字段到结果字典"""
    numeric_fields = {
        'Frequency', 'StartFreq', 'EndFreq', 'Span', 'IFBW',
        'Bandwidth', 'Step', 'Amplitude', 'SignalLevel', 'Azimuth',
        'Elevation', 'Level', 'Quality', 'PointCount', 'NArrays',
        'frequency', 'startfreq', 'stopfreq', 'signalStrength'
    }

    for child in element:
        tag_name = child.tag.split('}')[1] if '}' in child.tag else child.tag

        # 跳过特定标签
        if tag_name in ('Error', 'error', 'result', 'responsebody'):
            continue

        try:
            if child.text:
                if tag_name in numeric_fields:
                    result[tag_name] = int(child.text) if '.' not in child.text else float(child.text)
                else:
                    try:
                        result[tag_name] = float(child.text)
                    except (ValueError, TypeError):
                        result[tag_name] = child.text
            else:
                result[tag_name] = None
        except Exception:
            result[tag_name] = child.text


def dispatch_to_atom_service(operation: str, params: dict) -> dict:
    """
    将SOAP操作分发到原子服务（使用SOAP/XML协议）

    注意：统一使用 Real Atom 格式构建请求，与目标无关
    - Proxy-A → Mock Atom: 使用 Real Atom 格式请求
    - Proxy-B → Real Atom: 使用 Real Atom 格式请求

    Args:
        operation: SOAP操作名
        params: 参数字典

    Returns:
        原子服务返回的结果
    """
    try:
        atom_base_url = get_atom_base_url()

        # 统一使用 Real Atom 格式构建请求
        soap_request = build_real_atom_request(operation, params)

        # 根据目标决定 URL 端点
        if is_real_atom():
            # Real Atom 端点
            endpoint = get_real_atom_endpoint(operation)
            url = atom_base_url if not endpoint else f"{atom_base_url}/{endpoint}"
            logger.info(f"发送请求到 Real Atom: {operation} -> {endpoint or '/'}")
        else:
            # Mock Atom 端点（/services）
            endpoint = get_real_atom_endpoint(operation)
            # Mock Atom 也支持 Real Atom 格式的请求
            url = f"{atom_base_url}/services"
            logger.info(f"发送请求到 Mock Atom (Real Atom格式): {operation}")

        logger.debug(f"SOAP请求内容:\n{soap_request}")

        # 发送 SOAP 请求
        response = requests.post(
            url,
            data=soap_request,
            headers={'Content-Type': 'text/xml; charset=utf-8'},
            timeout=30
        )

        logger.info(f"收到原子服务响应: HTTP {response.status_code}")

        # 解析响应（统一按 Real Atom 格式解析）
        result = parse_soap_response_from_atom(response.text, is_real=True)

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
        atom_base_url = get_atom_base_url()
        response = requests.get(f"{atom_base_url}/health", timeout=5)
        return jsonify(response.json()), response.status_code
    except requests.RequestException as e:
        return jsonify({
            'status': 'error',
            'message': f'原子服务不可达: {str(e)}'
        }), 503


@proxy_bp.route('/debug/config', methods=['GET'])
def debug_config():
    """调试端点：查看当前配置"""
    import os
    from config import settings, settings_proxy_b

    proxy_mode = os.environ.get('PROXY_MODE', 'NOT_SET')

    # 获取当前生效的 atom 配置
    atom_base_url = get_atom_base_url()

    return jsonify({
        'proxy_mode': proxy_mode,
        'atom_base_url': atom_base_url,
        'settings_services': settings.SERVICES.get('atom', {}),
        'settings_proxy_b_services': settings_proxy_b.SERVICES.get('atom', {})
    }), 200
