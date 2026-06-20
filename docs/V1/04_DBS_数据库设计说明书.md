# 超短波监测管理一体化服务系统
# 数据库设计说明书

| 版本 | 日期 | 作者 | 审核 | 变更内容 |
|------|------|------|------|----------|
| 1.0 | 2026-04-04 | AI Assistant | - | 初版创建 |

---

## 1. 文档概述

### 1.1 目的

本文档为超短波监测管理一体化服务系统的数据库设计说明书，定义系统的数据存储结构、表结构设计、索引设计、视图设计、存储过程设计以及数据字典。

### 1.2 范围

本文档涵盖以下数据库设计内容：
- 数据库整体架构
- 核心业务表设计
- 索引设计
- 数据字典
- 初始化数据
- 数据库约束与关系

---

## 2. 数据库整体架构

### 2.1 数据库选型

| 用途 | 推荐数据库 | 说明 |
|------|-----------|------|
| 配置存储 | PostgreSQL 14+ | 关系型配置数据、主数据 |
| 监测数据 | TimescaleDB / InfluxDB | 时序监测数据存储 |
| 缓存 | Redis 6+ | 会话缓存、路由缓存 |
| 消息队列 | RabbitMQ / Kafka | 数据流推送 |

### 2.2 数据库实例规划

```sql
-- 监测管理主库
CREATE DATABASE monitor_platform
    WITH ENCODING = 'UTF8'
    LC_COLLATE = 'zh_CN.UTF-8'
    LC_CTYPE = 'zh_CN.UTF-8';

-- 时序数据库（用于高频监测数据）
CREATE DATABASE monitor_timeseries;

-- 配置库
CREATE DATABASE monitor_config;
```

### 2.3 数据库关系图

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│  监测设施库      │     │  设备库         │     │  监测任务库      │
│  (facility)    │     │  (equipment)   │     │  (task)         │
└────────┬────────┘     └────────┬────────┘     └────────┬────────┘
         │                       │                       │
         │                       │                       │
         ▼                       ▼                       ▼
┌─────────────────────────────────────────────────────────────────┐
│                         监测数据库                                │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │ 单频测量数据   │ │ 扫频数据     │ │ 测向数据      │           │
│  │ (sglfreq)    │ │ (fscan)      │ │ (direction)  │           │
│  └──────────────┘ └──────────────┘ └──────────────┘           │
│  ┌──────────────┐ ┌──────────────┐ ┌──────────────┐           │
│  │ 占用度数据    │ │ FFT数据       │ │ 任务日志      │           │
│  │ (occupancy)  │ │ (fft_data)   │ │ (task_log)   │           │
│  └──────────────┘ └──────────────┘ └──────────────┘           │
└─────────────────────────────────────────────────────────────────┘
```

---

## 3. 配置数据库设计

### 3.1 系统配置表 (system_config)

```sql
-- 系统配置表
CREATE TABLE system_config (
    config_id VARCHAR(64) PRIMARY KEY,           -- 配置项ID
    config_name VARCHAR(128) NOT NULL,          -- 配置项名称
    config_value TEXT,                           -- 配置项值
    config_type VARCHAR(32) NOT NULL,            -- 配置类型: SYSTEM, NETWORK, SERVICE
    config_group VARCHAR(64),                    -- 配置分组
    description VARCHAR(512),                    -- 配置描述
    is_encrypted BOOLEAN DEFAULT FALSE,         -- 是否加密存储
    is_system BOOLEAN DEFAULT FALSE,             -- 是否系统配置
    created_by VARCHAR(64),                      -- 创建人
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(64),                      -- 更新人
    updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    CONSTRAINT uk_config_name_type UNIQUE (config_name, config_type)
);

CREATE INDEX idx_config_type ON system_config(config_type);
CREATE INDEX idx_config_group ON system_config(config_group);
```

### 3.2 服务注册表 (service_registry)

```sql
-- 服务注册表
CREATE TABLE service_registry (
    service_id VARCHAR(64) PRIMARY KEY,          -- 服务实例ID
    service_name VARCHAR(128) NOT NULL,         -- 服务名称
    service_type VARCHAR(32) NOT NULL,          -- 服务类型: ATOM, STANDARD, MOCK
    mfid VARCHAR(16) NOT NULL,                  -- 监测设施标识
    equid VARCHAR(8) NOT NULL,                 -- 设备组合标识
    protocol_type VARCHAR(16) NOT NULL,         -- 协议类型: SOAP, REST
    endpoint_url VARCHAR(512),                  -- 服务端点地址
    health_check_url VARCHAR(256),              -- 健康检查地址
    status VARCHAR(16) DEFAULT 'ACTIVE',        -- 状态: ACTIVE, INACTIVE, FAILED
    priority INT DEFAULT 100,                   -- 优先级 (1-100, 越小优先级越高)
    weight INT DEFAULT 1,                       -- 负载权重
    max_connections INT DEFAULT 100,            -- 最大连接数
    timeout_ms INT DEFAULT 30000,              -- 超时时间(毫秒)
    retry_count INT DEFAULT 3,                  -- 重试次数
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_heartbeat TIMESTAMP,                   -- 最后心跳时间
    
    CONSTRAINT uk_service_name_mfid UNIQUE (service_name, mfid, equid)
);

