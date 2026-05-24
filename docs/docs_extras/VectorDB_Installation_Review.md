# 向量数据库安装回顾

> 归档日期：2026-04-06
> 作用域：整个 claude_workspace

---

## 一、选型过程

### 1.1 候选方案

| 方案 | 安装方式 | 是否含FAISS | 特点 |
|------|---------|------------|------|
| **ChromaDB** | `pip install chromadb` | ✅ 内置FAISS | 轻量级，API简单，持久化 |
| FAISS（纯） | `pip install faiss-cpu` | ✅ 纯FAISS | 高性能，需自己管理索引 |
| Qdrant | Docker | ❌ 自研 | 向量+标量过滤，REST/gRPC API |
| Milvus | Docker | ❌ 自研 | 大规模分布式，GPU支持 |
| Weaviate | Docker | ❌ 自研 | 混合搜索 |
| LanceDB | `pip install lancedb` | ❌ 自研 | 零拷贝，多语言 |

**选择理由**：ChromaDB 当时首选（内置FAISS，开箱即用）

---

## 二、ChromaDB 安装与问题排查

### 2.1 安装

```bash
pip install chromadb -i https://pypi.org/simple/
```

> 注：清华镜像源无匹配版本，需使用官方源

**安装成功** — ChromaDB v1.5.5，Python 3.13，Windows 11

### 2.2 首次启动（HTTP 服务模式）

```bash
chroma run --host localhost --port 8000
```

```
Saving data to: ./chroma
Connect to Chroma at: http://localhost:8000
```

启动成功 ✅，心跳检测正常 ✅

### 2.3 尝试向量化记忆文件

#### 方案 A：使用默认 embedding（ONNXMiniLM_L6_V2）

**失败** ❌

```
ImportError: DLL load failed while importing onnxruntime_pybind11_state:
动态链接库(DLL)初始化例程失败。
```

**原因**：onnxruntime 的 C++ 运行时 DLL 在 Windows 上加载失败

#### 方案 B：安装 sentence-transformers + Torch

**失败** ❌

```
OSError: [WinError 1114] 动态链接库(DLL)初始化例程失败。
Error loading "c10.dll" or one of its dependencies.
```

**原因**：PyTorch 同样存在 DLL 加载问题，Windows 环境对 ONNX/PyTorch 系库普遍存在兼容性问题

#### 方案 C：使用 OllamaEmbeddingFunction（Ollama nomic-embed-text）

**失败** ❌

- Ollama 运行正常（`E:\Ollama\ollama.exe`，`nomic-embed-text` 模型已下载）✅
- Python `ollama` 包安装成功 ✅
- embedding 计算成功（768维）✅
- 但通过 HTTP API add 数据时，ChromaDB 服务端返回 502 Bad Gateway
- 服务端进程崩溃 ❌

**过程记录**：
1. 创建 collection 成功
2. 发送 add 请求后服务端 502
3. 服务端进程消失（崩溃）
4. 反复测试多次，结果一致

**尝试的解决方案**：

| 尝试 | 方法 | 结果 |
|------|------|------|
| 换用 PersistentClient（嵌入式） | `chromadb.PersistentClient(path='...')` | Segfault ❌ |
| 添加 `--path` 持久化参数 | 持久化文件模式 | 仍崩溃 ❌ |
| 预计算 embedding 后传入 | 绕过客户端 embedding | 服务端崩溃 ❌ |

**推测根因**：ChromaDB 1.5.5 与 Python 3.13 存在兼容性问题，即使传入了预计算的 embedding，服务端内部处理数据时仍会触发 onnxruntime 相关路径，导致 FastAPI worker 崩溃。

---

## 三、ChromaDB 文件路径

