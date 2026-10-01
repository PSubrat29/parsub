"""
Conversion of LaTeX math snippets into SymPy expressions.

The heavy lifting is done by SymPy's LaTeX parser (ANTLR backend).  This module
adds the pre-processing that real papers need (labels, spacing, font macros,
trailing conditions such as ``(\\Re(z) > 0)``) and the post-processing that makes
the result usable for numerical work (``\\pi`` -> ``pi``, ``e^{x}`` -> ``exp(x)``,
``\\Gamma(z)`` -> ``gamma(z)``, clean symbol names such as ``v_0``).
"""

import re
from typing import Dict, List, Optional, Tuple

import sympy as sp
from sympy.core.relational import Relational
from sympy.core.function import AppliedUndef

try:  # SymPy's LaTeX parser needs antlr4-python3-runtime
    from sympy.parsing.latex import parse_latex as _parse_latex
    from sympy.parsing.latex.errors import LaTeXParsingError
except ImportError:  # pragma: no cover - depends on the installed SymPy
    _parse_latex = None

    class LaTeXParsingError(Exception):  # type: ignore[no-redef]
        pass


# Commands that only affect typesetting and can be dropped
_SPACING = re.compile(
    r"\\(?:,|;|:|!|\s|quad|qquad|displaystyle|textstyle|scriptstyle|limits|nolimits"
    r"|big|Big|bigg|Bigg|bigl|bigr|Bigl|Bigr)(?![A-Za-z])|~"
)
# A run of two or more spacing commands (or \quad) separates the formula from
# side conditions, e.g. ``... dl \,\,\,\,\, (\Re(z)>0)``
_CONDITION_SEPARATOR = re.compile(
    r"(?:\s*\\(?:,|;|:|quad|qquad)(?![A-Za-z])\s*){2,}|\s*\\q?quad(?![A-Za-z])\s*"
    r"|\s*\\(?:text|mbox|mathrm)\{\s*(?:for|where|if|when|with)\b[^}]*\}"
)
_FONT_MACROS = re.compile(
    r"\\(?:mathcal|mathbf|mathit|mathsf|mathtt|mathscr|mathfrak|boldsymbol|bm|vec|hat"
    r"|tilde|bar|widehat|widetilde|overline)\s*\{([^{}]*)\}"
)
_DROP_MACROS = re.compile(r"\\(?:label|tag|ref|eqref|cite)\s*\{[^{}]*\}|\\(?:nonumber|notag)")
_WORD_SUBSCRIPT = re.compile(r"_\{\s*(?:\\(?:text|mathrm|rm)\s*\{)?([A-Za-z]{2,})\}?\s*\}")

# Symbol names that indicate the snippet was not real mathematics
_JUNK_NAMES = {
    "prime", "dots", "ldots", "cdots", "vdots", "ddots", "mapsto", "to", "in", "notin",
    "forall", "exists", "mathbb", "mathrm", "operatorname", "text", "mbox", "quad",
    "left", "right", "infty", "subset", "subseteq", "cup", "cap", "rightarrow",
    "Rightarrow", "leftarrow", "longrightarrow", "dag", "ast", "star", "circ",
    "approx", "sim", "propto", "equiv", "pm", "mp", "neq", "ne", "leq", "geq",
}

# Undefined functions that are really well-known special functions
_KNOWN_FUNCTIONS = {
    "Gamma": sp.gamma,
    "erf": sp.erf,
    "erfc": sp.erfc,
}


def is_available() -> bool:
    """Return True when SymPy's LaTeX parser can be used."""
    return _parse_latex is not None


def _matching_close(text: str, start: int) -> int:
    """Index of the bracket closing the one opened at ``start`` (-1 if unbalanced)."""
    pairs = {"{": "}", "(": ")", "[": "]"}
    opening = text[start]
    closing = pairs[opening]
    depth = 0
    for index in range(start, len(text)):
        char = text[index]
        if char == opening and (index == 0 or text[index - 1] != "\\"):
            depth += 1
        elif char == closing and (index == 0 or text[index - 1] != "\\"):
            depth -= 1
            if depth == 0:
                return index
    return -1


def strip_outer_braces(latex: str) -> str:
    """Remove braces that wrap the whole snippet: ``{a+b}`` -> ``a+b``.

    A leading ``{`` that is never closed (left over after side conditions were
    split off a fully braced formula) is removed as well.
    """
    text = latex.strip()
    while text.startswith("{"):
        close = _matching_close(text, 0)
        if close == len(text) - 1:
            text = text[1:-1].strip()
        elif close == -1:
            text = text[1:].strip()
        else:
            break
    return text


