# Proxy-A 链路改造分析文档

> 创建日期：2026-04-08
> 更新日期：2026-04-08
> 目标：以 Proxy-B 链条为标准，改造 Proxy-A 链条，使 Mock Atom 返回与 Real Atom 一致的数据结构

---

## 1. 当前状态对比

### 1.1 两条链路的请求格式已统一

**routes.py 中的 `build_real_atom_request()`** 已实现：
- 使用 srrc 命名空间
- 使用 requestbody 结构
- 正确处理 equpara/items 和 equpara/groupitems 格式
- 正确添加 outputchannel

**结论**：Proxy-A 发出的请求格式已与 Proxy-B 一致，无需修改。

### 1.2 响应格式差异

| 接口 | Real Atom 响应 | Mock Atom 响应 | 差异 |
|------|---------------|----------------|------|
| B_QueryDeviceInfo | 复杂嵌套结构，含 featurelist 参数定义 | 简化列表 | **需改造** |
| B_QueryFaciDevStat | 设备状态信息 | 简化状态 | 需改造 |
| B_StopMeas | 停止确认 | 简化 | 基本满足 |
| B_SglFreqMeas | 测量结果+taskid | 测量结果+taskid | 基本满足 |
| B_SglFreqDF | 测向结果+taskid | 测向结果+taskid | 基本满足 |
| B_FScan | 扫描结果+taskid | 扫描结果+taskid | 基本满足 |
| B_PScan | 频谱结果+taskid | 频谱结果+taskid | 基本满足 |
| B_WBDF | 宽带测向结果 | 宽带测向结果 | 基本满足 |
| B_MScan | 多信道结果 | 多信道结果 | 基本满足 |
| B_MScanDF | 多信道测向结果 | 多信道测向结果 | 基本满足 |

---

## 2. 主要差异：B_QueryDeviceInfo

### 2.1 Real Atom 响应格式（完整结构）

```json
{
  "bizResCd": "BIZ-000001",
  "bizResText": "调用成功",
  "result": {
    "mfid": "53090001140012",
    "equid": "51cd8dfe-e543-40c9-bdc3-a292766fee7f",
    "equimanu": "KYB",
    "equmodel": "MS845",
    "equname": "MS845",
    "equsn": "12345678",
    "equstatus": "01",
    "equtype": "01",
    "maxtasknumber": 1,
    "featurelist": [
      {
        "code": "B_QueryDeviceInfo",
        "input": null
      },
      {
        "code": "B_SglFreqMeas",
        "input": {
          "parameters": [
            {"name": "frequency", "displayname": "频率", "type": "double", "defaultvalue": 100000000, "range": {"startval": 20000000, "stopval": 6000000000}},
            {"name": "ifbw", "displayname": "中频带宽", "type": "String", "defaultvalue": 40000000},
            ...
          ]
        }
      }
    ]
  }
}
```

### 2.2 Mock Atom 当前响应（简化结构）

```python
{
    'success': True,
    'taskid': task_id,
    'result': {
        'mfid': '53090001140007',
        'equid': 'mock-equid-001',
        'equimanu': 'Mock',
        'equmodel': 'MockAtom',
        'equname': 'Mock Atom',
        'equsn': 'MOCK123456',
        'equstatus': '01',
        'equtype': '01',
        'maxtasknumber': 1,
        'featurelist': [
            'B_QueryDeviceInfo',
            'B_QueryFaciDevStat',
            ...
        ]
    }
}
```

### 2.3 差异分析

| 字段 | Real Atom | Mock Atom | 说明 |
|------|-----------|-----------|------|
| featurelist | 对象数组，含 code/input | 字符串数组 | Mock Atom 缺少参数定义 |
| taskid | 无 | 有 | Real Atom 不返回 taskid |
| result 结构 | 扁平化 | 扁平化 | 一致 |

---

## 3. 需修改的文件

### 3.1 main_atom.py

**位置**: `dispatch_soap_operation()` 函数中的 B_QueryDeviceInfo 处理

**当前代码** (行 653-683):
```python
if operation == 'B_QueryDeviceInfo':
    return {
        'success': True,
        'taskid': task_id,
        'result': {
            'mfid': '53090001140007',
            'equid': 'mock-equid-001',
            'equimanu': 'Mock',
            'equmodel': 'MockAtom',
            'equname': 'Mock Atom',
            'equsn': 'MOCK123456',
            'equstatus': '01',
            'equtype': '01',
            'maxtasknumber': 1,
            'featurelist': [
                'B_QueryDeviceInfo',
                'B_QueryFaciDevStat',
                'B_TaskModification',
                'B_StopMeas',
                'B_SglFreqMeas',
                'B_SglFreqDF',
                'B_MScan',
                'B_MScanDF',
                'B_FScan',
                'B_FScanDF',
                'B_PScan',
                'B_WBDF'
            ]
        }
    }
```

