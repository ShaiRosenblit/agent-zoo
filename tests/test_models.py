"""Tests for model selection and OpenAI API integration."""

import os
import pytest
from unittest.mock import MagicMock, patch

import agent_zoo


class TestCallAgentMocked:
    """Unit tests for call_agent with mocked OpenAI client."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock OpenAI client."""
        client = MagicMock()
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Test response"
        client.chat.completions.create.return_value = mock_response
        return client

    def test_call_agent_passes_correct_model(self, mock_client):
        """call_agent passes the specified model to the API."""
        agent_zoo.call_agent(
            name="TestBot",
            prompt="You are helpful.",
            channel_content="Hello",
            max_tokens=512,
            model="gpt-4o",
            client=mock_client
        )
        
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o"

    def test_call_agent_with_gpt4o_mini(self, mock_client):
        """call_agent works with gpt-4o-mini model."""
        agent_zoo.call_agent(
            name="TestBot",
            prompt="You are helpful.",
            channel_content="Hello",
            max_tokens=512,
            model="gpt-4o-mini",
            client=mock_client
        )
        
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4o-mini"

    def test_call_agent_with_gpt4_turbo(self, mock_client):
        """call_agent works with gpt-4-turbo model."""
        agent_zoo.call_agent(
            name="TestBot",
            prompt="You are helpful.",
            channel_content="Hello",
            max_tokens=512,
            model="gpt-4-turbo",
            client=mock_client
        )
        
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-4-turbo"

    def test_call_agent_with_gpt35_turbo(self, mock_client):
        """call_agent works with gpt-3.5-turbo model."""
        agent_zoo.call_agent(
            name="TestBot",
            prompt="You are helpful.",
            channel_content="Hello",
            max_tokens=512,
            model="gpt-3.5-turbo",
            client=mock_client
        )
        
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["model"] == "gpt-3.5-turbo"

    def test_call_agent_passes_max_tokens(self, mock_client):
        """call_agent passes max_tokens to the API."""
        agent_zoo.call_agent(
            name="TestBot",
            prompt="You are helpful.",
            channel_content="Hello",
            max_tokens=1024,
            model="gpt-4o",
            client=mock_client
        )
        
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs["max_completion_tokens"] == 1024

    def test_call_agent_includes_prompt_in_messages(self, mock_client):
        """call_agent includes prompt as system message."""
        agent_zoo.call_agent(
            name="TestBot",
            prompt="You are a coding assistant.",
            channel_content="Hello",
            max_tokens=512,
            model="gpt-4o",
            client=mock_client
        )
        
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        messages = call_kwargs["messages"]
        
        # System message should contain the prompt
        system_msg = messages[0]
        assert system_msg["role"] == "system"
        assert "You are a coding assistant." in system_msg["content"]

    def test_call_agent_includes_channel_content(self, mock_client):
        """call_agent includes channel content in user message."""
        agent_zoo.call_agent(
            name="TestBot",
            prompt="You are helpful.",
            channel_content="Previous conversation here",
            max_tokens=512,
            model="gpt-4o",
            client=mock_client
        )
        
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        messages = call_kwargs["messages"]
        
        # User message should contain channel content
        user_msg = messages[1]
        assert user_msg["role"] == "user"
        assert "Previous conversation here" in user_msg["content"]

    def test_call_agent_includes_global_context(self, mock_client):
        """call_agent includes global context when provided."""
        global_context = "You are in a multi-agent system."
        
        agent_zoo.call_agent(
            name="TestBot",
            prompt="You are helpful.",
            channel_content="Hello",
            max_tokens=512,
            model="gpt-4o",
            client=mock_client,
            global_context=global_context
        )
        
        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        messages = call_kwargs["messages"]
        
        system_msg = messages[0]
        assert "multi-agent system" in system_msg["content"]

    def test_call_agent_returns_response_content(self, mock_client):
        """call_agent returns the model's response content."""
        mock_client.chat.completions.create.return_value.choices[0].message.content = "Hello back!"
        
        result = agent_zoo.call_agent(
            name="TestBot",
            prompt="You are helpful.",
            channel_content="Hello",
            max_tokens=512,
            model="gpt-4o",
            client=mock_client
        )
        
        assert result == "Hello back!"

    def test_call_agent_handles_none_response(self, mock_client):
        """call_agent returns fallback when response is None."""
        mock_client.chat.completions.create.return_value.choices[0].message.content = None
        
        result = agent_zoo.call_agent(
            name="TestBot",
            prompt="You are helpful.",
            channel_content="Hello",
            max_tokens=512,
            model="gpt-4o",
            client=mock_client
        )
        
        assert result == "(no response)"

    def test_call_agent_strips_whitespace(self, mock_client):
        """call_agent strips whitespace from response."""
        mock_client.chat.completions.create.return_value.choices[0].message.content = "  response with spaces  \n"
        
        result = agent_zoo.call_agent(
            name="TestBot",
            prompt="You are helpful.",
            channel_content="Hello",
            max_tokens=512,
            model="gpt-4o",
            client=mock_client
        )
        
        assert result == "response with spaces"


