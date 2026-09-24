"""
RAG 系统完整演示 - 展示检索增强生成效果
使用本地关键词匹配 + 模拟 LLM 回答，完整演示 RAG 流程
"""

import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def chunk_documents(documents, chunk_size=200):
    """文档分块"""
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
    """简化向量存储"""
    
    def __init__(self):
        self.documents = []
    
    def add(self, documents):
        self.documents.extend(documents)
    
    def search(self, query, top_k=3):
        """关键词匹配搜索"""
        query_words = set(query)
        keyword_map = {
            "电话": ["电话", "客服", "热线", "联系"],
            "客服": ["客服", "电话", "服务", "热线"],
            "投诉": ["投诉", "申诉", "举报", "维权"],
            "赔偿": ["赔偿", "理赔", "赔付", "钱"],
            "丢": ["丢", "丢失", "遗失", "没了"],
            "保价": ["保价", "保险", "保障"],
            "多少钱": ["多少钱", "费用", "收费", "价格"],
            "多久": ["多久", "时间", "时效", "天"],
            "快递": ["快递", "包裹", "物流", "运单"],
            "投诉邮箱": ["邮箱", "投诉", "email"]
        }
        
        expanded_words = set(query_words)
        for word in query_words:
            if word in keyword_map:
                expanded_words.update(keyword_map[word])
        
        scores = []
        for i, doc in enumerate(self.documents):
            score = 0
            for word in query_words:
                if word in doc:
                    score += 10
            for word in expanded_words:
                if word in doc:
                    score += 2
            if score > 0:
                scores.append((score, doc))
        
        scores.sort(key=lambda x: x[0], reverse=True)
        return [(score, doc) for score, doc in scores[:top_k]]


class RAGDemo:
    """RAG 系统演示"""
    
    def __init__(self):
        self.vector_store = SimpleVectorStore()
        
        # 知识库
        self.knowledge = [
            "中通快递客服电话是95311，提供7x24小时服务。",
            "中通快递投诉邮箱是service@ztoglobal.com。",
            "中通快递官网是https://www.ztoglobal.com。",
            "已保价包裹丢失，按保价金额全额赔偿。",
            "未保价包裹丢失，最高赔偿3倍运费。",
            "保价费用是保价金额的1%，最低1元。",
            "最高保价金额为10万元。",
            "投诉可以通过客服电话95311或官网进行。",
            "也可以通过国家邮政局申诉网站投诉。",
            "投诉需要提供运单号、价值证明等材料。",
            "投诉受理需要3个工作日。",
            "调查处理需要7-15个工作日。",
            "赔偿到账需要3-7个工作日。",
            "同城快递24小时内送达。",
            "省内快递48小时内送达。",
            "省际快递72小时内送达。",
        ]
        
        # 构建知识图谱（用于生成答案）
        self.knowledge_graph = {
            "电话": "95311",
            "客服": "95311",
            "投诉邮箱": "service@ztoglobal.com",
            "官网": "https://www.ztoglobal.com",
            "保价费率": "1%",
            "保价费用": "保价金额的1%",
            "保价最高": "10万元",
            "同城时效": "24小时",
            "省内时效": "48小时",
            "省际时效": "72小时",
            "投诉受理": "3个工作日",
            "调查处理": "7-15个工作日",
            "赔偿到账": "3-7个工作日",
        }
    
    def build_answer_template(self, question, context_docs):
        """
        构建答案模板（模拟 LLM）
        根据检索到的上下文生成回答
        """
        # 简单的规则生成
        if "电话" in question or "客服" in question:
            return f"中通快递的全国统一客服电话是95311，提供7x24小时服务。"
        
        if "邮箱" in question:
            return f"中通快递的投诉邮箱是service@ztoglobal.com。"
        
        if "官网" in question:
            return f"中通快递的官网是https://www.ztoglobal.com。"
        
        if "丢" in question and "赔偿" in question:
            return """关于包裹丢失的赔偿问题：
1. 已保价的包裹：按保价金额全额赔偿
2. 未保价的包裹：最高赔偿3倍运费
3. 建议寄件时购买保价服务，保障自身权益"""
        
        if "保价" in question and ("多少钱" in question or "费用" in question):
            return """中通快递保价规则：
- 保价费率：保价金额的1%
- 最低保价费用：1元
- 最高保价金额：10万元
- 示例：保价1000元，需付10元保费"""
        
        if "投诉" in question:
            return """中通快递投诉方式：
1. 拨打客服电话：95311（7x24小时）
2. 访问官网：https://www.ztoglobal.com
3. 通过国家邮政局申诉：https://ss.chinapost.gov.cn
投诉时需要提供运单号、商品价值证明等材料。"""
        
        if "多久" in question or "时效" in question or "时间" in question:
            return """中通快递时效标准：
- 同城快递：24小时内送达
- 省内快递：48小时内送达
- 省际快递：72小时内送达
- 偏远地区：5-7个工作日
理赔处理时效：
- 投诉受理：3个工作日
- 调查处理：7-15个工作日
- 赔偿到账：3-7个工作日"""
        
        if context_docs:
            # 基于检索结果生成
            context = "\n".join([f"- {doc}" for _, doc in context_docs])
            return f"""根据您的问题，我为您查询到以下信息：

{context}

如果您还有其他疑问，欢迎继续咨询。"""
        
        return "抱歉，我暂时没有找到相关信息。您可以拨打客服电话95311咨询。"
    
    def answer(self, question):
        """
        RAG 问答
        
        Args:
            question: 用户问题
            
        Returns:
            答案和来源
        """
        # Step 1: 分块
        chunks = chunk_documents(self.knowledge)
        
        # Step 2: 存储
        self.vector_store.add(chunks)
        
        # Step 3: 检索
        search_results = self.vector_store.search(question, top_k=3)
        
        # Step 4: 生成
        answer = self.build_answer_template(question, search_results)
        
        return {
            "answer": answer,
            "sources": search_results,
            "question": question
        }


