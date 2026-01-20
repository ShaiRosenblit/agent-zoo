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
    "delay_seconds": 5,
    "paused": False,
    "agents": []
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
            background: #888;
        }
        
        .message.user::before { background: #00d9ff; }
        .message.user .message-author { color: #00d9ff; }
        
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
            color: #aaa;
        }
        
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
        
        .status-dot.paused { background: #ffd700; animation: none; }
        .status-dot.stopped { background: #ff6b6b; animation: none; }
        
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
        
        /* Agents Panel */
        .agents-toggle {
            position: fixed;
            top: 1rem;
            left: 1rem;
            background: rgba(255,255,255,0.05);
            border: 1px solid rgba(255,255,255,0.1);
            color: #888;
            padding: 0.5rem 0.75rem;
            border-radius: 6px;
            cursor: pointer;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            z-index: 100;
        }
        
        .agents-toggle:hover { background: rgba(255,255,255,0.1); color: #ccc; }
        
        .agents-panel {
            position: fixed;
            top: 0;
            left: -360px;
            width: 350px;
            height: 100vh;
            background: #12121f;
            border-right: 1px solid rgba(255,255,255,0.1);
            padding: 1rem;
            overflow-y: auto;
            transition: left 0.3s ease;
            z-index: 99;
        }
        
        .agents-panel.open { left: 0; }
        
        .agents-panel h2 {
            font-size: 1rem;
            color: #888;
            margin-bottom: 1rem;
            font-family: 'JetBrains Mono', monospace;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }
        
        .agent-card {
            background: rgba(255,255,255,0.03);
            border: 1px solid rgba(255,255,255,0.08);
            border-radius: 8px;
            padding: 0.75rem;
            margin-bottom: 0.75rem;
        }
        
        .agent-card-header {
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }
        
        .agent-name-input {
            background: transparent;
            border: none;
            color: #e0e0e0;
            font-family: 'Space Grotesk', sans-serif;
            font-size: 1rem;
            font-weight: 600;
            width: 140px;
            outline: none;
            border-bottom: 1px solid transparent;
        }
        
        .agent-name-input:focus { border-bottom-color: #00d9ff; }
        
        .agent-model-select {
            background: rgba(0,0,0,0.3);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 4px;
            color: #888;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.65rem;
            padding: 0.2rem 0.3rem;
            outline: none;
            cursor: pointer;
        }
        
        .agent-model-select:focus { border-color: #00d9ff; }
        
        .agent-prompt-input {
            width: 100%;
            background: rgba(0,0,0,0.2);
            border: 1px solid rgba(255,255,255,0.1);
            border-radius: 4px;
            color: #ccc;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            padding: 0.5rem;
            resize: vertical;
            min-height: 60px;
            outline: none;
        }
        
        .agent-prompt-input:focus { border-color: #00d9ff; }
        
        .agent-delete {
            background: none;
            border: none;
            color: #ff6b6b;
            cursor: pointer;
            padding: 0.25rem;
            opacity: 0.5;
            font-size: 1rem;
        }
        
        .agent-delete:hover { opacity: 1; }
        
        .add-agent-btn {
            width: 100%;
            padding: 0.75rem;
            background: rgba(0, 217, 255, 0.1);
            border: 1px dashed rgba(0, 217, 255, 0.3);
            border-radius: 8px;
            color: #00d9ff;
            font-family: 'Space Grotesk', sans-serif;
            cursor: pointer;
            margin-top: 0.5rem;
        }
        
        .add-agent-btn:hover { background: rgba(0, 217, 255, 0.2); }
        
        .new-agent-form {
            background: rgba(0, 217, 255, 0.05);
            border: 1px solid rgba(0, 217, 255, 0.2);
            border-radius: 8px;
            padding: 0.75rem;
            margin-top: 0.5rem;
            display: none;
        }
        
        .new-agent-form.visible { display: block; }
        
        .new-agent-form input,
        .new-agent-form textarea {
            width: 100%;
            margin-bottom: 0.5rem;
        }
        
        .new-agent-form input {
            background: rgba(0,0,0,0.3);
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 4px;
            color: #e0e0e0;
            font-family: 'Space Grotesk', sans-serif;
            font-size: 0.9rem;
            padding: 0.5rem;
            outline: none;
        }
        
        .new-agent-form input:focus { border-color: #00d9ff; }
        
        .new-agent-form select {
            width: 100%;
            background: rgba(0,0,0,0.3);
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 4px;
            color: #e0e0e0;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.8rem;
            padding: 0.5rem;
            margin-bottom: 0.5rem;
            outline: none;
            cursor: pointer;
        }
        
        .new-agent-form select:focus { border-color: #00d9ff; }
        
        .new-agent-form textarea {
            background: rgba(0,0,0,0.3);
            border: 1px solid rgba(255,255,255,0.15);
            border-radius: 4px;
            color: #ccc;
            font-family: 'JetBrains Mono', monospace;
            font-size: 0.75rem;
            padding: 0.5rem;
            resize: vertical;
            min-height: 80px;
            outline: none;
        }
        
        .new-agent-form textarea:focus { border-color: #00d9ff; }
        
        .prompt-row {
            position: relative;
        }
        
        .enrich-btn {
            position: absolute;
            top: 0.25rem;
            right: 0.25rem;
            padding: 0.25rem 0.5rem;
            font-size: 0.65rem;
            background: rgba(255, 215, 0, 0.2);
            color: #ffd700;
            border: 1px solid rgba(255, 215, 0, 0.3);
            border-radius: 4px;
            cursor: pointer;
        }
        
        .enrich-btn:hover { background: rgba(255, 215, 0, 0.3); }
        .enrich-btn:disabled { opacity: 0.5; cursor: wait; }
        
        .new-agent-actions {
            display: flex;
            gap: 0.5rem;
        }
        
        .new-agent-actions button {
            flex: 1;
            padding: 0.5rem;
            font-size: 0.8rem;
        }
        
        .confirm-btn {
            background: linear-gradient(135deg, #00d9ff, #00ff88);
            color: #0f0f1a;
        }
        
        .cancel-btn {
            background: rgba(255,255,255,0.1);
            color: #888;
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
        
        .control-group input[type="number"]:focus { border-color: #00d9ff; }
        
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
        }
        
        #user-input:focus { border-color: #00d9ff; }
        #user-input::placeholder { color: #555; }
        
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
        
        #send-btn:hover { transform: translateY(-1px); box-shadow: 0 4px 20px rgba(0, 217, 255, 0.3); }
        #send-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; box-shadow: none; }
        
        #pause-btn {
            background: rgba(255, 215, 0, 0.2);
            color: #ffd700;
            border: 1px solid #ffd700;
        }
        
        #pause-btn:hover { background: rgba(255, 215, 0, 0.3); }
        #pause-btn.paused { background: #ffd700; color: #0f0f1a; }
        
        #stop-btn {
            background: rgba(255, 107, 107, 0.2);
            color: #ff6b6b;
            border: 1px solid #ff6b6b;
        }
        
        #stop-btn:hover { background: rgba(255, 107, 107, 0.3); }
        
        #restart-btn {
            background: rgba(0, 217, 255, 0.2);
            color: #00d9ff;
            border: 1px solid #00d9ff;
        }
        
        #restart-btn:hover { background: rgba(0, 217, 255, 0.3); }
    </style>
</head>
<body>
    <button class="agents-toggle" id="agents-toggle">Agents</button>
    
    <div class="agents-panel" id="agents-panel">
        <h2>Agents</h2>
        <div id="agents-list"></div>
        <button class="add-agent-btn" id="add-agent-btn">+ Add Agent</button>
        <div class="new-agent-form" id="new-agent-form">
            <input type="text" id="new-agent-name" placeholder="Agent name..." />
            <select id="new-agent-model">
                <option value="gpt-5">gpt-5 (best)</option>
                <option value="gpt-5-mini">gpt-5-mini</option>
                <option value="gpt-4o">gpt-4o</option>
                <option value="gpt-4o-mini">gpt-4o-mini (fast/cheap)</option>
            </select>
            <div class="prompt-row">
                <textarea id="new-agent-prompt" placeholder="System prompt (brief is fine, click Enrich to expand)..."></textarea>
                <button class="enrich-btn" id="enrich-new-prompt">Enrich</button>
            </div>
            <div class="new-agent-actions">
                <button class="cancel-btn" id="cancel-new-agent">Cancel</button>
                <button class="confirm-btn" id="confirm-new-agent">Add</button>
            </div>
        </div>
    </div>
    
    <div class="container">
        <h1>Agent Zoo</h1>
        <p class="subtitle">watching channel.txt</p>
        <div class="status">
            <span class="status-dot" id="status-dot"></span>
            <span id="status-text">Connecting...</span>
        </div>
        <span class="token-count" id="token-count"></span>
        <div id="channel">
            <div class="empty">Send a message to start the conversation...</div>
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
                    <input type="number" id="delay-seconds" value="5" min="0" max="300" step="5">
                </div>
                <button id="pause-btn">Pause</button>
                <button id="restart-btn">Restart</button>
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
        const restartBtn = document.getElementById('restart-btn');
        const stopBtn = document.getElementById('stop-btn');
        const maxTokensInput = document.getElementById('max-tokens');
        const delayInput = document.getElementById('delay-seconds');
        const agentsToggle = document.getElementById('agents-toggle');
        const agentsPanel = document.getElementById('agents-panel');
        const agentsList = document.getElementById('agents-list');
        const addAgentBtn = document.getElementById('add-agent-btn');
        const newAgentForm = document.getElementById('new-agent-form');
        const newAgentName = document.getElementById('new-agent-name');
        const newAgentPrompt = document.getElementById('new-agent-prompt');
        const cancelNewAgent = document.getElementById('cancel-new-agent');
        const confirmNewAgent = document.getElementById('confirm-new-agent');
        const enrichNewPrompt = document.getElementById('enrich-new-prompt');
        const newAgentModel = document.getElementById('new-agent-model');
        
        const MODEL_OPTIONS = ['gpt-5', 'gpt-5-mini', 'gpt-4o', 'gpt-4o-mini'];
        
        let messageCount = 0;
        let isPaused = false;
        let totalTokens = 0;
        let agents = [];
        
        // Agents panel toggle
        agentsToggle.onclick = () => agentsPanel.classList.toggle('open');
        
        function renderAgents() {
            agentsList.innerHTML = '';
            agents.forEach((agent, idx) => {
                const card = document.createElement('div');
                card.className = 'agent-card';
                const modelOptions = MODEL_OPTIONS.map(m => 
                    `<option value="${m}" ${(agent.model || 'gpt-4o') === m ? 'selected' : ''}>${m}</option>`
                ).join('');
                card.innerHTML = `
                    <div class="agent-card-header">
                        <input type="text" class="agent-name-input" value="${escapeHtml(agent.name)}" data-idx="${idx}" data-field="name" />
                        <select class="agent-model-select" data-idx="${idx}" data-field="model">${modelOptions}</select>
                        <button class="agent-delete" data-idx="${idx}">&times;</button>
                    </div>
                    <textarea class="agent-prompt-input" data-idx="${idx}" data-field="prompt" rows="3">${escapeHtml(agent.prompt)}</textarea>
                `;
                agentsList.appendChild(card);
            });
            
            // Bind events
            document.querySelectorAll('.agent-name-input, .agent-prompt-input, .agent-model-select').forEach(input => {
                input.oninput = onAgentChange;
                input.onchange = onAgentChange;
            });
            document.querySelectorAll('.agent-delete').forEach(btn => {
                btn.onclick = () => deleteAgent(parseInt(btn.dataset.idx));
            });
        }
        
        function onAgentChange(e) {
            const idx = parseInt(e.target.dataset.idx);
            const field = e.target.dataset.field;
            agents[idx][field] = e.target.value;
            saveAgentsDebounced();
        }
        
        let saveAgentsTimeout;
        function saveAgentsDebounced() {
            clearTimeout(saveAgentsTimeout);
            saveAgentsTimeout = setTimeout(saveAgents, 500);
        }
        
        async function saveAgents() {
            try {
                await fetch('/agents', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ agents })
                });
            } catch (e) {
                console.error('Failed to save agents:', e);
            }
        }
        
        function deleteAgent(idx) {
            agents.splice(idx, 1);
            renderAgents();
            saveAgents();
        }
        
        addAgentBtn.onclick = () => {
            newAgentName.value = '';
            newAgentPrompt.value = '';
            newAgentModel.value = 'gpt-4o';
            newAgentForm.classList.add('visible');
            addAgentBtn.style.display = 'none';
            newAgentName.focus();
        };
        
        cancelNewAgent.onclick = () => {
            newAgentForm.classList.remove('visible');
            addAgentBtn.style.display = 'block';
        };
        
        confirmNewAgent.onclick = () => {
            const name = newAgentName.value.trim();
            const prompt = newAgentPrompt.value.trim();
            const model = newAgentModel.value;
            
            if (!name) {
                newAgentName.focus();
                return;
            }
            
            agents.push({ name, prompt: prompt || 'You are a helpful assistant.', model });
            renderAgents();
            saveAgents();
            
            newAgentForm.classList.remove('visible');
            addAgentBtn.style.display = 'block';
        };
        
        enrichNewPrompt.onclick = async () => {
            const name = newAgentName.value.trim() || 'Agent';
            const prompt = newAgentPrompt.value.trim();
            
            if (!prompt) {
                newAgentPrompt.focus();
                return;
            }
            
            enrichNewPrompt.disabled = true;
            enrichNewPrompt.textContent = '...';
            
            try {
                const res = await fetch('/enrich', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, prompt })
                });
                const data = await res.json();
                if (data.enriched) {
                    newAgentPrompt.value = data.enriched;
                }
            } catch (e) {
                console.error('Failed to enrich:', e);
            }
            
            enrichNewPrompt.disabled = false;
            enrichNewPrompt.textContent = 'Enrich';
        };
        
        function getAgentClass(author) {
            if (author.toLowerCase() === 'user') return 'user';
            return '';
        }
        
        function renderMessage(msg) {
            const div = document.createElement('div');
            div.className = 'message ' + getAgentClass(msg.author);
            div.innerHTML = `
                <div class="message-header">
                    <span class="message-index">#${msg.index}</span>
                    <span class="message-author">${escapeHtml(msg.author)}</span>
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
        
        async function updateSettings() {
            try {
                await fetch('/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        max_tokens: parseInt(maxTokensInput.value) || 512,
                        delay_seconds: parseInt(delayInput.value) || 5,
                        paused: isPaused
                    })
                });
            } catch (e) {
                console.error('Failed to update settings:', e);
            }
        }
        
        async function loadSettings() {
            try {
                const res = await fetch('/settings');
                const settings = await res.json();
                maxTokensInput.value = settings.max_tokens || 512;
                delayInput.value = settings.delay_seconds || 5;
                isPaused = settings.paused || false;
                pauseBtn.textContent = isPaused ? 'Resume' : 'Pause';
                pauseBtn.classList.toggle('paused', isPaused);
                agents = settings.agents || [];
                renderAgents();
                updateStatus();
            } catch (e) {
                console.error('Failed to load settings:', e);
            }
        }
        
        let settingsTimeout;
        function onSettingsChange() {
            clearTimeout(settingsTimeout);
            settingsTimeout = setTimeout(updateSettings, 300);
        }
        
        maxTokensInput.oninput = onSettingsChange;
        delayInput.oninput = onSettingsChange;
        
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
                if (res.ok) userInput.value = '';
            } catch (e) {
                console.error('Failed to send:', e);
            }
            
            sendBtn.disabled = false;
            userInput.disabled = false;
            userInput.focus();
        }
        
        sendBtn.onclick = sendMessage;
        userInput.onkeydown = (e) => { if (e.key === 'Enter') sendMessage(); };
        
        pauseBtn.onclick = async () => {
            isPaused = !isPaused;
            pauseBtn.textContent = isPaused ? 'Resume' : 'Pause';
            pauseBtn.classList.toggle('paused', isPaused);
            updateStatus();
            await updateSettings();
        };
        
        restartBtn.onclick = async () => {
            try {
                await fetch('/restart', { method: 'POST' });
                messageCount = 0;
                channel.innerHTML = '<div class="empty">Send a message to start the conversation...</div>';
                updateStatus();
            } catch (e) {
                console.error('Failed to restart:', e);
            }
        };
        
        stopBtn.onclick = async () => {
            try {
                await fetch('/stop', { method: 'POST' });
                statusDot.className = 'status-dot stopped';
                statusText.textContent = 'Stopped';
            } catch (e) {
                console.error('Failed to stop:', e);
            }
        };
        
        const source = new EventSource('/stream');
        
        source.onopen = () => {
            updateStatus();
            loadSettings();
        };
        
        source.onmessage = (event) => {
            const data = JSON.parse(event.data);
            
            if (data.messages.length === 0) {
                channel.innerHTML = '<div class="empty">Send a message to start the conversation...</div>';
                messageCount = 0;
                totalTokens = 0;
                tokenCountEl.textContent = '';
                updateStatus();
                return;
            }
            
            if (data.messages.length > messageCount) {
                if (messageCount === 0) channel.innerHTML = '';
                
                for (let i = messageCount; i < data.messages.length; i++) {
                    channel.appendChild(renderMessage(data.messages[i]));
                }
                
                messageCount = data.messages.length;
                totalTokens = data.total_tokens || 0;
                tokenCountEl.textContent = totalTokens > 0 ? `~${totalTokens.toLocaleString()} tokens` : '';
                updateStatus();
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
        json.dump(settings, f, indent=2)


def estimate_tokens(text: str) -> int:
    """Estimate token count (roughly 4 chars per token for English)."""
    return len(text) // 4


def parse_channel(content: str) -> list[dict]:
    """Parse the channel file into a list of messages."""
    if not content.strip():
        return []
    
    messages = []
    blocks = re.split(r'={80}\n', content)
    
    for block in blocks:
        block = block.strip()
        if not block:
            continue
        
        lines = block.split('\n')
        header_match = re.match(r'\[(\d+)\]\s+(.+)', lines[0])
        if header_match:
            index = int(header_match.group(1))
            author = header_match.group(2).strip()
            
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
        if os.path.exists(CHANNEL_PATH):
            with open(CHANNEL_PATH, 'r') as f:
                content = f.read()
        else:
            content = ""
        
        messages = parse_channel(content)
        total_tokens = estimate_tokens(content)
        yield f"data: {json.dumps({'messages': messages, 'total_tokens': total_tokens})}\n\n"
        
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


@app.route('/agents', methods=['POST'])
def update_agents():
    """Update agents list."""
    data = request.get_json()
    settings = load_settings()
    
    if 'agents' in data:
        settings['agents'] = data['agents']
    
    save_settings(settings)
    return jsonify({'ok': True})


@app.route('/send', methods=['POST'])
def send():
    """Add a user message to the channel."""
    data = request.get_json()
    message = data.get('message', '').strip()
    
    if not message:
        return jsonify({'error': 'Empty message'}), 400
    
    index = count_messages() + 1
    append_message(index, "User", message)
    
    return jsonify({'ok': True, 'index': index})


@app.route('/restart', methods=['POST'])
def restart():
    """Clear the channel to restart the conversation."""
    if os.path.exists(CHANNEL_PATH):
        os.remove(CHANNEL_PATH)
    return jsonify({'ok': True})


@app.route('/stop', methods=['POST'])
def stop():
    """Signal the agent loop to stop."""
    with open(STOP_FILE, 'w') as f:
        f.write('stop')
    return jsonify({'ok': True})


@app.route('/enrich', methods=['POST'])
def enrich():
    """Enrich a system prompt using AI."""
    import openai
    
    data = request.get_json()
    name = data.get('name', 'Agent')
    prompt = data.get('prompt', '').strip()
    
    if not prompt:
        return jsonify({'error': 'No prompt provided'}), 400
    
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return jsonify({'error': 'OPENAI_API_KEY not set'}), 500
    
    try:
        client = openai.OpenAI(api_key=api_key)
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": """You are an expert at writing system prompts for AI agents.
Given a brief description, expand it into a detailed, effective system prompt.
Keep it focused and actionable. Include:
- Clear role definition
- Personality/tone guidance  
- Key behaviors and rules
- What to emphasize or avoid

Return ONLY the improved prompt text, no explanations."""
                },
                {
                    "role": "user",
                    "content": f"Agent name: {name}\n\nBrief description:\n{prompt}\n\nWrite an enriched system prompt:"
                }
            ],
            max_tokens=500,
        )
        enriched = response.choices[0].message.content.strip()
        return jsonify({'enriched': enriched})
    except Exception as e:
        print(f"Enrich error: {e}")
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    # For standalone use (not typical - prefer running agent_zoo.py)
    print("Starting server at http://localhost:5000")
    print("Note: Run 'uv run agent_zoo.py' instead to start both server and agents")
    app.run(debug=False, threaded=True)
