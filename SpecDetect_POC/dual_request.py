"""双通道对比请求工具

同时向 Proxy-A (Mock Atom) 和 Proxy-B (Real Atom) 发送相同请求，
对比响应差异。

使用方式:
    python dual_request.py --service sglfreq --freq 100000000
    python dual_request.py --service ifanalysis --freq 100000000 --span 1000000
    python dual_request.py --service fscan --start 100000000 --end 200000000 --step 1000000
"""
import argparse
import sys
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Optional, Tuple

import requests
from lxml import etree

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from utils.logger import setup_logger

logger = setup_logger('dual_request')

# 代理地址
PROXY_A_URL = "http://127.0.0.1:8080"
PROXY_B_URL = "http://127.0.0.1:8081"  # Proxy-B (routes to Real Atom at 8282)

# SOAP 命名空间
SOAP_NS = 'http://schemas.xmlsoap.org/soap/envelope/'
MON_NS = 'http://monitor.rrmp.gov.cn/services/'


def build_soap_request(operation: str, params: Dict[str, Any]) -> str:
    """构建SOAP请求 XML

    Args:
        operation: 操作名称 (SGLFREQ, IFANALYSIS, FSCAN, DF, IFDF)
        params: 参数字典

    Returns:
        SOAP XML字符串
    """
    root = etree.Element(
        f'{{{SOAP_NS}}}Envelope',
        nsmap={'soap': SOAP_NS, 'mon': MON_NS}
    )
    body = etree.SubElement(root, f'{{{SOAP_NS}}}Body')

    req = etree.SubElement(body, f'{{{MON_NS}}}{operation}')

    for key, value in params.items():
        elem = etree.SubElement(req, f'{{{MON_NS}}}{key}')
        elem.text = str(value)

    return etree.tostring(root, pretty_print=True, encoding='utf-8', xml_declaration=True).decode('utf-8')


def parse_soap_response(xml_text: str) -> Dict[str, Any]:
    """解析SOAP响应

    Args:
        xml_text: SOAP XML响应字符串

    Returns:
        解析后的数据字典
    """
    try:
        root = etree.fromstring(xml_text.encode('utf-8'))
    except etree.XMLSyntaxError as e:
        return {'success': False, 'error': f'XML解析失败: {e}'}

    body = root.find(f'{{{SOAP_NS}}}Body')
    if body is None:
        return {'success': False, 'error': '未找到SOAP Body'}

    # 检查是否有 Fault
    fault = body.find(f'{{{SOAP_NS}}}Fault')
    if fault is not None:
        faultstring = fault.find('faultstring')
        error_msg = faultstring.text if faultstring is not None else 'Unknown error'

        # 尝试获取详细错误码
        detail = fault.find('detail')
        if detail is not None:
            error_detail = detail.find(f'{{{MON_NS}}}ErrorDetail')
            if error_detail is not None:
                error_code = error_detail.find(f'{{{MON_NS}}}ErrorCode')
                error_message = error_detail.find(f'{{{MON_NS}}}ErrorMessage')
                return {
                    'success': False,
                    'error': error_msg,
                    'error_code': error_code.text if error_code is not None else None,
                    'error_message': error_message.text if error_message is not None else error_msg
                }
        return {'success': False, 'error': error_msg}

    # 解析 Response
    response = body.find(f'{{{MON_NS}}}Response')
    if response is None:
        # 尝试查找任意Response元素
        for child in body:
            if child.tag.endswith('}Response') or child.tag == 'Response':
                response = child
                break
        else:
            return {'success': False, 'error': '未找到Response元素'}

    result = {'success': True}

    for child in response:
        tag_name = child.tag.split('}')[1] if '}' in child.tag else child.tag
        if tag_name in ('ResultCode', 'ResultMessage'):
            result[tag_name] = child.text
        elif tag_name == 'Data':
            # Data 元素包含业务数据
            result['data'] = {}
            for data_child in child:
                data_tag = data_child.tag.split('}')[1] if '}' in data_child.tag else data_child.tag
                result['data'][data_tag] = data_child.text
        else:
            result[tag_name] = child.text

    return result


def send_request(url: str, operation: str, params: Dict[str, Any], timeout: int = 120) -> Tuple[str, Dict[str, Any]]:
    """发送SOAP请求

    Args:
        url: Proxy URL
        operation: 操作名称
        params: 参数
        timeout: 超时时间(秒)

    Returns:
        (raw_xml_response, parsed_result)
    """
    soap_request = build_soap_request(operation, params)

    logger.info(f"发送请求到 {url}")
    logger.debug(f"SOAP请求:\n{soap_request}")

    try:
        response = requests.post(
            f"{url}/soap",
            data=soap_request.encode('utf-8'),
            headers={'Content-Type': 'text/xml; charset=utf-8'},
            timeout=timeout
        )

        raw_xml = response.text
        parsed = parse_soap_response(raw_xml)

        logger.info(f"响应: success={parsed.get('success')}, error={parsed.get('error', 'N/A')}")

        return raw_xml, parsed

    except requests.RequestException as e:
        logger.error(f"请求失败: {e}")
        return "", {'success': False, 'error': str(e)}


