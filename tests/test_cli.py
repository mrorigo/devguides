"""Tests for CLI commands."""

import pytest
from click.testing import CliRunner
from unittest.mock import Mock, patch, AsyncMock
import json
from pathlib import Path

from devguides.cli.commands import cli
from devguides.core.engine import GenerationResult

@pytest.fixture
def runner():
    """Create CLI runner."""
    return CliRunner()

@pytest.fixture
def mock_config():
    """Mock configuration."""
    with patch('devguides.cli.commands.load_config') as mock:
        # Create a real config object to avoid mocking issues with Rich/Pydantic
        from devguides.config.config import DevGuidesConfig, ServerConfig, LLMConfig, OutputConfig, GenerationConfig
        
        config = DevGuidesConfig(
            server=ServerConfig(command="python"),
            llm=LLMConfig(provider="openai"),
            output=OutputConfig(output_directory="./docs", file_naming="query_based"),
            generation=GenerationConfig(timeout=60)
        )
        
        mock.return_value = config
        yield mock

class TestCLI:
    """Test CLI commands."""
    
    def test_version(self, runner):
        """Test version command."""
        result = runner.invoke(cli, ["version"])
        assert result.exit_code == 0
        assert "DevGuides v" in result.output
    
    def test_config_show(self, runner, mock_config):
        """Test config command."""
        result = runner.invoke(cli, ["config"])
        assert result.exit_code == 0
        assert "Current Configuration" in result.output
        assert "Server" in result.output
        assert "LLM" in result.output
    
    def test_generate_success(self, runner, mock_config):
        """Test successful generation."""
        import devguides.cli.commands
        
        with patch.object(devguides.cli.commands, 'DocumentationEngine') as MockEngine:
            with patch('devguides.cli.commands.CodeFlowMCPClient') as MockClient:
                with patch('devguides.cli.commands.LLMHandler') as MockHandler:
                    # Use a fake class instead of mocks to avoid async issues
                    class FakeEngine:
                        def __init__(self, *args, **kwargs):
                            pass
                            
                        async def generate(self, request):
                            return GenerationResult(
                                content="# Documentation\n\nTest content",
                                success=True,
                                execution_time=1.0,
                                metadata={"detail_level": "comprehensive"},
                                mermaid_diagram=None,
                                error_message=None
                            )
                    
                    # Use side_effect to ensure the class is instantiated
                    MockEngine.side_effect = FakeEngine
                    
                    # Ensure MCP client disconnect is async
                    mock_client_instance = Mock()
                    mock_client_instance.disconnect = AsyncMock()
                    MockClient.return_value = mock_client_instance
                    
                    # Run command
                    with runner.isolated_filesystem():
                        result = runner.invoke(cli, ["generate", "test query"])
                        
                        assert result.exit_code == 0
                        assert "Documentation generated" in result.output
                        
                        # Verify file was created
                        assert Path("docs/test_query.markdown").exists()
                        with open("docs/test_query.markdown") as f:
                            content = f.read()
                            assert "# Documentation" in content
    
    def test_generate_failure(self, runner, mock_config):
        """Test failed generation."""
        with patch('devguides.cli.commands.DocumentationEngine') as MockEngine:
            with patch('devguides.cli.commands.CodeFlowMCPClient'):
                with patch('devguides.cli.commands.LLMHandler'):
                    # Use a fake class for failure case
                    class FakeEngineFail:
                        def __init__(self, *args, **kwargs):
                            pass

                        async def generate(self, request):
                            return GenerationResult(
                                content="",
                                success=False,
                                error_message="Generation failed",
                                execution_time=1.0,
                                metadata={},
                                mermaid_diagram=None
                            )
                            
                    MockEngine.side_effect = FakeEngineFail
                    
                    # Run command
                    result = runner.invoke(cli, ["generate", "test query"])
                    
                    assert result.exit_code == 1
                    assert "Generation failed" in result.output
    
    def test_server_connection_success(self, runner, mock_config):
        """Test server connection check success."""
        with patch('devguides.cli.commands.CodeFlowMCPClient') as MockClient:
            mock_client = MockClient.return_value
            mock_client.connect = AsyncMock()
            mock_client.disconnect = AsyncMock()
            
            result = runner.invoke(cli, ["server"])
            
            assert result.exit_code == 0
            assert "Successfully connected" in result.output
            mock_client.connect.assert_called_once()
    
    def test_server_connection_failure(self, runner, mock_config):
        """Test server connection check failure."""
        with patch('devguides.cli.commands.CodeFlowMCPClient') as MockClient:
            mock_client = MockClient.return_value
            mock_client.connect = AsyncMock(side_effect=Exception("Connection failed"))
            mock_client.disconnect = AsyncMock()
            
            result = runner.invoke(cli, ["server"])
            
            assert result.exit_code == 1
            assert "Failed to connect" in result.output
