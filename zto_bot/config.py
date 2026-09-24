# ============================================================
# ZTO 快递投诉机器人 - 配置文件
# 密钥/带凭证的URL一律从环境变量 / 同目录 .env 读取，严禁硬编码提交到仓库
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

# Dify API 配置
DIFY_API_KEY = os.getenv("DIFY_API_KEY", "")
DIFY_API_BASE = os.getenv("DIFY_API_BASE", "http://localhost:8080")  # Dify 部署地址 (nginx端口已从80改为8080, 80被crmeb占用)
DIFY_APP_MODE = True

# 投诉信息
COMPLAINT_INFO = {
    "tracking_number": "ZT1234567890",
    "product": "电子产品",
    "issue": "包裹丢失",
    "value": "500元",
    "order_date": "2024-01-15",
    "description": "我的包裹在运输途中丢失，已经超过7天没有任何更新信息，多次联系客服都没有得到有效回复。"
}

# 浏览器配置
BROWSER_CHANNEL = "msedge"  # 使用本地 Edge 浏览器 (chrome未安装，改用msedge)
ZTO_URL = "https://www.zto.com/"
KF_URL = "https://kf.zto.com/"

# 中通在线客服直达地址（含 authToken，约2小时有效期）
# 获取方式：登录官网后从浏览器复制 kf.zto.com 完整地址，写入同目录 .env 的 KF_FULL_URL（勿提交到仓库）
# 过期后：重新复制替换 .env，或走「进入客服页」按钮点击兜底
KF_FULL_URL = os.getenv("KF_FULL_URL", "")

# 测试消息
TEST_MESSAGE = f"你好，我的运单号是{COMPLAINT_INFO['tracking_number']}，包裹已经丢失超过7天了，请帮我处理一下。"
