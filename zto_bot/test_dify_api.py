import requests
import json

from config import DIFY_API_KEY, DIFY_API_BASE

API_KEY = DIFY_API_KEY
API_BASE = DIFY_API_BASE

def test_dify_api():
    print("=" * 60)
    print("Dify API 连接测试")
    print("=" * 60)
    
    test_urls = [
        f"{API_BASE}/v1/info",
        f"{API_BASE}/v1/parameters"
    ]
    
    headers = {
        "Authorization": f"Bearer {API_KEY}",
        "Content-Type": "application/json"
    }
    
    for url in test_urls:
        print(f"\n测试 URL: {url}")
        try:
            response = requests.get(url, headers=headers, timeout=10)
            print(f"状态码: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                print(f"响应内容: {json.dumps(data, indent=2, ensure_ascii=False)[:500]}")
                print("✅ API 调用成功!")
            else:
                print(f"❌ API 调用失败: {response.text[:200]}")
                
        except requests.exceptions.ConnectionError:
            print(f"❌ 连接失败: 无法连接到 {API_BASE}")
        except requests.exceptions.Timeout:
            print("❌ 请求超时")
        except Exception as e:
            print(f"❌ 未知错误: {e}")
    
    print("\n" + "=" * 60)
    print("测试发送消息接口")
    print("=" * 60)
    
    send_url = f"{API_BASE}/v1/chat-messages"
    payload = {
        "inputs": {},
        "query": "你好，测试消息",
        "response_mode": "blocking",
        "user": "test_user"
    }
    
    print(f"\n测试 URL: {send_url}")
    try:
        response = requests.post(send_url, headers=headers, json=payload, timeout=30)
        print(f"状态码: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"会话ID: {data.get('conversation_id')}")
            print(f"回答: {data.get('answer', '')[:200]}")
            print("✅ 消息发送成功!")
        else:
            print(f"❌ 消息发送失败: {response.text[:200]}")
            
    except requests.exceptions.ConnectionError:
        print(f"❌ 连接失败: 无法连接到 {API_BASE}")
    except requests.exceptions.Timeout:
        print("❌ 请求超时")
    except Exception as e:
        print(f"❌ 未知错误: {e}")

if __name__ == "__main__":
    test_dify_api()