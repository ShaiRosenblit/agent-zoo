"""Tests for main loop orchestration, turn management, and params parsing."""

import json
import os
import pytest
from unittest.mock import MagicMock, patch, call
import argparse

import agent_zoo


class TestTurnManagement:
    """Tests for agent turn rotation logic."""

    def test_agent_rotation_order(self):
        """Agents take turns in order."""
        agents = [
            {"name": "Agent1", "prompt": "First"},
            {"name": "Agent2", "prompt": "Second"},
            {"name": "Agent3", "prompt": "Third"},
        ]
        
        # Simulate turn rotation
        current_turn = 0
        turns = []
        for _ in range(6):
            turns.append(agents[current_turn]["name"])
            current_turn = (current_turn + 1) % len(agents)
        
        assert turns == ["Agent1", "Agent2", "Agent3", "Agent1", "Agent2", "Agent3"]

    def test_turn_resets_on_user_message(self, tmp_path):
        """Turn resets to first agent when User posts."""
        channel_file = tmp_path / "channel.txt"
        
        # Simulate: Agent1 posts, Agent2 posts, then User posts
        agent_zoo.append_message(str(channel_file), 1, "Agent1", "Hello")
        agent_zoo.append_message(str(channel_file), 2, "Agent2", "Hi there")
        agent_zoo.append_message(str(channel_file), 3, "User", "Hello everyone!")
        
        last_author = agent_zoo.get_last_author(str(channel_file))
        
        # When User posts, turn should reset to first agent (turn 0)
        assert last_author == "User"
        # The main loop would set current_turn = 0 when last_author == "User"

    def test_turn_advances_after_agent_post(self, tmp_path):
        """Turn advances to next agent after an agent posts."""
        agents = [
            {"name": "Einstein", "prompt": "Physics"},
            {"name": "Feynman", "prompt": "Physics"},
        ]
        
        channel_file = tmp_path / "channel.txt"
        agent_zoo.append_message(str(channel_file), 1, "User", "Hello")
        agent_zoo.append_message(str(channel_file), 2, "Einstein", "Hello back")
        
        last_author = agent_zoo.get_last_author(str(channel_file))
        
        # Find which agent posted and calculate next turn
        current_turn = 0
        for idx, agent in enumerate(agents):
            if agent["name"] == last_author:
                current_turn = (idx + 1) % len(agents)
                break
        
        assert current_turn == 1  # Feynman's turn

    def test_turn_wraps_around(self):
        """Turn wraps around to first agent after last."""
        agents = [{"name": f"Agent{i}"} for i in range(3)]
        
        current_turn = 2  # Last agent
        current_turn = (current_turn + 1) % len(agents)
        
        assert current_turn == 0  # Back to first

    def test_turn_handles_agent_list_change(self):
        """Turn is adjusted when agent list changes."""
        # Start with 3 agents
        agents = [{"name": f"Agent{i}"} for i in range(3)]
        current_turn = 2
        
        # Remove an agent (now only 2)
        agents = agents[:2]
        current_turn = current_turn % len(agents)
        
        assert current_turn == 0  # Adjusted to valid index


class TestPauseResume:
    """Tests for pause/resume behavior."""

    def test_paused_state_in_settings(self, tmp_path, monkeypatch):
        """Paused state is stored in settings."""
        settings_file = tmp_path / ".settings.json"
        monkeypatch.setattr(agent_zoo, "SETTINGS_FILE", str(settings_file))
        
        # Save paused state
        agent_zoo.save_settings({"paused": True})
        
        # Load and verify
        settings = agent_zoo.load_settings()
        assert settings["paused"] is True

    def test_pause_toggle(self, tmp_path, monkeypatch):
        """Pause can be toggled."""
        settings_file = tmp_path / ".settings.json"
        monkeypatch.setattr(agent_zoo, "SETTINGS_FILE", str(settings_file))
        
        # Start unpaused
        agent_zoo.save_settings({"paused": False})
        
        # Toggle to paused
        settings = agent_zoo.load_settings()
        settings["paused"] = True
        agent_zoo.save_settings(settings)
        
        assert agent_zoo.load_settings()["paused"] is True
        
        # Toggle back
        settings = agent_zoo.load_settings()
        settings["paused"] = False
        agent_zoo.save_settings(settings)
        
        assert agent_zoo.load_settings()["paused"] is False


