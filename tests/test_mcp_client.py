"""Tests for CodeFlow MCP client."""

import pytest
import asyncio
from unittest.mock import Mock, AsyncMock, patch, MagicMock
import json

from devguides.core.mcp_client import CodeFlowMCPClient

class TestCodeFlowMCPClient:
    """Test CodeFlowMCPClient functionality."""
    
    @pytest.fixture
    def mock_config(self):
        """Mock configuration for testing."""
        return {
            "command": "python",
            "args": ["-m", "code_flow_graph.mcp_server"],
            "timeout": 30,
            "env": {"TEST_VAR": "test_value"}
        }
    
    @pytest.fixture
    def mcp_client(self, mock_config):
        """Create MCP client instance for testing."""
        return CodeFlowMCPClient(mock_config)
    
    def test_initialization(self, mcp_client, mock_config):
        """Test client initialization."""
        assert mcp_client.config == mock_config
        assert mcp_client.session is None
        assert mcp_client._connected is False
    
    @pytest.mark.asyncio
    async def test_connect_success(self, mcp_client):
        """Test successful connection to MCP server."""
        with patch('devguides.core.mcp_client.MCP_AVAILABLE', True):
            with patch('devguides.core.mcp_client.stdio_client') as mock_stdio:
                with patch('devguides.core.mcp_client.ClientSession') as MockSession:
                    # Create mocks
                    mock_read = Mock()
                    mock_write = Mock()
                    mock_session = Mock()
                    mock_session.initialize = AsyncMock()
                    
                    # Mock stdio_client as an async function that returns (read, write)
                    async def mock_stdio_async(*args, **kwargs):
                        return mock_read, mock_write
                    
                    mock_stdio.side_effect = mock_stdio_async
                    
                    # Mock ClientSession constructor to return mock_session
                    MockSession.return_value = mock_session
                    
                    # Test connection
                    await mcp_client.connect()
                    
                    # Verify connection was established
                    assert mcp_client._connected is True
                    assert mcp_client.session == mock_session
                    mock_session.initialize.assert_called_once()
                    
                    # Verify stdio_client was called with correct parameters
                    mock_stdio.assert_called_once_with(mcp_client._server_params)
    
    @pytest.mark.asyncio
    async def test_connect_failure(self, mcp_client):
        """Test connection failure handling."""
        with patch('devguides.core.mcp_client.MCP_AVAILABLE', True):
            with patch('devguides.core.mcp_client.stdio_client') as mock_stdio:
                # Simulate connection failure
                mock_stdio.side_effect = Exception("Connection failed")
                
                with pytest.raises(ConnectionError, match="Failed to connect to CodeFlow MCP server"):
                    await mcp_client.connect()
                
                assert mcp_client._connected is False
    
    @pytest.mark.asyncio
    async def test_disconnect(self, mcp_client):
        """Test disconnection."""
        # Setup connected client
        mock_session = Mock()
        mock_session.close = AsyncMock()
        mcp_client.session = mock_session
        mcp_client._connected = True
        
        # Test disconnection
        await mcp_client.disconnect()
        
        # Verify cleanup
        mock_session.close.assert_called_once()
        assert mcp_client.session is None
        assert mcp_client._connected is False
    
    @pytest.mark.asyncio
    async def test_semantic_search_success(self, mcp_client):
        """Test successful semantic search."""
        # Setup connected client
        mock_session = Mock()
        mock_session.call_tool = AsyncMock()
        mcp_client.session = mock_session
        mcp_client._connected = True
        
        # Mock search results
        mock_results = [
            {"fqn": "test.module.function", "relevance": 0.9, "file_path": "/test/path.py"}
        ]
        
        mock_response = Mock()
        mock_response.content = [Mock(type="text", text=json.dumps(mock_results))]
        mock_session.call_tool.return_value = mock_response
        
        # Test search
        results = await mcp_client.semantic_search("test query", n_results=5)
        
        # Verify results
        assert len(results) == 1
        assert results[0]["fqn"] == "test.module.function"
        assert results[0]["relevance"] == 0.9
        
        # Verify MCP call
        mock_session.call_tool.assert_called_once_with(
            "semantic_search",
            arguments={
                "query": "test query",
                "n_results": 5,
                "filters": {}
            }
        )
    
    @pytest.mark.asyncio
    async def test_semantic_search_mock_mode(self, mcp_client):
        """Test semantic search in mock mode (MCP not available)."""
        with patch('devguides.core.mcp_client.MCP_AVAILABLE', False):
            # Should return mock data
            results = await mcp_client.semantic_search("test query", n_results=3)
            
            assert len(results) == 3
            for i, result in enumerate(results):
                assert "fqn" in result
                assert "relevance" in result
                assert result["fqn"] == f"mock.module.function_{i}"
    
    @pytest.mark.asyncio
    async def test_get_call_graph_success(self, mcp_client):
        """Test successful call graph retrieval."""
        # Setup connected client
        mock_session = Mock()
        mock_session.call_tool = AsyncMock()
        mcp_client.session = mock_session
        mcp_client._connected = True
        
        # Mock call graph data
        mock_graph = {
            "nodes": [{"id": "func1"}, {"id": "func2"}],
            "edges": [{"from": "func1", "to": "func2"}]
        }
        
        mock_response = Mock()
        mock_response.content = [Mock(type="text", text=json.dumps(mock_graph))]
        mock_session.call_tool.return_value = mock_response
        
        # Test call graph retrieval
        fqns = ["test.module.func1", "test.module.func2"]
        result = await mcp_client.get_call_graph(fqns, format="json")
        
        # Verify results
        assert result["nodes"] == [{"id": "func1"}, {"id": "func2"}]
        assert result["edges"] == [{"from": "func1", "to": "func2"}]
    
    @pytest.mark.asyncio
    async def test_get_function_metadata_success(self, mcp_client):
        """Test successful function metadata retrieval."""
        # Setup connected client
        mock_session = Mock()
        mock_session.call_tool = AsyncMock()
        mcp_client.session = mock_session
        mcp_client._connected = True
        
        # Mock metadata
        mock_metadata = {
            "fqn": "test.module.function",
            "function_name": "function",
            "file_path": "/test/path.py",
            "line_number": 42,
            "docstring": "Test function"
        }
        
        mock_response = Mock()
        mock_response.content = [Mock(type="text", text=json.dumps(mock_metadata))]
        mock_session.call_tool.return_value = mock_response
        
        # Test metadata retrieval
        result = await mcp_client.get_function_metadata("test.module.function")
        
        # Verify results
        assert result["fqn"] == "test.module.function"
        assert result["function_name"] == "function"
        assert result["line_number"] == 42
    
    @pytest.mark.asyncio
    async def test_generate_mermaid_graph_success(self, mcp_client):
        """Test successful Mermaid diagram generation."""
        # Setup connected client
        mock_session = Mock()
        mock_session.call_tool = AsyncMock()
        mcp_client.session = mock_session
        mcp_client._connected = True
        
        # Mock Mermaid code
        mock_mermaid = "graph TD\\n    A[Start] --> B[End]"
        
        mock_response = Mock()
        mock_response.content = [Mock(type="text", text=mock_mermaid)]
        mock_session.call_tool.return_value = mock_response
        
        # Test Mermaid generation
        fqns = ["test.module.function"]
        result = await mcp_client.generate_mermaid_graph(fqns, llm_optimized=True)
        
        # Verify results
        assert result == mock_mermaid
    
    @pytest.mark.asyncio
    async def test_ping_success(self, mcp_client):
        """Test successful ping."""
        # Setup connected client
        mock_session = Mock()
        mock_session.call_tool = AsyncMock()
        mcp_client.session = mock_session
        mcp_client._connected = True
        
        mock_response = Mock()
        mock_session.call_tool.return_value = mock_response
        
        # Test ping
        result = await mcp_client.ping()
        
        # Verify ping succeeded
        assert result is True
        mock_session.call_tool.assert_called_once_with("ping", arguments={})
    
    @pytest.mark.asyncio
    async def test_get_available_tools(self, mcp_client):
        """Test getting available tools."""
        # Setup connected client
        mock_session = Mock()
        mock_session.list_tools = AsyncMock()
        mcp_client.session = mock_session
        mcp_client._connected = True
        
        # Mock tools - create proper tool objects with name attribute
        mock_tools = []
        for tool_name in ["semantic_search", "get_call_graph", "get_function_metadata"]:
            tool_mock = Mock()
            tool_mock.name = tool_name
            mock_tools.append(tool_mock)
        
        # Mock response needs to have a 'tools' attribute containing the tool list
        mock_response = Mock()
        mock_response.tools = mock_tools  # This is what the implementation expects: tools.tools
        mock_session.list_tools.return_value = mock_response
        
        # Test getting tools
        tools = await mcp_client.get_available_tools()
        
        # Verify tools list contains the expected tool names
        assert "semantic_search" in tools
        assert "get_call_graph" in tools
        assert "get_function_metadata" in tools
    
    def test_is_connected_property(self, mcp_client):
        """Test is_connected property."""
        # Not connected
        assert mcp_client.is_connected is False
        
        # Connected
        mcp_client._connected = True
        mcp_client.session = Mock()
        assert mcp_client.is_connected is True
    
    def test_server_params_setup(self, mock_config):
        """Test server parameters setup."""
        client = CodeFlowMCPClient(mock_config)
        
        # Verify server params were created correctly
        assert client._server_params is not None
        assert client._server_params.command == "python"
        assert client._server_params.args == ["-m", "code_flow_graph.mcp_server"]
        assert "TEST_VAR" in client._server_params.env
        assert client._server_params.env["TEST_VAR"] == "test_value"
    
    @pytest.mark.asyncio
    async def test_retry_logic_on_failure(self, mcp_client):
        """Test retry logic on MCP operation failure."""
        # Setup connected client
        mock_session = Mock()
        mock_session.call_tool = AsyncMock()
        mcp_client.session = mock_session
        mcp_client._connected = True
        
        # Mock permanent failure to test error handling
        mock_session.call_tool.side_effect = Exception("Persistent failure")
        
        # Test semantic search with failure
        results = await mcp_client.semantic_search("test query")
        
        # Should return empty list when all retries fail
        assert len(results) == 0
        # Should have attempted the call multiple times due to retry logic
        assert mock_session.call_tool.call_count >= 1