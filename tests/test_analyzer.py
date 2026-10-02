"""
Unit tests for the expression analyzer.
"""

import json
import unittest

import sympy as sp

from parsub.analyzer.expression_analyzer import ExpressionAnalyzer, analyze_expressions
from parsub.parser.latex_parser import parse_latex_source


def analyze_latex(latex):
    parsed = parse_latex_source(latex)
    context = {
        "goals": parsed["goals"],
        "methods": parsed["methods"],
        "parameters": parsed["parameters"],
        "assignments": parsed["assignments"],
        "constants": parsed["constants"],
    }
    return analyze_expressions(parsed["expressions"], context)


class TestExpressionAnalyzer(unittest.TestCase):
    """Test cases for expression analyzer."""

    def test_analyze_simple_expression(self):
        """A one-variable expression with a 'compute' goal is evaluated."""
        expressions = [{"sympy_expr": sp.sympify("x**2 + 2*x + 1"), "raw_latex": r"$x^2 + 2x + 1$"}]
        context = {"goals": ["we aim to compute the value"], "methods": ["using algebraic manipulation"]}
        tasks = analyze_expressions(expressions, context)
        self.assertEqual(len(tasks), 1)
        task = tasks[0]
        self.assertEqual(task["goal_type"], "evaluate")
        self.assertEqual(task["variables"], ["x"])
        self.assertEqual(task["independent_variables"], ["x"])
        self.assertEqual(task["suggested_sampling"]["ranges"]["x"], (-10.0, 10.0))

    def test_analyze_equation(self):
        """An equation with a 'solve' goal is solved for its variable."""
        expressions = [{"sympy_expr": sp.Eq(sp.Symbol("x") ** 2, 4), "raw_latex": r"$x^2 = 4$"}]
        context = {"goals": ["we want to solve for x"], "methods": ["taking square roots"]}
        tasks = analyze_expressions(expressions, context)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["goal_type"], "solve")
        self.assertEqual(tasks[0]["options"]["solve_for"], "x")
        self.assertIsNotNone(tasks[0]["equation"])

    def test_equation_defaults_to_solve(self):
        tasks = analyze_expressions([{"sympy_expr": sp.Eq(sp.Symbol("x") ** 2, 4)}])
        self.assertEqual(tasks[0]["goal_type"], "solve")

    def test_analyze_plot_request(self):
        """Analysis when plotting is requested."""
        expressions = [{"sympy_expr": sp.sympify("sin(x)"), "raw_latex": r"$\sin(x)$"}]
        context = {"goals": ["we want to plot the function"], "methods": ["using matplotlib"]}
        tasks = analyze_expressions(expressions, context)
        self.assertEqual(len(tasks), 1)
        self.assertEqual(tasks[0]["goal_type"], "plot")
        self.assertEqual(tasks[0]["expected_output_type"], "array")

    def test_definition_uses_right_hand_side(self):
        """For y = f(x) the right-hand side is computed and labelled y."""
        tasks = analyze_latex(r"$y = x^2 + 1$")
        self.assertEqual(tasks[0]["expression"], "x**2 + 1")
        self.assertEqual(tasks[0]["label"], "y")
        self.assertEqual(tasks[0]["goal_type"], "plot")

    def test_two_variable_plot_is_a_surface(self):
        tasks = analyze_latex(r"We plot $f(x, y) = x^2 + y^2$")
        self.assertEqual(tasks[0]["goal_type"], "plot")
        self.assertEqual(tasks[0]["independent_variables"], ["x", "y"])
        self.assertEqual(tasks[0]["suggested_sampling"]["method"], "meshgrid")

    def test_assigned_values_are_used_for_fixed_parameters(self):
        latex = r"""Let $g = 9.81$. We want to find the maximum range
        \begin{equation} R = \frac{v_0^2 \sin(2\theta)}{g} \end{equation}"""
        task = analyze_latex(latex)[0]
        self.assertEqual(task["goal_type"], "optimize")
        self.assertEqual(task["options"]["direction"], "maximize")
        self.assertEqual(task["independent_variables"], ["theta"])
        self.assertEqual(task["fixed_parameters"], {"v_0": 10.0, "g": 9.81})

    def test_identity_is_verified(self):
        """Equations between special functions/integrals are checked numerically."""
        tasks = analyze_latex(r"\begin{equation} \Gamma(z) = \int_0^\infty e^{-t} t^{z-1} dt \quad (\Re(z) > 0) \end{equation}")
        self.assertEqual(tasks[0]["goal_type"], "verify")
        low, high = tasks[0]["suggested_sampling"]["ranges"]["z"]
        self.assertGreater(low, 0)

    def test_unknown_functions_are_symbolic(self):
        tasks = analyze_latex(r"\[ w(0) = 0 \]")
        self.assertEqual(tasks[0]["goal_type"], "symbolic")

    def test_integral_and_derivative_detection(self):
        tasks = analyze_latex(r"$\int_0^1 x^2 dx$ and $\frac{d}{dx} x^3$")
        self.assertEqual([t["goal_type"] for t in tasks], ["integrate", "differentiate"])

    def test_analyze_multiple_expressions(self):
        expressions = [
            {"sympy_expr": sp.sympify("x**2"), "raw_latex": r"$x^2$"},
            {"sympy_expr": sp.sympify("sin(y)"), "raw_latex": r"$\sin(y)$"},
        ]
        context = {"goals": ["we aim to compute and plot"], "methods": ["numerical evaluation"]}
        tasks = analyze_expressions(expressions, context)
        self.assertEqual(len(tasks), 2)

    def test_duplicates_and_unconvertible_are_skipped(self):
        expressions = [
            {"sympy_expr": sp.sympify("x**2")},
            {"sympy_expr": sp.sympify("x**2")},
            {"sympy_expr": None, "raw_latex": r"\dots"},
            {"sympy_expr": sp.sympify("x > 1")},
        ]
        self.assertEqual(len(analyze_expressions(expressions)), 1)

    def test_empty_expressions(self):
        self.assertEqual(analyze_expressions([], {"goals": [], "methods": [], "parameters": []}), [])

    def test_variable_extraction(self):
        expressions = [{"sympy_expr": sp.sympify("x**2 + y**2 + z**2")}]
        tasks = analyze_expressions(expressions, {})
        variables = tasks[0]["variables"]
        self.assertEqual(sorted(variables), ["x", "y", "z"])
        self.assertEqual(tasks[0]["independent_variables"], ["x"])
        self.assertEqual(set(tasks[0]["fixed_parameters"]), {"y", "z"})

    def test_tasks_are_json_serialisable(self):
        tasks = analyze_latex(r"$y = \sin(x) e^{-t}$ and $\int_0^1 x dx$")
        json.dumps(tasks)
        self.assertTrue(all("srepr" in task for task in tasks))

    def test_function_definitions_are_expanded(self):
        """pi(x) defined in the document is substituted where it is used later."""
        latex = r"""
        \begin{equation} C(z) = \sum_{n=0}^{\infty} \pi(n) \frac{z^{n}}{n!} \end{equation}
        \begin{equation} \pi(x) = \frac{1}{\Gamma(x+1)} \end{equation}
        """
        task = analyze_latex(latex)[0]
        self.assertNotEqual(task["goal_type"], "symbolic")
        self.assertIn("gamma", task["expression"])

    def test_repeated_definitions_are_cross_checked(self):
        latex = r"""
        \begin{equation}\label{a} f(x) = \sin(x)^2 \end{equation}
        \begin{equation}\label{b} f(x) = \frac{1 - \cos(2x)}{2} \end{equation}
        """
        tasks = analyze_latex(latex)
        self.assertEqual([t["goal_type"] for t in tasks], ["plot", "verify"])
        self.assertIn("equations (a) and (b)", tasks[1]["description"])

    def test_symbol_definitions_fix_parameter_values(self):
        latex = r"""Let $b = 1$ and $\theta = \alpha + \frac{b+1}{2}$.
        \begin{equation} y = \sin(\theta x) \end{equation}"""
        task = analyze_latex(latex)[-1]
        self.assertEqual(task["independent_variables"], ["x"])
        self.assertEqual(task["fixed_parameters"]["theta"], 1.5)

    def test_coordinate_definitions_do_not_fix_variables(self):
        latex = r"""Let $x = r \cos(\phi)$. We plot \begin{equation} f = x^2 + y^2 \end{equation}"""
        task = analyze_latex(latex)[-1]
        self.assertEqual(task["independent_variables"], ["x", "y"])

    def test_imaginary_unit_constant(self):
        latex = r"""where $i=\sqrt{-1}$ and \begin{equation} e^{i x} = \cos(x) + i \sin(x) \end{equation}"""
        task = analyze_latex(latex)[0]
        self.assertEqual(task["goal_type"], "verify")
        self.assertNotIn("i", task["variables"])

    def test_task_objects(self):
        analyzer = ExpressionAnalyzer()
        tasks = analyzer.analyze_expressions([{"sympy_expr": sp.sympify("x**3")}])
        self.assertEqual(tasks[0].sympy_expr, sp.sympify("x**3"))


if __name__ == "__main__":
    unittest.main()
