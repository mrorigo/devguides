"""Documentation generation engine for DevGuides."""

import asyncio
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
import time

from ..utils.logging import get_logger
from .mcp_client import CodeFlowMCPClient
from .llm_handler import LLMHandler

logger = get_logger(__name__)

@dataclass
class GenerationRequest:
    """Request for documentation generation."""
    query: str
    detail_level: str = "comprehensive"
    output_format: str = "markdown"
    include_diagrams: bool = True
    max_results: int = 10
    template: str = "default"
    timeout: int = 60
    
@dataclass
class GenerationResult:
    """Result of documentation generation."""
    content: str
    mermaid_diagram: Optional[str] = None
    metadata: Optional[Dict[str, Any]] = None
    success: bool = True
    error_message: Optional[str] = None
    execution_time: float = 0.0

class DocumentationEngine:
    """Main documentation generation engine."""
    
    def __init__(self, mcp_client: CodeFlowMCPClient, llm_handler: LLMHandler):
        """Initialize the documentation engine."""
        self.mcp_client = mcp_client
        self.llm_handler = llm_handler
        
        logger.info("documentation_engine_initialized")
    
    async def generate(self, request: GenerationRequest) -> GenerationResult:
        """Main documentation generation pipeline."""
        start_time = time.time()
        
        try:
            logger.info("generation_started",
                       query=request.query,
                       detail_level=request.detail_level,
                       max_results=request.max_results)
            
            # Step 1: Validate request
            self._validate_request(request)
            
            # Step 2: Ensure MCP connection is established
            logger.info("establishing_mcp_connection")
            try:
                await self.mcp_client.connect(request.timeout)
            except Exception as e:
                logger.warning("mcp_connection_failed", error=str(e))
                logger.info("falling_back_to_mock_mode")
                # Continue with mock data - all MCP methods will use mock data
                pass
            
            # Step 3: Semantic search with CodeFlow (will use mock data if connection failed)
            search_results = await self.mcp_client.semantic_search(
                request.query,
                request.max_results
            )
            
            if not search_results:
                logger.warning("no_search_results_found", query=request.query)
                return GenerationResult(
                    content="",
                    success=False,
                    error_message="No relevant code found for query",
                    execution_time=time.time() - start_time
                )
            
            logger.info("search_completed", results_count=len(search_results))
            
            # Step 4: Extract function FQNs for call graph analysis
            fqns = [result.get("fqn") for result in search_results if result.get("fqn") and isinstance(result.get("fqn"), str)]
            
            # Step 5: Get call graph if requested and we have FQNs
            call_graph = {}
            mermaid_diagram = None
            
            if request.include_diagrams and fqns:
                logger.info("generating_call_graph")
                call_graph = await self.mcp_client.get_call_graph(fqns)
                
                if call_graph:
                    logger.info("generating_mermaid_diagram")
                    mermaid_diagram = await self.mcp_client.generate_mermaid_graph(
                        fqns,
                        llm_optimized=True
                    )
            
            # Step 6: Get detailed metadata for key functions
            logger.info("fetching_function_metadata")
            function_metadata = []
            
            # Limit to top 5 functions for context to avoid token limits
            for result in search_results[:5]:
                if result.get("fqn") and isinstance(result.get("fqn"), str):
                    metadata = await self.mcp_client.get_function_metadata(result["fqn"])
                    function_metadata.append(metadata)
            
            # Step 7: Build context for LLM
            context = self._build_context(
                search_results,
                call_graph,
                function_metadata,
                request
            )
            
            # Step 8: Generate documentation with LLM
            logger.info("generating_llm_documentation")
            llm_content = await self.llm_handler.generate_documentation(
                request.query,
                context,
                request.detail_level
            )
            
            # Step 9: Apply template and format output
            final_content = self._apply_template(
                llm_content,
                mermaid_diagram,
                request.template,
                request.detail_level,
                request.output_format
            )
            
            # Step 10: Create result
            execution_time = time.time() - start_time
            result = GenerationResult(
                content=final_content,
                mermaid_diagram=mermaid_diagram,
                metadata={
                    "search_results_count": len(search_results),
                    "functions_analyzed": len(fqns),
                    "detail_level": request.detail_level,
                    "query": request.query,
                    "template": request.template,
                    "include_diagrams": request.include_diagrams
                },
                success=True,
                execution_time=execution_time
            )
            
            logger.info("generation_completed",
                       execution_time=execution_time,
                       content_length=len(final_content))
            
            return result
            
        except asyncio.TimeoutError:
            logger.error("generation_timeout", timeout=request.timeout)
            return GenerationResult(
                content="",
                success=False,
                error_message=f"Generation timed out after {request.timeout} seconds",
                execution_time=time.time() - start_time
            )
            
        except Exception as e:
            logger.exception("generation_failed", error=str(e))
            return GenerationResult(
                content="",
                success=False,
                error_message=str(e),
                execution_time=time.time() - start_time
            )
    
    def _validate_request(self, request: GenerationRequest) -> None:
        """Validate generation request parameters."""
        if not request.query.strip():
            raise ValueError("Query cannot be empty")
        
        valid_detail_levels = ["concise", "comprehensive"]
        if request.detail_level not in valid_detail_levels:
            raise ValueError(f"Invalid detail level: {request.detail_level}. Must be one of: {valid_detail_levels}")
        
        valid_formats = ["markdown", "html"]
        if request.output_format not in valid_formats:
            raise ValueError(f"Invalid output format: {request.output_format}. Must be one of: {valid_formats}")
        
        if request.max_results < 1 or request.max_results > 50:
            raise ValueError("max_results must be between 1 and 50")
        
        if request.timeout < 10 or request.timeout > 300:
            raise ValueError("timeout must be between 10 and 300 seconds")
    
    def _build_context(
        self, 
        search_results: List[Dict], 
        call_graph: Dict, 
        function_metadata: List[Dict], 
        request: GenerationRequest
    ) -> Dict[str, Any]:
        """Build context for LLM from search results and metadata."""
        
        context = {
            "query": request.query,
            "detail_level": request.detail_level,
            "search_results": search_results,
            "call_graph": call_graph,
            "function_metadata": function_metadata,
            "include_diagrams": request.include_diagrams,
            "summary": {
                "total_results": len(search_results),
                "functions_with_metadata": len(function_metadata),
                "has_call_graph": bool(call_graph),
                "has_mermaid_diagram": bool(call_graph and request.include_diagrams)
            }
        }
        
        return context
    
    def _apply_template(
        self, 
        llm_content: str, 
        mermaid_diagram: Optional[str], 
        template: str,
        detail_level: str,
        output_format: str
    ) -> str:
        """Apply template formatting to generated content."""
        
        # Extract title from LLM content (first heading)
        title = "Documentation"
        lines = llm_content.split('\n')
        for line in lines:
            if line.strip().startswith('#'):
                title = line.strip('#').strip()
                break
        
        # Start building the final content
        if output_format == "markdown":
            content = self._format_as_markdown(llm_content, mermaid_diagram, title, detail_level)
        elif output_format == "html":
            content = self._format_as_html(llm_content, mermaid_diagram, title, detail_level)
        else:
            content = llm_content  # Fallback
        
        return content
    
    def _format_as_markdown(
        self, 
        llm_content: str, 
        mermaid_diagram: Optional[str], 
        title: str,
        detail_level: str
    ) -> str:
        """Format content as markdown."""
        
        # Add header with metadata
        header = f"# {title}\n\n"
        
        metadata = f"*Generated by DevGuides on {time.strftime('%Y-%m-%d %H:%M:%S')}*"
        if detail_level == "concise":
            metadata += " *(concise overview)*"
        else:
            metadata += " *(comprehensive guide)*"
        
        header += f"{metadata}\n\n"
        
        # Add diagram if available
        diagram_section = ""
        if mermaid_diagram:
            diagram_section = f"\n## Call Flow\n\n```mermaid\n{mermaid_diagram}\n```\n\n"
        
        return f"{header}{llm_content}{diagram_section}"
    
    def _format_as_html(
        self, 
        llm_content: str, 
        mermaid_diagram: Optional[str], 
        title: str,
        detail_level: str
    ) -> str:
        """Format content as HTML."""
        
        # Basic HTML template (could be enhanced with CSS framework)
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - DevGuides</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 800px; margin: 0 auto; padding: 2rem; line-height: 1.6; }}
        h1, h2, h3 {{ color: #2563eb; }}
        code {{ background: #f3f4f6; padding: 0.2rem 0.4rem; border-radius: 0.25rem; }}
        pre {{ background: #f9fafb; padding: 1rem; border-radius: 0.5rem; overflow-x: auto; }}
        .metadata {{ color: #6b7280; font-style: italic; margin-bottom: 2rem; }}
        .mermaid {{ text-align: center; margin: 2rem 0; }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
</head>
<body>
    <h1>{title}</h1>
    <div class="metadata">
        Generated by DevGuides on {timestamp} {'(concise overview)' if detail_level == 'concise' else '(comprehensive guide)'}
    </div>
"""
        
        # Convert markdown-like content to HTML (basic conversion)
        content_html = llm_content.replace('\n\n', '</p>\n<p>')
        content_html = content_html.replace('\n', '<br>')
        content_html = f"<p>{content_html}</p>"
        
        html += content_html
        
        if mermaid_diagram:
            html += f"""
    <h2>Call Flow</h2>
    <div class="mermaid">
{mermaid_diagram}
    </div>
"""
        
        html += """
    <script>
        mermaid.initialize({ startOnLoad: true });
    </script>
</body>
</html>"""
        
        return html
    
    async def validate_configuration(self) -> List[str]:
        """Validate that the engine is properly configured."""
        issues = []
        
        # Check MCP client
        if not self.mcp_client:
            issues.append("MCP client not configured")
        elif not await self.mcp_client.ping():
            issues.append("MCP server not responding")
        
        # Check LLM handler
        if not self.llm_handler:
            issues.append("LLM handler not configured")
        elif not self.llm_handler.provider_available:
            issues.append(f"LLM provider '{self.llm_handler.config.get('provider')}' not available")
        
        return issues
    
    def get_status(self) -> Dict[str, Any]:
        """Get status information about the engine."""
        return {
            "mcp_connected": self.mcp_client.is_connected if self.mcp_client else False,
            "llm_provider_available": self.llm_handler.provider_available if self.llm_handler else False,
            "llm_provider_info": self.llm_handler.provider_info if self.llm_handler else {}
        }