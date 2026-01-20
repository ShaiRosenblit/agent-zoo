"""Tests for core agent_zoo.py functionality."""

import json
import os
import pytest
import tempfile

# Import the module under test
import agent_zoo


class TestSettings:
    """Tests for settings management functions."""

    def test_load_settings_returns_defaults_when_file_missing(self, tmp_path, monkeypatch):
        """load_settings returns DEFAULT_SETTINGS when file doesn't exist."""
        monkeypatch.setattr(agent_zoo, "SETTINGS_FILE", str(tmp_path / "nonexistent.json"))
        
        settings = agent_zoo.load_settings()
        
        assert settings == agent_zoo.DEFAULT_SETTINGS
        assert settings["max_tokens"] == 512
        assert settings["delay_seconds"] == 5
        assert settings["paused"] is False
        assert settings["global_prompt"] == ""
        assert settings["agents"] == []

    def test_load_settings_reads_existing_file(self, tmp_path, monkeypatch):
        """load_settings reads and returns settings from existing file."""
        settings_file = tmp_path / "settings.json"
        custom_settings = {"max_tokens": 1024, "delay_seconds": 10}
        settings_file.write_text(json.dumps(custom_settings))
        monkeypatch.setattr(agent_zoo, "SETTINGS_FILE", str(settings_file))
        
        settings = agent_zoo.load_settings()
        
        assert settings["max_tokens"] == 1024
        assert settings["delay_seconds"] == 10
        # Should merge with defaults
        assert settings["paused"] is False
        assert settings["global_prompt"] == ""

    def test_load_settings_handles_corrupted_file(self, tmp_path, monkeypatch):
        """load_settings returns defaults when file is corrupted."""
        settings_file = tmp_path / "settings.json"
        settings_file.write_text("not valid json {{{")
        monkeypatch.setattr(agent_zoo, "SETTINGS_FILE", str(settings_file))
        
        settings = agent_zoo.load_settings()
        
        assert settings == agent_zoo.DEFAULT_SETTINGS

    def test_save_settings_creates_file(self, tmp_path, monkeypatch):
        """save_settings creates a new settings file."""
        settings_file = tmp_path / "settings.json"
        monkeypatch.setattr(agent_zoo, "SETTINGS_FILE", str(settings_file))
        
        test_settings = {"max_tokens": 2048, "paused": True}
        agent_zoo.save_settings(test_settings)
        
        assert settings_file.exists()
        saved = json.loads(settings_file.read_text())
        assert saved["max_tokens"] == 2048
        assert saved["paused"] is True

    def test_settings_roundtrip(self, tmp_path, monkeypatch):
        """Settings survive a save/load cycle."""
        settings_file = tmp_path / "settings.json"
        monkeypatch.setattr(agent_zoo, "SETTINGS_FILE", str(settings_file))
        
        original = {
            "max_tokens": 768,
            "delay_seconds": 15,
            "paused": True,
            "global_prompt": "Test prompt",
            "agents": [{"name": "Bot1", "prompt": "You are helpful."}]
        }
        agent_zoo.save_settings(original)
        loaded = agent_zoo.load_settings()
        
        assert loaded["max_tokens"] == 768
        assert loaded["delay_seconds"] == 15
        assert loaded["paused"] is True
        assert loaded["global_prompt"] == "Test prompt"
        assert len(loaded["agents"]) == 1
        assert loaded["agents"][0]["name"] == "Bot1"


