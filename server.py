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
AGENT_STATE_FILE = ".agent_state.json"
SEPARATOR = "=" * 80
SUBSEPARATOR = "-" * 80

DEFAULT_SETTINGS = {
    "max_tokens": 512,
    "delay_seconds": 0,
    "paused": False,
    "global_prompt": "",
    "agents": []
}

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>Agent Zoo</title>
    <style>
        :root {
            /* Neutral palette */
            --neutral-0: #FAFAFB;
            --neutral-50: #F4F5F7;
            --neutral-100: #E9EBEF;
            --neutral-200: #D6DAE3;
            --neutral-300: #B8BFCD;
            --neutral-400: #8A94A6;
            --neutral-500: #5B667A;
            --neutral-600: #3F4859;
            --neutral-700: #2C3240;
            --neutral-800: #1F2430;
            --neutral-900: #141722;
            
            /* Surface */
            --surface-0: #FFFFFF;
            --surface-1: #FFFFFF;
            --surface-2: #F9FAFC;
            
            /* Accent colors */
            --primary-50: #EEF4FF;
            --primary-100: #D9E6FF;
            --primary-500: #4C7DFF;
            --primary-600: #3A67E6;
            
            --secondary-50: #F4F0FF;
            --secondary-100: #E6DBFF;
            --secondary-500: #7B61FF;
            --secondary-600: #664DE6;
            
            --highlight-50: #EEFFF5;
            --highlight-100: #D7FBE7;
            --highlight-500: #2ECC71;
            --highlight-600: #28B863;
            
            /* Status */
            --success: #22C55E;
            --warning: #F59E0B;
            --danger: #EF4444;
            --info: #3B82F6;
            
            /* Typography */
            --font-sans: ui-sans-serif, system-ui, -apple-system, "Segoe UI", Roboto, "Helvetica Neue", Arial, "Noto Sans", sans-serif;
            --font-mono: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
            
            /* Shadows */
            --shadow-1: 0 1px 2px rgba(20, 23, 34, 0.06);
            --shadow-2: 0 6px 18px rgba(20, 23, 34, 0.08);
            --shadow-3: 0 14px 32px rgba(20, 23, 34, 0.10);
            
            /* Radii */
            --radius-xs: 6px;
            --radius-sm: 10px;
            --radius-md: 14px;
            --radius-lg: 18px;
            --radius-pill: 9999px;
            
            /* Motion */
            --ease-standard: cubic-bezier(0.2, 0.8, 0.2, 1);
            --duration-fast: 120ms;
            --duration-base: 180ms;
        }
        
        * { box-sizing: border-box; margin: 0; padding: 0; }
        
        body {
            font-family: var(--font-sans);
            background: var(--neutral-0);
            min-height: 100vh;
            color: var(--neutral-800);
            padding: 32px;
            padding-bottom: 200px;
            line-height: 1.5;
        }
        
        .container {
            max-width: 800px;
            margin: 0 auto;
        }
        
        h1 {
            font-size: 28px;
            font-weight: 600;
            margin-bottom: 8px;
            color: var(--neutral-800);
        }
        
        .subtitle {
            color: var(--neutral-500);
            margin-bottom: 32px;
            font-family: var(--font-mono);
            font-size: 14px;
        }
        
        .token-count {
            color: var(--neutral-400);
            font-family: var(--font-mono);
            font-size: 12px;
            position: fixed;
            top: 16px;
            right: 24px;
            background: var(--surface-0);
            padding: 6px 12px;
            border-radius: var(--radius-xs);
            border: 1px solid var(--neutral-100);
            box-shadow: var(--shadow-1);
        }
        
        #channel {
            display: flex;
            flex-direction: column;
            gap: 16px;
        }
        
        .message {
            background: var(--surface-0);
            border: 1px solid var(--neutral-100);
            border-radius: var(--radius-lg);
            padding: 20px;
            animation: fadeIn 0.26s var(--ease-standard);
            position: relative;
            overflow: hidden;
            box-shadow: var(--shadow-1);
        }
        
        .message::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background: var(--neutral-300);
        }
        
        .message.user::before { background: var(--primary-500); }
        .message.user .message-author { color: var(--primary-600); }
        
        .message-header {
            display: flex;
            align-items: center;
            gap: 12px;
            margin-bottom: 12px;
        }
        
        .message-index {
            font-family: var(--font-mono);
            font-size: 12px;
            color: var(--neutral-400);
            background: var(--neutral-50);
            padding: 4px 8px;
            border-radius: var(--radius-xs);
        }
        
        .message-author {
            font-weight: 600;
            font-size: 18px;
            color: var(--neutral-700);
        }
        
        .message-content {
            font-size: 16px;
            line-height: 1.65;
            white-space: pre-wrap;
            color: var(--neutral-600);
        }
        
        .status {
            font-family: var(--font-mono);
            font-size: 14px;
            color: var(--highlight-600);
            margin-bottom: 24px;
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .status-dot {
            width: 8px;
            height: 8px;
            background: var(--highlight-500);
            border-radius: 50%;
            animation: pulse 2s infinite;
        }
        
        .status-dot.paused { background: var(--warning); animation: none; }
        .status-dot.stopped { background: var(--danger); animation: none; }
        
        @keyframes fadeIn {
            from { opacity: 0; transform: translateY(8px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        @keyframes pulse {
            0%, 100% { opacity: 1; }
            50% { opacity: 0.4; }
        }
        
        @media (prefers-reduced-motion: reduce) {
            .message, .status-dot { animation: none; }
        }
        
        .empty {
            color: var(--neutral-400);
            font-size: 14px;
            padding: 40px;
            text-align: center;
            border: 1px dashed var(--neutral-200);
            border-radius: var(--radius-lg);
            background: var(--surface-2);
        }
        
        /* Agents Panel */
        .agents-toggle {
            position: fixed;
            top: 16px;
            left: 16px;
            background: var(--surface-0);
            border: 1px solid var(--neutral-200);
            color: var(--neutral-600);
            padding: 8px 12px;
            border-radius: var(--radius-xs);
            cursor: pointer;
            font-family: var(--font-mono);
            font-size: 12px;
            z-index: 100;
            box-shadow: var(--shadow-1);
            transition: all var(--duration-fast) var(--ease-standard);
        }
        
        .agents-toggle:hover { 
            background: var(--neutral-50); 
            color: var(--neutral-800);
            border-color: var(--neutral-300);
        }
        
        .agents-panel {
            position: fixed;
            top: 0;
            left: -340px;
            width: 320px;
            height: 100vh;
            background: var(--surface-0);
            border-right: 1px solid var(--neutral-100);
            padding: 16px;
            overflow-y: auto;
            transition: left 0.26s var(--ease-standard);
            z-index: 99;
            box-shadow: var(--shadow-2);
        }
        
        .agents-panel.open { left: 0; }
        
        .agents-panel h2 {
            font-size: 14px;
            color: var(--neutral-500);
            margin-bottom: 16px;
            font-family: var(--font-mono);
            text-transform: uppercase;
            letter-spacing: 0.05em;
            font-weight: 500;
        }
        
        .global-section {
            background: var(--highlight-50);
            border: 1px solid var(--highlight-100);
            border-radius: var(--radius-sm);
            padding: 12px;
            margin-bottom: 16px;
        }
        
        .global-section h3 {
            font-size: 12px;
            color: var(--highlight-600);
            margin-bottom: 8px;
            font-family: var(--font-mono);
            text-transform: uppercase;
            letter-spacing: 0.03em;
            font-weight: 600;
        }
        
        .global-section p {
            font-size: 12px;
            color: var(--neutral-500);
            margin-bottom: 8px;
            line-height: 1.5;
        }
        
        #global-prompt {
            width: 100%;
            background: var(--surface-0);
            border: 1px solid var(--neutral-200);
            border-radius: var(--radius-xs);
            color: var(--neutral-700);
            font-family: var(--font-mono);
            font-size: 12px;
            padding: 8px;
            resize: vertical;
            min-height: 60px;
            outline: none;
            transition: border-color var(--duration-fast) var(--ease-standard);
        }
        
        #global-prompt:focus { border-color: var(--highlight-500); background: var(--highlight-50); }
        #global-prompt::placeholder { color: var(--neutral-400); }
        
        .agent-card {
            background: var(--surface-0);
            border: 1px solid var(--neutral-100);
            border-radius: var(--radius-sm);
            padding: 12px;
            margin-bottom: 12px;
            box-shadow: var(--shadow-1);
        }
        
        .agent-card-header {
            display: flex;
            flex-direction: column;
            gap: 8px;
            margin-bottom: 8px;
        }
        
        .agent-card-header-top {
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        
        .agent-card-header-selects {
            display: flex;
            gap: 6px;
            align-items: center;
        }
        
        .agent-name-input {
            background: transparent;
            border: none;
            color: var(--neutral-800);
            font-family: var(--font-sans);
            font-size: 16px;
            font-weight: 600;
            flex: 1;
            min-width: 0;
            outline: none;
            border-bottom: 1px solid transparent;
            transition: border-color var(--duration-fast) var(--ease-standard);
        }
        
        .agent-name-input:focus { border-bottom-color: var(--primary-500); }
        
        .agent-model-select {
            background: var(--surface-2);
            border: 1px solid var(--neutral-200);
            border-radius: var(--radius-xs);
            color: var(--neutral-600);
            font-family: var(--font-mono);
            font-size: 11px;
            padding: 4px 8px;
            outline: none;
            cursor: pointer;
            transition: border-color var(--duration-fast) var(--ease-standard);
        }
        
        .agent-model-select:focus { border-color: var(--primary-500); }
        
        .agent-reasoning-select {
            background: var(--secondary-50);
            border: 1px solid var(--secondary-100);
            border-radius: var(--radius-xs);
            color: var(--secondary-600);
            font-family: var(--font-mono);
            font-size: 11px;
            padding: 4px 8px;
            outline: none;
            cursor: pointer;
        }
        
        .agent-reasoning-select:focus { border-color: var(--secondary-500); }
        .agent-reasoning-select.hidden { display: none; }
        
        .agent-prompt-input {
            width: 100%;
            background: var(--surface-2);
            border: 1px solid var(--neutral-200);
            border-radius: var(--radius-xs);
            color: var(--neutral-700);
            font-family: var(--font-mono);
            font-size: 12px;
            padding: 8px;
            resize: vertical;
            min-height: 60px;
            outline: none;
            transition: border-color var(--duration-fast) var(--ease-standard);
        }
        
        .agent-prompt-input:focus { border-color: var(--primary-500); background: var(--primary-50); }
        
        .agent-delete {
            background: none;
            border: none;
            color: var(--danger);
            cursor: pointer;
            padding: 4px;
            opacity: 0.5;
            font-size: 16px;
            transition: opacity var(--duration-fast) var(--ease-standard);
        }
        
        .agent-delete:hover { opacity: 1; }
        
        .add-agent-btn {
            width: 100%;
            padding: 12px;
            background: var(--primary-50);
            border: 1px dashed var(--primary-500);
            border-radius: var(--radius-sm);
            color: var(--primary-600);
            font-family: var(--font-sans);
            font-weight: 500;
            cursor: pointer;
            margin-top: 8px;
            transition: all var(--duration-fast) var(--ease-standard);
        }
        
        .add-agent-btn:hover { background: var(--primary-100); }
        
        .new-agent-form {
            background: var(--primary-50);
            border: 1px solid var(--primary-100);
            border-radius: var(--radius-sm);
            padding: 12px;
            margin-top: 8px;
            display: none;
        }
        
        .new-agent-form.visible { display: block; }
        
        .new-agent-form input,
        .new-agent-form textarea {
            width: 100%;
            margin-bottom: 8px;
        }
        
        .new-agent-form input {
            background: var(--surface-0);
            border: 1px solid var(--neutral-200);
            border-radius: var(--radius-xs);
            color: var(--neutral-800);
            font-family: var(--font-sans);
            font-size: 14px;
            padding: 8px;
            outline: none;
            transition: border-color var(--duration-fast) var(--ease-standard);
        }
        
        .new-agent-form input:focus { border-color: var(--primary-500); }
        
        .new-agent-form select {
            width: 100%;
            background: var(--surface-0);
            border: 1px solid var(--neutral-200);
            border-radius: var(--radius-xs);
            color: var(--neutral-700);
            font-family: var(--font-mono);
            font-size: 13px;
            padding: 8px;
            margin-bottom: 8px;
            outline: none;
            cursor: pointer;
            transition: border-color var(--duration-fast) var(--ease-standard);
        }
        
        .new-agent-form select:focus { border-color: var(--primary-500); }
        
        .new-agent-form textarea {
            background: var(--surface-0);
            border: 1px solid var(--neutral-200);
            border-radius: var(--radius-xs);
            color: var(--neutral-700);
            font-family: var(--font-mono);
            font-size: 12px;
            padding: 8px;
            resize: vertical;
            min-height: 80px;
            outline: none;
            transition: border-color var(--duration-fast) var(--ease-standard);
        }
        
        .new-agent-form textarea:focus { border-color: var(--primary-500); }
        
        .prompt-row {
            position: relative;
        }
        
        .enrich-btn {
            position: absolute;
            top: 4px;
            right: 4px;
            padding: 4px 8px;
            font-size: 11px;
            background: var(--secondary-50);
            color: var(--secondary-600);
            border: 1px solid var(--secondary-100);
            border-radius: var(--radius-xs);
            cursor: pointer;
            font-weight: 500;
            transition: all var(--duration-fast) var(--ease-standard);
        }
        
        .enrich-btn:hover { background: var(--secondary-100); }
        .enrich-btn:disabled { opacity: 0.5; cursor: wait; }
        
        .new-agent-actions {
            display: flex;
            gap: 8px;
        }
        
        .new-agent-actions button {
            flex: 1;
            padding: 8px;
            font-size: 13px;
        }
        
        .confirm-btn {
            background: var(--primary-500);
            color: white;
        }
        
        .confirm-btn:hover {
            background: var(--primary-600);
        }
        
        .cancel-btn {
            background: var(--neutral-100);
            color: var(--neutral-600);
        }
        
        .cancel-btn:hover {
            background: var(--neutral-200);
        }
        
        /* Control panel */
        .control-area {
            position: fixed;
            bottom: 0;
            left: 0;
            right: 0;
            background: linear-gradient(to top, var(--neutral-0) 0%, var(--neutral-0) 85%, transparent 100%);
            padding: 16px 32px 24px;
        }
        
        .control-container {
            max-width: 800px;
            margin: 0 auto;
            background: var(--surface-0);
            border: 1px solid var(--neutral-100);
            border-radius: var(--radius-lg);
            padding: 20px;
            box-shadow: var(--shadow-2);
        }
        
        .controls-row {
            display: flex;
            gap: 24px;
            margin-bottom: 16px;
            align-items: center;
            flex-wrap: wrap;
        }
        
        .control-group {
            display: flex;
            align-items: center;
            gap: 8px;
        }
        
        .control-group label {
            font-family: var(--font-mono);
            font-size: 12px;
            color: var(--neutral-500);
            text-transform: uppercase;
        }
        
        .control-group input[type="number"] {
            width: 80px;
            background: var(--surface-0);
            border: 1px solid var(--neutral-200);
            border-radius: var(--radius-xs);
            padding: 8px;
            font-family: var(--font-mono);
            font-size: 14px;
            color: var(--neutral-800);
            outline: none;
            transition: border-color var(--duration-fast) var(--ease-standard);
        }
        
        .control-group input[type="number"]:focus { border-color: var(--primary-500); }
        
        .input-row {
            display: flex;
            gap: 12px;
        }
        
        #user-input {
            flex: 1;
            background: var(--surface-0);
            border: 1px solid var(--neutral-200);
            border-radius: var(--radius-md);
            padding: 14px 16px;
            font-family: var(--font-sans);
            font-size: 16px;
            color: var(--neutral-800);
            outline: none;
            transition: border-color var(--duration-fast) var(--ease-standard), background var(--duration-fast) var(--ease-standard);
        }
        
        #user-input:focus { border-color: var(--primary-500); background: var(--primary-50); }
        #user-input::placeholder { color: var(--neutral-400); }
        
        button {
            padding: 12px 20px;
            border: none;
            border-radius: var(--radius-sm);
            font-family: var(--font-sans);
            font-size: 14px;
            font-weight: 600;
            cursor: pointer;
            transition: all var(--duration-fast) var(--ease-standard);
        }
        
        #send-btn {
            background: var(--primary-500);
            color: white;
            border-radius: var(--radius-pill);
            padding: 12px 24px;
        }
        
        #send-btn:hover { background: var(--primary-600); transform: translateY(-1px); box-shadow: var(--shadow-2); }
        #send-btn:disabled { opacity: 0.5; cursor: not-allowed; transform: none; box-shadow: none; }
        
        #pause-btn {
            background: var(--surface-0);
            color: var(--warning);
            border: 1px solid var(--warning);
        }
        
        #pause-btn:hover { background: rgba(245, 158, 11, 0.1); }
        #pause-btn.paused { background: var(--warning); color: white; }
        
        #stop-btn {
            background: var(--surface-0);
            color: var(--danger);
            border: 1px solid var(--danger);
        }
        
        #stop-btn:hover { background: rgba(239, 68, 68, 0.1); }
        
        #restart-btn {
            background: var(--surface-0);
            color: var(--primary-500);
            border: 1px solid var(--primary-500);
        }
        
        #restart-btn:hover { background: var(--primary-50); }
        
        /* Agent Activity Indicator */
        .agent-indicator-container {
            min-height: 32px;
            margin-top: 8px;
            display: flex;
            flex-direction: column;
            gap: 6px;
        }
        
        .agent-indicator {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 8px 14px;
            border-radius: var(--radius-sm);
            font-family: var(--font-mono);
            font-size: 13px;
            animation: indicatorFadeIn 0.2s var(--ease-standard);
        }
        
        .agent-indicator.thinking {
            background: var(--primary-50);
            border: 1px solid var(--primary-100);
            color: var(--primary-600);
        }
        
        .agent-indicator.passed {
            background: var(--neutral-50);
            border: 1px solid var(--neutral-100);
            color: var(--neutral-500);
            animation: indicatorFadeOut 3s var(--ease-standard) forwards;
        }
        
        .agent-indicator-dot {
            width: 8px;
            height: 8px;
            border-radius: 50%;
        }
        
        .agent-indicator.thinking .agent-indicator-dot {
            background: var(--info);
            animation: indicatorPulse 1.5s infinite;
        }
        
        .agent-indicator.passed .agent-indicator-dot {
            background: var(--neutral-400);
        }
        
        .agent-indicator-icon {
            font-size: 14px;
        }
        
        @keyframes indicatorFadeIn {
            from { opacity: 0; transform: translateY(-4px); }
            to { opacity: 1; transform: translateY(0); }
        }
        
        @keyframes indicatorFadeOut {
            0% { opacity: 1; }
            70% { opacity: 1; }
            100% { opacity: 0; }
        }
        
        @keyframes indicatorPulse {
            0%, 100% { opacity: 1; transform: scale(1); }
            50% { opacity: 0.5; transform: scale(0.85); }
        }
        
        @media (prefers-reduced-motion: reduce) {
            .agent-indicator, .agent-indicator-dot { animation: none; }
            .agent-indicator.passed { opacity: 0.5; }
        }
    </style>
