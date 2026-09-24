"""测试 Dify API - 使用本地 localhost"""
import requests
import json

from config import DIFY_API_KEY

api_key = DIFY_API_KEY
headers = {
    "Authorization": f"Bearer {api_key}",
    "Content-Type": "application/json"
}
payload = {
    "inputs": {},
    "query": "测试连接，请回复OK",
    "response_mode": "blocking",
    "user": "test_user"
}

for base in ["http://localhost", "http://192.168.1.8"]:
    print(f"\n--- 测试 {base} ---")
    try:
        r = requests.post(f"{base}/v1/chat-messages", headers=headers, json=payload, timeout=15)
        print(f"状态码: {r.status_code}")
        if r.status_code == 200:
            data = r.json()
            answer = data.get("answer", "")
            cid = data.get("conversation_id", "")
            print(f"✅ 成功!")
            print(f"回复: {answer[:200]}")
            print(f"会话ID: {cid}")
        else:
            print(f"❌ 错误: {r.text[:300]}")
    except Exception as e:
        print(f"❌ 异常: {type(e).__name__}: {e}")