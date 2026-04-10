"""远端 Real Atom 接口测试脚本

测试远端 Real Atom 的所有接口，并保存真实回调数据

使用方式:
    python test_remote_atom.py --operation B_FScan        # 测试单个接口
    python test_remote_atom.py --operation B_FScan --with-stop  # 测试接口+停止
    python test_remote_atom.py --sequence B_FScan          # 按顺序测试（执行+停止）
    python test_remote_atom.py --list                     # 列出所有接口

输出:
    docs/REAL_ATOM_INTEGRATION/responses/
"""

import argparse
import json
import os
import sys
import time
from datetime import datetime
from lxml import etree

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from config.settings_remote import REMOTE_CONFIG, SERVICES

# 命名空间
SOAP_NS = 'http://schemas.xmlsoap.org/soap/envelope/'
SRRC_NS = 'http://www.srrc.org.cn'

# 远端 Atom 连接信息
REMOTE_URL = REMOTE_CONFIG['url']
MFID = REMOTE_CONFIG['mfid']
EQUID = REMOTE_CONFIG['equid']

# 输出目录
RESPONSES_DIR = os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    'docs', 'REAL_ATOM_INTEGRATION', 'responses'
)

# 接口列表（按文档顺序）
INTERFACES = [
    'B_FScan',
    'B_FScanDF',
    'B_MScan',
    'B_MScanDF',
    'B_PScan',
    'B_QueryDeviceInfo',
    'B_QueryFaciDevStat',
    'B_SglFreqDF',
    'B_SglFreqMeas',
    'B_StopMeas',
    'B_TaskModification',
    'B_WBDF',
]

# 接口描述
INTERFACE_DESC = {
    'B_FScan': '频段扫描',
    'B_FScanDF': '频段扫描测向',
    'B_MScan': '多信道扫描',
    'B_MScanDF': '多信道扫描测向',
    'B_PScan': '频谱扫描',
    'B_QueryDeviceInfo': '设备信息查询',
    'B_QueryFaciDevStat': '设备状态查询',
    'B_SglFreqDF': '单频测向',
    'B_SglFreqMeas': '单频测量',
    'B_StopMeas': '停止测量',
    'B_TaskModification': '任务修改',
    'B_WBDF': '宽带测向',
}

# 需要配对停止的接口
STOP_REQUIRED = {
    'B_FScan', 'B_FScanDF', 'B_MScan', 'B_MScanDF',
    'B_PScan', 'B_SglFreqDF', 'B_SglFreqMeas', 'B_WBDF'
}


def build_minimal_request() -> str:
    """构建最小化请求（只有 mfid + equid）"""
    root = etree.Element(
        f'{{{SOAP_NS}}}Envelope',
        nsmap={'soapenv': SOAP_NS, 'srrc': SRRC_NS}
    )
    body = etree.SubElement(root, f'{{{SOAP_NS}}}Body')
    request_body = etree.SubElement(body, f'{{{SRRC_NS}}}requestbody')
    etree.SubElement(request_body, f'{{{SRRC_NS}}}mfid').text = MFID
    etree.SubElement(request_body, f'{{{SRRC_NS}}}equid').text = EQUID
    return etree.tostring(root, pretty_print=True, encoding='utf-8', xml_declaration=True).decode('utf-8')


