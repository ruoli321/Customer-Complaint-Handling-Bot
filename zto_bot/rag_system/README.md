# 中通快递投诉机器人 - RAG 系统

基于 RAG（检索增强生成）的中通快递投诉智能助手。

## 系统架构

```
┌─────────────────────────────────────────────┐
│              RAG 系统流程                    │
├─────────────────────────────────────────────┤
│  1. 文档分块 (Chunking)                      │
│     → 将长文档切分为 200 字符的小块           │
│                                              │
│  2. 向量化 (Embedding)                       │
│     → 使用本地 BGE 模型生成向量              │
│     → 存储到 Chroma 向量数据库              │
│                                              │
│  3. 检索 (Retrieval)                         │
│     → 向量相似度检索 Top-N 候选              │
│     → Cross-Encoder 重排序精排               │
│                                              │
│  4. 生成 (Generation)                        │
│     → 构建 Prompt（问题 + 参考资料）          │
│     → 调用 Dify API 生成回答                 │
└─────────────────────────────────────────────┘
```

## 快速开始

### 1. 安装依赖

```bash
# 进入项目目录
cd rag_system

# 安装核心依赖
pip install -r requirements.txt

# 或手动安装
pip install chromadb sentence-transformers langchain-text-splitters
```

### 2. 运行完整测试

```bash
# 运行完整 RAG 系统测试
python rag_main.py
```

### 3. 交互式问答

```bash
# 进入交互式问答模式
python rag_main.py --interactive
```

### 4. 快速演示

```bash
# 运行快速演示
python rag_main.py --demo
```

## 模块说明

| 模块 | 文件 | 功能 |
|------|------|------|
| 分块模块 | `chunking.py` | 文档切分为小块 |
| 向量库 | `vector_store.py` | Chroma 向量数据库管理 |
| 问答系统 | `rag_qa.py` | 检索增强生成问答 |
| 重排序 | `with_reranker.py` | Cross-Encoder 精排优化 |
| 主入口 | `rag_main.py` | 统一入口，整合所有模块 |

## 使用示例

```python
from rag_system.chunking import create_chunks, get_demo_documents
from rag_system.vector_store import RAGVectorStore
from rag_system.rag_qa import RAGSystem

# 1. 准备文档
documents = get_demo_documents()
chunks = create_chunks(documents)

# 2. 构建向量库
vector_store = RAGVectorStore("./my_db", "knowledge")
vector_store.add_documents(chunks)

# 3. 初始化 RAG
rag = RAGSystem(vector_store, use_dify=True)

# 4. 问答
result = rag.rag_answer("中通客服电话是多少？")
print(result["answer"])
```

## 扩展知识库

替换 `chunking.py` 中的 `get_demo_documents()` 函数，添加自己的文档：

```python
def get_demo_documents():
    return [
        "您的自定义文档1...",
        "您的自定义文档2...",
    ]
```

## 配置说明

### Dify API（已集成）

- API 地址: `http://localhost/v1`
- API 密钥: 在 `config.py` 中配置

### 本地模型（可选）

如需使用本地 LLM（而非 Dify），可安装 Ollama：

```bash
# 安装 Ollama
# Windows: 下载 https://ollama.com/download

# 拉取中文模型
ollama pull qwen2.5:7b

# 启动服务
ollama serve
```

## 注意事项

1. 首次运行会自动下载 Embedding 模型（约 100MB）
2. 向量数据库保存在 `./my_rag_db` 目录
3. 如需清空数据库，删除该目录即可
4. 重排序模型较大（约 2GB），首次加载较慢

## 系统要求

- Python 3.8+
- 至少 4GB 内存
- 建议有网络连接（首次加载模型）
