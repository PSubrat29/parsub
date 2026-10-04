"""Generate a self-contained, one-page A0 research poster in LaTeX."""

import math
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import sympy as sp
from sympy.core.relational import Equality

POSTER_FILENAME = "generated_poster.tex"
_DEFAULTS = {"x": (-10.0, 10.0), "t": (0.0, 10.0), "theta": (0.0, 2 * math.pi)}


def _without_comments(source: str) -> str:
    """Remove unescaped TeX comments while leaving escaped percent signs intact."""
    lines = []
    for line in source.splitlines():
        kept = []
        backslashes = 0
        for char in line:
            if char == "%" and backslashes % 2 == 0:
                break
            kept.append(char)
            backslashes = backslashes + 1 if char == "\\" else 0
        lines.append("".join(kept))
    return "\n".join(lines)


def _command_argument(source: str, name: str) -> Optional[str]:
    """Return the first balanced braced argument of a TeX metadata command."""
    match = re.search(r"\\{}(?![A-Za-z])".format(re.escape(name)), source)
    if not match:
        return None
    index = match.end()
    while index < len(source) and source[index].isspace():
        index += 1
    if index < len(source) and source[index] == "[":
        depth = 1
        index += 1
        while index < len(source) and depth:
            depth += (source[index] == "[") - (source[index] == "]")
            index += 1
    while index < len(source) and source[index].isspace():
        index += 1
    if index >= len(source) or source[index] != "{":
        return None

    start = index + 1
    depth = 1
    index += 1
    while index < len(source) and depth:
        char = source[index]
        escaped = index > 0 and source[index - 1] == "\\"
        if not escaped:
            depth += (char == "{") - (char == "}")
        index += 1
    return source[start:index - 1] if depth == 0 else None


def _metadata(source: str, source_name: Optional[str]) -> Dict[str, str]:
    clean_source = _without_comments(source)
    title = _command_argument(clean_source, "title") or ""
    authors = _command_argument(clean_source, "author") or ""
    address_parts = [
        value for command in ("address", "affiliation", "affil", "institute")
        if (value := _command_argument(clean_source, command))
    ]
    abstract_match = re.search(
        r"\\begin\s*\{abstract\}(.*?)\\end\s*\{abstract\}", clean_source, flags=re.DOTALL
    )
    abstract = abstract_match.group(1).strip() if abstract_match else ""
    if not title:
        title = _tex_escape(os.path.splitext(os.path.basename(source_name or "Research Poster"))[0].replace("_", " "))
    return {
        "title": title,
        "authors": authors or r"\textit{Author information not found in the source manuscript.}",
        "address": r"\\[0.25em]".join(address_parts)
        or r"\textit{Author address not found in the source manuscript.}",
        "abstract": abstract,
    }


def _tex_escape(text: Any) -> str:
    """Escape plain prose for safe inclusion in generated LaTeX."""
    replacements = {
        "\\": r"\textbackslash{}",
        "&": r"\&",
        "%": r"\%",
        "$": r"\$",
        "#": r"\#",
        "_": r"\_",
        "{": r"\{",
        "}": r"\}",
        "~": r"\textasciitilde{}",
        "^": r"\textasciicircum{}",
    }
    return "".join(replacements.get(char, char) for char in str(text))


def _compact_abstract(metadata: Dict[str, str], parsed: Dict[str, Any]) -> str:
    """Use the manuscript abstract verbatim, or build a restrained source-based fallback."""
    if metadata["abstract"]:
        return metadata["abstract"]
    facts = list(parsed.get("goals", [])) + list(parsed.get("methods", []))
    if facts:
        return _tex_escape(" ".join(facts[:2]))
    if parsed.get("expressions"):
        return (
            "This poster presents selected mathematical expressions from the source manuscript "
            "and summarizes their structure for review."
        )
    return (
        "This poster presents the source manuscript metadata and analysis summary. "
        "No abstract or convertible mathematical expressions were detected."
    )


