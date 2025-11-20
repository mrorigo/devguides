"""LLM integration layer for DevGuides."""

import json
import asyncio
from typing import Dict, List, Optional, Any, Union
from abc import ABC, abstractmethod
import os

try:
    import openai
    from openai import AsyncOpenAI
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False

from ..utils.logging import get_logger
from ..utils.error_handling import retry_with_backoff, handle_llm_errors

logger = get_logger(__name__)

class LLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    @abstractmethod
    async def generate(self, prompt: str, max_tokens: int = 2000, temperature: float = 0.3) -> str:
        """Generate text from a prompt."""
        pass
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if the provider is available and configured."""
        pass

class OpenAIProvider(LLMProvider):
    """OpenAI GPT provider implementation."""
    
    def __init__(self, api_key: str, model: str = "gpt-4", base_url: Optional[str] = None):
        """Initialize OpenAI provider."""
        self.api_key = api_key
        self.model = model
        self.base_url = base_url
        self.client = None
        
        if OPENAI_AVAILABLE:
            client_kwargs = {"api_key": api_key}
            if base_url:
                client_kwargs["base_url"] = base_url
            self.client = AsyncOpenAI(**client_kwargs)
        
        logger.info("openai_provider_initialized", model=model, base_url=base_url)
    
    def is_available(self) -> bool:
        """Check if OpenAI provider is available."""
        if not OPENAI_AVAILABLE:
            return False
        
        # If base_url is provided (local service), API key may be optional
        if self.base_url and self.api_key == "dummy":
            return True  # Available for local services without API key
        
        # For official OpenAI, API key is required
        return self.api_key is not None and len(self.api_key.strip()) > 0
    
    @retry_with_backoff(max_attempts=3, base_delay=1.0)
    @handle_llm_errors(default_return="")
    async def generate(self, prompt: str, max_tokens: int = 2000, temperature: float = 0.3) -> str:
        """Generate text using OpenAI API."""
        if not self.is_available():
            raise RuntimeError("OpenAI provider not available or configured")
        
        try:
            logger.info("openai_request_started", model=self.model, max_tokens=max_tokens)
            
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": "You are a helpful assistant that generates developer documentation."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=max_tokens,
                temperature=temperature,
                timeout=60.0
            )
            
            content = response.choices[0].message.content
            logger.info("openai_request_completed", 
                       tokens_used=response.usage.total_tokens if response.usage else 0)
            
            return content
            
        except Exception as e:
            logger.error("openai_request_failed", error=str(e))
            raise



class LLMHandler:
    """Main LLM handler that manages different providers."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize LLM handler with configuration."""
        self.config = config
        self.provider = self._create_provider()
        
        logger.info("llm_handler_initialized", 
                   provider_type=config.get("provider", "unknown"))
    
    def _create_provider(self) -> LLMProvider:
        """Create LLM provider based on configuration."""
        provider_type = self.config.get("provider", "openai")
        base_url = self.config.get("base_url")
        
        if provider_type == "openai":
            api_key = self.config.get("api_key")
            if not api_key:
                # Try environment variables (check multiple common names)
                api_key = (os.getenv("DEVGUIDES_LLM_API_KEY") or
                          os.getenv("OPENAI_API_KEY") or
                          os.getenv("OPENAI_KEY"))
            
            # If base_url is provided (local OpenAI-compatible service), API key is optional
            # If no base_url (official OpenAI), API key is required
            if not base_url and not api_key:
                raise ValueError(
                    "OpenAI API key not provided. Set DEVGUIDES_LLM_API_KEY environment variable "
                    "or configure api_key in config file."
                )
            
            return OpenAIProvider(
                api_key=api_key or "dummy",  # Use dummy key if none provided for local services
                model=self.config.get("model", "gpt-4"),
                base_url=base_url
            )
        
        else:
            raise ValueError(f"Unsupported LLM provider: {provider_type}")
    
    @handle_llm_errors(default_return="")
    async def generate_documentation(
        self, 
        query: str, 
        context: Dict[str, Any],
        detail_level: str = "comprehensive"
    ) -> str:
        """Generate documentation based on query and context."""
        
        prompt = self._build_prompt(query, context, detail_level)
        
        max_tokens = self.config.get("max_tokens", 2000)
        if detail_level == "concise":
            max_tokens = min(max_tokens, 1000)
        
        temperature = self.config.get("temperature", 0.3)
        
        logger.info("documentation_generation_started", 
                   query=query, 
                   detail_level=detail_level,
                   max_tokens=max_tokens)
        
        try:
            response = await self.provider.generate(prompt, max_tokens, temperature)
            
            logger.info("documentation_generation_completed", 
                       response_length=len(response))
            
            return response
            
        except Exception as e:
            logger.error("documentation_generation_failed", error=str(e))
            return f"Error generating documentation: {str(e)}"
    
    def _build_prompt(self, query: str, context: Dict[str, Any], detail_level: str) -> str:
        """Build structured prompt for documentation generation."""
        
        # Base prompt template
        base_prompt = f"""Generate developer documentation for the following query: "{query}"

Context from CodeFlow analysis:
{json.dumps(context, indent=2)}

Please generate {'comprehensive' if detail_level == 'comprehensive' else 'concise'} documentation that includes:

1. **Overview** - What this code does at a high level
2. **Key Components** - Important functions, classes, and their purposes
3. **Detailed Analysis** - Step-by-step explanation of how it works
4. **Usage Examples** - Practical code examples showing how to use
5. **Related Components** - Connections to other parts of the codebase
"""
        
        # Add information about available Mermaid diagram
        if context.get("has_mermaid_diagram"):
            base_prompt += """

NOTE: A Mermaid call flow diagram has been automatically generated and will be included in the final output. You can reference this diagram in your documentation (e.g., "See the call flow diagram below"). If you need to create additional diagrams for specific concepts, you may do so using Mermaid syntax in code blocks.
"""
        
        base_prompt += """

Focus on making this documentation useful for developers who need to understand or work with this code. Use technical but accessible language. Include relevant code snippets and explain the reasoning behind the implementation."""

        # Add detail level specific instructions
        if detail_level == "comprehensive":
            base_prompt += """

For comprehensive documentation, also include:
- Edge cases and error handling
- Performance considerations
- Potential improvements or extensions
- Security considerations if applicable
- Dependencies and prerequisites"""
        
        elif detail_level == "concise":
            base_prompt += """

For concise documentation, focus on:
- High-level overview
- Key entry points
- Basic usage patterns
- Essential relationships

Keep the response brief but informative."""

        return base_prompt
    

    
    @property
    def provider_available(self) -> bool:
        """Check if the configured provider is available."""
        return self.provider.is_available()
    
    @property
    def provider_info(self) -> Dict[str, Any]:
        """Get information about the current provider."""
        provider_type = self.config.get("provider", "unknown")
        
        info = {
            "type": provider_type,
            "available": self.provider_available
        }
        
        if provider_type == "openai":
            info.update({
                "model": self.config.get("model", "gpt-4"),
                "base_url": self.config.get("base_url")
            })
        
        return info