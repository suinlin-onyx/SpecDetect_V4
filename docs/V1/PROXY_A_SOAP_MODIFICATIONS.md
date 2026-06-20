# Proxy-A SOAP 接口改造文档

> 创建日期：2026-04-08
> 更新日期：2026-04-08
> 状态：✅ 已完成

---

## 1. 架构概述

```
Client → Proxy-A(8080) → Mock Atom(9090) → Real Device(172.18.114.33:8282)
```

| 组件 | 地址 | 说明 |
|------|------|------|
| Proxy-A | 127.0.0.1:8080 | SOAP 代理服务 |
| Mock Atom | 127.0.0.1:9090 | SOAP 服务端 |
| Real Device | 172.18.114.33:8282 | RMCPTP 设备 |

---

## 2. 支持的 SOAP 接口

### 2.1 接口总览

| # | 接口名称 | equpara格式 | outputchannel | taskid | 说明 |
|---|---------|-------------|--------------|--------|------|
| 1 | B_QueryDeviceInfo | xsi:nil | 否 | 否 | 设备信息查询 |
| 2 | B_QueryFaciDevStat | xsi:nil | 否 | 否 | 设备状态查询 |
| 3 | B_StopMeas | xsi:nil | 否 | 回显 | 停止测量 |
| 4 | B_SglFreqMeas | items | 是 | 是 | 单频测量 |
| 5 | B_SglFreqDF | items | 是 | 是 | 单频测向 |
| 6 | B_FScan | groupitems | 是 | 是 | 频段扫描 |
| 7 | B_FScanDF | items | 是 | 是 | 频段扫描测向 |
| 8 | B_MScan | groupitems | 是 | 是 | 多信道扫描 |
| 9 | B_MScanDF | items | 是 | 是 | 多信道扫描测向 |
| 10 | B_PScan | items | 是 | 是 | 频谱扫描 |
| 11 | B_WBDF | items | 是 | 是 | 宽带测向 |

### 2.2 接口分类

| 分类 | 接口 | 设备连接 | 说明 |
|------|------|---------|------|
| 查询接口 | B_QueryDeviceInfo, B_QueryFaciDevStat | 不需要 | 直接返回配置/状态 |
| 控制接口 | B_StopMeas | 不需要 | 停止任务，回显taskid |
| 执行接口 | 其他7个 | 需要 | 需连接设备发送RMCPTP |

---

## 3. SOAP 响应格式

### 3.1 成功响应

| 字段 | 位置 | 值 |
|------|------|-----|
| bizResCd | Header | BIZ-000001 |
| bizResText | Header | 调用成功 |

### 3.2 失败响应

| 字段 | 位置 | 值 |
|------|------|-----|
| bizResCd | Header | BIZ-000002 |
| bizResText | Header | 错误描述 |
| type | Body/error | cancel |
| code | Body/error | BIZ-000002 |
| text | Body/error | 错误描述 |

---

## 4. 关键函数

| 函数名 | 文件 | 功能 |
|--------|------|------|
| handle_soap() | main_atom.py | SOAP 请求入口，解析并分发 |
| dispatch_soap_operation() | main_atom.py | 根据操作类型分发到业务处理 |
| build_soap_response() | main_atom.py | 构建 Real Atom 格式响应 |
| load_device_config() | main_atom.py | 从XML文件加载设备配置 |
| _build_device_info_result() | main_atom.py | 构建设备信息查询结果 |
| _build_featurelist_into_result() | main_atom.py | 构建 featurelist XML 结构 |

---

## 5. 设备配置

### 5.1 配置文件路径

```
device/config/devinfo/{mfid}_{equid}.xml
```

示例：`device/config/devinfo/53090001140012_51cd8dfe-e543-40c9-bdc3-a292766fee7f.xml`

### 5.2 配置字段

| 字段 | 说明 |
|------|------|
| mfid | 厂商ID |
| equid | 设备ID |
| equname | 设备名称 |
| equtype | 设备类型 |
| equstatus | 设备状态 |
| equimanu | 制造商 |
| equmodel | 设备型号 |
| equsn | 序列号 |
| maxtasknumber | 最大任务数 |

