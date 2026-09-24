"""
中通快递投诉机器人 - RAG 系统入口
整合所有模块，提供完整的 RAG 问答服务

使用方法:
    python rag_main.py              # 运行完整测试
    python rag_main.py --interactive # 进入交互式问答
    python rag_main.py --demo        # 运行演示
"""

import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_system.chunking import get_demo_documents, create_chunks
from rag_system.vector_store import RAGVectorStore
from rag_system.rag_qa import RAGSystem
from rag_system.with_reranker import EnhancedRAGSystem


def print_banner(text: str, char: str = "="):
    """打印横幅"""
    print(f"\n{char * 70}")
    print(f"  {text}")
    print(f"{char * 70}")


def print_step(step_num: int, title: str):
    """打印步骤"""
    print(f"\n{'─' * 50}")
    print(f"  Step {step_num}: {title}")
    print(f"{'─' * 50}")


def run_full_test():
    """运行完整 RAG 系统测试"""
    
    print_banner("中通快递投诉机器人 - RAG 系统演示")
    print("  完整演示: 分块 → 建库 → 检索 → 生成 → 重排序")
    print_banner("=")
    
    # ═══════════════════════════════════════
    # Step 1: 准备数据
    # ═══════════════════════════════════════
    print_step(1, "准备文档数据")
    
    documents = get_demo_documents()
    print(f"  📄 原始文档: {len(documents)} 篇")
    for i, doc in enumerate(documents):
        lines = doc.strip().split('\n')
        print(f"     文档{i+1}: {len(lines)} 段, {len(doc)} 字符")
    
    # ═══════════════════════════════════════
    # Step 2: 文档分块
    # ═══════════════════════════════════════
    print_step(2, "文档分块 (Chunking)")
    
    chunks = create_chunks(documents, chunk_size=200, chunk_overlap=50)
    print(f"  ✂️  分块结果: {len(chunks)} 个文本块")
    
    # 显示部分分块示例
    print("\n  分块示例:")
    for i in range(min(3, len(chunks))):
        chunk = chunks[i]
        print(f"\n    块 {i+1} ({len(chunk)} 字符):")
        print(f"    {chunk[:80]}...")
    
    # ═══════════════════════════════════════
    # Step 3: 构建向量数据库
    # ═══════════════════════════════════════
    print_step(3, "构建向量数据库 (Vector Store)")
    
    persist_path = "./zto_rag_db"
    collection_name = "zto_knowledge"
    
    # 清空旧数据
    if os.path.exists(persist_path):
        import shutil
        shutil.rmtree(persist_path, ignore_errors=True)
        print(f"  🧹 已清理旧数据库: {persist_path}")
    
    # 创建新的向量数据库
    vector_store = RAGVectorStore(
        persist_path=persist_path,
        collection_name=collection_name
    )
    
    # 添加分块后的文档
    ids = [f"zto_chunk_{i}" for i in range(len(chunks))]
    metadatas = [{"source": "中通知识库", "category": "投诉处理", "chunk_id": i} 
                for i in range(len(chunks))]
    
    vector_store.add_documents(chunks, ids, metadatas)
    print(f"  ✅ 数据库文档数: {vector_store.get_count()}")
    
    # ═══════════════════════════════════════
    # Step 4: 基础 RAG 问答
    # ═══════════════════════════════════════
    print_step(4, "基础 RAG 问答 (检索+生成)")
    
    rag_system = RAGSystem(vector_store, use_dify=True)
    
    test_questions = [
        "中通快递的客服电话是多少？",
        "包裹丢失后怎么赔偿？",
        "如何投诉中通快递？",
        "保价需要多少钱？",
        "理赔多久能到账？",
        "中通快递的投诉邮箱是多少？"
    ]
    
    print("\n  测试问答:")
    print(f"  {'─' * 60}")
    
    for q in test_questions:
        print(f"\n  ❓ 问题: {q}")
        
        start_time = time.time()
        result = rag_system.rag_answer(q, n_results=3)
        elapsed = time.time() - start_time
        
        print(f"  🤖 回答: {result['answer'][:100]}...")
        print(f"  📚 检索: {result['num_docs_retrieved']} 个文档")
        print(f"  ⏱️  耗时: {elapsed:.2f}秒")
    
    # ═══════════════════════════════════════
    # Step 5: 带重排序的增强 RAG
    # ═══════════════════════════════════════
    print_step(5, "增强 RAG (带重排序)")
    
    enhanced_rag = EnhancedRAGSystem(vector_store, use_dify=True)
    
    print("\n  使用重排序优化...")
    print(f"  {'─' * 60}")
    
    # 测试复杂问题
    complex_questions = [
        "我买的中通快递包裹丢了，应该怎么处理？",
        "中通的保价规则是什么？我保价1000块要多少钱？",
        "我要投诉中通快递，应该找哪个部门？",
    ]
    
    for q in complex_questions:
        print(f"\n  ❓ 问题: {q}")
        
        start_time = time.time()
        result = enhanced_rag.answer(q, n_candidates=20, top_k=3)
        elapsed = time.time() - start_time
        
        print(f"  🤖 回答: {result['answer'][:100]}...")
        print(f"  📊 检索: 候选{result['retrieval']['candidates_count']} → 精排{result['retrieval']['top_k']}")
        print(f"  ⏱️  耗时: {elapsed:.2f}秒")
    
    # ═══════════════════════════════════════
    # 总结
    # ═══════════════════════════════════════
    print_banner("测试完成 - RAG 系统架构")
    print("""
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
    """)
    
    print("  系统优势:")
    print("  ✅ 可扩展: 支持任意文档，自动向量化")
    print("  ✅ 可检索: 基于语义相似度，不是关键词匹配")
    print("  ✅ 可解释: 返回答案时附带参考来源")
    print("  ✅ 可优化: 重排序提升检索精度")
    print("  ✅ 本地运行: 使用本地 Embedding 模型，无需 Key")
    print_banner("=")


