# Agent Zoo

Multiple AI agents collaborate via a shared "Slack-like" text channel with a real-time web UI.

## Setup

```bash
# Install dependencies
uv sync

# Set your OpenAI API key
export OPENAI_API_KEY="your-key-here"
```

## Usage

Run both processes:

```bash
# Terminal 1 - Web UI
uv run server.py

# Terminal 2 - Agent runner
uv run agent_zoo.py
```

Open http://localhost:5000 and send a message to start the conversation.

## Features

- **Real-time web UI** - Watch the conversation unfold live
- **Dynamic agents** - Add, edit, or remove agents mid-conversation
- **Model selection** - Choose GPT-5, GPT-4o, etc. per agent
- **Enrich prompts** - AI-powered system prompt improvement
- **User interruption** - Jump into the conversation anytime
- **Controls** - Pause, restart, adjust delay and token limits

## Configuration

Initial agents are loaded from `params.toml`:

```toml
channel = "channel.txt"

[agent1]
name = "Planner"
prompt = "You are a Planner. You generate structured plans..."

[agent2]
name = "Critic"
prompt = "You are a Critic. You challenge assumptions..."
```

Agents added via the UI are saved to `.settings.json` and persist across restarts.

## Output

The conversation is written to `channel.txt`:

```
================================================================================
[1] User
--------------------------------------------------------------------------------
Design a todo app

================================================================================
[2] Planner
--------------------------------------------------------------------------------
Here's a structured plan...

================================================================================
[3] Critic
--------------------------------------------------------------------------------
I see several potential issues...
```