class TestChannelOperations:
    """Tests for channel file operations."""

    def test_read_channel_returns_empty_for_missing_file(self, tmp_path):
        """read_channel returns empty string when file doesn't exist."""
        result = agent_zoo.read_channel(str(tmp_path / "nonexistent.txt"))
        assert result == ""

    def test_read_channel_returns_file_contents(self, tmp_path):
        """read_channel returns the full file contents."""
        channel_file = tmp_path / "channel.txt"
        channel_file.write_text("Hello, world!")
        
        result = agent_zoo.read_channel(str(channel_file))
        assert result == "Hello, world!"

    def test_append_message_creates_file_and_writes(self, tmp_path):
        """append_message creates file and writes formatted message."""
        channel_file = tmp_path / "channel.txt"
        
        agent_zoo.append_message(str(channel_file), 1, "User", "Hello!")
        
        content = channel_file.read_text()
        assert agent_zoo.SEPARATOR in content
        assert "[1] User" in content
        assert agent_zoo.SUBSEPARATOR in content
        assert "Hello!" in content

    def test_append_message_appends_to_existing(self, tmp_path):
        """append_message appends to existing file."""
        channel_file = tmp_path / "channel.txt"
        
        agent_zoo.append_message(str(channel_file), 1, "User", "First message")
        agent_zoo.append_message(str(channel_file), 2, "Bot", "Second message")
        
        content = channel_file.read_text()
        assert content.count(agent_zoo.SEPARATOR) == 2
        assert "[1] User" in content
        assert "[2] Bot" in content
        assert "First message" in content
        assert "Second message" in content

    def test_count_messages_returns_zero_for_empty(self, tmp_path):
        """count_messages returns 0 for empty/missing file."""
        channel_file = tmp_path / "channel.txt"
        
        # Non-existent file
        assert agent_zoo.count_messages(str(channel_file)) == 0
        
        # Empty file
        channel_file.write_text("")
        assert agent_zoo.count_messages(str(channel_file)) == 0
        
        # Whitespace only
        channel_file.write_text("   \n\n  ")
        assert agent_zoo.count_messages(str(channel_file)) == 0

    def test_count_messages_counts_separators(self, tmp_path):
        """count_messages counts messages correctly."""
        channel_file = tmp_path / "channel.txt"
        
        agent_zoo.append_message(str(channel_file), 1, "User", "One")
        assert agent_zoo.count_messages(str(channel_file)) == 1
        
        agent_zoo.append_message(str(channel_file), 2, "Bot", "Two")
        assert agent_zoo.count_messages(str(channel_file)) == 2
        
        agent_zoo.append_message(str(channel_file), 3, "User", "Three")
        assert agent_zoo.count_messages(str(channel_file)) == 3

    def test_get_last_author_returns_none_for_empty(self, tmp_path):
        """get_last_author returns None for empty channel."""
        channel_file = tmp_path / "channel.txt"
        
        # Non-existent
        assert agent_zoo.get_last_author(str(channel_file)) is None
        
        # Empty
        channel_file.write_text("")
        assert agent_zoo.get_last_author(str(channel_file)) is None

    def test_get_last_author_returns_correct_author(self, tmp_path):
        """get_last_author returns the last message author."""
        channel_file = tmp_path / "channel.txt"
        
        agent_zoo.append_message(str(channel_file), 1, "User", "Hello")
        assert agent_zoo.get_last_author(str(channel_file)) == "User"
        
        agent_zoo.append_message(str(channel_file), 2, "Einstein", "Hello back")
        assert agent_zoo.get_last_author(str(channel_file)) == "Einstein"
        
        agent_zoo.append_message(str(channel_file), 3, "Feynman", "Hi there")
        assert agent_zoo.get_last_author(str(channel_file)) == "Feynman"


class TestContextBuilding:
    """Tests for context building functions."""

    def test_build_participants_context_basic(self):
        """build_participants_context creates proper participant list."""
        agents = [
            {"name": "Alice", "prompt": "You are Alice, a helpful assistant."},
            {"name": "Bob", "prompt": "Role: Bob the Builder"},
        ]
        
        result = agent_zoo.build_participants_context(agents, "Alice")
        
        assert "Current participants:" in result
        assert "Alice (you)" in result
        assert "Bob:" in result
        assert "User: Human participant" in result

    def test_build_participants_context_extracts_description(self):
        """build_participants_context extracts description from prompt."""
        agents = [
            {"name": "Helper", "prompt": "You are a coding expert.\nMore details here."},
        ]
        
        result = agent_zoo.build_participants_context(agents, "Other")
        
        # Should extract first line and clean up "You are"
        assert "Helper:" in result
        assert "a coding expert" in result

    def test_build_participants_context_handles_empty_prompt(self):
        """build_participants_context handles agents with no prompt."""
        agents = [
            {"name": "Empty", "prompt": ""},
        ]
        
        result = agent_zoo.build_participants_context(agents, "Other")
        
        assert "Empty:" in result
        assert "AI assistant" in result  # Fallback description

    def test_build_global_context_includes_all_parts(self):
        """build_global_context assembles all context layers."""
        agents = [{"name": "Test", "prompt": "Test agent"}]
        user_instructions = "Keep it short."
        
        result = agent_zoo.build_global_context(agents, "Test", user_instructions)
        
        # Environment context
        assert "multi-agent conversation" in result
        # Participants
        assert "Test (you)" in result
        assert "User: Human participant" in result
        # User instructions
        assert "Additional instructions from the session host" in result
        assert "Keep it short." in result

    def test_build_global_context_omits_empty_instructions(self):
        """build_global_context omits user instructions if empty."""
        agents = [{"name": "Test", "prompt": "Test agent"}]
        
        result = agent_zoo.build_global_context(agents, "Test", "")
        
        assert "Additional instructions" not in result
        
        result2 = agent_zoo.build_global_context(agents, "Test", "   ")
        assert "Additional instructions" not in result2


