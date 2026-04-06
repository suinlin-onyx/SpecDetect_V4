# 超短波监测管理一体化服务系统
# 详细设计说明书（LLD）

| 版本 | 日期 | 作者 | 审核 | 变更内容 |
|------|------|------|------|----------|
| 1.0 | 2026-04-04 | AI Assistant | - | 初版创建 |

---

## 1. 文档概述

### 1.1 目的

本文档为超短波监测管理一体化服务系统的详细设计说明书，定义核心模块的类结构、函数逻辑、算法流程和异常处理机制。

### 1.2 范围

本文档涵盖以下详细设计内容：
- 核心类设计
- 函数逻辑说明
- 算法描述
- 关键流程
- 变量字典
- 异常处理

---

## 2. 核心类设计

### 2.1 代理服务层类设计

#### 2.1.1 SOAP处理类

```csharp
// 命名空间: ProxyService.SOAP
namespace ProxyService.SOAP
{
    /// <summary>
    /// SOAP消息处理器
    /// 职责: 解析SOAP请求、构建SOAP响应、处理SOAP Fault
    /// </summary>
    public class SoapMessageHandler
    {
        // ==================== 核心属性 ====================
        
        /// <summary>
        /// SOAP版本 (1.1 或 1.2)
        /// </summary>
        public SoapVersion Version { get; set; }
        
        /// <summary>
        /// SOAP命名空间管理器
        /// </summary>
        public XmlNamespaceManager NamespaceManager { get; }
        
        /// <summary>
        /// 认证服务
        /// </summary>
        private IAuthService _authService;
        
        // ==================== 核心方法 ====================
        
        /// <summary>
        /// 解析SOAP请求消息
        /// </summary>
        /// <param name="xmlContent">原始XML内容</param>
        /// <returns>解析后的请求对象</returns>
        /// <exception cref="SoapException">SOAP解析异常</exception>
        public SoapRequest ParseRequest(string xmlContent)
        {
            // 1. XML格式验证
            ValidateXmlFormat(xmlContent);
            
            // 2. SOAP信封解析
            var xmlDoc = new XmlDocument();
            xmlDoc.LoadXml(xmlContent);
            
            // 3. 提取Header
            var header = ParseHeader(xmlDoc);
            
            // 4. 提取Body
            var body = ParseBody(xmlDoc);
            
            // 5. 构建请求对象
            return new SoapRequest
            {
                Version = Version,
                Header = header,
                Body = body,
                RawXml = xmlContent
            };
        }
        
        /// <summary>
        /// 构建SOAP响应消息
        /// </summary>
        /// <param name="response">响应对象</param>
        /// <returns>SOAP XML字符串</returns>
        public string BuildResponse(SoapResponse response)
        {
            var xmlDoc = new XmlDocument();
            var envelope = CreateSoapEnvelope(xmlDoc, Version);
            
            // 添加Header
            if (response.Header != null)
            {
                var headerNode = envelope.AppendChild(xmlDoc.CreateElement("soap", "Header", GetSoapNamespace()));
                // Header内容...
            }
            
            // 添加Body
            var bodyNode = envelope.AppendChild(xmlDoc.CreateElement("soap", "Body", GetSoapNamespace()));
            SerializeResponseBody(bodyNode, response.Body);
            
            return xmlDoc.OuterXml;
        }
        
        /// <summary>
        /// 处理SOAP Fault
        /// </summary>
        public string BuildFault(int errorCode, string errorMessage, string detail = null)
        {
            var faultInfo = new SoapFault
            {
                Code = $"mon:Error{errorCode}",
                Reason = errorMessage,
                Detail = detail
            };
            
            return SerializeFault(faultInfo);
        }
    }
    
    /// <summary>
    /// SOAP版本枚举
    /// </summary>
    public enum SoapVersion
    {
        Version11 = 1,
        Version12 = 2
    }
    
    /// <summary>
    /// SOAP请求对象
    /// </summary>
    public class SoapRequest
    {
        public SoapVersion Version { get; set; }
        public SoapHeader Header { get; set; }
        public XmlElement Body { get; set; }
        public string RawXml { get; set; }
    }
    
    /// <summary>
    /// SOAP响应对象
    /// </summary>
    public class SoapResponse
    {
        public SoapHeader Header { get; set; }
        public object Body { get; set; }
        public bool IsSuccess { get; set; }
        public string ErrorMessage { get; set; }
    }
}
```

#### 2.1.2 路由分发类

```csharp
// 命名空间: ProxyService.Routing
namespace ProxyService.Routing
{
    /// <summary>
    /// 服务路由器
    /// 职责: 根据请求参数路由到对应的原子服务
    /// </summary>
    public class ServiceRouter
    {
        // ==================== 核心属性 ====================
        
        /// <summary>
        /// 路由规则表 (MFID+EQUID -> ServiceInstance)
        /// Key: "MFID:EQUID", Value: ServiceInstance
        /// </summary>
        private ConcurrentDictionary<string, ServiceInstance> _routeTable;
        
        /// <summary>
        /// 负载均衡器
        /// </summary>
        private ILoadBalancer _loadBalancer;
        
        /// <summary>
        /// 服务注册表
        /// </summary>
        private IServiceRegistry _serviceRegistry;
        
        // ==================== 核心方法 ====================
        
        /// <summary>
        /// 执行路由分发
        /// </summary>
        /// <param name="request">SOAP请求</param>
        /// <returns>目标服务实例</returns>
        public async Task<ServiceInstance> RouteAsync(SoapRequest request)
        {
            // 1. 解析服务类型和设备标识
            var routingKey = ParseRoutingKey(request);
            
            // 2. 查询路由表
            var instance = await FindServiceInstanceAsync(routingKey);
            
            if (instance == null)
            {
                // 3. 服务发现
                instance = await DiscoverServiceAsync(routingKey);
            }
            
            // 4. 负载均衡选择
            if (instance is IServiceGroup group)
            {
                instance = _loadBalancer.Select(group);
            }
            
            // 5. 健康检查
            if (!await IsHealthyAsync(instance))
            {
                // 故障转移
                instance = await FailoverAsync(routingKey, instance);
            }
            
            return instance;
        }
        
        /// <summary>
        /// 解析路由键
        /// </summary>
        /// <remarks>
        /// 路由键格式: {ServiceType}:{MFID}:{EQUID}
        /// 示例: SglFreqMeasure:44010001:A01
        /// </remarks>
        private RoutingKey ParseRoutingKey(SoapRequest request)
        {
            var body = request.Body;
            
            return new RoutingKey
            {
                ServiceType = GetElementValue(body, "ServiceType"),
                Mfid = GetElementValue(body, "StationID"),
                Equid = GetElementValue(body, "EquipmentID"),
                SubEquid = GetElementValue(body, "SubEquipmentID") ?? "00"
            };
        }
        
        /// <summary>
        /// 故障转移处理
        /// </summary>
        private async Task<ServiceInstance> FailoverAsync(
            RoutingKey key, 
            ServiceInstance failedInstance)
        {
            _logger.LogWarning($"Service {failedInstance.Id} failed, initiating failover");
            
            // 1. 从路由表移除故障实例
            var routeKey = $"{key.Mfid}:{key.Equid}";
            _routeTable.TryRemove(routeKey, out _);
            
            // 2. 发现备用服务
            var backupInstance = await DiscoverServiceAsync(key);
            
            if (backupInstance != null)
            {
                // 3. 更新路由表
                _routeTable[routeKey] = backupInstance;
                return backupInstance;
            }
            
            throw new ServiceUnavailableException($"No available service for {routeKey}");
        }
    }
    
    /// <summary>
    /// 路由键
    /// </summary>
    public class RoutingKey
    {
        public string ServiceType { get; set; }
        public string Mfid { get; set; }
        public string Equid { get; set; }
        public string SubEquid { get; set; }
        
        public override string ToString()
        {
            return $"{ServiceType}:{Mfid}:{Equid}:{SubEquid}";
        }
    }
    
    /// <summary>
    /// 服务实例
    /// </summary>
    public class ServiceInstance
    {
        public string Id { get; set; }
        public string Host { get; set; }
        public int Port { get; set; }
        public ServiceType Type { get; set; }
        public bool IsHealthy { get; set; }
        public int ActiveConnections { get; set; }
    }
}
```

