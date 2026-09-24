# ============================================================
# ZTO 快递投诉机器人 - 主程序
# 功能：Playwright 操作中通客服页面 + Dify AI 回复 + Tkinter GUI
# ============================================================

import json
import requests
import threading
import time
import tkinter as tk
from tkinter import scrolledtext, font
from datetime import datetime
from queue import Queue

from playwright.sync_api import sync_playwright

from config import *

# ============================================================
# 第一部分：Dify API 客户端
# ============================================================

class DifyClient:
    """Dify 对话型应用 API 客户端"""

    def __init__(self, api_key=DIFY_API_KEY, api_base=DIFY_API_BASE):
        self.api_key = api_key
        self.api_base = api_base
        self.conversation_id = None  # 用于多轮对话
        self.user = "zto_bot_user"

    def send_message(self, text: str, history: list = None) -> dict:
        """
        发送消息到 Dify 对话 API

        Args:
            text: 用户消息内容
            history: 历史对话列表，格式 [{"role":"user/assistant","content":"..."}]

        Returns:
            {"answer": "...", "conversation_id": "...", "error": None/str}
        """
        url = f"{self.api_base}/v1/chat-messages"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

        # 构建带上下文的 query
        system_context = f"""你是一个专业的投诉策略顾问，正在帮助用户与中通快递客服进行投诉对话。

用户投诉信息：
- 运单号：{COMPLAINT_INFO['tracking_number']}
- 物品：{COMPLAINT_INFO['product']}
- 问题：{COMPLAINT_INFO['issue']}
- 价值：{COMPLAINT_INFO['value']}
- 下单日期：{COMPLAINT_INFO['order_date']}
- 描述：{COMPLAINT_INFO['description']}

你的任务：
1. 分析客服的最新回复
2. 判断客服是否已解决问题或给出有效解决方案
3. 根据分析结果，生成下一步的投诉回复

回复策略：
- 如果客服推诿，要坚定但礼貌地要求解决
- 如果客服要求提供信息，提供所需信息
- 如果客服同意处理，确认处理时间和方式
- 保持专业、坚定的态度

请直接输出你的回复内容，不要输出JSON格式，用自然语言回复即可。"""

        # 构建完整的对话历史
        full_query = system_context + "\n\n"
        if history:
            for msg in history:
                role = "用户" if msg["role"] == "user" else "客服"
                full_query += f"{role}: {msg['content']}\n"
        full_query += f"\n用户最新消息：{text}\n\n请根据以上对话历史，生成你的投诉回复："

        payload = {
            "inputs": {},
            "query": full_query,
            "response_mode": "blocking",  # 非流式，简单直接
            "user": self.user
        }

        # 带上 conversation_id 实现多轮对话
        if self.conversation_id:
            payload["conversation_id"] = self.conversation_id

        try:
            resp = requests.post(url, headers=headers, json=payload, timeout=60)
            if resp.status_code == 200:
                data = resp.json()
                answer = data.get("answer", "")
                # 更新 conversation_id
                if data.get("conversation_id"):
                    self.conversation_id = data["conversation_id"]
                return {"answer": answer, "conversation_id": self.conversation_id, "error": None}
            else:
                err_msg = f"Dify API 错误 {resp.status_code}: {resp.text[:200]}"
                return {"answer": "", "conversation_id": self.conversation_id, "error": err_msg}
        except Exception as e:
            return {"answer": "", "conversation_id": self.conversation_id, "error": str(e)}

    def reset_conversation(self):
        """重置对话（开始新会话）"""
        self.conversation_id = None


# ============================================================
# 第二部分：Playwright 浏览器控制器
# ============================================================

