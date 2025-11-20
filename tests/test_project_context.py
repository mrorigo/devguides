import unittest
from unittest.mock import MagicMock, patch, mock_open
from pathlib import Path
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from devguides.core.engine import DocumentationEngine, GenerationRequest

class TestProjectContext(unittest.TestCase):
    def setUp(self):
        self.mock_mcp_client = MagicMock()
        self.mock_llm_handler = MagicMock()
        self.engine = DocumentationEngine(self.mock_mcp_client, self.mock_llm_handler)

    def test_get_project_context_agents_md(self):
        """Test that AGENTS.md is prioritized."""
        with patch("devguides.core.engine.Path") as MockPath:
            # Setup mock path instances
            mock_agents_path = MagicMock()
            mock_agents_path.exists.return_value = True
            mock_agents_path.is_file.return_value = True
            mock_agents_path.read_text.return_value = "AGENTS.md Content"
            
            # Configure the MockPath constructor to return our mock based on input
            def path_side_effect(arg):
                if arg == "AGENTS.md":
                    return mock_agents_path
                return MagicMock()
            
            MockPath.side_effect = path_side_effect
            
            # Run test
            context = self.engine._get_project_context()
            
            # Verify
            self.assertEqual(context, "AGENTS.md Content")

    def test_get_project_context_readme_fallback(self):
        """Test fallback to README.md when AGENTS.md is missing."""
        with patch("devguides.core.engine.Path") as MockPath:
            # Setup mock path instances
            mock_agents_path = MagicMock()
            mock_agents_path.exists.return_value = False
            
            mock_readme_path = MagicMock()
            mock_readme_path.exists.return_value = True
            mock_readme_path.is_file.return_value = True
            mock_readme_path.read_text.return_value = "README.md Content"
            
            def path_side_effect(arg):
                if arg == "AGENTS.md":
                    return mock_agents_path
                if arg == "README.md":
                    return mock_readme_path
                return MagicMock()
            
            MockPath.side_effect = path_side_effect
            
            # Run test
            context = self.engine._get_project_context()
            
            # Verify
            self.assertEqual(context, "README.md Content")

    def test_get_project_context_none(self):
        """Test empty return when neither file exists."""
        with patch("devguides.core.engine.Path") as MockPath:
            mock_path = MagicMock()
            mock_path.exists.return_value = False
            MockPath.return_value = mock_path
            
            # Run test
            context = self.engine._get_project_context()
            
            # Verify
            self.assertEqual(context, "")

    def test_build_context_includes_project_context(self):
        """Test that _build_context includes the project context."""
        # Mock _get_project_context
        self.engine._get_project_context = MagicMock(return_value="Mock Project Context")
        
        request = GenerationRequest(query="test")
        context = self.engine._build_context([], {}, [], request)
        
        self.assertIn("project_context", context)
        self.assertEqual(context["project_context"], "Mock Project Context")

if __name__ == "__main__":
    unittest.main()
