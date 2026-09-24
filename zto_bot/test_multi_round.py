import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import DifyClient
from config import COMPLAINT_INFO

print("=" * 60)
print("Dify API 多轮对话测试")
print("=" * 60)

client = DifyClient()

print(f"\nAPI基础地址: {client.api_base}")
print(f"API密钥: {client.api_key}")
print(f"\n投诉信息: {COMPLAINT_INFO}")

conversation_history = []

test_messages = [
    "你好，我的包裹丢了",
    "包裹已经超过7天了",
    "请给我一个明确的处理方案",
    "我需要申请理赔",
    "理赔需要提供什么材料"
]

print("\n" + "=" * 60)
print("开始多轮对话测试")
print("=" * 60)

for i, message in enumerate(test_messages, 1):
    print(f"\n--- 第 {i} 轮对话 ---")
    print(f"👤 用户: {message}")
    
    conversation_history.append({"role": "user", "content": message})
    
    result = client.send_message(message, history=conversation_history[:-1])
    
    if result.get("error"):
        print(f"❌ 错误: {result['error']}")
        break
    
    ai_reply = result.get("answer", "")
    print(f"🤖 AI回复: {ai_reply[:200]}")
    
    conversation_history.append({"role": "service", "content": ai_reply})
    
    print(f"📋 会话ID: {result.get('conversation_id', '')[:20]}...")

print("\n" + "=" * 60)
print("多轮对话测试完成")
print("=" * 60)