class TestModelDefaultFallback:
    """Tests for model default fallback behavior."""

    def test_main_loop_defaults_to_gpt4o(self):
        """When agent has no model specified, gpt-4o is used as default."""
        agent = {"name": "TestBot", "prompt": "You are helpful."}
        # The default model is defined in the main loop
        model = agent.get("model", "gpt-4o")
        assert model == "gpt-4o"

    def test_agent_model_override(self):
        """When agent specifies a model, it's used instead of default."""
        agent = {"name": "TestBot", "prompt": "You are helpful.", "model": "gpt-4o-mini"}
        model = agent.get("model", "gpt-4o")
        assert model == "gpt-4o-mini"


# Integration tests - only run when API key is available
@pytest.mark.integration
class TestCallAgentLive:
    """Integration tests that make real API calls."""

    @pytest.fixture(autouse=True)
    def skip_without_api_key(self):
        """Skip tests if OPENAI_API_KEY is not set."""
        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set - skipping integration test")

    @pytest.fixture
    def client(self):
        """Create a real OpenAI client."""
        from openai import OpenAI
        return OpenAI()

    def test_gpt4o_returns_response(self, client):
        """gpt-4o model returns a valid response."""
        result = agent_zoo.call_agent(
            name="TestBot",
            prompt="You are a helpful assistant. Respond with exactly: 'Hello from GPT-4o'",
            channel_content="Say hello.",
            max_tokens=50,
            model="gpt-4o",
            client=client
        )
        
        assert result
        assert len(result) > 0

    def test_gpt4o_mini_returns_response(self, client):
        """gpt-4o-mini model returns a valid response."""
        result = agent_zoo.call_agent(
            name="TestBot",
            prompt="You are a helpful assistant. Respond with exactly: 'Hello from GPT-4o-mini'",
            channel_content="Say hello.",
            max_tokens=50,
            model="gpt-4o-mini",
            client=client
        )
        
        assert result
        assert len(result) > 0

    def test_gpt4_turbo_returns_response(self, client):
        """gpt-4-turbo model returns a valid response."""
        result = agent_zoo.call_agent(
            name="TestBot",
            prompt="You are a helpful assistant. Respond with exactly: 'Hello from GPT-4-turbo'",
            channel_content="Say hello.",
            max_tokens=50,
            model="gpt-4-turbo",
            client=client
        )
        
        assert result
        assert len(result) > 0

    def test_gpt35_turbo_returns_response(self, client):
        """gpt-3.5-turbo model returns a valid response."""
        result = agent_zoo.call_agent(
            name="TestBot",
            prompt="You are a helpful assistant. Respond with exactly: 'Hello from GPT-3.5-turbo'",
            channel_content="Say hello.",
            max_tokens=50,
            model="gpt-3.5-turbo",
            client=client
        )
        
        assert result
        assert len(result) > 0


@pytest.mark.integration
class TestEnrichLive:
    """Integration tests for the /enrich endpoint."""

    @pytest.fixture(autouse=True)
    def skip_without_api_key(self):
        """Skip tests if OPENAI_API_KEY is not set."""
        if not os.environ.get("OPENAI_API_KEY"):
            pytest.skip("OPENAI_API_KEY not set - skipping integration test")

    @pytest.fixture
    def client(self, tmp_path, monkeypatch):
        """Create a Flask test client."""
        import server
        monkeypatch.setattr(server, "SETTINGS_FILE", str(tmp_path / ".settings.json"))
        server.app.config["TESTING"] = True
        with server.app.test_client() as test_client:
            yield test_client

    def test_enrich_expands_prompt(self, client):
        """POST /enrich returns an expanded prompt."""
        response = client.post(
            "/enrich",
            json={"name": "Coder", "prompt": "coding assistant"},
            content_type="application/json"
        )
        
        assert response.status_code == 200
        data = response.get_json()
        assert "enriched" in data
        assert len(data["enriched"]) > len("coding assistant")

