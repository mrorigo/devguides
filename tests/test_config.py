"""Tests for configuration system."""

import pytest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from devguides.config.config import (
    DevGuidesConfig, ServerConfig, LLMConfig, OutputConfig, 
    GenerationConfig, LoggingConfig
)

class TestServerConfig:
    """Test ServerConfig model."""
    
    def test_default_values(self):
        """Test default server configuration values."""
        config = ServerConfig()
        
        assert config.command == "code_flow_graph_mcp_server"
        assert config.args == []
        assert config.working_directory is None
        assert config.timeout == 30
        assert config.env == {}
    
    def test_custom_values(self):
        """Test custom server configuration values."""
        config = ServerConfig(
            command="python3",
            args=["-m", "custom.server"],
            working_directory="/custom/path",
            timeout=60,
            env={"CUSTOM_VAR": "value"}
        )
        
        assert config.command == "python3"
        assert config.args == ["-m", "custom.server"]
        assert config.working_directory == "/custom/path"
        assert config.timeout == 60
        assert config.env == {"CUSTOM_VAR": "value"}
    
    def test_timeout_validation(self):
        """Test timeout validation."""
        # Valid timeout
        config = ServerConfig(timeout=30)
        assert config.timeout == 30
        
        # Invalid timeout - too low
        with pytest.raises(ValueError, match="Timeout must be between 1 and 300 seconds"):
            ServerConfig(timeout=0)
        
        # Invalid timeout - too high
        with pytest.raises(ValueError, match="Timeout must be between 1 and 300 seconds"):
            ServerConfig(timeout=500)

class TestLLMConfig:
    """Test LLMConfig model."""
    
    def test_default_values(self):
        """Test default LLM configuration values."""
        config = LLMConfig()
        
        assert config.provider == "openai"
        assert config.model == "gpt-4"
        assert config.api_key is None
        assert config.base_url is None
        assert config.max_tokens == 2000
        assert config.temperature == 0.3
        assert config.timeout == 60
    
    def test_temperature_validation(self):
        """Test temperature validation."""
        # Valid temperature
        config = LLMConfig(temperature=1.5)
        assert config.temperature == 1.5
        
        # Invalid temperature - too low
        with pytest.raises(ValueError, match="Temperature must be between 0 and 2"):
            LLMConfig(temperature=-0.1)
        
        # Invalid temperature - too high
        with pytest.raises(ValueError, match="Temperature must be between 0 and 2"):
            LLMConfig(temperature=2.5)
    
    def test_max_tokens_validation(self):
        """Test max_tokens validation."""
        # Valid max_tokens
        config = LLMConfig(max_tokens=1000)
        assert config.max_tokens == 1000
        
        # Invalid max_tokens - too low
        with pytest.raises(ValueError, match="max_tokens must be between 100 and 8000"):
            LLMConfig(max_tokens=50)
        
        # Invalid max_tokens - too high
        with pytest.raises(ValueError, match="max_tokens must be between 100 and 8000"):
            LLMConfig(max_tokens=10000)

class TestOutputConfig:
    """Test OutputConfig model."""
    
    def test_default_values(self):
        """Test default output configuration values."""
        config = OutputConfig()
        
        assert config.format == "markdown"
        assert config.include_diagrams is True
        assert config.template == "default"
        assert config.output_directory == "./docs"
        assert config.file_naming == "query_based"
        assert config.max_file_size == 50000
    
    def test_format_validation(self):
        """Test format validation."""
        # Valid formats
        config = OutputConfig(format="html")
        assert config.format == "html"
        
        # Invalid format
        with pytest.raises(ValueError, match="Format must be one of:"):
            OutputConfig(format="pdf")

class TestGenerationConfig:
    """Test GenerationConfig model."""
    
    def test_default_values(self):
        """Test default generation configuration values."""
        config = GenerationConfig()
        
        assert config.detail_level == "comprehensive"
        assert config.include_examples is True
        assert config.max_results == 10
        assert config.timeout == 60
        assert config.retry_attempts == 3
        assert config.retry_delay == 1.0
    
    def test_detail_level_validation(self):
        """Test detail level validation."""
        # Valid levels
        config = GenerationConfig(detail_level="concise")
        assert config.detail_level == "concise"
        
        # Invalid level
        with pytest.raises(ValueError, match="detail_level must be one of:"):
            GenerationConfig(detail_level="detailed")

class TestLoggingConfig:
    """Test LoggingConfig model."""
    
    def test_default_values(self):
        """Test default logging configuration values."""
        config = LoggingConfig()
        
        assert config.level == "INFO"
        assert config.format == "text"
        assert config.file_path is None
        assert config.max_file_size == 10485760
        assert config.backup_count == 5
    
    def test_level_validation(self):
        """Test log level validation."""
        # Valid levels
        for level in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
            config = LoggingConfig(level=level)
            assert config.level == level
        
        # Invalid level
        with pytest.raises(ValueError, match="level must be one of:"):
            LoggingConfig(level="TRACE")

