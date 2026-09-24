import requests
import json
import re
import time
import argparse
import logging
from datetime import datetime
from config import *
from browser import BrowserController

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(f'complaint_bot_{datetime.now().strftime("%Y%m%d_%H%M%S")}.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)

class DeepSeekBrain:
    """DeepSeek 调度大脑：收到客服消息后自主决策——查 Dify 知识库再生成回复，或直接生成回复"""

    def __init__(self):
        self.api_key = DEEPSEEK_API_KEY
        self.api_base = DEEPSEEK_API_BASE
        self.model = DEEPSEEK_MODEL
        self.logger = logging.getLogger(__name__)

    # ---------- 基础能力 ----------

    def _chat(self, messages: list, temperature: float = 0.7, max_tokens: int = 1024) -> str:
        response = requests.post(
            f"{self.api_base}/chat/completions",
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            },
            json={
                "model": self.model,
                "messages": messages,
                "temperature": temperature,
                "max_tokens": max_tokens
            },
            timeout=30
        )
        if response.status_code != 200:
            raise RuntimeError(f"DeepSeek API Error: {response.status_code}")
        return response.json()['choices'][0]['message']['content']

    @staticmethod
    def _parse_json(text: str) -> dict:
        clean = text.strip()
        if clean.startswith('```'):
            clean = clean.replace('```json', '').replace('```', '').strip()
        return json.loads(clean)

    def _complaint_brief(self) -> str:
        return f"""用户投诉信息：
- 运单号：{COMPLAINT_INFO['tracking_number']}
- 物品：{COMPLAINT_INFO['product']}
- 问题：{COMPLAINT_INFO['issue']}
- 价值：{COMPLAINT_INFO['value']}
- 下单日期：{COMPLAINT_INFO['order_date']}
- 描述：{COMPLAINT_INFO['description']}"""

    def _complaint_info_text(self) -> str:
        """拼一段话传给 Dify 工作流的 complaint_info 输入（天数动态计算，LLM 无需推算日期）"""
        info = COMPLAINT_INFO
        days_text = ""
        try:
            days = (datetime.now() - datetime.strptime(info['order_date'], '%Y-%m-%d')).days
            days_text = f"丢件已过{days}天，"
        except (ValueError, KeyError):
            pass
        return (f"运单号{info['tracking_number']}，{info['product']}，价值{info['value']}，"
                f"{info['order_date']}下单，{days_text}问题：{info['issue']}。{info['description']}")

    @staticmethod
    def _history_text(chat_history: list) -> str:
        return "\n".join([
            f"{'用户' if msg['role'] == 'customer' else '客服'}: {msg['content']}"
            for msg in chat_history
        ])

    # ---------- 决策层：DeepSeek 判断走哪条路 ----------

    def decide(self, chat_history: list) -> dict:
        system_prompt = f"""你是投诉自动化系统的调度大脑。你正代替用户与中通快递客服对话，刚刚收到了客服的新消息。

{self._complaint_brief()}

当前对话历史（最后一条是客服最新消息）：
{self._history_text(chat_history)}

你的任务：根据客服最新消息，决定下一步行动，二选一：

1. "query_kb"：查 Dify 知识库。适用于客服消息涉及快递业务规则、理赔/赔偿标准与流程、时效承诺、投诉渠道、或客服推诿需要专业话术与法规依据反驳时。此时你必须同时给出 kb_query（用于知识库检索的完整问题，包含运单场景与诉求）。
2. "direct_reply"：直接生成回复。适用于仅需确认信息、提供运单号/联系方式、确认收到答复、催促进度等无需专业知识依据的场景。此时你必须同时给出 reply（要发送的完整回复）。

判断原则：涉及"该怎么赔、依据什么规定、流程是什么、能承诺什么"就查知识库；纯礼节性或信息确认就直接回复。

严格输出JSON格式，不要输出其他内容：
{{
    "action": "query_kb" 或 "direct_reply",
    "reason": "做出该决策的简要理由",
    "kb_query": "仅当action=query_kb时填写，传给Dify投诉工作流的内容，通常是客服最新消息原文或其中需要回应的诉求",
    "reply": "仅当action=direct_reply时填写，要发送的回复",
    "confidence": 0.0-1.0,
    "is_resolved": 客服最新消息是否表明问题已彻底解决，true/false
}}"""

        try:
            content = self._chat(
                [{"role": "system", "content": system_prompt}],
                temperature=0.3
            )
            decision = self._parse_json(content)
            self.logger.info(f"[决策] action={decision.get('action')} | 理由: {decision.get('reason')}")
            return decision
        except Exception as e:
            self.logger.warning(f"决策调用失败: {e}，降级为直接回复")
            return {
                "action": "direct_reply",
                "reason": f"决策异常降级: {e}",
                "reply": "请明确告诉我，我的包裹现在在哪里？什么时候能解决？",
                "confidence": 0.5,
                "is_resolved": False
            }

    # ---------- 知识库层：调 Dify 工作流「中通客服投诉机器人」（输入客服消息，输出生成的投诉回复） ----------

    def query_kb(self, kb_query: str, chat_history: list = None) -> str:
        url = f"{DIFY_API_BASE}/v1/workflows/run"
        headers = {
            "Authorization": f"Bearer {DIFY_API_KEY}",
            "Content-Type": "application/json"
        }
        if chat_history:
            history_text = self._history_text(chat_history[-6:])
        else:
            history_text = "（无，这是对话第一轮）"
        data = {
            "inputs": {
                "customer_service_reply": kb_query,
                "chat_history": history_text,
                "complaint_info": self._complaint_info_text()
            },
            "response_mode": "blocking",
            "user": "complaint_bot_user"
        }
        try:
            response = requests.post(url, headers=headers, json=data, timeout=120)
            if response.status_code != 200:
                raise RuntimeError(f"Dify Workflow API Error: {response.status_code} - {response.text[:200]}")
            result = response.json()
            data_obj = result.get('data') or {}
            if data_obj.get('status') != 'succeeded':
                raise RuntimeError(f"工作流执行失败: {data_obj.get('status')} {data_obj.get('error')}")

            outputs = data_obj.get('outputs') or {}
            reply = outputs.get('final_reply', '')
            # 兼容结构化输出：final_reply 可能已是对象而非 JSON 字符串
            if isinstance(reply, dict):
                reply = reply.get('reply') or reply.get('response') or ''
            # 工作流的 final_reply 是 JSON 字符串，键可能是 reply 或 response（LLM 输出不稳定），解析取正文
            try:
                parsed = json.loads(reply)
                if isinstance(parsed, dict):
                    reply = parsed.get('reply') or parsed.get('response') or reply
            except (json.JSONDecodeError, TypeError):
                # JSON 损坏（如值里含英文双引号），正则兜底提取正文
                m = re.search(r'"(?:reply|response)"\s*:\s*"(.*)"', reply or '', re.S)
                if m:
                    reply = m.group(1)

            reply = (reply or '').strip()
            # 仍解析不出正文时返回空，让上层降级为 DeepSeek 生成，避免把 JSON 原文发给客服
            if reply.startswith('{') and '"reply"' in reply:
                self.logger.warning("工作流返回无法解析的JSON，触发降级")
                return ""
            self.logger.info(f"[Dify工作流回复] {reply[:80]}")
            return reply
        except Exception as e:
            self.logger.warning(f"Dify工作流调用失败: {e}")
            return ""

    # ---------- 回复生成层 ----------

    def generate_with_kb(self, chat_history: list, kb_answer: str) -> dict:
        system_prompt = f"""你是专业的投诉策略顾问，正在代替用户与中通快递客服对话。

{self._complaint_brief()}

当前对话历史（最后一条是客服最新消息）：
{self._history_text(chat_history)}

以下是从中通投诉知识库检索到的参考资料：
{kb_answer if kb_answer else '（知识库检索无结果，请基于通用经验回复）'}

请结合参考资料生成下一步要发送的投诉回复。要求坚定但礼貌，引用知识库中的赔偿依据/流程/时效承诺来施压。

严格输出JSON格式：
{{
    "analysis": "对客服回复的分析",
    "suggested_reply": "建议发送的回复内容",
    "confidence": 0.0-1.0,
    "is_resolved": true/false
}}"""
        try:
            content = self._chat([{"role": "system", "content": system_prompt}], temperature=0.7)
            return self._parse_json(content)
        except Exception as e:
            self.logger.warning(f"知识库回复生成失败: {e}，降级为mock分析")
            return self._mock_analysis(chat_history)

    # ---------- 对外主入口：决策 → (查库) → 生成 ----------

    def analyze_and_reply(self, chat_history: list) -> dict:
        decision = self.decide(chat_history)

        if decision.get('is_resolved'):
            # DeepSeek 判断问题已解决，无需再发消息
            return {
                "analysis": f"[决策:问题已解决] {decision.get('reason', '')}",
                "suggested_reply": "",
                "confidence": decision.get('confidence', 0.9),
                "is_resolved": True
            }

        if decision.get('action') == 'query_kb' and DIFY_API_KEY:
            # 兜底输入：优先用 DeepSeek 给出的 kb_query，否则取客服最新消息原文
            last_service_msg = next(
                (m['content'] for m in reversed(chat_history) if m['role'] == 'service'), '')
            kb_reply = self.query_kb(decision.get('kb_query') or last_service_msg, chat_history)
            if kb_reply:
                # 工作流已生成完整投诉回复，直接采用
                return {
                    "analysis": f"[决策:查知识库] {decision.get('reason', '')} | Dify工作流已生成回复",
                    "suggested_reply": kb_reply,
                    "confidence": decision.get('confidence', 0.8),
                    "is_resolved": False
                }
            # 工作流无结果时降级：DeepSeek 结合对话历史直接生成
            result = self.generate_with_kb(chat_history, '')
            result['analysis'] = f"[决策:查知识库·工作流降级] {decision.get('reason', '')} | {result.get('analysis', '')}"
            return result

        # 直接回复路径
        reply = decision.get('reply') or ''
        if not reply:
            result = self._mock_analysis(chat_history)
            reply = result['suggested_reply']
        return {
            "analysis": f"[决策:直接回复] {decision.get('reason', '')}",
            "suggested_reply": reply,
            "confidence": decision.get('confidence', 0.7),
            "is_resolved": decision.get('is_resolved', False)
        }

    def _mock_analysis(self, chat_history: list) -> dict:
        if not chat_history:
            return {
                "analysis": "客服刚刚打招呼，需要开始投诉",
                "suggested_reply": f"你好，我的运单号是{COMPLAINT_INFO['tracking_number']}，包裹丢失了，已经7天了，请帮忙处理。",
                "confidence": 0.9,
                "is_resolved": False
            }

        last_service_msg = None
        for msg in reversed(chat_history):
            if msg['role'] == 'service':
                last_service_msg = msg['content']
                break

        if not last_service_msg:
            return {
                "analysis": "等待客服回复",
                "suggested_reply": "",
                "confidence": 0.5,
                "is_resolved": False
            }

        if "帮您查询" in last_service_msg or "请稍等" in last_service_msg:
            return {
                "analysis": "客服正在查询，需要等待结果",
                "suggested_reply": "好的，请尽快查询。",
                "confidence": 0.8,
                "is_resolved": False
            }

        if "延迟" in last_service_msg or "天气" in last_service_msg:
            return {
                "analysis": "客服试图推诿，说是天气原因延迟",
                "suggested_reply": "但是已经超过7天了，天气原因不应该导致这么长时间的延误，请给我一个明确的处理方案。",
                "confidence": 0.9,
                "is_resolved": False
            }

        if "耐心等待" in last_service_msg:
            return {
                "analysis": "客服要求继续等待，但用户已经等待太久",
                "suggested_reply": "我已经等待了7天，不能再等了，请立即处理我的理赔申请。",
                "confidence": 0.95,
                "is_resolved": False
            }

        if "理赔" in last_service_msg:
            return {
                "analysis": "客服提到理赔，需要跟进理赔流程",
                "suggested_reply": "好的，请告诉我理赔需要提供哪些材料，我会尽快准备。",
                "confidence": 0.85,
                "is_resolved": False
            }

        if "登记" in last_service_msg or "24小时" in last_service_msg:
            return {
                "analysis": "客服已登记投诉并承诺24小时回复",
                "suggested_reply": "好的，请务必在24小时内给我回复，我的电话是13800138000。",
                "confidence": 0.8,
                "is_resolved": False
            }

        if "感谢" in last_service_msg or "生活愉快" in last_service_msg:
            return {
                "analysis": "客服结束对话，但问题可能还未解决",
                "suggested_reply": "请确保我的问题得到妥善处理，否则我会继续投诉。",
                "confidence": 0.7,
                "is_resolved": True
            }

        return {
            "analysis": "客服回复无法识别，需要追问",
            "suggested_reply": "请明确告诉我，我的包裹现在在哪里？什么时候能解决？",
            "confidence": 0.6,
            "is_resolved": False
        }