def _numeric_curve(
    expression_data: Dict[str, Any],
    task: Dict[str, Any],
    parsed: Dict[str, Any],
) -> Optional[Tuple[str, List[Tuple[float, float]], str]]:
    expression = expression_data.get("sympy_expr")
    if not isinstance(expression, sp.Basic):
        return None

    plot_expr = expression
    if isinstance(expression, Equality):
        plot_expr = expression.rhs if expression.rhs.free_symbols else expression.lhs
    params = {item.get("name"): item.get("default") for item in parsed.get("parameters", [])}
    params.update({str(name): value for name, value in parsed.get("assignments", {}).items()})
    independent = list(task.get("independent_variables") or [])
    variable = next(
        (sp.Symbol(str(name)) for name in independent if sp.Symbol(str(name)) in plot_expr.free_symbols),
        None,
    )
    if variable is None:
        symbols = sorted(plot_expr.free_symbols, key=lambda symbol: symbol.name)
        if len(symbols) != 1:
            return None
        variable = symbols[0]

    substitutions = {
        symbol: params[symbol.name]
        for symbol in plot_expr.free_symbols
        if symbol != variable and symbol.name in params
    }
    plot_expr = plot_expr.subs(substitutions)
    if plot_expr.free_symbols != {variable}:
        return None

    configured_range = (task.get("suggested_sampling") or {}).get("ranges", {}).get(variable.name)
    if configured_range and len(configured_range) == 2:
        low, high = map(float, configured_range)
    elif variable.name in _DEFAULTS:
        low, high = _DEFAULTS[variable.name]
    else:
        low, high = -5.0, 5.0
    if not math.isfinite(low) or not math.isfinite(high) or low >= high:
        return None

    try:
        function = sp.lambdify(variable, plot_expr, modules="numpy")
        xs = np.linspace(low, high, 64)
        ys = np.asarray(function(xs), dtype=float)
        if ys.ndim == 0:
            ys = np.full(xs.shape, float(ys))
        ys = np.broadcast_to(ys, xs.shape)
    except (TypeError, ValueError, NameError, OverflowError, ZeroDivisionError, NotImplementedError):
        return None

    finite = np.isfinite(xs) & np.isfinite(ys)
    if np.count_nonzero(finite) < 4:
        return None
    xs, ys = xs[finite], ys[finite]
    ymin, ymax = float(np.min(ys)), float(np.max(ys))
    yrange = ymax - ymin
    if yrange < 1e-12:
        yrange = max(abs(ymin), 1.0)
        ymin -= yrange / 2
        ymax += yrange / 2
    points = [
        (float((x - low) / (high - low) * 100), float((y - ymin) / (ymax - ymin) * 48 + 6))
        for x, y in zip(xs, ys)
    ]
    label = sp.latex(expression)
    caption = (
        f"Illustrative model curve: ${label}$. "
        f"Sampled over ${sp.latex(variable)}\\in[{low:g},{high:g}]$; "
        "not experimental data."
    )
    return variable.name, points, caption


def _figure_tex(curve: Tuple[str, List[Tuple[float, float]], str]) -> str:
    variable, points, caption = curve
    coordinates = " ".join(f"({x:.2f},{y:.2f})" for x, y in points)
    return rf"""
\begin{{center}}
\begin{{tikzpicture}}[x=0.0085\linewidth,y=0.0085\linewidth]
  \draw[gray!60,very thin] (0,0) grid[xstep=20,ystep=12] (100,60);
  \draw[->,thick] (0,0) -- (104,0) node[right] {{$\mathrm{{{variable}}}$}};
  \draw[->,thick] (0,0) -- (0,64);
  \draw[ParSubBlue,very thick] plot[smooth] coordinates {{{coordinates}}};
\end{{tikzpicture}}
\end{{center}}
\small {caption}
"""


