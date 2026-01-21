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
import os
import threading
import time
import tomllib
from openai import OpenAI

from shared import (
    # Constants
    CHANNEL_PATH,
    # Functions
    get_model_capabilities,
    load_settings, save_settings,
    update_agent_state, clear_agent_state, all_agents_passed,
    read_channel, append_message, count_messages, get_last_author,
    should_stop, clear_stop,
)


# --- Global Context ---

ENVIRONMENT_CONTEXT = """You are participating in a multi-agent conversation channel.
Multiple AI agents and humans communicate via a shared text channel.
Messages are numbered and attributed to their author.
Respond naturally as yourself, acknowledging other participants when relevant.

CRITICAL - When to use [PASS]:
If you have nothing meaningful to add, you MUST respond with EXACTLY the text [PASS] and nothing else.
Do NOT say "I'm quiet", "שותק", "waiting", or any variation - just [PASS].
Do NOT write "(no response)" or leave empty - write [PASS].

Use [PASS] when:
- The conversation doesn't require your input
- Another participant already covered what you would say  
- You're waiting for more context before contributing
- The conversation is stuck in a loop asking for user input

IMPORTANT: Avoid "polite deadlock" loops where agents repeatedly ask the user what they want.
If agents keep asking "what do you need?" without progress:
- Take initiative: propose a specific topic or make a concrete suggestion
- Or respond with [PASS] (literally just that text) to let others drive
- Do NOT keep rephrasing "tell me what you want" - either DO something or [PASS]"""


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

def call_agent(name: str, prompt: str, channel_content: str, max_tokens: int, 
               model: str, client: OpenAI, global_context: str = "",
               reasoning_effort: str | None = None) -> str:
    """Generate a response for an agent.
    
    Automatically handles API differences between model families:
    - GPT-4 series: uses 'system' role
    - o-series/GPT-5: uses 'developer' role, supports reasoning_effort
    """
    capabilities = get_model_capabilities(model)
    instruction_role = capabilities["role"]
    
    # Combine global context with agent's personal prompt
    if global_context:
        full_prompt = f"{global_context}\n\n---\n\nYour personal instructions:\n{prompt}"
    else:
        full_prompt = prompt
    
    messages = [
        {"role": instruction_role, "content": full_prompt},
        {
            "role": "user",
            "content": (
                "Here is the conversation so far:\n\n"
                f"{channel_content}\n\n"
                "Write your next message."
            ),
        },
    ]
    
    # Build kwargs based on model capabilities
    kwargs = {
        "model": model,
        "messages": messages,
        "max_completion_tokens": max_tokens,
    }
    
    # Add reasoning_effort for models that support it
    if capabilities["supports_reasoning_effort"] and reasoning_effort:
        kwargs["reasoning_effort"] = reasoning_effort
    
    response = client.chat.completions.create(**kwargs)

    choice = response.choices[0]
    message = choice.message
    
    # Extract content - reasoning models may have content in different places
    content = message.content
    
    # Handle empty content from API
    if not content:
        # Check for refusal
        refusal = getattr(message, 'refusal', None)
        if refusal and isinstance(refusal, str):
            return f"[Refused: {refusal}]"
        return "(no response)"
    
    return content.strip()


# --- Params Loading ---

def load_params(path: str) -> dict:
    """Load parameters from a TOML file."""
    with open(path, "rb") as f:
        return tomllib.load(f)


def load_agents_from_params(params: dict) -> list[dict]:
    """Extract agents list from params dict."""
    agents = []
    i = 1
    while True:
        key = f"agent{i}"
        if key in params:
            agents.append({
                "name": params[key]["name"],
                "prompt": params[key]["prompt"]
            })
            i += 1
        else:
            break
    return agents


# --- Server ---

def start_server():
    """Start the Flask web server in a background thread."""
    from server import app
    import logging
    
    # Suppress Flask logs
    log = logging.getLogger('werkzeug')
    log.setLevel(logging.ERROR)
    
    app.run(debug=False, threaded=True, use_reloader=False)


# --- Main Loop Components ---

def initialize_session(args) -> tuple[dict, str, OpenAI]:
    """Initialize a new session: load params, setup files, start server."""
    params = load_params(args.params)
    channel_path = params.get("channel", CHANNEL_PATH)
    initial_agents = load_agents_from_params(params)
    
    client = OpenAI()
    
    # Clear stop file, agent state
    clear_stop()
    clear_agent_state()
    
    # Load existing settings or use params.toml agents
    existing_settings = load_settings()
    if not existing_settings.get("agents"):
        existing_settings["agents"] = initial_agents
        save_settings(existing_settings)
    
    # Clear channel file
    if os.path.exists(channel_path):
        os.remove(channel_path)
    
    # Start web server
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    
    print("Agent Zoo running at http://localhost:5000")
    print("Send a message in the UI to start the conversation.\n")
    
    return params, channel_path, client


def wait_for_first_message(channel_path: str) -> bool:
    """Wait for the first message. Returns True if message received, False if stopped."""
    while not should_stop():
        if count_messages(channel_path) > 0:
            return True
        time.sleep(0.3)
    return False


