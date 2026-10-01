"""
Unit tests for the LaTeX parser.
"""

import unittest
from pathlib import Path

import sympy as sp

from parsub.parser.latex_parser import LaTeXParser, parse_latex_source
from parsub.parser.latex_to_sympy import clean_latex, latex_to_sympy, parse_constraints, split_conditions

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
E, m, c, x, y, z = sp.symbols("E m c x y z")


def converted(result):
    return [expr["sympy_expr"] for expr in result["expressions"] if expr["sympy_expr"] is not None]


class TestLaTeXParser(unittest.TestCase):
    """Test cases for LaTeX parser."""

    def setUp(self):
        self.parser = LaTeXParser()

    def test_simple_expression(self):
        """Inline math is extracted and converted to an equation."""
        result = parse_latex_source(r"The energy is given by $E = mc^2$")
        self.assertEqual(converted(result), [sp.Eq(E, m * c**2)])
        expr = result["expressions"][0]
        self.assertEqual(expr["kind"], "equation")
        self.assertEqual(expr["variables"], ["E", "c", "m"])
        self.assertIn("energy", expr["context"])

    def test_equation_environment(self):
        """Display environments are extracted with their labels."""
        latex = r"""
        \begin{equation}\label{eq:newton}
        F = ma
        \end{equation}
        """
        result = parse_latex_source(latex)
        self.assertEqual(len(result["expressions"]), 1)
        expr = result["expressions"][0]
        self.assertEqual(expr["label"], "eq:newton")
        self.assertTrue(expr["display"])
        self.assertEqual(expr["sympy_expr"], sp.Eq(sp.Symbol("F"), sp.Symbol("a") * sp.Symbol("m")))

    def test_display_delimiters(self):
        """$$...$$ and \\[...\\] are display math."""
        result = parse_latex_source(r"First $$x^2 + 1$$ then \[ \sin(y) + y \]")
        self.assertEqual(converted(result), [x**2 + 1, sp.sin(y) + y])
        self.assertTrue(all(expr["display"] for expr in result["expressions"]))

    def test_fraction(self):
        """Fractions are converted."""
        result = parse_latex_source(r"The formula is $\frac{a}{b}$")
        self.assertEqual(converted(result), [sp.Symbol("a") / sp.Symbol("b")])

    def test_align_environment_is_split_into_lines(self):
        """Every line of an align environment becomes its own expression."""
        latex = r"""
        \begin{align}
        E &= mc^2 \\
        F &= \frac{G m_1 m_2}{r^2}
        \end{align}
        """
        result = parse_latex_source(latex)
        exprs = converted(result)
        self.assertEqual(len(exprs), 2)
        self.assertEqual(exprs[0], sp.Eq(E, m * c**2))
        self.assertEqual(set(map(str, exprs[1].free_symbols)), {"F", "G", "m_1", "m_2", "r"})

    def test_goals_extraction(self):
        """Research goals are extracted from prose."""
        latex = r"We aim to compute the trajectory. The goal is to find the maximum height."
        result = parse_latex_source(latex)
        self.assertEqual(result["goals"], ["compute the trajectory", "find the maximum height"])

    def test_methods_extraction(self):
        result = parse_latex_source(r"We use the Runge-Kutta method. Then we stop.")
        self.assertEqual(result["methods"], ["Runge-Kutta method"])

    def test_parameters_extraction(self):
        """Parameters carry type, range and default value."""
        result = parse_latex_source(r"The equation $y = mx + c$ describes a line.")
        names = {p["name"] for p in result["parameters"]}
        self.assertEqual(names, {"y", "m", "x", "c"})
        x_param = next(p for p in result["parameters"] if p["name"] == "x")
        self.assertEqual(x_param["type"], "continuous")
        self.assertEqual(x_param["suggested_range"], {"min": -10.0, "max": 10.0})

    def test_assignments(self):
        """Statements such as g = 9.81 are recorded as parameter values, not tasks."""
        result = parse_latex_source(r"with $g = 9.81$ and $x_{max} = 3$ we get $y = g x$")
        self.assertEqual(result["assignments"], {"g": 9.81, "x_max": 3.0})
        kinds = [expr["kind"] for expr in result["expressions"]]
        self.assertEqual(kinds, ["assignment", "assignment", "equation"])

    def test_inline_mentions_are_skipped(self):
        """Bare symbols and inequalities in running text are not expressions."""
        result = parse_latex_source(r"where $x$ is the distance, $\Gamma(z)$ the gamma function and $n\geq1$")
        self.assertEqual(result["expressions"], [])

    def test_preamble_and_comments_are_ignored(self):
        latex = r"""\documentclass{article}
        \newcommand{\norm}[1]{\left\Vert#1\right\Vert}
        \begin{document}
        % $a + b$ is commented out
        $x + 1$
        \end{document}"""
        self.assertEqual(converted(parse_latex_source(latex)), [x + 1])

    def test_empty_input(self):
        """Empty input gives an empty, well-formed result."""
        result = parse_latex_source("")
        self.assertEqual(result["expressions"], [])
        self.assertEqual(result["goals"], [])
        self.assertNotIn("parse_error", result)

    def test_unparseable_display_math_is_reported(self):
        """Display math that SymPy cannot read is kept with sympy_expr=None."""
        result = parse_latex_source(r"\[ _{1}F_{1}(a; b; z) = \dots \]")
        self.assertEqual(len(result["expressions"]), 1)
        self.assertIsNone(result["expressions"][0]["sympy_expr"])
        self.assertEqual(result["statistics"]["converted"], 0)

    def test_sample_paper(self):
        """The bundled example paper yields the key equations."""
        result = parse_latex_source((EXAMPLES / "sample.tex").read_text(encoding="utf-8"))
        self.assertNotIn("parse_error", result)
        by_label = {expr["label"]: expr for expr in result["expressions"] if expr["label"]}
        gamma_def = by_label["1"]["sympy_expr"]
        self.assertIsInstance(gamma_def, sp.Equality)
        self.assertEqual(gamma_def.lhs, sp.gamma(z))
        self.assertTrue(gamma_def.rhs.has(sp.Integral))
        self.assertEqual(by_label["1"]["constraints"], {"z": {"min": 0.0}})
        self.assertTrue(by_label["9"]["sympy_expr"].rhs.has(sp.Sum))
        self.assertGreaterEqual(result["statistics"]["converted"], 20)


