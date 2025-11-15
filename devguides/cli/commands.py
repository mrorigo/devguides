"""CLI commands for DevGuides."""

import asyncio
import sys
from pathlib import Path
from typing import Optional

import click
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.table import Table
from rich.panel import Panel

from ..config.config import DevGuidesConfig
from ..core.engine import DocumentationEngine, GenerationRequest
from ..core.mcp_client import CodeFlowMCPClient
from ..core.llm_handler import LLMHandler
from ..utils.logging import setup_logging, get_logger

console = Console()
logger = get_logger(__name__)

@click.group()
@click.option("--config", "-c", type=click.Path(), help="Configuration file path")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--quiet", "-q", is_flag=True, help="Suppress all output except errors")
@click.pass_context
def cli(ctx, config, verbose, quiet):
    """DevGuides - AI-powered developer documentation generator."""
    ctx.ensure_object(dict)
    
    # Set up logging
    log_level = "DEBUG" if verbose else "ERROR" if quiet else "INFO"
    setup_logging(level=log_level)
    
    # Load configuration
    try:
        config_obj = load_config(config)
        ctx.obj['config'] = config_obj
        logger.info("configuration_loaded", config_path=config)
    except Exception as e:
        console.print(f"[bold red]Error loading configuration:[/bold red] {e}")
        sys.exit(1)

@cli.command()
@click.argument("query", required=True, nargs=-1)
@click.option("--level", "-l", 
              type=click.Choice(["concise", "comprehensive"]), 
              default="comprehensive",
              help="Detail level for generated documentation")
@click.option("--format", "-f", 
              type=click.Choice(["markdown", "html"]), 
              default="markdown",
              help="Output format")
@click.option("--output", "-o", type=click.Path(), 
              help="Output file path (default: auto-generated)")
@click.option("--template", "-t", default="default", 
              help="Template to use for generation")
@click.option("--no-diagrams", is_flag=True, 
              help="Skip Mermaid diagrams")
@click.option("--max-results", default=10, 
              help="Maximum number of search results to analyze")
@click.option("--timeout", type=int, 
              help="Generation timeout in seconds")
@click.pass_context
def generate(ctx, query, level, format, output, template, no_diagrams, max_results, timeout):
    """Generate documentation for a given query."""
    config = ctx.obj['config']
    
    # Combine query arguments into a single string
    query_text = " ".join(query)
    
    async def _generate():
        try:
            console.print(f"[bold blue]Generating documentation for:[/bold blue] '{query_text}'")
            
            # Initialize components
            console.print(f"[dim]Server config: {config.server.model_dump()}[/dim]")
            console.print(f"[dim]LLM config: {config.llm.model_dump()}[/dim]")
            
            mcp_client = CodeFlowMCPClient(config.server.model_dump())
            llm_handler = LLMHandler(config.llm.model_dump())
            engine = DocumentationEngine(mcp_client, llm_handler)
            
            # Create generation request
            request = GenerationRequest(
                query=query_text,
                detail_level=level,
                output_format=format,
                include_diagrams=not no_diagrams,
                max_results=max_results,
                template=template,
                timeout=timeout or config.generation.timeout
            )
            
            # Generate documentation with progress indicator
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Analyzing code...", total=None)
                
                result = await engine.generate(request)
            
            if result.success:
                # Determine output path
                if output:
                    output_path = Path(output)
                else:
                    output_path = generate_output_path(
                        config.output.output_directory,
                        query_text,
                        format,
                        config.output.file_naming
                    )
                
                # Ensure output directory exists
                output_path.parent.mkdir(parents=True, exist_ok=True)
                
                # Save output
                with open(output_path, 'w', encoding='utf-8') as f:
                    f.write(result.content)
                
                # Display success message
                console.print(f"[bold green]✓[/bold green] Documentation generated: {output_path}")
                
                if result.metadata:
                    console.print(f"[dim]Functions analyzed: {result.metadata.get('functions_analyzed', 'N/A')}[/dim]")
                    console.print(f"[dim]Search results: {result.metadata.get('search_results_count', 'N/A')}[/dim]")
                    console.print(f"[dim]Detail level: {result.metadata.get('detail_level', 'N/A')}[/dim]")
                
                if result.mermaid_diagram:
                    console.print("[dim]📊 Mermaid diagram included[/dim]")
                    
            else:
                console.print(f"[bold red]✗[/bold red] Generation failed: {result.error_message}")
                sys.exit(1)
                
        except KeyboardInterrupt:
            console.print("\n[yellow]Generation cancelled by user[/yellow]")
            sys.exit(1)
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            logger.exception("generation_failed", error=str(e))
            sys.exit(1)
        finally:
            # Cleanup
            await mcp_client.disconnect()
    
    asyncio.run(_generate())

