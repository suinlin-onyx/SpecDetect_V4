"""SOAP数据模型"""
from dataclasses import dataclass
from typing import Optional, Dict, Any


@dataclass
class SOAPRequest:
    """SOAP请求模型"""
    operation: str
    params: Dict[str, Any]
    raw_xml: Optional[str] = None


@dataclass
class SOAPResponse:
    """SOAP响应模型"""
    success: bool
    data: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    raw_xml: Optional[str] = None
