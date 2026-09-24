"""
简化版 RAG 系统 - 使用纯 Python + Dify API 演示核心逻辑
无需安装额外依赖，可直接运行

完整版本请参考 rag_system/ 目录
"""

import sys
import os
import time
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from main import DifyClient
from config import COMPLAINT_INFO


# ═══════════════════════════════════════════════
# Step 1: 模拟文档分块（Chunking）
# ═══════════════════════════════════════════════
def chunk_documents(documents, chunk_size=200):
    """
    将文档切分为小块
    使用简单的字符切分（完整版使用 LangChain）
    """
    chunks = []
    for doc in documents:
        # 按句子切分
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


# ═══════════════════════════════════════════════
# Step 2: 模拟向量存储（Vector Store）
# ═══════════════════════════════════════════════
class SimpleVectorStore:
    """
    简化版向量存储
    使用关键词匹配 + 简单评分代替向量检索
    完整版使用 Chroma + Embedding 模型
    """
    
    def __init__(self):
        self.documents = []
        self.ids = []
        self.metadatas = []
    
    def add(self, documents, ids=None, metadatas=None):
        """添加文档"""
        if ids is None:
            ids = [f"doc_{len(self.documents)+i}" for i in range(len(documents))]
        if metadatas is None:
            metadatas = [{"source": "unknown"} for _ in documents]
        
        self.documents.extend(documents)
        self.ids.extend(ids)
        self.metadatas.extend(metadatas)
    
    def search(self, query, top_k=3):
        """
        简化版语义搜索
        使用关键词重叠度评分
        """
        # 提取查询关键词
        query_words = set(query.lower())
        # 扩展关键词（同义词）
        keyword_map = {
            "电话": ["电话", "客服", "热线", "联系"],
            "客服": ["客服", "电话", "服务", "热线"],
            "投诉": ["投诉", "申诉", "举报", "维权"],
            "赔偿": ["赔偿", "理赔", "赔付", "钱"],
            "丢": ["丢", "丢失", "遗失", "没了"],
            "保价": ["保价", "保险", "保障"],
            "快递": ["快递", "包裹", "物流", "运单"],
            "多少钱": ["多少钱", "费用", "收费", "价格"],
            "多久": ["多久", "时间", "时效", "天"],
        }
        
        # 扩展查询词
        expanded_words = set(query_words)
        for word in query_words:
            if word in keyword_map:
                expanded_words.update(keyword_map[word])
        
        # 评分
        scores = []
        for i, doc in enumerate(self.documents):
            doc_lower = doc.lower()
            score = 0
            
            # 精确匹配
            for word in query_words:
                if word in doc_lower:
                    score += 10
            
            # 扩展匹配
            for word in expanded_words:
                if word in doc_lower:
                    score += 2
            
            if score > 0:
                scores.append((score, i, doc))
        
        # 排序返回 top_k
        scores.sort(key=lambda x: x[0], reverse=True)
        results = scores[:top_k]
        
        return [{
            "document": r[2],
            "score": r[0],
            "id": self.ids[r[1]],
            "metadata": self.metadatas[r[1]]
        } for r in results]


# ═══════════════════════════════════════════════
# Step 3: RAG 问答系统
# ═══════════════════════════════════════════════
class SimplifiedRAG:
    """简化版 RAG 系统"""
    
    def __init__(self, use_dify=True):
        self.vector_store = SimpleVectorStore()
        self.use_dify = use_dify
        
        if use_dify:
            self.dify_client = DifyClient()
            print("✅ RAG 系统初始化完成 (Dify API)")
    
    def add_knowledge(self, documents):
        """添加知识库"""
        chunks = chunk_documents(documents)
        ids = [f"zto_{i}" for i in range(len(chunks))]
        metadatas = [{"source": "中通知识库", "chunk_id": i} for i in range(len(chunks))]
        self.vector_store.add(chunks, ids, metadatas)
        print(f"✅ 已添加 {len(chunks)} 条知识")
    
    def answer(self, question, top_k=3):
        """
        RAG 问答
        
        Args:
            question: 用户问题
            top_k: 检索文档数量
            
        Returns:
            答案和来源
        """
        # Step 1: 检索相关文档
        search_results = self.vector_store.search(question, top_k=top_k)
        
        if not search_results:
            return {
                "answer": "抱歉，我暂时没有找到相关信息。您可以拨打客服电话95311咨询。",
                "sources": []
            }
        
        # Step 2: 构建上下文
        context = "\n".join([
            f"参考资料{i+1}: {r['document']}" 
            for i, r in enumerate(search_results)
        ])
        
        # Step 3: 构建增强 Prompt
        enhanced_prompt = f"""你是中通快递公司的智能客服助手。请严格根据以下参考资料回答用户问题。
如果资料中没有相关信息，请明确告知用户"我暂时没有找到相关信息"，不要编造答案。

{context}

用户问题：{question}

请用中文给出准确、简洁的回答。"""
        
        # Step 4: 调用 Dify API
        result = self.dify_client.send_message(enhanced_prompt)
        
        if result.get("error"):
            answer = f"❌ 调用失败: {result['error']}"
        else:
            answer = result.get("answer", "未能获取回复")
        
        return {
            "answer": answer,
            "sources": search_results,
            "question": question
        }