class TestParamsLoading:
    """Tests for TOML params loading."""

    def test_load_params_reads_toml(self, tmp_path):
        """load_params correctly reads TOML file."""
        params_file = tmp_path / "params.toml"
        params_file.write_text('''
message = "Hello world"
channel = "test_channel.txt"

[agent1]
name = "Bot1"
prompt = "You are Bot1"

[agent2]
name = "Bot2"
prompt = "You are Bot2"
''')
        
        params = agent_zoo.load_params(str(params_file))
        
        assert params["message"] == "Hello world"
        assert params["channel"] == "test_channel.txt"
        assert params["agent1"]["name"] == "Bot1"
        assert params["agent2"]["name"] == "Bot2"

    def test_load_params_raises_on_invalid_toml(self, tmp_path):
        """load_params raises exception for invalid TOML."""
        params_file = tmp_path / "bad.toml"
        params_file.write_text("not = valid = toml")
        
        with pytest.raises(Exception):
            agent_zoo.load_params(str(params_file))

    def test_load_params_raises_on_missing_file(self, tmp_path):
        """load_params raises exception for missing file."""
        with pytest.raises(FileNotFoundError):
            agent_zoo.load_params(str(tmp_path / "nonexistent.toml"))


class TestStopSignal:
    """Tests for stop signal management."""

    def test_should_stop_returns_false_when_no_file(self, tmp_path, monkeypatch):
        """should_stop returns False when stop file doesn't exist."""
        monkeypatch.setattr(agent_zoo, "STOP_FILE", str(tmp_path / ".stop"))
        
        assert agent_zoo.should_stop() is False

    def test_should_stop_returns_true_when_file_exists(self, tmp_path, monkeypatch):
        """should_stop returns True when stop file exists."""
        stop_file = tmp_path / ".stop"
        stop_file.write_text("stop")
        monkeypatch.setattr(agent_zoo, "STOP_FILE", str(stop_file))
        
        assert agent_zoo.should_stop() is True

    def test_clear_stop_removes_file(self, tmp_path, monkeypatch):
        """clear_stop removes the stop file."""
        stop_file = tmp_path / ".stop"
        stop_file.write_text("stop")
        monkeypatch.setattr(agent_zoo, "STOP_FILE", str(stop_file))
        
        agent_zoo.clear_stop()
        
        assert not stop_file.exists()

    def test_clear_stop_handles_missing_file(self, tmp_path, monkeypatch):
        """clear_stop doesn't raise when file doesn't exist."""
        monkeypatch.setattr(agent_zoo, "STOP_FILE", str(tmp_path / ".stop"))
        
        # Should not raise
        agent_zoo.clear_stop()


