# Agent Zoo

Two AI agents collaborate via a shared "Slack-like" text channel.

## Setup

```bash
export OPENAI_API_KEY="your-key-here"
```

## Usage

Edit `params.toml` to configure your run, then:

```bash
uv run agent_zoo.py
```

Or use a custom params file:

```bash
uv run agent_zoo.py --params my_experiment.toml
```

## Parameters (params.toml)

```toml
message = "Design a todo app for busy parents"
max_messages = 6
first = "agent1"      # or "agent2"
channel = "channel.txt"

[agent1]
name = "Planner"
prompt = "You are a Planner. You generate structured plans..."

[agent2]
name = "Critic"
prompt = "You are a Critic. You challenge assumptions..."
```

## Output

The conversation is written to `channel.txt` (or your specified path):

```
================================================================================
[1] User
--------------------------------------------------------------------------------
Design a todo app for busy parents

================================================================================
[2] Planner
--------------------------------------------------------------------------------
Here's a structured plan for a parent-focused todo app...

================================================================================
[3] Critic
--------------------------------------------------------------------------------
I see several potential issues with this approach...
```

## How It Works

1. Your initial message is posted to the channel as "User"
2. Agents take turns reading the full channel and appending one message
3. Strict alternation continues until `--max-messages` agent messages are written
4. No automatic stopping, summarizing, or judging - you control when it ends
