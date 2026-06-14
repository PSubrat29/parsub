"""
LaTeX parser for extracting mathematical expressions and structures.
"""

import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass
from latexwalker import parse_latex
from latexwalker.expression import LatexExpressionNode, LatexCharsNode, LatexGroupNode, LatexMacroNode, LatexEnvironmentNode
import sympy as sp


@dataclass
class MathExpression:
    """Represents a mathematical expression extracted from LaTeX."""
    raw_latex: str
    sympy_expr: Optional[sp.Expr] = None
    variables: List[str] = None
    constants: List[str] = None
    description: Optional[str] = None

    def __post_init__(self):
        if self.variables is None:
            self.variables = []
        if self.constants is None:
            self.constants = []


class LaTeXParser:
    """Parses LaTeX input to extract mathematical expressions and structures."""

    def __init__(self):
        # Common LaTeX math environments
        self.math_environments = {
            'equation', 'align', 'gather', 'multline', 'flalign',
            'alignat', 'xalign', 'xxalign', 'eqnarray', 'displaymath'
        }
        # Common LaTeX math macros that indicate equations
        self.equation_macros = {
            'frac', 'sqrt', 'sum', 'prod', 'int', 'oint', 'lim',
            'nabla', 'partial', 'infty', 'alpha', 'beta', 'gamma',
            'delta', 'epsilon', 'zeta', 'eta', 'theta', 'iota',
            'kappa', 'lambda', 'mu', 'nu', 'xi', 'omicron', 'pi',
            'rho', 'sigma', 'tau', 'upsilon', 'phi', 'chi', 'psi',
            'omega', 'Gamma', 'Delta', 'Theta', 'Lambda', 'Xi',
            'Pi', 'Sigma', 'Upsilon', 'Phi', 'Psi', 'Omega'
        }

    def parse(self, latex_source: str) -> Dict[str, Any]:
        """
        Parse LaTeX source and extract mathematical content.

        Args:
            latex_source: Raw LaTeX source code

        Returns:
            Dictionary containing parsed mathematical expressions and metadata
        """
        try:
            # Parse the LaTeX
            parsed, pos, _ = parse_latex(latex_source)

            # Extract mathematical expressions
            expressions = self._extract_expressions(parsed)

            # Identify goals, methods, parameters
            goals = self._extract_goals(latex_source)
            methods = self._extract_methods(latex_source)
            parameters = self._extract_parameters(expressions)

            return {
                'expressions': expressions,
                'goals': goals,
                'methods': methods,
                'parameters': parameters,
                'raw_latex': latex_source
            }
        except Exception as e:
            # Return basic structure even if parsing fails
            return {
                'expressions': [],
                'goals': [],
                'methods': [],
                'parameters': [],
                'raw_latex': latex_source,
                'parse_error': str(e)
            }

    def _extract_expressions(self, nodes) -> List[MathExpression]:
        """Extract mathematical expressions from parsed LaTeX nodes."""
        expressions = []

        def _recursive_extract(node):
            if hasattr(node, 'nodelist') and node.nodelist:
                for child in node.nodelist:
                    _recursive_extract(child)
            elif isinstance(node, LatexExpressionNode):
                # Convert to SymPy expression if possible
                latex_str = self._node_to_latex(node)
                sympy_expr = self._latex_to_sympy(latex_str)

                expr = MathExpression(
                    raw_latex=latex_str,
                    sympy_expr=sympy_expr
                )
                if sympy_expr:
                    expr.variables = [str(var) for var in sympy_expr.free_symbols]
                expressions.append(expr)
            elif isinstance(node, LatexGroupNode):
                _recursive_extract(node)
            elif isinstance(node, LatexEnvironmentNode):
                # Check if it's a math environment
                if node.environment in self.math_environments:
                    _recursive_extract(node)
            elif isinstance(node, LatexMacroNode):
                # Handle macros like \frac, \sqrt, etc.
                _recursive_extract(node)

        _recursive_extract(parsed)
        return expressions

    def _node_to_latex(self, node) -> str:
        """Convert a LaTeX node back to LaTeX string."""
        if hasattr(node, 'to_latex'):
            return node.to_latex()
        elif hasattr(node, 'latex'):
            return node.latex
        elif isinstance(node, LatexCharsNode):
            return node.chars
        elif isinstance(node, LatexMacroNode):
            # Handle macros
            macro_name = node.macroname
            if node.nodeargs:
                args_latex = ''.join([self._node_to_latex(arg) for arg in node.nodeargs])
                return f'\\{macro_name}{args_latex}'
            else:
                return f'\\{macro_name}'
        elif isinstance(node, LatexGroupNode):
            content = ''.join([self._node_to_latex(child) for child in node.nodelist])
            return f'{{{content}}}'
        elif isinstance(node, LatexEnvironmentNode):
            content = ''.join([self._node_to_latex(child) for child in node.nodelist])
            return f'\\begin{{{node.environment}}}{content}\\end{{{node.environment}}}'
        else:
            return str(node)

    def _latex_to_sympy(self, latex_str: str) -> Optional[sp.Expr]:
        """Convert LaTeX string to SymPy expression."""
        try:
            # Clean up the LaTeX string
            cleaned = self._clean_latex_for_sympy(latex_str)
            # Use sympy's latex parser
            expr = sp.sympify(cleaned)
            return expr
        except Exception:
            # If conversion fails, return None
            return None

    def _clean_latex_for_sympy(self, latex_str: str) -> str:
        """Clean LaTeX string for SymPy parsing."""
        # Remove common LaTeX constructs that SymPy doesn't understand
        cleaned = latex_str

        # Remove display math markers
        cleaned = re.sub(r'\\\[|\\\]', '', cleaned)
        cleaned = re.sub(r'\\\$|\\\$', '', cleaned)

        # Replace common LaTeX macros with SymPy equivalents
        replacements = {
            r'\\frac{([^}]*)}{([^}]*)}': r'(\1)/(\2)',
            r'\\sqrt{([^}]*)}': r'sqrt(\1)',
            r'\\sqrt$$([^$$]*)$$': r'sqrt(\1)',
            r'\\sin': r'sin',
            r'\\cos': r'cos',
            r'\\tan': r'tan',
            r'\\exp': r'exp',
            r'\\log': r'log',
            r'\\ln': r'log',
            r'\\infty': r'oo',
            r'\\partial': r'd',
            r'\\sum': r'Sum',
            r'\\prod': r'Product',
            r'\\int': r'Integral',
        }

        for pattern, replacement in replacements.items():
            cleaned = re.sub(pattern, replacement, cleaned)

        # Remove extra braces that might interfere
        cleaned = re.sub(r'\\{([^}]*)\\}', r'\1', cleaned)

        return cleaned

    def _extract_goals(self, latex_source: str) -> List[str]:
        """Extract research goals from LaTeX source."""
        goals = []
        # Look for common goal-indicating phrases
        goal_patterns = [
            r'we\s+(?:aim|seek|strive|goal|objective|purpose)\s+to\s+([^.]+)',
            r'the\s+(?:aim|goal|objective|purpose)\s+is\s+to\s+([^.]+)',
            r'in\s+this\s+(?:paper|work|study)',  # Often followed by goals
            r'we\s+(?:show|prove|demonstrate|derive|compute|calculate)\s+([^.]+)',
        ]

        for pattern in goal_patterns:
            matches = re.findall(pattern, latex_source, re.IGNORECASE)
            goals.extend([match.strip() for match in matches])

        return goals[:5]  # Limit to top 5

    def _extract_methods(self, latex_source: str) -> List[str]:
        """Extract methods from LaTeX source."""
        methods = []
        # Look for common method-indicating phrases
        method_patterns = [
            r'we\s+(?:use|employ|utilize|apply|implement)\s+(?:the\s+)?([^.]+)',
            r'using\s+(?:the\s+)?([^.]+)',
            r'by\s+(?:using\s+)?([^.]+)',
            r'(?:method|approach|technique|scheme)\s+[:is]\s+([^.]+)',
        ]

        for pattern in method_patterns:
            matches = re.findall(pattern, latex_source, re.IGNORECASE)
            methods.extend([match.strip() for match in matches])

        return methods[:5]  # Limit to top 5

    def _extract_parameters(self, expressions: List[MathExpression]) -> List[Dict[str, Any]]:
        """Extract parameters from mathematical expressions."""
        parameters = []
        param_counts = {}

        # Collect all variables from expressions
        for expr in expressions:
            if expr.variables:
                for var in expr.variables:
                    param_counts[var] = param_counts.get(var, 0) + 1

        # Convert to parameter info
        for param_name, count in param_counts.items():
            # Try to infer parameter type and typical range
            param_info = {
                'name': param_name,
                'frequency': count,
                'type': self._infer_parameter_type(param_name),
                'suggested_range': self._infer_parameter_range(param_name)
            }
            parameters.append(param_info)

        # Sort by frequency (most used first)
        parameters.sort(key=lambda x: x['frequency'], reverse=True)
        return parameters

    def _infer_parameter_type(self, param_name: str) -> str:
        """Infer the type of a parameter based on its name."""
        name_lower = param_name.lower()

        # Common physics/math parameter patterns
        if any(char.isdigit() for char in param_name):
            return 'discrete'
        elif name_lower in ['n', 'm', 'k', 'j', 'i', 'l']:
            return 'integer'
        elif name_lower in ['x', 'y', 'z', 't', 'r', 'rho', 'phi', 'theta']:
            return 'continuous'
        elif name_lower in ['alpha', 'beta', 'gamma', 'delta', 'epsilon', 'zeta']:
            return 'continuous'
        elif name_lower in ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']:
            return 'constant'
        elif 'omega' in name_lower or 'w' == name_lower:
            return 'frequency'
        elif 'lambda' in name_lower or 'l' == name_lower and len(name_lower) == 1:
            return 'wavelength'
        elif 'k' in name_lower and ('wave' in name_lower or 'spring' in name_lower):
            return 'wave_number' if 'wave' in name_lower else 'spring_constant'
        else:
            return 'unknown'

    def _infer_parameter_range(self, param_name: str) -> Dict[str, float]:
        """Infer a reasonable range for a parameter based on its name."""
        name_lower = param_name.lower()

        # Default ranges
        ranges = {
            'x': (-10, 10),
            'y': (-10, 10),
            'z': (-10, 10),
            't': (0, 10),
            'r': (0, 10),
            'rho': (0, 5),
            'phi': (0, 2*3.14159),
            'theta': (0, 2*3.14159),
            'alpha': (0, 1),
            'beta': (0, 1),
            'gamma': (0, 1),
            'delta': (-1, 1),
            'epsilon': (0, 1),
            'n': (1, 20),
            'm': (1, 20),
            'k': (1, 10),
            'a': (-5, 5),
            'b': (-5, 5),
            'c': (-5, 5),
        }

        if name_lower in ranges:
            low, high = ranges[name_lower]
            return {'min': low, 'max': high}
        else:
            # Default range
            return {'min': -5, 'max': 5}


# Convenience function
def parse_latex_source(latex_source: str) -> Dict[str, Any]:
    """Parse LaTeX source and return extracted information."""
    parser = LaTeXParser()
    return parser.parse(latex_source)