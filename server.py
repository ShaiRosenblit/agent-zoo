#!/usr/bin/env python3
"""
Web UI for watching the agent conversation in real-time.

Usage:
    uv run server.py
    
Then open http://localhost:5000 in your browser.
Run agent_zoo.py in another terminal to see the conversation evolve.
"""

import json
import os
import re
import time
from flask import Flask, Response, render_template_string, request, jsonify

app = Flask(__name__)

CHANNEL_PATH = "channel.txt"
STOP_FILE = ".stop"
SETTINGS_FILE = ".settings.json"
SEPARATOR = "=" * 80
SUBSEPARATOR = "-" * 80

DEFAULT_SETTINGS = {
    "max_tokens": 512,
    "delay_seconds": 30,
    "paused": False
}

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Agent Zoo</title>
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
    <link href="https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@400;600&family=Space+Grotesk:wght@400;600&display=swap" rel="stylesheet">
    <style>
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            font-family: 'Space Grotesk', sans-serif;
            background: linear-gradient(135deg, #0f0f1a 0%, #1a1a2e 50%, #16213e 100%);
            min-height: 100vh;
            color: #e0e0e0;
            padding: 2rem;
            padding-bottom: 200px;
        }
        
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        
        h1 {
            font-size: 2.5rem;
            margin-bottom: 0.5rem;
            background: linear-gradient(90deg, #00d9ff, #00ff88);
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }
        
        .subtitle {
            color: #666;
            margin-bottom: 2rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.9rem;
        }
        
        .token-count {
            color: #555;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.7rem;
            position: fixed;
            top: 1rem;
            right: 1.5rem;
            background: rgba(15, 15, 26, 0.8);
            padding: 0.3rem 0.6rem;
            border-radius: 4px;
            border: 1px solid rgba(255,255,255,0.05);
        }
        
        #channel {
            display: flex;
            flex-direction: column;
            gap: 1rem;
        }
        
        .message {
            background: rgba(255, 255, 255, 0.03);
            border: 1px solid rgba(255, 255, 255, 0.08);
            border-radius: 12px;
            padding: 1.25rem;
            animation: fadeIn 0.4s ease-out;
            position: relative;
            overflow: hidden;
        }
        
        .message::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
        }
        
        .message.user::before { background: #00d9ff; }
        .message.einstein::before { background: #ffd700; }
        .message.feynman::before { background: #ff6b6b; }
        .message.planner::before { background: #00ff88; }
        .message.critic::before { background: #ff9f43; }
        .message.unknown::before { background: #888; }
        
        .message-header {
            display: flex;
            align-items: center;
            gap: 0.75rem;
            margin-bottom: 0.75rem;
        }
        
        .message-index {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            color: #555;
            background: rgba(255,255,255,0.05);
            padding: 0.2rem 0.5rem;
            border-radius: 4px;
        }
        
        .message-author {
            font-weight: 600;
            font-size: 1.1rem;
        }
        
        .message.user .message-author { color: #00d9ff; }
        .message.einstein .message-author { color: #ffd700; }
        .message.feynman .message-author { color: #ff6b6b; }
        .message.planner .message-author { color: #00ff88; }
        .message.critic .message-author { color: #ff9f43; }
        
        .message-content {
            font-size: 1rem;
            line-height: 1.7;
            white-space: pre-wrap;
            color: #ccc;
        }
        
        .status {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.85rem;
            color: #00ff88;
            margin-bottom: 1.5rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .status-dot {
            width: 8px;
            height: 8px;
            background: #00ff88;
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        
        .status-dot.paused {
            background: #ffd700;
            animation: none;
        }
        
        .status-dot.stopped {
            background: #ff6b6b;
            animation: none;
        }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(10px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }
        
        .empty {
            color: #555;
            font-style: italic;
            padding: 2rem;
            text-align: center;
            border: 1px dashed rgba(255,255,255,0.1);
            border-radius: 12px;
        }
        
        /* Control panel */
        .control-area {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: linear-gradient(to top, #0f0f1a 0%, #0f0f1a 90%, transparent 100%);
            padding: 1rem 2rem 1.5rem;
        }
        
        .control-container {
            max-width: 800px;
            margin: 0 auto;
        }
        
        .controls-row {
            display: flex;
            gap: 1.5rem;
            margin-bottom: 1rem;
            align-items: center;
            flex-wrap: wrap;
        }
        
        .control-group {
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }
        
        .control-group label {
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            color: #888;
            text-transform: uppercase;
        }
        
        .control-group input[type="number"] {
            width: 80px;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 6px;
            padding: 0.5rem;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.9rem;
            color: #e0e0e0;
            outline: none;
        }
        
        .control-group input[type="number"]:focus {
            border-color: #00d9ff;
        }
        
        .input-row {
            display: flex;
            gap: 0.75rem;
        }
        
        #user-input {
            flex: 1;
            background: rgba(255, 255, 255, 0.05);
            border: 1px solid rgba(255, 255, 255, 0.15);
            border-radius: 8px;
            padding: 0.875rem 1rem;
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1rem;
            color: #e0e0e0;
            outline: none;
            transition: border-color 0.2s;
        }
        
        #user-input:focus {
            border-color: #00d9ff;
        }
        
        #user-input::placeholder {
            color: #555;
        }
        
        button {
            padding: 0.75rem 1.25rem;
            border: none;
            border-radius: 8px;
            font-family: 'Space Grotesk', sans-serif;
            font-size: 0.9rem;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
        }
        
        #send-btn {
            background: linear-gradient(135deg, #00d9ff, #00ff88);
            color: #0f0f1a;
        }
        
        #send-btn:hover {
            transform: translateY(-1px);
            box-shadow: 0 4px 20px rgba(0, 217, 255, 0.3);
        }
        
        #send-btn:disabled {
            opacity: 0.5;
            cursor: not-allowed;
            transform: none;
            box-shadow: none;
        }
        
        #pause-btn {
            background: rgba(255, 215, 0, 0.2);
            color: #ffd700;
            border: 1px solid #ffd700;
        }
        
        #pause-btn:hover {
            background: rgba(255, 215, 0, 0.3);
        }
        
        #pause-btn.paused {
            background: #ffd700;
            color: #0f0f1a;
        }
        
        #stop-btn {
            background: rgba(255, 107, 107, 0.2);
            color: #ff6b6b;
            border: 1px solid #ff6b6b;
        }
        
        #stop-btn:hover {
            background: rgba(255, 107, 107, 0.3);
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Agent Zoo</h1>
        <p class="subtitle">watching channel.txt</p>
        <div class="status">
            <span class="status-dot" id="status-dot"></span>
            <span id="status-text">Connecting...</span>
        </div>
        <span class="token-count" id="token-count"></span>
        <div id="channel">
            <div class="empty">Waiting for messages...</div>
        </div>
    </div>
    
    <div class="control-area">
        <div class="control-container">
            <div class="controls-row">
                <div class="control-group">
                    <label>Max tokens</label>
                    <input type="number" id="max-tokens" value="512" min="100" max="4000" step="100">
                </div>
                <div class="control-group">
                    <label>Delay (sec)</label>
                    <input type="number" id="delay-seconds" value="30" min="0" max="300" step="5">
                </div>
                <button id="pause-btn">Pause</button>
                <button id="stop-btn">Stop</button>
            </div>
            <div class="input-row">
                <input type="text" id="user-input" placeholder="Type a message to interrupt the conversation..." />
                <button id="send-btn">Send</button>
            </div>
        </div>
    </div>
    
    <script>
        const channel = document.getElementById('channel');
        const statusText = document.getElementById('status-text');
        const statusDot = document.getElementById('status-dot');
        const tokenCountEl = document.getElementById('token-count');
        const userInput = document.getElementById('user-input');
        const sendBtn = document.getElementById('send-btn');
        const pauseBtn = document.getElementById('pause-btn');
        const stopBtn = document.getElementById('stop-btn');
        const maxTokensInput = document.getElementById('max-tokens');
        const delayInput = document.getElementById('delay-seconds');
        
        let messageCount = 0;
        let isPaused = false;
        let totalTokens = 0;
        
        function getAgentClass(author) {
            const lower = author.toLowerCase();
            if (lower === 'user') return 'user';
            if (lower === 'einstein') return 'einstein';
            if (lower === 'feynman') return 'feynman';
            if (lower === 'planner') return 'planner';
            if (lower === 'critic') return 'critic';
            return 'unknown';
        }
        
        function renderMessage(msg) {
            const div = document.createElement('div');
            div.className = 'message ' + getAgentClass(msg.author);
            div.innerHTML = `
                <div class="message-header">
                    <span class="message-index">#${msg.index}</span>
                    <span class="message-author">${msg.author}</span>
                </div>
                <div class="message-content">${escapeHtml(msg.content)}</div>
            `;
            return div;
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        function updateStatus() {
            if (isPaused) {
                statusDot.className = 'status-dot paused';
                statusText.textContent = `Paused - ${messageCount} messages`;
            } else {
                statusDot.className = 'status-dot';
                statusText.textContent = `${messageCount} messages`;
            }
        }
        
        // Update settings
        async function updateSettings() {
            const settings = {
                max_tokens: parseInt(maxTokensInput.value) || 512,
                delay_seconds: parseInt(delayInput.value) || 30,
                paused: isPaused
            };
            
            try {
                await fetch('/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(settings)
                });
            } catch (e) {
                console.error('Failed to update settings:', e);
            }
        }
        
        // Load initial settings
        async function loadSettings() {
            try {
                const res = await fetch('/settings');
                const settings = await res.json();
                maxTokensInput.value = settings.max_tokens || 512;
                delayInput.value = settings.delay_seconds || 30;
                isPaused = settings.paused || false;
                pauseBtn.textContent = isPaused ? 'Resume' : 'Pause';
                pauseBtn.classList.toggle('paused', isPaused);
                updateStatus();
            } catch (e) {
                console.error('Failed to load settings:', e);
            }
        }
        
        // Debounce for input changes
        let settingsTimeout;
        function onSettingsChange() {
            clearTimeout(settingsTimeout);
            settingsTimeout = setTimeout(updateSettings, 300);
        }
        
        maxTokensInput.oninput = onSettingsChange;
        delayInput.oninput = onSettingsChange;
        
        // Send message
        async function sendMessage() {
            const text = userInput.value.trim();
            if (!text) return;
            
            sendBtn.disabled = true;
            userInput.disabled = true;
            
            try {
                const res = await fetch('/send', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text })
                });
                
                if (res.ok) {
                    userInput.value = '';
                }
            } catch (e) {
                console.error('Failed to send:', e);
            }
            
            sendBtn.disabled = false;
            userInput.disabled = false;
            userInput.focus();
        }
        
        sendBtn.onclick = sendMessage;
        userInput.onkeydown = (e) => {
            if (e.key === 'Enter') sendMessage();
        };
        
        // Pause/Resume
        pauseBtn.onclick = async () => {
            isPaused = !isPaused;
            pauseBtn.textContent = isPaused ? 'Resume' : 'Pause';
            pauseBtn.classList.toggle('paused', isPaused);
            updateStatus();
            await updateSettings();
        };
        
        // Stop conversation
        stopBtn.onclick = async () => {
            try {
                await fetch('/stop', { method: 'POST' });
                statusDot.className = 'status-dot stopped';
                statusText.textContent = 'Stopped';
            } catch (e) {
                console.error('Failed to stop:', e);
            }
        };
        
        // SSE stream
        const source = new EventSource('/stream');
        
        source.onopen = () => {
            updateStatus();
            loadSettings();
        };
        
        source.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.messages.length === 0) {
                channel.innerHTML = '<div class="empty">Waiting for messages...</div>';
                messageCount = 0;
                totalTokens = 0;
                tokenCountEl.textContent = '';
                updateStatus();
                return;
            }
            
            // Only render new messages
            if (data.messages.length > messageCount) {
                if (messageCount === 0) {
                    channel.innerHTML = '';
                }
                
                for (let i = messageCount; i < data.messages.length; i++) {
                    channel.appendChild(renderMessage(data.messages[i]));
                }
                
                messageCount = data.messages.length;
                totalTokens = data.total_tokens || 0;
                tokenCountEl.textContent = totalTokens > 0 ? `~${totalTokens.toLocaleString()} tokens` : '';
                updateStatus();
                
                // Scroll to bottom
                window.scrollTo(0, document.body.scrollHeight);
            }
        };
        
        source.onerror = () => {
            statusText.textContent = 'Disconnected - retrying...';
        };
    </script>
