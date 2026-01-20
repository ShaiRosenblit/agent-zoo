"""Tests for server.py Flask API endpoints and utilities."""

import json
import os
import pytest

import server


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Create a Flask test client with isolated file paths."""
    # Isolate file paths to tmp_path
    monkeypatch.setattr(server, "CHANNEL_PATH", str(tmp_path / "channel.txt"))
    monkeypatch.setattr(server, "STOP_FILE", str(tmp_path / ".stop"))
    monkeypatch.setattr(server, "SETTINGS_FILE", str(tmp_path / ".settings.json"))
    
    server.app.config["TESTING"] = True
    with server.app.test_client() as test_client:
        yield test_client


@pytest.fixture
def settings_file(tmp_path, monkeypatch):
    """Provide path to isolated settings file."""
    path = tmp_path / ".settings.json"
    monkeypatch.setattr(server, "SETTINGS_FILE", str(path))
    return path


class TestGetSettings:
    """Tests for GET /settings endpoint."""

    def test_get_settings_returns_defaults(self, client, settings_file):
        """GET /settings returns default settings when no file exists."""
        response = client.get("/settings")
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["max_tokens"] == 512
        assert data["delay_seconds"] == 5
        assert data["paused"] is False
        assert data["global_prompt"] == ""
        assert data["agents"] == []

    def test_get_settings_returns_saved_settings(self, client, settings_file):
        """GET /settings returns previously saved settings."""
        settings_file.write_text(json.dumps({
            "max_tokens": 1024,
            "delay_seconds": 10,
            "paused": True,
            "global_prompt": "Test prompt",
            "agents": [{"name": "Bot", "prompt": "Hello"}]
        }))
        
        response = client.get("/settings")
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["max_tokens"] == 1024
        assert data["delay_seconds"] == 10
        assert data["paused"] is True
        assert data["global_prompt"] == "Test prompt"
        assert len(data["agents"]) == 1


class TestPostSettings:
    """Tests for POST /settings endpoint."""

    def test_post_settings_updates_max_tokens(self, client, settings_file):
        """POST /settings updates max_tokens."""
        response = client.post(
            "/settings",
            json={"max_tokens": 2048},
            content_type="application/json"
        )
        
        assert response.status_code == 200
        assert response.get_json()["ok"] is True
        
        # Verify saved
        saved = json.loads(settings_file.read_text())
        assert saved["max_tokens"] == 2048

    def test_post_settings_updates_delay_seconds(self, client, settings_file):
        """POST /settings updates delay_seconds."""
        response = client.post(
            "/settings",
            json={"delay_seconds": 15},
            content_type="application/json"
        )
        
        assert response.status_code == 200
        saved = json.loads(settings_file.read_text())
        assert saved["delay_seconds"] == 15

    def test_post_settings_updates_paused(self, client, settings_file):
        """POST /settings updates paused state."""
        response = client.post(
            "/settings",
            json={"paused": True},
            content_type="application/json"
        )
        
        assert response.status_code == 200
        saved = json.loads(settings_file.read_text())
        assert saved["paused"] is True

    def test_post_settings_updates_global_prompt(self, client, settings_file):
        """POST /settings updates global_prompt."""
        response = client.post(
            "/settings",
            json={"global_prompt": "Be concise."},
            content_type="application/json"
        )
        
        assert response.status_code == 200
        saved = json.loads(settings_file.read_text())
        assert saved["global_prompt"] == "Be concise."

    def test_post_settings_clamps_max_tokens_minimum(self, client, settings_file):
        """POST /settings clamps max_tokens to minimum of 100."""
        client.post("/settings", json={"max_tokens": 50})
        
        saved = json.loads(settings_file.read_text())
        assert saved["max_tokens"] == 100

    def test_post_settings_clamps_max_tokens_maximum(self, client, settings_file):
        """POST /settings clamps max_tokens to maximum of 4000."""
        client.post("/settings", json={"max_tokens": 10000})
        
        saved = json.loads(settings_file.read_text())
        assert saved["max_tokens"] == 4000

    def test_post_settings_clamps_delay_minimum(self, client, settings_file):
        """POST /settings clamps delay_seconds to minimum of 0."""
        client.post("/settings", json={"delay_seconds": -10})
        
        saved = json.loads(settings_file.read_text())
        assert saved["delay_seconds"] == 0

    def test_post_settings_clamps_delay_maximum(self, client, settings_file):
        """POST /settings clamps delay_seconds to maximum of 300."""
        client.post("/settings", json={"delay_seconds": 999})
        
        saved = json.loads(settings_file.read_text())
        assert saved["delay_seconds"] == 300

    def test_post_settings_partial_update(self, client, settings_file):
        """POST /settings does partial updates, preserving other fields."""
        # Set initial state
        settings_file.write_text(json.dumps({
            "max_tokens": 512,
            "delay_seconds": 5,
            "paused": False,
            "global_prompt": "Original",
            "agents": [{"name": "Bot"}]
        }))
        
        # Update only one field
        client.post("/settings", json={"max_tokens": 1024})
        
        saved = json.loads(settings_file.read_text())
        assert saved["max_tokens"] == 1024
        assert saved["global_prompt"] == "Original"  # Preserved
        assert saved["agents"] == [{"name": "Bot"}]  # Preserved


class TestPostAgents:
    """Tests for POST /agents endpoint."""

    def test_post_agents_saves_agents_list(self, client, settings_file):
        """POST /agents saves the agents list."""
        agents = [
            {"name": "Bot1", "prompt": "You are Bot1", "model": "gpt-4o"},
            {"name": "Bot2", "prompt": "You are Bot2", "model": "gpt-4o-mini"}
        ]
        
        response = client.post(
            "/agents",
            json={"agents": agents},
            content_type="application/json"
        )
        
        assert response.status_code == 200
        assert response.get_json()["ok"] is True
        
        saved = json.loads(settings_file.read_text())
        assert len(saved["agents"]) == 2
        assert saved["agents"][0]["name"] == "Bot1"
        assert saved["agents"][1]["model"] == "gpt-4o-mini"

    def test_post_agents_clears_agents(self, client, settings_file):
        """POST /agents with empty list clears agents."""
        settings_file.write_text(json.dumps({
            "agents": [{"name": "OldBot"}]
        }))
        
        client.post("/agents", json={"agents": []})
        
        saved = json.loads(settings_file.read_text())
        assert saved["agents"] == []


class TestSendMessage:
    """Tests for POST /send endpoint."""

    def test_send_creates_message(self, client, tmp_path, monkeypatch):
        """POST /send creates a message in the channel."""
        channel_path = tmp_path / "channel.txt"
        monkeypatch.setattr(server, "CHANNEL_PATH", str(channel_path))
        
        response = client.post(
            "/send",
            json={"message": "Hello, world!"},
            content_type="application/json"
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert data["ok"] is True
        assert data["index"] == 1
        
        content = channel_path.read_text()
        assert "User" in content
        assert "Hello, world!" in content

    def test_send_increments_index(self, client, tmp_path, monkeypatch):
        """POST /send increments message index correctly."""
        channel_path = tmp_path / "channel.txt"
        monkeypatch.setattr(server, "CHANNEL_PATH", str(channel_path))
        
        client.post("/send", json={"message": "First"})
        response = client.post("/send", json={"message": "Second"})
        
        assert response.get_json()["index"] == 2

    def test_send_rejects_empty_message(self, client):
        """POST /send rejects empty messages."""
        response = client.post(
            "/send",
            json={"message": ""},
            content_type="application/json"
        )
        
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_send_rejects_whitespace_only(self, client):
        """POST /send rejects whitespace-only messages."""
        response = client.post(
            "/send",
            json={"message": "   \n\t  "},
            content_type="application/json"
        )
        
        assert response.status_code == 400


class TestRestart:
    """Tests for POST /restart endpoint."""

    def test_restart_removes_channel_file(self, client, tmp_path, monkeypatch):
        """POST /restart removes the channel file."""
        channel_path = tmp_path / "channel.txt"
        channel_path.write_text("Some content")
        monkeypatch.setattr(server, "CHANNEL_PATH", str(channel_path))
        
        response = client.post("/restart")
        
        assert response.status_code == 200
        assert response.get_json()["ok"] is True
        assert not channel_path.exists()

    def test_restart_succeeds_when_no_file(self, client, tmp_path, monkeypatch):
        """POST /restart succeeds even when channel file doesn't exist."""
        monkeypatch.setattr(server, "CHANNEL_PATH", str(tmp_path / "nonexistent.txt"))
        
        response = client.post("/restart")
        
        assert response.status_code == 200


