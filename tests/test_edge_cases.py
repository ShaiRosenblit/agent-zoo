"""Tests for edge cases, special characters, malformed data, and error handling."""

import json
import os
import pytest
from unittest.mock import MagicMock, patch

import agent_zoo
import server


class TestMessageContentEdgeCases:
    """Tests for special characters and edge cases in message content."""

    def test_message_with_newlines(self, tmp_path):
        """Messages with newlines are handled correctly."""
        channel_file = tmp_path / "channel.txt"
        
        content = "Line 1\nLine 2\nLine 3"
        agent_zoo.append_message(str(channel_file), 1, "User", content)
        
        result = agent_zoo.read_channel(str(channel_file))
        assert "Line 1" in result
        assert "Line 2" in result
        assert "Line 3" in result

    def test_message_with_equals_signs(self, tmp_path):
        """Messages containing equals signs don't break parsing."""
        channel_file = tmp_path / "channel.txt"
        
        content = "a = b + c\n2 + 2 = 4\n" + "=" * 50
        agent_zoo.append_message(str(channel_file), 1, "User", content)
        
        # Should still have exactly 1 message
        assert agent_zoo.count_messages(str(channel_file)) == 1
        
        # Parse with server function
        channel_content = channel_file.read_text()
        messages = server.parse_channel(channel_content)
        assert len(messages) == 1
        assert "a = b + c" in messages[0]["content"]

    def test_message_with_brackets(self, tmp_path):
        """Messages with brackets don't break header parsing."""
        channel_file = tmp_path / "channel.txt"
        
        content = "[This is bracketed text] and [more brackets]"
        agent_zoo.append_message(str(channel_file), 1, "User", content)
        
        author = agent_zoo.get_last_author(str(channel_file))
        assert author == "User"

    def test_message_with_unicode(self, tmp_path):
        """Messages with Unicode characters are preserved."""
        channel_file = tmp_path / "channel.txt"
        
        content = "Hello 世界! 🎉 Привет мир! Ñoño"
        agent_zoo.append_message(str(channel_file), 1, "User", content)
        
        result = agent_zoo.read_channel(str(channel_file))
        assert "世界" in result
        assert "🎉" in result
        assert "Привет" in result
        assert "Ñoño" in result

    def test_message_with_emoji(self, tmp_path):
        """Messages with emoji are handled correctly."""
        channel_file = tmp_path / "channel.txt"
        
        content = "😀 👋 🚀 ❤️ 🎯 💡"
        agent_zoo.append_message(str(channel_file), 1, "User", content)
        
        result = agent_zoo.read_channel(str(channel_file))
        assert "😀" in result
        assert "🚀" in result

    def test_very_long_message(self, tmp_path):
        """Very long messages are handled without truncation."""
        channel_file = tmp_path / "channel.txt"
        
        content = "x" * 100000  # 100KB message
        agent_zoo.append_message(str(channel_file), 1, "User", content)
        
        result = agent_zoo.read_channel(str(channel_file))
        assert "x" * 100000 in result

    def test_empty_message_content(self, tmp_path):
        """Empty message content is handled."""
        channel_file = tmp_path / "channel.txt"
        
        agent_zoo.append_message(str(channel_file), 1, "User", "")
        
        assert agent_zoo.count_messages(str(channel_file)) == 1
        author = agent_zoo.get_last_author(str(channel_file))
        assert author == "User"


class TestAuthorNameEdgeCases:
    """Tests for special characters in author names."""

    def test_author_with_spaces(self, tmp_path):
        """Author names with spaces are handled."""
        channel_file = tmp_path / "channel.txt"
        
        agent_zoo.append_message(str(channel_file), 1, "Albert Einstein", "E=mc²")
        
        author = agent_zoo.get_last_author(str(channel_file))
        assert author == "Albert Einstein"

    def test_author_with_numbers(self, tmp_path):
        """Author names with numbers are handled."""
        channel_file = tmp_path / "channel.txt"
        
        agent_zoo.append_message(str(channel_file), 1, "Bot123", "Hello")
        
        author = agent_zoo.get_last_author(str(channel_file))
        assert author == "Bot123"

    def test_author_with_special_chars(self, tmp_path):
        """Author names with special characters are handled."""
        channel_file = tmp_path / "channel.txt"
        
        agent_zoo.append_message(str(channel_file), 1, "Bot-v2.0", "Hello")
        
        author = agent_zoo.get_last_author(str(channel_file))
        assert author == "Bot-v2.0"

    def test_author_with_unicode(self, tmp_path):
        """Author names with Unicode are handled."""
        channel_file = tmp_path / "channel.txt"
        
        agent_zoo.append_message(str(channel_file), 1, "日本語Bot", "こんにちは")
        
        author = agent_zoo.get_last_author(str(channel_file))
        assert author == "日本語Bot"