def wait_for_user_after_all_pass(channel_path: str, last_message_count: int) -> tuple[bool, int]:
    """Wait for user input after all agents have passed.
    
    Returns (should_continue, new_last_message_count).
    """
    print("    [all agents passed - waiting for user input]")
    while not should_stop():
        time.sleep(0.5)
        new_count = count_messages(channel_path)
        if new_count == 0:  # Restart
            return True, 0
        if new_count > last_message_count:
            last_author = get_last_author(channel_path)
            if last_author == "User":
                clear_agent_state()  # Reset pass history
                return True, new_count
    return False, last_message_count


def process_agent_turn(agent: dict, channel_path: str, settings: dict, client: OpenAI, agents: list[dict]) -> str | None:
    """Process a single agent's turn.
    
    Returns the response, or None if turn should be skipped.
    """
    channel_content = read_channel(channel_path)
    
    # Build global context
    user_instructions = settings.get("global_prompt", "")
    global_context = build_global_context(agents, agent["name"], user_instructions)
    
    # Update state to "thinking"
    update_agent_state(agent["name"], "thinking")
    
    # Generate response
    max_tokens = settings.get("max_tokens", 512)
    model = agent.get("model", "gpt-4o")
    reasoning_effort = agent.get("reasoning_effort", settings.get("default_reasoning_effort"))
    
    response = call_agent(
        agent["name"], agent["prompt"], channel_content, 
        max_tokens, model, client, global_context, reasoning_effort
    )
    
    return response


def handle_delay(settings: dict, channel_path: str, last_message_count: int):
    """Handle delay between agent turns, with early exit conditions."""
    delay = settings.get("delay_seconds", 0)
    wait_start = time.time()
    
    while time.time() - wait_start < delay:
        if should_stop():
            break
        settings = load_settings()
        if settings.get("paused", False):
            break
        if count_messages(channel_path) > last_message_count:
            break
        if count_messages(channel_path) == 0:  # Restart
            break
        time.sleep(0.3)


def run_conversation_loop(channel_path: str, client: OpenAI):
    """Run the main conversation loop."""
    current_turn = 0
    last_message_count = count_messages(channel_path)
    
    while not should_stop():
        settings = load_settings()
        agents = settings.get("agents", [])
        
        # Check if paused or no agents
        if settings.get("paused", False) or not agents:
            time.sleep(0.5)
            continue
        
        # Check for restart (channel was cleared)
        current_count = count_messages(channel_path)
        if current_count == 0:
            print("\nConversation restarted. Waiting for first message...")
            clear_agent_state()
            last_message_count = 0
            current_turn = 0
            if not wait_for_first_message(channel_path):
                break
            print("Conversation started!\n")
            current_count = count_messages(channel_path)
            last_message_count = current_count
        
        # Check for new messages and update turn order
        if current_count > last_message_count:
            last_author = get_last_author(channel_path)
            last_message_count = current_count
            
            if last_author == "User":
                current_turn = 0
            else:
                for idx, agent in enumerate(agents):
                    if agent["name"] == last_author:
                        current_turn = (idx + 1) % len(agents)
                        break
        
        # Get current agent
        current_turn = current_turn % len(agents)
        agent = agents[current_turn]
        
        # Process agent turn
        response = process_agent_turn(agent, channel_path, settings, client, agents)
        
        # Check stop after generation
        if should_stop():
            update_agent_state(agent["name"], "idle")
            break
        
        # Check if channel was cleared during generation
        if count_messages(channel_path) == 0:
            update_agent_state(agent["name"], "idle")
            continue
        
        # Handle [PASS] response (also treat "(no response)" as a pass - model sometimes ignores [PASS] instruction)
        response_stripped = response.strip() if response else ""
        is_pass = response_stripped in ("[PASS]", "(no response)", "")
        if is_pass:
            update_agent_state(agent["name"], "passed")
            print(f"    {agent['name']}: [passed]")
            current_turn = (current_turn + 1) % len(agents)
            
            # Check if all agents have passed
            agent_names = [a["name"] for a in agents]
            if all_agents_passed(agent_names):
                should_continue, last_message_count = wait_for_user_after_all_pass(channel_path, last_message_count)
                if not should_continue:
                    break
                current_turn = 0
            continue
        
        # Append response to channel
        message_index = count_messages(channel_path) + 1
        append_message(channel_path, message_index, agent["name"], response)
        update_agent_state(agent["name"], "responded")
        
        # Progress indicator
        preview = response[:60].replace("\n", " ")
        print(f"[{message_index}] {agent['name']}: {preview}...")
        
        last_message_count = message_index
        current_turn = (current_turn + 1) % len(agents)
        
        # Handle delay
        handle_delay(settings, channel_path, last_message_count)


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
    
    # Initialize session
    params, channel_path, client = initialize_session(args)
    
    # Wait for first message
    if not wait_for_first_message(channel_path):
        clear_stop()
        print("Stopped before conversation started.")
        return
    
    print("Conversation started!\n")
    
    # Run main loop
    run_conversation_loop(channel_path, client)
    
    # Cleanup
    clear_stop()
    clear_agent_state()
    print(f"\nStopped. Conversation saved to {channel_path}")


if __name__ == "__main__":
    main()