# ═══════════════════════════════════════════════
# 演示知识库
# ═══════════════════════════════════════════════
KNOWLEDGE_BASE = [
    # 客服联系
    """
    中通快递联系方式：
    - 全国统一客服电话：95311（7x24小时服务）
    - 官方网站：https://www.ztoglobal.com
    - 投诉邮箱：service@ztoglobal.com
    - 微信公众号：中通快递官方
    - 总部地址：上海市青浦区华新镇纪鹤路3188号
    """,
    
    # 赔偿政策
    """
    中通快递赔偿政策：
    一、保价赔偿
    - 已保价包裹丢失/损坏：按保价金额全额赔偿
    - 保价费用：保价金额的1%
    - 最高保价：10万元
    
    二、未保价赔偿
    - 普通包裹丢失：最高赔偿3倍运费
    - 贵重物品损坏：按实际价值赔偿
    - 不可抗力因素：不予赔偿
    """,
    
    # 投诉流程
    """
    中通快递投诉流程：
    一、投诉渠道
    1. 客服电话：95311
    2. 官网在线客服
    3. 微信公众号投诉入口
    4. 国家邮政局申诉：https://ss.chinapost.gov.cn
    
    二、所需材料
    - 运单号（12位数字）
    - 商品价值证明（订单截图、发票）
    - 问题照片
    - 与客服沟通记录
    
    三、处理时效
    - 投诉受理：3个工作日
    - 调查处理：7-15个工作日
    - 赔偿到账：3-7个工作日
    """,
    
    # 时效标准
    """
    中通快递时效标准：
    - 同城快递：24小时内送达
    - 省内快递：48小时内送达
    - 省际快递：72小时内送达
    - 偏远地区：5-7个工作日
    
    延误处理：
    - 超期1天：客服道歉
    - 超期3天：减免运费
    - 超期7天：全额退款+补偿
    - 超期15天：视为丢件处理
    """,
    
    # 保价规则
    """
    中通快递保价规则：
    - 保价费率：保价金额的1%
    - 最低保价：1元
    - 最高保价：10万元
    - 保价范围：从1元到10万元
    - 示例：保价1000元，需付10元保费
    - 保价可选项：寄件时自愿选择
    """
]


# ═══════════════════════════════════════════════
# 主程序
# ═══════════════════════════════════════════════
def main():
    print("\n" + "=" * 70)
    print("  中通快递投诉机器人 - RAG 系统演示")
    print("  简化版: 关键词检索 + Dify 生成")
    print("=" * 70)
    
    # 初始化 RAG 系统
    print("\n📦 初始化 RAG 系统...")
    rag = SimplifiedRAG(use_dify=True)
    
    # 添加知识库
    print("\n📚 加载知识库...")
    rag.add_knowledge(KNOWLEDGE_BASE)
    
    # 测试问答
    print("\n" + "─" * 50)
    print("  开始 RAG 问答测试")
    print("─" * 50)
    
    test_questions = [
        "中通客服电话是多少？",
        "包裹丢了怎么赔偿？",
        "如何投诉中通快递？",
        "保价1000块要多少钱？",
        "理赔多久能到账？",
        "中通快递几天能送到？"
    ]
    
    for i, question in enumerate(test_questions, 1):
        print(f"\n{'─' * 60}")
        print(f"  ❓ 问题 {i}: {question}")
        
        start_time = time.time()
        result = rag.answer(question)
        elapsed = time.time() - start_time
        
        print(f"\n  🤖 AI 回答:")
        print(f"     {result['answer']}")
        
        if result['sources']:
            print(f"\n  📚 参考来源:")
            for j, source in enumerate(result['sources'][:2]):
                print(f"     [{j+1}] 相关度: {source['score']:.1f}")
                print(f"         {source['document'][:80]}...")
        
        print(f"\n  ⏱️  耗时: {elapsed:.2f}秒")
    
    # 交互式问答
    print("\n" + "=" * 70)
    print("  进入交互式问答模式")
    print("  输入问题开始对话，输入 'quit' 退出")
    print("=" * 70)
    
    while True:
        try:
            question = input("\n❓ 请输入您的问题: ").strip()
            
            if question.lower() == 'quit':
                print("\n👋 退出 RAG 系统")
                break
            
            if not question:
                continue
            
            print("\n⏳ 正在检索知识并生成回答...")
            result = rag.answer(question)
            
            print(f"\n🤖 回答: {result['answer']}")
            
            if result['sources']:
                print(f"\n📚 参考:")
                for source in result['sources'][:2]:
                    print(f"  [{source['score']:.1f}] {source['document'][:60]}...")
                    
        except KeyboardInterrupt:
            print("\n👋 退出 RAG 系统")
            break
        except Exception as e:
            print(f"\n❌ 错误: {str(e)}")


if __name__ == "__main__":
    main()
