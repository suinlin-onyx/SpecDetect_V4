# RMCP Proxy 配置

# 代理监听配置
PROXY_HOST = "127.0.0.1"
PROXY_PORT = 9996

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
