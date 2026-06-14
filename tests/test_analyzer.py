"""
Unit tests for expression analyzer.
"""

import unittest
import sys
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "src"))

from parsub.analyzer.expression_analyzer import analyze_expressions
import sympy as sp


class TestExpressionAnalyzer(unittest.TestCase):
    """Test cases for expression analyzer."""

    def setUp(self):
        pass

    def test_analyze_simple_expression(self):
        """Test analysis of simple expression."""
        # Mock parsed expressions
        expressions = [
            {
                'sympy_expr': sp.sympify('x**2 + 2*x + 1'),
                'raw_latex': r'$x^2 + 2x + 1$'
            }
        ]

        context = {
            'goals': ['we aim to compute the value'],
            'methods': ['using algebraic manipulation'],
            'parameters': []
        }

        tasks = analyze_expressions(expressions, context)

        self.assertIsInstance(tasks, list)
        self.assertEqual(len(tasks), 1)
        self.assertIn('goal_type', tasks[0])
        self.assertIn('expression', tasks[0])
        self.assertIn('variables', tasks[0])

    def test_analyze_equation(self):
        """Test analysis of equation."""
        expressions = [
            {
                'sympy_expr': sp.Eq(sp.Symbol('x')**2, 4),
                'raw_latex': r'$x^2 = 4$'
            }
        ]

        context = {
            'goals': ['we want to solve for x'],
            'methods': ['taking square roots'],
            'parameters': []
        }

        tasks = analyze_expressions(expressions, context)

        self.assertEqual(len(tasks), 1)
        # Should detect solve goal type
        self.assertEqual(tasks[0]['goal_type'], 'solve')

    def test_analyze_plot_request(self):
        """Test analysis when plotting is requested."""
        expressions = [
            {
                'sympy_expr': sp.sympify('sin(x)'),
                'raw_latex': r'$\sin(x)$'
            }
        ]

        context = {
            'goals': ['we want to plot the function'],
            'methods': ['using matplotlib'],
            'parameters': []
        }

        tasks = analyze_expressions(expressions, context)

        self.assertEqual(len(tasks), 1)
        # Should detect plot goal type
        self.assertEqual(tasks[0]['goal_type'], 'plot')

    def test_analyze_multiple_expressions(self):
        """Test analysis of multiple expressions."""
        expressions = [
            {
                'sympy_expr': sp.sympify('x**2'),
                'raw_latex': r'$x^2$'
            },
            {
                'sympy_expr': sp.sympify('sin(y)'),
                'raw_latex': r'$\sin(y)$'
            }
        ]

        context = {
            'goals': ['we aim to compute and plot'],
            'methods': ['numerical evaluation'],
            'parameters': []
        }

        tasks = analyze_expressions(expressions, context)

        self.assertEqual(len(tasks), 2)
        # Each expression should generate a task

    def test_empty_expressions(self):
        """Test analysis with no expressions."""
        expressions = []
        context = {
            'goals': [],
            'methods': [],
            'parameters': []
        }

        tasks = analyze_expressions(expressions, context)

        self.assertEqual(len(tasks), 0)

    def test_variable_extraction(self):
        """Test that variables are correctly extracted."""
        expressions = [
            {
                'sympy_expr': sp.sympify('x**2 + y**2 + z**2'),
                'raw_latex': r'$x^2 + y^2 + z^2$'
            }
        ]

        context = {
            'goals': [],
            'methods': [],
            'parameters': []
        }

        tasks = analyze_expressions(expressions, context)

        self.assertEqual(len(tasks), 1)
        variables = tasks[0]['variables']
        self.assertIn('x', variables)
        self.assertIn('y', variables)
        self.assertIn('z', variables)
        self.assertEqual(len(variables), 3)


if __name__ == '__main__':
    unittest.main()