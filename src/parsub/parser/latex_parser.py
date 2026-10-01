"""
LaTeX parser for extracting mathematical expressions and structures.

The source is tokenised with pylatexenc's :class:`LatexWalker`.  Every inline
(``$...$``, ``\\(...\\)``) and display (``$$...$$``, ``\\[...\\]``, ``equation``,
``align``, ...) math segment is collected together with the text that precedes
it, converted to SymPy, and summarised as a JSON-friendly dictionary.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

import sympy as sp
from sympy.core.relational import Relational
from pylatexenc.latexwalker import (
    LatexCharsNode,
    LatexCommentNode,
    LatexEnvironmentNode,
    LatexGroupNode,
    LatexMacroNode,
    LatexMathNode,
    LatexSpecialsNode,
    LatexWalker,
)

from parsub.core.parameters import describe_parameter, infer_parameter_range, infer_parameter_type
from parsub.parser.latex_to_sympy import (
    assignment_value,
    clean_latex,
    free_symbol_names,
    is_assignment,
    latex_to_sympy,
    parse_constraints,
    split_conditions,
    split_top_level,
)

# Display-math environments (starred variants are handled automatically)
MATH_ENVIRONMENTS = {
    "equation", "align", "gather", "multline", "flalign", "alignat", "eqnarray",
    "displaymath", "math", "dmath", "dgroup", "split", "aligned", "gathered",
}
# Environments whose content is never part of the paper's mathematics
SKIPPED_ENVIRONMENTS = {"thebibliography", "verbatim", "lstlisting", "comment", "figure", "table"}
# Macros whose arguments are references or metadata rather than prose/math
SKIPPED_MACROS = {
    "label", "ref", "eqref", "cite", "citep", "citet", "bibitem", "url", "href",
    "newcommand", "renewcommand", "providecommand", "def", "usepackage", "documentclass",
    "newtheorem", "theoremstyle", "input", "include", "email", "address", "subjclass",
    "keywords", "thanks", "date", "numberwithin", "bibliographystyle", "bibliography",
    "includegraphics", "vfuzz", "hfuzz",
}
# Macros that delimit lines inside align-like environments
_LINE_BREAKS = {"\\", "cr", "newline"}
_DROPPED_IN_MATH = {"label", "nonumber", "notag", "tag"}


@dataclass
class MathExpression:
    """Represents a mathematical expression extracted from LaTeX."""

    raw_latex: str
    sympy_expr: Optional[sp.Basic] = None
    variables: List[str] = field(default_factory=list)
    constants: List[str] = field(default_factory=list)
    description: Optional[str] = None
    latex: str = ""
    kind: Optional[str] = None  # 'equation', 'expression' or None if not converted
    display: bool = False
    environment: str = "inline"
    label: Optional[str] = None
    context: str = ""
    conditions: str = ""
    constraints: Dict[str, Dict[str, float]] = field(default_factory=dict)

    def __post_init__(self):
        if self.variables is None:
            self.variables = []
        if self.constants is None:
            self.constants = []

    def to_dict(self) -> Dict[str, Any]:
        """Dictionary form used by the analyzer, the API and ``analysis.json``."""
        return {
            "raw_latex": self.raw_latex,
            "latex": self.latex,
            "sympy_expr": self.sympy_expr,
            "sympy_str": str(self.sympy_expr) if self.sympy_expr is not None else None,
            "variables": list(self.variables),
            "constants": list(self.constants),
            "description": self.description,
            "kind": self.kind,
            "display": self.display,
            "environment": self.environment,
            "label": self.label,
            "context": self.context,
            "conditions": self.conditions,
            "constraints": dict(self.constraints),
        }


class _Segment:
    """A raw math segment found while walking the document."""

    def __init__(self, latex: str, display: bool, environment: str, label: Optional[str], context: str):
        self.latex = latex
        self.display = display
        self.environment = environment
        self.label = label
        self.context = context


class LaTeXParser:
    """Parses LaTeX input to extract mathematical expressions and structures."""

    def __init__(self, context_chars: int = 400):
        self.math_environments = set(MATH_ENVIRONMENTS)
        self.context_chars = context_chars

    # ------------------------------------------------------------------ public
    def parse(self, latex_source: str) -> Dict[str, Any]:
        """
        Parse LaTeX source and extract mathematical content.

        Args:
            latex_source: Raw LaTeX source code

        Returns:
            Dictionary with ``expressions`` (list of dicts, see
            :meth:`MathExpression.to_dict`), ``goals``, ``methods``,
            ``parameters``, ``raw_latex``, ``text`` and ``statistics``.
            ``parse_error`` is present only if parsing failed.
        """
        try:
            segments, text = self._walk(latex_source or "")
            expressions, assignments = self._convert_segments(segments)
            goals = self._extract_goals(text)
            methods = self._extract_methods(text)
            parameters = self._extract_parameters(expressions)
            return {
                "expressions": [expr.to_dict() for expr in expressions],
                "goals": goals,
                "methods": methods,
                "parameters": parameters,
                "assignments": assignments,
                "raw_latex": latex_source,
                "text": text,
                "statistics": {
                    "math_segments": len(segments),
                    "expressions": len(expressions),
                    "converted": sum(1 for expr in expressions if expr.sympy_expr is not None),
                },
            }
        except Exception as exc:  # noqa: BLE001 - always return a usable structure
            return {
                "expressions": [],
                "goals": [],
                "methods": [],
                "parameters": [],
                "assignments": {},
                "raw_latex": latex_source,
                "text": "",
                "statistics": {"math_segments": 0, "expressions": 0, "converted": 0},
                "parse_error": str(exc),
            }

    # ----------------------------------------------------------------- walking
    def _walk(self, latex_source: str):
        """Walk the node tree, returning math segments and the plain prose text."""
        walker = LatexWalker(latex_source, tolerant_parsing=True)
        nodes, _, _ = walker.get_latex_nodes(pos=0)
        nodes = self._document_body(nodes)
        segments: List[_Segment] = []
        text_parts: List[str] = []

        def recent_text() -> str:
            joined = re.sub(r"\s+", " ", "".join(text_parts[-60:])).strip()
            return joined[-self.context_chars:]

        def visit(node_list) -> None:
            for node in node_list or []:
                if node is None or isinstance(node, LatexCommentNode):
                    continue
                if isinstance(node, LatexCharsNode):
                    text_parts.append(node.chars)
                elif isinstance(node, LatexMathNode):
                    display = node.displaytype == "display"
                    body = self._nodes_to_latex(node.nodelist)
                    segments.append(_Segment(body, display, "display" if display else "inline", None, recent_text()))
                    text_parts.append(" [math] ")
                elif isinstance(node, LatexEnvironmentNode):
                    name = node.environmentname.rstrip("*")
                    if name in self.math_environments:
                        label = self._find_label(node.nodelist)
                        context = recent_text()
                        for line in self._split_lines(node.nodelist):
                            segments.append(_Segment(line, True, node.environmentname, label, context))
                        text_parts.append(" [equation]. ")
                    elif name not in SKIPPED_ENVIRONMENTS:
                        visit(node.nodelist)
                        text_parts.append(" ")
                elif isinstance(node, LatexGroupNode):
                    visit(node.nodelist)
                elif isinstance(node, LatexMacroNode):
                    if node.macroname in SKIPPED_MACROS:
                        continue
                    if node.macroname in ("section", "subsection", "subsubsection", "paragraph", "item"):
                        text_parts.append(". ")
                    if node.nodeargd is not None:
                        visit([arg for arg in node.nodeargd.argnlist if arg is not None])
                    if node.macroname in ("section", "subsection", "subsubsection", "paragraph"):
                        text_parts.append(". ")
                elif isinstance(node, LatexSpecialsNode):
                    text_parts.append(" " if node.specials_chars in ("~", "&") else node.specials_chars)

        visit(nodes)
        text = re.sub(r"\s+", " ", "".join(text_parts)).strip()
        return segments, text

    @staticmethod
    def _document_body(nodes):
        """Return the content of ``\\begin{document}`` if present (skips the preamble)."""
        for node in nodes:
            if isinstance(node, LatexEnvironmentNode) and node.environmentname == "document":
                return node.nodelist
        return nodes

    @staticmethod
    def _find_label(node_list) -> Optional[str]:
        for node in node_list or []:
            if isinstance(node, LatexMacroNode) and node.macroname == "label" and node.nodeargd:
                args = [arg for arg in node.nodeargd.argnlist if arg is not None]
                if args:
                    return args[-1].latex_verbatim().strip("{} ")
        return None

    def _nodes_to_latex(self, node_list) -> str:
        """Re-assemble LaTeX from nodes, dropping labels and comments."""
        parts = []
        for node in node_list or []:
            if node is None or isinstance(node, LatexCommentNode):
                continue
            if isinstance(node, LatexMacroNode) and node.macroname in _DROPPED_IN_MATH:
                continue
            parts.append(node.latex_verbatim())
        return "".join(parts)

    def _split_lines(self, node_list) -> List[str]:
        """Split the body of an align-like environment at top-level ``\\\\``."""
        lines: List[List[Any]] = [[]]
        for node in node_list or []:
            if isinstance(node, LatexMacroNode) and node.macroname in _LINE_BREAKS:
                lines.append([])
            else:
                lines[-1].append(node)
        result = []
        for line in lines:
            text = self._nodes_to_latex(line).strip()
            if text:
                result.append(text)
        return result

    # -------------------------------------------------------------- conversion
    def _convert_segments(self, segments: List[_Segment]):
        """Convert raw segments into expressions and collect ``symbol = value`` assignments."""
        expressions: List[MathExpression] = []
        assignments: Dict[str, float] = {}
        seen = set()
        for segment in segments:
            formula, conditions = split_conditions(segment.latex)
            pieces = split_top_level(formula)
            if not pieces:
                continue
            if segment.display:
                # "f(x) = ..., x > 0": the first piece is the formula, the rest are conditions
                candidates = [pieces[0]]
                conditions = ", ".join(filter(None, pieces[1:] + [conditions]))
            else:
                candidates = pieces
            for candidate in candidates:
                cleaned = clean_latex(candidate)
                if not cleaned:
                    continue
                sympy_expr = latex_to_sympy(cleaned)
                assignment = assignment_value(sympy_expr) if sympy_expr is not None else None
                if assignment is not None:
                    assignments.setdefault(*assignment)
                if not segment.display and (sympy_expr is None or not self._is_computational(sympy_expr)):
                    continue  # inline mentions such as $x$ or $\Gamma(z)$, or non-math fragments
                if sympy_expr is not None and (
                    sympy_expr.is_Atom
                    or (isinstance(sympy_expr, Relational) and not isinstance(sympy_expr, sp.Equality))
                ):
                    sympy_expr = None  # displayed atoms and inequalities are kept, but not computed
                key = sp.srepr(sympy_expr) if sympy_expr is not None else cleaned
                if key in seen:
                    continue
                seen.add(key)
                expression = MathExpression(
                    raw_latex=segment.latex.strip(),
                    sympy_expr=sympy_expr,
                    latex=cleaned,
                    display=segment.display,
                    environment=segment.environment,
                    label=segment.label,
                    context=segment.context,
                    conditions=clean_latex(conditions) if conditions else "",
                    constraints=parse_constraints(conditions),
                )
                if sympy_expr is not None:
                    if is_assignment(sympy_expr):
                        expression.kind = "assignment"
                    elif isinstance(sympy_expr, sp.Equality):
                        expression.kind = "equation"
                    else:
                        expression.kind = "expression"
                    expression.variables = free_symbol_names(sympy_expr)
                    expression.constants = sorted(
                        str(atom) for atom in sympy_expr.atoms(sp.NumberSymbol) | sympy_expr.atoms(type(sp.I))
                    )
                expressions.append(expression)
        return expressions, assignments

    @staticmethod
    def _is_computational(expr: sp.Basic) -> bool:
        """False for bare mentions (``x``, ``3``, ``f(x)``) and for inequalities."""
        if isinstance(expr, Relational) and not isinstance(expr, sp.Equality):
            return False
        if isinstance(expr, sp.Equality):
            return True
        if expr.is_Atom:
            return False
        if isinstance(expr, sp.Function) and all(arg.is_Symbol for arg in expr.args):
            return False
        return True

    def _latex_to_sympy(self, latex_str: str) -> Optional[sp.Basic]:
        """Convert a LaTeX string to a SymPy expression (``None`` if impossible)."""
        formula, _ = split_conditions(latex_str)
        return latex_to_sympy(clean_latex(formula))

    # ------------------------------------------------------------ text mining
    @staticmethod
    def _sentences(matches: List[str], limit: int = 5) -> List[str]:
        result: List[str] = []
        for match in matches:
            text = re.sub(r"\[(?:math|equation)\]\.?", " ", match)
            text = re.sub(r"\s+", " ", text).strip(" ,;:")
            if len(text.split()) < 2:
                continue
            if len(text) > 160:
                text = text[:157].rstrip() + "..."
            if text and text.lower() not in (item.lower() for item in result):
                result.append(text)
            if len(result) >= limit:
                break
        return result

    def _extract_goals(self, text: str) -> List[str]:
        """Extract research goals (what the author wants to do) from prose."""
        goal_patterns = [
            r"\bwe\s+(?:aim|seek|strive|want|wish|need|intend|plan|propose|try|attempt)\s+to\s+([^.;]+)",
            r"\b(?:the|our)\s+(?:aim|goal|objective|purpose|task)\s+(?:is|was)\s+to\s+([^.;]+)",
            r"\bin\s+this\s+(?:paper|work|study|section|note|article),?\s+we\s+([^.;]+)",
            r"\bwe\s+(?:will\s+)?(?:show|prove|demonstrate|derive|compute|calculate|evaluate|"
            r"solve|plot|find|determine|obtain|estimate|maximi[sz]e|minimi[sz]e)\s+([^.;]+)",
        ]
        matches: List[str] = []
        for pattern in goal_patterns:
            matches.extend(re.findall(pattern, text, re.IGNORECASE))
        return self._sentences(matches)

    def _extract_methods(self, text: str) -> List[str]:
        """Extract methods (how the author does it) from prose."""
        method_patterns = [
            r"\bwe\s+(?:use|employ|utili[sz]e|apply|implement|adopt)\s+(?:the\s+)?([^.;]+)",
            r"\bby\s+(?:using|applying|means\s+of)\s+(?:the\s+)?([^.;]+)",
            r"\busing\s+(?:the\s+)?([^.;]+?(?:method|approach|technique|scheme|algorithm|"
            r"transform\w*|formula\w*|test|expansion|series|integration|approximation)s?)\b",
            r"\b(?:method|approach|technique|scheme)\s+(?:is|:)\s+([^.;]+)",
        ]
        matches: List[str] = []
        for pattern in method_patterns:
            matches.extend(re.findall(pattern, text, re.IGNORECASE))
        return self._sentences(matches)

    def _extract_parameters(self, expressions: List[MathExpression]) -> List[Dict[str, Any]]:
        """Collect every free symbol with its frequency, inferred type and range."""
        counts: Dict[str, int] = {}
        for expr in expressions:
            for var in expr.variables:
                counts[var] = counts.get(var, 0) + 1
        parameters = [describe_parameter(name, count) for name, count in counts.items()]
        parameters.sort(key=lambda item: (-item["frequency"], item["name"]))
        return parameters

    # Backwards-compatible helpers
    def _infer_parameter_type(self, param_name: str) -> str:
        return infer_parameter_type(param_name)

    def _infer_parameter_range(self, param_name: str) -> Dict[str, float]:
        return infer_parameter_range(param_name)


# Convenience function
def parse_latex_source(latex_source: str) -> Dict[str, Any]:
    """Parse LaTeX source and return extracted information."""
    parser = LaTeXParser()
    return parser.parse(latex_source)
