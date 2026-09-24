"""
Step 5: 重排序优化模块 (Reranker)
使用 Cross-Encoder 进行精排，提升检索质量
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


class RerankerSystem:
    """重排序系统 - 精排优化"""
    
    def __init__(self, model_name: str = "BAAI/bge-reranker-v2-m3"):
        """
        初始化重排序模型
        
        Args:
            model_name: 重排序模型名称
        """
        self.model = None
        self.model_name = model_name
        
        try:
            from sentence_transformers import CrossEncoder
            self.model = CrossEncoder(model_name)
            print(f"✅ 重排序模型加载成功: {model_name}")
        except ImportError:
            print("⚠️  未安装 sentence-transformers")
            print("   安装命令: pip install sentence-transformers")
        except Exception as e:
            print(f"⚠️  重排序模型加载失败: {str(e)}")
            print("   提示: 首次加载需要下载模型，可能需要网络")
    
    def rerank(self, query: str, documents: list, top_k: int = 3) -> list:
        """
        对检索结果进行重排序
        
        Args:
            query: 用户查询
            documents: 候选文档列表
            top_k: 返回前K个结果
            
        Returns:
            重排序后的文档列表，每个元素包含 (score, document)
        """
        if self.model is None:
            # 回退方案：不进行重排序
            print("   ⚠️  重排序模型不可用，返回原始顺序")
            return [(1.0, doc) for doc in documents[:top_k]]
        
        # 构建查询-文档对
        pairs = [[query, doc] for doc in documents]
        
        # 预测相关性分数
        scores = self.model.predict(pairs)
        
        # 按分数排序
        ranked = sorted(zip(scores, documents), reverse=True)
        
        # 返回前 top_k 个
        return ranked[:top_k]
    
    def rag_with_rerank(self, query: str, vector_store, 
                        n_candidates: int = 20, 
                        top_k: int = 3) -> dict:
        """
        带重排序的完整 RAG 流程
        
        Args:
            query: 用户查询
            vector_store: 向量数据库
            n_candidates: 粗排候选数量
            top_k: 精排返回数量
            
        Returns:
            结果字典
        """
        # ── 粗排：向量检索召回 Top-N ──
        retrieval_results = vector_store.query(
            query_text=query,
            n_results=n_candidates,
            include=["documents", "distances", "metadatas"]
        )
        
        candidates = retrieval_results["documents"][0]
        distances = retrieval_results["distances"][0]
        metadatas = retrieval_results.get("metadatas", [[]])[0]
        
        print(f"   📊 粗排召回: {len(candidates)} 个候选文档")
        
        # ── 精排：Cross-Encoder 重排序 ──
        ranked = self.rerank(query, candidates, top_k=top_k)
        
        print(f"   🎯 精排选出: {len(ranked)} 个最优文档")
        
        # ── 构建结果 ──
        top_docs = [doc for _, doc in ranked]
        top_scores = [score for score, _ in ranked]
        
        context = "\n".join([f"- {doc}" for doc in top_docs])
        
        return {
            "query": query,
            "candidates_count": len(candidates),
            "top_k": top_k,
            "ranked_docs": top_docs,
            "ranked_scores": top_scores,
            "context": context
        }


# 增强版 RAG 系统（带重排序）
class EnhancedRAGSystem:
    """带重排序的增强版 RAG 系统"""
    
    def __init__(self, vector_store, use_dify: bool = True):
        """
        初始化增强版 RAG 系统
        
        Args:
            vector_store: 向量数据库
            use_dify: 是否使用 Dify API
        """
        self.vector_store = vector_store
        self.use_dify = use_dify
        self.reranker = RerankerSystem()
        
        if use_dify:
            sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from main import DifyClient
            self.dify_client = DifyClient()
    
    def answer(self, question: str, 
               n_candidates: int = 20, 
               top_k: int = 3) -> dict:
        """
        带重排序的 RAG 问答
        
        Args:
            question: 用户问题
            n_candidates: 粗排候选数量
            top_k: 精排返回数量
            
        Returns:
            完整的问答结果
        """
        # Step 1: 带重排序的检索
        rerank_result = self.reranker.rag_with_rerank(
            query=question,
            vector_store=self.vector_store,
            n_candidates=n_candidates,
            top_k=top_k
        )
        
        # Step 2: 构建增强的 Prompt
        prompt = f"""你是中通快递公司的客服助手。请严格根据以下参考资料回答用户问题。
如果资料中没有相关信息，请明确告知用户"我暂时没有找到相关信息"，不要编造答案。

参考资料（已按相关性排序）：
{rerank_result['context']}

用户问题：{question}

请给出准确、简洁的回答，使用中文："""
        
        # Step 3: 调用 LLM
        if self.use_dify:
            result = self.dify_client.send_message(prompt)
            if result.get("error"):
                answer = f"❌ Dify API 错误: {result['error']}"
            else:
                answer = result.get("answer", "未能获取回复")
        else:
            answer = "❌ 请设置 use_dify=True 或实现本地模型"
        
        return {
            "answer": answer,
            "query": question,
            "retrieval": {
                "candidates_count": rerank_result["candidates_count"],
                "top_k": rerank_result["top_k"],
                "ranked_scores": rerank_result["ranked_scores"]
            },
            "sources": rerank_result["ranked_docs"]
        }


if __name__ == "__main__":
    from vector_store import RAGVectorStore
    
    print("=" * 60)
    print("Step 5: 重排序优化演示")
    print("=" * 60)
    
    # 初始化向量数据库
    vector_store = RAGVectorStore(
        persist_path="./zto_rag_db",
        collection_name="zto_knowledge"
    )
    
    # 初始化重排序系统
    print("\n📦 加载重排序模型...")
    reranker_system = RerankerSystem()
    
    # 测试重排序
    test_query = "中通快递的赔偿政策是什么？"
    
    print(f"\n🔍 查询: {test_query}")
    print("\n⏳ 执行带重排序的检索...")
    
    result = reranker_system.rag_with_rerank(
        query=test_query,
        vector_store=vector_store,
        n_candidates=10,
        top_k=3
    )
    
    print(f"\n📊 检索结果:")
    print(f"   候选文档数: {result['candidates_count']}")
    print(f"   精排返回数: {result['top_k']}")
    
    print("\n🎯 精排后的文档:")
    for i, (doc, score) in enumerate(zip(
        result['ranked_docs'], 
        result['ranked_scores']
    )):
        print(f"\n   [{i+1}] 相关度: {score:.4f}")
        print(f"       {doc[:100]}...")
    
    print("\n💡 重排序优化说明:")
    print("   1. 粗排：向量检索快速召回20个候选")
    print("   2. 精排：Cross-Encoder 精确计算相关性")
    print("   3. 最终选择最相关的3个文档给 LLM")