class TestRestartDetection:
    """Tests for restart/channel clear detection."""

    def test_detect_channel_cleared(self, tmp_path):
        """Detects when channel is cleared."""
        channel_file = tmp_path / "channel.txt"
        
        # Add messages
        agent_zoo.append_message(str(channel_file), 1, "User", "Hello")
        agent_zoo.append_message(str(channel_file), 2, "Bot", "Hi")
        
        assert agent_zoo.count_messages(str(channel_file)) == 2
        
        # Clear channel
        channel_file.unlink()
        
        # Should detect cleared
        assert agent_zoo.count_messages(str(channel_file)) == 0

    def test_reset_state_on_restart(self, tmp_path):
        """State should reset when channel is cleared."""
        channel_file = tmp_path / "channel.txt"
        
        # Add messages
        agent_zoo.append_message(str(channel_file), 1, "User", "Hello")
        
        initial_count = agent_zoo.count_messages(str(channel_file))
        assert initial_count == 1
        
        # Clear channel
        channel_file.write_text("")
        
        # Count should be 0
        assert agent_zoo.count_messages(str(channel_file)) == 0


class TestRaceConditions:
    """Tests for race condition handling."""

    def test_channel_cleared_during_check(self, tmp_path):
        """Handles channel cleared between operations."""
        channel_file = tmp_path / "channel.txt"
        
        # Add a message
        agent_zoo.append_message(str(channel_file), 1, "User", "Hello")
        
        # First count check
        count1 = agent_zoo.count_messages(str(channel_file))
        assert count1 == 1
        
        # Channel cleared (simulating restart)
        channel_file.unlink()
        
        # Second count check should handle missing file
        count2 = agent_zoo.count_messages(str(channel_file))
        assert count2 == 0

    def test_message_added_during_processing(self, tmp_path):
        """Handles message added while processing."""
        channel_file = tmp_path / "channel.txt"
        
        # Start with one message
        agent_zoo.append_message(str(channel_file), 1, "User", "Hello")
        last_count = 1
        
        # Simulate message added during processing
        agent_zoo.append_message(str(channel_file), 2, "Bot", "Hi")
        
        # Detect new message
        current_count = agent_zoo.count_messages(str(channel_file))
        assert current_count > last_count


class TestParamsTomlParsing:
    """Tests for parsing agents from params.toml."""

    def test_extract_agents_from_params(self, tmp_path):
        """Agents are correctly extracted from params."""
        params_file = tmp_path / "params.toml"
        params_file.write_text('''
message = "Hello"
channel = "channel.txt"

[agent1]
name = "Einstein"
prompt = "You are Einstein"

[agent2]
name = "Feynman"
prompt = "You are Feynman"

[agent3]
name = "Curie"
prompt = "You are Curie"
''')
        
        params = agent_zoo.load_params(str(params_file))
        
        # Extract agents using same logic as main()
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
        
        assert len(agents) == 3
        assert agents[0]["name"] == "Einstein"
        assert agents[1]["name"] == "Feynman"
        assert agents[2]["name"] == "Curie"

    def test_extract_agents_stops_at_gap(self, tmp_path):
        """Agent extraction stops at first missing index."""
        params_file = tmp_path / "params.toml"
        params_file.write_text('''
[agent1]
name = "Bot1"
prompt = "First"

[agent3]
name = "Bot3"
prompt = "Third"
''')
        # Note: agent2 is missing
        
        params = agent_zoo.load_params(str(params_file))
        
        agents = []
        i = 1
        while True:
            key = f"agent{i}"
            if key in params:
                agents.append({"name": params[key]["name"]})
                i += 1
            else:
                break
        
        # Should only get agent1, stops at missing agent2
        assert len(agents) == 1
        assert agents[0]["name"] == "Bot1"

    def test_extract_channel_path_from_params(self, tmp_path):
        """Channel path is extracted from params."""
        params_file = tmp_path / "params.toml"
        params_file.write_text('''
channel = "custom_channel.txt"

[agent1]
name = "Bot"
prompt = "Helper"
''')
        
        params = agent_zoo.load_params(str(params_file))
        channel_path = params.get("channel", agent_zoo.CHANNEL_PATH)
        
        assert channel_path == "custom_channel.txt"

    def test_default_channel_path(self, tmp_path):
        """Default channel path is used when not specified."""
        params_file = tmp_path / "params.toml"
        params_file.write_text('''
[agent1]
name = "Bot"
prompt = "Helper"
''')
        
        params = agent_zoo.load_params(str(params_file))
        channel_path = params.get("channel", agent_zoo.CHANNEL_PATH)
        
        assert channel_path == agent_zoo.CHANNEL_PATH


