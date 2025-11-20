"""Tests for Jinja2 template system."""

import pytest
from unittest.mock import Mock, patch, MagicMock
import os
from devguides.core.engine import DocumentationEngine

class TestJinjaTemplates:
    """Test Jinja2 template rendering via DocumentationEngine."""
    
    @pytest.fixture
    def engine(self):
        """Create engine instance."""
        return DocumentationEngine(Mock(), Mock())
    
    def test_markdown_template_rendering(self, engine):
        """Test rendering with default markdown template."""
        llm_content = "# Test Title\n\nTest content."
        mermaid_diagram = "graph TD\n    A --> B"
        
        # We need to mock the package loader to avoid needing actual files during test if possible,
        # but since we created the files, we can test integration or mock jinja2.
        # Let's test the actual rendering to ensure templates are valid.
        
        result = engine._apply_template(
            llm_content,
            mermaid_diagram,
            "default",
            "comprehensive",
            "markdown"
        )
        
        assert "# Test Title" in result
        assert "Test content" in result
        assert "Metadata" in result
        assert "Call Flow Diagram" in result
        assert "graph TD" in result
        
    def test_html_template_rendering(self, engine):
        """Test rendering with default HTML template."""
        llm_content = "# Test Title\n\nTest content."
        mermaid_diagram = "graph TD\n    A --> B"
        
        result = engine._apply_template(
            llm_content,
            mermaid_diagram,
            "default",
            "comprehensive",
            "html"
        )
        
        assert "<!DOCTYPE html>" in result
        assert "<h1>Test Title</h1>" in result
        assert "Test content" in result
        assert "mermaid.initialize" in result
        
    def test_missing_template_fallback(self, engine):
        """Test fallback to default when template is missing."""
        llm_content = "Content"
        
        # Should not raise exception, but log warning and use default
        result = engine._apply_template(
            llm_content,
            None,
            "nonexistent_template",
            "comprehensive",
            "markdown"
        )
        
        assert "Content" in result
        # Should look like default template
        assert "Metadata" in result