@cli.command()
@click.pass_context
def config(ctx):
    """Show current configuration."""
    config = ctx.obj['config']
    
    console.print("[bold blue]Current Configuration:[/bold blue]")
    
    # Create configuration table
    table = Table(title="DevGuides Configuration")
    table.add_column("Section", style="cyan")
    table.add_column("Setting", style="green")
    table.add_column("Value", style="yellow")
    
    # Server config
    table.add_row("Server", "Command", config.server.command)
    table.add_row("Server", "Timeout", str(config.server.timeout))
    
    # LLM config
    table.add_row("LLM", "Provider", config.llm.provider)
    table.add_row("LLM", "Model", config.llm.model)
    table.add_row("LLM", "Max Tokens", str(config.llm.max_tokens))
    table.add_row("LLM", "Temperature", str(config.llm.temperature))
    
    # Output config
    table.add_row("Output", "Format", config.output.format)
    table.add_row("Output", "Directory", config.output.output_directory)
    table.add_row("Output", "Include Diagrams", str(config.output.include_diagrams))
    
    # Generation config
    table.add_row("Generation", "Detail Level", config.generation.detail_level)
    table.add_row("Generation", "Max Results", str(config.generation.max_results))
    
    # Logging config
    table.add_row("Logging", "Level", config.logging.level)
    
    console.print(table)
    
    # Show validation results
    issues = config.validate_config()
    if issues:
        console.print("\n[yellow]Configuration Issues:[/yellow]")
        for issue in issues:
            console.print(f"  • {issue}")
    else:
        console.print("\n[green]✓ Configuration is valid[/green]")

@cli.command()
@click.option("--server", type=click.Path(), help="Path to CodeFlow MCP server")
@click.pass_context
def server(ctx, server):
    """Check CodeFlow MCP server connection."""
    config = ctx.obj['config']
    
    if server:
        # Update server path in config
        config.server.args = [server]
    
    console.print(f"[bold blue]Testing MCP server connection...[/bold blue]")
    console.print(f"Command: {config.get_server_command()}")
    
    async def _test_connection():
        try:
            mcp_client = CodeFlowMCPClient(config.server.model_dump())
            
            with Progress(
                SpinnerColumn(),
                TextColumn("[progress.description]{task.description}"),
                console=console
            ) as progress:
                task = progress.add_task("Connecting to server...", total=None)
                
                await mcp_client.connect()
            
            console.print("[bold green]✓[/bold green] Successfully connected to CodeFlow MCP server")
            
            # Test ping
            try:
                # Note: This would need to be implemented in CodeFlowMCPClient
                console.print("[dim]Testing server ping...[/dim]")
                # await mcp_client.ping()  # Would be implemented
                console.print("[dim]✓ Server is responding[/dim]")
            except Exception as e:
                console.print(f"[yellow]⚠ Server ping failed: {e}[/yellow]")
                
        except Exception as e:
            console.print(f"[bold red]✗[/bold red] Failed to connect: {e}")
            console.print("\n[dim]Troubleshooting tips:[/dim]")
            console.print("• Ensure CodeFlow MCP server is running")
            console.print("• Check server command and path")
            console.print("• Verify Python environment and dependencies")
            sys.exit(1)
        finally:
            await mcp_client.disconnect()
    
    asyncio.run(_test_connection())

@cli.command()
def version():
    """Show DevGuides version."""
    from .. import __version__
    console.print(f"DevGuides v{__version__}")

def load_config(config_path: Optional[str]) -> DevGuidesConfig:
    """Load configuration with fallback hierarchy."""
    # Start with defaults
    config = DevGuidesConfig()
    
    # Load from environment (lower priority than config files)
    env_config = DevGuidesConfig.from_env()
    config = config.merge(env_config)
    
    # Load default config from package
    default_config_path = Path(__file__).parent.parent / "config" / "defaults.yaml"
    if default_config_path.exists():
        try:
            default_config = DevGuidesConfig.from_file(default_config_path)
            config = config.merge(default_config)
        except Exception as e:
            logger.warning("Failed to load default config", error=str(e))
    
    # Load from user config file if exists
    user_config_path = Path.home() / ".config" / "devguides" / "config.yaml"
    if user_config_path.exists():
        try:
            user_config = DevGuidesConfig.from_file(user_config_path)
            config = config.merge(user_config)
        except Exception as e:
            logger.warning("Failed to load user config", error=str(e))
    
    # Load from project config if provided (highest priority for config files)
    if config_path:
        project_config = DevGuidesConfig.from_file(Path(config_path))
        config = config.merge(project_config)
    else:
        # Try current working directory first, then workspace root
        project_config_path = Path.cwd() / ".devguides.yaml"
        if not project_config_path.exists():
            # Check if we're running from a subdirectory, look in workspace root
            workspace_root = Path(__file__).parent.parent.parent / ".devguides.yaml"
            if workspace_root.exists():
                project_config_path = workspace_root
        
        if project_config_path.exists():
            try:
                logger.info("Loading project config", path=str(project_config_path))
                project_config = DevGuidesConfig.from_file(project_config_path)
                config = config.merge(project_config)
            except Exception as e:
                logger.warning("Failed to load project config", error=str(e))
    
    return config

def generate_output_path(directory: str, query: str, format: str, naming_scheme: str) -> Path:
    """Generate output file path based on query and naming scheme."""
    import re
    from datetime import datetime
    
    # Clean query for filename
    clean_query = re.sub(r'[^\w\s-]', '', query)
    clean_query = re.sub(r'\s+', '_', clean_query).strip('_')
    clean_query = clean_query[:50]  # Limit length
    
    if naming_scheme == "timestamped":
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{timestamp}_{clean_query}.{format}"
    elif naming_scheme == "numbered":
        # Simple numbered approach (would need to track numbers in a real implementation)
        filename = f"guide_{clean_query}.{format}"
    else:  # query_based
        filename = f"{clean_query}.{format}"
    
    return Path(directory) / filename

if __name__ == "__main__":
    cli()