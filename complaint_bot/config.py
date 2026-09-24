# ============================================================
# 中通客服投诉机器人 - 配置文件
# 密钥一律从环境变量 / 同目录 .env 读取，严禁硬编码提交到仓库
# ============================================================
import os


def _load_env():
    """极简 .env 加载器：解析同目录 .env 的 KEY=VALUE 行写入环境变量（已有环境变量优先）"""
    env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")
    if os.path.exists(env_path):
        with open(env_path, "r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, _, value = line.partition("=")
                    os.environ.setdefault(key.strip(), value.strip())


_load_env()

# DeepSeek API（https://platform.deepseek.com 申请）
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY", "")
DEEPSEEK_API_BASE = "https://api.deepseek.com"
DEEPSEEK_MODEL = "deepseek-chat"

# Dify API（本地部署 Dify 的应用 API Key，复制 .env.example 为 .env 后填入）
DIFY_API_KEY = os.getenv("DIFY_API_KEY", "")  # 「中通客服投诉机器人」workflow 应用
DIFY_API_BASE = os.getenv("DIFY_API_BASE", "http://localhost:8080")  # Dify nginx 端口为 8080（80 被 crmeb 占用）
DIFY_APP_MODE = False  # False=workflow（/v1/workflows/run），True=chat（/v1/chat-messages）

MOCK_SERVER_URL = "http://localhost:5001"
REAL_SERVER_URL = "https://www.zto.com"

COMPLAINT_INFO = {
    "tracking_number": "ZT1234567890",
    "product": "电子产品",
    "issue": "包裹丢失",
    "value": "500元",
    "order_date": "2026-09-08",
    "description": "我的包裹在运输途中丢失，已经超过7天没有任何更新信息，多次联系客服都没有得到有效回复。"
}

MAX_DIALOG_ROUNDS = 20
AUTO_SEND = True  # 自动发送模式：DeepSeek 决策后由 Playwright 自动输入并发送