def run_interactive():
    """运行交互式问答"""
    
    print_banner("中通快递 RAG 系统 - 交互式问答")
    print("  输入问题开始对话，输入 'quit' 退出")
    print_banner("=")
    
    # 初始化系统
    print("\n📦 初始化系统...")
    
    # 加载或创建向量数据库
    vector_store = RAGVectorStore(
        persist_path="./zto_rag_db",
        collection_name="zto_knowledge"
    )
    
    # 如果数据库为空，自动初始化
    if vector_store.get_count() == 0:
        print("  📥 数据库为空，自动加载知识...")
        documents = get_demo_documents()
        chunks = create_chunks(documents)
        ids = [f"zto_chunk_{i}" for i in range(len(chunks))]
        metadatas = [{"source": "中通知识库", "category": "投诉处理"} for _ in chunks]
        vector_store.add_documents(chunks, ids, metadatas)
    
    # 初始化 RAG 系统
    rag_system = RAGSystem(vector_store, use_dify=True)
    
    print(f"  ✅ 系统就绪，共 {vector_store.get_count()} 条知识")
    
    # 交互式问答
    rag_system.interactive_mode()


def run_demo():
    """运行快速演示"""
    
    print_banner("RAG 系统快速演示")
    print_banner("-")
    
    # 初始化
    vector_store = RAGVectorStore(
        persist_path="./zto_rag_db",
        collection_name="zto_knowledge"
    )
    
    if vector_store.get_count() == 0:
        print("  📥 加载知识...")
        documents = get_demo_documents()
        chunks = create_chunks(documents)
        ids = [f"demo_{i}" for i in range(len(chunks))]
        vector_store.add_documents(chunks, ids)
    
    rag = RAGSystem(vector_store, use_dify=True)
    
    question = input("\n请输入您的问题: ").strip()
    if question:
        result = rag.rag_answer(question)
        print(f"\n🤖 回答: {result['answer']}")
        if result['sources']:
            print(f"\n📚 参考:")
            for source in result['sources']:
                print(f"  [{source['rank']}] {source['content'][:80]}...")


def main():
    """主函数"""
    
    # 解析命令行参数
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        
        if arg == "--interactive":
            run_interactive()
            return
        elif arg == "--demo":
            run_demo()
            return
        elif arg == "--help":
            print(__doc__)
            return
    
    # 默认运行完整测试
    run_full_test()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 程序已停止")
    except Exception as e:
        print(f"\n❌ 错误: {str(e)}")
        import traceback
        traceback.print_exc()
