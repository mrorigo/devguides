# DevGuides Project Guidelines for AI Agents

## Project Foundation
- **Package Manager**: `uv` only - never use `pip` directly
- **Virtual Environment**: Use `uv venv` and activate in new shells with `source .venv/bin/activate`
- **Code Location**: All code under `devguides/` directory hierarchy
- **Language**: Python 3.8+ (no async/await in interface definitions)
- **Architecture**: Modular design - separate CLI, core engine, and utilities

## Critical Implementation Details

### MCP Integration Requirements
- **Dependency**: `mcp[cli]` must be included in dependencies (not just `mcp`)
- **Communication**: Uses stdio-based transport with `StdioServerParameters`
- **Server Requirement**: CodeFlow MCP server must be running before DevGuides operations
- **Error Handling**: Implement connection retry with exponential backoff
- **Transport Config**: 
  ```python
  server_params = StdioServerParameters(
      command="python",
      args=["-m", "code_flow_graph.mcp_server"],
      env={"PYTHONPATH": os.environ.get("PYTHONPATH", "")}
  )
  ```

### Configuration Management
- **Hierarchy**: CLI flags > project config (`.devguides.yaml`) > user config > env vars > defaults
- **Validation**: Use Pydantic models for config validation
- **Environment Variables**: Use `DEVGUIDES_` prefix for env-based config
- **Config Files**: YAML format with clear section separation

### Project Structure (Non-Negotiable)
```
devguides/
├── cli/           # CLI interface only
├── core/          # Business logic and integrations  
├── templates/     # Document templates
├── utils/         # Shared utilities
└── config/        # Configuration defaults
```

### Key Dependencies & Versions
```toml
dependencies = [
    "click>=8.0.0",           # CLI framework
    "pydantic>=2.0.0",        # Configuration validation
    "pyyaml>=6.0",            # YAML config parsing
    "mcp[cli]>=0.5.0",        # MCP protocol client (CLI variant)
    "openai>=1.0.0",          # LLM API integration
    "rich>=13.0.0",           # Terminal output formatting
    "structlog>=22.0.0",      # Structured logging
]
```

### Development Standards

#### Code Quality
- **Linting**: `black` for formatting, `isort` for imports, `mypy` for type checking
- **Testing**: Mandatory pytest with `pytest-asyncio` for async tests
- **Coverage**: Maintain 80%+ test coverage on core functionality
- **Documentation**: All public interfaces must have docstrings

#### Logging Strategy
- **Library**: `structlog` for structured JSON logging
- **Levels**: Use appropriate levels (INFO for normal, WARNING for recoverable errors, ERROR for failures)
- **Context**: Always include relevant identifiers (query, user, project path) in log context

#### Error Handling Patterns
```python
# Retry decorator for network/MCP operations
@retry_with_backoff(max_attempts=3, base_delay=1.0)
async def mcp_operation():
    # MCP operations with automatic retry

# Graceful degradation
try:
    result = await complex_operation()
except SpecificError as e:
    logger.warning("falling_back_to_simple_mode", error=str(e))
    return await simple_fallback()
```

### Testing Requirements
- **Unit Tests**: Test individual components in isolation
- **Integration Tests**: End-to-end flow testing with mocked MCP server
- **Test Structure**: `tests/test_[component].py` for each major component
- **Async Testing**: Use `@pytest.mark.asyncio` for all async tests
- **Mock Strategy**: Mock MCP server responses, not the transport layer

### Configuration Patterns

#### Pydantic Configuration Models
```python
class ServerConfig(BaseModel):
    command: str = Field(default="python")
    args: List[str] = Field(default=["-m", "code_flow_graph.mcp_server"])
    timeout: int = 30
    
    @validator('timeout')
    def validate_timeout(cls, v):
        if v < 1 or v > 300:
            raise ValueError('Timeout must be between 1 and 300 seconds')
        return v
```

