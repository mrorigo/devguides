"""Configuration management for DevGuides."""

import os
from typing import Dict, Any, Optional, List
from pathlib import Path
import yaml
from pydantic import BaseModel, Field, field_validator
from pydantic.config import ConfigDict
from pydantic_settings import BaseSettings, SettingsConfigDict

class ServerConfig(BaseModel):
    """Configuration for CodeFlow MCP server connection."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    command: str = Field(default="code_flow_graph_mcp_server")
    args: List[str] = Field(default=[])
    working_directory: Optional[str] = None
    timeout: int = 30
    env: Dict[str, str] = Field(default_factory=dict)
    
    @field_validator('timeout')
    @classmethod
    def validate_timeout(cls, v):
        if v < 1 or v > 300:
            raise ValueError('Timeout must be between 1 and 300 seconds')
        return v

class LLMConfig(BaseModel):
    """Configuration for LLM providers."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    provider: str = Field(default="openai")
    model: str = Field(default="gpt-4")
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    max_tokens: int = 2000
    temperature: float = 0.3
    timeout: int = 60
    
    @field_validator('temperature')
    @classmethod
    def validate_temperature(cls, v):
        if v < 0 or v > 2:
            raise ValueError('Temperature must be between 0 and 2')
        return v
    
    @field_validator('max_tokens')
    @classmethod
    def validate_max_tokens(cls, v):
        if v < 100 or v > 8000:
            raise ValueError('max_tokens must be between 100 and 8000')
        return v

class OutputConfig(BaseModel):
    """Configuration for output formatting and storage."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    format: str = Field(default="markdown")
    include_diagrams: bool = True
    template: str = "default"
    output_directory: str = "./docs"
    file_naming: str = "query_based"  # query_based, timestamped, numbered
    max_file_size: int = 50000  # characters
    
    @field_validator('format')
    @classmethod
    def validate_format(cls, v):
        allowed_formats = ["markdown", "html"]
        if v not in allowed_formats:
            raise ValueError(f'Format must be one of: {allowed_formats}')
        return v
    
    @field_validator('file_naming')
    @classmethod
    def validate_file_naming(cls, v):
        allowed_naming = ["query_based", "timestamped", "numbered"]
        if v not in allowed_naming:
            raise ValueError(f'file_naming must be one of: {allowed_naming}')
        return v

class GenerationConfig(BaseModel):
    """Configuration for documentation generation."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    detail_level: str = Field(default="comprehensive")
    include_examples: bool = True
    max_results: int = 10
    timeout: int = 60
    retry_attempts: int = 3
    retry_delay: float = 1.0
    
    @field_validator('detail_level')
    @classmethod
    def validate_detail_level(cls, v):
        allowed_levels = ["concise", "comprehensive"]
        if v not in allowed_levels:
            raise ValueError(f'detail_level must be one of: {allowed_levels}')
        return v
    
    @field_validator('max_results')
    @classmethod
    def validate_max_results(cls, v):
        if v < 1 or v > 50:
            raise ValueError('max_results must be between 1 and 50')
        return v

class LoggingConfig(BaseModel):
    """Configuration for logging."""
    model_config = ConfigDict(arbitrary_types_allowed=True)
    
    level: str = Field(default="INFO")
    format: str = Field(default="text")  # text, json
    file_path: Optional[str] = None
    max_file_size: int = 10485760  # 10MB
    backup_count: int = 5
    
    @field_validator('level')
    @classmethod
    def validate_level(cls, v):
        allowed_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if v.upper() not in allowed_levels:
            raise ValueError(f'level must be one of: {allowed_levels}')
        return v.upper()
    
    @field_validator('format')
    @classmethod
    def validate_format(cls, v):
        allowed_formats = ["text", "json"]
        if v not in allowed_formats:
            raise ValueError(f'format must be one of: {allowed_formats}')
        return v

class DevGuidesConfig(BaseSettings):
    """Main configuration class for DevGuides."""
    model_config = SettingsConfigDict(
        env_prefix='DEVGUIDES_',
        env_nested_delimiter='__',
        case_sensitive=False,
        arbitrary_types_allowed=True,
        extra='ignore'
    )
    
    server: ServerConfig = Field(default_factory=ServerConfig)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    output: OutputConfig = Field(default_factory=OutputConfig)
    generation: GenerationConfig = Field(default_factory=GenerationConfig)
    logging: LoggingConfig = Field(default_factory=LoggingConfig)
    
    @classmethod
    def from_file(cls, config_path: Path) -> "DevGuidesConfig":
        """Load configuration from YAML file."""
        with open(config_path, 'r') as f:
            config_dict = yaml.safe_load(f)
        # Pydantic settings will automatically merge with env vars if we initialize with dict
        return cls(**config_dict)
    
    @classmethod
    def from_env(cls) -> "DevGuidesConfig":
        """Load configuration from environment variables."""
        # pydantic-settings handles this automatically
        return cls()
    
    def merge(self, other: "DevGuidesConfig") -> "DevGuidesConfig":
        """Merge with another configuration (for CLI override)."""
        # Deep merge configuration dictionaries
        merged_dict = self.model_dump()
        other_dict = other.model_dump()
        
        for section, values in other_dict.items():
            if values and isinstance(values, dict):
                merged_dict[section].update(values)
            elif values is not None:
                merged_dict[section] = values
        
        return DevGuidesConfig(**merged_dict)
    
    def get_server_command(self) -> str:
        """Get the full server command as a string."""
        parts = [self.server.command] + self.server.args
        return " ".join(parts)
    
    def is_openai_configured(self) -> bool:
        """Check if OpenAI is properly configured."""
        return (
            self.llm.provider == "openai" and
            self.llm.api_key is not None and
            len(self.llm.api_key.strip()) > 0
        )
    
    def validate_config(self) -> List[str]:
        """Validate configuration and return list of issues."""
        issues = []
        
        # Check MCP server configuration
        if not self.server.command.strip():
            issues.append("Server command cannot be empty")
        
        # For console scripts, args can be empty
        is_console_script = (self.server.command == "code_flow_graph_mcp_server" or
                           "code_flow_graph_mcp_server" in self.server.command)
        if not is_console_script and not self.server.args:
            issues.append("Server args cannot be empty for non-console script commands")
        
        # Check LLM configuration
        if self.llm.provider == "openai":
            # For official OpenAI (no base_url), API key is required
            # For local OpenAI-compatible services (with base_url), API key is optional
            if not self.llm.base_url and not self.llm.api_key:
                issues.append("OpenAI API key is required when using OpenAI provider (unless using base_url for local service)")
        
        if self.llm.temperature < 0 or self.llm.temperature > 2:
            issues.append("LLM temperature must be between 0 and 2")
        
        # Check output configuration
        if not self.output.output_directory.strip():
            issues.append("Output directory cannot be empty")
        
        # Test generation configuration
        if self.generation.max_results < 1:
            issues.append("Max results must be at least 1")
        
        return issues