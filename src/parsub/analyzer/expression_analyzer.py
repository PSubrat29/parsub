"""
Analyzer for mathematical expressions to determine computational requirements.
"""

from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
import sympy as sp
import numpy as np


@dataclass
class ComputationTask:
    """Represents a computation task derived from a mathematical expression."""
    expression: str
    sympy_expr: sp.Expr
    variables: List[str]
    goal_type: str  # 'evaluate', 'solve', 'plot', 'optimize', etc.
    parameters: Dict[str, Any]
    suggested_sampling: Dict[str, Any]
    expected_output_type: str  # 'scalar', 'array', 'function'


class ExpressionAnalyzer:
    """Analyzes mathematical expressions to determine what computations to perform."""

    def __init__(self):
        self.operation_keywords = {
            'evaluate': ['evaluate', 'compute', 'calculate', 'find', 'determine'],
            'solve': ['solve', 'find roots', 'zero of', 'solution to'],
            'plot': ['plot', 'graph', 'visualize', 'draw'],
            'optimize': ['maximize', 'minimize', 'optimize', 'extreme'],
            'integrate': ['integrate', 'integral', 'area under'],
            'differentiate': ['differentiate', 'derivative', 'rate of change'],
            'series': ['series', 'expand', 'approximation'],
        }

    def analyze_expressions(self, expressions: List[Dict[str, Any]],
                          context: Dict[str, Any] = None) -> List[ComputationTask]:
        """
        Analyze expressions to determine computation tasks.

        Args:
            expressions: List of parsed mathematical expressions
            context: Additional context from goals/methods extraction

        Returns:
            List of computation tasks to perform
        """
        tasks = []
        context = context or {}

        for expr_data in expressions:
            expr = expr_data.get('sympy_expr')
            if expr is None:
                continue

            # Determine what kind of computation is needed
            goal_type = self._determine_goal_type(expr_data, context)

            # Extract variables
            variables = [str(var) for var in expr.free_symbols]

            # Create computation task
            task = ComputationTask(
                expression=str(expr),
                sympy_expr=expr,
                variables=variables,
                goal_type=goal_type,
                parameters=self._extract_parameters_from_expr(expr),
                suggested_sampling=self._suggest_sampling_strategy(expr, variables, goal_type),
                expected_output_type=self._determine_output_type(expr, variables, goal_type)
            )
            tasks.append(task)

        return tasks

    def _determine_goal_type(self, expr_data: Dict[str, Any],
                           context: Dict[str, Any]) -> str:
        """Determine what type of computation to perform based on context."""
        # Check explicit goals from context
        goals = context.get('goals', [])
        methods = context.get('methods', [])

        all_text = ' '.join(goals + methods).lower()

        # Check for explicit operation keywords
        for goal_type, keywords in self.operation_keywords.items():
            if any(keyword in all_text for keyword in keywords):
                return goal_type

        # Default based on expression characteristics
        expr_str = str(expr_data.get('sympy_expr', ''))

        # If it's an equation (contains =), likely solve
        if '=' in expr_str:
            return 'solve'

        # If it contains integral or derivative symbols
        if 'integral' in str(type(expr_data.get('sympy_expr'))) or 'Derivative' in str(type(expr_data.get('sympy_expr'))):
            if 'integral' in str(type(expr_data.get('sympy_expr'))):
                return 'integrate'
            else:
                return 'differentiate'

        # If it's a simple expression, likely evaluate or plot
        if len(expr_data.get('variables', [])) <= 2:
            return 'plot' if len(expr_data.get('variables', [])) == 2 else 'evaluate'
        else:
            return 'evaluate'

    def _extract_parameters_from_expr(self, expr: sp.Expr) -> Dict[str, Any]:
        """Extract parameter information from a SymPy expression."""
        params = {}
        free_symbols = expr.free_symbols

        for symbol in free_symbols:
            name = str(symbol)
            # Try to get any assumptions or default values
            params[name] = {
                'symbol': symbol,
                'assumptions': symbol.assumptions0
            }

        return params

    def _suggest_sampling_strategy(self, expr: sp.Expr,
                                 variables: List[str],
                                 goal_type: str) -> Dict[str, Any]:
        """Suggest sampling strategy for numerical evaluation."""
        sampling = {
            'method': 'uniform',
            'points': 100,
            'ranges': {}
        }

        # Default ranges for common variables
        default_ranges = {
            'x': (-5, 5),
            'y': (-5, 5),
            'z': (-5, 5),
            't': (0, 10),
            'r': (0, 5),
            'theta': (0, 2*np.pi),
            'phi': (0, 2*np.pi),
        }

        for var in variables:
            var_lower = var.lower()
            if var_lower in default_ranges:
                sampling['ranges'][var] = default_ranges[var_lower]
            else:
                # Generic range
                sampling['ranges'][var] = (-2, 2)

        # Adjust based on goal type
        if goal_type == 'plot':
            if len(variables) == 1:
                sampling['points'] = 200  # Higher resolution for 1D plots
            elif len(variables) == 2:
                sampling['points'] = 50   # Grid points for 2D plots
                sampling['method'] = 'meshgrid'
        elif goal_type == 'optimize':
            sampling['points'] = 1000  # More points for optimization
            sampling['method'] = 'adaptive'
        elif goal_type in ['integrate', 'differentiate']:
            sampling['points'] = 500

        return sampling

    def _determine_output_type(self, expr: sp.Expr,
                             variables: List[str],
                             goal_type: str) -> str:
        """Determine what type of output to expect."""
        if goal_type in ['evaluate', 'solve']:
            if len(variables) == 0:
                return 'scalar'
            else:
                return 'function'
        elif goal_type == 'plot':
            return 'array'  # Will produce arrays for plotting
        elif goal_type in ['integrate', 'differentiate']:
            if len(variables) == 0:
                return 'scalar'
            else:
                return 'function'
        else:
            return 'array'


# Convenience function
def analyze_expressions(expressions: List[Dict[str, Any]],
                       context: Dict[str, Any] = None) -> List[Dict[str, Any]]:
    """Analyze expressions and return computation tasks as dictionaries."""
    analyzer = ExpressionAnalyzer()
    tasks = analyzer.analyze_expressions(expressions, context)

    # Convert to dictionaries for easier serialization
    return [
        {
            'expression': task.expression,
            'variables': task.variables,
            'goal_type': task.goal_type,
            'parameters': task.parameters,
            'suggested_sampling': task.suggested_sampling,
            'expected_output_type': task.expected_output_type
        }
        for task in tasks
    ]