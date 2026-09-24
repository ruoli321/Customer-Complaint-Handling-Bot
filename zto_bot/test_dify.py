"""测试 Dify API 连接"""
import sys
sys.path.insert(0, r"d:\Project\pythonjiaoben\zto_bot")
from main import DifyClient, COMPLAINT_INFO

print("测试 Dify API 连接...")
print(f"Dify API: http://192.168.1.8")
print()

client = DifyClient()
result = client.send_message("测试连接")

if result["error"]:
    print(f"❌ Dify API 连接失败: {result['error']}")
else:
    print(f"✅ Dify API 连接成功!")
    print(f"回复: {result['answer'][:200]}...")
    print(f"会话ID: {result['conversation_id']}")

# 测试多轮对话
print("\n--- 测试多轮对话 ---")
result2 = client.send_message("我的包裹丢失了，请帮我处理", history=[
    {"role": "user", "content": "你好"},
    {"role": "service", "content": "您好，请问有什么可以帮您？"}
])
if result2["error"]:
    print(f"❌ 多轮对话失败: {result2['error']}")
else:
    print(f"✅ 多轮对话成功!")
    print(f"回复: {result2['answer'][:200]}...")
    print(f"会话ID: {result2['conversation_id']}")
    print(f"与第一次相同: {result2['conversation_id'] == result['conversation_id']}")