def split_top_level(latex: str, separator: str = ",") -> List[str]:
    """Split at ``separator`` characters that are not nested in (), [] or {}."""
    parts: List[str] = []
    depth = 0
    current = []
    for index, char in enumerate(latex):
        escaped = index > 0 and latex[index - 1] == "\\"
        if char in "([{" and not escaped:
            depth += 1
        elif char in ")]}" and not escaped:
            depth = max(depth - 1, 0)
        if char == separator and depth == 0 and not escaped:
            parts.append("".join(current))
            current = []
        else:
            current.append(char)
    parts.append("".join(current))
    return [part for part in (piece.strip() for piece in parts) if part]


def split_conditions(latex: str) -> Tuple[str, str]:
    """Split ``formula \\,\\,\\, (conditions)`` into the formula and the conditions."""
    text = re.sub(r"[\s,.;:]+$", "", _DROP_MACROS.sub("", latex))
    text = strip_outer_braces(text)
    match = _CONDITION_SEPARATOR.search(text)
    if match and text[: match.start()].strip():
        return text[: match.start()], text[match.end():]
    return text, ""


def clean_latex(latex: str) -> str:
    """Normalise a LaTeX math snippet so that SymPy can parse it."""
    text = _DROP_MACROS.sub("", latex)
    text = strip_outer_braces(text)
    text = text.replace(":=", "=").replace(r"\coloneqq", "=").replace("&", "")
    text = re.sub(r"\\[dt]frac(?![A-Za-z])", r"\\frac", text)
    text = _FONT_MACROS.sub(r"\1", text)
    text = re.sub(r"\\(?:left|right)\s*\.", "", text)
    text = re.sub(r"\\(?:left|right)\s*\\([{}])", r"\\\1", text)
    text = re.sub(r"\\(?:mid|vert)(?![A-Za-z])", "|", text)
    text = _SPACING.sub(" ", text)
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"[,.;:]+$", "", text).strip()
    return strip_outer_braces(text)


def _protect_word_subscripts(latex: str) -> Tuple[str, Dict[str, str]]:
    """Replace ``x_{max}`` by ``x_{9001}`` so SymPy keeps the subscript as one token."""
    mapping: Dict[str, str] = {}

    def replace(match: "re.Match[str]") -> str:
        token = str(9001 + len(mapping))
        mapping[token] = match.group(1)
        return "_{" + token + "}"

    return _WORD_SUBSCRIPT.sub(replace, latex), mapping


