"""Mock Atom 配置 - 转发到 rmcp_proxy

Mock Atom 接收 SOAP 请求，转发到 rmcp_proxy (9996)
再由 rmcp_proxy 转发到远程 Device

使用方式:
    from config.settings_rmcp_proxy import SERVICES
"""

# =============================================================================
# 服务配置 - Mock Atom + rmcp_proxy
# =============================================================================

SERVICES = {
    'proxy': {
        'host': '0.0.0.0',
        'port': 8283,  # Mock Atom 监听端口（8282 被 Real Atom 占用）
        'debug': True
    },
    'atom': {
        'host': '127.0.0.1',
        'port': 8283,
        # 关键配置：转发到 rmcp_proxy
        'device_host': '127.0.0.1',  # rmcp_proxy 地址
        'device_port': 9996,           # rmcp_proxy 端口
        'timeout': 30.0
    },
    'mock_device': {
        'host': '127.0.0.1',
        'port': 9000,
        'scenario': 'normal'
    }
}

# =============================================================================
# 协议配置
# =============================================================================

PROTOCOL = {
    'rmcp_version': 0x0007,
    'timeout': 30.0,
    'retry': 3
}

# RMCPTP帧配置
RMCPTP_FRAME = {
    'header_size': 18,
    'version': 0x0007,
}

# 数据类型定义
RMCPTP_DATA_TYPE = {
    0x00: '监测业务数据',
    0x01: '音频描述头',
    0x02: '音频数据',
    0x03: '分发请求',
    0x04: '信息数据',
    0x06: '业务数据描述头',
}

# 业务数据类型 (RMCPTP v2.0 规范)
BUSINESS_DATA_TYPE = {
    0x10: 'SGLFREQ',      # 单频测量
    0x11: 'IFANALYSIS',   # 中频分析
    0x12: 'DF',           # 单频测向
    0x13: 'IFDF',         # 中频测向
    0x14: 'DFSEARCH',     # 搜索测向
    0x15: 'FSCAN',        # 频段扫描
    0x16: 'DSCAN',        # 数字扫描
    0x17: 'PSCAN',        # 频谱扫描
    0x18: 'SPANALYSIS',   # 频谱分析
    0x19: 'WBMONDF',      # 宽带监测测向
    0x1A: 'TDANALYSIS',   # 时域分析
    0x1C: 'WBFFTMon',     # 宽带FFT观测
    0x1D: 'DIGDEM',       # IQ数字解调
    0x1E: 'WBMSCAN',      # 宽带扫描
    0x1F: 'EDETN',        # 能量探测
    0x22: 'MODREC',       # 信号识别
    0x23: 'SINA',         # 信号告警
    0x24: 'ITUMEAS',      # ITU测量
    0x26: 'DDCDEM',       # DDC解调
    0x27: 'SSDF',         # 空间谱测向
    0x28: 'MULTICHAN',    # 多信道监听
    0x29: 'ACDF',         # 旋转云台
    0x2B: 'DEMREC',       # 调制模式识别
    0x2C: 'MULCHANANA',   # 双/多信道分析
    0x31: 'DPX',          # 荧光谱
    0x33: 'FREQMEAS',     # 频点分析
}

# 场景配置
SCENARIOS = {
    'normal': {
        'name': '常规监测',
        'frequency': 100_000_000,
        'amplitude': -60,
        'noise': -100
    },
}

# funcid 到 业务数据类型 映射
FUNCID_TO_BUSINESS_TYPE = {
    11: 0x10,  # B_SglFreqMeas -> SGLFREQ
    13: 0x12,  # B_SglFreqDF -> DF
    14: 0x14,  # B_MScan -> DFSEARCH
    15: 0x15,  # B_FScan -> FSCAN
    16: 0x17,  # B_PScan -> PSCAN
    21: 0x12,  # B_FScanDF -> DF
    25: 0x19,  # B_WBDF -> WBMONDF
    32: 0x13,  # B_MScanDF -> IFDF
}

# 接口到 funcid 映射
INTERFACE_TO_FUNCID = {
    'B_SglFreqMeas': 11,
    'B_SglFreqDF': 13,
    'B_MScan': 14,
    'B_FScan': 15,
    'B_PScan': 16,
    'B_FScanDF': 21,
    'B_WBDF': 25,
    'B_MScanDF': 32,
}
