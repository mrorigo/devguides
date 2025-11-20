"""Documentation generation engine for DevGuides."""

import asyncio
from typing import Dict, List, Any, Optional, Union
from dataclasses import dataclass
import time
import os
from pathlib import Path

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
    max_files: int = 5
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
            await self.mcp_client.connect(request.timeout)
            
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
            
            # DEBUG: Log search results structure to verify FQN presence
            if search_results:
                logger.info("search_results_sample", 
                           first_result_keys=list(search_results[0].keys()) if search_results else [],
                           first_result_metadata_keys=list(search_results[0].get("metadata", {}).keys()) if search_results else [])
            
            # Step 4: Extract function FQNs for call graph analysis
            # FQNs are in metadata.fully_qualified_name, not at top level
            fqns = []
            for result in search_results:
                metadata = result.get("metadata", {})
                fqn = metadata.get("fully_qualified_name")
                if fqn and isinstance(fqn, str):
                    fqns.append(fqn)
            
            logger.info("fqns_extracted", count=len(fqns), fqns=fqns)
            
            # Step 5: Get call graph if requested and we have FQNs
            call_graph = {}
            mermaid_diagram = None
            
            if request.include_diagrams and fqns:
                logger.info("generating_call_graph")
                call_graph = await self.mcp_client.get_call_graph(fqns)
            
            # Step 6: Get detailed metadata for key functions
            logger.info("fetching_function_metadata")
            function_metadata = []
            
            # Limit to top 5 functions for context to avoid token limits
            for result in search_results[:5]:
                if result.get("fqn") and isinstance(result.get("fqn"), str):
                    metadata = await self.mcp_client.get_function_metadata(result["fqn"])
                    function_metadata.append(metadata)
            
            # Step 7: Generate Mermaid diagram BEFORE LLM generation
            # This way the LLM knows what diagram will be included
            mermaid_diagram = None
            if request.include_diagrams and fqns:
                try:
                    logger.info("generating_mermaid_diagram")
                    mermaid_diagram = await self.mcp_client.generate_mermaid_graph(
                        fqns, 
                        llm_optimized=True
                    )
                    logger.info("mermaid_diagram_generated", 
                               diagram_length=len(mermaid_diagram) if mermaid_diagram else 0)
                except Exception as e:
                    logger.warning("mermaid_diagram_generation_failed", error=str(e))
                    mermaid_diagram = None
            
            # Step 7.5: Expand search results with file content
            logger.info("expanding_search_results_with_file_content")
            expanded_files = self._expand_search_results(search_results, request.max_files)
            
            # Step 8: Build context for LLM (now includes diagram info and expanded files)
            context = {
                "search_results": search_results,
                "call_graph": call_graph,
                "function_metadata": function_metadata,
                "query": request.query,
                "detail_level": request.detail_level,
                "has_mermaid_diagram": bool(mermaid_diagram),
                "mermaid_diagram_preview": mermaid_diagram[:200] + "..." if mermaid_diagram and len(mermaid_diagram) > 200 else mermaid_diagram,
                "expanded_files": expanded_files
            }
            
            # Step 9: Generate documentation with LLM
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
                request.output_format,
                query=request.query,
                search_results_count=len(search_results),
                functions_analyzed=len(fqns)
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
            },
            "project_context": self._get_project_context()
        }
        
        return context
    
    def _get_project_context(self) -> str:
        """Get project context from AGENTS.md or README.md."""
        try:
            # Check for AGENTS.md first
            agents_path = Path("AGENTS.md")
            if agents_path.exists() and agents_path.is_file():
                logger.info("using_agents_md_context")
                return agents_path.read_text(encoding="utf-8")
            
            # Fallback to README.md
            readme_path = Path("README.md")
            if readme_path.exists() and readme_path.is_file():
                logger.info("using_readme_md_context")
                return readme_path.read_text(encoding="utf-8")
            
            logger.info("no_project_context_found")
            return ""
            
        except Exception as e:
            logger.warning("failed_to_read_project_context", error=str(e))
            return ""
    
    def _expand_search_results(self, search_results: List[Dict], max_files: int) -> Dict[str, str]:
        """Expand search results with surrounding file content.
        
        Args:
            search_results: List of search results from MCP
            max_files: Maximum number of files to expand
            
        Returns:
            Dictionary mapping filename to expanded content
        """
        from collections import defaultdict
        
        # Group results by file
        file_ranges = defaultdict(list)
        for result in search_results:
            filename = result.get("filename")
            line_number = result.get("line_number")
            
            if filename and line_number is not None:
                file_ranges[filename].append(line_number)
        
        # Limit to max_files
        files_to_expand = list(file_ranges.keys())[:max_files]
        expanded_files = {}
        
        for filename in files_to_expand:
            try:
                file_path = Path(filename)
                if not file_path.exists():
                    logger.warning("file_not_found", filename=filename)
                    continue
                
                # Read entire file
                with open(file_path, 'r', encoding='utf-8') as f:
                    lines = f.readlines()
                
                total_lines = len(lines)
                line_numbers = file_ranges[filename]
                
                # Calculate ranges (100 lines before and after each match)
                ranges = []
                for line_num in line_numbers:
                    start = max(0, line_num - 100)
                    end = min(total_lines, line_num + 100)
                    ranges.append((start, end))
                
                # Merge overlapping ranges
                merged_ranges = self._merge_ranges(ranges)
                
                # Build content with line numbers
                content_parts = []
                for start, end in merged_ranges:
                    content_parts.append(f"[Lines {start+1}-{end}]")
                    content_parts.append(''.join(lines[start:end]))
                
                expanded_files[filename] = '\n'.join(content_parts)
                logger.info("file_expanded", filename=filename, ranges=len(merged_ranges))
                
            except Exception as e:
                logger.warning("failed_to_expand_file", filename=filename, error=str(e))
        
        return expanded_files
    
    def _merge_ranges(self, ranges: List[tuple]) -> List[tuple]:
        """Merge overlapping or adjacent ranges.
        
        Args:
            ranges: List of (start, end) tuples
            
        Returns:
            List of merged (start, end) tuples
        """
        if not ranges:
            return []
        
        # Sort by start position
        sorted_ranges = sorted(ranges)
        merged = [sorted_ranges[0]]
        
        for current_start, current_end in sorted_ranges[1:]:
            last_start, last_end = merged[-1]
            
            # Check if ranges overlap or are adjacent
            if current_start <= last_end:
                # Merge by extending the end
                merged[-1] = (last_start, max(last_end, current_end))
            else:
                # No overlap, add as new range
                merged.append((current_start, current_end))
        
        return merged
    
    def _apply_template(
        self, 
        llm_content: str, 
        mermaid_diagram: Optional[str], 
        template: str,
        detail_level: str,
        output_format: str,
        query: str,
        search_results_count: int,
        functions_analyzed: int
    ) -> str:
        """Apply template formatting to generated content using Jinja2."""
        
        from jinja2 import Environment, PackageLoader, select_autoescape
        
        # Extract title from LLM content (first heading)
        title = "Documentation"
        lines = llm_content.split('\n')
        for line in lines:
            if line.strip().startswith('#'):
                title = line.strip('#').strip()
                break
        
        # Prepare template context
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        metadata = {
            "query": query,
            "detail_level": detail_level,
            "functions_analyzed": functions_analyzed,
            "search_results_count": search_results_count
        }
        
        # Initialize Jinja2 environment
        env = Environment(
            loader=PackageLoader("devguides", "templates"),
            autoescape=select_autoescape(['html', 'xml'])
        )
        
        # Select template file
        if output_format == "html":
            template_file = f"html/{template}.html.j2"
            # Convert markdown content to HTML for the template
            # In a real app, use a markdown library like 'markdown' or 'mistune'
            # For now, simple conversion as before
            content_html = self._convert_markdown_to_html(llm_content)
            
            try:
                jinja_template = env.get_template(template_file)
                return jinja_template.render(
                    title=title,
                    content_html=content_html,
                    mermaid_diagram=mermaid_diagram,
                    metadata=metadata,
                    timestamp=timestamp,
                    template_name=template
                )
            except Exception as e:
                logger.warning("template_load_failed", template=template_file, error=str(e))
                # Fallback to default if custom template fails
                jinja_template = env.get_template("html/default.html.j2")
                return jinja_template.render(
                    title=title,
                    content_html=content_html,
                    mermaid_diagram=mermaid_diagram,
                    metadata=metadata,
                    timestamp=timestamp,
                    template_name="default"
                )
                
        else: # markdown
            template_file = f"markdown/{template}.md.j2"
            
            try:
                jinja_template = env.get_template(template_file)
                return jinja_template.render(
                    title=title,
                    content=llm_content,
                    mermaid_diagram=mermaid_diagram,
                    metadata=metadata,
                    timestamp=timestamp,
                    template_name=template
                )
            except Exception as e:
                logger.warning("template_load_failed", template=template_file, error=str(e))
                # Fallback to default
                jinja_template = env.get_template("markdown/default.md.j2")
                return jinja_template.render(
                    title=title,
                    content=llm_content,
                    mermaid_diagram=mermaid_diagram,
                    metadata=metadata,
                    timestamp=timestamp,
                    template_name="default"
                )

    def _convert_markdown_to_html(self, content: str) -> str:
        """Convert basic markdown to HTML."""
        # Simple conversion logic moved here from HTMLTemplate
        lines = content.split('\n')
        html_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            if line.startswith('### '):
                html_lines.append(f'<h3>{line[4:].strip()}</h3>')
            elif line.startswith('## '):
                html_lines.append(f'<h2>{line[3:].strip()}</h2>')
            elif line.startswith('# '):
                html_lines.append(f'<h1>{line[2:].strip()}</h1>')
            elif not line:
                html_lines.append('')
            else:
                paragraph_lines = [line]
                i += 1
                while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith('#'):
                    paragraph_lines.append(lines[i].strip())
                    i += 1
                
                if paragraph_lines:
                    paragraph_text = ' '.join(paragraph_lines)
                    html_lines.append(f'<p>{paragraph_text}</p>')
                continue
            
            i += 1
        
        return '\n'.join(html_lines)
    
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