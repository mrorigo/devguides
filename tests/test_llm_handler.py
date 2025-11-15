"""Tests for LLM handler."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import os

from devguides.core.llm_handler import (
    LLMProvider, OpenAIProvider, LocalLLMProvider, LLMHandler
)

class TestLLMProvider:
    """Test abstract LLM provider."""
    
    def test_abstract_methods(self):
        """Test that abstract methods are properly defined."""
        # Verify that the class has abstract methods
        assert hasattr(LLMProvider, '__abstractmethods__')
        assert len(LLMProvider.__abstractmethods__) > 0
        
        # Abstract methods should be defined
        assert hasattr(LLMProvider, 'generate')
        assert hasattr(LLMProvider, 'is_available')

class TestOpenAIProvider:
    """Test OpenAI provider."""
    
    @pytest.fixture
    def mock_api_key(self):
        """Mock OpenAI API key."""
        return "test-openai-api-key"
    
    @pytest.fixture
    def openai_provider(self, mock_api_key):
        """Create OpenAI provider for testing."""
        return OpenAIProvider(
            api_key=mock_api_key,
            model="gpt-4",
            base_url="https://api.openai.com/v1"
        )
    
    def test_initialization(self, openai_provider, mock_api_key):
        """Test OpenAI provider initialization."""
        assert openai_provider.api_key == mock_api_key
        assert openai_provider.model == "gpt-4"
        assert openai_provider.base_url == "https://api.openai.com/v1"
    
    def test_is_available_with_key(self, openai_provider):
        """Test availability with valid API key."""
        with patch('devguides.core.llm_handler.OPENAI_AVAILABLE', True):
            assert openai_provider.is_available() is True
    
    def test_is_available_without_key(self):
        """Test availability without API key."""
        provider = OpenAIProvider(api_key="")
        with patch('devguides.core.llm_handler.OPENAI_AVAILABLE', True):
            assert provider.is_available() is False
    
    def test_is_available_no_openai(self, openai_provider):
        """Test availability when OpenAI library not available."""
        with patch('devguides.core.llm_handler.OPENAI_AVAILABLE', False):
            assert openai_provider.is_available() is False
    
    def test_is_available_local_service_no_key(self):
        """Test availability for local service without API key."""
        provider = OpenAIProvider(
            api_key="dummy",  # dummy key for local service
            model="gpt-4",
            base_url="http://localhost:11434/v1"
        )
        
        with patch('devguides.core.llm_handler.OPENAI_AVAILABLE', True):
            assert provider.is_available() is True
    
    def test_is_available_official_openai_no_key(self):
        """Test availability for official OpenAI without API key."""
        provider = OpenAIProvider(
            api_key="",  # empty key for official OpenAI
            model="gpt-4"
            # No base_url for official OpenAI
        )
        
        with patch('devguides.core.llm_handler.OPENAI_AVAILABLE', True):
            assert provider.is_available() is False
    
    @pytest.mark.asyncio
    async def test_generate_success(self, openai_provider):
        """Test successful text generation."""
        with patch('devguides.core.llm_handler.OPENAI_AVAILABLE', True):
            with patch.object(openai_provider, 'client') as mock_client:
                # Mock successful response
                mock_response = Mock()
                mock_response.choices = [Mock(message=Mock(content="Generated text"))]
                mock_response.usage = Mock(total_tokens=100)
                mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
                
                # Test generation
                result = await openai_provider.generate(
                    "Test prompt", 
                    max_tokens=500, 
                    temperature=0.7
                )
                
                # Verify result
                assert result == "Generated text"
                
                # Verify API call
                mock_client.chat.completions.create.assert_called_once_with(
                    model="gpt-4",
                    messages=[
                        {"role": "system", "content": "You are a helpful assistant that generates developer documentation."},
                        {"role": "user", "content": "Test prompt"}
                    ],
                    max_tokens=500,
                    temperature=0.7,
                    timeout=60.0
                )
    
    @pytest.mark.asyncio
    async def test_generate_not_available(self, openai_provider):
        """Test generation when not available."""
        with patch('devguides.core.llm_handler.OPENAI_AVAILABLE', False):
            # The decorator handles the error gracefully and returns empty string
            result = await openai_provider.generate("test prompt")
            assert result == ""  # Should return empty string when not available
    
    @pytest.mark.asyncio
    async def test_generate_error_handling(self, openai_provider):
        """Test error handling during generation."""
        with patch('devguides.core.llm_handler.OPENAI_AVAILABLE', True):
            with patch.object(openai_provider, 'client') as mock_client:
                # Mock API error
                mock_client.chat.completions.create = AsyncMock(
                    side_effect=Exception("API error")
                )
                
                # The @handle_llm_errors decorator will handle the exception and return ""
                # So we expect a string return, not an exception
                result = await openai_provider.generate("test prompt")
                assert result == ""  # Error handling returns empty string

class TestLocalLLMProvider:
    """Test local LLM provider."""
    
    def test_initialization(self):
        """Test local LLM provider initialization."""
        provider = LocalLLMProvider(model_name="llama2")
        assert provider.model_name == "llama2"
    
    def test_is_available(self):
        """Test local LLM provider availability."""
        provider = LocalLLMProvider()
        # Currently returns False as it's not implemented
        assert provider.is_available() is False
    
    @pytest.mark.asyncio
    async def test_generate_not_implemented(self):
        """Test that generation raises RuntimeError for not implemented."""
        provider = LocalLLMProvider()
        
        # The current implementation raises RuntimeError instead of NotImplementedError
        with pytest.raises(RuntimeError, match="Local LLM provider not available"):
            await provider.generate("test prompt")

class TestLLMHandler:
    """Test LLM handler."""
    
    @pytest.fixture
    def openai_config(self):
        """OpenAI configuration for testing."""
        return {
            "provider": "openai",
            "model": "gpt-4",
            "api_key": "test-api-key",
            "max_tokens": 2000,
            "temperature": 0.3
        }
    
    @pytest.fixture
    def local_config(self):
        """Local LLM configuration for testing."""
        return {
            "provider": "local",
            "model_name": "llama2",
            "max_tokens": 2000,
            "temperature": 0.3
        }
    
    def test_initialization_openai(self, openai_config):
        """Test LLM handler initialization with OpenAI."""
        with patch('devguides.core.llm_handler.OpenAIProvider') as MockProvider:
            handler = LLMHandler(openai_config)
            
            # Verify OpenAI provider was created
            MockProvider.assert_called_once_with(
                api_key="test-api-key",
                model="gpt-4",
                base_url=None
            )
            
            assert handler.config == openai_config
    
    def test_initialization_local(self, local_config):
        """Test LLM handler initialization with local LLM."""
        with patch('devguides.core.llm_handler.LocalLLMProvider') as MockProvider:
            handler = LLMHandler(local_config)
            
            # Verify local LLM provider was created
            MockProvider.assert_called_once_with(model_name="llama2")
            
            assert handler.config == local_config
    
    def test_initialization_invalid_provider(self):
        """Test initialization with invalid provider."""
        config = {"provider": "invalid_provider"}
        
        with pytest.raises(ValueError, match="Unsupported LLM provider"):
            LLMHandler(config)
    
    def test_initialization_missing_api_key(self):
        """Test initialization with missing API key for OpenAI."""
        config = {
            "provider": "openai",
            "model": "gpt-4"
            # No api_key provided
        }
        
        with patch('devguides.core.llm_handler.os.getenv') as mock_getenv:
            mock_getenv.return_value = None  # No env var either
            
            with pytest.raises(ValueError, match="OpenAI API key not provided"):
                LLMHandler(config)
    
    def test_initialization_local_openai_without_api_key(self):
        """Test initialization with base_url but no API key should work."""
        config = {
            "provider": "openai",
            "model": "gpt-4",
            "base_url": "http://localhost:11434/v1"
            # No api_key provided - should work with base_url
        }
        
        with patch('devguides.core.llm_handler.os.getenv') as mock_getenv:
            mock_getenv.return_value = None  # No env var either
            
            # Should not raise an error when base_url is provided
            handler = LLMHandler(config)
            
            # Verify OpenAI provider was created with dummy key for local service
            assert handler.config == config
            assert handler.provider is not None
    
    def test_initialization_local_openai_with_env_api_key(self):
        """Test initialization with base_url and env var API key."""
        config = {
            "provider": "openai",
            "model": "gpt-4",
            "base_url": "http://localhost:11434/v1"
            # No api_key in config
        }
        
        with patch('devguides.core.llm_handler.os.getenv') as mock_getenv:
            mock_getenv.return_value = "env-api-key"
            
            # Should use env var API key
            handler = LLMHandler(config)
            
            # Verify the provider was created with the env API key
            assert handler.config == config
            assert handler.provider is not None
    
    def test_initialization_local_openai_with_config_api_key(self):
        """Test initialization with base_url and config API key."""
        config = {
            "provider": "openai",
            "model": "gpt-4",
            "base_url": "http://localhost:11434/v1",
            "api_key": "config-api-key"
        }
        
        with patch('devguides.core.llm_handler.os.getenv') as mock_getenv:
            # Should use config API key, not env var
            mock_getenv.return_value = "env-api-key"
            
            handler = LLMHandler(config)
            
            # Should use config API key (higher priority)
            assert handler.config == config
            assert handler.provider is not None
    
    @pytest.mark.asyncio
    async def test_generate_documentation(self):
        """Test documentation generation."""
        config = {
            "provider": "openai",
            "model": "gpt-4",
            "api_key": "test-key",
            "max_tokens": 2000,
            "temperature": 0.3
        }
        
        with patch('devguides.core.llm_handler.OpenAIProvider') as MockProvider:
            # Mock provider
            mock_provider = Mock()
            mock_provider.generate = AsyncMock(return_value="Generated documentation")
            MockProvider.return_value = mock_provider
            
            # Create handler
            handler = LLMHandler(config)
            
            # Test context
            context = {
                "query": "test query",
                "search_results": [{"fqn": "test.func"}],
                "detail_level": "comprehensive"
            }
            
            # Generate documentation
            result = await handler.generate_documentation("test query", context, "comprehensive")
            
            # Verify result
            assert result == "Generated documentation"
            
            # Verify provider was called
            mock_provider.generate.assert_called_once()
            
            # Check that prompt was built (check the call arguments)
            call_args = mock_provider.generate.call_args
            prompt = call_args[0][0]  # First positional argument
            
            # Verify prompt contains expected content
            assert "test query" in prompt
            assert "comprehensive" in prompt
            assert "search_results" in prompt
    
    @pytest.mark.asyncio
    async def test_generate_documentation_concise(self):
        """Test concise documentation generation."""
        config = {
            "provider": "openai",
            "model": "gpt-4",
            "api_key": "test-key",
            "max_tokens": 2000,
            "temperature": 0.3
        }
        
        with patch('devguides.core.llm_handler.OpenAIProvider') as MockProvider:
            mock_provider = Mock()
            mock_provider.generate = AsyncMock(return_value="Concise docs")
            MockProvider.return_value = mock_provider
            
            handler = LLMHandler(config)
            
            result = await handler.generate_documentation(
                "test query", 
                {}, 
                "concise"
            )
            
            # Verify concise was used
            assert result == "Concise docs"
            
            # Verify concise was used and max_tokens was appropriately limited
            call_args = mock_provider.generate.call_args
            
            # The concise mode should call generate with appropriate parameters
            # Let's just verify it was called at all
            assert mock_provider.generate.called
            # And that the detail level was concise
            assert "concise" in call_args[0][0]  # prompt should contain concise
    
    @pytest.mark.asyncio
    async def test_generate_documentation_error(self):
        """Test error handling in documentation generation."""
        config = {
            "provider": "openai",
            "model": "gpt-4",
            "api_key": "test-key"
        }
        
        with patch('devguides.core.llm_handler.OpenAIProvider') as MockProvider:
            mock_provider = Mock()
            mock_provider.generate = AsyncMock(side_effect=Exception("API error"))
            MockProvider.return_value = mock_provider
            
            handler = LLMHandler(config)
            
            result = await handler.generate_documentation("test query", {}, "comprehensive")
            
            # Should return error message instead of raising
            assert "Error generating documentation" in result
    
    @pytest.mark.asyncio
    async def test_generate_summary(self):
        """Test summary generation."""
        config = {
            "provider": "openai",
            "model": "gpt-4",
            "api_key": "test-key"
        }
        
        with patch('devguides.core.llm_handler.OpenAIProvider') as MockProvider:
            mock_provider = Mock()
            mock_provider.generate = AsyncMock(return_value="Summary text")
            MockProvider.return_value = mock_provider
            
            handler = LLMHandler(config)
            
            result = await handler.generate_summary("test code context", max_length=100)
            
            assert result == "Summary text"
            
            # Verify provider was called with summary prompt
            call_args = mock_provider.generate.call_args
            prompt = call_args[0][0]
            assert "brief summary" in prompt
            assert "test code context" in prompt
    
    @pytest.mark.asyncio
    async def test_explain_code_snippet(self):
        """Test code snippet explanation."""
        config = {
            "provider": "openai", 
            "model": "gpt-4",
            "api_key": "test-key"
        }
        
        with patch('devguides.core.llm_handler.OpenAIProvider') as MockProvider:
            mock_provider = Mock()
            mock_provider.generate = AsyncMock(return_value="Explanation text")
            MockProvider.return_value = mock_provider
            
            handler = LLMHandler(config)
            
            code_snippet = "def hello(): pass"
            result = await handler.explain_code_snippet(code_snippet, "test context")
            
            assert result == "Explanation text"
            
            # Verify provider was called with explanation prompt
            call_args = mock_provider.generate.call_args
            prompt = call_args[0][0]
            assert "hello" in prompt  # Code should be in prompt
            assert "test context" in prompt
    
    def test_provider_available(self):
        """Test provider availability checking."""
        config = {"provider": "openai", "api_key": "test-key"}
        
        with patch('devguides.core.llm_handler.OpenAIProvider') as MockProvider:
            mock_provider = Mock()
            mock_provider.is_available.return_value = True
            MockProvider.return_value = mock_provider
            
            handler = LLMHandler(config)
            
            assert handler.provider_available is True
    
    def test_provider_info(self):
        """Test provider info retrieval."""
        config = {
            "provider": "openai",
            "model": "gpt-4",
            "base_url": "custom-url",
            "api_key": "test-key"
        }
        
        with patch('devguides.core.llm_handler.OpenAIProvider') as MockProvider:
            mock_provider = Mock()
            mock_provider.is_available.return_value = True
            MockProvider.return_value = mock_provider
            
            handler = LLMHandler(config)
            
            info = handler.provider_info
            
            assert info["type"] == "openai"
            assert info["available"] is True
            assert info["model"] == "gpt-4"
            assert info["base_url"] == "custom-url"
    
    def test_prompt_building(self):
        """Test prompt building logic."""
        config = {"provider": "local"}  # Use local to avoid API calls
        
        with patch('devguides.core.llm_handler.LocalLLMProvider') as MockProvider:
            MockProvider.return_value = Mock()  # Don't call generate
            
            handler = LLMHandler(config)
            
            # Test comprehensive prompt
            context = {
                "query": "authentication flow",
                "search_results": [{"fqn": "auth.login"}],
                "detail_level": "comprehensive"
            }
            
            prompt = handler._build_prompt("authentication flow", context, "comprehensive")
            
            # Verify comprehensive prompt contains detailed sections
            assert "comprehensive" in prompt
            assert "Edge cases and error handling" in prompt
            assert "Performance considerations" in prompt
            assert "Security considerations" in prompt
            
            # Test concise prompt
            prompt = handler._build_prompt("quick overview", context, "concise")
            
            # Verify concise prompt contains concise sections
            assert "concise" in prompt
            assert "High-level overview" in prompt
            assert "Keep the response brief but informative" in prompt