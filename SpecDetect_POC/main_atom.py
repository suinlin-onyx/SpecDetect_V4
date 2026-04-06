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
    'mon': 'http://monitor.rrmp.gov.cn/services/'
}


def build_soap_response(success: bool, data: dict = None, error: str = None) -> str:
    """构建SOAP响应"""
    root = etree.Element(
        '{http://schemas.xmlsoap.org/soap/envelope/}Envelope',
        nsmap=SOAP_NS
    )
    body = etree.SubElement(root, '{http://schemas.xmlsoap.org/soap/envelope/}Body')
    response = etree.SubElement(body, '{http://monitor.rrmp.gov.cn/services/}Response')
    response.set('success', 'true' if success else 'false')

    if success and data:
        for key, value in data.items():
            child = etree.SubElement(response, '{http://monitor.rrmp.gov.cn/services/}' + key)
            child.text = str(value)
    elif not success and error:
        child = etree.SubElement(response, '{http://monitor.rrmp.gov.cn/services/}Error')
        child.text = error

    return etree.tostring(root, pretty_print=True, encoding='utf-8').decode('utf-8')


@app.route('/services', methods=['POST'])
def handle_soap():
    """处理SOAP请求 - 原子服务接收来自代理服务的SOAP请求"""
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

    operation = body[0]
    operation_name = operation.tag.split('}')[1] if '}' in operation.tag else operation.tag

    logger.info(f"SOAP操作: {operation_name}")

    # 提取参数
    params = {}
    for child in operation:
        tag_name = child.tag.split('}')[1] if '}' in child.tag else child.tag
        params[tag_name] = child.text

    logger.info(f"参数: {params}")

    # 执行对应的业务操作
    result = dispatch_soap_operation(operation_name, params)

    # 构建SOAP响应
    soap_response = build_soap_response(
        success=result.get('success', True),
        data=result
    )

    return soap_response, 200, {'Content-Type': 'text/xml; charset=utf-8'}