def send_dual_request(operation: str, params: Dict[str, Any]) -> Dict[str, Any]:
    """同时向两个Proxy发送请求并对比结果

    Args:
        operation: 操作名称
        params: 参数

    Returns:
        包含两个通道响应和差异分析的字典
    """
    results = {
        'operation': operation,
        'params': params,
        'proxy_a': {'url': f"{PROXY_A_URL}/soap"},
        'proxy_b': {'url': f"{PROXY_B_URL}/soap"},
        'timestamp': time.strftime('%Y-%m-%d %H:%M:%S')
    }

    # 并行发送请求
    with ThreadPoolExecutor(max_workers=2) as executor:
        future_a = executor.submit(send_request, PROXY_A_URL, operation, params)
        future_b = executor.submit(send_request, PROXY_B_URL, operation, params)

        raw_a, parsed_a = future_a.result()
        raw_b, parsed_b = future_b.result()

    results['proxy_a']['raw_response'] = raw_a
    results['proxy_a']['parsed'] = parsed_a
    results['proxy_b']['raw_response'] = raw_b
    results['proxy_b']['parsed'] = parsed_b

    # 计算差异
    results['diff'] = compute_diff(parsed_a, parsed_b)

    return results


def compute_diff(parsed_a: Dict[str, Any], parsed_b: Dict[str, Any]) -> Dict[str, Any]:
    """计算两个响应之间的差异

    Args:
        parsed_a: Proxy-A (Mock Atom) 解析后的响应
        parsed_b: Proxy-B (Real Atom) 解析后的响应

    Returns:
        差异分析字典
    """
    diff = {
        'success_match': parsed_a.get('success') == parsed_b.get('success'),
        'fields_diff': [],
        'summary': ''
    }

    # 比较字段
    all_keys = set(parsed_a.keys()) | set(parsed_b.keys())
    all_keys.discard('success')  # 单独比较

    for key in all_keys:
        val_a = parsed_a.get(key)
        val_b = parsed_b.get(key)

        if val_a != val_b:
            diff['fields_diff'].append({
                'field': key,
                'mock_value': val_a,
                'real_value': val_b
            })

    # 生成摘要
    if parsed_a.get('success') and parsed_b.get('success'):
        diff['summary'] = '双方都成功'
    elif not parsed_a.get('success') and not parsed_b.get('success'):
        diff['summary'] = f'双方都失败: {parsed_a.get("error", "N/A")} vs {parsed_b.get("error", "N/A")}'
    else:
        mock_status = '成功' if parsed_a.get('success') else '失败'
        real_status = '成功' if parsed_b.get('success') else '失败'
        diff['summary'] = f'Mock Atom {mock_status}, Real Atom {real_status}'

    return diff


def format_dual_result(result: Dict[str, Any]) -> str:
    """格式化双通道结果输出

    Args:
        result: send_dual_request 返回的结果

    Returns:
        格式化的字符串
    """
    lines = []
    lines.append("=" * 70)
    lines.append(f"双通道对比结果 - {result['operation']}")
    lines.append(f"时间: {result['timestamp']}")
    lines.append("=" * 70)

    lines.append("\n【请求参数】")
    for key, value in result['params'].items():
        lines.append(f"  {key}: {value}")

    lines.append("\n【Proxy-A (Mock Atom)】")
    lines.append(f"  URL: {result['proxy_a']['url']}")
    parsed_a = result['proxy_a']['parsed']
    lines.append(f"  成功: {parsed_a.get('success')}")
    if parsed_a.get('success'):
        if 'data' in parsed_a:
            lines.append("  数据:")
            for k, v in parsed_a['data'].items():
                lines.append(f"    {k}: {v}")
    else:
        lines.append(f"  错误: {parsed_a.get('error')}")

    lines.append("\n【Proxy-B (Real Atom)】")
    lines.append(f"  URL: {result['proxy_b']['url']}")
    parsed_b = result['proxy_b']['parsed']
    lines.append(f"  成功: {parsed_b.get('success')}")
    if parsed_b.get('success'):
        if 'data' in parsed_b:
            lines.append("  数据:")
            for k, v in parsed_b['data'].items():
                lines.append(f"    {k}: {v}")
    else:
        lines.append(f"  错误: {parsed_b.get('error')}")

    lines.append("\n【差异分析】")
    diff = result['diff']
    lines.append(f"  状态匹配: {'是' if diff['success_match'] else '否'}")
    lines.append(f"  摘要: {diff['summary']}")

    if diff['fields_diff']:
        lines.append("  字段差异:")
        for field_diff in diff['fields_diff']:
            lines.append(f"    {field_diff['field']}:")
            lines.append(f"      Mock: {field_diff['mock_value']}")
            lines.append(f"      Real: {field_diff['real_value']}")

    lines.append("\n【原始响应】")
    lines.append("  Proxy-A (Mock Atom):")
    for line in result['proxy_a']['raw_response'].split('\n')[:10]:
        lines.append(f"    {line}")
    if len(result['proxy_a']['raw_response'].split('\n')) > 10:
        lines.append("    ...")

    lines.append("  Proxy-B (Real Atom):")
    for line in result['proxy_b']['raw_response'].split('\n')[:10]:
        lines.append(f"    {line}")
    if len(result['proxy_b']['raw_response'].split('\n')) > 10:
        lines.append("    ...")

    lines.append("\n" + "=" * 70)

    return '\n'.join(lines)