class ComplaintBot:
    def __init__(self, mock_mode: bool = True, headless: bool = False):
        self.mock_mode = mock_mode
        self.headless = headless
        self.browser = BrowserController(headless=headless)
        self.analyzer = DeepSeekBrain()
        self.chat_history = []
        self.logger = logging.getLogger(__name__)
        self.log_server_url = "http://localhost:5001/log"
        self.max_repeated_responses = 3
        self.max_rounds = 15

    def _send_log(self, message, type='info'):
        if self.mock_mode:
            try:
                requests.post(
                    self.log_server_url,
                    json={'message': message, 'type': type},
                    timeout=2
                )
            except:
                pass

    def _detect_loop(self) -> bool:
        service_messages = [msg['content'] for msg in self.chat_history if msg['role'] == 'service']
        
        if len(service_messages) < self.max_repeated_responses:
            return False
        
        recent_messages = service_messages[-self.max_repeated_responses:]
        unique_messages = set(recent_messages)
        
        if len(unique_messages) == 1:
            self._send_log(f"⚠️ 检测到死循环：客服连续{self.max_repeated_responses}次发送相同回复", 'warning')
            return True
        
        return False

    def start(self):
        self.logger.info("=" * 60)
        self.logger.info("中通投诉机器人启动")
        self.logger.info(f"模式: {'模拟模式' if self.mock_mode else '真实模式'}")
        self.logger.info(f"AI引擎: DeepSeek调度大脑 + Dify投诉工作流")
        self.logger.info(f"自动发送: {'是' if AUTO_SEND else '否'}")
        self.logger.info(f"无头模式: {'是' if self.headless else '否'}")
        self.logger.info(f"投诉信息: {json.dumps(COMPLAINT_INFO, ensure_ascii=False)}")
        self.logger.info("=" * 60)
        
        self._send_log("🚀 中通投诉机器人启动", 'success')
        self._send_log(f"模式: {'模拟模式' if self.mock_mode else '真实模式'}", 'info')
        self._send_log(f"AI引擎: DeepSeek调度大脑 + Dify投诉工作流", 'info')

        url = MOCK_SERVER_URL if self.mock_mode else REAL_SERVER_URL
        self.logger.info(f"\n正在连接: {url}")
        self._send_log(f"正在连接: {url}", 'info')
        
        self.browser.launch()
        self.browser.navigate(url)

        self.chat_history = self.browser.get_messages()
        self._log_history()

        self._run_dialog()

    def _run_dialog(self):
        for round_num in range(self.max_rounds):
            if self._detect_loop():
                self.logger.info("\n❌ 检测到对话死循环，自动结束对话")
                self._send_log("❌ 检测到对话死循环，自动结束对话", 'error')
                break

            self.logger.info(f"\n{'='*60}")
            self.logger.info(f"第 {round_num + 1} 轮对话")
            self.logger.info(f"{'='*60}")
            
            self._send_log(f"第 {round_num + 1} 轮对话开始", 'info')
            
            analysis = self.analyzer.analyze_and_reply(self.chat_history)
            self.logger.info(f"\n【AI分析结果】")
            self.logger.info(f"分析: {analysis['analysis']}")
            self.logger.info(f"建议回复: {analysis['suggested_reply']}")
            self.logger.info(f"置信度: {analysis['confidence']:.2f}")
            self.logger.info(f"问题已解决: {'是' if analysis['is_resolved'] else '否'}")
            
            self._send_log(f"AI分析: {analysis['analysis']}", 'info')
            self._send_log(f"建议回复: {analysis['suggested_reply']}", 'info')

            if analysis['is_resolved']:
                self.logger.info("\n✓ 问题已解决，结束对话")
                self._send_log("✓ 问题已解决，结束对话", 'success')
                break

            if not analysis['suggested_reply']:
                self.logger.info("\n⏳ 等待客服回复...")
                self._send_log("⏳ 等待客服回复...", 'info')
                time.sleep(3)
                self.chat_history = self.browser.get_messages()
                self._log_history()
                continue

            if AUTO_SEND:
                self.logger.info(f"\n📤 自动发送消息: {analysis['suggested_reply']}")
                self._send_log(f"📤 发送消息: {analysis['suggested_reply']}", 'success')
                if not self.browser.send_message(analysis['suggested_reply']):
                    self.logger.warning("⚠️ 消息发送未生效（输入框未清空）")
                    self._send_log("⚠️ 消息发送未生效（输入框未清空）", 'error')
            else:
                user_input = input("\n是否发送此消息？(y/n，输入其他内容修改消息): ").strip().lower()
                if user_input == 'y':
                    self.logger.info(f"\n📤 用户确认发送: {analysis['suggested_reply']}")
                    self._send_log(f"📤 用户确认发送: {analysis['suggested_reply']}", 'success')
                    self.browser.send_message(analysis['suggested_reply'])
                elif user_input == 'n':
                    self.logger.info("\n⏭️ 用户跳过此条消息")
                    self._send_log("⏭️ 用户跳过此条消息", 'warning')
                    continue
                else:
                    self.logger.info(f"\n📤 用户修改后发送: {user_input}")
                    self._send_log(f"📤 用户修改后发送: {user_input}", 'success')
                    self.browser.send_message(user_input)

            time.sleep(3)
            self.chat_history = self.browser.get_messages()
            self._log_history()

            if round_num + 1 >= self.max_rounds:
                self.logger.info("\n⚠️ 达到最大对话轮数，结束对话")
                self._send_log("⚠️ 达到最大对话轮数，结束对话", 'warning')
                break

        self.logger.info("\n" + "="*60)
        self.logger.info("对话结束")
        self.logger.info("="*60)
        self._log_full_summary()
        self._send_log("对话结束", 'success')
        self.browser.close()

    def _log_history(self):
        self.logger.info("\n【当前对话历史】")
        for i, msg in enumerate(self.chat_history):
            role = "👤 用户" if msg['role'] == 'customer' else "🤖 客服"
            self.logger.info(f"{i + 1}. {role}: {msg['content']}")
            
            if i == len(self.chat_history) - 1:
                role_text = "用户" if msg['role'] == 'customer' else "客服"
                self._send_log(f"[{role_text}] {msg['content']}", 'info')

    def _log_full_summary(self):
        self.logger.info("\n【对话完整总结】")
        self.logger.info(f"总轮数: {len(self.chat_history) // 2}")
        self.logger.info(f"总消息数: {len(self.chat_history)}")
        self.logger.info(f"用户消息: {sum(1 for m in self.chat_history if m['role'] == 'customer')}")
        self.logger.info(f"客服消息: {sum(1 for m in self.chat_history if m['role'] == 'service')}")
        self.logger.info("\n完整对话记录:")
        
        summary_text = f"对话总结: 共{len(self.chat_history) // 2}轮，用户{sum(1 for m in self.chat_history if m['role'] == 'customer')}条消息，客服{sum(1 for m in self.chat_history if m['role'] == 'service')}条消息"
        self._send_log(summary_text, 'success')
        
        for i, msg in enumerate(self.chat_history):
            role = "[用户]" if msg['role'] == 'customer' else "[客服]"
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.logger.info(f"[{timestamp}] {role} {msg['content']}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="中通投诉机器人（DeepSeek调度大脑 + Dify知识库 + Playwright执行）")
    parser.add_argument("--mock", action="store_true", default=True, help="使用模拟模式")
    parser.add_argument("--headless", action="store_true", help="无头模式运行")
    parser.add_argument("--no-auto", action="store_true", help="关闭自动发送（默认自动发送）")
    args = parser.parse_args()

    AUTO_SEND = not args.no_auto

    bot = ComplaintBot(mock_mode=args.mock, headless=args.headless)
    bot.start()