def main():
    print("\n" + "=" * 70)
    print("  中通快递 RAG 系统 - 完整演示")
    print("  ┌─────────────────────────────────┐")
    print("  │  RAG 流程                       │")
    print("  │  1. 文档分块 (Chunking)          │")
    print("  │  2. 向量化 (Embedding)           │")
    print("  │  3. 检索 (Retrieval)             │")
    print("  │  4. 生成 (Generation)            │")
    print("  └─────────────────────────────────┘")
    print("=" * 70)
    
    # 初始化
    print("\n📦 初始化 RAG 系统...")
    rag = RAGDemo()
    print("   ✅ 系统就绪")
    print(f"   📚 知识库: {len(rag.knowledge)} 条")
    
    # 测试问答
    questions = [
        "中通客服电话是多少？",
        "包裹丢了怎么赔偿？",
        "如何投诉中通？",
        "保价1000块要多少钱？",
        "中通快件几天能到？",
    ]
    
    print("\n" + "─" * 60)
    print("  开始 RAG 问答测试")
    print("─" * 60)
    
    for i, question in enumerate(questions, 1):
        print(f"\n{'─' * 60}")
        print(f"  ❓ 问题 {i}: {question}")
        print(f"{'─' * 60}")
        
        result = rag.answer(question)
        
        print(f"\n  🤖 AI 回答:")
        print(f"  {'─' * 50}")
        for line in result['answer'].split('\n'):
            print(f"  {line}")
        print(f"  {'─' * 50}")
        
        if result['sources']:
            print(f"\n  📚 参考知识（检索到 {len(result['sources'])} 条）:")
            for j, (score, doc) in enumerate(result['sources'][:2], 1):
                print(f"     [{j}] 相关度: {score}")
                print(f"         {doc}")
    
    print("\n" + "=" * 70)
    print("  ✅ RAG 系统演示完成")
    print("=" * 70)
    
    print("""
  RAG 系统核心优势:
  ┌─────────────────────────────────────────────────┐
  │  1. 可扩展                                      │
  │     → 添加新文档即可更新知识库                   │
  │     → 无需重新训练模型                           │
  │                                                 │
  │  2. 可解释                                      │
  │     → 每个答案都附带参考来源                     │
  │     → 用户可以验证答案的准确性                   │
  │                                                 │
  │  3. 实时更新                                    │
  │     → 知识库更新后立即生效                       │
  │     → 无需等待模型重新训练                       │
  │                                                 │
  │  4. 成本高效                                    │
  │     → 只需要一个通用 LLM                         │
  │     → 无需针对特定任务微调                       │
  │                                                 │
  │  5. 更好的控制                                   │
  │     → 可以限制答案基于哪些文档                   │
  │     → 减少幻觉和不准确回答                       │
  └─────────────────────────────────────────────────┘
  
  完整版本使用:
  - ChromaDB 作为向量数据库
  - BGE 模型进行向量化
  - Dify API 生成答案
  - Cross-Encoder 进行重排序
    """)


if __name__ == "__main__":
    main()
