# RMCP Proxy 配置

# 代理监听配置
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 9996
PROXY_PORT_2 = 9997  # 第二个监听端口（可选）

# 日志输出配置
ENABLE_JSON_OUTPUT = True  # 设为 False 禁用 .json 文件输出
ENABLE_RAW_OUTPUT = True    # 设为 False 禁用 .raw 文件输出
ENABLE_CONNECTIONS_CSV = True  # 设为 False 禁用 connections CSV 文件输出

# 已淘汰目标设备配置
# 100.89.170.72:9997
# 113.90.246.139:1449

# 现行可用的目标设备配置
# 100.72.95.36:1449
DEVICE_HOST = "100.72.95.36"
DEVICE_PORT = 1449

# 日志配置
LOG_DIR = "D:/arvin/claude_workspace/SpecDetect_V4/SpecDetect_POC/rmcp_proxy/capture"
LOG_LEVEL = "DEBUG"  # DEBUG, INFO, WARNING, ERROR

# 帧头大小
RMCP_FRAME_HEADER_SIZE = 18

# 消息类型
MSG_TYPE_REQUEST = 90    # 0x5A - 设备控制请求
MSG_TYPE_RESPONSE = 6    # 响应消息
MSG_TYPE_DATA_1 = 29     # 0x1D - 数据帧类型1
MSG_TYPE_DATA_2 = 95     # 0x5F - 数据帧类型2

# =============================================================================
# 接口映射配置 (根据实测校正)
# 注意: funcid (SOAP请求) 与 nBdType (RMCP回调) 是两个独立标识符
# =============================================================================

# =============================================================================
# SOAP接口映射 (funcid -> SOAP接口名)
# 来源: 协议文档 + 实测校正
# =============================================================================
# funcid -> SOAP接口名称
FUNCID_TO_NAME = {
    11: 'B_SglFreqMeas',  # 单频测量 (XML: frequency/ifbw/demodmode)
    12: 'B_FScan',        # 频段扫描 (XML: startfreq/stopfreq/step)
    14: 'B_MScan',        # 离散扫描 (XML: frequency/ifbw)
    15: 'B_FScan',        # 频段扫描 (XML: startfreq/stopfreq/step, 同时返回DSCAN)
    16: 'B_PScan',        # 频谱扫描 (XML: startfreq/stopfreq/step)
    # 待实测: B_WBDF(funcid=25), B_MScanDF(funcid=32)
}

# =============================================================================
# RMCP回调映射 (nBdType -> RMCP回调类型名)
# 来源: 协议文档 + 实测校正
# =============================================================================
# nBdType (payload[0]) -> RMCP回调类型名称
NBDTYPE_TO_NAME = {
    0x0B: 'IFANALYSIS',  # 中频分析 (funcid=11, demodmode=FM)
    0x0E: 'SGLFREQ',     # 单频测量 (funcid=11/14, frequency模式)
    0x0F: 'FSCAN',       # 频段扫描 (funcid=15)
    0x10: 'DSCAN',       # 数字扫描 (funcid=15伴随返回)
    0x01: 'PSCAN',       # 频谱扫描 (funcid=16, 实测1671B帧)
    # 注意: nBdType=0x01是PSCAN数据帧, nBdType=0x10(51B)是PSCAN的响应帧
}

# 文档标准定义 vs 实测差异
# 文档中: PSCAN=0x11, 实测: PSCAN=0x01

# =============================================================================
# 文档标准定义 (供参考，设备固件可能不一致)
# =============================================================================

# 文档标准定义 (供参考，设备固件可能不一致)
DOC_NBDTYPE_STANDARD = {
    10: 'SGLFREQ',      # 单频测量
    11: 'IFANALYSIS',   # 中频分析
    12: 'DF',           # 单频测向
    13: 'IFDF',         # 中频测向
    14: 'MSACN',        # 离散扫描
    15: 'FSCAN',        # 频段扫描
    16: 'DSCAN',        # 数字扫描
    17: 'PSCAN',        # 频谱扫描(保留)
    18: 'SPANALYSIS',   # 频谱分析
    19: 'TDANALYSIS',   # 时域分析
}
