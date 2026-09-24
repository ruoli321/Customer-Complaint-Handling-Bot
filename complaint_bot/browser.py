from playwright.sync_api import sync_playwright, Page, Browser
import time

class BrowserController:
    def __init__(self, headless: bool = False):
        self.playwright = None
        self.browser = None
        self.page = None
        self.headless = headless

    def launch(self):
        self.playwright = sync_playwright().start()
        self.browser = self.playwright.chromium.launch(headless=self.headless)
        self.page = self.browser.new_page()

    def navigate(self, url: str):
        self.page.goto(url)
        time.sleep(2)

    def get_messages(self):
        messages = []
        message_elements = self.page.query_selector_all('.message')
        for element in message_elements:
            class_name = element.get_attribute('class')
            role = 'customer' if 'customer' in class_name else 'service'
            content = element.inner_text()
            messages.append({'role': role, 'content': content})
        return messages

    def send_message(self, text: str):
        input_element = self.page.query_selector('#message-input')
        if not input_element:
            return False

        send_button = self.page.query_selector('.input-area button')
        if not send_button:
            return False

        for attempt in range(2):
            input_element.fill(text)
            time.sleep(0.5)
            send_button.click()
            time.sleep(1.5)

            # 验证发送生效：输入框必须已被清空
            remaining = (input_element.input_value() or '').strip()
            if not remaining:
                time.sleep(1.5)
                return True

        return False

    def wait_for_new_message(self, current_count: int, timeout: int = 10):
        start_time = time.time()
        while time.time() - start_time < timeout:
            messages = self.get_messages()
            if len(messages) > current_count:
                return messages[-1]
            time.sleep(0.5)
        return None

    def close(self):
        if self.browser:
            self.browser.close()
        if self.playwright:
            self.playwright.stop()