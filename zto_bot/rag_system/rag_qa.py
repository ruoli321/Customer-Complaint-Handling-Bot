"""
Step 4: RAG 问答模块 (RAG QA)
完整的检索增强生成问答系统
支持 Dify API 和本地模型两种方式
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import requests
import json

# 导入 Dify 客户端（复用已有代码）
from main import DifyClient
from config import COMPLAINT_INFO, DIFY_API_BASE, DIFY_API_KEY


class RAGSystem:
    """完整的 RAG 系统封装"""
    
    def __init__(self, vector_store, use_dify: bool = True):
        """
        初始化 RAG 系统
        
        Args:
            vector_store: 向量数据库实例
            use_dify: 是否使用 Dify API（True）或本地模型（False）
        """
        self.vector_store = vector_store
        self.use_dify = use_dify
        
        if use_dify:
            # 使用 Dify API（复用现有配置）
            self.dify_client = DifyClient()
            print(f"✅ RAG 系统初始化完成 (使用 Dify API)")
        else:
            # 使用本地模型
            self.local_llm = self._init_local_llm()
            print(f"✅ RAG 系统初始化完成 (使用本地模型)")
    
    def _init_local_llm(self):
        """初始化本地大模型（可选方案）"""
        try:
            # 尝试使用 Ollama（本地模型服务）
            import requests
            
            class LocalLLM:
                def __init__(self, base_url="http://localhost:11434"):
                    self.base_url = base_url
                    self.model = "qwen2.5:7b"  # 适合中文的模型
                    
                def generate(self, prompt: str) -> str:
                    """调用本地 Ollama 服务"""
                    try:
                        response = requests.post(
                            f"{self.base_url}/api/generate",
                            json={
                                "model": self.model,
                                "prompt": prompt,
                                "stream": False
                            },
                            timeout=30
                        )
                        if response.status_code == 200:
                            return response.json().get("response", "")
                        else:
                            return f"本地模型服务错误: {response.status_code}"
                    except requests.ConnectionError:
                        return "⚠️ 本地模型服务未启动，请先启动 Ollama: ollama serve"
                    except Exception as e:
                        return f"⚠️ 调用本地模型失败: {str(e)}"
            
            # 测试连接
            llm = LocalLLM()
            try:
                requests.get("http://localhost:11434/api/tags", timeout=2)
                print("   ℹ️  本地 Ollama 服务可用")
            except:
                print("   ⚠️  本地 Ollama 服务未启动")
            
            return llm
            
        except ImportError:
            print("   ⚠️  未安装 requests 库")
            return None
    
    def rag_answer(self, user_question: str, 
                  n_results: int = 3, 
                  include_sources: bool = True) -> dict:
        """
        完整的 RAG 问答函数
        
        Args:
            user_question: 用户问题
            n_results: 召回最相似的N个文档
            include_sources: 是否包含来源信息
            
        Returns:
            包含答案和来源的字典
        """
        # ── 第一步：检索相关文档 ──
        retrieval_results = self.vector_store.query(
            query_text=user_question,
            n_results=n_results,
            include=["documents", "distances", "metadatas"]
        )
        
        retrieved_docs = retrieval_results["documents"][0]
        distances = retrieval_results["distances"][0]
        metadatas = retrieval_results.get("metadatas", [[]])[0]
        
        # ── 第二步：构建上下文和 Prompt ──
        context = "\n".join([f"- {doc}" for doc in retrieved_docs])
        
        # 构建增强的用户问题
        enhanced_question = f"""你是中通快递公司的客服助手。请严格根据以下参考资料回答用户问题。
如果资料中没有相关信息，请明确告知用户"我暂时没有找到相关信息"，不要编造答案。

参考资料：
{context}

用户问题：{user_question}

