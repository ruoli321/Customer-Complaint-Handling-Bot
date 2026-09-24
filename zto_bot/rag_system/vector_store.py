"""
Step 3: 向量数据库模块 (Vector Store)
使用 Chroma 存储文档向量，支持本地 Embedding 模型
"""

import os
import chromadb
from chromadb.utils import embedding_functions


class RAGVectorStore:
    """RAG 系统向量数据库管理器"""
    
    def __init__(self, persist_path: str = "./my_rag_db", 
                 collection_name: str = "knowledge_base"):
        """
        初始化向量数据库
        
        Args:
            persist_path: 数据库持久化路径
            collection_name: 集合名称
        """
        self.persist_path = persist_path
        self.collection_name = collection_name
        
        # 方案B：使用本地 Embedding 模型（无需 API Key，中文推荐）
        # 首次运行会自动下载模型
        self.embedding_function = self._get_local_embedding()
        
        # 创建持久化客户端
        self.client = chromadb.PersistentClient(path=persist_path)
        
        # 创建或获取集合
        self.collection = self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"}  # 余弦相似度
        )
        
        print(f"✅ 向量数据库初始化成功: {persist_path}")
        
    def _get_local_embedding(self):
        """
        获取本地 Embedding 模型（方案B，无需 API Key）
        使用 sentence-transformers 的中文模型
        """
        try:
            from sentence_transformers import SentenceTransformer
            
            # 使用中文优化模型
            model = SentenceTransformer("BAAI/bge-small-zh-v1.5")
            
            # 包装为 Chroma 需要的格式
            class LocalEmbeddingFunction:
                def __init__(self, model):
                    self.model = model
                    
                def __call__(self, input):
                    if isinstance(input, str):
                        input = [input]
                    embeddings = self.model.encode(input, show_progress_bar=False)
                    return embeddings.tolist()
                    
            return LocalEmbeddingFunction(model)
            
        except ImportError:
            print("⚠️  未安装 sentence-transformers，使用默认 Embedding")
            print("   安装命令: pip install sentence-transformers")
            # 使用 Chroma 默认的 ONNX 模型
            return embedding_functions.DefaultEmbeddingFunction()
    
    def add_documents(self, documents: list, ids: list = None, 
                      metadatas: list = None):
        """
        批量添加文档到向量数据库
        
        Args:
            documents: 文档内容列表
            ids: 文档ID列表（可选，自动生成）
            metadatas: 元数据列表（可选）
        """
        if ids is None:
            ids = [f"doc_{i}" for i in range(len(documents))]
            
        if metadatas is None:
            metadatas = [{"source": "default", "category": "general"} 
                       for _ in documents]
        
        # 去重检查
        existing_ids = self.collection.get()["ids"]
        new_ids = [id for id in ids if id not in existing_ids]
        new_documents = [doc for doc, id in zip(documents, ids) if id in new_ids]
        new_metadatas = [meta for meta, id in zip(metadatas, ids) if id in new_ids]
        
        if new_ids:
            self.collection.add(
                documents=new_documents,
                ids=new_ids,
                metadatas=new_metadatas
            )
            print(f"✅ 已入库 {len(new_ids)} 条新文档")
        else:
            print("ℹ️  所有文档已存在，跳过添加")
    
    def query(self, query_text: str, n_results: int = 3) -> dict:
        """
        查询向量数据库
        
        Args:
            query_text: 查询文本
            n_results: 返回最相似的N个结果
            
        Returns:
            查询结果字典
        """
        results = self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            include=["documents", "distances", "metadatas"]
        )
        return results
    
    def get_all_documents(self) -> dict:
        """获取所有文档"""
        return self.collection.get(include=["documents", "metadatas"])
    
    def get_count(self) -> int:
        """获取文档数量"""
        return self.collection.count()
    
    def delete_document(self, doc_id: str):
        """删除指定文档"""
        self.collection.delete(ids=[doc_id])
        print(f"✅ 已删除文档: {doc_id}")
    
    def clear_collection(self):
        """清空集合"""
        self.client.delete_collection(name=self.collection_name)
        print(f"✅ 已清空集合: {self.collection_name}")
        # 重新创建
        self.collection = self.client.get_or_create_collection(
            name=self.collection_name,
            embedding_function=self.embedding_function,
            metadata={"hnsw:space": "cosine"}
        )


if __name__ == "__main__":
    print("=" * 60)
    print("Step 3: 向量数据库演示")
    print("=" * 60)
    
    # 初始化向量数据库
    vector_store = RAGVectorStore(
        persist_path="./my_rag_db",
        collection_name="zto_knowledge"
    )
    
    # 准备示例文档
    documents = [
        "中通快递客服电话是95311，提供7x24小时服务。",
        "包裹丢失后，用户可以在7天内提出投诉。",
        "已保价的包裹丢失，按保价金额全额赔偿。",
        "未保价包裹的赔偿标准是最高3倍运费。",
        "中通快递的投诉邮箱是service@ztoglobal.com",
        "用户可以通过国家邮政局申诉网站进行投诉。",
        "保价费用按保价金额的1%收取，最高保价10万元。",
        "理赔将在审核通过后3-7个工作日内完成。"
    ]
    
    ids = [f"zto_{i}" for i in range(len(documents))]
    metadatas = [
        {"source": "中通客服手册", "category": "客服信息"},
        {"source": "中通投诉政策", "category": "投诉流程"},
        {"source": "中通赔偿政策", "category": "赔偿标准"},
        {"source": "中通赔偿政策", "category": "赔偿标准"},
        {"source": "中通联系方式", "category": "联系渠道"},
        {"source": "中通投诉指南", "category": "投诉渠道"},
        {"source": "中通保价说明", "category": "保价规则"},
        {"source": "中通理赔流程", "category": "理赔时效"}
    ]
    
    # 添加文档
    vector_store.add_documents(documents, ids, metadatas)
    
    print(f"\n📊 数据库统计:")
    print(f"   总文档数: {vector_store.get_count()}")
    
    # 测试查询
    print("\n🔍 测试查询:")
    queries = [
        "中通客服电话是多少？",
        "包裹丢了怎么赔偿？",
        "如何投诉中通快递？"
    ]
    
    for query in queries:
        print(f"\n❓ 查询: {query}")
        results = vector_store.query(query, n_results=2)
        
        for i, (doc, dist) in enumerate(zip(
            results["documents"][0], 
            results["distances"][0]
        )):
            print(f"   结果{i+1} (相似度: {1-dist:.2f}): {doc}")
