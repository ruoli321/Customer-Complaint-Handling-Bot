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

print_banner("中通快递投诉机器人 - Dify API 交互式对话")

client = DifyClient()

print_log(f"Dify API地址: {client.api_base}/v1", "info")
print_log(f"Dify API密钥: {client.api_key[:8]}...", "info")

print("\n" + "-" * 70)
print_log("投诉信息:", "info")
print_log(f"  运单号: {COMPLAINT_INFO['tracking_number']}", "info")
print_log(f"  物品: {COMPLAINT_INFO['product']}", "info")
print_log(f"  问题: {COMPLAINT_INFO['issue']}", "info")
print_log(f"  价值: {COMPLAINT_INFO['value']}", "info")

conversation_history = []
round_num = 0

print_banner("开始交互式对话")
print_log("请输入中通客服的回复，按回车发送；输入 'exit' 结束对话", "warning")
print_log("示例回复: 您好，中通快递，请问有什么可以帮您？", "info")

while True:
    round_num += 1
    print(f"\n🔄 第 {round_num} 轮对话")
    print("-" * 50)
    
    service_reply = input("\n🤖 请输入客服回复: ").strip()
    
    if service_reply.lower() == "exit":
        print_log("用户结束对话", "info")
        break
    
    if not service_reply:
        print_log("请输入客服回复内容", "warning")
        round_num -= 1
        continue
    
    print_log(f"客服: {service_reply}", "service")
    
    conversation_history.append({"role": "service", "content": service_reply})
    
    print_log("⏳ 正在调用 Dify API 分析...", "info")
    
    result = client.send_message(service_reply, history=conversation_history[:-1])
    
    if result.get("error"):
        print_log(f"❌ Dify API调用失败: {result['error']}", "error")
        break
    
    ai_reply = result.get("answer", "")
    conversation_id = result.get("conversation_id", "")
    
    print_log(f"✅ Dify API调用成功!", "success")
    print_log(f"   会话ID: {conversation_id}", "info")
    
    print("\n🎯 AI分析结果:")
    print_log(f"   {ai_reply}", "ai")
    
    conversation_history.append({"role": "customer", "content": ai_reply})
    
    print(f"\n👤 用户回复: {ai_reply[:60]}...")

print_banner("对话结束")

print(f"\n📊 对话统计:")
print(f"   总轮数: {round_num}")
print(f"   会话ID: {client.conversation_id}")

print("\n" + "=" * 70)