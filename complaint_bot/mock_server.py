from flask import Flask, render_template_string, request, jsonify
import random
import time

app = Flask(__name__)

chat_history = []
log_messages = []

response_index = 0

preset_responses = [
    "好的，我来帮您查询一下您的包裹情况，请稍等。",
    "抱歉，您的包裹目前显示正在运输途中，可能因为天气原因有所延迟。",
    "请您再耐心等待一下，我们会尽快安排派送的。",
    "如果超过3天仍未送达，您可以申请理赔。",
    "理赔需要提供订单号和相关证明材料。",
    "好的，我已经帮您登记了投诉，我们会在24小时内给您回复。",
    "感谢您的理解，祝您生活愉快！"
]

def get_dynamic_response(user_message):
    if any(word in user_message for word in ["投诉", "强烈", "必须", "立刻", "马上"]):
        return random.choice([
            "非常理解您的心情，我会立即帮您升级处理，请稍等。",
            "抱歉让您这么生气，我马上联系相关部门处理。",
            "好的，我已经记录了您的投诉，会尽快处理。"
        ])
    
    if any(word in user_message for word in ["12305", "国家邮政局", "申诉", "举报"]):
        return random.choice([
            "请不要着急，我们一定会妥善处理您的问题。",
            "非常抱歉，我会立即向主管汇报您的情况。",
            "请给我们一些时间，我们会尽快给您满意的答复。"
        ])
    
    if any(word in user_message for word in ["理赔", "赔偿", "退款"]):
        return random.choice([
            "理赔需要提供订单号、商品价值证明和快递面单。",
            "请您准备好相关材料，我们会尽快为您办理。",
            "理赔流程需要3-5个工作日，请耐心等待。"
        ])
    
    if any(word in user_message for word in ["运单号", "单号", "ZT1234567890"]):
        return random.choice([
            "好的，我已经记下了您的运单号，正在查询中。",
            "您的运单号已记录，我会帮您追踪包裹位置。",
            "收到您的运单号，正在核实包裹状态。"
        ])
    
    if any(word in user_message for word in ["丢失", "找不到", "没收到"]):
        return random.choice([
            "非常抱歉听到这个消息，我会立即帮您查找。",
            "我们会尽力帮您找回包裹，请放心。",
            "我会启动丢失件处理流程，请耐心等待。"
        ])
    
    if any(word in user_message for word in ["多久", "什么时候", "时间"]):
        return random.choice([
            "一般处理时间是24-48小时，请耐心等待。",
            "我们会在24小时内给您回复，请留意电话。",
            "具体时间要看处理进度，我会帮您催促。"
        ])
    
    if any(word in user_message for word in ["升级", "主管", "经理"]):
        return random.choice([
            "好的，我马上帮您转接主管，请稍等。",
            "主管正在处理其他事务，我会帮您转达。",
            "已经为您升级到主管处理，请等待回电。"
        ])
    
    if any(word in user_message for word in ["工单", "编号", "工单号"]):
        return random.choice([
            "工单编号是KT20240115001，请您记好。",
            "已为您生成工单KT20240115001，您可以凭此查询进度。",
            "工单编号KT20240115001已发送至您的手机，请查收。"
        ])
    
    return random.choice([
        "非常抱歉给您带来不便，我们会尽快处理。",
        "请您提供更多信息，以便我们更好地帮助您。",
        "我们会重视您的反馈，尽快给您回复。",
        "感谢您的耐心等待，我们正在处理中。"
    ])

