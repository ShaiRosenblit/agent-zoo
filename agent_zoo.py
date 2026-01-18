#!/usr/bin/env python3
"""
Multi-Agent Channel: Two AI agents collaborate via a shared append-only text file.

Usage:
    uv run agent_zoo.py                    # Uses params.toml
    uv run agent_zoo.py --params my.toml   # Uses custom params file

The conversation runs until stopped. Users can inject messages via the web UI.
"""

import argparse
import json
import os
import time
import tomllib
from openai import OpenAI

SEPARATOR = "=" * 80
SUBSEPARATOR = "-" * 80
STOP_FILE = ".stop"
SETTINGS_FILE = ".settings.json"

DEFAULT_SETTINGS = {
    "max_tokens": 512,
    "delay_seconds": 30,
    "paused": False
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
        json.dump(settings, f)


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
    
    # Find the last header line [index] Author
    import re
    matches = list(re.finditer(r'\[(\d+)\]\s+(.+)', content))
    if matches:
        return matches[-1].group(2).strip()
    return None


# --- Agent ---

class Agent:
    def __init__(self, name: str, system_prompt: str, client: OpenAI):
        self.name = name
        self.system_prompt = system_prompt
        self.client = client

    def respond(self, channel_content: str, max_tokens: int) -> str:
        """Generate a response based on the current channel content."""
        messages = [
            {"role": "system", "content": self.system_prompt},
            {
                "role": "user",
                "content": (
                    "Here is the conversation so far:\n\n"
                    f"{channel_content}\n\n"
                    "Write your next message."
                ),
            },
        ]

        response = self.client.chat.completions.create(
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
    first = params.get("first", "agent1")
    channel_path = params.get("channel", "channel.txt")

    agent1_name = params["agent1"]["name"]
    agent1_prompt = params["agent1"]["prompt"]
    agent2_name = params["agent2"]["name"]
    agent2_prompt = params["agent2"]["prompt"]

    # Initialize OpenAI client
    client = OpenAI()

    # Create agents
    agent1 = Agent(agent1_name, agent1_prompt, client)
    agent2 = Agent(agent2_name, agent2_prompt, client)

    # Build agent lookup and turn order
    if first == "agent1":
        turn_order = [agent1, agent2]
    else:
        turn_order = [agent2, agent1]

    # Clear stop file and channel, initialize settings
    clear_stop()
    save_settings(DEFAULT_SETTINGS)
    
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
        # Load current settings
        settings = load_settings()
        
        # Check if paused
        if settings.get("paused", False):
            time.sleep(0.5)
            continue
        
        # Check if there's a new message (e.g., user injected one)
        current_count = count_messages(channel_path)
        
        if current_count > last_message_count:
            # Someone else posted - figure out who should respond
            last_author = get_last_author(channel_path)
            last_message_count = current_count
            
            # If User posted, the first agent in turn order responds
            if last_author == "User":
                current_turn = 0
            # If an agent posted, the other agent responds
            elif last_author == agent1.name:
                current_turn = 1 if turn_order[1].name == agent2.name else 0
            elif last_author == agent2.name:
                current_turn = 0 if turn_order[0].name == agent1.name else 1
        
        # Get current agent
        agent = turn_order[current_turn % 2]
        
        # Read current channel state
        channel_content = read_channel(channel_path)

        # Generate response with current max_tokens setting
        max_tokens = settings.get("max_tokens", 512)
        response = agent.respond(channel_content, max_tokens)

        # Check stop again before writing
        if should_stop():
            break

        # Append to channel
        message_index = count_messages(channel_path) + 1
        append_message(channel_path, message_index, agent.name, response)

        # Progress indicator
        preview = response[:60].replace("\n", " ")
        print(f"[{message_index}] {agent.name}: {preview}...")

        last_message_count = message_index
        current_turn = (current_turn + 1) % 2

        # Wait based on delay setting (check for stop/pause during wait)
        delay = settings.get("delay_seconds", 30)
        wait_start = time.time()
        while time.time() - wait_start < delay:
            if should_stop():
                break
            # Re-check settings in case user changed them
            settings = load_settings()
            if settings.get("paused", False):
                break
            # Check if user posted a new message
            if count_messages(channel_path) > last_message_count:
                break
            time.sleep(0.3)

    clear_stop()
    print(f"\nStopped. Conversation saved to {channel_path}")


if __name__ == "__main__":
    main()