def build_full_request(operation: str, params: dict = None) -> str:
    """构建完整请求（所有基础字段+equpara+resulttype+outputchannel）

    Args:
        operation: 接口名称
        params: 参数字典

    Returns:
        SOAP XML 字符串
    """
    params = params or {}

    root = etree.Element(
        f'{{{SOAP_NS}}}Envelope',
        nsmap={'soapenv': SOAP_NS, 'srrc': SRRC_NS}
    )
    body = etree.SubElement(root, f'{{{SOAP_NS}}}Body')
    request_body = etree.SubElement(body, f'{{{SRRC_NS}}}requestbody')

    # 基础字段
    remote_cfg = SERVICES['remote']
    etree.SubElement(request_body, f'{{{SRRC_NS}}}userid').text = remote_cfg['userid']
    etree.SubElement(request_body, f'{{{SRRC_NS}}}appid').text = remote_cfg['appid']
    etree.SubElement(request_body, f'{{{SRRC_NS}}}executetime').text = remote_cfg['executetime']
    etree.SubElement(request_body, f'{{{SRRC_NS}}}priority').text = remote_cfg['priority']
    etree.SubElement(request_body, f'{{{SRRC_NS}}}mfid').text = MFID
    etree.SubElement(request_body, f'{{{SRRC_NS}}}equid').text = EQUID

    # 构建 equpara
    equpara = etree.SubElement(request_body, f'{{{SRRC_NS}}}equpara')

    if operation == 'B_FScan':
        # resulttype: FSCAN, equpara: groupitems
        groupitems = etree.SubElement(equpara, f'{{{SRRC_NS}}}groupitems')
        groupitem = etree.SubElement(groupitems, f'{{{SRRC_NS}}}groupitem')
        etree.SubElement(groupitem, f'{{{SRRC_NS}}}groupid').text = '1'
        group_items = etree.SubElement(groupitem, f'{{{SRRC_NS}}}items')
        add_item(group_items, 'startfreq', 137000000)
        add_item(group_items, 'stopfreq', 173000000)
        add_item(group_items, 'step', 25000)
        add_item(group_items, 'gain', 'AGC')
        add_item(group_items, 'rfworkmode', '0')
        add_item(group_items, 'scanmode', '0')
        add_resulttype(request_body, 'FSCAN')

    elif operation == 'B_FScanDF':
        # resulttype: WBDF, equpara: items
        items = etree.SubElement(equpara, f'{{{SRRC_NS}}}items')
        add_item(items, 'startfreq', 137000000)
        add_item(items, 'stopfreq', 173000000)
        add_item(items, 'step', 25000)
        add_item(items, 'rfworkmode', '0')
        add_item(items, 'gain', 'AGC')
        add_resulttype(request_body, 'WBDF')

    elif operation == 'B_MScan':
        # resulttype: MSCAN, equpara: groupitems
        groupitems = etree.SubElement(equpara, f'{{{SRRC_NS}}}groupitems')
        groupitem = etree.SubElement(groupitems, f'{{{SRRC_NS}}}groupitem')
        etree.SubElement(groupitem, f'{{{SRRC_NS}}}groupid').text = '1'
        group_items = etree.SubElement(groupitem, f'{{{SRRC_NS}}}items')
        add_item(group_items, 'frequency', 100000000)
        add_item(group_items, 'ifbw', 40000000)
        add_item(group_items, 'gain', 'AGC')
        add_item(group_items, 'rfworkmode', '0')
        add_resulttype(request_body, 'MSCAN')

    elif operation == 'B_MScanDF':
        # resulttype: (空), equpara: items
        items = etree.SubElement(equpara, f'{{{SRRC_NS}}}items')
        add_item(items, 'frequency', 100000000)
        add_item(items, 'dfmode', '1')
        add_item(items, 'ifbw', 40000000)
        add_item(items, 'gain', 'AGC')
        add_item(items, 'rfworkmode', '0')
        # resulttype 为空

    elif operation == 'B_PScan':
        # resulttype: PSCAN, equpara: items
        items = etree.SubElement(equpara, f'{{{SRRC_NS}}}items')
        add_item(items, 'startfreq', 137000000)
        add_item(items, 'stopfreq', 173000000)
        add_item(items, 'step', 25000)
        add_item(items, 'gain', 'AGC')
        add_item(items, 'rfworkmode', '0')
        add_item(items, 'keepmode', '0')
        add_resulttype(request_body, 'PSCAN')

    elif operation == 'B_SglFreqDF':
        # resulttype: SFDF + audio, equpara: items
        items = etree.SubElement(equpara, f'{{{SRRC_NS}}}items')
        add_item(items, 'frequency', 100000000)
        add_item(items, 'dfmode', '1')
        add_item(items, 'ifbw', 40000000)
        add_item(items, 'gain', 'AGC')
        add_item(items, 'rfworkmode', '0')
        add_item(items, 'dftype', '0')
        add_item(items, 'spectrumswitch', 'on')
        add_resulttype(request_body, 'SFDF', add_audio=True)

    elif operation == 'B_SglFreqMeas':
        # resulttype: ITU + audio, equpara: items
        items = etree.SubElement(equpara, f'{{{SRRC_NS}}}items')
        add_item(items, 'frequency', 100000000)
        add_item(items, 'ifbw', 40000000)
        add_item(items, 'gain', 'AGC')
        add_item(items, 'rfworkmode', '0')
        add_item(items, 'audiotype', 'off')
        add_item(items, 'demodmode', 'FM')
        add_item(items, 'demodbw', 200000)
        add_item(items, 'spectrumswitch', 'on')
        add_item(items, 'ITUSwitch', 'on')
        add_resulttype(request_body, 'ITU', add_audio=True)

    elif operation == 'B_WBDF':
        # resulttype: WBDF, equpara: items
        items = etree.SubElement(equpara, f'{{{SRRC_NS}}}items')
        add_item(items, 'frequency', 100000000)
        add_item(items, 'ifbw', 40000000)
        add_item(items, 'gain', 'AGC')
        add_item(items, 'rfworkmode', '0')
        add_resulttype(request_body, 'WBDF')

    # outputchannel
    outputchannel = etree.SubElement(request_body, f'{{{SRRC_NS}}}outputchannel')
    etree.SubElement(outputchannel, f'{{{SRRC_NS}}}mode').text = 'source'
    etree.SubElement(outputchannel, f'{{{SRRC_NS}}}datachannel').text = 'stream'
    etree.SubElement(outputchannel, f'{{{SRRC_NS}}}host').text = ''
    etree.SubElement(outputchannel, f'{{{SRRC_NS}}}port').text = ''
    etree.SubElement(outputchannel, f'{{{SRRC_NS}}}stc').text = ''

    return etree.tostring(root, pretty_print=True, encoding='utf-8', xml_declaration=True).decode('utf-8')