### 2.2 原子服务层类设计

#### 2.2.1 设备通信类

```csharp
// 命名空间: AtomService.Device
namespace AtomService.Device
{
    /// <summary>
    /// 设备通信管理器
    /// 职责: 管理TCP连接、发送命令、接收数据
    /// </summary>
    public class DeviceCommunicator : IDisposable
    {
        // ==================== 常量定义 ====================
        
        private const int DEFAULT_TIMEOUT_MS = 5000;
        private const int HEARTBEAT_INTERVAL_MS = 30000;
        private const int MAX_RETRY_COUNT = 3;
        private const byte PROTOCOL_VERSION = 0x07;
        
        // ==================== 核心属性 ====================
        
        /// <summary>
        /// 连接状态
        /// </summary>
        public ConnectionState State => _connectionState;
        
        /// <summary>
        /// 设备标识
        /// </summary>
        public DeviceIdentifier DeviceId { get; private set; }
        
        private TcpClient _tcpClient;
        private NetworkStream _stream;
        private readonly object _sendLock = new object();
        private volatile ConnectionState _connectionState;
        
        // ==================== 连接管理 ====================
        
        /// <summary>
        /// 建立设备连接
        /// </summary>
        /// <param name="host">设备IP地址</param>
        /// <param name="port">端口号</param>
        public async Task ConnectAsync(string host, int port)
        {
            if (_connectionState == ConnectionState.Connected)
            {
                return;
            }
            
            try
            {
                _tcpClient = new TcpClient();
                
                // 设置连接超时
                using (var cts = new CancellationTokenSource(DEFAULT_TIMEOUT_MS))
                {
                    await _tcpClient.ConnectAsync(host, port, cts.Token);
                }
                
                _stream = _tcpClient.GetStream();
                _stream.ReadTimeout = DEFAULT_TIMEOUT_MS;
                _stream.WriteTimeout = DEFAULT_TIMEOUT_MS;
                
                _connectionState = ConnectionState.Connected;
                
                // 启动心跳
                StartHeartbeat();
                
                _logger.LogInfo($"Connected to device {host}:{port}");
            }
            catch (Exception ex)
            {
                _connectionState = ConnectionState.Error;
                throw new DeviceConnectionException($"Failed to connect: {ex.Message}", ex);
            }
        }
        
        /// <summary>
        /// 断开设备连接
        /// </summary>
        public async Task DisconnectAsync()
        {
            _connectionState = ConnectionState.Disconnecting;
            
            StopHeartbeat();
            
            if (_stream != null)
            {
                await _stream.DisposeAsync();
                _stream = null;
            }
            
            _tcpClient?.Dispose();
            _tcpClient = null;
            
            _connectionState = ConnectionState.Disconnected;
            _logger.LogInfo("Disconnected from device");
        }
        
        // ==================== 命令发送 ====================
        
        /// <summary>
        /// 发送命令并获取响应
        /// </summary>
        /// <param name="command">命令对象</param>
        /// <returns>设备响应</returns>
        public async Task<DeviceResponse> SendCommandAsync(DeviceCommand command)
        {
            if (_connectionState != ConnectionState.Connected)
            {
                throw new DeviceNotConnectedException();
            }
            
            // 1. 序列化命令为RX-RMCPTP帧
            var frame = SerializeCommand(command);
            
            // 2. 发送数据
            await SendFrameAsync(frame);
            
            // 3. 等待响应
            var responseFrame = await ReceiveFrameAsync();
            
            // 4. 反序列化响应
            return DeserializeResponse(responseFrame);
        }
        
        /// <summary>
        /// 发送数据帧
        /// </summary>
        private async Task SendFrameAsync(byte[] frame)
        {
            lock (_sendLock)
            {
                ValidateFrame(frame);
                
                // 计算校验和
                ushort checksum = CalculateChecksum(frame);
                
                // 添加校验和到帧尾
                var frameWithChecksum = new byte[frame.Length + 2];
                Array.Copy(frame, 0, frameWithChecksum, 0, frame.Length);
                frameWithChecksum[frame.Length] = (byte)(checksum & 0xFF);
                frameWithChecksum[frame.Length + 1] = (byte)((checksum >> 8) & 0xFF);
                
                await _stream.WriteAsync(frameWithChecksum, 0, frameWithChecksum.Length);
            }
        }
        
        // ==================== 辅助方法 ====================
        
        /// <summary>
        /// 计算帧头校验和
        /// </summary>
        /// <remarks>
        /// 算法: 无符号短整型形式的累加和，然后两次折半移位相加
        /// </remarks>
        private ushort CalculateChecksum(byte[] frame)
        {
            uint sum = 0;
            
            // 累加前16字节（帧头）
            for (int i = 0; i < 16 && i < frame.Length; i++)
            {
                sum += frame[i];
            }
            
            // 两次折半移位相加
            sum = (sum & 0xFFFF) + (sum >> 16);
            sum = (sum & 0xFFFF) + (sum >> 16);
            
            return (ushort)(~sum); // 取反码
        }
        
        /// <summary>
        /// 帧头校验和验证
        /// </summary>
        private bool ValidateChecksum(byte[] frame)
        {
            if (frame.Length < 18)
            {
                return false;
            }
            
            ushort receivedChecksum = (ushort)((frame[16] & 0xFF) | ((frame[17] << 8) & 0xFF00));
            ushort calculatedChecksum = CalculateChecksum(frame);
            
            return receivedChecksum == calculatedChecksum;
        }
    }
    
    /// <summary>
    /// 连接状态枚举
    /// </summary>
    public enum ConnectionState
    {
        Disconnected = 0,
        Connecting = 1,
        Connected = 2,
        Disconnecting = 3,
        Error = 4
    }
}
```