CREATE INDEX idx_service_mfid ON service_registry(mfid);
CREATE INDEX idx_service_equid ON service_registry(equid);
CREATE INDEX idx_service_status ON service_registry(status);
CREATE INDEX idx_service_type ON service_registry(service_type);
```

### 3.3 路由规则表 (routing_rule)

```sql
-- 路由规则表
CREATE TABLE routing_rule (
    rule_id VARCHAR(64) PRIMARY KEY,             -- 规则ID
    rule_name VARCHAR(128) NOT NULL,            -- 规则名称
    mfid VARCHAR(16),                            -- 监测设施标识(空表示全部)
    equid VARCHAR(8),                            -- 设备组合标识(空表示全部)
    service_id VARCHAR(64),                      -- 目标服务ID
    condition_expr TEXT,                         -- 条件表达式(JSON格式)
    priority INT DEFAULT 100,                   -- 优先级
    is_active BOOLEAN DEFAULT TRUE,             -- 是否激活
    description VARCHAR(512),                   -- 规则描述
    created_by VARCHAR(64),
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(64),
    updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (service_id) REFERENCES service_registry(service_id)
        ON DELETE SET NULL
);

CREATE INDEX idx_routing_mfid ON routing_rule(mfid);
CREATE INDEX idx_routing_equid ON routing_rule(equid);
CREATE INDEX idx_routing_active ON routing_rule(is_active);
```

---

## 4. 监测设施数据库设计

### 4.1 监测设施表 (monitor_facility)

```sql
-- 监测设施表
CREATE TABLE monitor_facility (
    mfid VARCHAR(16) PRIMARY KEY,               -- 监测设施标识 (格式: XX0000XX)
    facility_name VARCHAR(128) NOT NULL,        -- 设施名称
    facility_type VARCHAR(32),                   -- 设施类型: FIXED, MOBILE, PORTABLE
    station_code VARCHAR(16),                   -- 所属监测站编号
    station_name VARCHAR(128),                  -- 所属监测站名称
    region_code VARCHAR(16),                    -- 行政区划代码
    latitude DECIMAL(10, 6),                     -- 纬度
    longitude DECIMAL(10, 6),                    -- 经度
    altitude DECIMAL(8, 2),                      -- 海拔高度(米)
    address VARCHAR(256),                        -- 地址
    contact_person VARCHAR(64),                  -- 联系人
    contact_phone VARCHAR(32),                   -- 联系电话
    status VARCHAR(16) DEFAULT 'ACTIVE',         -- 状态: ACTIVE, INACTIVE, MAINTENANCE
    description VARCHAR(512),                   -- 描述
    created_by VARCHAR(64),
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(64),
    updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_facility_station ON monitor_facility(station_code);
CREATE INDEX idx_facility_region ON monitor_facility(region_code);
CREATE INDEX idx_facility_status ON monitor_facility(status);
CREATE INDEX idx_facility_type ON monitor_facility(facility_type);
```

### 4.2 设备信息表 (equipment_info)

```sql
-- 设备信息表
CREATE TABLE equipment_info (
    equid VARCHAR(8) PRIMARY KEY,                -- 设备组合标识 (格式: XX0)
    mfid VARCHAR(16) NOT NULL,                   -- 所属监测设施标识
    equipment_name VARCHAR(128) NOT NULL,        -- 设备名称
    equipment_type VARCHAR(32),                  -- 设备类型: RECEIVER, DIRECTION_FINDER
    manufacturer VARCHAR(64),                    -- 生产厂商
    model VARCHAR(64),                           -- 型号
    serial_number VARCHAR(64),                   -- 序列号
    firmware_version VARCHAR(32),                -- 固件版本
    software_version VARCHAR(32),                -- 软件版本
    ip_address VARCHAR(64),                      -- IP地址
    port INT DEFAULT 8000,                        -- 端口号
    protocol_version VARCHAR(16),                -- 协议版本
    freq_min BIGINT,                              -- 最小频率(Hz)
    freq_max BIGINT,                              -- 最大频率(Hz)
    max_bandwidth BIGINT,                        -- 最大带宽(Hz)
    antenna_type VARCHAR(64),                    -- 天线类型
    status VARCHAR(16) DEFAULT 'ACTIVE',         -- 状态: ACTIVE, INACTIVE, FAULT
    last_online_time TIMESTAMP,                  -- 最后在线时间
    description VARCHAR(512),
    created_by VARCHAR(64),
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(64),
    updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (mfid) REFERENCES monitor_facility(mfid)
        ON DELETE CASCADE
);

CREATE INDEX idx_equipment_mfid ON equipment_info(mfid);
CREATE INDEX idx_equipment_type ON equipment_info(equipment_type);
CREATE INDEX idx_equipment_status ON equipment_info(status);
CREATE INDEX idx_equipment_manufacturer ON equipment_info(manufacturer);
```

### 4.3 设备能力表 (equipment_capability)

```sql
-- 设备能力表
CREATE TABLE equipment_capability (
    capability_id VARCHAR(64) PRIMARY KEY,       -- 能力ID
    equid VARCHAR(8) NOT NULL,                   -- 设备组合标识
    capability_type VARCHAR(32) NOT NULL,        -- 能力类型
    capability_name VARCHAR(64) NOT NULL,        -- 能力名称
    is_supported BOOLEAN DEFAULT TRUE,           -- 是否支持
    parameters JSONB,                             -- 能力参数(JSON格式)
    description VARCHAR(512),
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (equid) REFERENCES equipment_info(equid)
        ON DELETE CASCADE
);

CREATE INDEX idx_cap_equid ON equipment_capability(equid);
CREATE INDEX idx_cap_type ON equipment_capability(capability_type);
```

### 4.4 频率表 (frequency_table)

```sql
-- 频率表
CREATE TABLE frequency_table (
    freq_id VARCHAR(64) PRIMARY KEY,              -- 频率标识
    frequency BIGINT NOT NULL,                   -- 频率值(Hz)
    channel_name VARCHAR(128),                    -- 频道名称
    modulation_type VARCHAR(32),                  -- 调制类型
    bandwidth BIGINT,                             -- 带宽(Hz)
    power_level DECIMAL(10, 2),                   -- 功率电平(dBm)
    station_name VARCHAR(128),                    -- 电台名称
    station_callsign VARCHAR(32),                 -- 呼号
    license_number VARCHAR(64),                   -- 执照号码
    valid_from DATE,                              -- 有效起始日期
    valid_until DATE,                             -- 有效截止日期
    region_code VARCHAR(16),                     -- 所属区域
    mfid VARCHAR(16),                            -- 关联监测设施
    status VARCHAR(16) DEFAULT 'ACTIVE',         -- 状态: ACTIVE, EXPIRED, CANCELLED
    created_by VARCHAR(64),
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(64),
    updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_freq_frequency ON frequency_table(frequency);
CREATE INDEX idx_freq_region ON frequency_table(region_code);
CREATE INDEX idx_freq_status ON frequency_table(status);
CREATE INDEX idx_freq_mfid ON frequency_table(mfid);
CREATE INDEX idx_freq_modulation ON frequency_table(modulation_type);
```

---

## 5. 监测任务数据库设计

### 5.1 监测任务表 (monitor_task)

```sql
-- 监测任务表
CREATE TABLE monitor_task (
    task_id VARCHAR(64) PRIMARY KEY,              -- 任务ID
    task_name VARCHAR(256) NOT NULL,             -- 任务名称
    task_type VARCHAR(32) NOT NULL,              -- 任务类型
    task_mode VARCHAR(16) NOT NULL,               -- 任务模式: REAL_TIME, SCHEDULED, ON_DEMAND
    mfid VARCHAR(16) NOT NULL,                   -- 监测设施标识
    equid VARCHAR(8),                             -- 设备组合标识
    service_type VARCHAR(32),                     -- 服务类型: SGLFREQ, FSCAN, WBFFT, IFDF
    priority INT DEFAULT 5,                      -- 优先级(1-9)
    status VARCHAR(16) DEFAULT 'PENDING',         -- 状态
    parameters JSONB NOT NULL,                   -- 任务参数(JSON格式)
    
    -- 时间控制
    scheduled_start TIMESTAMP,                   -- 计划开始时间
    scheduled_end TIMESTAMP,                     -- 计划结束时间
    actual_start TIMESTAMP,                      -- 实际开始时间
    actual_end TIMESTAMP,                        -- 实际结束时间
    
    -- 结果存储
    result_storage_type VARCHAR(16),             -- 存储类型: DATABASE, FTP, URL
    result_path VARCHAR(512),                    -- 结果路径
    result_format VARCHAR(16) DEFAULT 'BINARY',   -- 结果格式: BINARY, XML, JSON
    
    -- 执行控制
    max_duration INT,                            -- 最大持续时间(秒)
    retry_count INT DEFAULT 0,                    -- 重试次数
    max_retry INT DEFAULT 3,                     -- 最大重试次数
    
    -- 用户信息
    created_by VARCHAR(64),
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(64),
    updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    completed_by VARCHAR(64),
    completed_time TIMESTAMP,
    
    -- 结果信息
    result_summary TEXT,                          -- 结果摘要
    error_message TEXT,                          -- 错误信息
    
    FOREIGN KEY (mfid) REFERENCES monitor_facility(mfid)
);

CREATE INDEX idx_task_mfid ON monitor_task(mfid);
CREATE INDEX idx_task_equid ON monitor_task(equid);
CREATE INDEX idx_task_type ON monitor_task(task_type);
CREATE INDEX idx_task_status ON monitor_task(status);
CREATE INDEX idx_task_mode ON monitor_task(task_mode);
CREATE INDEX idx_task_scheduled ON monitor_task(scheduled_start);
CREATE INDEX idx_task_created_by ON monitor_task(created_by);
CREATE INDEX idx_task_created_time ON monitor_task(created_time);
```

### 5.2 任务参数说明表 (task_parameters)

任务参数根据不同的服务类型存储相应的配置：

```sql
-- 单频测量任务参数
-- parameters字段JSON结构:
-- {
--   "frequency": 95800000,          -- 测量频率(Hz)
--   "span": 200000,                 -- 跨距(Hz)
--   "referenceLevel": -30,           -- 参考电平(dBm)
--   "rbw": 1000,                    -- 分辨率带宽(Hz)
--   "vbw": 100,                     -- 视频带宽(Hz)
--   "detector": "AVERAGE",          -- 检波模式
--   "sweepTime": 100,               -- 扫描时间(ms)
--   "ituTypes": [1, 2, 3, 4],       -- ITU测量类型
--   "antennaId": "ANT001"           -- 天线标识
-- }

-- 扫频测量任务参数
-- parameters字段JSON结构:
-- {
--   "startFreq": 80000000,          -- 起始频率(Hz)
--   "endFreq": 1000000000,          -- 终止频率(Hz)
--   "step": 10000,                  -- 频率步进(Hz)
--   "rbw": 3000,                    -- 分辨率带宽(Hz)
--   "referenceLevel": -40,          -- 参考电平(dBm)
--   "attenuation": 10,              -- 衰减量(dB)
--   "sweepTime": 1000,              -- 扫描时间(ms)
--   "maxHold": false,               -- 最大保持
--   "attMode": "AUTO"               -- 衰减模式
-- }

-- 测向任务参数
-- parameters字段JSON结构:
-- {
--   "frequency": 95800000,          -- 测向频率(Hz)
--   "mode": "NORMAL",               -- 测向模式
--   "bandwidth": 16000,             -- 带宽(Hz)
--   "integrationTime": 100,         -- 积分时间(ms)
--   "measurementCount": 10          -- 测量次数
-- }
```

### 5.3 任务日志表 (task_log)

```sql
-- 任务日志表
CREATE TABLE task_log (
    log_id VARCHAR(64) PRIMARY KEY,               -- 日志ID
    task_id VARCHAR(64) NOT NULL,                 -- 关联任务ID
    log_level VARCHAR(16) NOT NULL,              -- 日志级别: DEBUG, INFO, WARN, ERROR
    log_type VARCHAR(32) NOT NULL,               -- 日志类型
    message TEXT,                                 -- 日志消息
    context JSONB,                                -- 上下文信息
    operator VARCHAR(64),                        -- 操作人
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    
    FOREIGN KEY (task_id) REFERENCES monitor_task(task_id)
        ON DELETE CASCADE
);

CREATE INDEX idx_log_task ON task_log(task_id);
CREATE INDEX idx_log_level ON task_log(log_level);
CREATE INDEX idx_log_type ON task_log(log_type);
CREATE INDEX idx_log_time ON task_log(created_time);
```

---

## 6. 监测数据数据库设计

### 6.1 单频测量数据表 (data_sglfreq)

```sql
-- 单频测量数据表
CREATE TABLE data_sglfreq (
    data_id VARCHAR(64) PRIMARY KEY,              -- 数据ID
    task_id VARCHAR(64),                         -- 关联任务ID
    mfid VARCHAR(16) NOT NULL,                   -- 监测设施标识
    equid VARCHAR(8) NOT NULL,                   -- 设备组合标识
    
    -- 测量基本信息
    frequency BIGINT NOT NULL,                   -- 测量频率(Hz)
    measure_time TIMESTAMP NOT NULL,              -- 测量时间
    measure_duration INT,                         -- 测量持续时间(ms)
    
    -- 信号参数
    signal_level DECIMAL(10, 2),                  -- 信号电平(dBm)
    freq_offset DECIMAL(12, 2),                   -- 频率偏移(Hz)
    modulation_type VARCHAR(32),                  -- 调制类型
    demod_freq_offset DECIMAL(12, 2),           -- 解调频率偏移
    
    -- ITU测量结果 (JSON格式存储)
    itu_results JSONB,                            -- ITU测量结果
    
    -- 原始数据
    raw_data BYTEA,                               -- 原始数据
    raw_data_size BIGINT,                         -- 原始数据大小
    
    -- 存储信息
    storage_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    storage_location VARCHAR(512),              -- 存储位置
    
    FOREIGN KEY (mfid) REFERENCES monitor_facility(mfid),
    FOREIGN KEY (task_id) REFERENCES monitor_task(task_id)
);

CREATE INDEX idx_sglfreq_mfid ON data_sglfreq(mfid);
CREATE INDEX idx_sglfreq_equid ON data_sglfreq(equid);
CREATE INDEX idx_sglfreq_freq ON data_sglfreq(frequency);
CREATE INDEX idx_sglfreq_time ON data_sglfreq(measure_time);
CREATE INDEX idx_sglfreq_task ON data_sglfreq(task_id);
CREATE INDEX idx_sglfreq_level ON data_sglfreq(signal_level);

-- 时序分区表 (使用TimescaleDB)
SELECT create_hypertable('data_sglfreq', 'measure_time', 
    chunk_time_interval => INTERVAL '1 day');
```

### 6.2 扫频测量数据表 (data_fscan)

```sql
-- 扫频测量数据表
CREATE TABLE data_fscan (
    data_id VARCHAR(64) PRIMARY KEY,              -- 数据ID
    task_id VARCHAR(64),                          -- 关联任务ID
    mfid VARCHAR(16) NOT NULL,                    -- 监测设施标识
    equid VARCHAR(8) NOT NULL,                    -- 设备组合标识
    
    -- 扫描参数
    start_freq BIGINT NOT NULL,                   -- 起始频率(Hz)
    end_freq BIGINT NOT NULL,                     -- 终止频率(Hz)
    step_freq BIGINT,                              -- 频率步进(Hz)
    point_count INT NOT NULL,                     -- 数据点数量
    
    -- 测量信息
    measure_time TIMESTAMP NOT NULL,              -- 测量时间
    measure_duration INT,                         -- 测量持续时间(ms)
    reference_level DECIMAL(10, 2),               -- 参考电平(dBm)
    
    -- 频谱数据 (二进制或JSON格式)
    spectrum_data BYTEA,                          -- 频谱数据
    spectrum_min DECIMAL(10, 2),                  -- 最小电平
    spectrum_max DECIMAL(10, 2),                  -- 最大电平
    spectrum_avg DECIMAL(10, 2),                  -- 平均电平
    
    -- 信号检测结果
    signals_detected INT,                         -- 检测到的信号数
    peak_freq BIGINT,                             -- 峰值频率
    peak_level DECIMAL(10, 2),                    -- 峰值电平
    
    -- 存储信息
    storage_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    storage_location VARCHAR(512),
    
    FOREIGN KEY (mfid) REFERENCES monitor_facility(mfid),
    FOREIGN KEY (task_id) REFERENCES monitor_task(task_id)
);

CREATE INDEX idx_fscan_mfid ON data_fscan(mfid);
CREATE INDEX idx_fscan_equid ON data_fscan(equid);
CREATE INDEX idx_fscan_time ON data_fscan(measure_time);
CREATE INDEX idx_fscan_freq_range ON data_fscan(start_freq, end_freq);
CREATE INDEX idx_fscan_task ON data_fscan(task_id);
CREATE INDEX idx_fscan_peak ON data_fscan(peak_freq, peak_level);

-- 时序分区
SELECT create_hypertable('data_fscan', 'measure_time',
    chunk_time_interval => INTERVAL '1 day');
```

### 6.3 测向数据表 (data_direction)

```sql
-- 测向数据表
CREATE TABLE data_direction (
    data_id VARCHAR(64) PRIMARY KEY,              -- 数据ID
    task_id VARCHAR(64),                          -- 关联任务ID
    mfid VARCHAR(16) NOT NULL,                    -- 监测设施标识
    equid VARCHAR(8) NOT NULL,                     -- 设备组合标识
    
    -- 测向参数
    df_type VARCHAR(16) NOT NULL,                 -- 测向类型: IFDF, SGLFREQ_DF, WBDF, FSCAN_DF
    frequency BIGINT NOT NULL,                    -- 测向频率(Hz)
    measure_time TIMESTAMP NOT NULL,              -- 测量时间
    
    -- 测向结果
    azimuth DECIMAL(8, 3) NOT NULL,                -- 方位角(度)
    azimuth_confidence DECIMAL(5, 2),            -- 方位角置信度(%)
    amplitude DECIMAL(10, 2),                    -- 幅度(dBuV/m)
    
    -- 多信道测向数据
    channel_count INT,                            -- 信道数
    channel_data JSONB,                           -- 信道数据
    
    -- 原始数据
    raw_data BYTEA,
    raw_data_size BIGINT,
    
    -- 存储信息
    storage_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    storage_location VARCHAR(512),
    
    FOREIGN KEY (mfid) REFERENCES monitor_facility(mfid),
    FOREIGN KEY (task_id) REFERENCES monitor_task(task_id)
);

CREATE INDEX idx_df_mfid ON data_direction(mfid);
CREATE INDEX idx_df_equid ON data_direction(equid);
CREATE INDEX idx_df_freq ON data_direction(frequency);
CREATE INDEX idx_df_time ON data_direction(measure_time);
CREATE INDEX idx_df_azimuth ON data_direction(azimuth);
CREATE INDEX idx_df_type ON data_direction(df_type);
CREATE INDEX idx_df_task ON data_direction(task_id);

SELECT create_hypertable('data_direction', 'measure_time',
    chunk_time_interval => INTERVAL '1 day');
```

### 6.4 占用度数据表 (data_occupancy)

```sql
-- 占用度数据表
CREATE TABLE data_occupancy (
    data_id VARCHAR(64) PRIMARY KEY,              -- 数据ID
    task_id VARCHAR(64),                          -- 关联任务ID
    mfid VARCHAR(16) NOT NULL,                    -- 监测设施标识
    equid VARCHAR(8) NOT NULL,                    -- 设备组合标识
    
    -- 占用度测量参数
    start_freq BIGINT NOT NULL,                   -- 起始频率(Hz)
    end_freq BIGINT NOT NULL,                     -- 终止频率(Hz)
    bandwidth BIGINT,                              -- 测量带宽(Hz)
    threshold DECIMAL(10, 2),                     -- 判定阈值(dBm)
    measure_time TIMESTAMP NOT NULL,              -- 测量时间
    measure_duration INT,                         -- 测量持续时间(秒)
    
    -- 占用度结果
    occupancy_rate DECIMAL(5, 2),                 -- 占用度百分比
    occupied_channels INT,                        -- 占用信道数
    total_channels INT,                           -- 总信道数
    channel_details JSONB,                        -- 信道详情
    
    -- 统计信息
    stat_min DECIMAL(10, 2),                      -- 最小值
    stat_max DECIMAL(10, 2),                      -- 最大值
    stat_avg DECIMAL(10, 2),                      -- 平均值
    stat_std DECIMAL(10, 2),                      -- 标准差
    
    -- 存储信息
    storage_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    storage_location VARCHAR(512),
    
    FOREIGN KEY (mfid) REFERENCES monitor_facility(mfid),
    FOREIGN KEY (task_id) REFERENCES monitor_task(task_id)
);

CREATE INDEX idx_occ_mfid ON data_occupancy(mfid);
CREATE INDEX idx_occ_equid ON data_occupancy(equid);
CREATE INDEX idx_occ_freq_range ON data_occupancy(start_freq, end_freq);
CREATE INDEX idx_occ_time ON data_occupancy(measure_time);
CREATE INDEX idx_occ_rate ON data_occupancy(occupancy_rate);

SELECT create_hypertable('data_occupancy', 'measure_time',
    chunk_time_interval => INTERVAL '1 day');
```

### 6.5 FFT数据表 (data_fft)

```sql
-- FFT频谱数据表
CREATE TABLE data_fft (
    data_id VARCHAR(64) PRIMARY KEY,              -- 数据ID
    task_id VARCHAR(64),                           -- 关联任务ID
    mfid VARCHAR(16) NOT NULL,                     -- 监测设施标识
    equid VARCHAR(8) NOT NULL,                     -- 设备组合标识
    
    -- FFT参数
    fft_type VARCHAR(16) NOT NULL,                -- FFT类型: WBFFT, IF_FFT
    center_freq BIGINT NOT NULL,                   -- 中心频率(Hz)
    bandwidth BIGINT NOT NULL,                     -- 带宽(Hz)
    sample_rate BIGINT,                             -- 采样率(Hz)
    fft_size INT,                                  -- FFT点数
    window_type VARCHAR(16),                       -- 窗函数类型
    
    -- 数据信息
    measure_time TIMESTAMP NOT NULL,                -- 测量时间
    point_count INT NOT NULL,                      -- 数据点数
    unit_type VARCHAR(8),                          -- 数据单位: DBM, DBUV, LINEAR
    
    -- 频谱数据
    spectrum_data BYTEA,                           -- 频谱数据
    spectrum_ref_level DECIMAL(10, 2),             -- 参考电平
    
    -- IQ数据
    iq_data BYTEA,                                 -- IQ数据(可选)
    iq_format VARCHAR(16),                         -- IQ格式
    
    -- 存储信息
    storage_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    storage_location VARCHAR(512),
    
    FOREIGN KEY (mfid) REFERENCES monitor_facility(mfid),
    FOREIGN KEY (task_id) REFERENCES monitor_task(task_id)
);

CREATE INDEX idx_fft_mfid ON data_fft(mfid);
CREATE INDEX idx_fft_equid ON data_fft(equid);
CREATE INDEX idx_fft_center ON data_fft(center_freq);
CREATE INDEX idx_fft_time ON data_fft(measure_time);
CREATE INDEX idx_fft_type ON data_fft(fft_type);
CREATE INDEX idx_fft_task ON data_fft(task_id);

SELECT create_hypertable('data_fft', 'measure_time',
    chunk_time_interval => INTERVAL '1 day');
```

---

## 7. 用户权限数据库设计

### 7.1 用户表 (sys_user)

```sql
-- 用户表
CREATE TABLE sys_user (
    user_id VARCHAR(64) PRIMARY KEY,               -- 用户ID
    username VARCHAR(64) NOT NULL UNIQUE,           -- 用户名
    password_hash VARCHAR(256) NOT NULL,           -- 密码哈希
    real_name VARCHAR(128),                         -- 真实姓名
    email VARCHAR(128),                              -- 邮箱
    phone VARCHAR(32),                               -- 电话
    department VARCHAR(128),                        -- 部门
    role_code VARCHAR(32),                          -- 角色代码
    status VARCHAR(16) DEFAULT 'ACTIVE',           -- 状态
    last_login_time TIMESTAMP,                      -- 最后登录时间
    last_login_ip VARCHAR(64),                      -- 最后登录IP
    created_by VARCHAR(64),
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(64),
    updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_user_username ON sys_user(username);
CREATE INDEX idx_user_role ON sys_user(role_code);
CREATE INDEX idx_user_status ON sys_user(status);
```

### 7.2 角色表 (sys_role)

```sql
-- 角色表
CREATE TABLE sys_role (
    role_id VARCHAR(64) PRIMARY KEY,               -- 角色ID
    role_code VARCHAR(32) NOT NULL UNIQUE,        -- 角色代码
    role_name VARCHAR(128) NOT NULL,              -- 角色名称
    role_type VARCHAR(16),                         -- 角色类型
    description VARCHAR(512),
    permissions JSONB,                              -- 权限列表
    created_by VARCHAR(64),
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_by VARCHAR(64),
    updated_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_role_code ON sys_role(role_code);
```

### 7.3 操作日志表 (sys_audit_log)

```sql
-- 操作审计日志表
CREATE TABLE sys_audit_log (
    log_id VARCHAR(64) PRIMARY KEY,               -- 日志ID
    user_id VARCHAR(64),                          -- 用户ID
    username VARCHAR(64),                          -- 用户名
    action VARCHAR(64) NOT NULL,                  -- 操作类型
    resource_type VARCHAR(64),                     -- 资源类型
    resource_id VARCHAR(64),                      -- 资源ID
    request_method VARCHAR(16),                   -- 请求方法
    request_url VARCHAR(512),                     -- 请求URL
    request_params JSONB,                         -- 请求参数
    response_code VARCHAR(16),                   -- 响应码
    ip_address VARCHAR(64),                       -- IP地址
    user_agent TEXT,                              -- 用户代理
    execution_time INT,                           -- 执行时间(ms)
    error_message TEXT,                           -- 错误信息
    created_time TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_audit_user ON sys_audit_log(user_id);
CREATE INDEX idx_audit_action ON sys_audit_log(action);
CREATE INDEX idx_audit_resource ON sys_audit_log(resource_type, resource_id);
CREATE INDEX idx_audit_time ON sys_audit_log(created_time);
CREATE INDEX idx_audit_ip ON sys_audit_log(ip_address);
```

---

## 8. 数据字典

### 8.1 任务状态字典 (task_status)

| 状态码 | 状态名称 | 说明 |
|--------|----------|------|
| PENDING | 待执行 | 任务等待调度 |
| RUNNING | 执行中 | 任务正在执行 |
| COMPLETED | 已完成 | 任务成功完成 |
| FAILED | 失败 | 任务执行失败 |
| CANCELLED | 已取消 | 任务被取消 |
| PAUSED | 已暂停 | 任务暂停执行 |

### 8.2 设备状态字典 (equipment_status)

| 状态码 | 状态名称 | 说明 |
|--------|----------|------|
| ACTIVE | 在线 | 设备正常工作 |
| INACTIVE | 离线 | 设备未连接 |
| FAULT | 故障 | 设备故障 |
| MAINTENANCE | 维护 | 设备维护中 |
| UNAUTHORIZED | 未授权 | 设备未授权 |

### 8.3 服务类型字典 (service_type)

| 类型码 | 类型名称 | 说明 |
|--------|----------|------|
| SGLFREQ | 单频测量 | 单频点测量服务 |
| WBFFT | 宽带FFT | 宽带频谱观测 |
| FSCAN | 扫频测量 | 频段扫描服务 |
| MSCAN | 频率表扫描 | 离散频点测量 |
| IFDF | 中频测向 | 中频FFT测向 |
| SGLFREQ_DF | 单频测向 | 固定频点测向 |
| WBDF | 宽带测向 | 宽带频段测向 |
| FSCAN_DF | 扫频测向 | 扫描步进测向 |
| OCCUPANCY | 占用度测量 | 频段占用度统计 |
| SIGNAL | 信号识别解调 | 数字信号处理 |

### 8.4 ITU测量类型字典 (itu_type)

| 类型码 | 类型名称 | 单位 | 说明 |
|--------|----------|------|------|
| 1 | 信号电平 | dBm | 接收信号强度 |
| 2 | 频率偏移 | Hz | 与标称频率的偏移 |
| 3 | 调制深度 | % | AM调制深度 |
| 4 | 频偏 | Hz | FM频偏 |
| 5 | 信噪比 | dB | 信噪比 |
| 6 | 占用带宽 | Hz | 信号占用带宽 |
| 7 | 邻道功率 | dBc | 邻道泄漏比 |
| 8 | 杂散发射 | dBc | 杂散信号强度 |

### 8.5 调制类型字典 (modulation_type)

| 类型码 | 类型名称 | 说明 |
|--------|----------|------|
| FM | 调频 | 频率调制 |
| AM | 调幅 | 幅度调制 |
| USB | 上边带 | 单边带(上) |
| LSB | 下边带 | 单边带(下) |
| CW | 等幅报 | 连续波 |
| FSK | 频移键控 | 数字调制 |
| PSK | 相移键控 | 相位调制 |
| QAM | 正交幅度 | 正交调制 |
| OFDM | 正交频分 | 多载波调制 |
| UNKNOWN | 未知 | 未能识别 |

---

## 9. 初始化数据

### 9.1 系统配置初始数据

```sql
-- 插入系统配置
INSERT INTO system_config (config_id, config_name, config_value, config_type, config_group, description) VALUES
-- 数据库连接配置
('DB001', 'max_connections', '100', 'DATABASE', 'POOL', '数据库连接池最大连接数'),
('DB002', 'connection_timeout', '30000', 'DATABASE', 'POOL', '数据库连接超时时间(ms)'),
('DB003', 'command_timeout', '60000', 'DATABASE', 'POOL', '命令执行超时时间(ms)'),

-- 服务配置
('SVC001', 'heartbeat_interval', '30000', 'SERVICE', 'HEALTH', '服务心跳间隔(ms)'),
('SVC002', 'health_check_interval', '10000', 'SERVICE', 'HEALTH', '健康检查间隔(ms)'),
('SVC003', 'max_retry_count', '3', 'SERVICE', 'RETRY', '最大重试次数'),

-- 日志配置
('LOG001', 'log_level', 'INFO', 'SYSTEM', 'LOGGING', '日志级别'),
('LOG002', 'log_retention_days', '30', 'SYSTEM', 'LOGGING', '日志保留天数'),
('LOG003', 'audit_enabled', 'true', 'SYSTEM', 'LOGGING', '是否启用审计日志'),

-- 监测配置
('MON001', 'default_rbw', '1000', 'MONITOR', 'SPECTRUM', '默认分辨率带宽(Hz)'),
('MON002', 'default_vbw', '100', 'MONITOR', 'SPECTRUM', '默认视频带宽(Hz)'),
('MON003', 'default_reference_level', '-30', 'MONITOR', 'SPECTRUM', '默认参考电平(dBm)'),
('MON004', 'max_concurrent_tasks', '10', 'MONITOR', 'TASK', '最大并发任务数'),
('MON005', 'task_timeout', '300000', 'MONITOR', 'TASK', '任务默认超时时间(ms)');
```

### 9.2 角色初始数据

```sql
-- 插入默认角色
INSERT INTO sys_role (role_id, role_code, role_name, role_type, description, permissions) VALUES
('ROLE001', 'ADMIN', '系统管理员', 'SYSTEM', '拥有系统全部权限', 
 '["*:*"]'),
('ROLE002', 'OPER', '操作员', 'BUSINESS', '执行监测操作',
 '["task:create", "task:execute", "task:cancel", "monitor:start", "monitor:stop", "data:query", "data:export"]'),
('ROLE003', 'VIEWER', '查看者', 'BUSINESS', '仅可查看数据和任务',
 '["data:query", "data:export"]');
```

### 9.3 行政区划初始数据

```sql
-- 插入省级行政区划
INSERT INTO region_code (code, name, level, parent_code) VALUES
('110000', '北京市', 1, NULL),
('120000', '天津市', 1, NULL),
('310000', '上海市', 1, NULL),
('440000', '广东省', 1, NULL),
('510000', '四川省', 1, NULL);
```

---

## 10. 索引汇总

### 10.1 主键索引

| 表名 | 字段 | 索引类型 |
|------|------|----------|
| monitor_facility | mfid | PRIMARY KEY |
| equipment_info | equid | PRIMARY KEY |
| monitor_task | task_id | PRIMARY KEY |
| service_registry | service_id | PRIMARY KEY |
| sys_user | user_id | PRIMARY KEY |

### 10.2 业务索引

| 表名 | 索引名称 | 索引字段 | 说明 |
|------|----------|----------|------|
| data_sglfreq | idx_sglfreq_time | measure_time | 时间范围查询 |
| data_sglfreq | idx_sglfreq_freq | frequency | 频率查询 |
| data_fscan | idx_fscan_freq_range | start_freq, end_freq | 频段查询 |
| data_direction | idx_df_azimuth | azimuth | 方位角统计 |
| monitor_task | idx_task_scheduled | scheduled_start | 任务调度 |
| equipment_info | idx_equipment_mfid | mfid | 设施设备查询 |

### 10.3 时序索引

| 表名 | 分区字段 | 分区策略 | 保留策略 |
|------|----------|----------|----------|
| data_sglfreq | measure_time | 按天分区 | 90天 |
| data_fscan | measure_time | 按天分区 | 90天 |
| data_direction | measure_time | 按天分区 | 180天 |
| data_occupancy | measure_time | 按天分区 | 180天 |
| data_fft | measure_time | 按天分区 | 30天 |
| sys_audit_log | created_time | 按月分区 | 365天 |

---

## 11. 视图设计

### 11.1 设施设备视图

```sql
-- 监测设施与设备完整信息视图
CREATE OR REPLACE VIEW v_facility_equipment AS
SELECT 
    f.mfid,
    f.facility_name,
    f.facility_type,
    f.station_code,
    f.station_name,
    f.region_code,
    f.latitude,
    f.longitude,
    f.status AS facility_status,
    e.equid,
    e.equipment_name,
    e.equipment_type,
    e.manufacturer,
    e.model,
    e.ip_address,
    e.port,
    e.freq_min,
    e.freq_max,
    e.status AS equipment_status,
    e.last_online_time
FROM monitor_facility f
LEFT JOIN equipment_info e ON f.mfid = e.mfid
ORDER BY f.mfid, e.equid;
```

### 11.2 任务统计视图

```sql
-- 任务执行统计视图
CREATE OR REPLACE VIEW v_task_statistics AS
SELECT 
    t.mfid,
    t.service_type,
    DATE_TRUNC('day', t.created_time) AS stat_date,
    COUNT(*) AS total_tasks,
    COUNT(CASE WHEN t.status = 'COMPLETED' THEN 1 END) AS completed_tasks,
    COUNT(CASE WHEN t.status = 'FAILED' THEN 1 END) AS failed_tasks,
    AVG(EXTRACT(EPOCH FROM (t.actual_end - t.actual_start))) AS avg_duration_seconds
FROM monitor_task t
WHERE t.created_time >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY t.mfid, t.service_type, DATE_TRUNC('day', t.created_time);
```

### 11.3 监测数据汇总视图

```sql
-- 监测数据实时汇总视图
CREATE OR REPLACE VIEW v_monitor_summary AS
SELECT 
    m.mfid,
    f.facility_name,
    m.service_type,
    COUNT(*) AS total_measurements,
    MAX(m.measure_time) AS last_measure_time,
    COUNT(DISTINCT DATE_TRUNC('hour', m.measure_time)) AS active_hours
FROM (
    SELECT mfid, equid, frequency, measure_time, 'SGLFREQ' AS service_type FROM data_sglfreq
    UNION ALL
    SELECT mfid, equid, start_freq, measure_time, 'FSCAN' AS service_type FROM data_fscan
    UNION ALL
    SELECT mfid, equid, frequency, measure_time, 'DF' AS service_type FROM data_direction
) m
JOIN monitor_facility f ON m.mfid = f.mfid
GROUP BY m.mfid, f.facility_name, m.service_type;
```

---

## 12. 数据生命周期管理

### 12.1 保留策略

| 数据类型 | 保留周期 | 存储位置 | 归档策略 |
|----------|----------|----------|----------|
| 实时监测数据 | 90天 | 时序数据库 | 热存储 |
| 历史监测数据 | 1年 | 归档存储 | 冷存储 |
| 任务日志 | 180天 | PostgreSQL | - |
| 操作审计 | 365天 | PostgreSQL | 按月分区 |
| 系统配置 | 永久 | PostgreSQL | - |
| 设备信息 | 永久 | PostgreSQL | - |

### 12.2 归档存储过程

```sql
-- 数据归档存储过程
CREATE OR REPLACE FUNCTION archive_old_data(
    p_data_type VARCHAR,
    p_before_date DATE
) RETURNS void AS $$
DECLARE
    v_table_name VARCHAR;
BEGIN
    -- 根据数据类型确定归档目标表
    CASE p_data_type
        WHEN 'SGLFREQ' THEN v_table_name := 'data_sglfreq_archive';
        WHEN 'FSCAN' THEN v_table_name := 'data_fscan_archive';
        WHEN 'DIRECTION' THEN v_table_name := 'data_direction_archive';
        ELSE RAISE EXCEPTION 'Unknown data type: %', p_data_type;
    END CASE;
    
    -- 执行归档插入
    EXECUTE format(
        'INSERT INTO %I SELECT * FROM data_%s WHERE measure_time < %L',
        v_table_name,
        lower(p_data_type),
        p_before_date
    );
    
    -- 删除已归档数据
    EXECUTE format(
        'DELETE FROM data_%s WHERE measure_time < %L',
        lower(p_data_type),
        p_before_date
    );
END;
$$ LANGUAGE plpgsql;
```

---

## 13. 附录

### 13.1 ER图关键实体

```
┌─────────────────┐       ┌─────────────────┐
│ MonitorFacility │──────<│ EquipmentInfo   │
│ 监测设施         │  1:N  │ 设备信息         │
├─────────────────┤       ├─────────────────┤
│ mfid (PK)       │       │ equid (PK)      │
│ facility_name   │       │ mfid (FK)       │
│ facility_type   │       │ equipment_type  │
│ station_code    │       │ manufacturer    │
│ region_code     │       │ ip_address      │
└─────────────────┘       │ freq_min/max    │
         │                └─────────────────┘
         │
         │ 1:N
         ▼
┌─────────────────┐       ┌─────────────────┐
│ MonitorTask     │──────<│ DataSglFreq     │
│ 监测任务         │  1:N  │ 单频测量数据     │
├─────────────────┤       ├─────────────────┤
│ task_id (PK)    │       │ data_id (PK)    │
│ mfid (FK)       │       │ task_id (FK)    │
│ task_type       │       │ frequency       │
│ status          │       │ measure_time    │
│ parameters       │       │ signal_level    │
└─────────────────┘       └─────────────────┘
```

### 13.2 参考标准

- GWJ001-2015 平台架构规范
- GWJ002-2015 服务和接口规范
- GWJ003-2015 设备操作服务规范
- GWJ004-2015 数据服务规范
- GWJ006-2016 数据存储结构规范

---

**文档结束**