class TestStop:
    """Tests for POST /stop endpoint."""

    def test_stop_creates_stop_file(self, client, tmp_path, monkeypatch):
        """POST /stop creates the stop signal file."""
        stop_path = tmp_path / ".stop"
        monkeypatch.setattr(server, "STOP_FILE", str(stop_path))
        
        response = client.post("/stop")
        
        assert response.status_code == 200
        assert response.get_json()["ok"] is True
        assert stop_path.exists()


class TestEnrich:
    """Tests for POST /enrich endpoint."""

    def test_enrich_rejects_empty_prompt(self, client):
        """POST /enrich rejects empty prompt."""
        response = client.post(
            "/enrich",
            json={"name": "Bot", "prompt": ""},
            content_type="application/json"
        )
        
        assert response.status_code == 400
        assert "error" in response.get_json()

    def test_enrich_requires_api_key(self, client, monkeypatch):
        """POST /enrich returns error when OPENAI_API_KEY not set."""
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        
        response = client.post(
            "/enrich",
            json={"name": "Bot", "prompt": "A helpful bot"},
            content_type="application/json"
        )
        
        assert response.status_code == 500
        assert "OPENAI_API_KEY" in response.get_json()["error"]


class TestParseChannel:
    """Tests for parse_channel utility function."""

    def test_parse_channel_empty(self):
        """parse_channel returns empty list for empty content."""
        assert server.parse_channel("") == []
        assert server.parse_channel("   \n\n  ") == []

    def test_parse_channel_single_message(self):
        """parse_channel parses a single message."""
        content = f"""{server.SEPARATOR}
[1] User
{server.SUBSEPARATOR}
Hello, world!
"""
        messages = server.parse_channel(content)
        
        assert len(messages) == 1
        assert messages[0]["index"] == 1
        assert messages[0]["author"] == "User"
        assert messages[0]["content"] == "Hello, world!"

    def test_parse_channel_multiple_messages(self):
        """parse_channel parses multiple messages."""
        content = f"""{server.SEPARATOR}
[1] User
{server.SUBSEPARATOR}
First message

{server.SEPARATOR}
[2] Bot
{server.SUBSEPARATOR}
Second message
"""
        messages = server.parse_channel(content)
        
        assert len(messages) == 2
        assert messages[0]["author"] == "User"
        assert messages[1]["author"] == "Bot"
        assert messages[1]["index"] == 2

    def test_parse_channel_multiline_content(self):
        """parse_channel handles multiline message content."""
        content = f"""{server.SEPARATOR}
[1] User
{server.SUBSEPARATOR}
Line 1
Line 2
Line 3
"""
        messages = server.parse_channel(content)
        
        assert "Line 1" in messages[0]["content"]
        assert "Line 2" in messages[0]["content"]
        assert "Line 3" in messages[0]["content"]