</body>
</html>
"""


def load_settings() -> dict:
    """Load settings from file."""
    if os.path.exists(SETTINGS_FILE):
        try:
            with open(SETTINGS_FILE, "r") as f:
                return {**DEFAULT_SETTINGS, **json.load(f)}
        except Exception:
            pass
    return DEFAULT_SETTINGS.copy()


def save_settings(settings: dict) -> None:
    """Save settings to file."""
    with open(SETTINGS_FILE, "w") as f:
        json.dump(settings, f)


def estimate_tokens(text: str) -> int:
    """Estimate token count (roughly 4 chars per token for English)."""
    return len(text) // 4


def parse_channel(content: str) -> list[dict]:
    """Parse the channel file into a list of messages."""
    if not content.strip():
        return []
    
    messages = []
    # Split by the separator line
    blocks = re.split(r'={80}\n', content)
    
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        
        # Parse header: [index] Author
        lines = block.split('\n')
        header_match = re.match(r'\[(\d+)\]\s+(.+)', lines[0])
        if header_match:
            index = int(header_match.group(1))
            author = header_match.group(2).strip()
            
            # Content is everything after the separator line
            content_start = 1
            if len(lines) > 1 and lines[1].startswith('-' * 10):
                content_start = 2
            
            content = '\n'.join(lines[content_start:]).strip()
            
            messages.append({
                'index': index,
                'author': author,
                'content': content
            })
    
    return messages


def count_messages() -> int:
    """Count messages in the channel."""
    if not os.path.exists(CHANNEL_PATH):
        return 0
    with open(CHANNEL_PATH, 'r') as f:
        content = f.read()
    if not content.strip():
        return 0
    return content.count(SEPARATOR)


def append_message(index: int, author: str, content: str) -> None:
    """Append a message to the channel file."""
    with open(CHANNEL_PATH, "a") as f:
        f.write(f"{SEPARATOR}\n")
        f.write(f"[{index}] {author}\n")
        f.write(f"{SUBSEPARATOR}\n")
        f.write(f"{content}\n\n")


def watch_channel():
    """Generator that yields channel content when it changes."""
    last_content = None
    last_mtime = 0
    
    while True:
        try:
            if os.path.exists(CHANNEL_PATH):
                mtime = os.path.getmtime(CHANNEL_PATH)
                if mtime != last_mtime:
                    with open(CHANNEL_PATH, 'r') as f:
                        content = f.read()
                    if content != last_content:
                        last_content = content
                        last_mtime = mtime
                        yield content
            else:
                if last_content is not None:
                    last_content = None
                    yield ""
        except Exception:
            pass
        
        time.sleep(0.3)


@app.route('/')
def index():
    return render_template_string(HTML)


@app.route('/stream')
def stream():
    def generate():
        # Send initial state
        if os.path.exists(CHANNEL_PATH):
            with open(CHANNEL_PATH, 'r') as f:
                content = f.read()
        else:
            content = ""
        
        messages = parse_channel(content)
        total_tokens = estimate_tokens(content)
        yield f"data: {json.dumps({'messages': messages, 'total_tokens': total_tokens})}\n\n"
        
        # Watch for changes
        for content in watch_channel():
            messages = parse_channel(content)
            total_tokens = estimate_tokens(content)
            yield f"data: {json.dumps({'messages': messages, 'total_tokens': total_tokens})}\n\n"
    
    return Response(generate(), mimetype='text/event-stream')


@app.route('/settings', methods=['GET'])
def get_settings():
    """Get current settings."""
    return jsonify(load_settings())


@app.route('/settings', methods=['POST'])
def update_settings():
    """Update settings."""
    data = request.get_json()
    settings = load_settings()
    
    if 'max_tokens' in data:
        settings['max_tokens'] = max(100, min(4000, int(data['max_tokens'])))
    if 'delay_seconds' in data:
        settings['delay_seconds'] = max(0, min(300, int(data['delay_seconds'])))
    if 'paused' in data:
        settings['paused'] = bool(data['paused'])
    
    save_settings(settings)
    return jsonify({'ok': True})


@app.route('/send', methods=['POST'])
def send():
    """Add a user message to the channel."""
    data = request.get_json()
    message = data.get('message', '').strip()
    
    if not message:
        return jsonify({'error': 'Empty message'}), 400
    
    if not os.path.exists(CHANNEL_PATH):
        return jsonify({'error': 'No active conversation'}), 400
    
    index = count_messages() + 1
    append_message(index, "User", message)
    
    return jsonify({'ok': True, 'index': index})


@app.route('/stop', methods=['POST'])
def stop():
    """Signal the agent loop to stop."""
    with open(STOP_FILE, 'w') as f:
        f.write('stop')
    return jsonify({'ok': True})


if __name__ == '__main__':
    print("Starting server at http://localhost:5000")
    print("Run 'uv run agent_zoo.py' in another terminal to start a conversation")
    app.run(debug=False, threaded=True)