---

## 6. equpara 结构

### 6.1 xsi:nil 格式（查询/控制接口）

```xml
<srrc:equpara xsi:nil="true" xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"/>
```

### 6.2 items 格式（单参数接口）

```xml
<srrc:equpara>
  <srrc:items>
    <srrc:item>
      <srrc:paraname>frequency</srrc:paraname>
      <srrc:paravalue>100000000</srrc:paravalue>
    </srrc:item>
  </srrc:items>
</srrc:equpara>
```

### 6.3 groupitems 格式（多参数接口）

```xml
<srrc:equpara>
  <srrc:groupitems>
    <srrc:groupitem>
      <srrc:groupid>1</srrc:groupid>
      <srrc:items>
        <srrc:item>
          <srrc:paraname>startfreq</srrc:paraname>
          <srrc:paravalue>137000000</srrc:paravalue>
        </srrc:item>
        <srrc:item>
          <srrc:paraname>stopfreq</srrc:paraname>
          <srrc:paravalue>173000000</srrc:paravalue>
        </srrc:item>
      </srrc:items>
    </srrc:groupitem>
  </srrc:groupitems>
</srrc:equpara>
```

---

## 7. 临时修改记录

| # | 位置 | 修改内容 | 原因 | 状态 |
|---|------|---------|------|------|
| 1 | main_atom.py:891 | 注释掉 check_device_connected() 检查 | 跳过设备连接检查，方便测试RMCPTP请求 | ⚠️ 待恢复 |

**恢复方法**：删除注释，还原代码

---

## 8. 配置参数

### 8.1 settings.py

| 参数 | 值 | 说明 |
|------|-----|------|
| atom.device_host | 172.18.114.33 | 目标设备地址 |
| atom.device_port | 8282 | 目标设备端口 |
| protocol.timeout | 10.0 | 连接超时(秒) |

---

## 9. 测试结果

| # | 接口 | SOAPAction | 结果 | bizResCd |
|---|------|------------|------|----------|
| 1 | B_QueryDeviceInfo | B_QueryDeviceInfo | ✅ | BIZ-000001 |
| 2 | B_QueryFaciDevStat | B_QueryFaciDevStat | ✅ | BIZ-000001 |
| 3 | B_StopMeas | B_StopMeas | ✅ | BIZ-000001 |
| 4 | B_SglFreqMeas | B_SglFreqMeas | ⚠️ | BIZ-000002(设备未连接) |
| 5 | B_SglFreqDF | B_SglFreqDF | ⚠️ | BIZ-000002 |
| 6 | B_FScan | B_FScan | ⚠️ | BIZ-000002 |
| 7 | B_FScanDF | B_FScanDF | ⚠️ | BIZ-000002 |
| 8 | B_MScan | B_MScan | ⚠️ | BIZ-000002 |
| 9 | B_MScanDF | B_MScanDF | ⚠️ | BIZ-000002 |
| 10 | B_PScan | B_PScan | ⚠️ | BIZ-000002 |
| 11 | B_WBDF | B_WBDF | ⚠️ | BIZ-000002 |

**说明**：执行接口返回 BIZ-000002 是因为远端设备 172.18.114.33:8282 不可达

---

## 10. 相关文件

| 文件路径 | 作用 |
|----------|------|
| main_atom.py | Mock Atom 主服务 |
| config/settings.py | Proxy-A 配置 |
| device/config/devinfo/*.xml | 设备配置文件 |
| app/atom_service/device_client.py | RMCPTP 客户端 |
| app/atom_service/protocol_builder.py | RMCPTP 帧构建 |

---

## 11. 命名空间

| 前缀 | 命名空间 |
|------|----------|
| soapenv | http://schemas.xmlsoap.org/soap/envelope/ |
| srrc | http://www.srrc.org.cn |
| mon | http://monitor.rrmp.gov.cn/services/ |
