"""SOAP Proxy 日志记录器"""
import os
import uuid
import json
from datetime import datetime
from pathlib import Path


class SOAPProxyLogger:
    """SOAP 请求/响应日志记录器"""

    def __init__(self, log_dir: str = "logs/soap_proxy"):
        self.log_dir = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        # 当天日志文件（加小时分钟）
        self.date_str = datetime.now().strftime("%Y%m%d_%H%M")
        self.log_file = self.log_dir / f"soap_proxy_{self.date_str}.log"
        self.req_dir = self.log_dir / f"requests_{self.date_str}"
        self.req_dir.mkdir(exist_ok=True)

    def _get_timestamp(self) -> str:
        """获取微秒级时间戳"""
        return datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")

    def _append_log(self, content: str):
        """追加到日志文件"""
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(content + "\n")

    def log_request(self, request_id: str, operation: str, xml_data: str, headers: dict):
        """记录 SOAP 请求

        Args:
            request_id: 请求唯一标识
            operation: 操作名称
            xml_data: 请求 XML
            headers: 请求头
        """
        timestamp = self._get_timestamp()

        # 写入汇总日志
        log_entry = f"""[SOAP Request] {timestamp}
Request-ID: {request_id}
Operation: {operation}
Headers: {json.dumps(dict(headers), ensure_ascii=False)}
---
{xml_data}
---
"""
        self._append_log(log_entry)

        # 保存完整 XML
        req_file = self.req_dir / f"{request_id}_req.xml"
        with open(req_file, "w", encoding="utf-8") as f:
            f.write(xml_data)

    def log_response(self, request_id: str, operation: str, xml_data: str, status_code: int):
        """记录 SOAP 响应

        Args:
            request_id: 请求唯一标识（关联请求）
            operation: 操作名称
            xml_data: 响应 XML
            status_code: HTTP 状态码
        """
        timestamp = self._get_timestamp()

        # 写入汇总日志
        log_entry = f"""[SOAP Response] {timestamp}
Request-ID: {request_id}
Operation: {operation}
Status: {status_code}
---
{xml_data}
---

"""
        self._append_log(log_entry)

        # 保存完整 XML
        res_file = self.req_dir / f"{request_id}_res.xml"
        with open(res_file, "w", encoding="utf-8") as f:
            f.write(xml_data)

    def log_error(self, request_id: str, operation: str, error: str):
        """记录错误

        Args:
            request_id: 请求唯一标识
            operation: 操作名称
            error: 错误信息
        """
        timestamp = self._get_timestamp()
        log_entry = f"""[SOAP Error] {timestamp}
Request-ID: {request_id}
Operation: {operation}
Error: {error}
---
"""
        self._append_log(log_entry)

    def extract_operation(self, xml_data: str) -> str:
        """从 XML 中提取操作名称

        Args:
            xml_data: SOAP XML 字符串

        Returns:
            操作名称
        """
        import re

        # 模式1: <srrc:requestbody> -> 提取 "requestbody"
        match = re.search(r'<[^:]+:requestbody', xml_data)
        if match:
            tag = match.group(0)  # e.g., "<srrc:requestbody>"
            parts = tag.split(':')
            if len(parts) >= 2:
                return parts[1].replace('>', '').replace('requestbody', '')

        # 模式2: <srrc:B_XXX> 形式 - 执行接口
        match = re.search(r'<[^:]+:(B_\w+)>', xml_data)
        if match:
            return match.group(1)

        # 模式3: 直接查找 B_ 开头的标签
        match = re.search(r'<[^:]+:(B_\w+)\s', xml_data)
        if match:
            return match.group(1)

        # 模式4: 从 SOAPAction header 提取 (最后备用)
        # SOAPAction: "B_QueryDeviceInfo" 或 'B_QueryDeviceInfo'
        match = re.search(r'SOAPAction[:\s]+["\']?([B_]\w+)["\']?', xml_data)
        if match:
            action = match.group(1)
            return action

        return "Unknown"