def add_item(parent: etree._Element, paraname: str, paravalue) -> None:
    """向 items 添加一个参数项"""
    item = etree.SubElement(parent, f'{{{SRRC_NS}}}item')
    etree.SubElement(item, f'{{{SRRC_NS}}}paraname').text = paraname
    etree.SubElement(item, f'{{{SRRC_NS}}}paravalue').text = str(paravalue)


def add_resulttype(request_body, type_name: str, add_audio: bool = False) -> None:
    """添加 resulttype"""
    resulttype = etree.SubElement(request_body, f'{{{SRRC_NS}}}resulttype')
    etree.SubElement(resulttype, f'{{{SRRC_NS}}}{type_name}')
    if add_audio:
        etree.SubElement(resulttype, f'{{{SRRC_NS}}}audio')


def build_request(operation: str) -> str:
    """根据接口类型构建请求

    Args:
        operation: 接口名称

    Returns:
        SOAP XML 字符串
    """
    # 最小化格式接口
    minimal_ops = {'B_QueryFaciDevStat', 'B_StopMeas'}
    if operation in minimal_ops:
        return build_minimal_request()

    # 完整格式接口
    return build_full_request(operation)


def send_request(operation: str) -> tuple:
    """发送请求到远端 Atom

    Args:
        operation: 接口名称

    Returns:
        (响应文本, 耗时, 成功标志)
    """
    url = f"{REMOTE_URL}/{operation}"
    soap_request = build_request(operation)

    print(f"\n{'='*60}")
    print(f"接口: {operation} ({INTERFACE_DESC.get(operation, '未知')})")
    print(f"URL: {url}")
    print(f"{'='*60}")
    print(f"请求:\n{soap_request}")

    try:
        start_time = time.time()
        response = requests.post(
            url,
            data=soap_request,
            headers={'Content-Type': 'text/xml; charset=utf-8'},
            timeout=REMOTE_CONFIG.get('timeout', 30)
        )
        elapsed = time.time() - start_time

        print(f"\n响应状态: HTTP {response.status_code}")
        print(f"响应时间: {elapsed:.2f}秒")
        print(f"\n响应:\n{response.text}")

        return response.text, elapsed, True

    except requests.RequestException as e:
        print(f"\n请求失败: {e}")
        return str(e), 0, False


def parse_response(xml_response: str) -> dict:
    """解析 SOAP 响应"""
    try:
        root = etree.fromstring(xml_response.encode('utf-8'))
    except etree.XMLSyntaxError as e:
        return {'success': False, 'error': f'XML解析失败: {e}', 'raw': xml_response}

    body = root.find(f'{{{SOAP_NS}}}Body')
    if body is None:
        return {'success': False, 'error': '未找到 SOAP Body', 'raw': xml_response}

    result = {'success': True, 'raw_xml': xml_response}

    # 查找 responsebody
    responsebody = body.find(f'{{{SRRC_NS}}}responsebody')
    if responsebody is None:
        for child in body:
            if 'responsebody' in child.tag.lower():
                responsebody = child
                break

    if responsebody is not None:
        # 检查错误
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
            for child in result_elem:
                tag_name = child.tag.split('}')[1] if '}' in child.tag else child.tag
                if child.text:
                    result[tag_name] = child.text

    # 检查 Header 中的 bizResCd
    envelope = body.getparent().getparent()
    header = envelope.find(f'{{{SOAP_NS}}}Header') if envelope is not None else None
    if header is not None:
        provider_response = header.find(f'{{{SRRC_NS}}}ProviderResponse')
        if provider_response is not None:
            biz_res_cd = provider_response.find(f'{{{SRRC_NS}}}bizResCd')
            biz_res_text = provider_response.find(f'{{{SRRC_NS}}}bizResText')
            if biz_res_cd is not None:
                result['bizResCd'] = biz_res_cd.text
                result['success'] = biz_res_cd.text == 'BIZ-000001'
            if biz_res_text is not None:
                result['bizResText'] = biz_res_text.text

    return result