class ZTOBrowserController:
    """控制浏览器与中通客服页面交互"""

    def __init__(self, gui_queue: Queue):
        self.gui_queue = gui_queue
        self.playwright = None
        self.browser = None
        self.context = None
        self.page = None
        self.kf_page = None
        self._stop = False
        self._lock = threading.Lock()
        self.login_confirmed = False  # GUI"登录完成"按钮置位，令自动检测立即通过
        # Playwright 同步 API 绑定创建线程：所有浏览器操作必须串行到同一专用线程执行，
        # 否则会报 "cannot switch to a different thread"
        self._task_queue = Queue()
        self._browser_thread = None

    # ---------------- 浏览器专用线程基础设施 ----------------

    def _ensure_thread(self):
        """确保浏览器专用线程存活"""
        if self._browser_thread is None or not self._browser_thread.is_alive():
            self._browser_thread = threading.Thread(
                target=self._browser_loop, daemon=True, name="BrowserThread")
            self._browser_thread.start()

    def _browser_loop(self):
        """常驻浏览器线程：从队列取任务串行执行"""
        while not self._stop:
            try:
                task = self._task_queue.get(timeout=0.5)
            except Exception:
                continue
            if task is None:
                break
            func, done, box = task
            try:
                box["result"] = func()
                box["ok"] = True
            except Exception as e:
                box["error"] = e
                box["ok"] = False
            done.set()

    def _submit(self, func, timeout=180):
        """提交浏览器任务并阻塞等待完成，返回 (ok, result_or_error)"""
        self._ensure_thread()
        done = threading.Event()
        box = {}
        self._task_queue.put((func, done, box))
        if not done.wait(timeout):
            return False, TimeoutError(f"浏览器任务执行超时({timeout}s)")
        if box.get("ok"):
            return True, box.get("result")
        return False, box.get("error")

    def _log(self, msg: str, level="info"):
        """发送日志到 GUI"""
        self.gui_queue.put({"type": "log", "message": msg, "level": level})

    def launch(self):
        """启动本地 Edge 浏览器，打开中通首页（提交到浏览器线程执行）"""
        ok, err = self._submit(self._launch_impl, timeout=120)
        if not ok:
            raise err

    def _launch_impl(self):
        self._log("正在启动浏览器...")
        self.playwright = sync_playwright().start()
        # 使用本地 Edge 浏览器，允许弹出窗口
        self.browser = self.playwright.chromium.launch(
            channel=BROWSER_CHANNEL,
            headless=False,
            ignore_default_args=["--enable-automation"],
            args=[
                "--start-maximized",
                "--disable-popup-blocking",
                "--allow-popups",
                "--allow-popups-from-sites",
                "--disable-blink-features=AutomationControlled",
                "--disable-features=CrossSiteDocumentBlockingIfIsolating",
                "--disable-features=CrossSiteDocumentBlockingAlways",
                "--disable-web-security"
            ]
        )
        # 创建 context（no_viewport=True 配合 --start-maximized 使用真实窗口尺寸，
        # 之前同时传 viewport 会被 no_viewport 覆盖导致矛盾）
        self.context = self.browser.new_context(
            no_viewport=True,
            permissions=["geolocation"],
        )
        # 降低自动化特征 + 绕过通知权限对话框
        # 实测：点击"在线客服"时网站 JS 会调用 Notification.requestPermission()，
        # Edge 弹出权限对话框(edge://permission-request-dialog)并中断后续流程，
        # 导致打开 kf.zto.com 的 window.open 永不执行 —— 表现为"点击被拦截"。
        # 伪造 requestPermission 直接返回 granted，网站代码即可继续打开客服窗口。
        self.context.add_init_script("""
            Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
            if (window.Notification) {
                Notification.requestPermission = function(cb) {
                    if (cb) { try { cb('granted'); } catch (e) {} }
                    return Promise.resolve('granted');
                };
                try {
                    Object.defineProperty(Notification, 'permission', {get: () => 'granted'});
                } catch (e) {}
            }
            // 劫持 window.open：记录弹窗地址。若新窗口被浏览器拦截，
            // 脚本仍可读取 __last_popup_url 自行打开客服页
            (() => {
                const _open = window.open;
                window.open = function(url, name, specs) {
                    window.__last_popup_url = url;
                    window.__popup_count = (window.__popup_count || 0) + 1;
                    try {
                        return _open ? _open.call(window, url, name, specs) : null;
                    } catch (e) {
                        return null;
                    }
                };
            })();
        """)
        # 设置弹出窗口处理
        self.context.on("page", lambda page: self._on_new_page(page))

        self.page = self.context.new_page()
        self.page.goto(ZTO_URL, wait_until="domcontentloaded", timeout=60000)
        try:
            self.page.wait_for_load_state("load", timeout=30000)
        except Exception:
            pass
        self._log(f"已打开 {ZTO_URL}，请在页面右上角手动登录...", "success")

    def _on_new_page(self, page):
        """处理新打开的页面（如客服窗口）。
        popup 刚创建时 URL 往往是 about:blank，需同时监听 load 事件后再判定。"""
        self._log(f"检测到新页面: {page.url}")
        kf_logged = {"done": False}  # 防止 load/domcontentloaded 重复打日志

        def _check_kf(_=None):
            try:
                url = page.url
                if "kf.zto.com" in url:
                    self.kf_page = page
                    page.bring_to_front()
                    if not kf_logged["done"]:
                        kf_logged["done"] = True
                        self._log(f"客服页面已打开: {url[:80]}", "success")
            except Exception:
                pass

        _check_kf()
        try:
            page.on("load", _check_kf)
            page.on("domcontentloaded", _check_kf)
        except Exception:
            pass

    def wait_for_login(self, timeout_minutes=10):
        """等待用户手动登录（提交到浏览器线程执行，防误判判定见 impl）"""
        ok, r = self._submit(
            lambda: self._wait_for_login_impl(timeout_minutes),
            timeout=timeout_minutes * 60 + 60)
        return r if ok else False

    def _wait_for_login_impl(self, timeout_minutes=10):
        """
        等待用户手动登录中通官网（实测登录入口为 div.header-btn.login，文本"登录/注册"）。
        判定规则（防误判）：
        1. 必须先"见过"登录入口，其消失才有效 —— 避免页面未加载完时误判
        2. 入口消失期间必须停留在 zto.com —— 避免跳转登录页时误判
        3. 入口消失需连续 3 次（约6秒）确认
        4. 页面出现脱敏手机号（如 185****0052）直接判定成功
        5. 用户点 GUI「登录完成」按钮立即通过
        """
        self._log("等待手动登录中通官网...（登录后自动继续，也可点「登录完成」按钮）", "warning")
        start = time.time()
        timeout = timeout_minutes * 60
        seen_entry = False   # 是否见过登录入口
        gone_count = 0       # 入口连续不可见次数

        while time.time() - start < timeout:
            if self._stop:
                return False
            if self.login_confirmed:
                self._log("用户已手动确认登录", "success")
                return True
            try:
                on_zto = "zto.com" in self.page.url

                # 正向信号：登录后右上角显示脱敏手机号
                try:
                    if self.page.query_selector("text=/18\\d{2}\\*{4}\\d{4}/"):
                        self._log("检测到已登录手机号，判定登录成功", "success")
                        return True
                except Exception:
                    pass

                # 登录入口检测（真实 class: .header-btn.login）
                el = None
                try:
                    el = self.page.query_selector("div.header-btn.login, .header-btn[class*='login']")
                    if not (el and el.is_visible()):
                        el2 = self.page.query_selector('text=登录/注册')
                        if el2 and el2.is_visible():
                            el = el2
                except Exception:
                    # 页面跳转中查询失败，不计入消失计数
                    time.sleep(2)
                    continue

                if el and el.is_visible():
                    if not seen_entry:
                        seen_entry = True
                        self._log("已定位登录入口，等待您完成登录...", "info")
                    gone_count = 0
                else:
                    # 入口不可见：仅在"见过入口 + 位于 zto.com"时才累计消失次数
                    if seen_entry and on_zto:
                        gone_count += 1
                        if gone_count >= 3:
                            self._log("登录入口已消失（回到中通首页），判定登录成功", "success")
                            return True
                    elif not seen_entry and on_zto:
                        # cookie 已登录场景：入口从未出现。连续多次确认后视为已登录
                        gone_count += 1
                        if gone_count >= 5:
                            self._log("页面始终无登录入口，判定为已登录状态", "success")
                            return True
            except Exception:
                pass
            time.sleep(2)

        self._log("等待登录超时，可手动点击「登录完成」按钮继续", "error")
        return False

    def open_kf_by_url(self, url=None):
        """直接访问带 token 的 kf 客服页地址（提交到浏览器线程执行）"""
        ok, r = self._submit(lambda: self._open_kf_by_url_impl(url), timeout=120)
        return r if ok else False

    def _open_kf_by_url_impl(self, url=None):
        url = url or KF_FULL_URL
        if not url:
            self._log("未配置 KF_FULL_URL 直达地址", "warning")
            return False
        self._log("正在直达访问中通在线客服页...", "info")
        try:
            kf = None
            for p in (self.context.pages if self.context else []):
                if "kf.zto.com" in p.url:
                    kf = p
                    break
            if kf is None:
                kf = self.context.new_page()
            kf.goto(url, wait_until="domcontentloaded", timeout=60000)
            try:
                kf.wait_for_load_state("load", timeout=30000)
            except Exception:
                pass
            self.kf_page = kf
            kf.bring_to_front()
            self._log(f"客服页已打开: {kf.url[:80]}", "success")
            return True
        except Exception as e:
            self._log(f"直达访问客服页失败: {e}", "error")
            return False

    def click_online_service(self):
        """点击官网右侧"在线客服"按钮（提交到浏览器线程执行，作为直达地址的兜底）"""
        ok, r = self._submit(self._click_online_service_impl, timeout=120)
        return r if ok else False

    def _click_online_service_impl(self):
        """点击中通首页右侧悬浮栏的"在线客服"按钮（在新窗口打开 kf.zto.com）。
        注意：kf.zto.com 的 authToken 有时效性，必须通过页面点击让网站实时生成，
        不能直接导航到带旧 token 的 URL。"""
        # 登录后可能停留在个人中心等子页面，先确保回到官网首页再找按钮
        try:
            if "zto.com" in self.page.url and not self.page.url.rstrip("/").startswith(ZTO_URL.rstrip("/")):
                self._log(f"当前在子页面 {self.page.url[:60]}，先返回官网首页...", "info")
                self.page.goto(ZTO_URL, wait_until="domcontentloaded", timeout=60000)
                try:
                    self.page.wait_for_load_state("load", timeout=20000)
                except Exception:
                    pass
                time.sleep(2)
        except Exception as e:
            self._log(f"返回首页失败: {e}", "warning")

        self._log("正在查找首页\"在线客服\"入口...")

        def _click(el) -> bool:
            try:
                el.click(timeout=5000)
            except Exception as e:
                self._log(f"点击失败: {e}", "warning")
                return False
            self._log("已点击\"在线客服\"按钮", "success")

            # 层1: 等待新窗口（同步弹窗即使漏捕获，context.on("page") 也会兜底设置 kf_page）
            try:
                with self.context.expect_page(timeout=4000) as popup_info:
                    pass
                new_page = popup_info.value
                self._log(f"客服页在新窗口打开: {new_page.url[:80]}", "info")
                return True
            except Exception:
                pass

            # 层2: 弹窗被拦截时，从劫持的 window.open 中取回带 token 的地址自行打开
            try:
                popup_url = self.page.evaluate("() => window.__last_popup_url || null")
            except Exception:
                popup_url = None
            if popup_url and "kf.zto.com" in str(popup_url):
                self._log("检测到弹窗被拦截，使用记录的地址直接打开客服页", "warning")
                try:
                    kf = self.context.new_page()
                    kf.goto(popup_url, wait_until="domcontentloaded", timeout=60000)
                    self.kf_page = kf
                    kf.bring_to_front()
                    self._log("客服页已在当前浏览器新标签页打开", "success")
                    return True
                except Exception as e:
                    self._log(f"打开客服页失败: {e}", "error")
                    return False

            # 层3: 当前页直接跳转的情况（switch_to_kf_page 会再兜底检测）
            self._log("未捕获新窗口，尝试按当前页跳转处理", "warning")
            return True

        # 1) 精确文本匹配，避免误点"智能客服"/"合作咨询"等其他入口
        selectors = [
            'text="在线客服"',
            "span:text-is('在线客服')",
            "div:text-is('在线客服')",
            "a:text-is('在线客服')",
            "p:text-is('在线客服')",
            "li:text-is('在线客服')",
        ]
        for sel in selectors:
            try:
                for el in self.page.query_selector_all(sel):
                    try:
                        if el.is_visible():
                            self._log(f"找到在线客服按钮 ({sel})")
                            return _click(el)
                    except Exception:
                        continue
            except Exception:
                continue

        # 2) 兜底：遍历可见元素找精确文本"在线客服"
        self._log("精确选择器未命中，遍历页面元素查找...", "warning")
        try:
            for el in self.page.query_selector_all("a, button, span, div, p, li"):
                try:
                    if (el.inner_text() or "").strip() == "在线客服" and el.is_visible():
                        self._log("通过文本遍历找到在线客服按钮")
                        return _click(el)
                except Exception:
                    continue
        except Exception as e:
            self._log(f"遍历元素失败: {e}", "error")

        self._log("未找到\"在线客服\"按钮，请手动点击进入客服页", "warning")
        return False

    def switch_to_kf_page(self):
        """切换到客服页面（提交到浏览器线程执行）"""
        ok, r = self._submit(self._switch_to_kf_page_impl, timeout=60)
        return r if ok else False

    def _switch_to_kf_page_impl(self):
        """切换到客服页面"""
        self._log("正在切换到客服页面...")

        # 等待新页面/标签页打开
        timeout = 20
        start = time.time()
        while time.time() - start < timeout:
            try:
                pages = self.context.pages if self.context else self.browser.contexts[0].pages
                for p in pages:
                    if KF_URL in p.url or "kf.zto.com" in p.url:
                        self.kf_page = p
                        self.kf_page.bring_to_front()
                        self._log(f"已切换到客服页面: {p.url[:80]}", "success")
                        return True
            except Exception:
                pass

            # 如果当前页面已经跳转
            current_url = self.page.url
            if "kf.zto.com" in current_url:
                self.kf_page = self.page
                self._log(f"当前页面已跳转到客服页: {current_url}", "success")
                return True

            time.sleep(1)

        self._log("未检测到客服页面，请在浏览器中手动打开", "warning")
        return False

    def enable_chat_input(self):
        """检测并激活客服聊天输入框（提交到浏览器线程执行）"""
        ok, r = self._submit(self._enable_chat_input_impl, timeout=60)
        return r if ok else False

    def _enable_chat_input_impl(self):
        """
        点击输入框使其可以输入消息。
        """
        if not self.kf_page:
            self._log("客服页面未就绪", "error")
            return False

        self._log("正在检测聊天输入框...")

        # 输入框选择器列表（kf.zto.com 输入框 placeholder 为"请输入..."，优先高精度匹配）
        input_selectors = [
            "[placeholder*='请输入']",
            "textarea",
            "[contenteditable='true']",
            "div[role='textbox']",
            "input[type='text']",
            ".chat-input",
            ".msg-input",
            ".input-area textarea",
            "#chat-input",
            ".send-message-input",
            ".el-input__inner",
            ".el-textarea__inner",
            ".editable",
            "[placeholder*='输入']",
            "[placeholder*='消息']",
            "[class*='chat-input']",
            "[class*='message-input']",
        ]

        for sel in input_selectors:
            try:
                el = self.kf_page.query_selector(sel)
                if el and el.is_visible():
                    self._log(f"找到输入框: {sel}")
                    el.click()
                    time.sleep(0.5)
                    self._log("输入框已激活，可以开始发送消息", "success")
                    return True
            except Exception:
                continue

        self._log("未找到聊天输入框，请在浏览器中手动点击输入框", "warning")
        return False

    def send_to_chat(self, text: str):
        """向客服聊天框发送消息（提交到浏览器线程执行）"""
        ok, r = self._submit(lambda: self._send_to_chat_impl(text), timeout=90)
        return r if ok else False

    def _send_to_chat_impl(self, text: str):
        """
        向客服聊天框发送消息。
        实测 kf.zto.com 结构：输入框为 <textarea id="sendText" class="send-textare" maxlength="200">；
        Enter 会触发页面导航（禁止用作发送）；"送"按钮为动态渲染，需前端框架状态同步后才激活。
        """
        if not self.kf_page:
            self._log("客服页面未就绪，无法发送消息", "error")
            return False

        self._log(f"正在发送消息: {text[:50]}...", "info")

        # 1. 定位输入框（实测真实 id: #sendText）
        input_el = None
        for sel in ["#sendText", "textarea.send-textare",
                    "textarea[placeholder*='请输入']", "textarea"]:
            try:
                cand = self.kf_page.query_selector(sel)
                if cand and cand.is_visible():
                    input_el = cand
                    break
            except Exception:
                continue
        if input_el is None:
            self._log("发送消息失败：未找到输入框(#sendText)", "error")
            return False

        try:
            # 2. maxlength=200 截断保护（浏览器会静默截断超长输入）
            send_text = text
            max_len = input_el.get_attribute("maxlength")
            if max_len and len(send_text) > int(max_len):
                send_text = send_text[:int(max_len)]
                self._log(f"AI 回复超过 {max_len} 字，已截断（可在 Dify 后台让回复更简短）", "warning")

            # 3. 键盘级清空 + 逐字输入（Ctrl+A/Delete 比 fill 可靠，不破坏前端框架状态）
            input_el.click()
            time.sleep(0.2)
            self.kf_page.keyboard.press("Control+A")
            self.kf_page.keyboard.press("Delete")
            time.sleep(0.2)
            input_el.type(send_text, delay=30)
            time.sleep(0.3)

            # 4. 原生 value setter + input 事件同步前端框架状态（激活"送"按钮）
            self._sync_send_text(send_text)
            self._log("消息已输入", "success")

            # 5. 多策略点击"送"按钮（坐标真人点击 → Playwright 点击 → JS 点击），验证清空才算成功
            for attempt in range(3):
                info = self._find_send_btn_state()
                if not info.get("found"):
                    self._log(f"未找到可见的\"送\"按钮（输入框值: {str(info.get('taValue', ''))[:30]}）", "warning")
                    self._sync_send_text(send_text)
                    time.sleep(0.5)
                    continue
                if attempt == 0:
                    self._log(f"发送按钮诊断: <{info.get('tag')} class={info.get('cls')}> "
                              f"disabled={info.get('disabled')}", "info")

                # 策略1: 坐标级真实点击（最接近真人操作，isTrusted=true）
                try:
                    r = info["rect"]
                    self.kf_page.mouse.move(r["x"], r["y"], steps=5)
                    self.kf_page.mouse.click(r["x"], r["y"])
                except Exception:
                    pass
                time.sleep(1.2)
                if self._sendbox_cleared(input_el):
                    self._log("消息已发送", "success")
                    return True

                # 策略2: Playwright 元素点击（自动等待可点击状态）
                try:
                    self.kf_page.get_by_text("送", exact=True).first.click(timeout=2000, force=True)
                except Exception:
                    pass
                time.sleep(1.2)
                if self._sendbox_cleared(input_el):
                    self._log("消息已发送", "success")
                    return True

                # 策略3: JS DOM 点击
                self._js_click_send()
                time.sleep(1.2)
                if self._sendbox_cleared(input_el):
                    self._log("消息已发送", "success")
                    return True

                self._log(f"发送未生效（输入框未清空），重试 {attempt + 1}/3...", "warning")
                self._sync_send_text(send_text)
                time.sleep(0.5)

            self._log("消息发送失败：三种点击策略均未生效", "error")
            return False
        except Exception as e:
            self._log(f"发送消息异常: {e}", "error")
            return False

    def _find_send_btn_state(self):
        """查找"送"按钮并返回诊断状态（tag/class/disabled/中心坐标）"""
        try:
            return self.kf_page.evaluate("""() => {
                let btn = null;
                const cands = document.querySelectorAll('button, label, a, span, div, input');
                for (const el of cands) {
                    const t = (el.innerText || el.value || '').trim();
                    if ((t === '送' || t === '发送') && el.offsetWidth > 0) {
                        if ((el.className || '').toString().includes('over')) continue;
                        btn = el.closest('button') || el;
                        break;
                    }
                }
                const ta = document.querySelector('#sendText');
                if (!btn) return {found: false, taValue: ta ? ta.value : null};
                const r = btn.getBoundingClientRect();
                return {found: true, tag: btn.tagName,
                        cls: String(btn.className).slice(0, 60),
                        disabled: !!btn.disabled,
                        html: btn.outerHTML.slice(0, 150),
                        rect: {x: r.x + r.width / 2, y: r.y + r.height / 2}};
            }""")
        except Exception:
            return {"found": False}

    def _sendbox_cleared(self, input_el) -> bool:
        """输入框已清空 = 消息真正发出"""
        try:
            return not input_el.evaluate("el => (el.value || '').trim()")
        except Exception:
            return False

    def _sync_send_text(self, text: str):
        """用原生 value setter + input 事件把文本同步进 #sendText，激活前端框架的发送按钮"""
        try:
            self.kf_page.evaluate("""(txt) => {
                const el = document.querySelector('#sendText');
                if (!el) return;
                el.focus();
                const setter = Object.getOwnPropertyDescriptor(
                    window.HTMLTextAreaElement.prototype, 'value').set;
                setter.call(el, txt);
                el.dispatchEvent(new Event('input', {bubbles: true}));
                el.dispatchEvent(new Event('change', {bubbles: true}));
            }""", text)
        except Exception:
            pass

    def _js_click_send(self):
        """JS 点击"送"按钮（精确匹配文字，排除"结束会话"）"""
        try:
            return self.kf_page.evaluate("""() => {
                const candidates = document.querySelectorAll('button, label, a, span, div');
                for (const el of candidates) {
                    const t = (el.innerText || '').trim();
                    if ((t === '送' || t === '发送') && el.offsetWidth > 0) {
                        if (el.closest('.over') || (el.className || '').includes('over')) continue;
                        const btn = el.closest('button') || el;
                        if (btn.disabled) continue;
                        btn.click();
                        return true;
                    }
                }
                return false;
            }""")
        except Exception:
            return False

    def get_latest_chat_messages(self, known_count=0) -> list:
        """获取客服聊天区域最新消息列表（提交到浏览器线程执行）"""
        ok, r = self._submit(self._get_latest_chat_messages_impl, timeout=60)
        return r if ok else []

    def _get_latest_chat_messages_impl(self, known_count=0) -> list:
        """
        获取客服聊天区域的最新消息列表。
        返回格式: [{"role": "user/service", "content": "..."}]
        """
        if not self.kf_page:
            return []

        messages = []

        # 消息容器选择器
        msg_selectors = [
            ".chat-messages .message",
            ".message-list .message",
            ".chat-content .message",
            ".msg-item",
            ".chat-msg",
            ".message-item",
            ".el-message",
            ".chat-record",
            "[class*='message']",
            "[class*='chat-msg']",
            "[class*='msg-item']",
            ".content",
            ".chat-container",
            "li",
        ]

        role_selectors = {
            "user": [
                ".user-message", ".self-message", ".right",
                "[class*='user']", "[class*='self']", "[class*='right']",
                "[class*='send']", "[class*='my']"
            ],
            "service": [
                ".service-message", ".other-message", ".left",
                "[class*='service']", "[class*='other']", "[class*='left']",
                "[class*='receive']", "[class*='kf']"
            ]
        }

        for sel in msg_selectors:
            try:
                elements = self.kf_page.query_selector_all(sel)
                if len(elements) > 0:
                    for el in elements:
                        try:
                            text = el.inner_text().strip()
                            if not text:
                                continue

                            # 判断角色
                            class_attr = el.get_attribute("class") or ""
                            role = "service"  # 默认客服
                            for r, sels in role_selectors.items():
                                for rs in sels:
                                    if rs in class_attr:
                                        role = r
                                        break

                            messages.append({"role": role, "content": text})
                        except Exception:
                            continue
                    break
            except Exception:
                continue

        return messages

    def wait_for_new_kf_message(self, current_count=0, last_text=None, exclude_texts=None, timeout=30):
        """等待客服发送新消息（提交到浏览器线程执行）。返回新消息内容，超时返回 None。"""
        ok, r = self._submit(
            lambda: self._wait_for_new_kf_message_impl(current_count, last_text, exclude_texts, timeout),
            timeout=timeout + 60)
        return r if ok else None

    def _wait_for_new_kf_message_impl(self, current_count=0, last_text=None, exclude_texts=None, timeout=30):
        """
        等待客服发送新消息。
        优先按"内容与 last_text 不同"判定新消息（避免把欢迎语等旧消息误判为回复），
        exclude_texts 中的内容（如刚发送的用户消息）会被跳过。
        last_text 为 None 时退回数量判定。
        返回新消息内容，超时返回 None。
        """
        exclude = {t.strip() for t in (exclude_texts or []) if t and t.strip()}
        start = time.time()
        while time.time() - start < timeout:
            if self._stop:
                return None
            try:
                messages = self._get_latest_chat_messages_impl()
                if last_text is not None:
                    # 从最新往前找第一条有效客服消息：
                    # 跳过空消息和刚发送的内容，与发送前最后一条客服消息比对
                    for msg in reversed(messages):
                        if msg["role"] != "service":
                            continue
                        content = msg["content"].strip()
                        if not content or content in exclude:
                            continue
                        if content != last_text.strip():
                            self._log(f"客服新消息: {content[:60]}...", "info")
                            return content
                        break  # 最新有效客服消息仍是发送前的旧消息，继续等
                elif len(messages) > current_count:
                    new_msgs = messages[current_count:]
                    for msg in new_msgs:
                        if msg["role"] == "service":
                            self._log(f"客服新消息: {msg['content'][:60]}...", "info")
                            return msg["content"]
            except Exception:
                pass
            time.sleep(1.5)
        return None

    def stop(self):
        """停止浏览器（提交到浏览器线程执行）"""
        self._stop = True
        try:
            self._submit(self._stop_impl, timeout=15)
        except Exception:
            pass

    def _stop_impl(self):
        """释放浏览器资源"""
        try:
            if self.browser:
                self.browser.close()
        except Exception:
            pass
        try:
            if self.playwright:
                self.playwright.stop()
        except Exception:
            pass


