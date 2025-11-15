"""Base template class for DevGuides documentation generation."""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional
import time

class BaseTemplate(ABC):
    """Abstract base class for documentation templates."""
    
    def __init__(self, name: str, description: str):
        """Initialize template with name and description."""
        self.name = name
        self.description = description
    
    @abstractmethod
    def format(
        self, 
        content: str, 
        mermaid_diagram: Optional[str],
        metadata: Dict[str, Any],
        output_format: str = "markdown"
    ) -> str:
        """Format the generated content with template."""
        pass
    
    def get_metadata_section(self, metadata: Dict[str, Any]) -> str:
        """Generate metadata section for the template."""
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        
        metadata_items = []
        metadata_items.append(f"**Query:** {metadata.get('query', 'N/A')}")
        metadata_items.append(f"**Detail Level:** {metadata.get('detail_level', 'N/A').title() if metadata.get('detail_level') else 'N/A'}")
        metadata_items.append(f"**Functions Analyzed:** {metadata.get('functions_analyzed', 'N/A')}")
        metadata_items.append(f"**Search Results:** {metadata.get('search_results_count', 'N/A')}")
        
        metadata_items.append(f"**Generated:** {timestamp}")
        metadata_items.append(f"**Template:** {self.name}")
        
        return "### Metadata\n\n" + "\n".join(f"- {item}" for item in metadata_items) + "\n\n"
    
    def validate_content(self, content: str) -> bool:
        """Validate that content meets template requirements."""
        # Remove all whitespace characters including newlines
        stripped = content.strip().replace('\n', '').replace('\t', '').replace(' ', '')
        return len(stripped) > 0

class MarkdownTemplate(BaseTemplate):
    """Base markdown template functionality."""
    
    def format(
        self, 
        content: str, 
        mermaid_diagram: Optional[str],
        metadata: Dict[str, Any],
        output_format: str = "markdown"
    ) -> str:
        """Format content as markdown."""
        
        # Extract title from content
        title = self._extract_title(content)
        
        # Build the formatted content
        result = f"# {title}\n\n"
        
        # Add metadata if requested
        result += self.get_metadata_section(metadata)
        
        # Add main content
        result += content + "\n\n"
        
        # Add diagram if provided
        if mermaid_diagram:
            result += "## Call Flow\n\n"
            result += f"```mermaid\n{mermaid_diagram}\n```\n\n"
        
        return result
    
    def _extract_title(self, content: str) -> str:
        """Extract title from content (first heading)."""
        lines = content.split('\n')
        for line in lines:
            line = line.strip()
            if line.startswith('#'):
                # Remove all leading # and return just the title part (before any newlines)
                title = line.lstrip('#').strip()
                # Split on first newline to get just the title part
                return title.split('\n')[0].strip()
        return "Documentation"

