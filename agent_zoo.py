#!/usr/bin/env python3
"""
Multi-Agent Channel: Multiple AI agents collaborate via a shared append-only text file.

Usage:
    uv run agent_zoo.py                    # Uses params.toml
    uv run agent_zoo.py --params my.toml   # Uses custom params file

The conversation runs until stopped. Users can add/edit agents via the web UI.
Conversation starts when user sends the first message from the UI.
"""

import argparse
import json
import os
import re
import threading
import time
import tomllib
from openai import OpenAI

SEPARATOR = "=" * 80
SUBSEPARATOR = "-" * 80
STOP_FILE = ".stop"
SETTINGS_FILE = ".settings.json"
CHANNEL_PATH = "channel.txt"

DEFAULT_SETTINGS = {
    "max_tokens": 512,
    "delay_seconds": 5,
    "paused": False,
    "global_prompt": "",
    "agents": []
}


# --- Settings ---

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


# --- Global Context ---

ENVIRONMENT_CONTEXT = """You are participating in a multi-agent conversation channel.
Multiple AI agents and humans communicate via a shared text channel.
Messages are numbered and attributed to their author.
Respond naturally as yourself, acknowledging other participants when relevant."""


def build_participants_context(agents: list[dict], current_agent_name: str) -> str:
    """Build a description of all participants for the global context."""
    lines = ["Current participants:"]
    
    for agent in agents:
        name = agent.get("name", "Unknown")
        # Extract first meaningful line from prompt as the public description
        prompt = agent.get("prompt", "")
        first_line = prompt.split("\n")[0].strip() if prompt else ""
        # Clean up common prefixes
        for prefix in ["Role:", "You are", "You're"]:
            if first_line.lower().startswith(prefix.lower()):
                first_line = first_line[len(prefix):].strip()
        description = first_line[:80] if first_line else "AI assistant"
        
        marker = " (you)" if name == current_agent_name else ""
        lines.append(f"- {name}{marker}: {description}")
    
    lines.append("- User: Human participant")
    return "\n".join(lines)


def build_global_context(agents: list[dict], current_agent_name: str, user_instructions: str) -> str:
    """Assemble the complete global context from all three layers."""
    parts = [ENVIRONMENT_CONTEXT]
    
    # Add participants context
    participants = build_participants_context(agents, current_agent_name)
    parts.append(participants)
    
    # Add user instructions if provided
    if user_instructions and user_instructions.strip():
        parts.append(f"Additional instructions from the session host:\n{user_instructions.strip()}")
    
    return "\n\n".join(parts)


# --- Agent ---

def call_agent(name: str, prompt: str, channel_content: str, max_tokens: int, model: str, client: OpenAI, global_context: str = "") -> str:
    """Generate a response for an agent."""
    # Combine global context with agent's personal prompt
    if global_context:
        full_prompt = f"{global_context}\n\n---\n\nYour personal instructions:\n{prompt}"
    else:
        full_prompt = prompt
    
    messages = [
        {"role": "system", "content": full_prompt},
        {
            "role": "user",
            "content": (
                "Here is the conversation so far:\n\n"
                f"{channel_content}\n\n"
                "Write your next message."
            ),
        },
    ]
    
    response = client.chat.completions.create(
        model=model,
        messages=messages,
        max_completion_tokens=max_tokens,
    )

    content = response.choices[0].message.content
    return content.strip() if content else "(no response)"


# --- Main ---

def load_params(path: str) -> dict:
    """Load parameters from a TOML file."""
    with open(path, "rb") as f:
        return tomllib.load(f)


def should_stop() -> bool:
    """Check if stop signal exists."""
    return os.path.exists(STOP_FILE)


def clear_stop():
    """Clear the stop signal."""
    if os.path.exists(STOP_FILE):
        os.remove(STOP_FILE)


def start_server():
    """Start the Flask web server in a background thread."""
    from server import app
    import logging
    
    # Suppress Flask logs
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    app.run(debug=False, threaded=True, use_reloader=False)