#### 2.2.2 协议解析类

```csharp
// 命名空间: AtomService.Protocol
namespace AtomService.Protocol
{
    /// <summary>
    /// RX-RMCPTP协议解析器
    /// 职责: 解析/封装RX-RMCPTP数据帧
    /// </summary>
    public class RmcpProtocolParser
    {
        // ==================== 常量定义 ====================
        
        /// <summary>
        /// 帧头长度
        /// </summary>
        public const int FRAME_HEADER_SIZE = 18;
        
        /// <summary>
        /// 报文数据类型常量
        /// </summary>
        public static class DataTypes
        {
            public const byte BusinessData = 0x00;        // 监测业务数据
            public const byte AudioDescHead = 0x01;        // 音频描述头
            public const byte AudioData = 0x02;           // 音频数据
            public const byte DistributeRequest = 0x03;    // 分发请求
            public const byte InfoData = 0x04;            // 信息数据
            public const byte BusinessDescHead = 0x06;     // 业务数据描述头
            public const byte NotifyMessage = 0x08;      // 通知消息
            public const byte GpsData = 0x0B;            // GPS数据
        }
        
        /// <summary>
        /// 业务数据类型常量
        /// </summary>
        public static class BusinessTypes
        {
            public const byte SglFreq = 0x10;         // 单频测量
            public const byte IfAnalysis = 0x11;      // 中频分析
            public const byte Df = 0x12;            // 单频测向
            public const byte IfDf = 0x13;          // 中频测向
            public const byte Mscan = 0x14;         // 离散扫描
            public const byte Fscan = 0x15;         // 频段扫描
            public const byte Dscan = 0x16;         // 数字扫描
            public const byte SpAnalysis = 0x18;    // 频谱分析
            public const byte TdAnalysis = 0x19;    // 时域分析
            public const byte DfSearch = 0x20;       // 搜索测向
            public const byte ScanDf = 0x21;        // 频率测向
            public const byte Msearch = 0x22;       // 离散信号搜索
            public const byte Fsearch = 0x23;       // 信号搜索
            public const byte Itu = 0x24;           // ITU测量
            public const byte WbMonDf = 0x25;       // 宽带监测测向
            public const byte WMon = 0x28;         // 宽带监测
            public const byte DigDem = 0x29;       // IQ数字解调
            public const byte EDetn = 0x31;        // 能量探测
            public const byte Ddf = 0x32;           // 离散测向
            public const byte SignalMeas = 0x33;   // 信号测量
            public const byte ModRec = 0x34;        // 信号识别
            public const byte Sina = 0x35;         // 信号告警
            public const byte DdcDem = 0x38;      // DDC解调
            public const byte SsDf = 0x39;          // 空间谱测向
            public const byte MultiChan = 0x40;    // 多信道监听
            public const byte Acdf = 0x41;         // 旋转云台
            public const byte DemRec = 0x43;        // 调制模式识别
            public const byte MulChanAna = 0x44;   // 双/多信道分析
            public const byte FreqMeas = 0x51;     // 频点分析
        }
        
        // ==================== 核心方法 ====================
        
        /// <summary>
        /// 解析数据帧
        /// </summary>
        /// <param name="data">原始数据</param>
        /// <returns>解析后的帧对象</returns>
        public RmcpFrame ParseFrame(byte[] data)
        {
            if (data == null || data.Length < FRAME_HEADER_SIZE)
            {
                throw new ProtocolParseException("数据长度不足");
            }
            
            var frame = new RmcpFrame();
            
            // 解析帧头
            using (var ms = new MemoryStream(data))
            using (var reader = new BinaryReader(ms))
            {
                // 报文长度 (4字节)
                frame.Length = reader.ReadUInt32();
                
                // 报文时间戳 (8字节)
                frame.Timestamp = DateTime.FromFileTime(reader.ReadInt64());
                
                // 报文版本号 (2字节)
                frame.Version = reader.ReadUInt16();
                if (frame.Version != 0x0007)
                {
                    throw new ProtocolVersionException($"不支持的协议版本: 0x{frame.Version:X4}");
                }
                
                // 报文数据类型 (1字节)
                frame.DataType = reader.ReadByte();
                
                // 报文标志 (1字节)
                frame.Flags = reader.ReadByte();
                
                // 头校验和 (2字节)
                frame.HeaderChecksum = reader.ReadUInt16();
                
                // 验证校验和
                if (!ValidateHeaderChecksum(data))
                {
                    throw new ChecksumException("帧头校验和验证失败");
                }
                
                // 解析数据部分
                int dataLength = (int)frame.Length - FRAME_HEADER_SIZE;
                if (dataLength > 0)
                {
                    frame.Data = reader.ReadBytes(dataLength);
                }
            }
            
            // 根据数据类型处理数据
            frame.ParsedData = ParseDataByType(frame.DataType, frame.Data);
            
            return frame;
        }
        
        /// <summary>
        /// 封装数据帧
        /// </summary>
        public byte[] BuildFrame(byte dataType, byte[] data, FrameFlags flags = FrameFlags.None)
        {
            var frame = new RmcpFrame
            {
                Version = 0x0007,
                DataType = dataType,
                Flags = (byte)flags,
                Data = data
            };
            
            return SerializeFrame(frame);
        }
        
        /// <summary>
        /// 根据数据类型解析数据
        /// </summary>
        private object ParseDataByType(byte dataType, byte[] data)
        {
            switch (dataType)
            {
                case DataTypes.BusinessData:
                    return ParseBusinessData(data);
                    
                case DataTypes.BusinessDescHead:
                    return ParseBusinessDescHead(data);
                    
                case DataTypes.AudioData:
                    return ParseAudioData(data);
                    
                case DataTypes.NotifyMessage:
                    return ParseNotifyMessage(data);
                    
                case DataTypes.GpsData:
                    return ParseGpsData(data);
                    
                default:
                    return data;
            }
        }
        
        /// <summary>
        /// 解析业务数据
        /// </summary>
        private BusinessData ParseBusinessData(byte[] data)
        {
            if (data.Length < 9)
            {
                throw new ProtocolParseException("业务数据长度不足");
            }
            
            using (var ms = new MemoryStream(data))
            using (var reader = new BinaryReader(ms))
            {
                var businessData = new BusinessData();
                
                // 业务数据类型 (1字节)
                businessData.Type = reader.ReadByte();
                
                // 业务数据标志 (2字节)
                businessData.Flags = reader.ReadInt16();
                
                // 动态数组数目 (4字节)
                businessData.Arrays = reader.ReadUInt32();
                
                // 动态数据
                int offset = 9;
                if (data.Length > offset)
                {
                    var dynamicData = new byte[data.Length - offset];
                    Array.Copy(data, offset, dynamicData, 0, dynamicData.Length);
                    businessData.DynamicData = ParseDynamicData(businessData.Type, dynamicData);
                }
                
                return businessData;
            }
        }
        
        /// <summary>
        /// 解析单频测量业务数据
        /// </summary>
        private SglFreqData ParseSglFreqData(byte[] data)
        {
            var result = new SglFreqData();
            
            using (var ms = new MemoryStream(data))
            using (var reader = new BinaryReader(ms))
            {
                // 跳过静态部分
                reader.ReadByte(); // nBdType = 0x10
                reader.ReadBytes(4); // nArrays
                
                // 读取频率 (8字节)
                result.Frequency = reader.ReadInt64();
                
                // 跳过天线名 (64字节)
                reader.ReadBytes(64);
                
                // 动态部分 - ITU数据
                while (ms.Position < ms.Length)
                {
                    var ituValue = reader.ReadSingle();
                    result ItuValues.Add(ituValue);
                }
                
                // 解析占用度 (如果存在)
                if ((result.Flags & 0x0001) != 0)
                {
                    result.Occupancy = reader.ReadInt16();
                }
            }
            
            return result;
        }
    }
    
    /// <summary>
    /// RX-RMCPTP帧结构
    /// </summary>
    [StructLayout(LayoutKind.Sequential, Pack = 1)]
    public struct RmcpFrameHeader
    {
        public UInt32 Length;       // 报文长度
        public Int64 Timestamp;      // 报文产生时间
        public UInt16 Version;       // 报文版本号
        public Byte DataType;        // 报文数据类型
        public Byte Flags;           // 报文标志
        public UInt16 HeaderChecksum;// 头校验和
    }
    
    /// <summary>
    /// 帧标志位
    /// </summary>
    [Flags]
    public enum FrameFlags : byte
    {
        None = 0x00,
        Discardable = 0x01,     // 数据可抛弃
        LevelData = 0x02,       // 电平数据
        FieldStrength = 0x04,   // 场强数据
        Freq放大1000 = 0x08     // 频率放大标志
    }
}
```