class TestLatexToSympy(unittest.TestCase):
    """Test cases for the LaTeX -> SymPy conversion helpers."""

    def test_constants_and_functions(self):
        self.assertEqual(latex_to_sympy(r"e^{x} + \pi"), sp.exp(x) + sp.pi)
        self.assertEqual(latex_to_sympy(r"\Gamma(z)"), sp.gamma(z))
        self.assertEqual(latex_to_sympy(r"\sqrt{x^2+1}"), sp.sqrt(x**2 + 1))

    def test_symbol_names_are_cleaned(self):
        expr = latex_to_sympy(r"v_{0} t + x_{max}")
        self.assertEqual({str(s) for s in expr.free_symbols}, {"v_0", "t", "x_max"})

    def test_partial_parses_are_rejected(self):
        """Trailing unparseable content must not be silently dropped."""
        self.assertIsNone(latex_to_sympy(r"\frac{1}{\Gamma(a)} _{0}F_{1}(-; a; z)"))
        self.assertIsNone(latex_to_sympy(r"x_1, x_2, \ldots, x_n"))

    def test_chained_equation(self):
        self.assertEqual(latex_to_sympy("a = b = c"), sp.Eq(sp.Symbol("a"), sp.Symbol("b")))

    def test_conditions_are_split_off(self):
        formula, conditions = split_conditions(r"{f(z) = z^2 \,\,\,\, (\Re(z)>0)}.")
        self.assertEqual(clean_latex(formula), "f(z) = z^2")
        self.assertEqual(parse_constraints(conditions), {"z": {"min": 0.0}})

    def test_clean_latex(self):
        self.assertEqual(clean_latex(r"\mathcal{C}_{n} \label{x} = \dfrac{a}{b},"), r"C_{n} = \frac{a}{b}")


if __name__ == "__main__":
    unittest.main()