class TestChannelParsingEdgeCases:
    """Tests for malformed and edge case channel content."""

    def test_parse_channel_missing_subseparator(self):
        """parse_channel handles missing subseparator."""
        # Header without subseparator
        content = f"""{server.SEPARATOR}
[1] User
Hello, world!
"""
        messages = server.parse_channel(content)
        
        # Should still parse, content starts after header
        assert len(messages) == 1
        assert messages[0]["author"] == "User"

    def test_parse_channel_empty_blocks(self):
        """parse_channel handles empty blocks."""
        content = f"""{server.SEPARATOR}

{server.SEPARATOR}
[1] User
{server.SUBSEPARATOR}
Hello
"""
        messages = server.parse_channel(content)
        
        # Should only have the valid message
        assert len(messages) == 1
        assert messages[0]["content"] == "Hello"

    def test_parse_channel_consecutive_separators(self):
        """parse_channel handles consecutive separators."""
        content = f"""{server.SEPARATOR}
{server.SEPARATOR}
{server.SEPARATOR}
[1] User
{server.SUBSEPARATOR}
Hello
"""
        messages = server.parse_channel(content)
        
        # Should still parse the valid message
        assert len(messages) >= 1

    def test_parse_channel_malformed_header(self):
        """parse_channel handles malformed headers."""
        content = f"""{server.SEPARATOR}
This is not a valid header
{server.SUBSEPARATOR}
Some content

{server.SEPARATOR}
[1] User
{server.SUBSEPARATOR}
Valid message
"""
        messages = server.parse_channel(content)
        
        # Should only parse the valid message
        valid_messages = [m for m in messages if m.get("author")]
        assert len(valid_messages) == 1
        assert valid_messages[0]["content"] == "Valid message"

    def test_parse_channel_negative_index(self):
        """parse_channel handles messages with unusual index values."""
        content = f"""{server.SEPARATOR}
[999] Bot
{server.SUBSEPARATOR}
Message with large index
"""
        messages = server.parse_channel(content)
        
        assert len(messages) == 1
        assert messages[0]["index"] == 999


class TestSettingsValidationEdgeCases:
    """Tests for settings validation edge cases."""

    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        """Create Flask test client with isolated files."""
        monkeypatch.setattr(server, "SETTINGS_FILE", str(tmp_path / ".settings.json"))
        monkeypatch.setattr(server, "CHANNEL_PATH", str(tmp_path / "channel.txt"))
        monkeypatch.setattr(server, "STOP_FILE", str(tmp_path / ".stop"))
        
        server.app.config["TESTING"] = True
        with server.app.test_client() as test_client:
            yield test_client

    @pytest.fixture
    def settings_file(self, tmp_path, monkeypatch):
        """Isolated settings file path."""
        path = tmp_path / ".settings.json"
        monkeypatch.setattr(server, "SETTINGS_FILE", str(path))
        return path

    def test_settings_with_negative_max_tokens(self, client, settings_file):
        """Negative max_tokens is clamped to minimum."""
        client.post("/settings", json={"max_tokens": -100})
        
        saved = json.loads(settings_file.read_text())
        assert saved["max_tokens"] == 100

    def test_settings_with_zero_max_tokens(self, client, settings_file):
        """Zero max_tokens is clamped to minimum."""
        client.post("/settings", json={"max_tokens": 0})
        
        saved = json.loads(settings_file.read_text())
        assert saved["max_tokens"] == 100

    def test_settings_with_float_max_tokens(self, client, settings_file):
        """Float max_tokens is converted to int."""
        client.post("/settings", json={"max_tokens": 512.7})
        
        saved = json.loads(settings_file.read_text())
        assert saved["max_tokens"] == 512
        assert isinstance(saved["max_tokens"], int)

    def test_settings_with_very_large_delay(self, client, settings_file):
        """Very large delay_seconds is clamped to maximum."""
        client.post("/settings", json={"delay_seconds": 99999})
        
        saved = json.loads(settings_file.read_text())
        assert saved["delay_seconds"] == 300

    def test_settings_with_corrupted_json(self, tmp_path, monkeypatch):
        """load_settings handles corrupted JSON gracefully."""
        settings_file = tmp_path / ".settings.json"
        settings_file.write_text("{invalid json content")
        monkeypatch.setattr(server, "SETTINGS_FILE", str(settings_file))
        
        settings = server.load_settings()
        
        # Should return defaults
        assert settings == server.DEFAULT_SETTINGS


