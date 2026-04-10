"""原子服务入口

提供HTTP接口，调用设备执行监测和测向任务
"""
import sys
import os
import asyncio
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from functools import partial

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from flask import Flask, jsonify, request
from flask_cors import CORS
from lxml import etree

from app.atom_service.device_client import DeviceClient
from app.atom_service.protocol_builder import RMCPTPBuilder
from app.atom_service.services.monitor import MonitorService
from app.atom_service.services.direction import DirectionService
from app.atom_service.services.device import DeviceService
from config.settings import SERVICES
from utils.logger import setup_logger
from utils.protocol_hook import HookManager, bytes_to_hex

# 创建日志记录器
logger = setup_logger('atom')

# 创建Flask应用
app = Flask(__name__)
CORS(app)

# 线程池用于执行异步代码
executor = ThreadPoolExecutor(max_workers=4)

# 全局设备客户端
_device_client: DeviceClient = None
_monitor_service: MonitorService = None
_direction_service: DirectionService = None
_device_service: DeviceService = None

# 全局连接状态管理
_device_connected: bool = False
_device_client: DeviceClient = None

# 请求锁：防止并发访问同一连接（使用线程锁，跨线程同步）
_request_lock = threading.Lock()
_background_loop: asyncio.AbstractEventLoop = None
_background_thread: threading.Thread = None


def _run_background_loop():
    """后台线程运行事件循环（使用SelectorEventLoop以兼容Windows）"""
    global _background_loop
    # Windows上需要使用SelectorEventLoop才能与run_coroutine_threadsafe配合
    _background_loop = asyncio.SelectorEventLoop()
    asyncio.set_event_loop(_background_loop)
    _background_loop.run_forever()


def get_async_loop() -> asyncio.AbstractEventLoop:
    """获取后台异步事件循环（单例）"""
    global _background_loop, _background_thread
    if _background_thread is None or not _background_thread.is_alive():
        _background_thread = threading.Thread(target=_run_background_loop, daemon=True)
        _background_thread.start()
        # 等待循环启动
        while _background_loop is None:
            time.sleep(0.01)
    return _background_loop


def run_async(coro):
    """运行异步代码（使用独立事件循环）

    注意：每次创建新事件循环是无奈之举，因为 asyncio 要求事件循环必须是线程本地的。
    为避免连接泄漏，必须在关闭前取消所有待处理的任务。
    """
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        # 先运行协程
        future = loop.run_until_complete(coro)
        # 确保所有待发送的数据都已发送
        loop.run_until_complete(asyncio.sleep(0.05))
        return future
    finally:
        # 取消所有待处理的任务，避免连接泄漏
        pending = asyncio.all_tasks(loop)
        for task in pending:
            task.cancel()
        # 等待取消完成
        if pending:
            loop.run_until_complete(asyncio.gather(*pending, return_exceptions=True))
        loop.close()


def get_device_client() -> DeviceClient:
    """每次创建新的设备客户端（短连接模式，避免多请求竞态）"""
    config = SERVICES['atom']
    return DeviceClient(
        host=config['device_host'],
        port=config['device_port'],
        timeout=config.get('timeout', 5.0)
    )


def get_connected_device_client() -> DeviceClient:
    """获取已连接的设备客户端（保持长连接）"""
    global _device_client
    return _device_client


def get_monitor_service() -> MonitorService:
    """每次创建新的监测服务（配合新的设备客户端）"""
    return MonitorService(get_device_client())


def get_direction_service() -> DirectionService:
    """每次创建新的测向服务"""
    return DirectionService(get_device_client())


def get_device_service() -> DeviceService:
    """每次创建新的设备服务"""
    return DeviceService(get_device_client())


@app.route('/health', methods=['GET'])
def health_check():
    """健康检查"""
    return jsonify({
        'status': 'ok',
        'service': 'atom',
        'device_connected': _device_connected
    }), 200


@app.route('/device/connect', methods=['POST'])
def connect_device():
    """连接设备"""
    global _device_client, _device_connected
    try:
        client = get_device_client()
        run_async(client.connect())
        _device_client = client  # 保存全局客户端引用
        _device_connected = True
        logger.info("设备连接成功")
        return jsonify({'success': True, 'message': '设备连接成功'}), 200
    except Exception as e:
        logger.error(f"设备连接失败: {e}")
        _device_connected = False
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/device/disconnect', methods=['POST'])
def disconnect_device():
    """断开设备"""
    global _device_client, _device_connected
    try:
        if _device_client:
            run_async(_device_client.disconnect())
            _device_client = None
        _device_connected = False
        logger.info("设备断开成功")
        return jsonify({'success': True, 'message': '设备断开成功'}), 200
    except Exception as e:
        logger.error(f"设备断开失败: {e}")
        _device_connected = False
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/device/status', methods=['GET'])
def get_device_status():
    """获取设备状态"""
    config = SERVICES['atom']
    return jsonify({
        'host': config['device_host'],
        'port': config['device_port'],
        'connected': _device_connected
    }), 200


# ==================== 监测服务接口 ====================

# 错误码定义 (按文档规范)
ERR_DEVICE_OFFLINE = 3001

def check_device_connected():
    """检查设备连接状态，未连接则返回错误响应"""
    if not _device_connected:
        return jsonify({
            'success': False,
            'error': 'ERR_DEVICE_OFFLINE',
            'error_code': ERR_DEVICE_OFFLINE,
            'message': '设备未连接，请先调用 /device/connect 连接设备'
        }), 503
    return None