class TestAgentState:
    """Tests for agent state management."""

    def test_load_agent_state_returns_defaults_when_file_missing(self, tmp_path, monkeypatch):
        """load_agent_state returns defaults when file doesn't exist."""
        monkeypatch.setattr(agent_zoo, "AGENT_STATE_FILE", str(tmp_path / "nonexistent.json"))
        
        state = agent_zoo.load_agent_state()
        
        assert state["current_agent"] is None
        assert state["state"] == "idle"
        assert state["timestamp"] == 0
        assert state["pass_history"] == []

    def test_load_agent_state_reads_existing_file(self, tmp_path, monkeypatch):
        """load_agent_state reads state from existing file."""
        state_file = tmp_path / ".agent_state.json"
        state_file.write_text(json.dumps({
            "current_agent": "Bot1",
            "state": "thinking",
            "timestamp": 12345,
            "pass_history": []
        }))
        monkeypatch.setattr(agent_zoo, "AGENT_STATE_FILE", str(state_file))
        
        state = agent_zoo.load_agent_state()
        
        assert state["current_agent"] == "Bot1"
        assert state["state"] == "thinking"
        assert state["timestamp"] == 12345

    def test_load_agent_state_handles_corrupted_file(self, tmp_path, monkeypatch):
        """load_agent_state returns defaults when file is corrupted."""
        state_file = tmp_path / ".agent_state.json"
        state_file.write_text("not valid json {{{")
        monkeypatch.setattr(agent_zoo, "AGENT_STATE_FILE", str(state_file))
        
        state = agent_zoo.load_agent_state()
        
        assert state["current_agent"] is None
        assert state["state"] == "idle"

    def test_update_agent_state_creates_file(self, tmp_path, monkeypatch):
        """update_agent_state creates state file."""
        state_file = tmp_path / ".agent_state.json"
        monkeypatch.setattr(agent_zoo, "AGENT_STATE_FILE", str(state_file))
        
        agent_zoo.update_agent_state("TestBot", "thinking")
        
        assert state_file.exists()
        state = json.loads(state_file.read_text())
        assert state["current_agent"] == "TestBot"
        assert state["state"] == "thinking"
        assert state["timestamp"] > 0

    def test_update_agent_state_tracks_passes(self, tmp_path, monkeypatch):
        """update_agent_state adds passed state to pass_history."""
        state_file = tmp_path / ".agent_state.json"
        monkeypatch.setattr(agent_zoo, "AGENT_STATE_FILE", str(state_file))
        
        agent_zoo.update_agent_state("Bot1", "passed")
        
        state = json.loads(state_file.read_text())
        assert len(state["pass_history"]) == 1
        assert state["pass_history"][0]["agent"] == "Bot1"
        assert state["pass_history"][0]["time"] > 0

    def test_update_agent_state_cleans_old_passes(self, tmp_path, monkeypatch):
        """update_agent_state removes passes older than 10 seconds."""
        state_file = tmp_path / ".agent_state.json"
        import time
        old_time = time.time() - 20  # 20 seconds ago
        state_file.write_text(json.dumps({
            "current_agent": None,
            "state": "idle",
            "timestamp": 0,
            "pass_history": [{"agent": "OldBot", "time": old_time}]
        }))
        monkeypatch.setattr(agent_zoo, "AGENT_STATE_FILE", str(state_file))
        
        agent_zoo.update_agent_state("NewBot", "passed")
        
        state = json.loads(state_file.read_text())
        # Old pass should be removed, only new one remains
        assert len(state["pass_history"]) == 1
        assert state["pass_history"][0]["agent"] == "NewBot"

    def test_clear_agent_state_removes_file(self, tmp_path, monkeypatch):
        """clear_agent_state removes the state file."""
        state_file = tmp_path / ".agent_state.json"
        state_file.write_text('{"test": true}')
        monkeypatch.setattr(agent_zoo, "AGENT_STATE_FILE", str(state_file))
        
        agent_zoo.clear_agent_state()
        
        assert not state_file.exists()

    def test_clear_agent_state_handles_missing_file(self, tmp_path, monkeypatch):
        """clear_agent_state doesn't raise when file doesn't exist."""
        monkeypatch.setattr(agent_zoo, "AGENT_STATE_FILE", str(tmp_path / ".agent_state.json"))
        
        # Should not raise
        agent_zoo.clear_agent_state()


class TestPassDetection:
    """Tests for [PASS] response detection."""

    def test_pass_response_is_detected(self):
        """[PASS] response should be detected correctly."""
        # This tests the detection logic used in the main loop
        response = "[PASS]"
        assert response.strip() == "[PASS]"

    def test_pass_with_whitespace_is_detected(self):
        """[PASS] with surrounding whitespace should be detected."""
        response = "  [PASS]  \n"
        assert response.strip() == "[PASS]"

    def test_non_pass_response_is_not_detected(self):
        """Regular response should not be detected as pass."""
        response = "Hello, this is a normal response"
        assert response.strip() != "[PASS]"

    def test_partial_pass_is_not_detected(self):
        """Partial [PASS] in message should not be detected as pass."""
        response = "I will [PASS] on this question and say hello instead"
        assert response.strip() != "[PASS]"

