"""
非交互式 RAG 系统测试 - 直接运行查看结果
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import DifyClient


def chunk_documents(documents, chunk_size=200):
    """将文档切分为小块"""
    chunks = []
    for doc in documents:
        sentences = doc.replace('\n', ' ').split('。')
        current_chunk = ""
        
        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue
                
            if len(current_chunk) + len(sentence) <= chunk_size:
                current_chunk += sentence + "。"
            else:
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence + "。"
                
        if current_chunk:
            chunks.append(current_chunk)
    
    return chunks


class SimpleVectorStore:
    """简化版向量存储"""
    
    def __init__(self):
        self.documents = []
        self.ids = []
        self.metadatas = []
    
    def add(self, documents, ids=None, metadatas=None):
        if ids is None:
            ids = [f"doc_{len(self.documents)+i}" for i in range(len(documents))]
        if metadatas is None:
            metadatas = [{"source": "unknown"} for _ in documents]
        
        self.documents.extend(documents)
        self.ids.extend(ids)
        self.metadatas.extend(metadatas)
    
    def search(self, query, top_k=3):
        """关键词匹配搜索"""
        query_words = set(query)
        keyword_map = {
            "电话": ["电话", "客服", "热线"],
            "客服": ["客服", "电话", "服务"],
            "投诉": ["投诉", "申诉", "举报"],
            "赔偿": ["赔偿", "理赔", "赔付"],
            "丢": ["丢", "丢失", "遗失"],
            "保价": ["保价", "保险"],
            "多少钱": ["多少钱", "费用", "收费"],
            "多久": ["多久", "时间", "时效"],
        }
        
        expanded_words = set(query_words)
        for word in query_words:
            if word in keyword_map:
                expanded_words.update(keyword_map[word])
        
        scores = []
        for i, doc in enumerate(self.documents):
            doc_lower = doc
            score = 0
            for word in query_words:
                if word in doc_lower:
                    score += 10
            for word in expanded_words:
                if word in doc_lower:
                    score += 2
            
            if score > 0:
                scores.append((score, i, doc))
        
        scores.sort(key=lambda x: x[0], reverse=True)
        results = scores[:top_k]
        
        return [{
            "document": r[2],
            "score": r[0],
            "id": self.ids[r[1]]
        } for r in results]


KNOWLEDGE_BASE = [
    """中通快递联系方式：全国统一客服电话95311（7x24小时服务），官网https://www.ztoglobal.com，投诉邮箱service@ztoglobal.com""",
    """中通快递赔偿政策：已保价包裹丢失按保价金额全额赔偿，保价费用为保价金额的1%，最高保价10万元。未保价包裹丢失最高赔偿3倍运费""",
    """中通快递投诉流程：投诉渠道包括客服电话95311、官网客服、国家邮政局申诉网站。所需材料包括运单号、商品价值证明、问题照片""",
    """中通快递处理时效：投诉受理3个工作日，调查处理7-15个工作日，赔偿到账3-7个工作日。同城快递24小时送达，省内48小时，省际72小时""",
    """中通快递保价规则：保价费率为保价金额的1%，最低1元，最高10万元。保价1000元需付10元保费，寄件时自愿选择""",
]


def main():
    print("\n" + "=" * 70)
    print("  中通快递 RAG 系统测试")
    print("  流程: 分块 → 存储 → 检索 → 生成")
    print("=" * 70)
    
    # Step 1: 初始化
    print("\n📦 Step 1: 初始化系统")
    vector_store = SimpleVectorStore()
    dify_client = DifyClient()
    print("   ✅ Dify 客户端初始化完成")
    
    # Step 2: 文档分块
    print("\n📄 Step 2: 文档分块")
    chunks = chunk_documents(KNOWLEDGE_BASE)
    print(f"   原始文档: {len(KNOWLEDGE_BASE)} 篇")
    print(f"   分块数量: {len(chunks)} 块")
    
    # Step 3: 存储到向量库
    print("\n💾 Step 3: 存储到向量库")
    ids = [f"zto_{i}" for i in range(len(chunks))]
    vector_store.add(chunks, ids)
    print(f"   ✅ 已存储 {len(chunks)} 条知识")
    
    # Step 4: RAG 问答测试
    print("\n🔍 Step 4: RAG 问答测试")
    
    test_questions = [
        "中通客服电话是多少？",
        "包裹丢了怎么赔偿？",
        "如何投诉中通？",
        "保价1000块要多少钱？",
        "理赔多久到账？"
    ]
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n{'─' * 60}")
        print(f"  ❓ 问题 {i}: {question}")
        
        # 检索
        search_results = vector_store.search(question, top_k=3)
        
        if search_results:
            context = "\n".join([
                f"参考资料{i}: {r['document']}" 
                for i, r in enumerate(search_results, 1)
            ])
            
            enhanced_prompt = f"""你是中通快递公司的客服助手。请根据以下参考资料回答用户问题。
如果资料中没有相关信息，请告知用户"我暂时没有找到相关信息"。

{context}

用户问题：{question}

请用中文回答。"""
            
            # 调用 Dify API
            result = dify_client.send_message(enhanced_prompt)
            
            if result.get("error"):
                answer = f"❌ 错误: {result['error']}"
            else:
                answer = result.get("answer", "未能获取回复")
        else:
            answer = "抱歉，我暂时没有找到相关信息。"
        
        print(f"\n  🤖 AI 回答:")
        print(f"     {answer}")
        
        if search_results:
            print(f"\n  📚 检索到 {len(search_results)} 条相关知识:")
            for j, source in enumerate(search_results[:2], 1):
                print(f"     [{j}] 相关度:{source['score']} {source['document'][:60]}...")
    
    print("\n" + "=" * 70)
    print("  ✅ RAG 系统测试完成")
    print("=" * 70)
    print("""
  RAG 流程演示:
  ┌─────────────┐
  │  1. 文档分块  │  ← 将长文档切分为小块
  └──────┬──────┘
         ▼
  ┌─────────────┐
  │  2. 向量存储  │  ← 存储到数据库
  └──────┬──────┘
         ▼
  ┌─────────────┐
  │  3. 语义检索  │  ← 找到相关文档
  └──────┬──────┘
         ▼
  ┌─────────────┐
  │  4. LLM 生成  │  ← Dify API 生成回答
  └─────────────┘
    """)


if __name__ == "__main__":
    main()
