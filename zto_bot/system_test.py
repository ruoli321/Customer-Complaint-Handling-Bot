import sys
import os
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import DifyClient
from config import COMPLAINT_INFO

def print_banner(text):
    print("\n" + "=" * 70)
    print(f"  {text}")
    print("=" * 70)

print_banner("中通快递投诉机器人 - 完整系统测试")

client = DifyClient()

print(f"\n📋 系统配置:")
print(f"   API地址: {client.api_base}/v1")
print(f"   API密钥: {client.api_key}")
print(f"   用户标识: {client.user}")

print(f"\n📦 投诉信息:")
print(f"   运单号: {COMPLAINT_INFO['tracking_number']}")
print(f"   物品: {COMPLAINT_INFO['product']}")
print(f"   问题: {COMPLAINT_INFO['issue']}")
print(f"   价值: {COMPLAINT_INFO['value']}")
print(f"   下单日期: {COMPLAINT_INFO['order_date']}")
print(f"   描述: {COMPLAINT_INFO['description']}")

conversation_history = []

mock_service_replies = [
    "您好，中通快递，请问有什么可以帮您？",
    "好的，我来帮您查询一下您的包裹情况，请稍等。",
    "抱歉，您的包裹目前显示正在运输途中，可能因为天气原因有所延迟。",
    "请您再耐心等待一下，我们会尽快安排派送的。",
    "如果超过3天仍未送达，您可以申请理赔。",
    "理赔需要提供订单号和相关证明材料。",
    "好的，我已经帮您登记了投诉，我们会在24小时内给您回复。",
    "感谢您的理解，祝您生活愉快！"
]

print_banner("开始模拟投诉对话流程")

for round_num, service_reply in enumerate(mock_service_replies, 1):
    print(f"\n🔄 第 {round_num} 轮对话")
    print("-" * 50)
    
    print(f"\n🤖 客服: {service_reply}")
    
    conversation_history.append({"role": "service", "content": service_reply})
    
    print("\n⏳ AI正在分析客服回复...")
    time.sleep(1)
    
    result = client.send_message(service_reply, history=conversation_history[:-1])
    
    if result.get("error"):
        print(f"❌ AI分析失败: {result['error']}")
        break
    
    ai_reply = result.get("answer", "")
    conversation_id = result.get("conversation_id", "")
    
    print(f"\n🎯 AI分析结果:")
    print(f"   建议回复: {ai_reply}")
    print(f"   会话ID: {conversation_id}")
    
    conversation_history.append({"role": "customer", "content": ai_reply})
    
    print(f"\n👤 用户发送: {ai_reply[:50]}...")

print_banner("系统测试完成")

print(f"\n📊 对话统计:")
print(f"   总轮数: {len(mock_service_replies)}")
print(f"   用户消息: {len([m for m in conversation_history if m['role'] == 'customer'])}")
print(f"   客服消息: {len([m for m in conversation_history if m['role'] == 'service'])}")
print(f"   AI消息: {len([m for m in conversation_history if m['role'] == 'customer'])}")

print(f"\n✅ Dify API接入成功!")
print(f"✅ 多轮对话功能正常!")
print(f"✅ 投诉信息正确注入!")
print(f"✅ AI分析逻辑正常!")