</head>
<body>
    <button class="agents-toggle" id="agents-toggle">Agents</button>
    
    <div class="agents-panel" id="agents-panel">
        <h2>Agents</h2>
        <div class="global-section">
            <h3>Global Instructions</h3>
            <p>Shared context given to all agents (topic, rules, scenario setup)</p>
            <textarea id="global-prompt" placeholder="e.g., 'Keep responses under 150 words. The topic is quantum physics.'"></textarea>
        </div>
        <div id="agents-list"></div>
        <button class="add-agent-btn" id="add-agent-btn">+ Add Agent</button>
        <div class="new-agent-form" id="new-agent-form">
            <input type="text" id="new-agent-name" placeholder="Agent name..." />
            <select id="new-agent-model">
                <optgroup label="GPT-4 Series">
                    <option value="gpt-4o">gpt-4o (recommended)</option>
                    <option value="gpt-4o-mini">gpt-4o-mini (fast/cheap)</option>
                    <option value="gpt-4.1">gpt-4.1</option>
                    <option value="gpt-4.1-mini">gpt-4.1-mini</option>
                    <option value="gpt-4.1-nano">gpt-4.1-nano (fastest)</option>
                </optgroup>
                <optgroup label="Reasoning Models (o-series)">
                    <option value="o1">o1 (advanced reasoning)</option>
                    <option value="o1-mini">o1-mini</option>
                    <option value="o3">o3</option>
                    <option value="o3-mini">o3-mini</option>
                    <option value="o4-mini">o4-mini</option>
                </optgroup>
                <optgroup label="GPT-5 Series">
                    <option value="gpt-5.2">gpt-5.2 (latest)</option>
                </optgroup>
                <optgroup label="Legacy">
                    <option value="gpt-4-turbo">gpt-4-turbo</option>
                    <option value="gpt-3.5-turbo">gpt-3.5-turbo</option>
                </optgroup>
            </select>
            <select id="new-agent-reasoning" class="hidden" title="Reasoning effort (for o-series/GPT-5 models)">
                <option value="low">low reasoning</option>
                <option value="medium" selected>medium reasoning</option>
                <option value="high">high reasoning</option>
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
        <div class="agent-indicator-container" id="agent-indicators"></div>
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
                    <input type="number" id="delay-seconds" value="0" min="0" max="300" step="5">
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
        const newAgentReasoning = document.getElementById('new-agent-reasoning');
        const globalPromptInput = document.getElementById('global-prompt');
        
        const MODEL_OPTIONS = [
            // GPT-4 series
            'gpt-4o', 'gpt-4o-mini', 'gpt-4.1', 'gpt-4.1-mini', 'gpt-4.1-nano',
            // o-series reasoning models
            'o1', 'o1-mini', 'o3', 'o3-mini', 'o4-mini',
            // GPT-5 series
            'gpt-5.2',
            // Legacy
            'gpt-4-turbo', 'gpt-3.5-turbo'
        ];
        
        const REASONING_EFFORT_OPTIONS = ['low', 'medium', 'high'];
        
        // Models that support reasoning_effort parameter
        const REASONING_MODELS = ['o1', 'o3', 'o3-mini', 'o4-mini', 'gpt-5.2'];
        
        function supportsReasoningEffort(model) {
            return REASONING_MODELS.some(m => model && model.startsWith(m));
        }
        
        const agentIndicators = document.getElementById('agent-indicators');
        
        let messageCount = 0;
        let isPaused = false;
        let totalTokens = 0;
        let agents = [];
        let globalPrompt = '';
        let lastAgentState = null;
        let passIndicatorTimeouts = {};
        
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
                const reasoningOptions = REASONING_EFFORT_OPTIONS.map(r =>
                    `<option value="${r}" ${(agent.reasoning_effort || 'medium') === r ? 'selected' : ''}>${r}</option>`
                ).join('');
                const showReasoning = supportsReasoningEffort(agent.model || 'gpt-4o');
                card.innerHTML = `
                    <div class="agent-card-header">
                        <div class="agent-card-header-top">
                            <input type="text" class="agent-name-input" value="${escapeHtml(agent.name)}" data-idx="${idx}" data-field="name" />
                            <button class="agent-delete" data-idx="${idx}">&times;</button>
                        </div>
                        <div class="agent-card-header-selects">
                            <select class="agent-model-select" data-idx="${idx}" data-field="model">${modelOptions}</select>
                            <select class="agent-reasoning-select ${showReasoning ? '' : 'hidden'}" data-idx="${idx}" data-field="reasoning_effort" title="Reasoning effort">${reasoningOptions}</select>
                        </div>
                    </div>
                    <textarea class="agent-prompt-input" data-idx="${idx}" data-field="prompt" rows="3">${escapeHtml(agent.prompt)}</textarea>
                `;
                agentsList.appendChild(card);
            });
            
            // Bind events
            document.querySelectorAll('.agent-name-input, .agent-prompt-input, .agent-model-select, .agent-reasoning-select').forEach(input => {
                input.oninput = onAgentChange;
                input.onchange = onAgentChange;
            });
            // Special handler for model select to show/hide reasoning effort
            document.querySelectorAll('.agent-model-select').forEach(select => {
                select.onchange = (e) => {
                    onAgentChange(e);
                    const idx = parseInt(e.target.dataset.idx);
                    const reasoningSelect = document.querySelector(`.agent-reasoning-select[data-idx="${idx}"]`);
                    if (reasoningSelect) {
                        reasoningSelect.classList.toggle('hidden', !supportsReasoningEffort(e.target.value));
                    }
                };
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
            newAgentReasoning.value = 'medium';
            newAgentReasoning.classList.add('hidden');
            newAgentForm.classList.add('visible');
            addAgentBtn.style.display = 'none';
            newAgentName.focus();
        };
        
        // Show/hide reasoning effort based on model selection in new agent form
        newAgentModel.onchange = () => {
            newAgentReasoning.classList.toggle('hidden', !supportsReasoningEffort(newAgentModel.value));
        };
        
        cancelNewAgent.onclick = () => {
            newAgentForm.classList.remove('visible');
            addAgentBtn.style.display = 'block';
        };
        
        confirmNewAgent.onclick = () => {
            const name = newAgentName.value.trim();
            const prompt = newAgentPrompt.value.trim();
            const model = newAgentModel.value;
            const reasoning_effort = newAgentReasoning.value;
            
            if (!name) {
                newAgentName.focus();
                return;
            }
            
            const newAgent = { name, prompt: prompt || 'You are a helpful assistant.', model };
            // Only include reasoning_effort for models that support it
            if (supportsReasoningEffort(model)) {
                newAgent.reasoning_effort = reasoning_effort;
            }
            agents.push(newAgent);
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
                <div class="message-content" dir="auto">${escapeHtml(msg.content)}</div>
            `;
            return div;
        }
        
        function escapeHtml(text) {
            const div = document.createElement('div');
            div.textContent = text;
            return div.innerHTML;
        }
        
        function renderAgentIndicators(agentState) {
            if (!agentState) return;
            
            // Clear thinking indicator if state changed OR agent changed
            const thinkingIndicator = agentIndicators.querySelector('.thinking');
            if (thinkingIndicator) {
                const currentAgentInIndicator = thinkingIndicator.dataset.agent;
                if (agentState.state !== 'thinking' || currentAgentInIndicator !== agentState.current_agent) {
                    thinkingIndicator.remove();
                }
            }
            
            // Show thinking indicator
            if (agentState.state === 'thinking' && agentState.current_agent) {
                if (!agentIndicators.querySelector('.thinking')) {
                    const indicator = document.createElement('div');
                    indicator.className = 'agent-indicator thinking';
                    indicator.dataset.agent = agentState.current_agent;
                    indicator.innerHTML = `
                        <span class="agent-indicator-dot"></span>
                        <span>${escapeHtml(agentState.current_agent)} is thinking...</span>
                    `;
                    agentIndicators.appendChild(indicator);
                }
            }
            
            // Show passed indicators from history
            const now = Date.now() / 1000;
            const recentPasses = (agentState.pass_history || []).filter(p => now - p.time < 5);
            
            // Add new pass indicators
            recentPasses.forEach(pass => {
                const passId = `pass-${pass.agent}-${Math.floor(pass.time * 1000)}`;
                if (!agentIndicators.querySelector(`[data-pass-id="${passId}"]`) && !passIndicatorTimeouts[passId]) {
                    const indicator = document.createElement('div');
                    indicator.className = 'agent-indicator passed';
                    indicator.dataset.passId = passId;
                    indicator.innerHTML = `
                        <span class="agent-indicator-icon">↪</span>
                        <span>${escapeHtml(pass.agent)} read and passed</span>
                    `;
                    agentIndicators.appendChild(indicator);
                    
                    // Remove after animation completes (3 seconds)
                    passIndicatorTimeouts[passId] = setTimeout(() => {
                        indicator.remove();
                        delete passIndicatorTimeouts[passId];
                    }, 3000);
                }
            });
            
            lastAgentState = agentState;
        }
        
        function clearAgentIndicators() {
            agentIndicators.innerHTML = '';
            // Clear any pending timeouts
            Object.values(passIndicatorTimeouts).forEach(clearTimeout);
            passIndicatorTimeouts = {};
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
                        delay_seconds: parseInt(delayInput.value) || 0,
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
                delayInput.value = settings.delay_seconds ?? 0;
                isPaused = settings.paused || false;
                pauseBtn.textContent = isPaused ? 'Resume' : 'Pause';
                pauseBtn.classList.toggle('paused', isPaused);
                agents = settings.agents || [];
                globalPrompt = settings.global_prompt || '';
                globalPromptInput.value = globalPrompt;
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
        
        // Global prompt handler
        let globalPromptTimeout;
        globalPromptInput.oninput = () => {
            globalPrompt = globalPromptInput.value;
            clearTimeout(globalPromptTimeout);
            globalPromptTimeout = setTimeout(saveGlobalPrompt, 500);
        };
        
        async function saveGlobalPrompt() {
            try {
                await fetch('/settings', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ global_prompt: globalPrompt })
                });
            } catch (e) {
                console.error('Failed to save global prompt:', e);
            }
        }
        
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
                clearAgentIndicators();
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
                clearAgentIndicators();
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
            
            // Update agent indicators
            if (data.agent_state) {
                renderAgentIndicators(data.agent_state);
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


def load_agent_state() -> dict:
    """Load agent state from file."""
    if os.path.exists(AGENT_STATE_FILE):
        try:
            with open(AGENT_STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"current_agent": None, "state": "idle", "timestamp": 0, "pass_history": []}


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


def watch_channel_and_state():
    """Generator that yields channel content and agent state when either changes."""
    last_content = None
    last_channel_mtime = 0
    last_state_mtime = 0
    
    while True:
        try:
            changed = False
            content = ""
            
            # Check channel file
            if os.path.exists(CHANNEL_PATH):
                mtime = os.path.getmtime(CHANNEL_PATH)
                if mtime != last_channel_mtime:
                    with open(CHANNEL_PATH, 'r') as f:
                        content = f.read()
                    if content != last_content:
                        last_content = content
                        last_channel_mtime = mtime
                        changed = True
                else:
                    content = last_content or ""
            else:
                if last_content is not None:
                    last_content = None
                    changed = True
                content = ""
            
            # Check agent state file
            if os.path.exists(AGENT_STATE_FILE):
                state_mtime = os.path.getmtime(AGENT_STATE_FILE)
                if state_mtime != last_state_mtime:
                    last_state_mtime = state_mtime
                    changed = True
            
            if changed:
                yield content
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
        agent_state = load_agent_state()
        yield f"data: {json.dumps({'messages': messages, 'total_tokens': total_tokens, 'agent_state': agent_state})}\n\n"
        
        for content in watch_channel_and_state():
            messages = parse_channel(content)
            total_tokens = estimate_tokens(content)
            agent_state = load_agent_state()
            yield f"data: {json.dumps({'messages': messages, 'total_tokens': total_tokens, 'agent_state': agent_state})}\n\n"
    
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
    if 'global_prompt' in data:
        settings['global_prompt'] = str(data['global_prompt'])
    
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