请给出准确、简洁的回答，使用中文："""
        
        # ── 第三步：调用 LLM 生成答案 ──
        if self.use_dify:
            # 使用 Dify API
            result = self.dify_client.send_message(enhanced_question)
            
            if result.get("error"):
                answer = f"❌ Dify API 错误: {result['error']}"
                sources = []
            else:
                answer = result.get("answer", "未能获取回复")
                sources = []
        else:
            # 使用本地模型
            if self.local_llm:
                answer = self.local_llm.generate(enhanced_question)
            else:
                answer = "❌ 本地模型不可用"
            sources = []
        
        # ── 第四步：构建来源信息 ──
        if include_sources:
            for i, (doc, dist, meta) in enumerate(zip(
                retrieved_docs, distances, metadatas
            )):
                source_info = {
                    "rank": i + 1,
                    "content": doc,
                    "similarity": round(1 - dist, 4),
                    "source": meta.get("source", "未知") if meta else "未知",
                    "category": meta.get("category", "未知") if meta else "未知"
                }
                sources.append(source_info)
        
        return {
            "answer": answer,
            "sources": sources,
            "query": user_question,
            "num_docs_retrieved": len(retrieved_docs)
        }
    
    def batch_qa(self, questions: list) -> list:
        """
        批量问答
        
        Args:
            questions: 问题列表
            
        Returns:
            结果列表
        """
        results = []
        for q in questions:
            print(f"  处理问题: {q[:30]}...")
            result = self.rag_answer(q)
            results.append(result)
        return results
    
    def interactive_mode(self):
        """
        交互式问答模式
        """
        print("\n" + "=" * 60)
        print("RAG 交互式问答模式")
        print("输入问题开始对话，输入 'quit' 退出")
        print("=" * 60)
        
        while True:
            try:
                question = input("\n❓ 请输入您的问题: ").strip()
                
                if question.lower() == 'quit':
                    print("👋 退出 RAG 系统")
                    break
                    
                if not question:
                    continue
                    
                print("\n⏳ 正在检索相关文档并生成回答...")
                result = self.rag_answer(question)
                
                print(f"\n🤖 AI 回答: {result['answer']}")
                
                if result['sources']:
                    print("\n📚 参考来源:")
                    for source in result['sources']:
                        print(f"  [{source['rank']}] {source['source']} "
                              f"(相似度: {source['similarity']:.2f})")
                        print(f"      {source['content'][:80]}...")
                        
            except KeyboardInterrupt:
                print("\n👋 退出 RAG 系统")
                break
            except Exception as e:
                print(f"\n❌ 错误: {str(e)}")


if __name__ == "__main__":
    from chunking import get_demo_documents, create_chunks
    from vector_store import RAGVectorStore
    
    print("=" * 60)
    print("Step 4: RAG 问答系统演示")
    print("=" * 60)
    
    # Step 1: 准备数据
    print("\n📄 Step 1: 准备文档...")
    documents = get_demo_documents()
    chunks = create_chunks(documents)
    print(f"   文档数量: {len(documents)}")
    print(f"   分块数量: {len(chunks)}")
    
    # Step 2: 构建向量库
    print("\n📦 Step 2: 构建向量数据库...")
    vector_store = RAGVectorStore(
        persist_path="./zto_rag_db",
        collection_name="zto_knowledge"
    )
    
    ids = [f"zto_{i}" for i in range(len(chunks))]
    metadatas = [{"source": "中通知识库", "category": "投诉处理"} 
                for _ in chunks]
    vector_store.add_documents(chunks, ids, metadatas)
    
    # Step 3: 初始化 RAG 系统
    print("\n🔧 Step 3: 初始化 RAG 系统...")
    rag = RAGSystem(vector_store, use_dify=True)
    
    # Step 4: 测试问答
    print("\n🔍 Step 4: 测试问答")
    test_questions = [
        "中通客服电话是多少？",
        "包裹丢了怎么赔偿？",
        "如何投诉中通快递？",
        "保价费用是多少？",
        "理赔需要多长时间？"
    ]
    
    for q in test_questions:
        print(f"\n{'─' * 50}")
        print(f"❓ 问题: {q}")
        result = rag.rag_answer(q)
        print(f"🤖 回答: {result['answer']}")
        if result['sources']:
            print(f"📚 参考: {result['sources'][0]['source']}")