**目标格式**:
```python
if operation == 'B_QueryDeviceInfo':
    return {
        'success': True,
        'result': {
            'mfid': '53090001140012',
            'equid': '51cd8dfe-e543-40c9-bdc3-a292766fee7f',
            'equimanu': 'KYB',
            'equmodel': 'MS845',
            'equname': 'MS845',
            'equsn': '12345678',
            'equstatus': '01',
            'equtype': '01',
            'maxtasknumber': 1,
            'featurelist': [
                {'code': 'B_QueryDeviceInfo', 'input': None},
                {'code': 'B_QueryFaciDevStat', 'input': None},
                {'code': 'B_TaskModification', 'input': None},
                {'code': 'B_StopMeas', 'input': None},
                {'code': 'B_SglFreqMeas', 'input': {'parameters': [...]}},
                {'code': 'B_SglFreqDF', 'input': {'parameters': [...]}},
                {'code': 'B_MScan', 'input': {'parameters': [...]}},
                {'code': 'B_MScanDF', 'input': {'parameters': [...]}},
                {'code': 'B_FScan', 'input': {'parameters': [...]}},
                {'code': 'B_FScanDF', 'input': {'parameters': [...]}},
                {'code': 'B_PScan', 'input': {'parameters': [...]}},
                {'code': 'B_WBDF', 'input': {'parameters': [...]}}
            ]
        }
    }
```

---

## 4. 改造步骤

### 步骤 1：修改 B_QueryDeviceInfo 响应（高优先级）

**文件**: `main_atom.py`
**函数**: `dispatch_soap_operation()` 中的 B_QueryDeviceInfo 分支
**修改内容**: 返回完整的 featurelist 结构

### 步骤 2：修改 B_StopMeas 响应（移除 taskid）

**文件**: `main_atom.py`
**函数**: `dispatch_soap_operation()` 中的 B_StopMeas 分支
**当前**: 返回 `{'taskid': stop_taskid, ...}`
**目标**: Real Atom 不返回 taskid

### 步骤 3：验证 SOAP 响应格式

**文件**: `main_atom.py`
**函数**: `build_soap_response()`
**检查**: 确保输出的 XML 格式与 Real Atom 一致

---

## 5. 执行接口的响应

执行接口（B_SglFreqMeas、B_FScan 等）的响应格式在 Mock Atom 和 Real Atom 之间差异较小，主要差异：

| 字段 | Real Atom | Mock Atom | 说明 |
|------|-----------|-----------|------|
| taskid | **无** | 有 | Real Atom 不返回 taskid |
| result 嵌套 | 是 | 是 | 格式一致 |

**建议**: 执行接口的 taskid 差异可暂时忽略（客户端通常不依赖此字段）

---

## 6. 配置文件确认

**settings.py** 中 Mock Atom 指向的设备地址：
```python
SERVICES = {
    'atom': {
        'device_host': '172.18.114.33',  # Real Device 地址
        'device_port': 9998               # Real Device RMCPTP 端口
    }
}
```

---

## 7. 预期结果

改造完成后：
- Proxy-A (8080) → Mock Atom (9090) → Real Device (172.18.114.33:9998)
- Mock Atom 的 SOAP 响应格式与 Real Atom 基本一致
- 客户端可以无感知地切换 Proxy-A 和 Proxy-B

---

## 8. 相关文件清单

| 文件 | 作用 | 需修改 |
|------|------|--------|
| `main_atom.py` | Mock Atom 主服务 | ✅ 是 |
| `routes.py` | Proxy 路由 | ❌ 否（已统一） |
| `settings.py` | 服务配置 | ❌ 否 |
| `build_soap_response()` | SOAP 响应构建 | ✅ 是（确认格式） |

---

## 9. 下一步行动

1. [ ] 修改 main_atom.py 中的 B_QueryDeviceInfo 返回完整 featurelist
2. [ ] 修改 main_atom.py 中的 B_StopMeas 移除 taskid
3. [ ] 验证 build_soap_response() 输出格式
4. [ ] 启动 Dual Proxy 进行对比测试