@app.route('/monitor/sglfreq', methods=['POST'])
def start_sglfreq():
    """单频测量"""
    # 启动Hook上下文（始终记录）
    hook = HookManager.get_instance()
    hook.start_context()

    try:
        # ========== 后端验证：按文档规范 ==========
        error_resp = check_device_connected()
        if error_resp:
            hook.log_layer("atom", {"error": "设备未连接"})
            return error_resp
        # ==========================================

        data = request.get_json() or {}
        frequency = data.get('frequency', 100_000_000)
        bandwidth = data.get('bandwidth', 120000)
        antenna = data.get('antenna', 'default')

        # 记录Atom层参数
        hook.log_layer("atom", {
            "interface": "/monitor/sglfreq",
            "business_type": "0x10 (SGLFREQ)",
            "params": {"frequency": frequency, "bandwidth": bandwidth, "antenna": antenna}
        })

        async def do_sglfreq():
            # 每次请求创建独立的短连接
            client = get_device_client()
            await client.connect()
            try:
                builder = RMCPTPBuilder()
                frame = builder.build_sglfreq_command(frequency, antenna)

                # 记录发送帧
                hook.log_frame("send", "RMCPTP_CMD", bytes_to_hex(frame))

                header_info, payload, raw_frame = await client.send_and_receive(frame)

                # 记录接收帧
                hook.log_frame("recv", "RMCPTP_RESP", bytes_to_hex(raw_frame))

                # 简单解析响应 (跳过business_type字节)
                import struct
                result = {'frequency': frequency, 'bandwidth': bandwidth}
                if payload and len(payload) > 20:
                    # business_type(1) + header(11) + freq(8) = 20, itu_value在20-24
                    result['amplitude'] = struct.unpack('!f', payload[20:24])[0]
                return result
            finally:
                await client.disconnect()

        result = run_async(do_sglfreq())
        result['success'] = True

        # 记录响应数据
        hook.log_layer("atom", {"result": {k: v for k, v in result.items() if k != 'success'}})

        return jsonify(result), 200
    except Exception as e:
        logger.error(f"单频测量失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        hook.end_context()


@app.route('/monitor/fscan', methods=['POST'])
def start_fscan():
    """频段扫描"""
    # 启动Hook上下文（始终记录）
    hook = HookManager.get_instance()
    hook.start_context()

    try:
        # ========== 后端验证：按文档规范 ==========
        error_resp = check_device_connected()
        if error_resp:
            hook.log_layer("atom", {"error": "设备未连接"})
            return error_resp
        # ==========================================

        data = request.get_json() or {}
        start_freq = data.get('start_freq', 100_000_000)
        end_freq = data.get('end_freq', 200_000_000)
        step = data.get('step', 1_000_000)

        # 记录Atom层参数
        hook.log_layer("atom", {
            "interface": "/monitor/fscan",
            "business_type": "0x15 (FSCAN)",
            "params": {"start_freq": start_freq, "end_freq": end_freq, "step": step}
        })

        async def do_fscan():
            # 每次请求创建独立的短连接，避免连接状态问题
            client = get_device_client()
            await client.connect()
            try:
                service = MonitorService(client)
                return await service.start_fscan(start_freq, end_freq, step)
            finally:
                await client.disconnect()

        result = run_async(do_fscan())
        result['success'] = True

        # 记录响应数据
        hook.log_layer("atom", {"result_points": result.get('point_count', 0)})

        return jsonify(result), 200
    except Exception as e:
        logger.error(f"频段扫描失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        hook.end_context()


@app.route('/monitor/ifanalysis', methods=['POST'])
def start_ifanalysis():
    """中频分析"""
    # 启动Hook上下文（始终记录）
    hook = HookManager.get_instance()
    hook.start_context()

    try:
        # ========== 后端验证：按文档规范 ==========
        error_resp = check_device_connected()
        if error_resp:
            hook.log_layer("atom", {"error": "设备未连接"})
            return error_resp
        # ==========================================

        data = request.get_json() or {}
        frequency = data.get('frequency', 100_000_000)
        span = data.get('span', 1_000_000)
        ifbw = data.get('ifbw', 100000)

        # 记录Atom层参数
        hook.log_layer("atom", {
            "interface": "/monitor/ifanalysis",
            "business_type": "0x11 (IFANALYSIS)",
            "params": {"frequency": frequency, "span": span, "ifbw": ifbw}
        })

        async def do_ifanalysis():
            # 每次请求创建独立的短连接
            client = get_device_client()
            await client.connect()
            try:
                service = MonitorService(client)
                return await service.start_ifanalysis(frequency, span, ifbw)
            finally:
                await client.disconnect()

        result = run_async(do_ifanalysis())
        result['success'] = True

        # 记录响应数据
        hook.log_layer("atom", {"result_points": result.get('point_count', 0)})

        return jsonify(result), 200
    except Exception as e:
        logger.error(f"中频分析失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        hook.end_context()


@app.route('/monitor/realtime_spectrum', methods=['GET'])
def get_realtime_spectrum():
    """获取实时频谱数据（用于自动刷新）"""
    # 启动Hook上下文（始终记录）
    hook = HookManager.get_instance()
    hook.start_context()

    try:
        # ========== 后端验证：按文档规范 ==========
        error_resp = check_device_connected()
        if error_resp:
            hook.log_layer("atom", {"error": "设备未连接"})
            return error_resp
        # ==========================================

        data = request.args
        frequency = int(data.get('frequency', 100_000_000))
        span = int(data.get('span', 10_000_000))

        # 记录Atom层参数
        hook.log_layer("atom", {
            "interface": "/monitor/realtime_spectrum",
            "business_type": "0x15 (FSCAN)",
            "params": {"frequency": frequency, "span": span}
        })

        service = MonitorService(_device_client)
        result = run_async(service.start_fscan(
            start_freq=frequency - span // 2,
            end_freq=frequency + span // 2,
            step=max(100000, span // 100)
        ))

        # 记录响应数据
        hook.log_layer("atom", {"result_points": result.get('point_count', 0)})

        return jsonify(result), 200
    except Exception as e:
        logger.error(f"获取实时频谱失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        hook.end_context()


# ==================== SOAP接口 ====================

SOAP_NS = {
    'soap': 'http://schemas.xmlsoap.org/soap/envelope/',
    'mon': 'http://monitor.rrmp.gov.cn/services/',
    'srrc': 'http://www.srrc.org.cn'
}

# 设备基础信息（Real Atom 配置）
DEVICE_INFO = {
    'mfid': '53090001140012',
    'equid': '51cd8dfe-e543-40c9-bdc3-a292766fee7f',
    'equimanu': 'KYB',
    'equmodel': 'MS845',
    'equname': 'MS845',
    'equsn': '12345678',
    'equstatus': '01',
    'equtype': '01',
    'maxtasknumber': 1
}

# outputchannel 默认值（Mock Device）
DEFAULT_OUTPUTCHANNEL = {
    'host': '127.0.0.1',
    'port': '9000',
    'stc': ''  # 动态生成
}

# 设备配置文件路径
DEVICE_CONFIG_PATH = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    'device', 'config', 'devinfo'
)

# 设备配置缓存
_device_config_cache = {}


def load_device_config(mfid: str, equid: str) -> dict:
    """加载设备配置

    Args:
        mfid: 厂商ID
        equid: 设备ID

    Returns:
        设备配置字典，如果未找到返回空字典
    """
    cache_key = f"{mfid}_{equid}"

    if cache_key in _device_config_cache:
        return _device_config_cache[cache_key]

    config_file = os.path.join(DEVICE_CONFIG_PATH, f"{mfid}_{equid}.xml")

    if not os.path.exists(config_file):
        logger.warning(f"设备配置文件不存在: {config_file}")
        return {}

    try:
        tree = etree.parse(config_file)
        root = tree.getroot()

        # 提取配置数据
        config = {}

        # 解析 result 下的字段
        result = root.find('.//srrc:result', namespaces={'srrc': 'http://www.srrc.org.cn'})
        if result is None:
            result = root.find('.//{http://www.srrc.org.cn}result')

        if result is not None:
            for child in result:
                tag = child.tag.split('}')[1] if '}' in child.tag else child.tag
                if tag == 'featurelist':
                    # featurelist 需要特殊处理，保留原始元素
                    config['featurelist'] = child
                elif tag == 'host' or tag == 'port':
                    # 跳过空的主机和端口
                    if child.text:
                        config[tag] = child.text
                else:
                    config[tag] = child.text

        _device_config_cache[cache_key] = config
        logger.info(f"加载设备配置成功: {mfid}/{equid}")
        return config

    except Exception as e:
        logger.error(f"加载设备配置失败: {e}")
        return {}


def generate_taskid() -> str:
    """生成 Real Atom 格式的 taskid"""
    import uuid
    return str(uuid.uuid4()).upper()


def get_outputchannel_xml(mode: str = 'source', datachannel: str = 'stream') -> str:
    """生成 outputchannel XML"""
    import time
    stc = str(int(time.time()))
    return f'<srrc:outputchannel xmlns:srrc="http://www.srrc.org.cn"><srrc:mode>{mode}</srrc:mode><srrc:datachannel>{datachannel}</srrc:datachannel><srrc:host>{DEFAULT_OUTPUTCHANNEL["host"]}</srrc:host><srrc:port>{DEFAULT_OUTPUTCHANNEL["port"]}</srrc:port><srrc:stc>{stc}</srrc:stc></srrc:outputchannel>'


def build_soap_response(success: bool, data: dict = None, error: str = None, error_code: str = None) -> str:
    """构建SOAP响应（Real Atom格式）

    Args:
        success: 是否成功
        data: 响应数据字典
        error: 错误描述
        error_code: 错误码（如 BIZ-000002, BIZ-00002-conflict）
    """
    root = etree.Element(
        '{http://schemas.xmlsoap.org/soap/envelope/}Envelope',
        nsmap=SOAP_NS
    )

    # Header with bizResCd
    header = etree.SubElement(root, '{http://schemas.xmlsoap.org/soap/envelope/}Header')
    provider_response = etree.SubElement(header, '{http://www.srrc.org.cn}ProviderResponse')
    biz_res_cd = etree.SubElement(provider_response, '{http://www.srrc.org.cn}bizResCd')
    biz_res_text = etree.SubElement(provider_response, '{http://www.srrc.org.cn}bizResText')

    # Body
    body = etree.SubElement(root, '{http://schemas.xmlsoap.org/soap/envelope/}Body')
    response_body = etree.SubElement(body, '{http://www.srrc.org.cn}responsebody')

    if success and data:
        biz_res_cd.text = 'BIZ-000001'
        biz_res_text.text = '调用成功'
        _build_result_element(response_body, data)
    elif not success and error:
        biz_res_cd.text = error_code or 'BIZ-000002'
        biz_res_text.text = error
        error_elem = etree.SubElement(response_body, '{http://www.srrc.org.cn}error')
        error_type = etree.SubElement(error_elem, '{http://www.srrc.org.cn}type')
        error_type.text = 'cancel'
        error_code_elem = etree.SubElement(error_elem, '{http://www.srrc.org.cn}code')
        error_code_elem.text = error_code or 'BIZ-000002'
        error_text_elem = etree.SubElement(error_elem, '{http://www.srrc.org.cn}text')
        error_text_elem.text = error

    return etree.tostring(root, pretty_print=True, encoding='utf-8').decode('utf-8')


def _build_result_element(parent: etree._Element, data: dict) -> None:
    """构建result元素，支持复杂的嵌套结构"""
    result = etree.SubElement(parent, '{http://www.srrc.org.cn}result')

    for key, value in data.items():
        if value is None:
            continue

        if key == 'featurelist':
            # 特殊处理 featurelist：直接在 result 下构建 XML 结构
            _build_featurelist_into_result(result, value)
            continue

        if key in ('equpara', 'outputchannel') and isinstance(value, str) and value.startswith('<'):
            # 特殊处理 XML 字符串：解析并添加子元素
            elem = etree.SubElement(result, '{http://www.srrc.org.cn}' + key)
            wrapped = '<root xmlns:srrc="http://www.srrc.org.cn">' + value + '</root>'
            parsed = etree.fromstring(wrapped.encode('utf-8'))
            for child in parsed:
                elem.append(child)
            continue

        elem = etree.SubElement(result, '{http://www.srrc.org.cn}' + key)

        if isinstance(value, dict):
            _build_dict_element(elem, value)
        elif isinstance(value, list):
            _build_list_element(elem, value)
        else:
            elem.text = str(value) if value is not None else ''


def _build_dict_element(parent: etree._Element, data: dict) -> None:
    """构建嵌套字典元素"""
    for key, value in data.items():
        if value is None:
            continue

        if key in ('equpara', 'outputchannel', 'featurelist'):
            # 特殊处理：直接添加 etree.Element 或 XML字符串
            if isinstance(value, etree._Element):
                # 直接追加元素到父元素
                parent.append(value)
            elif isinstance(value, str) and value.startswith('<'):
                # 创建包装元素
                wrapper = etree.SubElement(parent, '{http://www.srrc.org.cn}' + key)
                # 解析XML字符串（需要包装在临时根元素中）
                wrapped = '<root xmlns:srrc="http://www.srrc.org.cn">' + value + '</root>'
                parsed = etree.fromstring(wrapped.encode('utf-8'))
                # 将解析后的子元素移动到包装器
                for child in parsed:
                    wrapper.append(child)
            else:
                child = etree.SubElement(parent, '{http://www.srrc.org.cn}' + key)
                if isinstance(value, dict):
                    _build_dict_element(child, value)
                elif isinstance(value, list):
                    _build_list_element(child, value)
                else:
                    child.text = str(value)
        else:
            child = etree.SubElement(parent, '{http://www.srrc.org.cn}' + key)
            if isinstance(value, dict):
                _build_dict_element(child, value)
            elif isinstance(value, list):
                _build_list_element(child, value)
            else:
                child.text = str(value) if value is not None else ''


def _build_list_element(parent: etree._Element, items: list) -> None:
    """构建列表元素"""
    for item in items:
        if isinstance(item, dict):
            child = etree.SubElement(parent, '{http://www.srrc.org.cn}feature')
            for k, v in item.items():
                if v is None:
                    continue
                gc = etree.SubElement(child, '{http://www.srrc.org.cn}' + k)
                if isinstance(v, dict):
                    _build_dict_element(gc, v)
                elif isinstance(v, list):
                    _build_list_element(gc, v)
                else:
                    gc.text = str(v) if v is not None else ''
        else:
            parent.text = str(item)


@app.route('/services', methods=['POST'])
def handle_soap():
    """处理SOAP请求 - 原子服务接收来自代理服务的SOAP请求

    支持两种格式:
    1. Mock Atom 格式: <mon:StartMeasure>...</mon:StartMeasure>
    2. Real Atom 格式: <srrc:requestbody><srrc:equpara>...</srrc:equpara></srrc:requestbody>
    """
    xml_data = request.data.decode('utf-8')
    logger.info(f"收到SOAP请求")

    try:
        root = etree.fromstring(xml_data.encode('utf-8'))
    except etree.XMLSyntaxError as e:
        logger.error(f"SOAP XML解析失败: {e}")
        return build_soap_response(False, error=f"SOAP XML解析失败: {e}"), 500, {'Content-Type': 'text/xml; charset=utf-8'}

    # 提取Body内容
    body = root.find('soap:Body', namespaces=SOAP_NS)
    if body is None:
        return build_soap_response(False, error="未找到SOAP Body"), 400, {'Content-Type': 'text/xml; charset=utf-8'}

    if len(body) == 0:
        return build_soap_response(False, error="SOAP Body为空"), 400, {'Content-Type': 'text/xml; charset=utf-8'}

    # 判断请求格式
    first_child = body[0]
    first_child_tag = first_child.tag.split('}')[1] if '}' in first_child.tag else first_child.tag

    if first_child_tag == 'requestbody':
        # Real Atom 格式解析
        soap_action = request.headers.get('SOAPAction', '')
        operation_name, params = _parse_real_atom_request(first_child, soap_action)
    else:
        # Mock Atom 格式解析 (兼容旧格式)
        operation_name = first_child_tag
        params = {}
        for child in first_child:
            tag_name = child.tag.split('}')[1] if '}' in child.tag else child.tag
            params[tag_name] = child.text

    logger.info(f"SOAP操作: {operation_name}")
    logger.info(f"参数: {params}")

    # 执行对应的业务操作
    result = dispatch_soap_operation(operation_name, params)

    # 判断成功/失败：'success' 键为 False 表示失败
    is_success = result.get('success', True)
    error_msg = result.get('error')
    error_code = result.get('error_code')

    # 构建SOAP响应
    if not is_success and error_msg:
        soap_response = build_soap_response(
            success=False,
            error=error_msg,
            error_code=error_code
        )
    else:
        soap_response = build_soap_response(
            success=True,
            data=result
        )

    return soap_response, 200, {'Content-Type': 'text/xml; charset=utf-8'}


def _parse_real_atom_request(requestbody_elem, soap_action: str = '') -> tuple:
    """解析 Real Atom 格式的 requestbody

    Real Atom 请求结构:
    <srrc:requestbody>
        <srrc:mfid>...</srrc:mfid>
        <srrc:equid>...</srrc:equid>
        <srrc:equpara>
            <srrc:items> 或 <srrc:groupitems>
                ...
            </srrc:items> 或 </srrc:groupitems>
        </srrc:equpara>
        <srrc:appid>...</srrc:appid>
        <srrc:userid>...</srrc:userid>
        <srrc:taskid>...</srrc:taskid>  (可选)
        <srrc:outputchannel>...</srrc:outputchannel>  (可选)
    </srrc:requestbody>

    Args:
        requestbody_elem: requestbody XML元素
        soap_action: SOAPAction header 值

    Returns:
        (operation_name, params_dict)
    """
    params = {}

    # 从传入的 soap_action 参数获取操作名
    soap_action = soap_action.strip('"')
    # SOAPAction 可能是 "B_SglFreqMeas" 或 "{namespace}B_SglFreqMeas"
    if '}' in soap_action:
        operation_name = soap_action.split('}')[1]
    else:
        operation_name = soap_action

    # 解析 requestbody 中的字段
    for child in requestbody_elem:
        tag_name = child.tag.split('}')[1] if '}' in child.tag else child.tag

        if tag_name == 'equpara':
            # 保存原始 equpara XML 用于回显
            params['_raw_equpara'] = etree.tostring(child, encoding='unicode')
            # 解析 equpara 内的参数
            _parse_equpara(child, params)
        elif tag_name == 'outputchannel':
            # 保存原始 outputchannel XML 用于回显
            params['_raw_outputchannel'] = etree.tostring(child, encoding='unicode')
            # 解析 outputchannel
            for oc in child:
                oc_name = oc.tag.split('}')[1] if '}' in oc.tag else oc.tag
                if oc_name not in ('mode', 'datachannel', 'host', 'port', 'stc'):
                    params[oc_name] = oc.text
                else:
                    params['oc_' + oc_name] = oc.text if oc.text else ''
        elif tag_name == 'taskid':
            params['taskid'] = child.text
        elif tag_name in ('appid', 'userid', 'priority', 'executetime', 'mfid', 'equid'):
            params[tag_name] = child.text

    # 如果 SOAPAction 为空，尝试从 equpara 结构推断操作类型
    if not operation_name:
        if 'frequency' in params and 'dfmode' not in params:
            operation_name = 'B_SglFreqMeas'
        elif 'frequency' in params and 'dfmode' in params:
            operation_name = 'B_SglFreqDF'
        elif 'startfreq' in params and 'stopfreq' in params and 'step' in params:
            operation_name = 'B_FScan'
        else:
            operation_name = 'Unknown'

    return operation_name, params


def _parse_equpara(equpara_elem, params: dict):
    """解析 equpara 元素，提取参数"""
    for child in equpara_elem:
        tag_name = child.tag.split('}')[1] if '}' in child.tag else child.tag

        if tag_name == 'items':
            # items 结构：<item><paraname>...</paraname><paravalue>...</paravalue></item>
            for item in child:
                item_name = item.tag.split('}')[1] if '}' in item.tag else item.tag
                if item_name == 'item':
                    paraname = None
                    paravalue = None
                    for sub in item:
                        sub_name = sub.tag.split('}')[1] if '}' in sub.tag else sub.tag
                        if sub_name == 'paraname':
                            paraname = sub.text
                        elif sub_name == 'paravalue':
                            paravalue = sub.text
                    if paraname:
                        # 尝试转换为数值
                        try:
                            if paravalue and paravalue.isdigit():
                                params[paraname] = int(paravalue)
                            elif paravalue:
                                try:
                                    params[paraname] = float(paravalue)
                                except ValueError:
                                    params[paraname] = paravalue
                        except (ValueError, AttributeError):
                            params[paraname] = paravalue

        elif tag_name == 'groupitems':
            # groupitems 结构
            for groupitem in child:
                group_name = groupitem.tag.split('}')[1] if '}' in groupitem.tag else groupitem.tag
                if group_name == 'groupitem':
                    group_id = None
                    for gi_child in groupitem:
                        gi_tag = gi_child.tag.split('}')[1] if '}' in gi_child.tag else gi_child.tag
                        if gi_tag == 'groupid':
                            group_id = gi_child.text
                        elif gi_tag == 'items':
                            # 递归解析 items
                            _parse_equpara(gi_child, params)


def dispatch_soap_operation(operation: str, params: dict) -> dict:
    """根据SOAP操作分发到对应的业务处理函数

    返回格式说明：
    - 返回的 dict 会传递给 build_soap_response 构建 SOAP 响应
    - 查询接口返回设备信息
    - 执行接口返回业务数据 + 回显字段
    """
    # 生成 taskid
    task_id = generate_taskid()

    try:
        # ==================== 查询接口（不需要设备连接） ====================

        if operation == 'B_QueryDeviceInfo':
            # 设备信息查询 - 返回完整设备信息
            return _build_device_info_result(params)

        elif operation == 'B_QueryFaciDevStat':
            # 设备状态查询
            return {
                'status': 'online' if _device_connected else 'offline',
                'device_connected': _device_connected
            }

        elif operation == 'B_TaskModification':
            # 任务修改
            action = params.get('action', 'start')
            return {
                'action': action,
                'status': 'modified'
            }

        elif operation == 'B_StopMeas':
            # 停止测量 - 回显基础字段（不含 equpara 和 outputchannel）
            stop_taskid = params.get('taskid', task_id)
            # 移除 _raw_equpara 和 _raw_outputchannel，避免回显
            params_copy = {k: v for k, v in params.items() if k not in ('_raw_equpara', '_raw_outputchannel')}
            return _build_base_result(params_copy, stop_taskid)

        # ==================== 执行接口（需要设备连接） ====================

        elif operation in ('StartMeasure', 'B_SglFreqMeas'):
            # 单频测量 (SGLFREQ 0x10)
            frequency = int(params.get('frequency', 100_000_000))
            bandwidth = int(params.get('ifbw', 120000))

            hook = HookManager.get_instance()
            hook.start_context()

            try:
                # [临时修改] 跳过设备连接检查，直接发送请求
                # TODO: 正式环境需要恢复设备连接检查
                # error_resp = check_device_connected()
                # if error_resp:
                #     return {
                #         'success': False,
                #         'error': '设备未连接',
                #         'error_code': 'BIZ-000002'
                #     }

                hook.log_layer("atom", {
                    "interface": "/services (SOAP)",
                    "operation": "B_SglFreqMeas",
                    "business_type": "0x10 (SGLFREQ)",
                    "params": {"frequency": frequency, "bandwidth": bandwidth}
                })

                async def do_sglfreq():
                    client = get_device_client()
                    await client.connect()
                    try:
                        builder = RMCPTPBuilder()
                        frame = builder.build_sglfreq_command(frequency, 'default')
                        hook.log_frame("send", "RMCPTP_CMD", bytes_to_hex(frame))
                        header_info, payload, raw_frame = await client.send_and_receive(frame)
                        hook.log_frame("recv", "RMCPTP_RESP", bytes_to_hex(raw_frame))
                        import struct
                        result = {'frequency': frequency}
                        if payload and len(payload) > 20:
                            result['amplitude'] = struct.unpack('!f', payload[20:24])[0]
                        return result
                    finally:
                        await client.disconnect()

                device_result = run_async(do_sglfreq())
                return _build_base_result(params, task_id, include_outputchannel=True)
            finally:
                hook.end_context()

        elif operation == 'B_SglFreqDF':
            # 单频测向 (DF 0x12)
            frequency = int(params.get('frequency', 100_000_000))

            hook = HookManager.get_instance()
            hook.start_context()

            try:
                error_resp = check_device_connected()
                if error_resp:
                    return {
                        'success': False,
                        'error': '设备未连接',
                        'error_code': 'BIZ-000002'
                    }

                hook.log_layer("atom", {
                    "interface": "/services (SOAP)",
                    "operation": "B_SglFreqDF",
                    "business_type": "0x12 (DF)",
                    "params": {"frequency": frequency}
                })

                async def do_df():
                    client = get_device_client()
                    await client.connect()
                    try:
                        import struct
                        builder = RMCPTPBuilder()
                        business_data = struct.pack('!B Q', 0x12, frequency)
                        frame = builder.build_command_frame(business_type=0x12, params=business_data)
                        hook.log_frame("send", "RMCPTP_CMD", bytes_to_hex(frame))
                        header_info, payload, raw_frame = await client.send_and_receive(frame)
                        hook.log_frame("recv", "RMCPTP_RESP", bytes_to_hex(raw_frame))
                        return {'frequency': frequency}
                    finally:
                        await client.disconnect()

                run_async(do_df())
                return _build_base_result(params, task_id, include_outputchannel=True)
            finally:
                hook.end_context()

        elif operation in ('StartScan', 'B_FScan'):
            # 频段扫描 (FSCAN 0x15)
            hook = HookManager.get_instance()
            hook.start_context()

            try:
                error_resp = check_device_connected()
                if error_resp:
                    return {
                        'success': False,
                        'error': '设备未连接',
                        'error_code': 'BIZ-000002'
                    }

                hook.log_layer("atom", {
                    "interface": "/services (SOAP)",
                    "operation": "B_FScan",
                    "business_type": "0x15 (FSCAN)"
                })

                async def do_fscan():
                    client = get_device_client()
                    await client.connect()
                    try:
                        service = MonitorService(client)
                        return await service.start_fscan(
                            int(params.get('startfreq', 100_000_000)),
                            int(params.get('stopfreq', 200_000_000)),
                            int(params.get('step', 1_000_000))
                        )
                    finally:
                        await client.disconnect()

                run_async(do_fscan())
                return _build_base_result(params, task_id, include_outputchannel=True)
            finally:
                hook.end_context()

        elif operation == 'B_FScanDF':
            # 频段扫描测向
            hook = HookManager.get_instance()
            hook.start_context()

            try:
                error_resp = check_device_connected()
                if error_resp:
                    return {
                        'success': False,
                        'error': '设备未连接',
                        'error_code': 'BIZ-000002'
                    }

                async def do_fscan_df():
                    client = get_device_client()
                    await client.connect()
                    try:
                        service = MonitorService(client)
                        return await service.start_fscan(
                            int(params.get('startfreq', 100_000_000)),
                            int(params.get('stopfreq', 200_000_000)),
                            int(params.get('step', 1_000_000))
                        )
                    finally:
                        await client.disconnect()

                run_async(do_fscan_df())
                return _build_base_result(params, task_id, include_outputchannel=True)
            finally:
                hook.end_context()

        elif operation == 'B_MScan':
            # 多信道扫描 (MSCAN 0x14)
            hook = HookManager.get_instance()
            hook.start_context()

            try:
                error_resp = check_device_connected()
                if error_resp:
                    return {
                        'success': False,
                        'error': '设备未连接',
                        'error_code': 'BIZ-000002'
                    }

                async def do_mscan():
                    client = get_device_client()
                    await client.connect()
                    try:
                        builder = RMCPTPBuilder()
                        frame = builder.build_mscan_command(
                            int(params.get('frequency', 100_000_000)),
                            int(params.get('ifbw', 120000))
                        )
                        hook.log_frame("send", "RMCPTP_CMD", bytes_to_hex(frame))
                        header_info, payload, raw_frame = await client.send_and_receive(frame)
                        hook.log_frame("recv", "RMCPTP_RESP", bytes_to_hex(raw_frame))
                        return {}
                    finally:
                        await client.disconnect()

                run_async(do_mscan())
                return _build_base_result(params, task_id, include_outputchannel=True)
            finally:
                hook.end_context()

        elif operation == 'B_MScanDF':
            # 多信道扫描测向
            hook = HookManager.get_instance()
            hook.start_context()

            try:
                error_resp = check_device_connected()
                if error_resp:
                    return {
                        'success': False,
                        'error': '设备未连接',
                        'error_code': 'BIZ-000002'
                    }

                async def do_mscan_df():
                    client = get_device_client()
                    await client.connect()
                    try:
                        builder = RMCPTPBuilder()
                        frame = builder.build_mscan_command(
                            int(params.get('frequency', 100_000_000)),
                            int(params.get('ifbw', 120000))
                        )
                        hook.log_frame("send", "RMCPTP_CMD", bytes_to_hex(frame))
                        header_info, payload, raw_frame = await client.send_and_receive(frame)
                        hook.log_frame("recv", "RMCPTP_RESP", bytes_to_hex(raw_frame))
                        return {}
                    finally:
                        await client.disconnect()

                run_async(do_mscan_df())
                return _build_base_result(params, task_id, include_outputchannel=True)
            finally:
                hook.end_context()

        elif operation == 'B_PScan':
            # 频谱扫描 (PSCAN 0x17)
            hook = HookManager.get_instance()
            hook.start_context()

            try:
                error_resp = check_device_connected()
                if error_resp:
                    return {
                        'success': False,
                        'error': '设备未连接',
                        'error_code': 'BIZ-000002'
                    }

                async def do_pscan():
                    client = get_device_client()
                    await client.connect()
                    try:
                        builder = RMCPTPBuilder()
                        frame = builder.build_pscan_command(
                            int(params.get('startfreq', 100_000_000)),
                            int(params.get('stopfreq', 200_000_000)),
                            int(params.get('step', 1_000_000))
                        )
                        hook.log_frame("send", "RMCPTP_CMD", bytes_to_hex(frame))
                        header_info, payload, raw_frame = await client.send_and_receive(frame)
                        hook.log_frame("recv", "RMCPTP_RESP", bytes_to_hex(raw_frame))
                        return {}
                    finally:
                        await client.disconnect()

                run_async(do_pscan())
                return _build_base_result(params, task_id, include_outputchannel=True)
            finally:
                hook.end_context()

        elif operation == 'B_WBDF':
            # 宽带测向 (WBDF 0x19)
            hook = HookManager.get_instance()
            hook.start_context()

            try:
                error_resp = check_device_connected()
                if error_resp:
                    return {
                        'success': False,
                        'error': '设备未连接',
                        'error_code': 'BIZ-000002'
                    }

                async def do_wbdf():
                    client = get_device_client()
                    await client.connect()
                    try:
                        builder = RMCPTPBuilder()
                        frame = builder.build_wbdf_command(
                            int(params.get('frequency', 100_000_000)),
                            int(params.get('ifbw', 40000000))
                        )
                        hook.log_frame("send", "RMCPTP_CMD", bytes_to_hex(frame))
                        header_info, payload, raw_frame = await client.send_and_receive(frame)
                        hook.log_frame("recv", "RMCPTP_RESP", bytes_to_hex(raw_frame))
                        return {}
                    finally:
                        await client.disconnect()

                run_async(do_wbdf())
                return _build_base_result(params, task_id, include_outputchannel=True)
            finally:
                hook.end_context()

        else:
            logger.warning(f"未知的SOAP操作: {operation}")
            return {
                'success': False,
                'error': f'未知操作: {operation}',
                'error_code': 'BIZ-000002'
            }

    except Exception as e:
        logger.error(f"处理SOAP请求失败: {e}")
        return {
            'success': False,
            'error': str(e),
            'error_code': 'BIZ-000002'
        }


def _build_base_result(params: dict, task_id: str, include_outputchannel: bool = False) -> dict:
    """构建基础回显结果

    Args:
        params: 请求参数（包含 _raw_equpara, _raw_outputchannel 等）
        task_id: 任务ID
        include_outputchannel: 是否包含 outputchannel

    Returns:
        回显结果字典
    """
    result = {}

    # 基础字段回显
    for field in ('appid', 'userid', 'priority', 'executetime', 'mfid', 'equid'):
        if field in params and params[field]:
            result[field] = params[field]
        elif field in DEVICE_INFO:
            result[field] = DEVICE_INFO[field]

    # equpara 回显
    if '_raw_equpara' in params:
        result['equpara'] = params['_raw_equpara']

    # taskid
    result['taskid'] = task_id

    # outputchannel
    if include_outputchannel:
        if '_raw_outputchannel' in params:
            result['outputchannel'] = params['_raw_outputchannel']
        else:
            result['outputchannel'] = get_outputchannel_xml()

    return result


def _build_featurelist_into_result(parent: etree._Element, featurelist_data) -> None:
    """将 featurelist 结构直接构建到 parent 元素下"""
    NS = 'http://www.srrc.org.cn'

    # 创建 featurelist 元素
    featurelist_elem = etree.SubElement(parent, '{%s}featurelist' % NS)

    # 无参数的接口
    no_param_codes = ['B_QueryDeviceInfo', 'B_QueryFaciDevStat', 'B_TaskModification', 'B_StopMeas']

    for code in no_param_codes:
        feature = etree.SubElement(featurelist_elem, '{%s}feature' % NS)
        code_elem = etree.SubElement(feature, '{%s}code' % NS)
        code_elem.text = code
        etree.SubElement(feature, '{%s}input' % NS)

    # 有参数的接口定义
    param_features = {
        'B_SglFreqMeas': [
            {'name': 'frequency', 'type': 'double', 'defaultvalue': '100000000', 'range': {'startval': '20000000', 'stopval': '6000000000'}},
            {'name': 'ifbw', 'type': 'String', 'defaultvalue': '40000000'},
            {'name': 'gain', 'type': 'String', 'defaultvalue': 'AGC'},
            {'name': 'rfworkmode', 'type': 'String', 'defaultvalue': '0'},
            {'name': 'audiotype', 'type': 'String', 'defaultvalue': 'off'},
            {'name': 'demodmode', 'type': 'String', 'defaultvalue': 'FM'},
            {'name': 'demodbw', 'type': 'String', 'defaultvalue': '200000'},
            {'name': 'spectrumswitch', 'type': 'string', 'defaultvalue': 'on'},
            {'name': 'ITUSwitch', 'type': 'string', 'defaultvalue': 'on'},
        ],
        'B_SglFreqDF': [
            {'name': 'frequency', 'type': 'double', 'defaultvalue': '100000000', 'range': {'startval': '20000000', 'stopval': '6000000000'}},
            {'name': 'dfmode', 'type': 'String', 'defaultvalue': '1'},
            {'name': 'ifbw', 'type': 'String', 'defaultvalue': '40000000'},
            {'name': 'gain', 'type': 'String', 'defaultvalue': 'AGC'},
            {'name': 'rfworkmode', 'type': 'String', 'defaultvalue': '0'},
            {'name': 'dftype', 'type': 'String', 'defaultvalue': '0'},
            {'name': 'spectrumswitch', 'type': 'string', 'defaultvalue': 'on'},
        ],
        'B_MScan': [
            {'name': 'frequency', 'type': 'double', 'defaultvalue': '100000000', 'isgroupset': 'true'},
            {'name': 'ifbw', 'type': 'String', 'defaultvalue': '40000000'},
            {'name': 'gain', 'type': 'String', 'defaultvalue': 'AGC'},
            {'name': 'rfworkmode', 'type': 'String', 'defaultvalue': '0'},
        ],
        'B_FScan': [
            {'name': 'startfreq', 'type': 'double', 'defaultvalue': '137000000', 'range': {'startval': '20000000', 'stopval': '6000000000'}},
            {'name': 'stopfreq', 'type': 'double', 'defaultvalue': '173000000', 'range': {'startval': '20000000', 'stopval': '8000000000'}},
            {'name': 'step', 'type': 'String', 'defaultvalue': '25000'},
            {'name': 'gain', 'type': 'String', 'defaultvalue': 'AGC'},
            {'name': 'rfworkmode', 'type': 'String', 'defaultvalue': '0'},
            {'name': 'scanmode', 'type': 'String', 'defaultvalue': '0'},
        ],
        'B_PScan': [
            {'name': 'startfreq', 'type': 'double', 'defaultvalue': '137000000'},
            {'name': 'stopfreq', 'type': 'double', 'defaultvalue': '173000000'},
            {'name': 'step', 'type': 'String', 'defaultvalue': '25000'},
            {'name': 'gain', 'type': 'String', 'defaultvalue': 'AGC'},
            {'name': 'rfworkmode', 'type': 'String', 'defaultvalue': '0'},
            {'name': 'keepmode', 'type': 'String', 'defaultvalue': '0'},
        ],
        'B_FScanDF': [
            {'name': 'startfreq', 'type': 'double', 'defaultvalue': '137000000'},
            {'name': 'stopfreq', 'type': 'double', 'defaultvalue': '173000000'},
            {'name': 'step', 'type': 'String', 'defaultvalue': '25000'},
            {'name': 'rfworkmode', 'type': 'String', 'defaultvalue': '0'},
            {'name': 'gain', 'type': 'String', 'defaultvalue': 'AGC'},
        ],
        'B_WBDF': [
            {'name': 'frequency', 'type': 'double', 'defaultvalue': '100000000'},
            {'name': 'ifbw', 'type': 'String', 'defaultvalue': '40000000'},
            {'name': 'gain', 'type': 'String', 'defaultvalue': 'AGC'},
            {'name': 'rfworkmode', 'type': 'String', 'defaultvalue': '0'},
        ],
        'B_MScanDF': [
            {'name': 'frequency', 'type': 'double', 'defaultvalue': '100000000'},
            {'name': 'dfmode', 'type': 'String', 'defaultvalue': '1'},
            {'name': 'ifbw', 'type': 'String', 'defaultvalue': '40000000'},
            {'name': 'gain', 'type': 'String', 'defaultvalue': 'AGC'},
            {'name': 'rfworkmode', 'type': 'String', 'defaultvalue': '0'},
        ],
    }

    for code, parameters in param_features.items():
        feature = etree.SubElement(featurelist_elem, '{%s}feature' % NS)
        code_elem = etree.SubElement(feature, '{%s}code' % NS)
        code_elem.text = code
        input_elem = etree.SubElement(feature, '{%s}input' % NS)

        for param in parameters:
            param_elem = etree.SubElement(input_elem, '{%s}parameter' % NS)
            for pkey, pvalue in param.items():
                if pkey == 'range':
                    range_elem = etree.SubElement(param_elem, '{%s}range' % NS)
                    for rkey, rvalue in pvalue.items():
                        r_elem = etree.SubElement(range_elem, '{%s}%s' % (NS, rkey))
                        r_elem.text = rvalue
                elif pkey == 'isgroupset':
                    g_elem = etree.SubElement(param_elem, '{%s}%s' % (NS, pkey))
                    g_elem.text = pvalue
                else:
                    p_elem = etree.SubElement(param_elem, '{%s}%s' % (NS, pkey))
                    p_elem.text = pvalue


def _build_device_info_result(params: dict = None) -> dict:
    """构建设备信息查询结果

    Args:
        params: 请求参数（包含 mfid, equid）

    Returns:
        设备信息字典
    """
    # 从请求参数获取 mfid 和 equid，如果不存在则使用默认值
    mfid = None
    equid = None

    if params:
        mfid = params.get('mfid')
        equid = params.get('equid')

    # 如果请求中没有 mfid/equid，使用默认配置
    if not mfid or not equid:
        mfid = DEVICE_INFO['mfid']
        equid = DEVICE_INFO['equid']

    # 尝试加载设备配置
    config = load_device_config(mfid, equid)

    if config:
        result = {}
        # 基础字段
        for field in ('mfid', 'equid', 'equname', 'equtype', 'equstatus',
                       'equimanu', 'equmodel', 'equsn', 'maxtasknumber'):
            if field in config:
                result[field] = config[field]
            elif field in DEVICE_INFO:
                result[field] = DEVICE_INFO[field]

        # 如果有 featurelist 元素，直接使用
        if 'featurelist' in config and isinstance(config['featurelist'], etree._Element):
            result['featurelist'] = config['featurelist']
        else:
            # 否则标记需要构建
            result['featurelist'] = True
    else:
        # 配置文件不存在，使用默认值
        result = dict(DEVICE_INFO)
        result['featurelist'] = True

    return result


def _build_featurelist_element() -> etree._Element:
    """构建完整的 featurelist 元素树（参考 Real Atom 格式）"""
    NS = 'http://www.srrc.org.cn'
    NSMAP = {'srrc': NS}

    # 创建 featurelist 根元素
    featurelist = etree.Element('{%s}featurelist' % NS, nsmap=NSMAP)

    # 无参数的接口
    no_param_codes = ['B_QueryDeviceInfo', 'B_QueryFaciDevStat', 'B_TaskModification', 'B_StopMeas']

    for code in no_param_codes:
        feature = etree.SubElement(featurelist, '{%s}feature' % NS)
        code_elem = etree.SubElement(feature, '{%s}code' % NS)
        code_elem.text = code
        input_elem = etree.SubElement(feature, '{%s}input' % NS)

    # 有参数的接口定义
    param_features = {
        'B_SglFreqMeas': [
            {'name': 'frequency', 'type': 'double', 'defaultvalue': '100000000', 'range': {'startval': '20000000', 'stopval': '6000000000'}},
            {'name': 'ifbw', 'type': 'String', 'defaultvalue': '40000000'},
            {'name': 'gain', 'type': 'String', 'defaultvalue': 'AGC'},
            {'name': 'rfworkmode', 'type': 'String', 'defaultvalue': '0'},
            {'name': 'audiotype', 'type': 'String', 'defaultvalue': 'off'},
            {'name': 'demodmode', 'type': 'String', 'defaultvalue': 'FM'},
            {'name': 'demodbw', 'type': 'String', 'defaultvalue': '200000'},
            {'name': 'spectrumswitch', 'type': 'string', 'defaultvalue': 'on'},
            {'name': 'ITUSwitch', 'type': 'string', 'defaultvalue': 'on'},
        ],
        'B_SglFreqDF': [
            {'name': 'frequency', 'type': 'double', 'defaultvalue': '100000000', 'range': {'startval': '20000000', 'stopval': '6000000000'}},
            {'name': 'dfmode', 'type': 'String', 'defaultvalue': '1'},
            {'name': 'ifbw', 'type': 'String', 'defaultvalue': '40000000'},
            {'name': 'gain', 'type': 'String', 'defaultvalue': 'AGC'},
            {'name': 'rfworkmode', 'type': 'String', 'defaultvalue': '0'},
            {'name': 'dftype', 'type': 'String', 'defaultvalue': '0'},
            {'name': 'spectrumswitch', 'type': 'string', 'defaultvalue': 'on'},
        ],
        'B_MScan': [
            {'name': 'frequency', 'type': 'double', 'defaultvalue': '100000000', 'isgroupset': 'true'},
            {'name': 'ifbw', 'type': 'String', 'defaultvalue': '40000000'},
            {'name': 'gain', 'type': 'String', 'defaultvalue': 'AGC'},
            {'name': 'rfworkmode', 'type': 'String', 'defaultvalue': '0'},
        ],
        'B_FScan': [
            {'name': 'startfreq', 'type': 'double', 'defaultvalue': '137000000', 'range': {'startval': '20000000', 'stopval': '6000000000'}},
            {'name': 'stopfreq', 'type': 'double', 'defaultvalue': '173000000', 'range': {'startval': '20000000', 'stopval': '8000000000'}},
            {'name': 'step', 'type': 'String', 'defaultvalue': '25000'},
            {'name': 'gain', 'type': 'String', 'defaultvalue': 'AGC'},
            {'name': 'rfworkmode', 'type': 'String', 'defaultvalue': '0'},
            {'name': 'scanmode', 'type': 'String', 'defaultvalue': '0'},
        ],
        'B_PScan': [
            {'name': 'startfreq', 'type': 'double', 'defaultvalue': '137000000'},
            {'name': 'stopfreq', 'type': 'double', 'defaultvalue': '173000000'},
            {'name': 'step', 'type': 'String', 'defaultvalue': '25000'},
            {'name': 'gain', 'type': 'String', 'defaultvalue': 'AGC'},
            {'name': 'rfworkmode', 'type': 'String', 'defaultvalue': '0'},
            {'name': 'keepmode', 'type': 'String', 'defaultvalue': '0'},
        ],
        'B_FScanDF': [
            {'name': 'startfreq', 'type': 'double', 'defaultvalue': '137000000'},
            {'name': 'stopfreq', 'type': 'double', 'defaultvalue': '173000000'},
            {'name': 'step', 'type': 'String', 'defaultvalue': '25000'},
            {'name': 'rfworkmode', 'type': 'String', 'defaultvalue': '0'},
            {'name': 'gain', 'type': 'String', 'defaultvalue': 'AGC'},
        ],
        'B_WBDF': [
            {'name': 'frequency', 'type': 'double', 'defaultvalue': '100000000'},
            {'name': 'ifbw', 'type': 'String', 'defaultvalue': '40000000'},
            {'name': 'gain', 'type': 'String', 'defaultvalue': 'AGC'},
            {'name': 'rfworkmode', 'type': 'String', 'defaultvalue': '0'},
        ],
        'B_MScanDF': [
            {'name': 'frequency', 'type': 'double', 'defaultvalue': '100000000'},
            {'name': 'dfmode', 'type': 'String', 'defaultvalue': '1'},
            {'name': 'ifbw', 'type': 'String', 'defaultvalue': '40000000'},
            {'name': 'gain', 'type': 'String', 'defaultvalue': 'AGC'},
            {'name': 'rfworkmode', 'type': 'String', 'defaultvalue': '0'},
        ],
    }

    for code, parameters in param_features.items():
        feature = etree.SubElement(featurelist, '{%s}feature' % NS)
        code_elem = etree.SubElement(feature, '{%s}code' % NS)
        code_elem.text = code
        input_elem = etree.SubElement(feature, '{%s}input' % NS)

        for param in parameters:
            param_elem = etree.SubElement(input_elem, '{%s}parameter' % NS)
            for pkey, pvalue in param.items():
                if pkey == 'range':
                    range_elem = etree.SubElement(param_elem, '{%s}range' % NS)
                    for rkey, rvalue in pvalue.items():
                        r_elem = etree.SubElement(range_elem, '{%s}%s' % (NS, rkey))
                        r_elem.text = rvalue
                elif pkey == 'isgroupset':
                    g_elem = etree.SubElement(param_elem, '{%s}%s' % (NS, pkey))
                    g_elem.text = pvalue
                else:
                    p_elem = etree.SubElement(param_elem, '{%s}%s' % (NS, pkey))
                    p_elem.text = pvalue

    return featurelist


# ==================== 测向服务接口 ====================

@app.route('/direction/df', methods=['POST'])
def start_df():
    """单频测向"""
    # 启动Hook上下文（始终记录）
    hook = HookManager.get_instance()
    hook.start_context()

    try:
        # ========== 后端验证：按文档规范 ==========
        error_resp = check_device_connected()
        if error_resp:
            hook.log_layer("atom", {"error": "设备未连接"})
            return error_resp
        # ==========================================

        import struct
        builder = RMCPTPBuilder()
        data = request.get_json() or {}
        frequency = data.get('frequency', 100_000_000)
        bandwidth = data.get('bandwidth', 120000)

        # 记录Atom层参数
        hook.log_layer("atom", {
            "interface": "/direction/df",
            "business_type": "0x12 (DF)",
            "params": {"frequency": frequency, "bandwidth": bandwidth}
        })

        async def do_df():
            # 每次请求创建独立的短连接
            client = get_device_client()
            await client.connect()
            try:
                business_data = struct.pack('!B Q', 0x12, frequency)
                frame = builder.build_command_frame(business_type=0x12, params=business_data)

                # 记录发送帧
                hook.log_frame("send", "RMCPTP_CMD", bytes_to_hex(frame))

                header_info, payload, raw_frame = await client.send_and_receive(frame)

                # 记录接收帧
                hook.log_frame("recv", "RMCPTP_RESP", bytes_to_hex(raw_frame))

                # 检查错误响应 (business_type == 0xFF)
                if payload and len(payload) > 0 and payload[0] == 0xFF:
                    if len(payload) >= 15:
                        error_code = struct.unpack('!I', payload[11:15])[0]
                        error_msg = payload[15:].decode('utf-8', errors='replace')
                        raise Exception(f"设备错误 {error_code}: {error_msg}")
                    raise Exception("设备返回未知错误")
                # 正常响应，交给 DirectionService 解析
                service = DirectionService(client)
                result = service._parse_df_response(payload)
                result.update({
                    'success': True,
                    'frequency': frequency,
                    'bandwidth': bandwidth
                })

                # 记录响应数据
                hook.log_layer("atom", {"result": result})

                return result
            finally:
                await client.disconnect()

        result = run_async(do_df())
        return jsonify(result), 200
    except Exception as e:
        logger.error(f"单频测向失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        hook.end_context()


@app.route('/direction/ifdf', methods=['POST'])
def start_ifdf():
    """中频测向"""
    # 启动Hook上下文（始终记录）
    hook = HookManager.get_instance()
    hook.start_context()

    try:
        # ========== 后端验证：按文档规范 ==========
        error_resp = check_device_connected()
        if error_resp:
            hook.log_layer("atom", {"error": "设备未连接"})
            return error_resp
        # ==========================================

        data = request.get_json() or {}
        frequency = data.get('frequency', 100_000_000)
        span = data.get('span', 1_000_000)
        ifbw = data.get('ifbw', 100000)

        # 记录Atom层参数
        hook.log_layer("atom", {
            "interface": "/direction/ifdf",
            "business_type": "0x13 (IFDF)",
            "params": {"frequency": frequency, "span": span, "ifbw": ifbw}
        })

        async def do_ifdf():
            # 每次请求创建独立的短连接
            client = get_device_client()
            await client.connect()
            try:
                service = DirectionService(client)
                return await service.start_ifdf(frequency, span, ifbw)
            finally:
                await client.disconnect()

        result = run_async(do_ifdf())

        # 记录响应数据
        hook.log_layer("atom", {"result": result})

        return jsonify(result), 200
    except Exception as e:
        logger.error(f"中频测向失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        hook.end_context()


@app.route('/direction/wbfft', methods=['POST'])
def start_wbfft():
    """宽带FFT"""
    # 启动Hook上下文（始终记录）
    hook = HookManager.get_instance()
    hook.start_context()

    try:
        # ========== 后端验证：按文档规范 ==========
        error_resp = check_device_connected()
        if error_resp:
            hook.log_layer("atom", {"error": "设备未连接"})
            return error_resp
        # ==========================================

        data = request.get_json() or {}
        start_freq = data.get('start_freq', 100_000_000)
        end_freq = data.get('end_freq', 200_000_000)

        # 记录Atom层参数
        hook.log_layer("atom", {
            "interface": "/direction/wbfft",
            "business_type": "0x1C (WBFFT)",
            "params": {"start_freq": start_freq, "end_freq": end_freq}
        })

        async def do_wbfft():
            # 每次请求创建独立的短连接
            client = get_device_client()
            await client.connect()
            try:
                service = DirectionService(client)
                return await service.start_wbfft(start_freq, end_freq)
            finally:
                await client.disconnect()

        result = run_async(do_wbfft())

        # 记录响应数据
        hook.log_layer("atom", {"result": result})

        return jsonify(result), 200
    except Exception as e:
        logger.error(f"宽带FFT失败: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500
    finally:
        hook.end_context()


def main():
    """主函数"""
    config = SERVICES['atom']
    logger.info(f"启动原子服务: {config['host']}:{config['port']}")
    logger.info(f"设备地址: {config['device_host']}:{config['device_port']}")

    app.run(
        host=config['host'],
        port=config['port'],
        debug=False,
        threaded=True
    )


if __name__ == '__main__':
    main()