@app.route('/')
def index():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>中通客服模拟系统</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 1200px; margin: 0 auto; padding: 20px; background-color: #f5f5f5; }
            .main-container { display: flex; gap: 20px; }
            .chat-section { flex: 1; background-color: white; border-radius: 12px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); }
            .log-section { width: 400px; background-color: #1e1e1e; border-radius: 12px; padding: 20px; box-shadow: 0 2px 10px rgba(0,0,0,0.1); color: #d4d4d4; }
            .chat-container { height: 450px; overflow-y: auto; background-color: #f9f9f9; border-radius: 8px; padding: 15px; margin-bottom: 15px; }
            .log-container { height: 450px; overflow-y: auto; font-family: 'Consolas', monospace; font-size: 13px; line-height: 1.5; }
            .message { margin-bottom: 12px; padding: 10px 14px; border-radius: 8px; max-width: 80%; word-wrap: break-word; }
            .customer { background-color: #4CAF50; color: white; text-align: right; margin-left: auto; }
            .service { background-color: #ffffff; border: 1px solid #ddd; text-align: left; }
            .input-area { display: flex; gap: 10px; }
            .input-area input { flex: 1; padding: 12px; border: 1px solid #ccc; border-radius: 6px; font-size: 14px; }
            .input-area button { padding: 12px 24px; background-color: #4CAF50; color: white; border: none; border-radius: 6px; cursor: pointer; font-size: 14px; }
            .input-area button:hover { background-color: #45a049; }
            .welcome-banner { text-align: center; margin-bottom: 15px; color: #333; font-size: 24px; }
            .log-header { color: #4CAF50; margin-bottom: 15px; padding-bottom: 10px; border-bottom: 1px solid #333; }
            .log-info { color: #61afef; }
            .log-success { color: #98c379; }
            .log-warning { color: #e5c07b; }
            .log-error { color: #e06c75; }
            .status-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px; padding: 10px; background-color: #e8f5e9; border-radius: 6px; }
            .status-item { display: flex; align-items: center; gap: 8px; }
            .status-dot { width: 8px; height: 8px; border-radius: 50%; background-color: #4CAF50; animation: pulse 2s infinite; }
            @keyframes pulse { 0%, 100% { opacity: 1; } 50% { opacity: 0.5; } }
            .clear-log-btn { background-color: #f44336; padding: 6px 12px; border: none; border-radius: 4px; color: white; cursor: pointer; font-size: 12px; }
            .clear-log-btn:hover { background-color: #d32f2f; }
        </style>
    </head>
    <body>
        <h1 class="welcome-banner">📦 中通快递客服中心</h1>
        
        <div class="main-container">
            <div class="chat-section">
                <div class="status-bar">
                    <div class="status-item">
                        <span class="status-dot"></span>
                        <span>在线客服</span>
                    </div>
                    <div class="status-item">
                        <span>对话轮数: <strong id="round-count">0</strong></span>
                    </div>
                </div>
                
                <div class="chat-container" id="chat-container">
                    <div class="message service" id="welcome">您好，中通快递，请问有什么可以帮您？</div>
                </div>
                
                <div class="input-area">
                    <input type="text" id="message-input" placeholder="请输入您的消息...">
                    <button onclick="sendMessage()">发送</button>
                </div>
            </div>
            
            <div class="log-section">
                <div style="display: flex; justify-content: space-between; align-items: center;">
                    <h3 class="log-header">🤖 机器人日志</h3>
                    <button class="clear-log-btn" onclick="clearLog()">清空日志</button>
                </div>
                <div class="log-container" id="log-container">
                    <div class="log-info">[系统] 日志系统已启动，等待机器人连接...</div>
                </div>
            </div>
        </div>
        
        <script>
            var logOffset = 0;
            
            function sendMessage() {
                var input = document.getElementById('message-input');
                var text = input.value.trim();
                if (!text) return;
                
                var container = document.getElementById('chat-container');
                var customerMsg = document.createElement('div');
                customerMsg.className = 'message customer';
                customerMsg.textContent = text;
                container.appendChild(customerMsg);
                
                input.value = '';
                container.scrollTop = container.scrollHeight;
                
                fetch('/send', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text })
                }).then(response => response.json()).then(data => {
                    setTimeout(() => {
                        var serviceMsg = document.createElement('div');
                        serviceMsg.className = 'message service';
                        serviceMsg.textContent = data.response;
                        container.appendChild(serviceMsg);
                        container.scrollTop = container.scrollHeight;
                    }, 1500 + Math.random() * 1000);
                });
            }
            
            document.getElementById('message-input').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') sendMessage();
            });
            
            function addLog(message, type = 'info') {
                var container = document.getElementById('log-container');
                var logItem = document.createElement('div');
                var timestamp = new Date().toLocaleTimeString();
                logItem.innerHTML = '<span style="color:#888;">[' + timestamp + ']</span> <span class="log-' + type + '">' + message + '</span>';
                container.appendChild(logItem);
                container.scrollTop = container.scrollHeight;
            }
            
            function clearLog() {
                document.getElementById('log-container').innerHTML = '<div class="log-info">[系统] 日志已清空</div>';
                logOffset = 0;
            }
            
            function fetchLogs() {
                fetch('/logs?offset=' + logOffset)
                    .then(response => response.json())
                    .then(data => {
                        if (data.logs && data.logs.length > 0) {
                            data.logs.forEach(log => {
                                addLog(log.message, log.type);
                            });
                            logOffset = data.offset;
                        }
                        
                        var roundCount = document.querySelectorAll('.message').length;
                        document.getElementById('round-count').textContent = Math.floor(roundCount / 2);
                    })
                    .catch(error => console.error('Failed to fetch logs:', error));
            }
            
            setInterval(fetchLogs, 1500);
        </script>
    </body>
    </html>
    """
    return render_template_string(html)

@app.route('/send', methods=['POST'])
def send_message():
    global response_index
    data = request.get_json()
    user_message = data.get('message', '')
    
    chat_history.append({'role': 'customer', 'content': user_message})
    
    if response_index < len(preset_responses):
        response = preset_responses[response_index]
        response_index += 1
    else:
        response = get_dynamic_response(user_message)
    
    chat_history.append({'role': 'service', 'content': response})
    
    return jsonify({'response': response})

@app.route('/history')
def get_history():
    return jsonify(chat_history)

@app.route('/reset')
def reset():
    global response_index, chat_history, log_messages
    response_index = 0
    chat_history = []
    log_messages = []
    return jsonify({'status': 'ok'})

@app.route('/logs')
def get_logs():
    global log_messages
    offset = int(request.args.get('offset', 0))
    new_logs = log_messages[offset:]
    return jsonify({
        'logs': new_logs,
        'offset': len(log_messages)
    })

@app.route('/log', methods=['POST'])
def add_log():
    global log_messages
    data = request.get_json()
    log_messages.append({
        'timestamp': time.time(),
        'message': data.get('message', ''),
        'type': data.get('type', 'info')
    })
    return jsonify({'status': 'ok'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5001, debug=True)