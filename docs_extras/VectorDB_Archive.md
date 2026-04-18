# 向量数据库归档

> 归档日期：2026-04-06
> 更新时间：2026-04-06（ChromaDB 卸载，Qdrant 为当前方案）
> 作用域：整个 claude_workspace

---

## 一、选型方案

| 方案 | 安装方式 | 是否含FAISS | 特点 |
|------|---------|------------|------|
| ~~ChromaDB~~ | ~~已卸载~~ | ~~已卸载~~ | ~~onnxruntime DLL 兼容性问题，已废弃~~ |
| ~~FAISS（纯）~~ | ~~pip install faiss-cpu~~ | ~~纯FAISS~~ | ~~DLL 加载失败~~ |
| **Qdrant** ✅ | Docker | ❌ 自研 | 向量+标量过滤，REST/gRPC API |
| Milvus | Docker | ❌ 自研 | 大规模分布式，GPU支持 |
| Weaviate | Docker | ❌ 自研 | 混合搜索 |
| LanceDB | `pip install lancedb` | ❌ 自研 | 零拷贝，多语言 |

**当前方案**：Qdrant Docker（稳定，已在用）

---

## 二、当前向量数据库状态

| 数据库 | 端口 | 状态 | 用途 |
|--------|------|------|------|
| **Qdrant** | 6333 | ✅ 运行中 | claude_workspace 主向量数据库 |
| `memory` | - | ✅ | Claude Code 记忆向量化 |
| `mem0` | - | ✅ | **Qclaw 智能体**（非本 workspace） |

---

## 三、文件路径总览

### 3.1 Qdrant Docker

| 类型 | 绝对路径 |
|------|---------|
| 数据目录 | `D:\arvin\claude_workspace\services\qdrant\storage\` |
| 启动命令 | `docker run -d --name qdrant -p 6333:6333 -p 6334:6334 -v D:/arvin/claude_workspace/services/qdrant/storage:/qdrant/storage qdrant/qdrant` |

### 3.2 ChromaDB（已卸载）

| 类型 | 原路径（已删除） |
|------|------------------|
| Python 包 | `C:\Users\tuoyi5\AppData\Local\Programs\Python\Python313\Lib\site-packages\chromadb` |
| CLI 可执行文件 | `C:\Users\tuoyi5\AppData\Local\Programs\Python\Python313\Scripts\chroma.exe` |
| 启动脚本 | `D:\arvin\claude_workspace\services\chromadb\`（已删除） |

---

## 四、ChromaDB 卸载原因

- onnxruntime DLL 在 Windows 上加载失败
- ChromaDB HTTP 服务端在调用 Ollama embedding 时崩溃
- Qdrant Docker 更稳定，已满足需求

---

## 五、Qdrant 使用

### 5.1 启动

```bash
docker run -d --name qdrant \
  -p 6333:6333 -p 6334:6334 \
  -v D:/arvin/claude_workspace/services/qdrant/storage:/qdrant/storage \
  qdrant/qdrant
```

### 5.2 连接

```python
from qdrant_client import QdrantClient
client = QdrantClient("localhost", port=6333)
```

### 5.3 Dashboard

```
http://localhost:6333/dashboard
```

---

## 六、相关文档

| 文档 | 说明 |
|------|------|
| `services/vector_manager.py` | 向量管理器（自动启动 Qdrant） |
| `docs/VectorDB_Installation_Review.md` | 安装回顾 |
| `memory/project_specdetect.md` | Claude Code 记忆 |

---

## 三、安装步骤

### 3.1 在线安装

```bash
pip install chromadb -i https://pypi.org/simple/
```

> 注：清华镜像源无匹配版本，需使用官方源

### 3.2 离线环境安装

```bash
pip install -r requirements.txt -i https://pypi.org/simple/
```

requirements.txt 内容：
```txt
chromadb>=1.5.0
```

---

## 四、启动与运行

### 4.1 启动服务

双击运行，或命令行：
```bash
cd D:\arvin\claude_workspace\services\chromadb
run_chromadb.bat
```

### 4.2 服务地址

| 项目 | 值 |
|------|---|
| Host | `localhost` |
| Port | `8000` |
| 协议 | HTTP |

---

## 五、客户端使用

### 5.1 连接

```python
import chromadb

client = chromadb.HttpClient(host="localhost", port=8000)
```

### 5.2 创建 Collection

```python
collection = client.create_collection("my_data")
```

### 5.3 添加数据

```python
collection.add(
    ids=["id1", "id2"],
    embeddings=[[0.1, 0.2, 0.3], [0.4, 0.5, 0.6]],
    metadatas=[{"source": "doc1"}, {"source": "doc2"}]
)
```

### 5.4 相似度查询

```python
results = collection.query(
    query_embeddings=[[0.1, 0.2, 0.3]],
    n_results=2
)
```

---

## 六、开机自启（可选）

1. 打开"任务计划程序"
2. 创建基本任务
3. 触发器：计算机启动
4. 操作：启动程序
5. 程序：`C:\Users\tuoyi5\AppData\Local\Programs\Python\Python313\Scripts\chroma.exe`
6. 参数：`run --host localhost --port 8000`

---

## 七、注意事项

1. **首次运行需等待启动**：ChromaDB 服务启动约需 2-3 秒
2. **端口占用**：确保 8000 端口未被占用
3. **Windows 兼容性**：推荐使用 HTTP 服务模式（`chroma run`）
4. **独立运行**：ChromaDB 是 workspace 级别公共服务，不随项目启动

---

## 八、相关文档

| 文档 | 说明 |
|------|------|
| `services/chromadb/README.md` | 服务使用说明 |
| `services/chromadb/run_chromadb.bat` | 启动脚本 |
| `memory/project_specdetect.md` | Claude Code 记忆 |
| `SpecDetect_V4/docs/CHROMADB_SETUP.md` | 项目级文档（已废弃，迁移至本文档） |