def clean_name(name: str, word_subscripts: Optional[Dict[str, str]] = None) -> str:
    """Turn a SymPy symbol name such as ``v_{0}`` or ``w_{alpha}`` into ``v_0``/``w_alpha``."""
    for token, word in (word_subscripts or {}).items():
        name = name.replace(token, word)
    name = name.replace("\\", "").replace("'", "_prime")
    name = re.sub(r"[{}\s]", "", name)
    name = re.sub(r"[^0-9A-Za-z_]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "x"


def _postprocess(expr: sp.Basic, word_subscripts: Dict[str, str]) -> sp.Basic:
    """Rebuild the expression with clean names and standard constants/functions."""
    # Evaluate the unevaluated tree that the LaTeX parser produces (flattens
    # nested Add/Mul, turns log(x, E) into log(x)), without evaluating integrals.
    expr = sp.sympify(sp.srepr(expr))

    replacements: Dict[sp.Basic, sp.Basic] = {}
    for symbol in expr.free_symbols:
        if symbol.name == "pi":
            replacements[symbol] = sp.pi
        else:
            new_name = clean_name(symbol.name, word_subscripts)
            if new_name != symbol.name:
                replacements[symbol] = sp.Symbol(new_name)
    for bound in expr.atoms(sp.Symbol) - expr.free_symbols:
        new_name = clean_name(bound.name, word_subscripts)
        if new_name != bound.name:
            replacements[bound] = sp.Symbol(new_name)
    if replacements:
        expr = expr.xreplace(replacements)

    # e^{x} -> exp(x)
    euler = sp.Symbol("e")
    expr = expr.replace(lambda node: node.is_Pow and node.base == euler, lambda node: sp.exp(node.exp))

    # Undefined functions: map well-known names, clean the others
    for application in sorted(expr.atoms(AppliedUndef), key=sp.default_sort_key):
        name = application.func.__name__
        if name in _KNOWN_FUNCTIONS:
            new = _KNOWN_FUNCTIONS[name](*application.args)
        else:
            cleaned = clean_name(name, word_subscripts)
            if cleaned == name:
                continue
            new = sp.Function(cleaned)(*application.args)
        expr = expr.xreplace({application: new})
    return expr


def _looks_like_junk(expr: sp.Basic) -> bool:
    names = {symbol.name for symbol in expr.atoms(sp.Symbol)}
    names |= {app.func.__name__ for app in expr.atoms(AppliedUndef)}
    return bool(names & _JUNK_NAMES)


def latex_to_sympy(latex: str) -> Optional[sp.Basic]:
    """
    Convert a (cleaned) LaTeX snippet to a SymPy expression.

    Returns ``None`` when the snippet cannot be interpreted as mathematics.
    Equations are returned as :class:`sympy.Eq`; chained equations
    ``a = b = c`` are reduced to ``Eq(a, b)``.
    """
    if not latex or not latex.strip() or _parse_latex is None:
        return None
    if re.search(r"\.\.\.|\\[lcv]?dots|\\begin|\\end", latex):
        return None
    prepared, word_subscripts = _protect_word_subscripts(latex)
    try:
        try:
            # strict mode rejects input that would otherwise be parsed only partially
            expr = _parse_latex(prepared, strict=True)
        except TypeError:  # SymPy without the ``strict`` argument
            expr = _parse_latex(prepared)
    except (LaTeXParsingError, Exception):  # noqa: BLE001 - the parser raises many types
        return None
    if isinstance(expr, sp.Equality) and isinstance(expr.lhs, sp.Equality):
        expr = sp.Eq(expr.lhs.lhs, expr.lhs.rhs, evaluate=False)
    if not isinstance(expr, (sp.Expr, Relational)):
        return None
    try:
        expr = _postprocess(expr, word_subscripts)
    except Exception:  # noqa: BLE001
        return None
    if _looks_like_junk(expr):
        return None
    return expr


_RELATION = r"(>=|<=|>|<|\\geq?|\\leq?|\\geqslant|\\leqslant|\\ge|\\le)"
_NUMBER = r"(-?\d+(?:\.\d+)?)"


def parse_constraints(conditions: str) -> Dict[str, Dict[str, float]]:
    """
    Extract simple bounds such as ``\\Re(z) > 0`` or ``x \\geq 1`` from a
    condition string.  Returns ``{variable: {"min": value}}`` style records.
    """
    constraints: Dict[str, Dict[str, float]] = {}
    if not conditions:
        return constraints
    text = _FONT_MACROS.sub(r"\1", conditions)
    pattern = re.compile(
        r"(?:\\(?:Re|Im)\s*\(\s*)?\\?([A-Za-z]+(?:_\{?[A-Za-z0-9]+\}?)?)\s*\)?\s*" + _RELATION + r"\s*" + _NUMBER
    )
    for name, relation, number in pattern.findall(text):
        value = float(number)
        key = clean_name(name)
        record = constraints.setdefault(key, {})
        if relation.startswith(">") or "g" in relation:
            record["min"] = value
        else:
            record["max"] = value
    return constraints


def is_assignment(expr: Optional[sp.Basic]) -> bool:
    """True for equations such as ``g = 9.81`` or ``a_1 = a`` that only assign/rename a symbol."""
    if not isinstance(expr, sp.Equality):
        return False
    lhs, rhs = expr.lhs, expr.rhs
    if lhs.is_Symbol and rhs.is_Symbol:
        return True  # renaming such as a_1 = a
    return (lhs.is_Symbol and rhs.is_number) or (rhs.is_Symbol and lhs.is_number)


def assignment_value(expr: sp.Basic) -> Optional[Tuple[str, float]]:
    """Return ``(name, value)`` for a real-valued assignment equation."""
    if not is_assignment(expr) or (expr.lhs.is_Symbol and expr.rhs.is_Symbol):
        return None
    symbol, value = (expr.lhs, expr.rhs) if expr.lhs.is_Symbol else (expr.rhs, expr.lhs)
    try:
        number = complex(value)
    except (TypeError, ValueError):
        return None
    if abs(number.imag) > 1e-12:
        return None
    return symbol.name, float(number.real)


def free_symbol_names(expr: Optional[sp.Basic]) -> List[str]:
    """Sorted names of the free symbols of an expression."""
    if expr is None:
        return []
    return sorted(str(symbol) for symbol in expr.free_symbols)