#### 2.2.3 监测服务类

```csharp
// 命名空间: AtomService.Monitoring
namespace AtomService.Monitoring
{
    /// <summary>
    /// 监测服务基类
    /// </summary>
    public abstract class MonitorServiceBase : IDisposable
    {
        protected DeviceCommunicator Device { get; }
        protected RmcpProtocolParser ProtocolParser { get; }
        protected ILogger Logger { get; }
        
        /// <summary>
        /// 任务ID
        /// </summary>
        public string TaskId { get; protected set; }
        
        /// <summary>
        /// 任务状态
        /// </summary>
        public TaskState State { get; protected set; }
        
        /// <summary>
        /// 数据回调
        /// </summary>
        public event EventHandler<MonitorDataEventArgs> OnDataReceived;
        
        /// <summary>
        /// 开始监测任务
        /// </summary>
        public abstract Task StartAsync(MonitorParameters parameters);
        
        /// <summary>
        /// 停止监测任务
        /// </summary>
        public abstract Task StopAsync();
        
        /// <summary>
        /// 处理接收到的数据
        /// </summary>
        protected virtual void ProcessData(RmcpFrame frame)
        {
            var args = new MonitorDataEventArgs
            {
                Frame = frame,
                Timestamp = DateTime.Now
            };
            
            OnDataReceived?.Invoke(this, args);
        }
    }
    
    /// <summary>
    /// 单频测量服务
    /// </summary>
    public class SglFreqMeasureService : MonitorServiceBase
    {
        /// <summary>
        /// 监测参数
        /// </summary>
        public class SglFreqParameters : MonitorParameters
        {
            /// <summary>
            /// 监测频率 (Hz)
            /// </summary>
            public Int64 Frequency { get; set; }
            
            /// <summary>
            /// 天线名称
            /// </summary>
            public string Antenna { get; set; }
            
            /// <summary>
            /// 中频带宽 (Hz)
            /// </summary>
            public Int64? Ifbw { get; set; }
            
            /// <summary>
            /// ITU测量项列表
            /// </summary>
            public List<string> ItuMeasurements { get; set; }
        }
        
        private CancellationTokenSource _cancellationSource;
        private Task _receiveTask;
        
        public override async Task StartAsync(MonitorParameters parameters)
        {
            var param = parameters as SglFreqParameters;
            if (param == null)
            {
                throw new ArgumentException("无效的监测参数");
            }
            
            // 1. 构建命令
            var command = BuildMeasureCommand(param);
            
            // 2. 发送开始测量命令
            var response = await Device.SendCommandAsync(command);
            
            if (response.Code != 0)
            {
                throw new MonitorException($"测量启动失败: {response.Message}");
            }
            
            // 3. 记录任务ID
            TaskId = response.TaskId;
            State = TaskState.Running;
            
            // 4. 启动数据接收循环
            _cancellationSource = new CancellationTokenSource();
            _receiveTask = ReceiveDataLoop(_cancellationSource.Token);
            
            Logger.LogInfo($"SglFreqMeasure started: TaskId={TaskId}, Frequency={param.Frequency}");
        }
        
        public override async Task StopAsync()
        {
            if (State != TaskState.Running)
            {
                return;
            }
            
            // 1. 取消数据接收
            _cancellationSource?.Cancel();
            
            // 2. 发送停止命令
            var stopCommand = BuildStopCommand(TaskId);
            await Device.SendCommandAsync(stopCommand);
            
            // 3. 等待接收任务结束
            if (_receiveTask != null)
            {
                await _receiveTask;
            }
            
            State = TaskState.Stopped;
            Logger.LogInfo($"SglFreqMeasure stopped: TaskId={TaskId}");
        }
        
        /// <summary>
        /// 构建测量命令
        /// </summary>
        private DeviceCommand BuildMeasureCommand(SglFreqParameters param)
        {
            // 构建XML参数
            var xmlParams = $@"
                <parameter groups='1'>
                    <group>
                        <item name='frequency' value='{FormatFrequency(param.Frequency)}' />
                        <item name='antenna' value='{param.Antenna}' />
                        {(param.Ifbw.HasValue ? $"<item name='ifbw' value='{param.Ifbw.Value}' />" : ""}
                    </group>
                </parameter>";
            
            return new DeviceCommand
            {
                CommandType = CommandTypes.StartMeasure,
                ServiceType = "SglFreqMeasure",
                Parameters = xmlParams,
                TaskId = GenerateTaskId()
            };
        }
        
        /// <summary>
        /// 数据接收循环
        /// </summary>
        private async Task ReceiveDataLoop(CancellationToken ct)
        {
            while (!ct.IsCancellationRequested)
            {
                try
                {
                    var frame = await ReceiveFrameAsync(ct);
                    
                    if (frame.DataType == DataTypes.BusinessData)
                    {
                        ProcessData(frame);
                    }
                }
                catch (OperationCanceledException)
                {
                    break;
                }
                catch (Exception ex)
                {
                    Logger.LogError($"Data receive error: {ex.Message}");
                }
            }
        }
        
        /// <summary>
        /// 格式化频率为MHz字符串
        /// </summary>
        private string FormatFrequency(Int64 frequencyHz)
        {
            if (frequencyHz >= 1_000_000)
            {
                return $"{frequencyHz / 1_000_000.0:F4}MHz";
            }
            return $"{frequencyHz}Hz";
        }
    }
    
    /// <summary>
    /// 任务状态枚举
    /// </summary>
    public enum TaskState
    {
        Idle = 0,
        Starting = 1,
        Running = 2,
        Paused = 3,
        Stopping = 4,
        Stopped = 5,
        Error = 6
    }
}
```

