# VectorManager 向量管理器

> 创建日期：2026-04-06
> 文件位置：`D:\arvin\claude_workspace\services\vector_manager.py`

---

## 一、概述

VectorManager 是一个自动化向量存储模块，为 claude_workspace 提供记忆向量化能力。

**功能**：
- 依赖检查（Docker/Qdrant, Ollama）
- 条件满足时自动向量化
- 条件不满足时降级处理
- 自行启动服务（尽可能）

---

## 二、依赖项

| 依赖 | 作用 | 默认端口 |
|------|------|---------|
| Docker Desktop | Qdrant 容器运行环境 | - |
| Qdrant Docker | 向量数据库服务 | 6333/6334 |
| Ollama | embedding 计算 | 11434 |
| Python qdrant-client | Qdrant Python SDK | - |
| Python ollama | Ollama Python SDK | - |

---

## 三、文件路径

| 文件 | 路径 |
|------|------|
| 向量管理器 | `D:\arvin\claude_workspace\services\vector_manager.py` |
| Qdrant 数据 | `D:\arvin\Qdrant_workspace\storage\` |
| Qdrant collection | `memory` |

---

## 四、API 使用

### 4.1 基础用法

```python
from services.vector_manager import get_manager, vectorize_memory, query_memory

# 获取管理器（自动检查依赖并连接）
m = get_manager()

# 向量化所有记忆文件
result = vectorize_memory()
# 返回: {'status': 'ok', 'count': 3, 'failed': []}

# 查询记忆
results = query_memory("向量数据库 ChromaDB", limit=3)
# 返回: [{'source': '...', 'score': 0.6352, 'path': '...', 'id': ...}]

# 查看状态
print(m.status())
```

### 4.2 详细 API

#### `VectorManager.ensure_dependencies()`

检查并启动所有依赖，返回 `True` 表示正常模式，`False` 表示降级模式。

#### `VectorManager.vectorize_file(file_path, file_id, metadata)`

向量化单个文件。

```python
m.vectorize_file(
    file_path='C:/path/to/file.md',
    file_id='unique_id',
    metadata={'source': 'filename.md', 'type': 'project'}
)
```

#### `VectorManager.query(query_text, limit=2)`

查询最相似的记忆。

```python
results = m.query("SpecDetect 项目", limit=5)
for r in results:
    print(f"[{r['score']:.4f}] {r['source']}")
```

#### `VectorManager.status()`

返回当前状态字典：

```python
{
    'connected': True,        # 是否已连接 Qdrant
    'fallback_mode': False,   # 是否降级模式
    'docker': True,           # Docker 是否运行
    'qdrant': True,           # Qdrant 是否就绪
    'ollama': True,           # Ollama 是否就绪
}
```

---

## 五、自动化行为

| 情况 | 行为 |
|------|------|
| 依赖满足 | 自动连接，直接使用 |
| Ollama 未运行 | 自动启动 `ollama serve`，等待30秒 |
| Docker 未运行 | 自动启动 Docker Desktop，等待90秒 |
| Qdrant 未运行 | 自动启动/重启 qdrant 容器，等待30秒 |
| 全部失败 | 降级模式，跳过向量化，打印警告 |

**降级模式**：不抛出异常，向量化操作静默跳过，保留纯文本记录。

---

## 六、降级模式说明

降级模式下：
- `vectorize_file()` 返回 `False`，不写入向量数据库
- `query()` 返回空列表 `[]`
- `status()['fallback_mode']` 为 `True`
- 不影响程序继续运行

---

## 七、测试

```bash
cd D:\arvin\claude_workspace\services
python vector_manager.py
```

预期输出：
```
依赖检查...
[OK] Ollama 已就绪
[OK] Docker 已就绪
[OK] Qdrant 已就绪
[OK] 向量管理器已就绪

--- 向量化记忆 ---
[OK] MEMORY.md
[OK] project_specdetect.md
[OK] feedback_testing.md
结果: {'status': 'ok', 'count': 3, 'failed': []}

--- 查询测试 ---
[0.6352] project_specdetect.md
[0.6352] project_specdetect.md
```

---

## 八、相关文档

| 文档 | 说明 |
|------|------|
| `docs/VectorDB_Installation_Review.md` | 向量数据库安装回顾 |
| `docs/VectorDB_Archive.md` | 向量数据库归档 |
| `D:\arvin\Qdrant_workspace\storage\` | Qdrant 数据目录 |