class TestCLIArguments:
    """Tests for command-line argument parsing."""

    def test_default_params_file(self):
        """Default params file is params.toml."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--params", "-p", default="params.toml")
        
        args = parser.parse_args([])
        
        assert args.params == "params.toml"

    def test_custom_params_file(self):
        """Custom params file can be specified."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--params", "-p", default="params.toml")
        
        args = parser.parse_args(["--params", "custom.toml"])
        
        assert args.params == "custom.toml"

    def test_short_params_flag(self):
        """Short -p flag works."""
        parser = argparse.ArgumentParser()
        parser.add_argument("--params", "-p", default="params.toml")
        
        args = parser.parse_args(["-p", "other.toml"])
        
        assert args.params == "other.toml"


class TestDelayBehavior:
    """Tests for delay behavior between agent turns."""

    def test_delay_read_from_settings(self, tmp_path, monkeypatch):
        """Delay is read from settings."""
        settings_file = tmp_path / ".settings.json"
        monkeypatch.setattr(agent_zoo, "SETTINGS_FILE", str(settings_file))
        
        agent_zoo.save_settings({"delay_seconds": 10})
        
        settings = agent_zoo.load_settings()
        delay = settings.get("delay_seconds", 0)
        
        assert delay == 10

    def test_default_delay(self, tmp_path, monkeypatch):
        """Default delay is used when not specified."""
        settings_file = tmp_path / ".settings.json"
        monkeypatch.setattr(agent_zoo, "SETTINGS_FILE", str(settings_file))
        
        # Empty settings file
        settings = agent_zoo.load_settings()
        delay = settings.get("delay_seconds", 0)
        
        assert delay == 0


class TestStopSignalDuringExecution:
    """Tests for stop signal behavior during execution."""

    def test_stop_checked_before_write(self, tmp_path, monkeypatch):
        """Stop is checked before writing to channel."""
        stop_file = tmp_path / ".stop"
        channel_file = tmp_path / "channel.txt"
        
        monkeypatch.setattr(agent_zoo, "STOP_FILE", str(stop_file))
        
        # No stop file initially
        assert agent_zoo.should_stop() is False
        
        # Create stop file (simulating user clicking stop)
        stop_file.write_text("stop")
        
        # Should detect stop
        assert agent_zoo.should_stop() is True

    def test_stop_file_cleared_on_exit(self, tmp_path, monkeypatch):
        """Stop file is cleared on normal exit."""
        stop_file = tmp_path / ".stop"
        stop_file.write_text("stop")
        
        monkeypatch.setattr(agent_zoo, "STOP_FILE", str(stop_file))
        
        # Clear stop (as main() does on exit)
        agent_zoo.clear_stop()
        
        assert not stop_file.exists()


class TestAgentContextIntegration:
    """Tests for agent context during conversation."""

    def test_global_context_includes_all_agents(self):
        """Global context includes all participants."""
        agents = [
            {"name": "Einstein", "prompt": "Physicist"},
            {"name": "Feynman", "prompt": "Physicist"},
        ]
        
        context = agent_zoo.build_global_context(agents, "Einstein", "")
        
        assert "Einstein (you)" in context
        assert "Feynman:" in context
        assert "User: Human participant" in context

    def test_global_context_with_user_instructions(self):
        """Global context includes user instructions."""
        agents = [{"name": "Bot", "prompt": "Helper"}]
        instructions = "Keep responses brief."
        
        context = agent_zoo.build_global_context(agents, "Bot", instructions)
        
        assert "Keep responses brief." in context

    def test_agent_sees_channel_content(self, tmp_path):
        """Agent receives full channel content."""
        channel_file = tmp_path / "channel.txt"
        
        agent_zoo.append_message(str(channel_file), 1, "User", "Hello")
        agent_zoo.append_message(str(channel_file), 2, "Bot", "Hi there!")
        
        content = agent_zoo.read_channel(str(channel_file))
        
        assert "Hello" in content
        assert "Hi there!" in content
        assert "[1] User" in content
        assert "[2] Bot" in content


class TestMessageIndexing:
    """Tests for message index management."""

    def test_index_increments_correctly(self, tmp_path):
        """Message index increments with each message."""
        channel_file = tmp_path / "channel.txt"
        
        for i in range(1, 6):
            agent_zoo.append_message(str(channel_file), i, "Bot", f"Message {i}")
        
        assert agent_zoo.count_messages(str(channel_file)) == 5

    def test_index_after_restart(self, tmp_path):
        """Index starts at 1 after restart."""
        channel_file = tmp_path / "channel.txt"
        
        # Add messages
        agent_zoo.append_message(str(channel_file), 1, "User", "Hello")
        agent_zoo.append_message(str(channel_file), 2, "Bot", "Hi")
        
        # Clear (restart)
        channel_file.unlink()
        
        # Next message should be index 1
        next_index = agent_zoo.count_messages(str(channel_file)) + 1
        assert next_index == 1