def dispatch_soap_operation(operation: str, params: dict) -> dict:
    """根据SOAP操作分发到对应的业务处理函数"""
    try:
        if operation == 'StartMeasure' or operation.endswith('StartMeasure'):
            # 单频测量
            frequency = int(params.get('Frequency', params.get('frequency', 100_000_000)))
            bandwidth = int(params.get('Bandwidth', params.get('bandwidth', 120000)))
            antenna = params.get('AntennaID', 'default')

            hook = HookManager.get_instance()
            hook.start_context()

            try:
                error_resp = check_device_connected()
                if error_resp:
                    return {'success': False, 'error': '设备未连接'}

                hook.log_layer("atom", {
                    "interface": "/services (SOAP)",
                    "operation": "StartMeasure",
                    "business_type": "0x10 (SGLFREQ)",
                    "params": {"frequency": frequency, "bandwidth": bandwidth}
                })

                async def do_sglfreq():
                    client = get_device_client()
                    await client.connect()
                    try:
                        builder = RMCPTPBuilder()
                        frame = builder.build_sglfreq_command(frequency, antenna)
                        hook.log_frame("send", "RMCPTP_CMD", bytes_to_hex(frame))
                        header_info, payload, raw_frame = await client.send_and_receive(frame)
                        hook.log_frame("recv", "RMCPTP_RESP", bytes_to_hex(raw_frame))
                        import struct
                        result = {'frequency': frequency, 'bandwidth': bandwidth}
                        if payload and len(payload) > 20:
                            result['amplitude'] = struct.unpack('!f', payload[20:24])[0]
                        return result
                    finally:
                        await client.disconnect()

                result = run_async(do_sglfreq())
                result['success'] = True
                return result
            finally:
                hook.end_context()

        elif operation == 'StartScan' or operation.endswith('StartScan'):
            # 频段扫描
            start_freq = int(params.get('StartFreq', params.get('StartFreq', 100_000_000)))
            end_freq = int(params.get('EndFreq', params.get('EndFreq', 200_000_000)))
            step = int(params.get('Step', params.get('step', 1_000_000)))

            hook = HookManager.get_instance()
            hook.start_context()

            try:
                error_resp = check_device_connected()
                if error_resp:
                    return {'success': False, 'error': '设备未连接'}

                hook.log_layer("atom", {
                    "interface": "/services (SOAP)",
                    "operation": "StartScan",
                    "business_type": "0x15 (FSCAN)",
                    "params": {"start_freq": start_freq, "end_freq": end_freq, "step": step}
                })

                async def do_fscan():
                    client = get_device_client()
                    await client.connect()
                    try:
                        service = MonitorService(client)
                        return await service.start_fscan(start_freq, end_freq, step)
                    finally:
                        await client.disconnect()

                result = run_async(do_fscan())
                result['success'] = True
                return result
            finally:
                hook.end_context()

        elif operation == 'StartIFAnalysis' or operation.endswith('StartIFAnalysis'):
            # 中频分析
            frequency = int(params.get('Frequency', params.get('frequency', 100_000_000)))
            span = int(params.get('Span', params.get('span', 1_000_000)))
            ifbw = int(params.get('IFBW', params.get('ifbw', 100000)))

            hook = HookManager.get_instance()
            hook.start_context()

            try:
                error_resp = check_device_connected()
                if error_resp:
                    return {'success': False, 'error': '设备未连接'}

                hook.log_layer("atom", {
                    "interface": "/services (SOAP)",
                    "operation": "StartIFAnalysis",
                    "business_type": "0x11 (IFANALYSIS)",
                    "params": {"frequency": frequency, "span": span, "ifbw": ifbw}
                })

                async def do_ifanalysis():
                    client = get_device_client()
                    await client.connect()
                    try:
                        service = MonitorService(client)
                        return await service.start_ifanalysis(frequency, span, ifbw)
                    finally:
                        await client.disconnect()

                result = run_async(do_ifanalysis())
                result['success'] = True
                return result
            finally:
                hook.end_context()

        elif operation == 'StartDirection' or operation.endswith('StartDirection'):
            # 单频测向
            frequency = int(params.get('Frequency', params.get('frequency', 100_000_000)))
            bandwidth = int(params.get('Bandwidth', params.get('bandwidth', 120000)))

            hook = HookManager.get_instance()
            hook.start_context()

            try:
                error_resp = check_device_connected()
                if error_resp:
                    return {'success': False, 'error': '设备未连接'}

                hook.log_layer("atom", {
                    "interface": "/services (SOAP)",
                    "operation": "StartDirection",
                    "business_type": "0x12 (DF)",
                    "params": {"frequency": frequency, "bandwidth": bandwidth}
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
                        if payload and len(payload) > 0 and payload[0] == 0xFF:
                            if len(payload) >= 15:
                                error_code = struct.unpack('!I', payload[11:15])[0]
                                error_msg = payload[15:].decode('utf-8', errors='replace')
                                raise Exception(f"设备错误 {error_code}: {error_msg}")
                            raise Exception("设备返回未知错误")
                        service = DirectionService(client)
                        result = service._parse_df_response(payload)
                        result.update({'success': True, 'frequency': frequency, 'bandwidth': bandwidth})
                        return result
                    finally:
                        await client.disconnect()

                return run_async(do_df())
            finally:
                hook.end_context()

        elif operation == 'StartIFDirection' or operation.endswith('StartIFDirection'):
            # 中频测向
            frequency = int(params.get('Frequency', params.get('frequency', 100_000_000)))
            span = int(params.get('Span', params.get('span', 1_000_000)))
            ifbw = int(params.get('IFBW', params.get('ifbw', 100000)))

            hook = HookManager.get_instance()
            hook.start_context()

            try:
                error_resp = check_device_connected()
                if error_resp:
                    return {'success': False, 'error': '设备未连接'}

                hook.log_layer("atom", {
                    "interface": "/services (SOAP)",
                    "operation": "StartIFDirection",
                    "business_type": "0x13 (IFDF)",
                    "params": {"frequency": frequency, "span": span, "ifbw": ifbw}
                })

                async def do_ifdf():
                    client = get_device_client()
                    await client.connect()
                    try:
                        service = DirectionService(client)
                        return await service.start_ifdf(frequency, span, ifbw)
                    finally:
                        await client.disconnect()

                result = run_async(do_ifdf())
                result['success'] = True
                return result
            finally:
                hook.end_context()

        else:
            logger.warning(f"未知的SOAP操作: {operation}")
            return {'success': False, 'error': f'未知操作: {operation}'}

    except Exception as e:
        logger.error(f"处理SOAP请求失败: {e}")
        return {'success': False, 'error': str(e)}


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