# =============================================================================
# 命令行参数解析
# =============================================================================

SERVICE_CONFIGS = {
    'sglfreq': {
        'operation': 'StartMeasure',
        'params': [
            {'name': 'freq', 'type': int, 'default': 100_000_000, 'help': '频率 (Hz)'},
            {'name': 'bandwidth', 'type': int, 'default': 120_000, 'help': '带宽 (Hz)'},
        ],
        'help': '单点频率测量 (SGLFREQ)'
    },
    'ifanalysis': {
        'operation': 'StartIFAnalysis',
        'params': [
            {'name': 'freq', 'type': int, 'default': 100_000_000, 'help': '频率 (Hz)'},
            {'name': 'span', 'type': int, 'default': 1_000_000, 'help': '跨度 (Hz)'},
            {'name': 'ifbw', 'type': int, 'default': 100_000, 'help': '中频带宽 (Hz)'},
        ],
        'help': '中频分析 (IFANALYSIS)'
    },
    'fscan': {
        'operation': 'StartScan',
        'params': [
            {'name': 'start', 'type': int, 'default': 100_000_000, 'help': '起始频率 (Hz)'},
            {'name': 'end', 'type': int, 'default': 200_000_000, 'help': '结束频率 (Hz)'},
            {'name': 'step', 'type': int, 'default': 1_000_000, 'help': '步进 (Hz)'},
        ],
        'help': '频谱扫描 (FSCAN)'
    },
    'df': {
        'operation': 'StartDirection',
        'params': [
            {'name': 'freq', 'type': int, 'default': 100_000_000, 'help': '频率 (Hz)'},
            {'name': 'bandwidth', 'type': int, 'default': 120_000, 'help': '带宽 (Hz)'},
        ],
        'help': '测向功能 (DF)'
    },
    'ifdf': {
        'operation': 'StartIFDirection',
        'params': [
            {'name': 'freq', 'type': int, 'default': 100_000_000, 'help': '频率 (Hz)'},
            {'name': 'span', 'type': int, 'default': 1_000_000, 'help': '跨度 (Hz)'},
            {'name': 'ifbw', 'type': int, 'default': 100_000, 'help': '中频带宽 (Hz)'},
        ],
        'help': '中频测向 (IFDF)'
    },
}


def main():
    parser = argparse.ArgumentParser(
        description='双通道对比请求工具 - 同时测试 Mock Atom 和 Real Atom',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python dual_request.py --service sglfreq --freq 100000000
  python dual_request.py --service ifanalysis --freq 100000000 --span 2000000
  python dual_request.py --service fscan --start 100000000 --end 200000000 --step 500000

服务类型:
  sglfreq    - 单点频率测量 (StartMeasure)
  ifanalysis - 中频分析 (StartIFAnalysis)
  fscan      - 频谱扫描 (StartScan)
  df         - 测向功能 (StartDirection)
  ifdf       - 中频测向 (StartIFDirection)
        """
    )

    parser.add_argument('--service', '-s', required=True,
                        choices=list(SERVICE_CONFIGS.keys()),
                        help='服务类型')

    # 添加所有可能的参数（带默认值）
    all_params = {}
    for service_name, config in SERVICE_CONFIGS.items():
        for param in config['params']:
            all_params[param['name']] = param

    for param_name, param_info in all_params.items():
        parser.add_argument(f"--{param_name}", type=param_info['type'],
                           default=None,
                           help=f"{param_info['help']}")

    args = parser.parse_args()

    # 验证服务类型并获取配置
    service_config = SERVICE_CONFIGS[args.service]

    # 使用默认值填充未提供的参数
    params = {}
    for param in service_config['params']:
        value = getattr(args, param['name'], None)
        params[param['name'].capitalize()] = value if value is not None else param['default']

    operation = service_config['operation']

    print(f"\n准备发送 {operation} 请求到双通道...")
    print(f"参数: {params}\n")

    # 发送双通道请求
    result = send_dual_request(operation, params)

    # 输出结果
    output = format_dual_result(result)
    print(output)

    # 保存结果到文件
    import json
    output_file = f"dual_request_result_{int(time.time())}.json"
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n结果已保存到: {output_file}")

    return 0 if result['diff']['success_match'] else 1


if __name__ == '__main__':
    sys.exit(main())