# ============================================================
# 第三部分：Tkinter GUI
# ============================================================

class ZTOBotGUI:
    """Tkinter 图形界面"""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("中通快递投诉机器人 🤖")
        self.root.geometry("900x700")
        self.root.minsize(700, 500)

        # 状态变量
        self.browser_ready = False
        self.chat_ready = False
        self.bot_thread = None
        self.dify_client = DifyClient()
        self.browser_ctrl = None
        self.gui_queue = Queue()
        self.conversation_history = []  # 对话历史
        self.auto_reply_on = False      # AI 自动回复开关（真实状态，控制 AI 回复是否自动发送）
        self.MAX_AUTO_ROUNDS = 30       # 自动回复最大轮数，防止无限循环
        self.monitor_running = False    # 客服消息监听线程运行标志
        self._closing = False           # 程序退出标志
        self.last_service_text = None   # 最后处理的客服消息（监听基准，防止重复分析）
        self.last_sent_text = None      # 最近发送的消息（防止把自己的消息当客服回复）
        self.auto_rounds = 0            # 自动回复已发送轮数
        self._kf_flow_started = False   # 防止"进入客服页"流程重复触发

        # 设置主题色
        self.bg_color = "#f0f0f0"
        self.primary_color = "#2196F3"
        self.success_color = "#4CAF50"
        self.warning_color = "#FF9800"
        self.error_color = "#f44336"

        self.root.configure(bg=self.bg_color)

        self._build_ui()

        # 启动队列检查
        self._check_queue()

        self._log("系统就绪，点击「启动浏览器」开始")

    def _build_ui(self):
        """构建界面"""
        # --- 顶部标题 ---
        header = tk.Frame(self.root, bg=self.primary_color, height=50)
        header.pack(fill=tk.X)
        header.pack_propagate(False)
        tk.Label(
            header, text="中通快递投诉机器人", bg=self.primary_color,
            fg="white", font=("微软雅黑", 16, "bold")
        ).pack(side=tk.LEFT, padx=15, pady=8)

        # --- 状态栏 ---
        self.status_frame = tk.Frame(self.root, bg=self.bg_color, height=35)
        self.status_frame.pack(fill=tk.X, padx=10, pady=(5, 0))
        self.status_frame.pack_propagate(False)

        self.status_label = tk.Label(
            self.status_frame, text="● 等待启动", fg="#888",
            bg=self.bg_color, font=("微软雅黑", 10)
        )
        self.status_label.pack(side=tk.LEFT, padx=5)

        self.conversation_id_label = tk.Label(
            self.status_frame, text="", fg="#888",
            bg=self.bg_color, font=("微软雅黑", 9)
        )
        self.conversation_id_label.pack(side=tk.RIGHT, padx=5)

        # --- 聊天日志区域 ---
        log_frame = tk.Frame(self.root, bg="white", relief=tk.GROOVE, bd=1)
        log_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=5)

        self.log_area = scrolledtext.ScrolledText(
            log_frame, wrap=tk.WORD, font=("微软雅黑", 10),
            bg="#1e1e1e", fg="#d4d4d4", state=tk.DISABLED,
            height=20, padx=10, pady=10
        )
        self.log_area.pack(fill=tk.BOTH, expand=True)

        # 配置日志标签样式
        self.log_area.tag_config("info", foreground="#d4d4d4")
        self.log_area.tag_config("success", foreground="#4CAF50")
        self.log_area.tag_config("warning", foreground="#FF9800")
        self.log_area.tag_config("error", foreground="#f44336")
        self.log_area.tag_config("user", foreground="#61afef")
        self.log_area.tag_config("service", foreground="#e5c07b")
        self.log_area.tag_config("ai", foreground="#98c379")
        self.log_area.tag_config("system", foreground="#888888")
        self.log_area.tag_config("timestamp", foreground="#555555")

        # --- 底部控制区 ---
        control_frame = tk.Frame(self.root, bg=self.bg_color)
        control_frame.pack(fill=tk.X, padx=10, pady=(0, 10))

        # 按钮行
        btn_frame = tk.Frame(control_frame, bg=self.bg_color)
        btn_frame.pack(fill=tk.X, pady=(0, 5))

        self.start_btn = self._create_button(
            btn_frame, "🚀 启动浏览器", self._start_browser,
            self.primary_color, side=tk.LEFT, padx=5
        )
        
        self.login_done_btn = self._create_button(
            btn_frame, "✅ 登录完成", self._confirm_login,
            "#4CAF50", side=tk.LEFT, padx=5
        )
        self.login_done_btn.config(state=tk.DISABLED)
        
        self.enter_kf_btn = self._create_button(
            btn_frame, "🔄 进入客服页", self._enter_kf_page,
            "#FF9800", side=tk.LEFT, padx=5
        )
        self.enter_kf_btn.config(state=tk.DISABLED)

        self.test_btn = self._create_button(
            btn_frame, "📤 发送测试消息", self._send_test_message,
            "#2196F3", side=tk.LEFT, padx=5
        )
        self.test_btn.config(state=tk.DISABLED)

        self.auto_btn = self._create_button(
            btn_frame, "🤖 AI 自动回复", self._toggle_auto_reply,
            "#9C27B0", side=tk.LEFT, padx=5
        )
        self.auto_btn.config(state=tk.DISABLED)

        self.clear_btn = self._create_button(
            btn_frame, "🗑 清空日志", self._clear_log,
            "#888", side=tk.RIGHT, padx=5
        )

        # 输入行
        input_frame = tk.Frame(control_frame, bg=self.bg_color)
        input_frame.pack(fill=tk.X)

        self.input_var = tk.StringVar()
        self.input_entry = tk.Entry(
            input_frame, textvariable=self.input_var,
            font=("微软雅黑", 11), relief=tk.GROOVE, bd=1
        )
        self.input_entry.pack(side=tk.LEFT, fill=tk.X, expand=True, ipady=5)
        self.input_entry.bind("<Return>", lambda e: self._send_manual_message())
        self.input_entry.config(state=tk.DISABLED)

        self.send_btn = self._create_button(
            input_frame, "发送", self._send_manual_message,
            self.primary_color, side=tk.RIGHT, padx=(5, 0)
        )
        self.send_btn.config(state=tk.DISABLED)

    def _create_button(self, parent, text, command, color, side=tk.LEFT, padx=0):
        """创建统一风格的按钮"""
        btn = tk.Button(
            parent, text=text, command=command,
            font=("微软雅黑", 10), bg=color, fg="white",
            relief=tk.FLAT, padx=12, pady=5, cursor="hand2",
            activebackground=color, activeforeground="white"
        )
        btn.pack(side=side, padx=padx)
        return btn

    def _log(self, msg: str, level="info"):
        """向日志区域添加消息"""
        def _add():
            self.log_area.config(state=tk.NORMAL)
            timestamp = datetime.now().strftime("%H:%M:%S")
            self.log_area.insert(tk.END, f"[{timestamp}] ", "timestamp")
            self.log_area.insert(tk.END, f"{msg}\n", level)
            self.log_area.see(tk.END)
            self.log_area.config(state=tk.DISABLED)
        self.root.after(0, _add)

    def _clear_log(self):
        """清空日志，并重置对话历史与监听基准（开始全新投诉对话）"""
        self.log_area.config(state=tk.NORMAL)
        self.log_area.delete(1.0, tk.END)
        self.log_area.config(state=tk.DISABLED)
        self.conversation_history = []
        self.last_service_text = None
        self.last_sent_text = None
        self.auto_rounds = 0
        if self.dify_client:
            self.dify_client.conversation_id = None
        self._log("🗑 已清空日志与对话历史（监听继续运行）", "info")

    def _update_status(self, text: str, color: str = "#888"):
        """更新状态栏"""
        self.status_label.config(text=f"● {text}", fg=color)

    def _check_queue(self):
        """定期检查 GUI 队列中的消息"""
        try:
            while True:
                item = self.gui_queue.get_nowait()
                msg_type = item.get("type", "log")

                if msg_type == "log":
                    self._log(item["message"], item.get("level", "info"))
                elif msg_type == "status":
                    self._update_status(item["message"], item.get("color", "#888"))
                elif msg_type == "browser_ready":
                    self.browser_ready = True
                    self.login_done_btn.config(state=tk.NORMAL)
                    self._update_status("浏览器就绪 - 请登录中通", self.warning_color)
                elif msg_type == "login_detected":
                    self._log("✅ 检测到登录成功，自动进入客服页...", "success")
                    self.login_done_btn.config(state=tk.DISABLED)
                    self._enter_kf_page()
                elif msg_type == "kf_flow_failed":
                    # 允许用户手动处理后再点「进入客服页」重试
                    self._kf_flow_started = False
                    self.enter_kf_btn.config(state=tk.NORMAL)
                    self._update_status("进入客服页失败，可重试", self.error_color)
                elif msg_type == "chat_ready":
                    self.chat_ready = True
                    self.test_btn.config(state=tk.NORMAL)
                    self.auto_btn.config(state=tk.NORMAL)
                    self.input_entry.config(state=tk.NORMAL)
                    self.send_btn.config(state=tk.NORMAL)
                    self._log("💬 客服页面已就绪，可以开始对话", "success")
                elif msg_type == "ai_response":
                    self._log(f"🤖 AI 回复: {item['message']}", "ai")
                elif msg_type == "conversation_id":
                    cid = item["message"]
                    self.conversation_id_label.config(
                        text=f"会话ID: {cid[:16]}..." if len(cid) > 16 else f"会话ID: {cid}"
                    )
        except Exception:
            pass
        self.root.after(200, self._check_queue)

    def _start_browser(self):
        """启动浏览器线程"""
        if self.bot_thread and self.bot_thread.is_alive():
            self._log("浏览器已在运行中", "warning")
            return

        self.start_btn.config(state=tk.DISABLED, text="⏳ 启动中...")
        self._update_status("正在启动浏览器...", self.warning_color)

        # 重置流程状态，允许本轮重新走完整流程
        self._kf_flow_started = False
        self.chat_ready = False
        self.conversation_history = []
        self.monitor_running = False
        self.last_service_text = None
        self.last_sent_text = None
        self.auto_rounds = 0

        self.gui_queue = Queue()
        self.browser_ctrl = ZTOBrowserController(self.gui_queue)

        self.bot_thread = threading.Thread(target=self._browser_worker, daemon=True)
        self.bot_thread.start()

    def _browser_worker(self):
        """浏览器工作线程"""
        try:
            # 1. 启动浏览器并打开中通首页
            self.browser_ctrl.launch()
            self.gui_queue.put({"type": "browser_ready", "message": ""})

            # 2. 后台自动检测登录状态，登录成功后自动进入客服页
            #    （用户也可随时点「登录完成」按钮手动确认）
            def wait_login():
                ok = self.browser_ctrl.wait_for_login(timeout_minutes=10)
                if ok and not self.browser_ctrl._stop:
                    self.gui_queue.put({"type": "login_detected", "message": ""})
                else:
                    self.gui_queue.put({"type": "log",
                                        "message": "⚠️ 未检测到登录，请登录后手动点击「登录完成」",
                                        "level": "warning"})

            threading.Thread(target=wait_login, daemon=True).start()

        except Exception as e:
            self.gui_queue.put({"type": "log", "message": f"❌ 浏览器错误: {e}", "level": "error"})
            self.gui_queue.put({"type": "status", "message": "浏览器出错", "color": self.error_color})

    def _confirm_login(self):
        """用户手动确认登录完成"""
        if not self.browser_ctrl:
            self._log("⚠️ 浏览器未启动", "warning")
            return

        # 置位后自动检测线程会立即通过，这里直接触发进入客服页流程
        self.browser_ctrl.login_confirmed = True
        self.login_done_btn.config(state=tk.DISABLED)
        self._log("✅ 用户确认登录完成", "success")
        self._enter_kf_page()

    def _enter_kf_page(self):
        """点击首页"在线客服"并进入客服聊天页（防重复触发）"""
        if not self.browser_ctrl:
            self._log("⚠️ 浏览器未启动", "warning")
            return
        if self._kf_flow_started:
            return
        self._kf_flow_started = True

        self._update_status("正在进入客服页面...", self.warning_color)
        self.enter_kf_btn.config(state=tk.DISABLED)

        def enter_kf_worker():
            try:
                # 1. 优先：直达访问配置的 kf 客服页地址（绕过官网点击弹窗链路）
                opened = self.browser_ctrl.open_kf_by_url()

                # 2. 兜底：点击官网首页"在线客服"按钮（token 由网站实时生成）
                if not opened:
                    self.gui_queue.put({"type": "log",
                                        "message": "直达地址未成功，尝试点击官网\"在线客服\"按钮...",
                                        "level": "warning"})
                    clicked = self.browser_ctrl.click_online_service()
                    if not clicked:
                        self.gui_queue.put({"type": "log",
                                            "message": "⚠️ 未找到在线客服按钮，请在浏览器中手动点击后重试",
                                            "level": "warning"})
                        self.gui_queue.put({"type": "kf_flow_failed", "message": ""})
                        return
                    switched = self.browser_ctrl.switch_to_kf_page()
                    if not switched:
                        self.gui_queue.put({"type": "log",
                                            "message": "⚠️ 未检测到客服页面，若已手动打开请重试",
                                            "level": "warning"})
                        self.gui_queue.put({"type": "kf_flow_failed", "message": ""})
                        return

                # 3. 激活输入框并就绪
                self.browser_ctrl.enable_chat_input()

                # 4. 主动读取客服页已有消息（欢迎语等），记录并显示
                #    —— 否则只有发送第一条消息后才能感知到客服消息
                try:
                    existing = self.browser_ctrl.get_latest_chat_messages()
                    service_msgs = [m for m in existing
                                    if m.get("role") == "service" and m.get("content", "").strip()]
                    if service_msgs:
                        self.gui_queue.put({"type": "log",
                                            "message": f"📋 检测到客服已有 {len(service_msgs)} 条消息:",
                                            "level": "info"})
                        for m in service_msgs:
                            preview = m["content"][:60] + ("..." if len(m["content"]) > 60 else "")
                            self.gui_queue.put({"type": "log",
                                                "message": f"   💬 {preview}",
                                                "level": "service"})
                            # 记入对话历史（去重：GUI 历史里可能已有首条欢迎语）
                            if not any(h.get("role") == "service" and h.get("content") == m["content"]
                                       for h in self.conversation_history):
                                self.conversation_history.append({"role": "service",
                                                                  "content": m["content"]})
                    else:
                        self.gui_queue.put({"type": "log",
                                            "message": "暂未检测到客服消息（等待客服回复后将自动识别）",
                                            "level": "info"})
                except Exception as e:
                    self.gui_queue.put({"type": "log",
                                        "message": f"读取已有消息失败（不影响后续对话）: {e}",
                                        "level": "warning"})

                self.gui_queue.put({"type": "chat_ready", "message": ""})
                self.gui_queue.put({"type": "status", "message": "客服页面就绪", "color": self.success_color})
                # 页面就绪即自动启动客服消息监听（无需手动发送测试消息）
                self._start_monitor()

            except Exception as e:
                self.gui_queue.put({"type": "log", "message": f"❌ 进入客服页错误: {e}", "level": "error"})
                self.gui_queue.put({"type": "kf_flow_failed", "message": ""})

        threading.Thread(target=enter_kf_worker, daemon=True).start()

    def _send_test_message(self):
        """发送测试消息：优先发送输入框中输入的内容，输入框为空时才用默认测试消息"""
        text = self.input_var.get().strip()
        if text:
            self.input_var.set("")
            self._log("发送输入框中的内容...", "info")
        else:
            text = TEST_MESSAGE
            self._log("输入框为空，发送默认测试消息...", "info")
        self._send_message(text)

    def _send_manual_message(self):
        """发送手动输入的消息"""
        text = self.input_var.get().strip()
        if not text:
            return
        self.input_var.set("")
        self._send_message(text)

    def _send_message(self, text: str):
        """发送一条消息到客服（纯发送；之后的客服回复由监听线程自动接管分析）"""
        if not self.browser_ctrl or not self.browser_ctrl.kf_page:
            self._log("⚠️ 客服页面未就绪，请先启动浏览器", "warning")
            return

        self._log(f"👤 发送: {text}", "user")
        self.conversation_history.append({"role": "user", "content": text})
        self.last_sent_text = text

        def send_worker():
            # 发送前记录最后一条客服消息作为监听基准（防止把旧消息当新回复）
            try:
                msgs = self.browser_ctrl.get_latest_chat_messages()
                for m in reversed(msgs):
                    c = (m.get("content") or "").strip()
                    if m.get("role") == "service" and c:
                        self.last_service_text = c
                        break
            except Exception:
                pass
            if not self.browser_ctrl.send_to_chat(text):
                self.gui_queue.put({"type": "log", "message": "❌ 消息发送失败", "level": "error"})

        threading.Thread(target=send_worker, daemon=True).start()

    def _start_monitor(self):
        """启动客服消息监听（幂等）：客服页面就绪后自动运行，
        客服回复 → 抓取文字 → Dify 分析 → 自动发送 AI 回复 → 继续监听"""
        if self.monitor_running:
            return
        self.monitor_running = True

        def init_worker():
            # 基准 = 当前最后一条客服消息（欢迎语等已有消息不触发分析）
            try:
                msgs = self.browser_ctrl.get_latest_chat_messages()
                for m in reversed(msgs):
                    c = (m.get("content") or "").strip()
                    if m.get("role") == "service" and c:
                        self.last_service_text = c
                        break
            except Exception:
                pass
            self.gui_queue.put({"type": "log",
                                "message": "👀 客服消息监听已启动：客服回复将自动交给 Dify 分析并回复",
                                "level": "success"})
            threading.Thread(target=self._monitor_worker, daemon=True,
                             name="ChatMonitor").start()

        threading.Thread(target=init_worker, daemon=True).start()

    def _monitor_worker(self):
        """监听循环：每2秒检查客服新消息 → Dify 分析 → 自动回复（来回聊直到有结果/停止）"""
        while self.monitor_running and not self._closing:
            time.sleep(2)
            if not (self.browser_ctrl and self.browser_ctrl.kf_page):
                continue
            try:
                msgs = self.browser_ctrl.get_latest_chat_messages()
            except Exception:
                continue

            # 取最新一条非空客服消息
            latest = None
            for m in reversed(msgs):
                c = (m.get("content") or "").strip()
                if m.get("role") == "service" and c:
                    latest = c
                    break
            if latest is None:
                continue

            # 与基准比对：相同 = 无新消息；与刚发送内容相同 = 自己的消息被误判为客服
            base = (self.last_service_text or "").strip()
            if latest == base or latest == (self.last_sent_text or "").strip():
                continue

            # === 检测到客服新回复 ===
            self.last_service_text = latest
            preview = latest[:80] + ("..." if len(latest) > 80 else "")
            self.gui_queue.put({"type": "log", "message": f"💬 客服回复: {preview}", "level": "service"})
            self.conversation_history.append({"role": "service", "content": latest})

            if not self.auto_reply_on:
                self.gui_queue.put({"type": "log",
                                    "message": "（AI 自动回复未开启，已记录；开启后将自动回复）",
                                    "level": "warning"})
                continue
            if self.auto_rounds >= self.MAX_AUTO_ROUNDS:
                self.gui_queue.put({"type": "log",
                                    "message": f"⏹ 已达自动回复最大轮数({self.MAX_AUTO_ROUNDS})，请手动处理或点「清空」重置",
                                    "level": "warning"})
                continue

            # Dify 分析客服回复
            self.gui_queue.put({"type": "log", "message": "🤖 正在请求 Dify AI 分析...", "level": "info"})
            self.gui_queue.put({"type": "status", "message": "AI 分析中...", "color": self.warning_color})
            result = self.dify_client.send_message(latest, history=self.conversation_history[:-1])
            if result["error"]:
                self.gui_queue.put({"type": "log", "message": f"❌ Dify 错误: {result['error']}", "level": "error"})
                self.gui_queue.put({"type": "status", "message": "AI 分析出错", "color": self.error_color})
                continue

            ai_reply = result["answer"]
            self.gui_queue.put({"type": "ai_response", "message": ai_reply})
            self.gui_queue.put({"type": "conversation_id", "message": result["conversation_id"] or ""})
            self.gui_queue.put({"type": "status", "message": "AI 分析完成", "color": self.success_color})
            self.conversation_history.append({"role": "assistant", "content": ai_reply})

            # 自动发送 AI 回复，进入下一轮来回
            self.auto_rounds += 1
            self.gui_queue.put({"type": "log",
                                "message": f"📤 自动发送 AI 回复（第{self.auto_rounds}轮）...", "level": "info"})
            self._send_message(ai_reply)

    def _toggle_auto_reply(self):
        """切换 AI 自动回复模式（用真实状态判断，按钮文字含"自动回复"不可靠）"""
        if not self.auto_reply_on:
            self.auto_reply_on = True
            self.auto_rounds = 0  # 重新开启 = 新一轮对话
            self.auto_btn.config(text="⏹ 停止自动回复", bg=self.error_color)
            self._log("🤖 AI 自动回复已开启", "success")
            self._start_monitor()
        else:
            self.auto_reply_on = False
            self.auto_btn.config(text="🤖 AI 自动回复", bg=self.success_color)
            self._log("🤖 AI 自动回复已关闭", "warning")

    def run(self):
        """运行 GUI"""
        self.root.mainloop()

    def stop(self):
        """停止所有操作"""
        self._closing = True
        self.monitor_running = False
        if self.browser_ctrl:
            self.browser_ctrl.stop()


# ============================================================
# 主入口
# ============================================================

def main():
    print("=" * 60)
    print("中通快递投诉机器人")
    print(f"Dify API: {DIFY_API_BASE}")
    print(f"浏览器: {BROWSER_CHANNEL}")
    print("=" * 60)
    print()

    gui = ZTOBotGUI()
    try:
        gui.run()
    except KeyboardInterrupt:
        print("\n正在退出...")
    finally:
        gui.stop()
        print("已退出")


if __name__ == "__main__":
    main()