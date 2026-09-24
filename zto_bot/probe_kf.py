# -*- coding: utf-8 -*-
"""临时探测5：实测 kf.zto.com 聊天输入框与发送按钮的真实结构和可用发送方式，用完即删"""
import json
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    b = p.chromium.launch(
        channel="msedge", headless=False,
        ignore_default_args=["--enable-automation"],
        args=["--start-maximized", "--disable-blink-features=AutomationControlled"])
    ctx = b.new_context(no_viewport=True)
    ctx.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined});")
    pg = ctx.new_page()
    pg.goto("https://kf.zto.com/", wait_until="domcontentloaded", timeout=60000)
    pg.wait_for_timeout(8000)
    print("URL:", pg.url[:80])
    print("TITLE:", pg.title())

    # 1. 输入框结构
    info = pg.evaluate("""() => {
        const out = {};
        const cands = {
            textarea: document.querySelector('textarea'),
            ph: document.querySelector('[placeholder*="请输入"]'),
            ce: document.querySelector('[contenteditable="true"]'),
            textbox: document.querySelector('[role="textbox"]'),
        };
        for (const [k, el] of Object.entries(cands)) {
            if (el) out[k] = {
                tag: el.tagName, cls: String(el.className).slice(0, 120),
                placeholder: el.getAttribute ? el.getAttribute('placeholder') : null,
                html: el.outerHTML.slice(0, 250)
            };
        }
        // 发送按钮
        const btns = [];
        document.querySelectorAll('button, [class*="send"] , .btn').forEach(el => {
            const t = (el.innerText || '').trim();
            if (t && t.length <= 4) btns.push({tag: el.tagName, text: t, cls: String(el.className).slice(0, 100),
                disabled: el.disabled !== undefined ? el.disabled : null, html: el.outerHTML.slice(0, 150)});
        });
        out.buttons = btns.slice(0, 15);
        return out;
    }""")
    print("\n===== 输入框与按钮结构 =====")
    print(json.dumps(info, ensure_ascii=False, indent=1)[:2500])

    # 2. 找到输入框并测试输入方式
    box = pg.query_selector('textarea') or pg.query_selector('[placeholder*="请输入"]') \
        or pg.query_selector('[contenteditable="true"]')
    if not box:
        print("\n!! 未找到输入框")
        b.close()
        raise SystemExit

    print("\n输入框 tag:", box.evaluate("el => el.tagName"))

    # 方式A：click + type
    box.click()
    pg.keyboard.press("Control+A")
    pg.keyboard.press("Delete")
    box.type("你好，测试消息", delay=30)
    pg.wait_for_timeout(1000)
    state1 = box.evaluate("""el => {
        const tag = el.tagName.toLowerCase();
        const val = (tag === 'input' || tag === 'textarea') ? el.value : el.innerText;
        // 找"送"按钮状态
        let btn = null;
        document.querySelectorAll('button, span, div').forEach(e => {
            if ((e.innerText || '').trim() === '送' && e.offsetWidth) btn = e;
        });
        let btnInfo = null;
        if (btn) {
            const realBtn = btn.closest('button') || btn;
            btnInfo = {tag: realBtn.tagName, cls: String(realBtn.className).slice(0, 100),
                       disabled: realBtn.disabled !== undefined ? realBtn.disabled : null};
        }
        return {value: val.slice(0, 100), sendBtn: btnInfo};
    }""")
    print("\n[A: type输入后]", json.dumps(state1, ensure_ascii=False))

    # 尝试点击"送"
    clicked = False
    for sel in ["button:has-text('送')", "button:text-is('送')"]:
        try:
            el = pg.query_selector(sel)
            if el and el.is_visible():
                el.click(force=True)
                clicked = True
                break
        except Exception:
            pass
    print("[A] 点击了送按钮:", clicked)
    pg.wait_for_timeout(2000)
    state2 = box.evaluate("""el => {
        const tag = el.tagName.toLowerCase();
        return ((tag === 'input' || tag === 'textarea') ? el.value : el.innerText).trim();
    }""")
    print("[A] 发送后输入框内容:", repr(state2[:50]))

    # 检查消息是否发出（页面文本变化）
    body = pg.evaluate("() => document.body.innerText")
    print("[A] 页面含'测试消息':", "测试消息" in body)

    # 方式B：Enter 发送（若 A 失败输入框还有文字）
    if state2.strip():
        box.click()
        pg.keyboard.press("Enter")
        pg.wait_for_timeout(2000)
        state3 = box.evaluate("""el => {
            const tag = el.tagName.toLowerCase();
            return ((tag === 'input' || tag === 'textarea') ? el.value : el.innerText).trim();
        }""")
        body2 = pg.evaluate("() => document.body.innerText")
        print("[B: Enter] 输入框:", repr(state3[:50]), "| 页面含'测试消息':", "测试消息" in body2)

    # 方式C：Ctrl+Enter
    if state2.strip():
        box.click()
        pg.keyboard.press("Control+Enter")
        pg.wait_for_timeout(2000)
        state4 = box.evaluate("""el => {
            const tag = el.tagName.toLowerCase();
            return ((tag === 'input' || tag === 'textarea') ? el.value : el.innerText).trim();
        }""")
        body3 = pg.evaluate("() => document.body.innerText")
        print("[C: Ctrl+Enter] 输入框:", repr(state4[:50]), "| 页面含'测试消息':", "测试消息" in body3)

    # 方式D：dispatch input 事件 + 点击（针对 Vue/React 受控组件）
    if state2.strip():
        pg.evaluate("""() => {
            const el = document.querySelector('textarea') || document.querySelector('[contenteditable="true"]');
            if (!el) return;
            const proto = el.tagName === 'TEXTAREA' || el.tagName === 'INPUT'
                ? window.HTMLTextAreaElement.prototype : window.HTMLInputElement.prototype;
            const setter = Object.getOwnPropertyDescriptor(proto, 'value').set;
            setter.call(el, el.value || '');
            el.dispatchEvent(new Event('input', {bubbles: true}));
        }""")
        pg.wait_for_timeout(500)
        try:
            el = pg.query_selector("button:has-text('送')")
            if el and el.is_visible():
                el.click()
                pg.wait_for_timeout(2000)
                body4 = pg.evaluate("() => document.body.innerText")
                print("[D: input事件+点击] 页面含'测试消息':", "测试消息" in body4)
        except Exception as e:
            print("[D] err:", e)

    pg.wait_for_timeout(3000)
    b.close()
