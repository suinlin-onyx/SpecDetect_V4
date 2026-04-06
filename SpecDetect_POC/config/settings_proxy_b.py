"""Proxy-B 配置文件

用于双Proxy并行模式 - Proxy-B (8081) 连接到 Real Atom

使用方式:
    from config.settings_proxy_b import SERVICES as SERVICES_B
    from config.settings_proxy_b import PROXY_B_CONFIG
"""

# =============================================================================
# Proxy-B 配置
# =============================================================================

PROXY_B_CONFIG = {
    'port': 8081,
    'log_file': 'logs/service_8081.log',
}

# =============================================================================
# 服务配置 - Real Atom 连接
# =============================================================================

# 注意: Real Atom 的地址需要在 CONFIG.md 中确认后填入
# 从 VHFMonitor_Python/flask_proxy.py 确认：
#   Real Atom: 127.0.0.1:8282
#   Mock Atom: 127.0.0.1:8288
REAL_ATOM_HOST = '127.0.0.1'
REAL_ATOM_PORT = 8282

SERVICES = {
    'proxy': {
        'host': '0.0.0.0',
        'port': 8081,
        'debug': True
    },
    'atom': {
        'host': REAL_ATOM_HOST,       # Real Atom 地址
        'port': REAL_ATOM_PORT,       # Real Atom 端口
        'device_host': '127.0.0.1',  # Device 地址（如果需要）
        'device_port': 9000
    },
    'mock_device': {
        'host': '127.0.0.1',
        'port': 9000,
        'scenario': 'normal'
    }
}

# =============================================================================
# 以下配置与 settings.py 保持一致
# =============================================================================

# 协议配置
PROTOCOL = {
    'rmcp_version': 0x0007,
    'timeout': 5.0,
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

# 业务数据类型 (RMCPTP v2.0 规范) - 与 settings.py 保持一致
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

# 场景配置 - 与 settings.py 保持一致
SCENARIOS = {
    'normal': {
        'name': '常规监测',
        'frequency': 100_000_000,
        'amplitude': -60,
        'noise': -100
    },
    'interference': {
        'name': '干扰场景',
        'signals': [
            {'freq': 100_000_000, 'amp': -50},
            {'freq': 100_500_000, 'amp': -70}
        ]
    },
    'abnormal': {
        'name': '异常场景',
        'failure_type': 'data_error'
    },
    'boundary': {
        'name': '边界场景',
        'frequency': 3_000_000_000,
        'amplitude': -120
    },
    'stress': {
        'name': '压力测试',
        'data_size': 10000
    }
}
