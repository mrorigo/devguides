import unittest
from unittest.mock import MagicMock, patch
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from devguides.core.engine import DocumentationEngine

class TestContextExpansion(unittest.TestCase):
    def setUp(self):
        self.mock_mcp_client = MagicMock()
        self.mock_llm_handler = MagicMock()
        self.engine = DocumentationEngine(self.mock_mcp_client, self.mock_llm_handler)

    def test_merge_ranges_no_overlap(self):
        """Test merging non-overlapping ranges."""
        ranges = [(0, 10), (20, 30), (40, 50)]
        result = self.engine._merge_ranges(ranges)
        self.assertEqual(result, [(0, 10), (20, 30), (40, 50)])

    def test_merge_ranges_with_overlap(self):
        """Test merging overlapping ranges."""
        ranges = [(0, 15), (10, 25), (20, 30)]
        result = self.engine._merge_ranges(ranges)
        self.assertEqual(result, [(0, 30)])

    def test_merge_ranges_adjacent(self):
        """Test merging adjacent ranges."""
        ranges = [(0, 10), (10, 20), (20, 30)]
        result = self.engine._merge_ranges(ranges)
        self.assertEqual(result, [(0, 30)])

    def test_merge_ranges_mixed(self):
        """Test merging mixed overlapping and non-overlapping ranges."""
        ranges = [(0, 10), (5, 15), (30, 40), (35, 45)]
        result = self.engine._merge_ranges(ranges)
        self.assertEqual(result, [(0, 15), (30, 45)])

    def test_merge_ranges_empty(self):
        """Test merging empty list."""
        ranges = []
        result = self.engine._merge_ranges(ranges)
        self.assertEqual(result, [])

    def test_merge_ranges_single(self):
        """Test merging single range."""
        ranges = [(10, 20)]
        result = self.engine._merge_ranges(ranges)
        self.assertEqual(result, [(10, 20)])

if __name__ == "__main__":
    unittest.main()
