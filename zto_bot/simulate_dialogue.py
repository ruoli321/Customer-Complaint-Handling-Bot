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

def print_log(msg, level="info"):
    timestamp = time.strftime("%H:%M:%S")
    colors = {
        "info": "\033[0m",
        "success": "\033[92m",
        "warning": "\033[93m",
        "error": "\033[91m",
        "user": "\033[94m",
        "service": "\033[93m",
        "ai": "\033[96m"
    }
    print(f"[{timestamp}] {colors.get(level, '')}{msg}\033[0m")

print_banner("中通快递投诉机器人 - Dify API 模拟对话")

client = DifyClient()

print_log(f"Dify API地址: {client.api_base}/v1", "info")
print_log(f"Dify API密钥: {client.api_key[:8]}...", "info")

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

print_banner("开始模拟中通客服对话")
print_log("客服消息为预设模拟，用户回复由Dify API实时生成", "info")

for round_num, service_reply in enumerate(mock_service_replies, 1):
    print(f"\n{'='*70}")
    print(f"                    第 {round_num} 轮对话")
    print(f"{'='*70}")
    
    print("\n" + "▌" * 2 + " 中通客服:")
    print(f"  {service_reply}")
    
    conversation_history.append({"role": "service", "content": service_reply})
    
    print("\n" + "⏳" * 3 + " 正在调用 Dify API 分析客服回复...")
    
    result = client.send_message(service_reply, history=conversation_history[:-1])
    
    if result.get("error"):
        print(f"\n❌ Dify API调用失败: {result['error']}")
        break
    
    ai_reply = result.get("answer", "")
    conversation_id = result.get("conversation_id", "")
    
    print(f"\n✅ Dify API调用成功!")
    print(f"   会话ID: {conversation_id}")
    
    print("\n" + "▌" * 2 + " 用户回复 (Dify AI生成):")
    print(f"  {ai_reply}")
    
    conversation_history.append({"role": "customer", "content": ai_reply})
    
    time.sleep(2)

print_banner("模拟对话结束")

print(f"\n📊 对话统计:")
print(f"   总轮数: {len(mock_service_replies)}")
print(f"   会话ID: {client.conversation_id}")
print(f"   投诉信息: 运单号={COMPLAINT_INFO['tracking_number']}, 物品={COMPLAINT_INFO['product']}, 价值={COMPLAINT_INFO['value']}")

print("\n🎉 Dify API模拟对话测试完成！所有回复均由Dify AI实时生成。")