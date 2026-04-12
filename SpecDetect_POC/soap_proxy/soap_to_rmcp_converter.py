# -*- coding: utf-8 -*-
"""
SOAP → RMCP 转换器 (验证性实现)

功能:
1. 接收 SOAP XML
2. 解析参数
3. 构建 RMCP 帧 (含占位符)
4. 保存到本地

输出文件:
- {timestamp}_{operation}_soap.xml: 原始 SOAP XML
- {timestamp}_{operation}_predicted_rmcp.bin: 预测的 RMCP 帧

用于与 rmcp_proxy 捕获的实际 RMCP 帧对比
"""

import os
import struct
import xml.etree.ElementTree as ET
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Dict, Any, Optional

from soap_proxy.soap_rmcp_converter import (
    parse_soap_request,
    SOAP_FUNCID_MAP,
    FUNCID_SOAP_MAP,
)


class SOAPToRMCPConverter:
    """SOAP → RMCP 转换器"""

    def __init__(self, output_dir: str = "conversion_output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def _get_timestamp_str(self) -> str:
        """获取时间戳字符串 (精确到秒)"""
        return datetime.now().strftime("%Y%m%d_%H%M%S")

    def _create_filetime(self) -> bytes:
        """
        创建当前 UTC 时间的 FILETIME

        FILETIME: 从 1601-01-01 UTC 开始的 100纳秒间隔数
        返回: 8字节 little-endian FILETIME
        """
        now_utc = datetime.now(timezone.utc)
        ft_epoch = datetime(1601, 1, 1, tzinfo=timezone.utc)
        ft_value = int((now_utc - ft_epoch) / timedelta(microseconds=1)) * 10
        return struct.pack('<Q', ft_value)

    def _calculate_checksum(self, frame_header: bytes) -> int:
        """
        计算 RMCP 帧头校验和

        算法 (协议文档):
        1. length + timestamp (64位)
        2. 第一次折半移位: 高32位 + 低32位
        3. 第二次折半移位: 高16位 + 低16位 (循环直到 <= 0xFFFF)
        4. 取反码 (~result)
        """
        length = struct.unpack('<I', frame_header[0:4])[0]
        timestamp = struct.unpack('<Q', frame_header[4:12])[0]

        total = timestamp + length

        # 第一次折半移位
        high = (total >> 32) & 0xFFFFFFFF
        low = total & 0xFFFFFFFF
        result1 = high + low

        # 第二次折半移位 (循环处理溢出)
        result2 = (result1 >> 16) + (result1 & 0xFFFF)
        while result2 > 0xFFFF:
            result2 = ((result2 >> 16) & 0xFFFF) + (result2 & 0xFFFF)

        # 取反码
        return (~result2) & 0xFFFF

    def _ensure_output_dir(self) -> Path:
        """确保输出目录存在"""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        return self.output_dir

    def parse_operation_from_xml(self, xml_data: str) -> str:
        """从 XML 提取操作名"""
        import re

        # 模式: <srrc:B_XXX> 或 <srrc:requestbody>
        match = re.search(r'<[^:]+:(B_\w+)>', xml_data)
        if match:
            return match.group(1)

        match = re.search(r'<[^:]+:requestbody', xml_data)
        if match:
            tag = match.group(0)
            parts = tag.split(':')
            if len(parts) >= 2:
                return parts[1].replace('>', '').replace('requestbody', '')

        return "Unknown"

    def _build_action_xml(self, soap_xml: str) -> str:
        """
        将原始 SOAP XML 转换为 RMCP Action XML 格式

        SOAP 格式分类:
        1. xsi:nil (无参数): B_QueryDeviceInfo, B_QueryFaciDevStat, B_StopMeas
        2. items (单层): B_SglFreqMeas, B_SglFreqDF, B_FScanDF, B_MScanDF, B_PScan, B_WBDF
        3. groupitems (嵌套): B_FScan, B_MScan
        """
        root = ET.fromstring(soap_xml)
        ns = {'srrc': 'http://www.srrc.org.cn'}

        # 查找 requestbody
        requestbody = root.find('.//srrc:requestbody', ns)
        if requestbody is None:
            requestbody = root.find('.//requestbody')

        # 获取 mfid
        mfid = ''
        if requestbody is not None:
            mfid_elem = requestbody.find('srrc:mfid', ns)
            if mfid_elem is None:
                mfid_elem = requestbody.find('mfid')
            if mfid_elem is not None:
                mfid = mfid_elem.text or ''

        # stationid/deviceid
        if len(mfid) >= 8:
            stationid = mfid[:8]
        else:
            stationid = '53090001'
        deviceid = '00106'

        # 查找 equpara
        equpara = root.find('.//srrc:equpara', ns)
        if equpara is None:
            equpara = root.find('.//equpara')

        # 检查是否是 xsi:nil (无参数接口)
        is_nil = equpara is None or equpara.get('xsi:nil') == 'true' or equpara.get('{http://www.w3.org/2001/XMLSchema-instance}nil') == 'true'

        action_items = []
        funcid = 15  # 默认 B_FScan

        if not is_nil and equpara is not None:
            # 尝试 groupitems (嵌套结构: B_FScan, B_MScan)
            groupitems_elem = equpara.find('.//srrc:groupitems', ns)
            if groupitems_elem is None:
                groupitems_elem = equpara.find('.//groupitems')

            if groupitems_elem is not None:
                # 嵌套结构: groupitem > items > item
                for groupitem in groupitems_elem:
                    if groupitem.tag.endswith('groupitem'):
                        items_elem = groupitem.find('.//srrc:items', ns)
                        if items_elem is None:
                            items_elem = groupitem.find('.//items')
                        if items_elem is not None:
                            for item in items_elem:
                                self._parse_soap_item(item, action_items)
            else:
                # 单层 items 结构
                items_elem = equpara.find('.//srrc:items', ns)
                if items_elem is None:
                    items_elem = equpara.find('.//items')
                if items_elem is not None:
                    for item in items_elem:
                        self._parse_soap_item(item, action_items)

        # 检查 taskid (B_StopMeas 回显 taskid)
        has_taskid = requestbody is not None and requestbody.find('srrc:taskid', ns) is not None
        if requestbody is not None and requestbody.find('taskid') is not None:
            has_taskid = True

        # 从 action_items + 结构推断 funcid (根据参数特征)
        funcid = self._infer_funcid(action_items, is_nil, has_taskid)

        # 映射 SOAP 参数名 -> Action 参数名
        self._map_param_names(action_items)

        # 根据 funcid 过滤/调整参数
        self._adjust_params_by_funcid(action_items, funcid)

        # 格式化频率值 (Hz -> MHz/kHz)
        self._format_action_items(action_items)

        # 构建 Action XML
        items_xml = [f'<item name="{name}" value="{value}" />' for name, value in action_items]
        items_str = '\n            '.join(items_xml)

        action_xml = f'''<?xml version="1.0" encoding="gb2312" ?>
<action id="1">
    <parameter groups="1" stationid="{stationid}" deviceid="{deviceid}" devicename="MS845" funcid="{funcid}">
        <group index="0">
            {items_str}
        </group>
    </parameter>
</action>'''

        return action_xml

    def _parse_soap_item(self, item_elem, action_items: list):
        """解析 SOAP item 元素，提取 paraname/paravalue"""
        paraname = None
        paravalue = None
        for child in item_elem:
            if child.tag.endswith('paraname'):
                paraname = child.text
            elif child.tag.endswith('paravalue'):
                paravalue = child.text
        if paraname and paravalue is not None:
            action_items.append((paraname, paravalue))

    def _infer_funcid(self, action_items: list, is_nil: bool = False, has_taskid: bool = False) -> int:
        """
        根据 action_items + SOAP 结构推断 funcid

        SOAP 操作 ↔ funcid 映射:
        - B_FScan: startfreq+stopfreq+step (扫频, funcid=15)
        - B_MScan: 多组 startfreq+stopfreq+step (funcid=14)
        - B_SglFreqMeas: frequency (单频测量, funcid=12)
        - B_SglFreqDF: frequency+dfmode (单频测向, funcid=11)
        - B_FScanDF: startfreq+stopfreq+step+dfmode (funcid=21)
        - B_PScan: startfreq+stopfreq+step (频谱扫描, funcid=13)
        - B_WBDF: startfreq+stopfreq (宽带测向, funcid=17)
        - B_StopMeas: xsi:nil + taskid (funcid=32)
        - B_QueryDeviceInfo: xsi:nil (funcid=10)
        - B_QueryFaciDevStat: xsi:nil (funcid=?)

        判断优先级:
        1. xsi:nil + taskid -> B_StopMeas (32)
        2. xsi:nil -> B_QueryDeviceInfo (10) 或 B_QueryFaciDevStat
        3. frequency+dfmode -> B_SglFreqDF (11)
        4. frequency -> B_SglFreqMeas (12)
        5. dfmode -> B_FScanDF (21) or B_SglFreqDF
        6. startfreq+stopfreq+step -> B_FScan (15) or B_MScan (14)
        7. startfreq+stopfreq -> B_WBDF (17) or B_PScan (13)
        """
        names = {name for name, _ in action_items}

        # 优先级1: xsi:nil 格式
        if is_nil:
            if has_taskid:
                return 32  # B_StopMeas
            else:
                return 10  # B_QueryDeviceInfo (默认)

        # 优先级2: 单频测量
        if 'frequency' in names and 'dfmode' in names:
            return 11  # B_SglFreqDF
        elif 'frequency' in names:
            return 12  # B_SglFreqMeas

        # 优先级3: 扫频相关
        if 'startfreq' in names and 'stopfreq' in names and 'step' in names and 'dfmode' in names:
            return 21  # B_FScanDF
        elif 'startfreq' in names and 'stopfreq' in names and 'step' in names:
            # 区分 B_FScan 和 B_MScan 需要检查是否为 groupitems (多组)
            # 这里简化处理，默认 B_FScan
            return 15  # B_FScan
        elif 'startfreq' in names and 'stopfreq' in names:
            return 17  # B_WBDF
        elif 'startfreq' in names or 'stopfreq' in names:
            return 13  # B_PScan

        # 默认
        return 15

    # SOAP 参数名 -> Action 参数名 映射表
    SOAP_TO_ACTION_PARAM_MAP = {
        'gain': 'gainctrl',  # SOAP gain -> Action gainctrl
        # 可以添加其他映射...
    }

    def _map_param_names(self, action_items: list):
        """映射 SOAP 参数名到 Action 参数名"""
        for i, (name, value) in enumerate(action_items):
            if name in self.SOAP_TO_ACTION_PARAM_MAP:
                action_items[i] = (self.SOAP_TO_ACTION_PARAM_MAP[name], value)

    def _adjust_params_by_funcid(self, action_items: list, funcid: int):
        """
        根据 funcid 调整参数
        - 移除某些接口不需要的参数
        - Atom 会根据接口类型过滤参数
        """
        names = {name for name, _ in action_items}

        # B_SglFreqDF (11): 移除 dfmode (Atom 不发送)
        if funcid == 11 and 'dfmode' in names:
            action_items[:] = [(n, v) for n, v in action_items if n != 'dfmode']

        # B_WBDF (17): 可能需要调整参数
        # 其他接口如有特殊需求，在此处理

    def _format_action_items(self, action_items: list):
        """格式化 action_items 中的频率值"""
        for i, (name, value) in enumerate(action_items):
            try:
                val = int(value)
                if name in ('startfreq', 'stopfreq', 'frequency'):
                    # 频率格式化: Hz -> MHz
                    action_items[i] = (name, f"{val // 1000000}MHz")
                elif name == 'step':
                    action_items[i] = (name, f"{val // 1000}kHz")
                elif name == 'ifbw':
                    # ifbw 格式化: Hz -> kHz
                    action_items[i] = (name, f"{val // 1000}kHz")
            except (ValueError, TypeError):
                pass

    def build_rmcp_frame(self, soap_xml: str, funcid: int = 15) -> bytes:
        """
        构建 RMCP REQUEST 帧

        Args:
            soap_xml: SOAP XML 字符串
            funcid: 功能 ID

        Returns:
            RMCP 二进制帧
        """
        # 将 SOAP XML 转换为 Action XML 格式 (与 Atom 一致)
        action_xml = self._build_action_xml(soap_xml)

        # Action XML 编码为 GB2312
        xml_bytes = action_xml.encode('gb2312')

        # RMCP 帧头结构 (实测验证):
        # Bytes 0-3:   dwLength (4 bytes, little-endian)
        # Bytes 4-11:  tmStamp (8 bytes FILETIME, little-endian, 100ns间隔 since 1601-01-01)
        # Byte 12:     0x00
        # Byte 13:     nVersion (=7)
        # Byte 14:     nMsgType (=90 for REQUEST)
        # Byte 15:     nFlags (=1)
        # Bytes 16-17: nCheckSum (2 bytes, 占位)
        # Byte 18+:    SOAP XML (GB2312)

        # 计算总长度
        total_len = 19 + len(xml_bytes) + 1  # 帧头(19) + XML + null

        # 构建帧
        frame = bytearray()

        # dwLength (4 bytes, little-endian)
        frame.extend(struct.pack('<I', total_len))

        # Bytes 4-11: FILETIME (8 bytes, little-endian)
        frame.extend(self._create_filetime())

        # Byte 12: 0x00
        frame.append(0x00)

        # Byte 13: nVersion = 7
        frame.append(0x07)

        # Byte 14: nMsgType = 90 (REQUEST)
        frame.append(0x5A)

        # Byte 15: nFlags = 1
        frame.append(0x01)

        # Bytes 16-17: nCheckSum (先占位,稍后计算)
        checksum_pos = len(frame)
        frame.extend(bytes([0xCC, 0xCC]))

        # Byte 18: 0x00
        frame.append(0x00)

        # SOAP XML
        frame.extend(xml_bytes)

        # null 终止符
        frame.append(0x00)

        # 计算校验和并更新到帧头
        header_for_checksum = bytes(frame[:18])
        calculated_checksum = self._calculate_checksum(header_for_checksum)
        frame[checksum_pos:checksum_pos+2] = struct.pack('<H', calculated_checksum)

        return bytes(frame)

    def convert_and_save(self, xml_data: str, soap_action: str = None) -> Dict[str, Any]:
        """
        转换 SOAP XML 为 RMCP 帧并保存

        Args:
            xml_data: SOAP XML 字符串
            soap_action: SOAPAction header (如 "B_FScan")

        Returns:
            {
                'timestamp': 时间戳字符串,
                'operation': 操作名,
                'funcid': funcid,
                'soap_file': SOAP XML 文件路径,
                'rmcp_file': RMCP 帧文件路径,
                'parsed_params': 解析的参数
            }
        """
        timestamp = self._get_timestamp_str()
        operation = self.parse_operation_from_xml(xml_data)

        # 从 SOAPAction 确定 funcid
        funcid = 15
        if soap_action:
            # 去掉引号
            action_name = soap_action.strip('"')
            funcid = SOAP_FUNCID_MAP.get(action_name, 15)
            operation = action_name

        # 确保目录存在
        output_dir = self._ensure_output_dir()

        # 保存 SOAP XML
        soap_filename = f"{timestamp}_{operation}_soap.xml"
        soap_filepath = output_dir / soap_filename
        with open(soap_filepath, 'w', encoding='utf-8') as f:
            f.write(xml_data)

        # 构建 RMCP 帧
        rmcp_frame = self.build_rmcp_frame(xml_data, funcid)

        # 保存 RMCP 帧
        rmcp_filename = f"{timestamp}_{operation}_predicted_rmcp.bin"
        rmcp_filepath = output_dir / rmcp_filename
        with open(rmcp_filepath, 'wb') as f:
            f.write(rmcp_frame)

        result = {
            'timestamp': timestamp,
            'operation': operation,
            'funcid': funcid,
            'soap_file': str(soap_filepath),
            'rmcp_file': str(rmcp_filepath),
            'rmcp_hex': rmcp_frame.hex(),
        }

        print(f"[SOAP→RMCP] Converted: {operation} (funcid={funcid})")
        print(f"  SOAP: {soap_filepath}")
        print(f"  RMCP: {rmcp_filepath}")

        return result


def test_converter():
    """测试转换器"""
    # 读取实际 SOAP 请求
    soap_path = 'D:/arvin/claude_workspace/SpecDetect_V4/SpecDetect_POC/soap_proxy/logs/requests_20260411_1910/8ce334c8_req.xml'
    with open(soap_path, 'r', encoding='utf-8') as f:
        xml_data = f.read()

    converter = SOAPToRMCPConverter(output_dir='D:/arvin/claude_workspace/SpecDetect_V4/SpecDetect_POC/soap_proxy/conversion_output')
    result = converter.convert_and_save(xml_data)

    print("\n=== 转换结果 ===")
    for k, v in result.items():
        if k != 'parsed_params':
            print(f"  {k}: {v}")

    print("\n  parsed_params:")
    for k, v in result['parsed_params'].items():
        print(f"    {k}: {v}")


if __name__ == '__main__':
    test_converter()
