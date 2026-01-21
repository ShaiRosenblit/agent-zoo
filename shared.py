#!/usr/bin/env python3
"""
Shared constants, configuration, and utilities for Agent Zoo.

This module provides common functionality used by both agent_zoo.py and server.py:
- File path constants
- Settings management  
- Agent state tracking
- Channel operations
- Model capabilities
"""

import json
import os
import re
import time

# --- File Path Constants ---

SEPARATOR = "=" * 80
SUBSEPARATOR = "-" * 80
STOP_FILE = ".stop"
SETTINGS_FILE = ".settings.json"
CHANNEL_PATH = "channel.txt"
AGENT_STATE_FILE = ".agent_state.json"

# --- Default Settings ---

DEFAULT_SETTINGS = {
    "max_tokens": 512,
    "delay_seconds": 0,
    "paused": False,
    "global_prompt": "",
    "agents": [],
    "default_reasoning_effort": "medium"
}

# --- Model Capabilities ---

MODEL_CAPABILITIES = {
    # GPT-4 series - standard behavior (system role, supports temperature)
    "gpt-4o": {"role": "system", "supports_temperature": True, "supports_reasoning_effort": False},
    "gpt-4o-mini": {"role": "system", "supports_temperature": True, "supports_reasoning_effort": False},
    "gpt-4.1": {"role": "system", "supports_temperature": True, "supports_reasoning_effort": False},
    "gpt-4.1-mini": {"role": "system", "supports_temperature": True, "supports_reasoning_effort": False},
    "gpt-4.1-nano": {"role": "system", "supports_temperature": True, "supports_reasoning_effort": False},
    "gpt-4-turbo": {"role": "system", "supports_temperature": True, "supports_reasoning_effort": False},
    "gpt-3.5-turbo": {"role": "system", "supports_temperature": True, "supports_reasoning_effort": False},
    
    # o-series reasoning models - developer role, no temperature, supports reasoning_effort
    "o1": {"role": "developer", "supports_temperature": False, "supports_reasoning_effort": True},
    "o1-mini": {"role": "developer", "supports_temperature": False, "supports_reasoning_effort": False},
    "o3": {"role": "developer", "supports_temperature": False, "supports_reasoning_effort": True},
    "o3-mini": {"role": "developer", "supports_temperature": False, "supports_reasoning_effort": True},
    "o4-mini": {"role": "developer", "supports_temperature": False, "supports_reasoning_effort": True},
    
    # GPT-5 series - developer role with reasoning
    "gpt-5.2": {"role": "developer", "supports_temperature": False, "supports_reasoning_effort": True},
}


def get_model_capabilities(model: str) -> dict:
    """Get capabilities for a model, with fallback detection for unknown models."""
    if model in MODEL_CAPABILITIES:
        return MODEL_CAPABILITIES[model]
    # Fallback: detect by prefix for unknown model versions
    if model.startswith(("o1", "o3", "o4")):
        return {"role": "developer", "supports_temperature": False, "supports_reasoning_effort": True}
    if model.startswith("gpt-5"):
        return {"role": "developer", "supports_temperature": False, "supports_reasoning_effort": True}
    # Default to GPT-4 style for unknown models
    return {"role": "system", "supports_temperature": True, "supports_reasoning_effort": False}


# --- Settings Management ---

def load_settings() -> dict:
    """Load settings from file, or return defaults."""
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


# --- Agent State Management ---

def load_agent_state() -> dict:
    """Load agent state from file."""
    if os.path.exists(AGENT_STATE_FILE):
        try:
            with open(AGENT_STATE_FILE, "r") as f:
                return json.load(f)
        except Exception:
            pass
    return {"current_agent": None, "state": "idle", "timestamp": 0, "pass_history": []}


def update_agent_state(agent_name: str, state: str) -> None:
    """Update agent state (thinking, passed, responded, idle)."""
    current = load_agent_state()
    current["current_agent"] = agent_name
    current["state"] = state
    current["timestamp"] = time.time()
    
    # Track passes in history (keep last 10 seconds worth)
    if state == "passed":
        current["pass_history"].append({"agent": agent_name, "time": current["timestamp"]})
    
    # Clean old pass history (older than 10 seconds)
    cutoff = time.time() - 10
    current["pass_history"] = [p for p in current["pass_history"] if p["time"] > cutoff]
    
    with open(AGENT_STATE_FILE, "w") as f:
        json.dump(current, f)


def clear_agent_state() -> None:
    """Clear agent state file."""
    if os.path.exists(AGENT_STATE_FILE):
        os.remove(AGENT_STATE_FILE)


def all_agents_passed(agent_names: list[str]) -> bool:
    """Check if all agents have passed in recent history (loop detection)."""
    state = load_agent_state()
    pass_history = state.get("pass_history", [])
    
    if not pass_history or not agent_names:
        return False
    
    # Check if every agent has passed at least once in recent history
    passed_agents = {p["agent"] for p in pass_history}
    return all(name in passed_agents for name in agent_names)


# --- Channel Operations ---

def read_channel(path: str) -> str:
    """Read the entire channel file. Returns empty string if file doesn't exist."""
    if not os.path.exists(path):
        return ""
    with open(path, "r") as f:
        return f.read()


def append_message(path: str, index: int, author: str, content: str) -> None:
    """Append a message to the channel file."""
    with open(path, "a") as f:
        f.write(f"{SEPARATOR}\n")
        f.write(f"[{index}] {author}\n")
        f.write(f"{SUBSEPARATOR}\n")
        f.write(f"{content}\n\n")


def count_messages(path: str) -> int:
    """Count messages in the channel."""
    content = read_channel(path)
    if not content.strip():
        return 0
    return content.count(SEPARATOR)


def get_last_author(path: str) -> str | None:
    """Get the author of the last message."""
    content = read_channel(path)
    if not content.strip():
        return None
    
    matches = list(re.finditer(r'\[(\d+)\]\s+(.+)', content))
    if matches:
        return matches[-1].group(2).strip()
    return None


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
            
            msg_content = '\n'.join(lines[content_start:]).strip()
            
            messages.append({
                'index': index,
                'author': author,
                'content': msg_content
            })
    
    return messages


def estimate_tokens(text: str) -> int:
    """Estimate token count (roughly 4 chars per token for English)."""
    return len(text) // 4


# --- Stop Signal Management ---

def should_stop() -> bool:
    """Check if stop signal exists."""
    return os.path.exists(STOP_FILE)


def clear_stop() -> None:
    """Clear the stop signal."""
    if os.path.exists(STOP_FILE):
        os.remove(STOP_FILE)