def main():
    parser = argparse.ArgumentParser(
        description="Run a multi-agent conversation via a shared channel."
    )
    parser.add_argument(
        "--params", "-p",
        default="params.toml",
        help="Path to params file (default: params.toml)."
    )

    args = parser.parse_args()

    # Load params from file
    params = load_params(args.params)
    channel_path = params.get("channel", CHANNEL_PATH)

    # Build initial agents list from params
    initial_agents = []
    i = 1
    while True:
        key = f"agent{i}"
        if key in params:
            initial_agents.append({
                "name": params[key]["name"],
                "prompt": params[key]["prompt"]
            })
            i += 1
        else:
            break

    # Initialize OpenAI client
    client = OpenAI()

    # Clear stop file, initialize settings
    clear_stop()
    
    # Load existing settings (preserve UI-added agents) or use params.toml agents
    existing_settings = load_settings()
    if not existing_settings.get("agents"):
        # No agents in settings, use params.toml agents
        existing_settings["agents"] = initial_agents
        save_settings(existing_settings)
    
    # Clear channel file
    if os.path.exists(channel_path):
        os.remove(channel_path)

    # Start web server in background thread
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    print("Agent Zoo running at http://localhost:5000")
    print("Send a message in the UI to start the conversation.\n")

    # Wait for first message
    while not should_stop():
        if count_messages(channel_path) > 0:
            break
        time.sleep(0.3)

    if should_stop():
        clear_stop()
        print("Stopped before conversation started.")
        return

    print("Conversation started!\n")

    # Main loop: runs until stopped
    current_turn = 0
    last_message_count = count_messages(channel_path)

    while not should_stop():
        # Load current settings (agents may have changed)
        settings = load_settings()
        agents = settings.get("agents", [])
        
        # Check if paused or no agents
        if settings.get("paused", False) or not agents:
            time.sleep(0.5)
            continue
        
        # Check current message count (may have been reset by restart)
        current_count = count_messages(channel_path)
        
        # Handle restart (channel was cleared)
        if current_count == 0:
            print("\nConversation restarted. Waiting for first message...")
            last_message_count = 0
            current_turn = 0
            while not should_stop() and count_messages(channel_path) == 0:
                time.sleep(0.3)
            if should_stop():
                break
            print("Conversation started!\n")
            current_count = count_messages(channel_path)
            last_message_count = current_count
        
        # Check if there's a new message
        if current_count > last_message_count:
            last_author = get_last_author(channel_path)
            last_message_count = current_count
            
            # If User posted, reset to first agent
            if last_author == "User":
                current_turn = 0
            else:
                # Find which agent posted and move to next
                for idx, agent in enumerate(agents):
                    if agent["name"] == last_author:
                        current_turn = (idx + 1) % len(agents)
                        break
        
        # Get current agent (handle case where agents list changed)
        current_turn = current_turn % len(agents)
        agent = agents[current_turn]
        
        # Read current channel state
        channel_content = read_channel(channel_path)

        # Build global context for this agent
        user_instructions = settings.get("global_prompt", "")
        global_context = build_global_context(agents, agent["name"], user_instructions)

        # Generate response
        max_tokens = settings.get("max_tokens", 512)
        model = agent.get("model", "gpt-4o")
        response = call_agent(agent["name"], agent["prompt"], channel_content, max_tokens, model, client, global_context)

        # Check stop again before writing
        if should_stop():
            break
        
        # Check if channel was cleared during generation
        if count_messages(channel_path) == 0:
            continue

        # Append to channel
        message_index = count_messages(channel_path) + 1
        append_message(channel_path, message_index, agent["name"], response)

        # Progress indicator
        preview = response[:60].replace("\n", " ")
        print(f"[{message_index}] {agent['name']}: {preview}...")

        last_message_count = message_index
        current_turn = (current_turn + 1) % len(agents)

        # Wait based on delay setting
        delay = settings.get("delay_seconds", 5)
        wait_start = time.time()
        while time.time() - wait_start < delay:
            if should_stop():
                break
            settings = load_settings()
            if settings.get("paused", False):
                break
            if count_messages(channel_path) > last_message_count:
                break
            # Check for restart
            if count_messages(channel_path) == 0:
                break
            time.sleep(0.3)

    clear_stop()
    print(f"\nStopped. Conversation saved to {channel_path}")


if __name__ == "__main__":
    main()
