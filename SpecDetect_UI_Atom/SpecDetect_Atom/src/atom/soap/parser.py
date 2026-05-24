# -*- coding: utf-8 -*-
"""
SOAP 解析模块

负责解析 HTTP + SOAP 请求
"""

import re
from typing import Optional, Dict, Tuple


def parse_http_header(data: bytes) -> Tuple[Optional[Dict], bytes]:
    """解析 HTTP 头"""
    try:
        text = data.decode('utf-8', errors='replace')
    except Exception:
        return None, data

    # 兼容 CRLF 和 LF 换行
    parts = text.split('\r\n\r\n', 1)
    if len(parts) < 2:
        parts = text.split('\n\n', 1)
    if len(parts) < 2:
        return None, data

    header_text = parts[0]
    body = parts[1].encode('utf-8') if isinstance(data, bytes) else parts[1]

    lines = header_text.replace('\r\n', '\n').split('\n')
    if not lines:
        return None, data

    request_line = lines[0]
    match = re.match(r'(GET|POST)\s+(\S+)\s+HTTP/(\d+\.\d+)', request_line)
    if not match:
        return None, data

    method = match.group(1)
    path = match.group(2)
    version = match.group(3)

    headers = {
        'method': method,
        'path': path,
        'version': version,
        'SOAPAction': None
    }

    for line in lines[1:]:
        if ':' in line:
            key, value = line.split(':', 1)
            key = key.strip()
            value = value.strip()
            headers[key.lower()] = value
            if key.lower() == 'soapaction':
                headers['SOAPAction'] = value.strip('"\'')

    return headers, body


def _extract_from_soap_action(text: str) -> Optional[str]:
    """从 SOAPAction header 提取操作名称"""
    match = re.search(r'SOAPAction:\s*"?([^"\n]+)"?', text, re.IGNORECASE)
    if match:
        action = match.group(1).strip()
        if '#' in action:
            action = action.split('#')[-1]
        return action
    return None


def _extract_method_from_xml(body_content: str, soap_action: str = None) -> tuple:
    """从 XML Body 内容提取方法名

    优先从 SOAPAction header 提取（最可靠），其次从 XML body 提取。
    """
    # 优先从 SOAPAction 提取
    if soap_action:
        # SOAPAction: "http://www.srrc.org.cn/B_FScan" 或 "B_FScan"
        action = soap_action.split('/')[-1].strip('"\'')
        known_interfaces = {
            'B_FScan', 'B_PScan', 'B_MScan', 'B_StopMeas', 'B_QueryDeviceInfo',
            'B_SglFreqMeas', 'B_QueryFaciDevStat', 'B_TaskModification',
            'B_FScanRequest', 'B_PScanRequest', 'B_FScanDFRequest'
        }
        if action in known_interfaces:
            return action, None

    # 其次从 XML body 提取（作为备用）
    known_interfaces_list = [
        'B_FScan', 'B_PScan', 'B_MScan', 'B_StopMeas', 'B_QueryDeviceInfo',
        'B_SglFreqMeas', 'B_QueryFaciDevStat', 'B_TaskModification',
        'B_FScanRequest', 'B_PScanRequest', 'B_FScanDFRequest'
    ]

    body_stripped = body_content.strip()

    for iface in known_interfaces_list:
        match = re.search(rf'<(\w+):{iface}\b', body_stripped)
        if match:
            return iface, match.group(1)

    for iface in known_interfaces_list:
        match = re.search(rf'<{iface}\b', body_stripped)
        if match:
            return iface, None

    return None, None


def parse_soap_body(body: bytes, soap_action_header: str = None) -> Optional[Dict]:
    """解析 SOAP Body"""
    try:
        text = body.decode('utf-8', errors='replace')
    except Exception:
        return None

    body_match = re.search(r'<[^>]*:Body[^>]*>(.+)</[^>]*:Body>', text, re.IGNORECASE | re.DOTALL)
    if not body_match:
        return None

    body_content = body_match.group(1)

    method, ns = _extract_method_from_xml(body_content, soap_action_header)

    result = {
        'soap_action': soap_action_header,
        'method': method,
        'namespace': ns,
        'body': body_content
    }

    for field in ['taskid', 'mfid', 'equid', 'appid', 'userid', 'priority']:
        pattern = f'<[^>]*:{field}[^>]*>([^<]+)</[^>]*:{field}>'
        match = re.search(pattern, body_content, re.IGNORECASE)
        if match:
            result[field] = match.group(1).strip()

    params = ['startfreq', 'stopfreq', 'step', 'gain', 'rfworkmode', 'scanmode', 'dfmode']
    for param in params:
        pattern = f'<[^>]*:{param}[^>]*>([^<]+)</[^>]*:{param}>'
        match = re.search(pattern, body_content, re.IGNORECASE)
        if match:
            result[param] = match.group(1).strip()

    equpara_match = re.search(r'<[^>]*:equpara[^>]*>(.+)</[^>]*:equpara>', body_content, re.IGNORECASE | re.DOTALL)
    if equpara_match:
        result['equpara'] = equpara_match.group(1)

    # 解析 outputchannel 字段
    outputchannel_match = re.search(
        r'<[^>]*:outputchannel[^>]*>(.+)</[^>]*:outputchannel>',
        body_content, re.IGNORECASE | re.DOTALL
    )
    if outputchannel_match:
        outputchannel_content = outputchannel_match.group(1)
        outputchannel = {}

        # 解析 outputchannel 子字段
        for field in ['mode', 'datachannel', 'host', 'port', 'stc']:
            pattern = f'<[^>]*:{field}[^>]*>([^<]+)</[^>]*:{field}>'
            match = re.search(pattern, outputchannel_content, re.IGNORECASE)
            if match:
                value = match.group(1).strip()
                # port 字段转换为整数
                if field == 'port':
                    try:
                        value = int(value)
                    except ValueError:
                        pass
                outputchannel[field] = value

        # 只有当所有必需字段都存在时才添加到结果
        required_fields = {'mode', 'datachannel', 'host', 'port', 'stc'}
        if required_fields.issubset(outputchannel.keys()):
            result['outputchannel'] = outputchannel

    return result


def extract_soap_request(data: bytes) -> Optional[Dict]:
    """提取完整的 SOAP 请求信息"""
    headers, body = parse_http_header(data)
    if not headers:
        return None

    soap_action = headers.get('SOAPAction')

    soap_body = parse_soap_body(body, soap_action)
    if not soap_body:
        return None

    return {
        'headers': headers,
        'body': body,
        'soap_action': soap_body.get('soap_action'),
        'method': soap_body.get('method'),
        'namespace': soap_body.get('namespace'),
        'params': {k: v for k, v in soap_body.items()
                   if k not in ('soap_action', 'method', 'namespace', 'body', 'equpara')}
    }