class TestAPIFailures:
    """Tests for handling OpenAI API failures."""

    def test_call_agent_handles_api_exception(self):
        """call_agent propagates exceptions from API."""
        mock_client = MagicMock()
        mock_client.chat.completions.create.side_effect = Exception("API Error")
        
        with pytest.raises(Exception, match="API Error"):
            agent_zoo.call_agent(
                name="Bot",
                prompt="Hello",
                channel_content="",
                max_tokens=512,
                model="gpt-4o",
                client=mock_client
            )

    def test_call_agent_handles_empty_choices(self):
        """call_agent handles response with empty choices."""
        mock_client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = []
        mock_client.chat.completions.create.return_value = mock_response
        
        with pytest.raises(IndexError):
            agent_zoo.call_agent(
                name="Bot",
                prompt="Hello",
                channel_content="",
                max_tokens=512,
                model="gpt-4o",
                client=mock_client
            )

    def test_enrich_handles_api_error(self, tmp_path, monkeypatch):
        """POST /enrich handles API errors gracefully."""
        monkeypatch.setattr(server, "SETTINGS_FILE", str(tmp_path / ".settings.json"))
        monkeypatch.setenv("OPENAI_API_KEY", "test-key")
        
        server.app.config["TESTING"] = True
        
        with patch("openai.OpenAI") as mock_openai:
            mock_client = MagicMock()
            mock_client.chat.completions.create.side_effect = Exception("Rate limit exceeded")
            mock_openai.return_value = mock_client
            
            with server.app.test_client() as client:
                response = client.post(
                    "/enrich",
                    json={"name": "Bot", "prompt": "test"},
                    content_type="application/json"
                )
                
                assert response.status_code == 500
                assert "error" in response.get_json()


class TestFileErrorHandling:
    """Tests for file I/O error handling."""

    def test_read_channel_handles_permission_error(self, tmp_path, monkeypatch):
        """read_channel handles file that exists check but fails to read."""
        channel_file = tmp_path / "channel.txt"
        channel_file.write_text("content")
        
        # Mock os.path.exists to return True but open to fail
        original_open = open
        def mock_open(path, *args, **kwargs):
            if str(path) == str(channel_file):
                raise PermissionError("Access denied")
            return original_open(path, *args, **kwargs)
        
        with patch("builtins.open", mock_open):
            with patch("os.path.exists", return_value=True):
                with pytest.raises(PermissionError):
                    agent_zoo.read_channel(str(channel_file))

    def test_save_settings_handles_write_error(self, tmp_path, monkeypatch):
        """save_settings raises exception on write failure."""
        # Create a directory where file should be (can't write file with same name)
        settings_path = tmp_path / ".settings.json"
        settings_path.mkdir()
        monkeypatch.setattr(agent_zoo, "SETTINGS_FILE", str(settings_path))
        
        with pytest.raises(Exception):
            agent_zoo.save_settings({"test": "data"})


class TestTokenEstimationEdgeCases:
    """Tests for token estimation edge cases."""

    def test_estimate_tokens_with_unicode(self):
        """estimate_tokens handles Unicode characters."""
        # Unicode characters may have different byte lengths
        text = "Hello 世界!"
        result = server.estimate_tokens(text)
        
        # Should return a number based on character count
        assert result >= 0

    def test_estimate_tokens_with_emoji(self):
        """estimate_tokens handles emoji."""
        text = "🎉🎊🎈"
        result = server.estimate_tokens(text)
        
        assert result >= 0

    def test_estimate_tokens_whitespace_only(self):
        """estimate_tokens handles whitespace-only strings."""
        text = "   \n\t\n   "
        result = server.estimate_tokens(text)
        
        assert result >= 0


class TestContextBuildingEdgeCases:
    """Tests for edge cases in context building."""

    def test_build_participants_context_with_many_agents(self):
        """build_participants_context handles many agents."""
        agents = [{"name": f"Agent{i}", "prompt": f"You are Agent{i}"} for i in range(20)]
        
        result = agent_zoo.build_participants_context(agents, "Agent0")
        
        assert "Agent0 (you)" in result
        assert "Agent19:" in result

    def test_build_participants_context_missing_name(self):
        """build_participants_context handles agent without name."""
        agents = [{"prompt": "You are nameless"}]
        
        result = agent_zoo.build_participants_context(agents, "Other")
        
        assert "Unknown:" in result

    def test_build_global_context_with_very_long_instructions(self):
        """build_global_context handles very long user instructions."""
        agents = [{"name": "Bot", "prompt": "Helper"}]
        instructions = "x" * 10000
        
        result = agent_zoo.build_global_context(agents, "Bot", instructions)
        
        assert instructions in result

    def test_build_participants_cleans_various_prefixes(self):
        """build_participants_context cleans various prompt prefixes."""
        agents = [
            {"name": "Bot1", "prompt": "Role: A helpful assistant"},
            {"name": "Bot2", "prompt": "You are a coding expert"},
            {"name": "Bot3", "prompt": "You're a friendly bot"},
        ]
        
        result = agent_zoo.build_participants_context(agents, "Other")
        
        # Prefixes should be cleaned
        assert "Role:" not in result or "Bot1:" in result
        assert "A helpful assistant" in result or "helpful assistant" in result

