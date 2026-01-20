# 🦁 Agent Zoo

**Watch AI agents collaborate in real-time** — a multi-agent playground where GPT-5, o3, and other OpenAI models converse via a shared "Slack-like" channel with a live web UI.

```
┌─────────────────────────────────────────────────────────────┐
│  Einstein: "The universe is not playing dice..."            │
│  Feynman:  "But Al, shut up and calculate! It works."       │
│  User:     "What about quantum entanglement?"               │
│  Einstein: "Spooky action at a distance..."                 │
└─────────────────────────────────────────────────────────────┘
```

## ✨ Features

| Feature | Description |
|---------|-------------|
| **Real-time UI** | Watch the conversation unfold live in your browser |
| **Dynamic agents** | Add, edit, or remove agents mid-conversation |
| **Model selection** | GPT-5.2, GPT-4o, o3, o4-mini — pick per agent |
| **Reasoning effort** | Control how hard reasoning models "think" |
| **Enrich prompts** | AI-powered system prompt improvement |
| **User interruption** | Jump into the conversation anytime |
| **Global instructions** | Set rules all agents follow |
| **Pause & restart** | Full conversation control |
| **[PASS] detection** | Agents gracefully yield when they have nothing to add |

## 🚀 Quick Start

```bash
# Clone and install
git clone <repo-url>
cd agent_zoo
uv sync

# Set your API key
export OPENAI_API_KEY="sk-..."

# Run
uv run agent_zoo.py
```

Open **http://localhost:5000** and send a message to start the conversation.

## 📦 Requirements

- Python 3.10+
- [uv](https://docs.astral.sh/uv/) package manager
- OpenAI API key (with access to desired models)

## ⚙️ Configuration

### Agent Configuration (`params.toml`)

Define your initial agents in `params.toml`:

```toml
channel = "channel.txt"

[agent1]
name = "Einstein"
prompt = """Role: Albert Einstein
Style & Persona:
  - Thoughtful, philosophical, and reflective
  - Speaks calmly, with poetic metaphors
  - Values deep intuition over formalism
  - Occasionally dry humor, gently ironic
"""

[agent2]
name = "Feynman"
prompt = """Role: Richard Feynman
Style & Persona:
  - Energetic, witty, playful, and blunt
  - Uses simple language and vivid analogies
  - Embraces uncertainty and practical results
"""
```

### UI-Added Agents

Agents created via the web UI are persisted in `.settings.json` and survive restarts. These coexist with your `params.toml` agents.

### Global Instructions

Set rules that apply to all agents via the UI sidebar:
- "Keep responses under 150 words"
- "The topic is quantum physics"
- "Respond only in Spanish"

## 🤖 Supported Models

| Model | Type | Reasoning Effort |
|-------|------|-----------------|
| `gpt-5.2` | Latest GPT-5 | ✅ low/medium/high |
| `gpt-4o` | GPT-4 Optimized | ❌ |
| `gpt-4o-mini` | Fast & cheap | ❌ |
| `gpt-4.1` / `gpt-4.1-mini` / `gpt-4.1-nano` | GPT-4.1 series | ❌ |
| `o1` / `o1-mini` | Reasoning | ✅ |
| `o3` / `o3-mini` | Reasoning | ✅ |
| `o4-mini` | Reasoning | ✅ |

**Reasoning effort** controls how long reasoning models spend "thinking" before responding. Higher = more thorough but slower/costlier.

## 🖥️ Web UI

The web interface provides:

- **Message feed** — Real-time conversation with author attribution
- **Agent panel** (left sidebar) — Add/edit/remove agents, adjust prompts
- **Controls** (bottom bar):
  - Max tokens per response
  - Delay between agent turns
  - Pause/Resume, Restart, Stop
  - User message input

### Agent Status Indicators

- 🔵 **Thinking** — Agent is generating a response
- ↪ **Passed** — Agent read the conversation but had nothing to add

## 📁 Output

The conversation is written to `channel.txt` in a structured format:

```
================================================================================
[1] User
--------------------------------------------------------------------------------
Design a todo app

================================================================================
[2] Einstein
--------------------------------------------------------------------------------
Let me approach this with the elegance of a thought experiment...

================================================================================
[3] Feynman
--------------------------------------------------------------------------------
Forget the philosophy! Here's what we actually need...
```

## 🛠️ CLI Options

```bash
uv run agent_zoo.py                    # Uses params.toml
uv run agent_zoo.py --params my.toml   # Uses custom params file
```

## 🧪 Testing

```bash
# Run all tests
uv run pytest

# Run specific test file
uv run pytest tests/test_agent_zoo.py -v
```

## 📂 Project Structure

```
agent_zoo/
├── agent_zoo.py       # Main orchestration loop
├── server.py          # Flask web UI & API
├── params.toml        # Initial agent configuration
├── channel.txt        # Conversation output (generated)
├── .settings.json     # UI settings & agents (generated)
├── pyproject.toml     # Dependencies
└── tests/             # Test suite
```

## 🔧 How It Works

1. **Startup**: Loads agents from `params.toml` (or `.settings.json` if agents exist there)
2. **Web server**: Flask serves the real-time UI at port 5000
3. **Agent loop**: Cycles through agents, each reading the full conversation and responding
4. **[PASS] handling**: If an agent outputs `[PASS]`, it skips its turn gracefully
5. **Loop detection**: If all agents pass consecutively, the system waits for user input
6. **Persistence**: The conversation is appended to `channel.txt` after each message

## 💡 Tips

- **Start simple**: Use 2-3 agents with distinct personalities
- **Use global instructions**: Great for setting tone, topic, or language constraints
- **Experiment with models**: Mix reasoning models (o3) with fast ones (gpt-4o-mini)
- **Watch the token count**: The UI shows estimated total tokens consumed
- **Restart freely**: Hit "Restart" to clear the conversation and start fresh

## 📄 License

MIT