#### 2.2.4 模拟服务类

```csharp
// 命名空间: AtomService.Mock
namespace AtomService.Mock
{
    /// <summary>
    /// 模拟监测服务
    /// 职责: 生成模拟监测数据，用于测试和开发
    /// </summary>
    public class MockMonitorService : MonitorServiceBase
    {
        // ==================== 配置属性 ====================
        
        /// <summary>
        /// 模拟场景类型
        /// </summary>
        public MockScenarioType Scenario { get; set; }
        
        /// <summary>
        /// 数据生成间隔 (毫秒)
        /// </summary>
        public int DataIntervalMs { get; set; } = 100;
        
        /// <summary>
        /// 信号电平范围 (dBuV)
        /// </summary>
        public (double Min, double Max) LevelRange { get; set; } = (-120, -40);
        
        /// <summary>
        /// 噪声底 (dBuV)
        /// </summary>
        public double NoiseFloor { get; set; } = -110;
        
        private CancellationTokenSource _simulationCts;
        private Task _simulationTask;
        private readonly Random _random = new Random();
        
        // ==================== 模拟场景定义 ====================
        
        public enum MockScenarioType
        {
            /// <summary>常规场景 - 正常信号和噪声</summary>
            Normal,
            
            /// <summary>强信号场景 - 高电平信号</summary>
            StrongSignal,
            
            /// <summary>弱信号场景 - 低信噪比</summary>
            WeakSignal,
            
            /// <summary>干扰场景 - 多个干扰信号</summary>
            Interference,
            
            /// <summary>跳频场景 - 频率快速变化</summary>
            FrequencyHopping,
            
            /// <summary>压力测试场景 - 高数据量</summary>
            StressTest
        }
        
        // ==================== 核心方法 ====================
        
        public override async Task StartAsync(MonitorParameters parameters)
        {
            var param = parameters as MockParameters;
            
            TaskId = GenerateTaskId();
            State = TaskState.Running;
            
            // 初始化模拟环境
            InitializeSimulation(param);
            
            // 启动模拟循环
            _simulationCts = new CancellationTokenSource();
            _simulationTask = RunSimulationLoop(_simulationCts.Token);
            
            Logger.LogInfo($"Mock service started: TaskId={TaskId}, Scenario={Scenario}");
        }
        
        public override async Task StopAsync()
        {
            _simulationCts?.Cancel();
            
            if (_simulationTask != null)
            {
                await _simulationTask;
            }
            
            State = TaskState.Stopped;
            Logger.LogInfo($"Mock service stopped: TaskId={TaskId}");
        }
        
        /// <summary>
        /// 初始化模拟环境
        /// </summary>
        private void InitializeSimulation(MockParameters param)
        {
            // 根据场景类型设置参数
            switch (Scenario)
            {
                case MockScenarioType.StrongSignal:
                    LevelRange = (-60, -20);
                    NoiseFloor = -80;
                    break;
                    
                case MockScenarioType.WeakSignal:
                    LevelRange = (-120, -80);
                    NoiseFloor = -115;
                    break;
                    
                case MockScenarioType.Interference:
                    // 多信号将在生成函数中处理
                    break;
            }
        }
        
        /// <summary>
        /// 运行模拟循环
        /// </summary>
        private async Task RunSimulationLoop(CancellationToken ct)
        {
            while (!ct.IsCancellationRequested)
            {
                try
                {
                    // 生成模拟数据帧
                    var frame = GenerateMockFrame();
                    
                    // 处理数据
                    ProcessData(frame);
                    
                    // 按间隔等待
                    await Task.Delay(DataIntervalMs, ct);
                }
                catch (OperationCanceledException)
                {
                    break;
                }
            }
        }
        
        /// <summary>
        /// 生成模拟帧
        /// </summary>
        private RmcpFrame GenerateMockFrame()
        {
            var param = GetCurrentParameters();
            
            // 生成业务数据
            byte[] businessData = Scenario switch
            {
                MockScenarioType.Normal => GenerateNormalData(param),
                MockScenarioType.Interference => GenerateInterferenceData(param),
                MockScenarioType.FrequencyHopping => GenerateHoppingData(param),
                _ => GenerateNormalData(param)
            };
            
            // 构建完整帧
            return ProtocolParser.BuildFrame(DataTypes.BusinessData, businessData);
        }
        
        /// <summary>
        /// 生成常规数据
        /// </summary>
        private byte[] GenerateNormalData(MockParameters param)
        {
            using var ms = new MemoryStream();
            using var writer = new BinaryWriter(ms);
            
            // 业务数据类型
            writer.Write(param.BusinessType);
            
            // 业务数据标志
            writer.Write((short)0x0003); // 含基础数据和占用度
            
            // 动态数组数目
            writer.Write((uint)param.SampleCount);
            
            // 相对偏移
            writer.Write((uint)0);
            
            // 频率
            writer.Write(param.Frequency);
            
            // 生成电平数据
            for (int i = 0; i < param.SampleCount; i++)
            {
                // 生成随机电平 (dBuV * 100)
                double level = GenerateNoise() + (param.SignalPresent ? GenerateSignal() : 0);
                short levelValue = (short)(level * 100);
                writer.Write(levelValue);
            }
            
            return ms.ToArray();
        }
        
        /// <summary>
        /// 生成干扰数据
        /// </summary>
        private byte[] GenerateInterferenceData(MockParameters param)
        {
            using var ms = new MemoryStream();
            using var writer = new BinaryWriter(ms);
            
            // 写入静态部分...
            writer.Write(param.BusinessType);
            writer.Write((short)0x0003);
            writer.Write((uint)param.SampleCount);
            writer.Write((uint)0);
            writer.Write(param.Frequency);
            
            // 计算频率范围
            double freqStart = param.Frequency - param.Span / 2.0;
            double freqStep = param.Span / param.SampleCount;
            
            // 生成含干扰的频谱
            for (int i = 0; i < param.SampleCount; i++)
            {
                double freq = freqStart + i * freqStep;
                double level = GenerateNoise();
                
                // 添加干扰信号
                foreach (var干扰 in InterferenceSignals)
                {
                    if (Math.Abs(freq - 干扰.Frequency) < freqStep)
                    {
                        level += 干扰.Level;
                    }
                }
                
                short levelValue = (short)(level * 100);
                writer.Write(levelValue);
            }
            
            return ms.ToArray();
        }
        
        /// <summary>
        /// 生成噪声
        /// </summary>
        private double GenerateNoise()
        {
            // 高斯噪声
            double u1 = _random.NextDouble();
            double u2 = _random.NextDouble();
            double gaussian = Math.Sqrt(-2.0 * Math.Log(u1)) * Math.Cos(2.0 * Math.PI * u2);
            
            return NoiseFloor + gaussian * 3; // 约99.7%在±3σ范围内
        }
        
        /// <summary>
        /// 生成信号分量
        /// </summary>
        private double GenerateSignal()
        {
            // 均匀分布的信号强度
            return _random.NextDouble() * (LevelRange.Max - LevelRange.Min) + LevelRange.Min;
        }
        
        private List<InterferenceSignal> InterferenceSignals { get; set; }
            = new List<InterferenceSignal>();
    }
    
    /// <summary>
    /// 干扰信号定义
    /// </summary>
    public class InterferenceSignal
    {
        public Int64 Frequency { get; set; }
        public double Level { get; set; }  // dBuV
        public double Bandwidth { get; set; } // Hz
    }
}
```