class HTMLTemplate(BaseTemplate):
    """Base HTML template functionality."""
    
    def format(
        self, 
        content: str, 
        mermaid_diagram: Optional[str],
        metadata: Dict[str, Any],
        output_format: str = "markdown"
    ) -> str:
        """Format content as HTML."""
        
        # Extract title from content
        title = self._extract_title(content)
        timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
        
        # Basic HTML template
        html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title} - DevGuides</title>
    <style>
        body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; 
               max-width: 800px; margin: 0 auto; padding: 2rem; line-height: 1.6; 
               color: #1f2937; }}
        h1, h2, h3, h4 {{ color: #1d4ed8; margin-top: 2rem; }}
        h1 {{ border-bottom: 2px solid #e5e7eb; padding-bottom: 0.5rem; }}
        code {{ background: #f3f4f6; padding: 0.2rem 0.4rem; border-radius: 0.25rem; 
               font-family: 'SF Mono', Monaco, 'Cascadia Code', monospace; }}
        pre {{ background: #f9fafb; padding: 1rem; border-radius: 0.5rem; 
              overflow-x: auto; border: 1px solid #e5e7eb; }}
        .metadata {{ background: #f0f9ff; padding: 1rem; border-radius: 0.5rem; 
                     border-left: 4px solid #0ea5e9; margin-bottom: 2rem; }}
        .metadata h3 {{ margin-top: 0; color: #0c4a6e; }}
        .metadata ul {{ margin: 0; padding-left: 1.5rem; }}
        .mermaid {{ text-align: center; margin: 2rem 0; padding: 1rem; 
                    background: #f9fafb; border-radius: 0.5rem; }}
        .footer {{ margin-top: 3rem; padding-top: 2rem; border-top: 1px solid #e5e7eb; 
                   color: #6b7280; font-size: 0.9rem; text-align: center; }}
    </style>
    <script src="https://cdn.jsdelivr.net/npm/mermaid/dist/mermaid.min.js"></script>
</head>
<body>
    <h1>{title}</h1>
    
    <div class="metadata">
        <h3>Documentation Metadata</h3>
        <ul>
"""
        
        # Add metadata items
        if "query" in metadata:
            html += f"            <li><strong>Query:</strong> {metadata['query']}</li>\n"
        if "detail_level" in metadata:
            html += f"            <li><strong>Detail Level:</strong> {metadata['detail_level'].title()}</li>\n"
        if "functions_analyzed" in metadata:
            html += f"            <li><strong>Functions Analyzed:</strong> {metadata['functions_analyzed']}</li>\n"
        if "search_results_count" in metadata:
            html += f"            <li><strong>Search Results:</strong> {metadata['search_results_count']}</li>\n"
        
        html += f"            <li><strong>Generated:</strong> {timestamp}</li>\n"
        html += f"            <li><strong>Template:</strong> {self.name}</li>\n"
        html += """        </ul>
    </div>
    
"""
        
        # Convert content to basic HTML (simple conversion)
        content_html = self._convert_markdown_to_html(content)
        html += content_html
        
        if mermaid_diagram:
            html += f"""
    <h2>Call Flow</h2>
    <div class="mermaid">
{mermaid_diagram}
    </div>
"""
        
        html += f"""
    <div class="footer">
        <p>Generated by <strong>DevGuides</strong> on {timestamp}</p>
    </div>
    
    <script>
        mermaid.initialize({{ startOnLoad: true, theme: 'default' }});
    </script>
</body>
</html>"""
        
        return html
    
    def _extract_title(self, content: str) -> str:
        """Extract title from content (first heading)."""
        lines = content.split('\n')
        for line in lines:
            if line.strip().startswith('#'):
                return line.strip('#').strip()
        return "Documentation"
    
    def _convert_markdown_to_html(self, content: str) -> str:
        """Convert basic markdown to HTML."""
        lines = content.split('\n')
        html_lines = []
        i = 0
        
        while i < len(lines):
            line = lines[i].strip()
            
            # Handle headers
            if line.startswith('### '):
                html_lines.append(f'<h3>{line[4:].strip()}</h3>')
            elif line.startswith('## '):
                html_lines.append(f'<h2>{line[3:].strip()}</h2>')
            elif line.startswith('# '):
                html_lines.append(f'<h1>{line[2:].strip()}</h1>')
            # Skip empty lines
            elif not line:
                html_lines.append('')
            else:
                # This is regular content - collect it into paragraphs
                paragraph_lines = [line]
                i += 1
                
                # Collect subsequent lines until we hit a header or empty line
                while i < len(lines) and lines[i].strip() and not lines[i].strip().startswith('#'):
                    paragraph_lines.append(lines[i].strip())
                    i += 1
                
                # Join paragraph lines and wrap in <p> tags
                if paragraph_lines:
                    paragraph_text = ' '.join(paragraph_lines)
                    html_lines.append(f'<p>{paragraph_text}</p>')
                continue
            
            i += 1
        
        return '\n'.join(html_lines)