| 类型 | 路径 |
|------|------|
| Python 包 | `C:\Users\tuoyi5\AppData\Local\Programs\Python\Python313\Lib\site-packages\chromadb` |
| CLI 可执行文件 | `C:\Users\tuoyi5\AppData\Local\Programs\Python\Python313\Scripts\chroma.exe` |
| 启动脚本 | `D:\arvin\claude_workspace\services\chromadb\run_chromadb.bat` |
| 服务说明 | `D:\arvin\claude_workspace\services\chromadb\README.md` |

---

## 四、自建向量存储方案

### 4.1 方案 A：vector_store.py

**成功** ✅

基于 Ollama embedding + JSON 持久化，自建轻量向量库：

```
D:\arvin\claude_workspace\services\vector_store.py
```

**特点**：
- 使用 Ollama `nomic-embed-text` 计算 embedding（768维）
- JSON 文件持久化
- 余弦相似度查询
- 绕过 ChromaDB，避开 DLL 问题

**向量化结果**：
- 记忆文件：MEMORY.md, project_specdetect.md, feedback_testing.md
- 查询 "向量数据库 ChromaDB"：
  1. project_specdetect.md (distance: 0.3648)
  2. feedback_testing.md (distance: 0.3786)

### 4.2 方案 C：Qdrant Docker

**成功** ✅

最终采用方案，作为生产级向量数据库。

---

## 五、Qdrant Docker 安装与配置

### 5.1 前提条件

Docker Desktop 必须处于运行状态。

启动 Docker Desktop：
```bash
"C:/Program Files/Docker/Docker/Docker Desktop.exe"
```

### 5.2 启动命令

```bash
docker run -d --name qdrant \
  -p 6333:6333 \
  -p 6334:6334 \
  -v D:/arvin/claude_workspace/services/qdrant/storage:/qdrant/storage \
  qdrant/qdrant
```

### 5.3 服务信息

| 项目 | 值 |
|------|---|
| HTTP API | `http://localhost:6333` |
| gRPC API | `localhost:6334` |
| Dashboard | `http://localhost:6333/dashboard` |
| 数据目录 | `D:\arvin\claude_workspace\services\qdrant\storage\` |
| 初始状态 | 无 collections |

### 5.4 验证

```bash
curl http://localhost:6333/collections
# {"result":{"collections":[]},"status":"ok",...}
```

---

## 六、方案对比总结

| 维度 | vector_store.py | Qdrant Docker | ChromaDB |
|------|-----------------|---------------|----------|
| 稳定性 | ✅ 稳定 | ✅ 稳定 | ❌ 服务端崩溃 |
| 数据规模 | ~万条 | 百万~亿级 | ~万条 |
| 查询性能 | O(n) 全量遍历 | O(log n) HNSW | O(log n) HNSW |
| API 丰富度 | 基础 | 完整 | 完整 |
| 持久化 | JSON | RocksDB | 嵌入式 |
| UI | 无 | Web Dashboard | 无 |
| 依赖 | Ollama | Docker | onnxruntime（有问题） |

---

## 七、当前状态

| 项目 | 状态 |
|------|------|
| ChromaDB pip 包 | 已安装（服务不稳定） |
| Ollama embedding | 正常（nomic-embed-text） |
| vector_store.py | 已验证可用 |
| Qdrant Docker | 已启动，数据目录已创建 |

---

## 八、后续任务

- [ ] 用 Qdrant 重新向量化记忆文件
- [ ] 更新 vector_store.py 改用 Qdrant 作为后端
- [ ] 编写 Qdrant 使用文档

---

## 九、相关文档

| 文档 | 说明 |
|------|------|
| `services/chromadb/run_chromadb.bat` | ChromaDB 启动脚本 |
| `services/chromadb/README.md` | ChromaDB 服务说明 |
| `services/vector_store.py` | 自建向量存储 |
| `services/qdrant/storage/` | Qdrant 数据目录 |
| `docs/VectorDB_Archive.md` | 向量数据库归档文档 |
| `memory/project_specdetect.md` | Claude Code 记忆 |