def save_response(operation: str, result: dict, suffix: str = '') -> str:
    """保存响应到文件"""
    os.makedirs(RESPONSES_DIR, exist_ok=True)

    if suffix:
        filename = f"{operation}_{suffix}_response.json"
    else:
        filename = f"{operation}_response.json"

    filepath = os.path.join(RESPONSES_DIR, filename)

    result['operation'] = operation
    result['timestamp'] = datetime.now().isoformat()

    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)

    print(f"\n已保存: {filepath}")
    return filepath


def test_single(operation: str, with_stop: bool = False) -> dict:
    """测试单个接口

    Args:
        operation: 接口名称
        with_stop: 是否自动发送停止请求

    Returns:
        测试结果字典
    """
    print(f"\n{'#'*60}")
    print(f"# 测试接口: {operation}")
    print(f"{'#'*60}")

    # 发送请求
    response_text, elapsed, success = send_request(operation)

    result = {
        'operation': operation,
        'success': success,
        'elapsed_time': elapsed,
        'response': response_text
    }

    if success:
        parsed = parse_response(response_text)
        result.update(parsed)

    # 保存响应
    save_response(operation, result)

    # 如果需要停止
    if with_stop and operation in STOP_REQUIRED:
        print(f"\n{'='*60}")
        print(f"# 发送停止请求: B_StopMeas")
        print(f"{'='*60}")

        time.sleep(3)  # 等待

        stop_response, stop_elapsed, stop_success = send_request('B_StopMeas')
        stop_result = {
            'operation': 'B_StopMeas',
            'success': stop_success,
            'elapsed_time': stop_elapsed,
            'response': stop_response
        }

        if stop_success:
            stop_parsed = parse_response(stop_response)
            stop_result.update(stop_parsed)

        save_response(operation, stop_result, suffix='stop')
        result['stop_result'] = stop_result

    return result


def test_sequence(operations: list = None) -> list:
    """按顺序测试接口（执行+停止配对）

    Args:
        operations: 接口列表，默认为全部 INTERFACES

    Returns:
        测试结果列表
    """
    if operations is None:
        operations = INTERFACES

    results = []

    for op in operations:
        # 判断是否需要停止配对
        need_stop = op in STOP_REQUIRED

        result = test_single(op, with_stop=need_stop)
        results.append(result)

        # 等待后再进行下一个
        if need_stop:
            time.sleep(3)  # 停止后等待
        else:
            time.sleep(3)  # 查询接口也等待

    return results


def list_interfaces():
    """列出所有可用接口"""
    print("\n可用接口列表:")
    print("-" * 50)
    for i, op in enumerate(INTERFACES, 1):
        need_stop = "需要停止" if op in STOP_REQUIRED else "独立接口"
        print(f"  {i:2d}. {op:25s} - {INTERFACE_DESC.get(op, ''):15s} [{need_stop}]")
    print()


def main():
    parser = argparse.ArgumentParser(
        description='远端 Real Atom 接口测试脚本',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument('--operation', '-o', type=str, default=None,
                        help='指定测试的接口 (如 B_FScan)')
    parser.add_argument('--with-stop', action='store_true',
                        help='测试接口后自动发送停止请求')
    parser.add_argument('--sequence', '-s', action='store_true',
                        help='按顺序测试所有接口（执行+停止配对）')
    parser.add_argument('--list', '-l', action='store_true',
                        help='列出所有可用接口')
    parser.add_argument('--nosave', action='store_true',
                        help='不保存响应到文件')

    args = parser.parse_args()

    # 列出接口
    if args.list:
        list_interfaces()
        return

    # 显示配置
    print(f"\n远端 Real Atom 测试")
    print(f"URL: {REMOTE_URL}")
    print(f"mfid: {MFID}")
    print(f"equid: {EQUID}")
    print(f"保存响应: {not args.nosave}")

    results = []

    if args.sequence:
        # 按顺序测试所有接口
        results = test_sequence()

    elif args.operation:
        # 测试单个接口
        if args.operation not in INTERFACES:
            print(f"\n错误: 未知接口 '{args.operation}'")
            list_interfaces()
            return

        result = test_single(args.operation, with_stop=args.with_stop)
        results.append(result)

    else:
        print("\n错误: 请指定 --operation 或 --sequence")
        list_interfaces()
        return

    # 打印汇总
    print(f"\n{'='*60}")
    print("测试汇总")
    print(f"{'='*60}")
    success_count = sum(1 for r in results if r.get('success', False))
    print(f"总测试数: {len(results)}")
    print(f"成功: {success_count}")
    print(f"失败: {len(results) - success_count}")

    for r in results:
        status = "✅" if r.get('success', False) else "❌"
        biz = r.get('bizResCd', 'N/A')
        print(f"  {status} {r.get('operation')}: {biz}")


if __name__ == '__main__':
    main()
