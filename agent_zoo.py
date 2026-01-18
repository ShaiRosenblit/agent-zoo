#!/usr/bin/env python3
"""
Multi-Agent Channel: Multiple AI agents collaborate via a shared append-only text file.

Usage:
    uv run agent_zoo.py                    # Uses params.toml
    uv run agent_zoo.py --params my.toml   # Uses custom params file

The conversation runs until stopped. Users can add/edit agents via the web UI.
"""

import argparse
import json
import os
import re
import time
import tomllib
from openai import OpenAI

SEPARATOR = "=" * 80
SUBSEPARATOR = "-" * 80
STOP_FILE = ".stop"
SETTINGS_FILE = ".settings.json"

DEFAULT_SETTINGS = {
    "max_tokens": 512,
    "delay_seconds": 5,
    "paused": False,
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


# --- Agent ---

def call_agent(name: str, prompt: str, channel_content: str, max_tokens: int, client: OpenAI) -> str:
    """Generate a response for an agent."""
    messages = [
        {"role": "system", "content": prompt},
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
        model="gpt-4o",
        messages=messages,
        max_tokens=max_tokens,
    )

    return response.choices[0].message.content.strip()


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

    message = params["message"]
    channel_path = params.get("channel", "channel.txt")

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

    # Clear stop file and channel, initialize settings with agents
    clear_stop()
    
    initial_settings = {
        **DEFAULT_SETTINGS,
        "agents": initial_agents
    }
    save_settings(initial_settings)
    
    if os.path.exists(channel_path):
        os.remove(channel_path)

    message_index = 1
    append_message(channel_path, message_index, "User", message)
    print(f"[{message_index}] User: {message[:60]}...")

    # Main loop: runs until stopped
    current_turn = 0
    last_message_count = 1

    print("\nConversation running. Stop via web UI or Ctrl+C.\n")

    while not should_stop():
        # Load current settings (agents may have changed)
        settings = load_settings()
        agents = settings.get("agents", [])
        
        # Check if paused or no agents
        if settings.get("paused", False) or not agents:
            time.sleep(0.5)
            continue
        
        # Check if there's a new message (e.g., user injected one)
        current_count = count_messages(channel_path)
        
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

        # Generate response
        max_tokens = settings.get("max_tokens", 512)
        response = call_agent(agent["name"], agent["prompt"], channel_content, max_tokens, client)

        # Check stop again before writing
        if should_stop():
            break

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
            time.sleep(0.3)

    clear_stop()
    print(f"\nStopped. Conversation saved to {channel_path}")


if __name__ == "__main__":
    main()
