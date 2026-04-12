"""配置文件"""

# 服务配置
SERVICES = {
    'proxy': {
        'host': '0.0.0.0',
        'port': 8080,
        'debug': True
    },
    'atom': {
        'host': '127.0.0.1',
        'port': 9090,
        'device_host': '172.18.114.33',  # Real Device RMCPTP 地址
        'device_port': 8282,              # Real Device RMCPTP 端口
        'streamsrc_host': '127.0.0.1',    # streamsrc 监听地址
        'streamsrc_port': 18012            # streamsrc 监听端口
    },
    'mock_device': {
        'host': '127.0.0.1',
        'port': 9000,
        'scenario': 'normal'
    }
}

# 协议配置
PROTOCOL = {
    'rmcp_version': 0x0007,
    'timeout': 10.0,
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

# 日志配置
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'default': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        },
        'detailed': {
            'format': '%(asctime)s - %(name)s - %(levelname)s - [%(filename)s:%(lineno)d] - %(message)s'
        }
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'level': 'INFO',
            'formatter': 'default',
            'stream': 'ext://sys.stdout'
        },
        'file': {
            'class': 'logging.FileHandler',
            'level': 'DEBUG',
            'formatter': 'detailed',
            'filename': 'logs/app.log',
            'mode': 'a'
        }
    },
    'loggers': {
        'proxy': {'level': 'DEBUG', 'handlers': ['console', 'file']},
        'atom': {'level': 'DEBUG', 'handlers': ['console', 'file']},
        'mock': {'level': 'DEBUG', 'handlers': ['console', 'file']},
    },
    'root': {
        'level': 'INFO',
        'handlers': ['console']
    }
}
