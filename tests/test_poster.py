"""Tests for the generated A0 poster source."""

import os
import shutil
import tempfile
import unittest

import sympy as sp

from parsub.core.pipeline import analyze_latex
from parsub.generator.poster_generator import _numeric_curve


class TestPosterGeneration(unittest.TestCase):
    def setUp(self):
        self.output_dir = tempfile.mkdtemp(prefix="parsub_poster_")

    def tearDown(self):
        shutil.rmtree(self.output_dir, ignore_errors=True)

    def test_uses_manuscript_metadata_and_embeds_model_curve(self):
        source = r"""
\documentclass{article}
\title[Short]{A \textbf{careful} study of waves}
\author{Ada Author}
\address{Department of Physics\\Example University}
\begin{document}
\begin{abstract}We examine a wave model and its behavior across a finite interval.\end{abstract}
We aim to plot the wave profile. We use numerical sampling.
The fixed acceleration is $g=9.81$.
\begin{equation} y = \sin(x) \end{equation}
\end{document}
"""
        result = analyze_latex(source, self.output_dir, source_name="wave.tex")
        with open(result.poster_path, encoding="utf-8") as handle:
            poster = handle.read()

        self.assertIn(r"\documentclass{article}", poster)
        self.assertIn(r"paperwidth=841mm,paperheight=1189mm", poster)
        self.assertIn(r"A \textbf{careful} study of waves", poster)
        self.assertIn("Ada Author", poster)
        self.assertIn(r"Department of Physics\\Example University", poster)
        self.assertIn("We examine a wave model and its behavior across a finite interval.", poster)
        self.assertIn(r"\begin{tikzpicture}", poster)
        self.assertIn(r"Illustrative model curve: $y = \sin{\left(x \right)}$", poster)
        self.assertIn("not experimental data", poster)
        self.assertEqual(os.path.basename(result.poster_path), "generated_poster.tex")

    def test_metadata_fallback_and_non_numeric_expression_still_generate_tex(self):
        result = analyze_latex("A short manuscript with no formula.", self.output_dir)
        with open(result.poster_path, encoding="utf-8") as handle:
            poster = handle.read()
        self.assertIn("Author information not found", poster)
        self.assertIn("No abstract or convertible mathematical expressions", poster)
        self.assertIn(r"\end{document}", poster)

    def test_unsupported_symbolic_plot_is_skipped_without_failing(self):
        z, t = sp.symbols("z t")
        expression = sp.Integral(t ** (z - 1) * sp.exp(-t), (t, 0, sp.oo))
        task = {"independent_variables": ["z"], "suggested_sampling": {"ranges": {"z": (0.1, 2.0)}}}
        self.assertIsNone(
            _numeric_curve(
                {"sympy_expr": expression},
                task,
                {"parameters": [], "assignments": {}},
            )
        )


if __name__ == "__main__":
    unittest.main()
