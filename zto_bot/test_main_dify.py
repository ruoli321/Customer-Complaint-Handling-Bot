import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from main import DifyClient

print("=" * 60)
print("测试 main.py 中的 DifyClient 类")
print("=" * 60)

client = DifyClient()

print(f"\nAPI基础地址: {client.api_base}")
print(f"API密钥: {client.api_key}")

print("\n测试发送消息...")
result = client.send_message("你好，这是一个测试消息")

print(f"\n返回结果:")
print(f"  answer: {result.get('answer', '')[:100]}")
print(f"  conversation_id: {result.get('conversation_id', '')}")
print(f"  error: {result.get('error', 'None')}")

if result.get('error'):
    print("\n❌ Dify API调用失败")
    print(f"   错误原因: {result['error']}")
else:
    print("\n✅ Dify API调用成功")

print("\n" + "=" * 60)
print("测试完成")
print("=" * 60)