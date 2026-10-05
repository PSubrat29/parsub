"""
Conversion of LaTeX math snippets into SymPy expressions.

The heavy lifting is done by SymPy's LaTeX parser (ANTLR backend).  This module
adds the pre-processing that real papers need (labels, spacing, font macros,
trailing conditions such as ``(\\Re(z) > 0)``) and the post-processing that makes
the result usable for numerical work (``\\pi`` -> ``pi``, ``e^{x}`` -> ``exp(x)``,
``\\Gamma(z)`` -> ``gamma(z)``, clean symbol names such as ``v_0``).  Standard
special-function notation is understood as well: hypergeometric functions
``{}_pF_q(a; b; z)``, Pochhammer symbols ``(a)_n``, Laguerre/Gegenbauer/Jacobi
polynomials ``L_n^{(a)}(x)``, Bessel functions ``J_\\nu(x)`` and indexed functions
``w_{\\alpha}(z)`` (read as ``w(alpha, z)``).
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


def split_top_level(latex: str, separator: str = ",", keep_empty: bool = False) -> List[str]:
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
    stripped = [piece.strip() for piece in parts]
    return stripped if keep_empty else [part for part in stripped if part]


def split_conditions(latex: str) -> Tuple[str, str]:
    """Split ``formula \\,\\,\\, (conditions)`` into the formula and the conditions."""
    text = re.sub(r"[\s,.;:]+$", "", _DROP_MACROS.sub("", latex))
    text = strip_outer_braces(text)
    for match in _CONDITION_SEPARATOR.finditer(text):
        # only spacing at the top level separates conditions (not inside \frac{...}{...})
        if _nesting_depth(text, match.start()) == 0 and text[: match.start()].strip():
            return text[: match.start()], text[match.end():]
    return text, ""


def _nesting_depth(text: str, position: int) -> int:
    depth = 0
    for index in range(position):
        char = text[index]
        if index > 0 and text[index - 1] == "\\":
            continue
        if char in "({[":
            depth += 1
        elif char in ")}]":
            depth = max(depth - 1, 0)
    return depth


def clean_latex(latex: str) -> str:
    """Normalise a LaTeX math snippet so that SymPy can parse it."""
    text = _DROP_MACROS.sub("", latex)
    text = strip_outer_braces(text)
    text = text.replace(":=", "=").replace(r"\coloneqq", "=").replace("&", "")
    text = re.sub(r"\\[dt]frac(?![A-Za-z])", r"\\frac", text)
    text = _FONT_MACROS.sub(r"\1", text)
    text = re.sub(r"\\(?:left|right)\s*\.", "", text)
    text = re.sub(r"\\(?:left|right)\s*\\([{}])", r"\\\1", text)
    text = re.sub(r"\\(?:left|right)\s*(?=[()\[\]|])", "", text)
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


# ----------------------------------------------------------------------------
# Special-function notation that SymPy's LaTeX parser does not understand.
# Each construct is replaced by a placeholder call Q_{7xxx}(...) that the parser
# reads as a function application; _postprocess turns it into the real object.
# ----------------------------------------------------------------------------
_GREEK = (
    "alpha", "beta", "gamma", "delta", "epsilon", "varepsilon", "zeta", "eta", "theta",
    "vartheta", "iota", "kappa", "lambda", "mu", "nu", "xi", "rho", "varrho", "sigma",
    "tau", "upsilon", "phi", "varphi", "chi", "psi", "omega", "Gamma", "Delta", "Theta",
    "Lambda", "Xi", "Sigma", "Upsilon", "Phi", "Psi", "Omega",
)
_FUNCTION_NAME = r"(?<![A-Za-z\\])(\\(?:%s)(?![A-Za-z])|[A-Za-z])" % "|".join(sorted(_GREEK, key=len, reverse=True))
_HYPERGEOMETRIC = re.compile(
    r"(?:\{\s*\}\s*)?_\s*(?:\{\s*(\d)\s*\}|(\d))\s*F\s*_\s*(?:\{\s*(\d)\s*\}|(\d))\s*\("
)
_POLYNOMIAL = re.compile(
    r"(?<![A-Za-z\\])([A-Za-z])\s*_\s*(?:\{([^{}]*)\}|([A-Za-z0-9]))\s*\^\s*\{\s*\(([^{}()]*)\)\s*\}\s*\("
)
_INDEXED_FUNCTION = re.compile(_FUNCTION_NAME + r"\s*_\s*(?:\{([^{}]*)\}|([A-Za-z]))\s*\(")
_POCHHAMMER_TAIL = re.compile(r"\)\s*_\s*(?:\{([^{}]*)\}|([A-Za-z0-9]))")
_PRIMED_FUNCTION = re.compile(
    r"(?<![A-Za-z\\])([A-Za-z])\s*(?:\^\s*\{\s*((?:\\prime\s*)+)\}|('+))\s*\("
)
_PLACEHOLDER_NAME = re.compile(r"^Q_\{?(7\d{3})\}?$")
_BESSEL = {"J": sp.besselj, "Y": sp.bessely, "I": sp.besseli, "K": sp.besselk}


def _brackets_to_parentheses(latex: str) -> str:
    """``[ ... ]`` grouping -> ``( ... )`` (the optional argument of ``\\sqrt[n]`` is kept)."""
    out: List[str] = []
    index = 0
    while index < len(latex):
        if latex.startswith("\\sqrt[", index):
            close = _matching_close(latex, index + 5)
            if close == -1:
                return latex
            out.append(latex[index:close + 1])
            index = close + 1
            continue
        char = latex[index]
        escaped = index > 0 and latex[index - 1] == "\\"
        out.append("(" if char == "[" and not escaped else ")" if char == "]" and not escaped else char)
        index += 1
    return "".join(out)


class _Placeholders:
    def __init__(self) -> None:
        self.mapping: Dict[str, Tuple[str, Tuple]] = {}

    def new(self, kind: str, *info) -> str:
        token = str(7001 + len(self.mapping))
        self.mapping[token] = (kind, info)
        return "Q_{" + token + "}"


def _rewrite_hypergeometric(latex: str, holders: _Placeholders) -> str:
    """``{}_pF_q(a_1, ...; b_1, ...; z)`` -> placeholder(a..., b..., z)."""
    search_from = 0
    while True:
        match = _HYPERGEOMETRIC.search(latex, search_from)
        if not match:
            return latex
        open_index = match.end() - 1
        close = _matching_close(latex, open_index)
        parts = split_top_level(latex[open_index + 1:close], ";", keep_empty=True) if close != -1 else []
        if len(parts) != 3:
            search_from = match.end()
            continue
        numerators, denominators = (
            [] if part.strip() in ("", "-", "--") else split_top_level(part) for part in parts[:2]
        )
        arguments = ", ".join(numerators + denominators + [parts[2]])
        token = holders.new("hyper", len(numerators), len(denominators))
        latex = latex[:match.start()] + token + "(" + arguments + latex[close:]
        search_from = match.start()


def _rewrite_polynomials(latex: str, holders: _Placeholders) -> str:
    """``L_n^{(a)}(x)``, ``C_n^{(a)}(x)``, ``P_n^{(a,b)}(x)`` -> placeholder(n, a[, b], x)."""
    def replace(match: "re.Match[str]") -> str:
        letter, index = match.group(1), match.group(2) or match.group(3)
        params = split_top_level(match.group(4))
        kind = {("L", 1): "laguerre", ("C", 1): "gegenbauer", ("P", 2): "jacobi"}.get((letter, len(params)), "indexed")
        token = holders.new(kind, letter)
        return token + "(" + ", ".join([index] + params) + ", "

    return _POLYNOMIAL.sub(replace, latex)


def _rewrite_pochhammer(latex: str, holders: _Placeholders) -> str:
    """Pochhammer symbol ``(a)_{n}`` -> placeholder(a, n)."""
    search_from = 0
    while True:
        match = _POCHHAMMER_TAIL.search(latex, search_from)
        if not match:
            return latex
        close = match.start()
        depth, open_index = 0, -1
        for index in range(close, -1, -1):
            if latex[index] == ")":
                depth += 1
            elif latex[index] == "(":
                depth -= 1
                if depth == 0:
                    open_index = index
                    break
        if open_index == -1 or (open_index > 0 and latex[open_index - 1].isalpha()):
            search_from = match.end()  # f(x)_n: a function value, not a Pochhammer symbol
            continue
        index = match.group(1) or match.group(2)
        token = holders.new("rf")
        latex = latex[:open_index] + token + "(" + latex[open_index + 1:close] + ", " + index + ")" + latex[match.end():]
        search_from = open_index


def _rewrite_indexed_functions(latex: str, holders: _Placeholders) -> str:
    """``w_{\\alpha}(z)`` -> placeholder(alpha, z): the subscript becomes an argument."""
    def replace(match: "re.Match[str]") -> str:
        name, index = match.group(1), match.group(2) or match.group(3)
        if re.fullmatch(r"\s*\d+\s*", index) or re.fullmatch(r"7\d{3}|9\d{3}", index.strip()):
            return match.group(0)  # f_1(x), or a protected token: keep the parser's default
        token = holders.new("indexed", name.lstrip("\\"))
        return token + "(" + index + ", "

    return _INDEXED_FUNCTION.sub(replace, latex)


def _rewrite_derivatives(latex: str, holders: _Placeholders) -> str:
    r"""``w''(z)`` or ``w^{\prime\prime}(z)`` -> placeholder(z) for the 2nd derivative of w."""
    def replace(match: "re.Match[str]") -> str:
        order = match.group(2).count("prime") if match.group(2) else len(match.group(3))
        return holders.new("derivative", match.group(1), order) + "("

    return _PRIMED_FUNCTION.sub(replace, latex)


def _prepare_special_notation(latex: str) -> Tuple[str, Dict[str, Tuple[str, Tuple]]]:
    holders = _Placeholders()
    text = _brackets_to_parentheses(latex)
    text = _rewrite_derivatives(text, holders)
    text = _rewrite_hypergeometric(text, holders)
    text = _rewrite_polynomials(text, holders)
    text = _rewrite_pochhammer(text, holders)
    text = _rewrite_indexed_functions(text, holders)
    return text, holders.mapping


def _build_placeholder(kind: str, info: Tuple, args: Tuple[sp.Basic, ...]) -> sp.Basic:
    if kind == "hyper":
        p, q = info
        if len(args) != p + q + 1:
            raise ValueError("hypergeometric argument count")
        return sp.hyper(args[:p], args[p:p + q], args[-1])
    if kind == "rf":
        return sp.rf(*args)
    if kind == "laguerre" and len(args) == 3:
        return sp.assoc_laguerre(*args)
    if kind == "gegenbauer" and len(args) == 3:
        return sp.gegenbauer(*args)
    if kind == "jacobi" and len(args) == 4:
        return sp.jacobi(*args)
    if kind == "derivative":
        name, order = info
        function = sp.Function(name)(*args)
        variable = args[-1]
        if variable.is_Symbol:
            return sp.Derivative(function, variable, order)
        dummy = sp.Dummy("t")
        return sp.Subs(sp.Derivative(sp.Function(name)(*(args[:-1] + (dummy,))), dummy, order), dummy, variable)
    name = info[0]
    if kind == "indexed" and name in _BESSEL and len(args) == 2:
        return _BESSEL[name](*args)
    return sp.Function(name)(*args)


def _replace_placeholders(expr: sp.Basic, mapping: Dict[str, Tuple[str, Tuple]]) -> sp.Basic:
    if not mapping:
        return expr

    def is_placeholder(node: sp.Basic) -> bool:
        return isinstance(node, AppliedUndef) and bool(_PLACEHOLDER_NAME.match(node.func.__name__))

    def build(node: sp.Basic) -> sp.Basic:
        token = _PLACEHOLDER_NAME.match(node.func.__name__).group(1)
        kind, info = mapping[token]
        return _build_placeholder(kind, info, node.args)

    return expr.replace(is_placeholder, build)


def clean_name(name: str, word_subscripts: Optional[Dict[str, str]] = None) -> str:
    """Turn a SymPy symbol name such as ``v_{0}`` or ``w_{alpha}`` into ``v_0``/``w_alpha``."""
    for token, word in (word_subscripts or {}).items():
        name = name.replace(token, word)
    name = name.replace("\\", "").replace("'", "_prime")
    name = re.sub(r"[{}\s]", "", name)
    name = re.sub(r"[^0-9A-Za-z_]", "_", name)
    name = re.sub(r"_+", "_", name).strip("_")
    return name or "x"


def _postprocess(expr: sp.Basic, word_subscripts: Dict[str, str],
                 placeholders: Optional[Dict[str, Tuple[str, Tuple]]] = None) -> sp.Basic:
    """Rebuild the expression with clean names and standard constants/functions."""
    # Evaluate the unevaluated tree that the LaTeX parser produces (flattens
    # nested Add/Mul, turns log(x, E) into log(x)), without evaluating integrals.
    expr = sp.sympify(sp.srepr(expr))
    expr = _replace_placeholders(expr, placeholders or {})

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
        sides = split_top_level(latex, "=", keep_empty=True)
        if len(sides) >= 3 and all(sides[:2]) and not re.search(r"\.\.\.|dots|\\begin", sides[0] + sides[1]):
            return latex_to_sympy(sides[0] + " = " + sides[1])
        return None
    prepared, word_subscripts = _protect_word_subscripts(latex)
    prepared, placeholders = _prepare_special_notation(prepared)
    try:
        try:
            # strict mode rejects input that would otherwise be parsed only partially
            expr = _parse_latex(prepared, strict=True)
        except TypeError:  # SymPy without the ``strict`` argument
            expr = _parse_latex(prepared)
    except (LaTeXParsingError, Exception):  # noqa: BLE001 - the parser raises many types
        sides = split_top_level(latex, "=", keep_empty=True)
        if len(sides) >= 3 and all(sides[:2]):
            # a = b = \begin{cases}...: keep the first, parseable relation
            return latex_to_sympy(sides[0] + " = " + sides[1])
        return None
    if isinstance(expr, sp.Equality) and isinstance(expr.lhs, sp.Equality):
        expr = sp.Eq(expr.lhs.lhs, expr.lhs.rhs, evaluate=False)
    if not isinstance(expr, (sp.Expr, Relational)):
        return None
    try:
        expr = _postprocess(expr, word_subscripts, placeholders)
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


def constant_value(expr: sp.Basic) -> Optional[Tuple[str, sp.Basic]]:
    """``i = \\sqrt{-1}`` -> ``("i", I)``: a symbol given a non-real constant value."""
    if not is_assignment(expr) or (expr.lhs.is_Symbol and expr.rhs.is_Symbol):
        return None
    symbol, value = (expr.lhs, expr.rhs) if expr.lhs.is_Symbol else (expr.rhs, expr.lhs)
    try:
        number = complex(value)
    except (TypeError, ValueError):
        return None
    if abs(number.imag) <= 1e-12:
        return None
    return symbol.name, value


def free_symbol_names(expr: Optional[sp.Basic]) -> List[str]:
    """Sorted names of the free symbols of an expression."""
    if expr is None:
        return []
    return sorted(str(symbol) for symbol in expr.free_symbols)