def generate_poster_tex(
    parsed: Dict[str, Any],
    tasks: List[Dict[str, Any]],
    output_dir: str,
    source_name: Optional[str] = None,
) -> str:
    """Write a portrait A0 poster containing source metadata and analysis-derived content."""
    os.makedirs(output_dir, exist_ok=True)
    metadata = _metadata(parsed.get("raw_latex") or "", source_name)
    abstracts = _compact_abstract(metadata, parsed)

    goals = parsed.get("goals", [])
    methods = parsed.get("methods", [])
    objectives = "\n".join(r"\item " + _tex_escape(goal) for goal in goals[:4])
    if not objectives:
        objectives = r"\item Research objectives are not stated explicitly in the source text."
    method_items = "\n".join(r"\item " + _tex_escape(method) for method in methods[:4])
    if not method_items:
        method_items = r"\item Mathematical expressions were parsed and classified for analysis."

    equations = []
    for expr in parsed.get("expressions", []):
        sympy_expr = expr.get("sympy_expr")
        if isinstance(sympy_expr, sp.Basic) and expr.get("kind") != "assignment":
            equations.append(sp.latex(sympy_expr))
        if len(equations) == 5:
            break
    equation_content = "\n".join(
        r"\begin{center}\resizebox{\linewidth}{!}{$" + equation + r"$}\end{center}"
        for equation in equations
    )
    if not equation_content:
        equation_content = r"\textit{No convertible equations were found in this manuscript.}"

    expressions_by_source = {}
    for expr_data in parsed.get("expressions", []):
        for source in (expr_data.get("latex"), expr_data.get("raw_latex")):
            if source:
                expressions_by_source.setdefault(source, expr_data)

    curves = []
    for task in tasks:
        expr_data = expressions_by_source.get(task.get("source_latex"))
        if expr_data is None:
            continue
        curve = _numeric_curve(expr_data, task, parsed)
        if curve:
            curves.append(curve)
        if len(curves) == 2:
            break
    figure_content = "\n".join(_figure_tex(curve) for curve in curves)
    if not figure_content:
        figure_content = (
            r"\textit{No safely evaluable one-variable model curve was identified. "
            r"Equations above are retained for manual review.}"
        )

    task_items = []
    for index, task in enumerate(tasks[:8], 1):
        description = task.get("description") or task.get("expression") or task.get("goal_type", "analysis")
        task_items.append(r"\item \textbf{" + _tex_escape(task.get("goal_type", "analysis").title())
                          + r":} " + _tex_escape(description))
    task_content = "\n".join(task_items) or r"\item No computational tasks were generated."

    tex = rf"""\documentclass{{article}}
\usepackage[paperwidth=841mm,paperheight=1189mm,margin=22mm]{{geometry}}
\usepackage[T1]{{fontenc}}
\usepackage{{lmodern}}
\usepackage{{amsmath,amssymb}}
\usepackage{{xcolor}}
\usepackage{{tikz}}
\usepackage{{graphicx}}
\usepackage{{microtype}}
\pagestyle{{empty}}
\setlength{{\parindent}}{{0pt}}
\setlength{{\parskip}}{{0.45em}}
\definecolor{{ParSubBlue}}{{HTML}}{{123B5D}}
\definecolor{{ParSubTeal}}{{HTML}}{{087E8B}}
\definecolor{{ParSubPale}}{{HTML}}{{EFF5F8}}
\definecolor{{ParSubGold}}{{HTML}}{{E3A72F}}
\newcommand{{\PosterSection}}[2]{{%
  \par\medskip\noindent
  \colorbox{{ParSubBlue}}{{\parbox{{\dimexpr\linewidth-2\fboxsep\relax}}{{%
    \color{{white}}\bfseries\Large #1}}}}%
  \par\smallskip
  \colorbox{{ParSubPale}}{{\parbox{{\dimexpr\linewidth-2\fboxsep\relax}}{{%
    \color{{black}}#2}}}}%
  \par\medskip
}}
\begin{{document}}
\fontsize{{24}}{{29}}\selectfont
\noindent\begin{{minipage}}[t]{{\textwidth}}
\centering
{{\fontsize{{62}}{{70}}\selectfont\bfseries\color{{ParSubBlue}} {metadata["title"]}\par}}
\vspace{{0.7em}}
{{\fontsize{{34}}{{40}}\selectfont\bfseries {metadata["authors"]}\par}}
\vspace{{0.3em}}
{{\fontsize{{26}}{{32}}\selectfont\color{{ParSubTeal}} {metadata["address"]}\par}}
\vspace{{1.2em}}
\PosterSection{{ABSTRACT}}{{{abstracts}}}
\vspace{{0.4em}}
\begin{{minipage}}[t]{{0.318\textwidth}}
\PosterSection{{MOTIVATION \& OBJECTIVES}}{{\begin{{itemize}}{objectives}\end{{itemize}}}}
\PosterSection{{METHODS}}{{\begin{{itemize}}{method_items}\end{{itemize}}}}
\PosterSection{{ANALYSIS OVERVIEW}}{{\begin{{itemize}}{task_content}\end{{itemize}}}}
\end{{minipage}}\hfill
\begin{{minipage}}[t]{{0.318\textwidth}}
\PosterSection{{MATHEMATICAL FRAMEWORK}}{{{equation_content}}}
\PosterSection{{COMPUTATIONAL FIGURES}}{{{figure_content}}}
\end{{minipage}}\hfill
\begin{{minipage}}[t]{{0.318\textwidth}}
\PosterSection{{KEY FINDINGS}}{{The poster summarizes the source manuscript's objectives, methods, and selected equations. Numerical curves, when available, are model-based illustrations sampled from parsed expressions; they are not empirical results. Review equations, assumptions, units, and parameter values against the original work before presentation.}}
\PosterSection{{REPRODUCIBILITY}}{{This poster was generated by ParSub from the supplied LaTeX manuscript. Analysis tasks: {len(tasks)}. Parsed expressions: {len(parsed.get("expressions", []))}. The generated curves use source-derived expressions and default or manuscript-assigned parameter values.}}
\PosterSection{{PRESENTATION NOTE}}{{The layout is an editable LaTeX starting point, not a substitute for author review or conference-specific formatting requirements. Confirm author metadata, scientific interpretation, references, and numerical settings before submission.}}
\end{{minipage}}
\vfill
\begin{{center}}\color{{ParSubTeal}}\rule{{0.92\linewidth}}{{2pt}}\\[0.4em]
\small Generated from { _tex_escape(source_name or "LaTeX manuscript") } \textbullet\ ParSub
\end{{center}}
\end{{minipage}}
\end{{document}}
"""
    path = os.path.join(output_dir, POSTER_FILENAME)
    Path(path).write_text(tex, encoding="utf-8")
    return path