---

## 3. 算法描述

### 3.1 校验和算法

```csharp
/// <summary>
/// 计算帧头校验和
/// </summary>
/// <param name="frame">原始帧数据</param>
/// <returns>校验和（16位）</returns>
/// <remarks>
/// 算法描述：
/// 1. 累加帧头前16字节（无符号16位加法）
/// 2. 第一次折半移位相加：sum = (sum & 0xFFFF) + (sum >> 16)
/// 3. 第二次折半移位相加：sum = (sum & 0xFFFF) + (sum >> 16)
/// 4. 取反码：checksum = ~sum
/// </remarks>
private ushort CalculateHeaderChecksum(byte[] frame)
{
    uint sum = 0;
    
    // 步骤1: 累加前16字节
    for (int i = 0; i < 16 && i < frame.Length; i++)
    {
        sum += frame[i];
    }
    
    // 步骤2-3: 两次折半移位相加
    sum = (sum & 0xFFFF) + (sum >> 16);
    sum = (sum & 0xFFFF) + (sum >> 16);
    
    // 步骤4: 取反码
    return (ushort)(~sum);
}
```

### 3.2 负载均衡算法

```csharp
/// <summary>
/// 加权轮询负载均衡
/// </summary>
public class WeightedRoundRobinBalancer : ILoadBalancer
{
    private readonly List<ServiceInstance> _instances;
    private readonly Dictionary<string, int> _weights;
    private int _currentIndex = 0;
    private readonly object _lock = new object();
    
    public ServiceInstance Select(IServiceGroup group)
    {
        var instances = group.Instances.Where(i => i.IsHealthy).ToList();
        
        if (instances.Count == 0)
        {
            throw new NoAvailableInstanceException();
        }
        
        lock (_lock)
        {
            // 简单加权轮询实现
            int totalWeight = instances.Sum(i => _weights.GetValueOrDefault(i.Id, 1));
            
            int currentWeight = 0;
            ServiceInstance selected = instances[0];
            
            for (int i = 0; i < instances.Count; i++)
            {
                int idx = (_currentIndex + i) % instances.Count;
                int weight = _weights.GetValueOrDefault(instances[idx].Id, 1);
                
                currentWeight += weight;
                
                if (currentWeight >= totalWeight)
                {
                    selected = instances[idx];
                    _currentIndex = (idx + 1) % instances.Count;
                    break;
                }
            }
            
            return selected;
        }
    }
}
```

### 3.3 数据解析算法

```csharp
/// <summary>
/// 解析频谱数据
/// </summary>
/// <param name="data">原始数据</param>
/// <param name="offset">起始偏移</param>
/// <param name="count">数据点数</param>
/// <returns>电平数组</returns>
/// <remarks>
/// 电平值在协议中使用short类型存储，值为实际电平*100
/// 例如：-45.67 dBuV 存储为 -4567
/// </remarks>
private double[] ParseSpectrumData(byte[] data, int offset, int count)
{
    var levels = new double[count];
    
    using (var ms = new MemoryStream(data))
    using (var reader = new BinaryReader(ms))
    {
        reader.BaseStream.Seek(offset, SeekOrigin.Begin);
        
        for (int i = 0; i < count; i++)
        {
            short rawValue = reader.ReadInt16();
            levels[i] = rawValue / 100.0; // 还原实际值
        }
    }
    
    return levels;
}

/// <summary>
/// 计算占用度
/// </summary>
/// <param name="occValue">占用度原始值</param>
/// <returns>占用度百分比</returns>
/// <remarks>
/// 占用度 = 高4字节(有效采样) / 低4字节(总采样) * 100%
/// </remarks>
private double CalculateOccupancy(long occValue)
{
    int validSamples = (int)((occValue >> 32) & 0xFFFFFFFF);
    int totalSamples = (int)(occValue & 0xFFFFFFFF);
    
    if (totalSamples == 0)
    {
        return 0;
    }
    
    return (double)validSamples / totalSamples * 100.0;
}
```

---

## 4. 关键流程

### 4.1 设备连接流程

```
┌─────────┐
│ 开始    │
└────┬────┘
     │
     ▼
┌─────────────────┐
│ 创建TCP连接    │────超时────▶ 抛出异常
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 设置Socket参数  │
│ 超时=5000ms    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 发送握手命令    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 等待握手响应    │────超时────▶ 断开连接
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 验证响应        │────失败────▶ 断开连接
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 启动心跳线程    │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ 连接状态=已连接 │
└────────┬────────┘
         │
         ▼
      结束
```