#### Environment Variable Handling
```python
# Load config with environment override
if os.getenv("DEVGUIDES_OPENAI_API_KEY"):
    config.llm.api_key = os.getenv("DEVGUIDES_OPENAI_API_KEY")
```

### MCP Client Implementation Details
- **Session Management**: Always use context manager for `ClientSession`
- **Tool Calls**: Validate tool responses before processing
- **Error Types**: Handle `ConnectionError`, `TimeoutError`, and tool-specific errors
- **Response Parsing**: Check content type before JSON parsing
- **Cleanup**: Always disconnect in finally blocks or context exit

### LLM Integration Patterns
- **Provider Abstraction**: Support multiple LLM providers through abstract base class
- **Prompt Engineering**: Structured prompts with clear sections and context limits
- **Token Management**: Implement token counting for long responses
- **Rate Limiting**: Use `asyncio-throttle` for API rate limiting
- **Local Fallback**: Provide local model option for sensitive codebases

### Template System
- **Base Class**: All templates inherit from `BaseTemplate`
- **Content Sections**: Consistent structure (Overview, Components, Analysis, Examples)
- **Diagram Integration**: Embed Mermaid diagrams when available
- **Markdown Generation**: Clean, valid markdown output with proper heading hierarchy

### Performance Considerations
- **Concurrent Operations**: Use `asyncio.gather()` for parallel MCP tool calls
- **Memory Management**: Limit context size for large codebases
- **Caching**: Cache analysis results to avoid re-processing
- **Resource Limits**: Implement timeout and memory constraints

### Security Requirements
- **API Key Management**: Support both env vars and secure key files
- **Code Privacy**: Option to exclude sensitive patterns from analysis
- **Local Processing**: Support for local LLM models when required
- **Input Validation**: Sanitize all user inputs before processing

### Documentation Standards
- **Generated Docs**: Always include source references and confidence indicators
- **Code Comments**: Explain "why" not "what" for complex logic
- **README Structure**: Include setup, usage examples, and architecture overview
- **API Documentation**: Use consistent parameter naming and return types

### CI/CD Integration
- **Python Versions**: Test on 3.8, 3.9, 3.10, 3.11
- **Build Process**: Use `uv` for dependency resolution and building
- **Quality Gates**: Linting, type checking, and coverage must pass
- **Release Process**: Tagged releases with changelog

### Debugging & Troubleshooting
- **Common Issues**:
  - MCP server not running: Check server command and working directory
  - Connection timeouts: Verify server responsiveness and increase timeout
  - LLM API errors: Check API key validity and rate limits
  - Empty results: Verify CodeFlow analysis completeness

- **Debug Tools**: 
  - Enable structured logging with `DEVGUIDES_LOG_LEVEL=DEBUG`
  - Use `--verbose` CLI flag for detailed operation logs
  - Test MCP connectivity with `devguides config --test-server`

### Version Compatibility
- **CodeFlow**: Requires specific MCP server version - pin in documentation
- **Python**: No asyncio in interface definitions (Python 3.8 compatible)
- **Dependencies**: Pin major versions, allow minor/patch updates
- **Breaking Changes**: Document any API changes with migration guides

### Non-Obvious Gotchas
- **MCP Response Parsing**: Always check `content[0].type` before accessing `.text`
- **Async Session Management**: Use async context managers for MCP client sessions
- **Configuration Merging**: Implement proper deep merge for nested config objects
- **Template Inheritance**: Base template methods must be callable with keyword args
- **Error Recovery**: Some MCP tool failures are transient - implement retry logic
- **Token Limits**: LLM responses may be truncated - implement token counting
- **File Permissions**: Generated docs respect source file permissions

### When to Update This Document
- Add new ambiguity resolution patterns discovered during implementation
- Update version requirements when dependencies change
- Add newGotchas found during testing and debugging
- Document new configuration options or CLI flags
- Update testing patterns or mock strategies

Remember: This document should remain concise but comprehensive. Focus on non-obvious details that would cause bugs or confusion for implementing agents.