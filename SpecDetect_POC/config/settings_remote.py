"""Remote Real Atom 配置文件

用于连接远端 Real Atom (113.90.244.216:8282)

使用方式:
    from config.settings_remote import SERVICES as SERVICES_REMOTE
    from config.settings_remote import REMOTE_CONFIG
"""

# =============================================================================
# Remote Atom 配置
# =============================================================================

REMOTE_CONFIG = {
    'name': 'Remote Real Atom',
    'url': 'http://113.90.244.216:8282',
    'mfid': '53090001140012',
    'equid': '51cd8dfe-e543-40c9-bdc3-a292766fee7f',
    'timeout': 30,
}

# =============================================================================
# 服务配置 - 远端 Real Atom 连接
# =============================================================================

SERVICES = {
    'proxy': {
        'host': '0.0.0.0',
        'port': 8082,  # 使用独立端口避免冲突
        'debug': True
    },
    'atom': {
        'host': '113.90.244.216',
        'port': 8282,
        'device_host': '127.0.0.1',  # 设备层暂不关注
        'device_port': 9000
    },
    'remote': {
        'mfid': '53090001140012',
        'equid': '51cd8dfe-e543-40c9-bdc3-a292766fee7f',
        'userid': 'RX_admin',
        'appid': '123456',
        'executetime': '0',
        'priority': '9'
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
    0x10: 'SGLFREQ',
    0x11: 'IFANALYSIS',
    0x12: 'DF',
    0x13: 'IFDF',
    0x14: 'DFSEARCH',
    0x15: 'FSCAN',
    0x16: 'DSCAN',
    0x17: 'PSCAN',
    0x18: 'SPANALYSIS',
    0x19: 'WBMONDF',
    0x1A: 'TDANALYSIS',
    0x1C: 'WBFFTMon',
    0x1D: 'DIGDEM',
    0x1E: 'WBMSCAN',
    0x1F: 'EDETN',
    0x22: 'MODREC',
    0x23: 'SINA',
    0x24: 'ITUMEAS',
    0x26: 'DDCDEM',
    0x27: 'SSDF',
    0x28: 'MULTICHAN',
    0x29: 'ACDF',
    0x2B: 'DEMREC',
    0x2C: 'MULCHANANA',
    0x31: 'DPX',
    0x33: 'FREQMEAS',
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