### 4.2 监测任务执行流程

```
┌─────────┐
│ 开始    │
└────┬────┘
     │
     ▼
┌─────────────────────────┐
│ 解析监测参数            │
│ - 频率/带宽/模式等     │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│ 构建RX-RMCPTP命令帧    │
│ - ServiceType=业务类型 │
│ - Parameters=参数XML   │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│ 发送开始测量命令        │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│ 等待响应                │──失败──▶ 抛出异常
│ - 检查返回码            │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│ 保存任务ID              │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│ 启动数据接收循环        │
│ ┌───────────────────┐  │
│ │ 接收数据帧         │  │
│ │ 验证校验和         │  │
│ │ 解析业务数据       │  │
│ │ 触发数据回调       │  │
│ └───────────────────┘  │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│ 停止测量命令            │
└──────────┬──────────────┘
           │
           ▼
      结束
```

---

## 5. 变量字典

### 5.1 核心变量

| 变量名 | 类型 | 作用域 | 说明 |
|--------|------|--------|------|
| TaskId | string | 实例 | 监测任务唯一标识 |
| State | TaskState | 实例 | 当前任务状态 |
| DeviceId | DeviceIdentifier | 类 | 设备标识信息 |
| ConnectionState | ConnectionState | 实例 | TCP连接状态 |
| _routeTable | ConcurrentDictionary | 类 | 路由表缓存 |
| _loadBalancer | ILoadBalancer | 实例 | 负载均衡器 |
| ProtocolParser | RmcpProtocolParser | 实例 | 协议解析器 |

### 5.2 业务变量

| 变量名 | 类型 | 说明 |
|--------|------|------|
| Frequency | Int64 | 监测频率(Hz) |
| Span | Int64 | 频谱跨距(Hz) |
| IFBW | Int64 | 中频带宽(Hz) |
| Antenna | string | 天线名称 |
| Level | double | 信号电平(dBuV) |
| DfLevel | double | 测向电平(dBuV) |
| Azimuth | double | 方位角(度) |
| Elevation | double | 俯仰角(度) |
| Quality | double | 测向质量(%) |
| Occupancy | double | 占用度(%) |

### 5.3 帧结构变量

| 变量名 | 类型 | 偏移 | 说明 |
|--------|------|------|------|
| dwLength | UInt32 | 0 | 报文长度(BYTE) |
| tmStamp | Int64 | 4 | 报文产生时间 |
| nVersion | UInt16 | 12 | 报文版本号 |
| nDataType | Byte | 14 | 报文数据类型 |
| nFlags | Byte | 15 | 报文标志 |
| nCheckSum | UInt16 | 16 | 头校验和 |

---

## 6. 异常处理

### 6.1 异常类型定义

```csharp
namespace AtomService.Exceptions
{
    /// <summary>
    /// 设备连接异常
    /// </summary>
    public class DeviceConnectionException : Exception
    {
        public string DeviceAddress { get; }
        
        public DeviceConnectionException(string message) : base(message) { }
        public DeviceConnectionException(string message, Exception inner) : base(message, inner) { }
    }
    
    /// <summary>
    /// 设备未连接异常
    /// </summary>
    public class DeviceNotConnectedException : Exception
    {
        public DeviceNotConnectedException() : base("设备未连接") { }
    }
    
    /// <summary>
    /// 协议解析异常
    /// </summary>
    public class ProtocolParseException : Exception
    {
        public ProtocolParseException(string message) : base(message) { }
    }
    
    /// <summary>
    /// 校验和异常
    /// </summary>
    public class ChecksumException : Exception
    {
        public ushort Expected { get; }
        public ushort Actual { get; }
        
        public ChecksumException(string message) : base(message) { }
        public ChecksumException(string message, ushort expected, ushort actual) 
            : base(message)
        {
            Expected = expected;
            Actual = actual;
        }
    }
    
    /// <summary>
    /// 协议版本异常
    /// </summary>
    public class ProtocolVersionException : Exception
    {
        public ushort Version { get; }
        
        public ProtocolVersionException(string message) : base(message) { }
    }
    
    /// <summary>
    /// 监测异常
    /// </summary>
    public class MonitorException : Exception
    {
        public int ErrorCode { get; }
        
        public MonitorException(string message) : base(message) { }
        public MonitorException(string message, int errorCode) : base(message)
        {
            ErrorCode = errorCode;
        }
    }
    
    /// <summary>
    /// 服务不可用异常
    /// </summary>
    public class ServiceUnavailableException : Exception
    {
        public ServiceUnavailableException(string message) : base(message) { }
    }
}
```

### 6.2 异常处理策略

| 异常类型 | 处理策略 | 重试次数 |
|----------|----------|----------|
| DeviceConnectionException | 重试 → 故障转移 | 3次 |
| DeviceNotConnectedException | 重新连接 | 3次 |
| ProtocolParseException | 记录日志，跳过数据 | N/A |
| ChecksumException | 记录日志，请求重发 | 2次 |
| TimeoutException | 重试 | 3次 |
| ServiceUnavailableException | 路由到备用服务 | N/A |

---

## 7. 配置说明

### 7.1 配置文件结构

```json
{
  "appSettings": {
    "serviceName": "AtomSvcV3",
    "serviceVersion": "1.0.0",
    "listenPort": 8080,
    "logLevel": "Info"
  },
  
  "deviceSettings": {
    "connectionTimeout": 5000,
    "heartbeatInterval": 30000,
    "maxRetryCount": 3,
    "bufferSize": 65536
  },
  
  "routingSettings": {
    "strategy": "WeightedRoundRobin",
    "healthCheckInterval": 10000,
    "failoverEnabled": true
  },
  
  "monitorSettings": {
    "defaultSampleRate": 100,
    "maxConcurrentTasks": 10,
    "dataRetentionDays": 7
  },
  
  "mockSettings": {
    "enabled": false,
    "defaultScenario": "Normal",
    "dataIntervalMs": 100
  }
}
```

---

## 8. 服务调用流程

### 8.1 单频测量服务调用时序图

