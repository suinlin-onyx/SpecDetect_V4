"""双通道响应差异分析工具

提供格式化输出和差异分析功能，可独立使用或被 dual_request.py 调用。

使用方式:
    python diff_output.py --file dual_request_result_xxx.json
    python diff_output.py --result_a "..." --result_b "..."
"""
import argparse
import sys
import os
import json
from typing import Dict, Any, Optional, List

# 添加项目根目录到路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from lxml import etree

# SOAP 命名空间
SOAP_NS = 'http://schemas.xmlsoap.org/soap/envelope/'
MON_NS = 'http://monitor.rrmp.gov.cn/services/'


class DiffAnalyzer:
    """响应差异分析器"""

    def __init__(self):
        pass

    def parse_soap_response(self, xml_text: str) -> Dict[str, Any]:
        """解析SOAP响应"""
        try:
            root = etree.fromstring(xml_text.encode('utf-8'))
        except etree.XMLSyntaxError as e:
            return {'success': False, 'error': f'XML解析失败: {e}'}

        body = root.find(f'{{{SOAP_NS}}}Body')
        if body is None:
            return {'success': False, 'error': '未找到SOAP Body'}

        fault = body.find(f'{{{SOAP_NS}}}Fault')
        if fault is not None:
            faultstring = fault.find('faultstring')
            error_msg = faultstring.text if faultstring is not None else 'Unknown error'

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

        response = body.find(f'{{{MON_NS}}}Response')
        if response is None:
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
                result['data'] = {}
                for data_child in child:
                    data_tag = data_child.tag.split('}')[1] if '}' in data_child.tag else data_child.tag
                    result['data'][data_tag] = data_child.text
            else:
                result[tag_name] = child.text

        return result

    def compute_field_diff(self, dict_a: Dict, dict_b: Dict, path: str = "") -> List[Dict]:
        """递归计算两个字典之间的字段差异

        Args:
            dict_a: 第一个字典
            dict_b: 第二个字典
            path: 当前路径（用于嵌套结构）

        Returns:
            差异列表
        """
        diffs = []

        all_keys = set(dict_a.keys()) | set(dict_b.keys())

        for key in all_keys:
            current_path = f"{path}.{key}" if path else key
            val_a = dict_a.get(key)
            val_b = dict_b.get(key)

            if isinstance(val_a, dict) and isinstance(val_b, dict):
                diffs.extend(self.compute_field_diff(val_a, val_b, current_path))
            elif val_a != val_b:
                diffs.append({
                    'path': current_path,
                    'mock_value': val_a,
                    'real_value': val_b,
                    'type': 'value_diff'
                })

        return diffs

    def analyze(self, result_a: Dict[str, Any], result_b: Dict[str, Any]) -> Dict[str, Any]:
        """分析两个响应结果的差异

        Args:
            result_a: Proxy-A (Mock Atom) 响应
            result_b: Proxy-B (Real Atom) 响应

        Returns:
            差异分析结果
        """
        analysis = {
            'success_a': result_a.get('success', False),
            'success_b': result_b.get('success', False),
            'success_match': result_a.get('success') == result_b.get('success'),
            'error_a': result_a.get('error'),
            'error_b': result_b.get('error'),
            'fields_diff': [],
            'summary': ''
        }

        # 计算字段差异
        if analysis['success_match'] and result_a.get('success'):
            # 两者都成功，比较数据字段
            data_a = result_a.get('data', {})
            data_b = result_b.get('data', {})

            if data_a and data_b:
                analysis['fields_diff'] = self.compute_field_diff(data_a, data_b)
            elif data_a != data_b:
                analysis['fields_diff'] = [{
                    'path': 'data',
                    'mock_value': data_a,
                    'real_value': data_b,
                    'type': 'data_diff'
                }]
        elif not analysis['success_match']:
            # 一个成功一个失败
            status_a = '成功' if result_a.get('success') else '失败'
            status_b = '成功' if result_b.get('success') else '失败'
            analysis['summary'] = f'Mock Atom {status_a}, Real Atom {status_b}'

            # 比较错误信息
            if result_a.get('error') != result_b.get('error'):
                analysis['fields_diff'].append({
                    'path': 'error',
                    'mock_value': result_a.get('error'),
                    'real_value': result_b.get('error'),
                    'type': 'error_diff'
                })
        else:
            # 两者都失败
            analysis['summary'] = f'双方都失败'

        return analysis


def format_analysis_report(analysis: Dict[str, Any], operation: str = "") -> str:
    """格式化差异分析报告

    Args:
        analysis: DiffAnalyzer.analyze() 返回的分析结果
        operation: 操作名称

    Returns:
        格式化的报告字符串
    """
    lines = []

    header = "响应差异分析报告"
    if operation:
        header += f" - {operation}"
    lines.append("=" * 70)
    lines.append(header)
    lines.append("=" * 70)

    lines.append("\n【状态对比】")
    lines.append(f"  Mock Atom (Proxy-A): {'成功' if analysis['success_a'] else '失败'}")
    lines.append(f"  Real Atom (Proxy-B): {'成功' if analysis['success_b'] else '失败'}")
    lines.append(f"  状态匹配: {'是' if analysis['success_match'] else '否'}")

    if not analysis['success_match']:
        lines.append("\n【错误信息】")
        if analysis['error_a']:
            lines.append(f"  Mock Atom: {analysis['error_a']}")
        if analysis['error_b']:
            lines.append(f"  Real Atom: {analysis['error_b']}")

    if analysis['fields_diff']:
        lines.append("\n【字段差异】")
        for diff in analysis['fields_diff']:
            lines.append(f"  {diff['path']}:")
            lines.append(f"    Mock: {diff['mock_value']}")
            lines.append(f"    Real: {diff['real_value']}")

    lines.append("\n" + "=" * 70)

    return '\n'.join(lines)


def load_result_from_json(filepath: str) -> Dict[str, Any]:
    """从JSON文件加载结果"""
    with open(filepath, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    parser = argparse.ArgumentParser(
        description='双通道响应差异分析工具',
        formatter_class=argparse.RawDescriptionHelpFormatter
    )

    parser.add_argument('--file', '-f',
                        help='dual_request.py 生成的JSON结果文件')
    parser.add_argument('--result_a',
                        help='Proxy-A (Mock Atom) 的原始响应 XML')
    parser.add_argument('--result_b',
                        help='Proxy-B (Real Atom) 的原始响应 XML')
    parser.add_argument('--operation', '-o', default='',
                        help='操作名称（可选）')

    args = parser.parse_args()

    analyzer = DiffAnalyzer()

    if args.file:
        # 从文件加载结果
        result = load_result_from_json(args.file)
        result_a = result['proxy_a']['parsed']
        result_b = result['proxy_b']['parsed']
        operation = result.get('operation', '')
    elif args.result_a and args.result_b:
        # 直接解析响应
        result_a = analyzer.parse_soap_response(args.result_a)
        result_b = analyzer.parse_soap_response(args.result_b)
        operation = args.operation
    else:
        print("错误: 必须提供 --file 或同时提供 --result_a 和 --result_b")
        return 1

    # 分析差异
    analysis = analyzer.analyze(result_a, result_b)

    # 输出报告
    report = format_analysis_report(analysis, operation)
    print(report)

    return 0


if __name__ == '__main__':
    sys.exit(main())
