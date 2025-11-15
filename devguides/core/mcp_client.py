"""CodeFlow MCP Client integration for DevGuides."""

import asyncio
import json
import os
import time
import subprocess
from typing import Dict, List, Optional, Any
from pathlib import Path
from contextlib import AsyncExitStack

# Import MCP types - assuming MCP is always available
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from datetime import timedelta

from ..utils.logging import get_logger
from ..utils.error_handling import retry_with_backoff

logger = get_logger(__name__)

class CodeFlowMCPClient:
    """Real CodeFlow MCP client - no mock fallbacks."""
    
    def __init__(self, config: Dict[str, Any]):
        """Initialize MCP client."""
        self.config = config
        self.session: Optional[ClientSession] = None
        self._server_process: Optional[subprocess.Popen] = None
        self._exit_stack: Optional[AsyncExitStack] = None
        self._connected = False
        
        logger.info("MCP_client_initialized")
    
    async def connect(self, timeout: float = 120.0) -> None:
        """Connect to CodeFlow server using AsyncExitStack pattern."""
        if self._connected and self.session:
            try:
                # Test existing connection
                await self.session.list_tools()
                logger.info("reusing_existing_mcp_connection")
                return
            except Exception as e:
                logger.warning("existing_connection_failed", error=str(e))
                await self.disconnect()
        
        # Use AsyncExitStack for proper resource management
        exit_stack = AsyncExitStack()
        
        try:
            logger.info("=== MCP CONNECTION START ===")
            logger.info("connecting_to_codeflow_mcp_server")
            
            # Get server config from config
            server_command = self.config.get("command", "bash")
            server_args = self.config.get("args", [])
            
            # Handle run.sh script - use absolute path if provided
            script_path = None
            if server_command.endswith("run.sh"):
                if os.path.isabs(server_command):
                    # Use absolute path
                    script_path = Path(server_command)
                    working_dir = str(script_path.parent)
                    logger.info("run_from_absolute_path",
                               script_path=str(script_path),
                               working_dir=working_dir,
                               exists=script_path.exists())
                else:
                    # Use relative path from parent directory
                    working_dir = "../codeflowgraph"
                    script_path = Path(working_dir) / server_command
                    logger.info("run_from_codeflowgraph_dir",
                               working_dir=working_dir,
                               script_path=str(script_path),
                               exists=script_path.exists())
            else:
                working_dir = self.config.get("working_directory", ".")
            
            logger.info("server_config",
                       server_command=server_command,
                       server_args=server_args,
                       working_dir=working_dir,
                       pythonpath=os.environ.get("PYTHONPATH", ""))
            
            # For run.sh, we need to make sure it's executable
            if server_command.endswith("run.sh"):
                if script_path and script_path.exists():
                    # Make sure script is executable
                    os.chmod(script_path, 0o755)
                    logger.info("made_run_sh_executable", path=str(script_path))
                else:
                    logger.error("run_sh_script_not_found", path=str(script_path) if script_path else "unknown")
                    raise ConnectionError(f"run.sh script not found: {script_path}")
            
            # Set up environment properly
            # For run.sh, we need a clean environment (no venv variables)
            if server_command.endswith("run.sh"):
                # Clean environment for run.sh - remove venv variables
                env_vars = {}
                # Only keep essential system variables
                for key in ['PATH', 'HOME', 'SHELL', 'USER', 'LANG']:
                    if key in os.environ:
                        env_vars[key] = os.environ[key]
                # Set PYTHONPATH to codeflowgraph only to avoid mcp.py shadowing
                env_vars["PYTHONPATH"] = "."
                # Ensure unbuffered output
                env_vars["PYTHONUNBUFFERED"] = "1"
                logger.info("clean_environment_for_run_sh",
                           pythonpath=env_vars["PYTHONPATH"],
                           working_dir=working_dir,
                           venv_active=bool(os.environ.get("VIRTUAL_ENV")),
                           unbuffered=env_vars["PYTHONUNBUFFERED"])
            else:
                # Standard environment for direct Python commands
                env_vars = os.environ.copy()
                pythonpath = env_vars.get("PYTHONPATH", "")
                if "../codeflowgraph" not in pythonpath:
                    env_vars["PYTHONPATH"] = f"../codeflowgraph:{pythonpath}"
                env_vars["PYTHONUNBUFFERED"] = "1"
                logger.info("standard_environment_setup",
                           pythonpath=env_vars["PYTHONPATH"],
                           cwd=working_dir,
                           unbuffered=env_vars["PYTHONUNBUFFERED"])
            
            logger.info("connecting_to_mcp_server_via_stdio")
            
            # Create server parameters
            server_params = StdioServerParameters(
                command=server_command,
                args=server_args,
                env=env_vars
            )
            
            # Use AsyncExitStack for proper resource management
            logger.info("stdio_client_connecting")
            stdio_transport = await exit_stack.enter_async_context(
                stdio_client(server_params)
            )
            
            read, write = stdio_transport
            
            logger.info("stdio_client_connected")
            
            # Create session with increased timeout
            self.session = await exit_stack.enter_async_context(
                ClientSession(
                    read,
                    write,
                    read_timeout_seconds=timedelta(seconds=60)  # Increased timeout for initialization
                )
            )
            
            logger.info("session_created_with_extended_timeout")
            
            # Initialize session with retry logic
            logger.info("attempting_mcp_session_initialization")
            max_attempts = 2
            for attempt in range(max_attempts):
                attempt_timeout = (attempt + 1) * 30.0  # 30s, 60s
                try:
                    logger.info("session_initialization_attempt", attempt=attempt + 1, timeout=attempt_timeout)
                    
                    await asyncio.wait_for(
                        self.session.initialize(),
                        timeout=attempt_timeout
                    )
                    
                    logger.info("mcp_session_initialized_successfully")
                    
                    # Test that the session is working
                    tools = await self.session.list_tools()
                    logger.info("connection_test_successful",
                               tools=[t.name for t in tools.tools])
                    
                    # Store the exit stack for cleanup
                    self._exit_stack = exit_stack
                    self._connected = True
                    logger.info("=== MCP CONNECTION SUCCESSFUL ===")
                    return
                    
                except Exception as e:
                    logger.warning("session_initialization_attempt_failed",
                                 attempt=attempt + 1,
                                 timeout=attempt_timeout,
                                 error=str(e))
                    
                    if attempt < max_attempts - 1:
                        logger.info("waiting_before_retry", wait_time=5)
                        await asyncio.sleep(5)
                    else:
                        logger.error("all_session_initialization_attempts_failed")
                        raise ConnectionError(f"Failed to initialize MCP session after {max_attempts} attempts") from e
            
        except Exception as e:
            logger.error("=== MCP CONNECTION FAILED ===")
            logger.error("mcp_connection_failed", error=str(e))
            
            # Clean up resources
            try:
                await exit_stack.aclose()
            except Exception as cleanup_error:
                logger.warning("cleanup_error", error=str(cleanup_error))
            
            raise
    
    async def disconnect(self) -> None:
        """Disconnect from server and clean up."""
        try:
            self._connected = False
            
            if self._exit_stack:
                try:
                    await self._exit_stack.aclose()
                    self._exit_stack = None
                    logger.info("exit_stack_closed")
                except Exception as e:
                    logger.warning("exit_stack_close_error", error=str(e))
            
            if self.session:
                try:
                    await self.session.__aexit__(None, None, None)
                except Exception as e:
                    logger.warning("session_close_error", error=str(e))
                self.session = None
            
            if self._server_process:
                try:
                    self._server_process.terminate()
                    self._server_process.wait(timeout=5)
                    logger.info("server_process_terminated")
                except Exception as e:
                    logger.warning("server_termination_error", error=str(e))
                    try:
                        self._server_process.kill()
                    except Exception:
                        pass
                self._server_process = None
            
            logger.info("mcp_disconnected")
            
        except Exception as e:
            logger.warning("disconnect_error", error=str(e))
    
    async def _cleanup(self) -> None:
        """Emergency cleanup."""
        if self._exit_stack:
            try:
                await self._exit_stack.aclose()
            except Exception:
                pass
            self._exit_stack = None
        
        if self._server_process:
            try:
                self._server_process.terminate()
                self._server_process.wait(timeout=5)
            except Exception:
                try:
                    self._server_process.kill()
                except Exception:
                    pass
            self._server_process = None
        
        self._connected = False
        self.session = None
    
    async def semantic_search(self, query: str, n_results: int = 10) -> List[Dict[str, Any]]:
        """Search for relevant code elements."""
        if not self._connected or not self.session:
            raise ConnectionError("Not connected to CodeFlow MCP server")
        
        try:
            logger.info("semantic_search_request", query=query, n_results=n_results)
            
            result = await self.session.call_tool(
                "semantic_search",
                arguments={
                    "query": query,
                    "n_results": n_results,
                    "filters": {},
                    "format": "json"  # Request JSON format for DevGuides
                }
            )
            
            if result.content and result.content[0].type == "text":
                try:
                    parsed_response = json.loads(result.content[0].text)
                    # Extract results field from server response
                    search_results = parsed_response.get("results", [])
                    logger.info("semantic_search_completed", results_count=len(search_results))
                    return search_results
                except json.JSONDecodeError as e:
                    logger.error("semantic_search_json_parse_failed", error=str(e))
                    raise
            else:
                logger.warning("semantic_search_empty_response")
                return []
                
        except Exception as e:
            logger.error("semantic_search_failed", error=str(e))
            raise
    
    async def get_call_graph(self, fqns: List[str], format: str = "json") -> Dict[str, Any]:
        """Get call graph for functions."""
        if not self._connected or not self.session:
            raise ConnectionError("Not connected to CodeFlow MCP server")
        
        try:
            logger.info("get_call_graph_request", fqns_count=len(fqns), format=format)
            
            result = await self.session.call_tool(
                "get_call_graph",
                arguments={
                    "fqns": fqns,
                    "format": format
                }
            )
            
            if result.content and result.content[0].type == "text":
                call_graph = json.loads(result.content[0].text)
                logger.info("get_call_graph_completed", format=format)
                return call_graph
            else:
                logger.warning("get_call_graph_empty_response")
                return {}
                
        except Exception as e:
            logger.error("get_call_graph_failed", error=str(e))
            raise
    
    async def get_function_metadata(self, fqn: str) -> Dict[str, Any]:
        """Get function metadata."""
        if not self._connected or not self.session:
            raise ConnectionError("Not connected to CodeFlow MCP server")
        
        try:
            logger.info("get_function_metadata_request", fqn=fqn)
            
            result = await self.session.call_tool(
                "get_function_metadata",
                arguments={"fqn": fqn}
            )
            
            if result.content and result.content[0].type == "text":
                metadata = json.loads(result.content[0].text)
                logger.info("get_function_metadata_completed", fqn=fqn)
                return metadata
            else:
                logger.warning("get_function_metadata_empty_response", fqn=fqn)
                return {}
                
        except Exception as e:
            logger.error("get_function_metadata_failed", fqn=fqn, error=str(e))
            raise
    
    async def generate_mermaid_graph(self, fqns: List[str], llm_optimized: bool = False) -> str:
        """Generate Mermaid diagram."""
        if not self._connected or not self.session:
            raise ConnectionError("Not connected to CodeFlow MCP server")
        
        try:
            logger.info("generate_mermaid_graph_request", 
                       fqns_count=len(fqns), llm_optimized=llm_optimized)
            
            result = await self.session.call_tool(
                "generate_mermaid_graph",
                arguments={
                    "fqns": fqns,
                    "llm_optimized": llm_optimized
                }
            )
            
            if result.content and result.content[0].type == "text":
                mermaid_code = result.content[0].text
                logger.info("generate_mermaid_graph_completed")
                return mermaid_code
            else:
                logger.warning("generate_mermaid_graph_empty_response")
                return ""
                
        except Exception as e:
            logger.error("generate_mermaid_graph_failed", error=str(e))
            raise
    
    async def ping(self) -> bool:
        """Test server connectivity."""
        if not self._connected or not self.session:
            return False
        
        try:
            result = await self.session.call_tool("ping", arguments={})
            return result.content is not None
        except Exception:
            return False
    
    @property
    def is_connected(self) -> bool:
        """Check if connected."""
        return self._connected and self.session is not None