class TestEstimateTokens:
    """Tests for estimate_tokens utility function."""

    def test_estimate_tokens_empty(self):
        """estimate_tokens returns 0 for empty string."""
        assert server.estimate_tokens("") == 0

    def test_estimate_tokens_short_text(self):
        """estimate_tokens estimates correctly for short text."""
        # ~4 chars per token
        result = server.estimate_tokens("Hello world")  # 11 chars
        assert result == 2  # 11 // 4 = 2

    def test_estimate_tokens_longer_text(self):
        """estimate_tokens estimates correctly for longer text."""
        text = "a" * 100
        result = server.estimate_tokens(text)
        assert result == 25  # 100 // 4


class TestCountMessages:
    """Tests for count_messages utility function."""

    def test_count_messages_missing_file(self, tmp_path, monkeypatch):
        """count_messages returns 0 for missing file."""
        monkeypatch.setattr(server, "CHANNEL_PATH", str(tmp_path / "nonexistent.txt"))
        assert server.count_messages() == 0

    def test_count_messages_empty_file(self, tmp_path, monkeypatch):
        """count_messages returns 0 for empty file."""
        channel = tmp_path / "channel.txt"
        channel.write_text("")
        monkeypatch.setattr(server, "CHANNEL_PATH", str(channel))
        
        assert server.count_messages() == 0

    def test_count_messages_counts_separators(self, tmp_path, monkeypatch):
        """count_messages counts separator occurrences."""
        channel = tmp_path / "channel.txt"
        monkeypatch.setattr(server, "CHANNEL_PATH", str(channel))
        
        # Add messages using append_message
        server.append_message(1, "User", "First")
        assert server.count_messages() == 1
        
        server.append_message(2, "Bot", "Second")
        assert server.count_messages() == 2


class TestIndexRoute:
    """Tests for GET / endpoint."""

    def test_index_returns_html(self, client):
        """GET / returns the HTML page."""
        response = client.get("/")
        
        assert response.status_code == 200
        assert b"Agent Zoo" in response.data
        assert b"<!DOCTYPE html>" in response.data

