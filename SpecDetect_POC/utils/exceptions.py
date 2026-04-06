"""异常定义"""


class RMCPTPError(Exception):
    """RMCPTP协议基础异常"""
    pass


class ProtocolParseError(RMCPTPError):
    """协议解析错误"""
    pass


class ProtocolBuildError(RMCPTPError):
    """协议构建错误"""
    pass


class ChecksumError(ProtocolParseError):
    """校验和错误"""
    pass


class DeviceConnectionError(RMCPTPError):
    """设备连接错误"""
    pass


class DeviceTimeoutError(DeviceConnectionError):
    """设备超时错误"""
    pass


class SOAPParseError(Exception):
    """SOAP解析错误"""
    pass


class ServiceError(Exception):
    """服务基础异常"""
    pass


class ConfigurationError(ServiceError):
    """配置错误"""
    pass