class TestDevGuidesConfig:
    """Test DevGuidesConfig main model."""
    
    def test_default_initialization(self):
        """Test default configuration initialization."""
        config = DevGuidesConfig()
        
        assert isinstance(config.server, ServerConfig)
        assert isinstance(config.llm, LLMConfig)
        assert isinstance(config.output, OutputConfig)
        assert isinstance(config.generation, GenerationConfig)
        assert isinstance(config.logging, LoggingConfig)
    
    def test_from_file(self):
        """Test loading configuration from YAML file."""
        config_content = """
server:
  command: "python3"
  timeout: 45

llm:
  provider: "openai"
  model: "gpt-3.5-turbo"
  api_key: "test-key"

output:
  format: "html"
  output_directory: "./custom-docs"
"""
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            f.write(config_content)
            f.flush()
            
            config = DevGuidesConfig.from_file(Path(f.name))
            
            assert config.server.command == "python3"
            assert config.server.timeout == 45
            assert config.llm.provider == "openai"
            assert config.llm.model == "gpt-3.5-turbo"
            assert config.llm.api_key == "test-key"
            assert config.output.format == "html"
            assert config.output.output_directory == "./custom-docs"
    
    def test_from_env(self):
        """Test loading configuration from environment variables."""
        with patch.dict(os.environ, {
            "DEVGUIDES_SERVER__COMMAND": "python3.11",
            "DEVGUIDES_SERVER__TIMEOUT": "60",
            "DEVGUIDES_LLM__API_KEY": "env-api-key",
            "DEVGUIDES_LLM__MODEL": "gpt-4-turbo",
            "DEVGUIDES_OUTPUT__OUTPUT_DIRECTORY": "./env-docs"
        }):
            config = DevGuidesConfig.from_env()
            
            assert config.server.command == "python3.11"
            assert config.server.timeout == 60
            assert config.llm.api_key == "env-api-key"
            assert config.llm.model == "gpt-4-turbo"
            assert config.output.output_directory == "./env-docs"
    
    def test_merge(self):
        """Test configuration merging."""
        config1 = DevGuidesConfig(
            server=ServerConfig(command="python", timeout=30),
            llm=LLMConfig(provider="openai", model="gpt-4")
        )
        
        config2 = DevGuidesConfig(
            server=ServerConfig(timeout=60),
            llm=LLMConfig(model="gpt-3.5-turbo")
        )
        
        merged = config1.merge(config2)
        
        # config2 values should override config1
        assert merged.server.command == "code_flow_graph_mcp_server"  # from config1
        assert merged.server.timeout == 60        # from config2
        assert merged.llm.provider == "openai"    # from config1
        assert merged.llm.model == "gpt-3.5-turbo" # from config2
    
    def test_get_server_command(self):
        """Test getting full server command."""
        config = DevGuidesConfig(
            server=ServerConfig(
                command="python",
                args=["-m", "code_flow_graph.mcp_server"]
            )
        )
        
        expected = "python -m code_flow_graph.mcp_server"
        assert config.get_server_command() == expected
    
    def test_is_openai_configured(self):
        """Test OpenAI configuration checking."""
        # Configured OpenAI
        config = DevGuidesConfig(
            llm=LLMConfig(provider="openai", api_key="test-key")
        )
        assert config.is_openai_configured() is True
        
        # Unconfigured OpenAI
        config = DevGuidesConfig(
            llm=LLMConfig(provider="openai", api_key="")
        )
        assert config.is_openai_configured() is False
        
        # Different provider
        config = DevGuidesConfig(
            llm=LLMConfig(provider="local", api_key="test-key")
        )
        assert config.is_openai_configured() is False
    
    def test_validate(self):
        """Test configuration validation."""
        # Valid configuration
        config = DevGuidesConfig(
            llm=LLMConfig(provider="local"),  # No API key needed for local
            server=ServerConfig(command="python", args=["-m", "server"])
        )
        issues = config.validate_config()
        assert len(issues) == 0
        
        # Invalid configuration - missing API key for OpenAI
        config = DevGuidesConfig(
            llm=LLMConfig(provider="openai")  # No API key
        )
        issues = config.validate_config()
        assert len(issues) > 0
        assert "OpenAI API key is required" in " ".join(issues)
        
        # Invalid configuration - empty server command
        config = DevGuidesConfig(
            server=ServerConfig(command="")
        )
        issues = config.validate_config()
        assert len(issues) > 0
        assert "Server command cannot be empty" in " ".join(issues)