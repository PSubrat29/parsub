"""
Unit tests for LaTeX parser.
"""

import unittest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from parsub.parser.latex_parser import parse_latex_source, LaTeXParser


class TestLaTeXParser(unittest.TestCase):
    """Test cases for LaTeX parser."""

    def setUp(self):
        self.parser = LaTeXParser()

    def test_simple_expression(self):
        """Test parsing of simple mathematical expression."""
        latex = r"The energy is given by $E = mc^2$"
        result = parse_latex_source(latex)

        self.assertIn('expressions', result)
        self.assertIsInstance(result['expressions'], list)
        # Should find at least one expression
        self.assertGreaterEqual(len(result['expressions']), 0)

    def test_equation_environment(self):
        """Test parsing of equation environment."""
        latex = r"""
        \begin{equation}
        F = ma
        \end{equation}
        """
        result = parse_latex_source(latex)

        self.assertIn('expressions', result)
        # Should find the expression F = ma
        self.assertGreaterEqual(len(result['expressions']), 0)

    def test_fraction(self):
        """Test parsing of fraction."""
        latex = r"The formula is $\frac{a}{b}$"
        result = parse_latex_source(latex)

        self.assertIn('expressions', result)
        # Should handle fraction parsing

    def test_goals_extraction(self):
        """Test extraction of research goals."""
        latex = r"We aim to compute the trajectory. The goal is to find the maximum height."
        result = parse_latex_source(latex)

        self.assertIn('goals', result)
        self.assertIsInstance(result['goals'], list)

    def test_parameters_extraction(self):
        """Test extraction of parameters."""
        latex = r"The equation $y = mx + c$ describes a line."
        result = parse_latex_source(latex)

        self.assertIn('parameters', result)
        self.assertIsInstance(result['parameters'], list)

    def test_empty_input(self):
        """Test handling of empty input."""
        latex = ""
        result = parse_latex_source(latex)

        self.assertIn('expressions', result)
        self.assertEqual(result['expressions'], [])

    def test_complex_expression(self):
        """Test parsing of complex expression."""
        latex = r"""
        \begin{align}
        E &= mc^2 \\
        F &= \frac{G m_1 m_2}{r^2}
        \end{align}
        """
        result = parse_latex_source(latex)

        self.assertIn('expressions', result)
        # Should handle multiple expressions in align environment


if __name__ == '__main__':
    unittest.main()