```
┌──────┐     ┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│ 客户端 │     │  ProxySvc    │     │  AtomSvcV3   │     │   Device     │
└──┬───┘     └──────┬───────┘     └──────┬───────┘     └──────┬───────┘
   │                 │                    │                    │
   │ 1.SOAP请求      │                    │                    │
   │────────────────>│                    │                    │
   │                 │ 2.解析SOAP        │                    │
   │                 │───────────────────>│                    │
   │                 │                    │ 3.TCP发送命令      │
   │                 │                    │───────────────────>│
   │                 │                    │                    │
   │                 │                    │ 4.设备响应数据     │
   │                 │                    │<───────────────────│
   │                 │                    │                    │
   │                 │                    │ 5.解析RMCPTP帧    │
   │                 │                    │ 5.1帧头解析        │
   │                 │                    │ 5.2校验和验证      │
   │                 │                    │ 5.3数据类型分发   │
   │                 │                    │ 5.4业务数据解析   │
   │                 │                    │                    │
   │                 │ 6.SOAP响应        │                    │
   │ 7.SOAP响应      │<───────────────────│                    │
   │<────────────────│                    │                    │
   │                 │                    │                    │
```

### 8.2 连续数据采集流程

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│   Device     │     │  AtomSvcV3   │     │  DataBuffer  │
└──────┬───────┘     └──────┬───────┘     └──────┬───────┘
       │                    │                    │
       │ 数据帧(0x00)       │                    │
       │───────────────────>│                    │
       │                    │ 解析帧头           │
       │                    │────────┐           │
       │                    │        │           │
       │                    │<───────┘           │
       │                    │                    │
       │                    │ 数据分发           │
       │                    │────────┐           │
       │                    │        │           │
       │                    │<───────┘           │
       │                    │                    │
       │                    │ 写入缓冲区         │
       │                    │───────────────────>│
       │                    │                    │
       │                    │ 批量推送           │
       │                    │───────────────────>│
       │                    │                    │
```

---

## 9. 配置项详细说明

### 9.1 设备连接配置

```json
{
  "devices": [
    {
      "deviceId": "DEV001",
      "name": "监测接收机A",
      "manufacturer": "嵘兴",
      "model": "RX-9000",
      "connection": {
        "type": "TCP",
        "host": "192.168.1.100",
        "port": 9000,
        "protocol": "RMCPTP",
        "protocolVersion": "2.0"
      },
      "capabilities": {
        "frequencyRange": {
          "min": 20000000,
          "max": 3000000000
        },
        "bandwidths": [200, 1000, 3000, 10000, 30000],
        "measurementTypes": ["SGLFREQ", "FSCAN", "DF", "IFDF"]
      },
      "auth": {
        "username": "admin",
        "password": "******"
      }
    }
  ]
}
```

### 9.2 设备能力配置

```json
{
  "deviceCapabilities": {
    "frequencyRange": {
      "minHz": 20000000,
      "maxHz": 3000000000,
      "stepHz": 1
    },
    "measurementBandwidths": [
      {"bwHz": 200, "description": "200Hz"},
      {"bwHz": 1000, "description": "1kHz"},
      {"bwHz": 3000, "description": "3kHz"},
      {"bwHz": 10000, "description": "10kHz"},
      {"bwHz": 30000, "description": "30kHz"}
    ],
    "detectorTypes": ["PEAK", "RMS", "AVERAGE", "QUASI-PEAK"],
    "antennaPorts": ["ANT1", "ANT2", "LOOP"]
  }
}
```

### 9.3 数据解析器配置

```json
{
  "dataParsers": {
    "enabledParsers": [
      "SGLFREQ",    // 单频测量
      "FSCAN",      // 频段扫描
      "IFDF",       // 中频测向
      "DF",         // 单频测向
      "WBFFT",      // 宽带FFT
      "MODREC"      // 调制识别
    ],
    "parserSettings": {
      "bufferSize": 8192,
      "validateChecksum": true,
      "skipInvalidFrames": false,
      "logLevel": "Info"
    }
  }
}
```

### 9.4 配置项说明表

| 配置项 | 类型 | 默认值 | 说明 |
|--------|------|--------|------|
| `deviceSettings.connectionTimeout` | int | 5000 | 连接超时(毫秒) |
| `deviceSettings.heartbeatInterval` | int | 30000 | 心跳间隔(毫秒) |
| `deviceSettings.maxRetryCount` | int | 3 | 最大重试次数 |
| `deviceSettings.bufferSize` | int | 65536 | 接收缓冲区大小 |
| `monitorSettings.defaultSampleRate` | int | 100 | 默认采样率 |
| `monitorSettings.maxConcurrentTasks` | int | 10 | 最大并发任务数 |
| `dataParsers.bufferSize` | int | 8192 | 解析器缓冲区大小 |
| `dataParsers.validateChecksum` | bool | true | 是否验证校验和 |

---

## 10. 文档交叉引用

### 10.1 相关文档

| 文档编号 | 文档名称 | 主要内容 | 引用章节 |
|----------|----------|----------|----------|
| 01_SRS | 软件需求说明书 | 功能需求、数据类型ID定义 | 本文档所有章节 |
| 02_HLD | 概要设计说明书 | 系统架构、模块划分 | 第2章 |
| 04_DBS | 数据库设计说明书 | 数据表结构、存储过程 | 第5章部分 |
| 05_API | 接口文档 | SOAP接口定义 | 第2.1节 |
| **06_RMCPTP** | **无线电协议规范** | **协议帧格式、业务数据类型** | **第2.2节、第5章** |

### 10.2 协议规范引用

**RX-RMCPTP v2.0 协议规范** (`06_RMCPTP_v2.0_无线电协议规范.md`) 与本文档的对应关系：

| 协议章节 | 本文档对应章节 | 说明 |
|----------|----------------|------|
| 2.1 帧头说明 | 2.2.2 RmcpProtocolParser | 帧结构定义 |
| 2.2 报文数据类型 | 2.2.2 DataTypes常量 | 0x00-0x0B |
| 4.1 业务数据类型 | 2.2.2 BusinessTypes常量 | 0x10-0x51 |
| 4.2-4.4 业务数据格式 | 待实现 | 各业务数据解析器 |
| 6.1 调制模式类型 | 6.1 调制模式定义 | 模式ID映射 |
| 7.1 通知消息格式 | 5.3.4 ParseNotifyMessage | GPS数据解析 |
| 8.1 通用频点分析 | 6.2 频点分析协议 | 通用协议 |

### 10.3 代码与协议对照表

| C# 类/方法 | 协议规范章节 | 功能 |
|------------|--------------|------|
| `RmcpProtocolParser.ParseFrame()` | 2.1 帧头说明 | 帧头解析 |
| `RmcpProtocolParser.ValidateChecksum()` | 2.1.5 报文标志 | 校验和验证 |
| `RmcpProtocolParser.ParseDataByType()` | 2.1.6 报文数据类型 | 数据类型分发 |
| `DeviceCommunicator.SendCommandAsync()` | 3 数据分发请求报文 | 命令发送 |
| `ParseSglFreqData()` | 4.2.1 单频测量 | 单频测量数据 |
| `ParseFscanData()` | 4.2.3 频段扫描 | 扫频数据 |

---

**文档结束**
