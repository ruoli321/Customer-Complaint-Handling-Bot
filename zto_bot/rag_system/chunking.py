"""
Step 2: 文档分块模块 (Chunking)
将长文档切分为适合检索的小块
"""

from langchain_text_splitters import RecursiveCharacterTextSplitter

def create_chunks(documents: list, chunk_size: int = 200, chunk_overlap: int = 50) -> list:
    """
    将文档列表切分为小块
    
    Args:
        documents: 文档列表，每个元素为字符串
        chunk_size: 每个块的最大字符数
        chunk_overlap: 相邻块的重叠字符数
        
    Returns:
        chunks: 切分后的文本块列表
    """
    # 创建分块器
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
        separators=["\n\n", "\n", "。", ".", " ", ""]
    )
    
    # 对每篇文档进行分块
    all_chunks = []
    for doc in documents:
        chunks = splitter.split_text(doc)
        all_chunks.extend(chunks)
    
    return all_chunks


def get_demo_documents() -> list:
    """
    获取中通快递投诉相关的演示文档
    可以替换为真实的知识库文档
    """
    documents = [
        """
中通快递投诉处理流程：

一、投诉渠道
1. 客服电话：95311（全国统一客服热线）
2. 官网投诉：https://www.ztoglobal.com/customer-service
3. 微信公众号：中通快递
4. 国家邮政局申诉网站：https://ss.chinapost.gov.cn

二、投诉时效
- 包裹出现问题后，建议7天内提出投诉
- 理赔案件将在3个工作日内受理
- 复杂案件处理时效为7-15个工作日

三、所需材料
- 运单号（12位数字）
- 收件人/寄件人姓名
- 商品价值证明（订单截图、发票等）
- 问题描述和相关照片
        """,
        """
中通快递丢件赔偿政策：

一、保价赔偿
- 已保价包裹：按保价金额全额赔偿
- 保价费用：按保价金额的1%收取
- 保价上限：单票最高保价金额为10万元

二、未保价赔偿
- 未保价包裹：按实际价值赔偿
- 赔偿标准：普通包裹最高赔偿3倍运费
- 贵重物品：建议保价寄送

三、赔偿流程
1. 客服核实丢件情况
2. 用户提供价值证明
3. 启动赔偿审核流程
4. 3-7个工作日内完成赔偿
5. 赔偿金原路返回（原支付账户）

四、特殊情况
- 不可抗力因素（地震、洪水等）：不予赔偿
- 用户自行包装不当：部分责任
- 违禁物品：不予赔偿
        """,
        """
中通快递延误处理规定：

一、时效标准
- 同城快递：24小时内送达
- 省内快递：48小时内送达
- 省际快递：72小时内送达
- 偏远地区：5-7个工作日

二、延误处理
- 超过承诺时效1天：客服道歉
- 超过承诺时效3天：减免运费
- 超过承诺时效7天：全额退款+额外补偿
- 超过承诺时效15天：视为丢件处理

三、例外情况
- 恶劣天气影响
- 交通管制
- 节假日高峰
- 不可抗力因素

四、申诉渠道
- 官网在线客服
- 客服热线95311
- 国家邮政局12305
        """,
        """
中通快递投诉举证指南：

一、必备证据
1. 运单照片（清晰完整）
2. 商品订单截图
3. 支付凭证
4. 包裹问题照片（破损、丢失等）
5. 与客服的沟通记录

二、证据要求
- 照片清晰，能看清关键信息
- 截图完整，包含时间戳
- 视频建议30秒以内
- 文件大小不超过5MB

三、提交方式
- 客服系统内直接上传
- 发送邮件至官方邮箱
- 通过微信公众号提交

四、注意事项
- 保留原始证据
- 提交时间不超过投诉后7天
- 确保证据链完整
        """
    ]
    
    return documents


if __name__ == "__main__":
    print("=" * 60)
    print("Step 2: 文档分块演示")
    print("=" * 60)
    
    # 获取演示文档
    documents = get_demo_documents()
    print(f"\n📄 原始文档数量: {len(documents)} 篇")
    
    # 执行分块
    chunks = create_chunks(documents, chunk_size=200, chunk_overlap=50)
    print(f"✂️  分块后数量: {len(chunks)} 块")
    
    # 显示每个块的内容
    for i, chunk in enumerate(chunks):
        print(f"\n--- 块 {i+1} ---")
        print(f"({len(chunk)} 字符)")
        print(chunk[:100] + "..." if len(chunk) > 100 else chunk)
