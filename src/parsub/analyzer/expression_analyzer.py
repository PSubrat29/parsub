"""
Analyzer for mathematical expressions to determine computational requirements.

For every parsed expression the analyzer decides *what* to compute (the goal
type), *which* variables to sweep (independent variables), *which* to hold fixed
(and at what value), and over which ranges to sample.  The resulting task
dictionaries are JSON-serialisable and are consumed by the code generator.
"""

import re
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple

import sympy as sp
from sympy.core.function import AppliedUndef
from sympy.core.relational import Relational

from parsub.core.parameters import INDEPENDENT_PREFERENCE, base_name, parameter_hint

GOAL_TYPES = (
    "evaluate", "plot", "solve", "optimize", "integrate", "differentiate",
    "series", "verify", "symbolic",
)

# Keyword patterns (regular expressions) that signal a computational goal
GOAL_KEYWORDS: Dict[str, List[str]] = {
    "solve": [r"\bsolv\w*", r"\broots?\b", r"\bzeros?\b"],
    "optimize": [r"\bmaxim\w*", r"\bminim\w*", r"\boptim\w*", r"\bextrem\w*"],
    "integrate": [r"\bintegrat\w*", r"\bintegrals?\b", r"\barea under\b"],
    "differentiate": [r"\bdifferentiat\w*", r"\bderivatives?\b", r"\brate of change\b", r"\bgradients?\b"],
    "series": [r"\bseries\s+expansion\b", r"\bexpand\w*", r"\btaylor\b", r"\bmaclaurin\b", r"\bapproximat\w*"],
    "plot": [r"\bplot\w*", r"\bgraph\w*", r"\bvisuali[sz]\w*", r"\bdraw\w*", r"\bsketch\w*"],
    "evaluate": [r"\bevaluat\w*", r"\bcomput\w*", r"\bcalculat\w*", r"\bdetermin\w*",
                 r"\bfind\b(?!\s+(?:the\s+|a\s+|its\s+)?(?:max|min|optim|extrem|roots?|zeros?|solutions?)\w*)"],
}
# Tie-break order when several goals are mentioned equally often
GOAL_PRIORITY = ["solve", "optimize", "integrate", "differentiate", "series", "plot", "evaluate"]

DEFAULT_POINTS = {
    "evaluate": 100,
    "plot": 200,
    "plot2d": 40,
    "solve": 400,
    "optimize": 1000,
    "integrate": 200,
    "differentiate": 200,
    "series": 200,
    "verify": 100,
    "symbolic": 0,
}


@dataclass
class ComputationTask:
    """Represents a computation task derived from a mathematical expression."""

    expression: str
    sympy_expr: sp.Basic
    variables: List[str]
    goal_type: str  # one of GOAL_TYPES
    parameters: Dict[str, Any]
    suggested_sampling: Dict[str, Any]
    expected_output_type: str  # 'scalar', 'array', 'function', 'symbolic'
    independent_variables: List[str] = field(default_factory=list)
    fixed_parameters: Dict[str, float] = field(default_factory=dict)
    options: Dict[str, Any] = field(default_factory=dict)
    label: Optional[str] = None
    equation: Optional[Dict[str, str]] = None
    source_latex: str = ""
    source_label: Optional[str] = None
    description: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """JSON-serialisable representation (used by the generator and the API)."""
        return {
            "expression": self.expression,
            "srepr": sp.srepr(self.sympy_expr),
            "latex": sp.latex(self.sympy_expr),
            "variables": list(self.variables),
            "goal_type": self.goal_type,
            "parameters": self.parameters,
            "suggested_sampling": self.suggested_sampling,
            "expected_output_type": self.expected_output_type,
            "independent_variables": list(self.independent_variables),
            "fixed_parameters": dict(self.fixed_parameters),
            "options": dict(self.options),
            "label": self.label,
            "equation": self.equation,
            "source_latex": self.source_latex,
            "source_label": self.source_label,
            "description": self.description,
        }


def _get(expr_data: Any, key: str, default: Any = None) -> Any:
    """Read a field from an expression dict or a MathExpression-like object."""
    if isinstance(expr_data, dict):
        return expr_data.get(key, default)
    return getattr(expr_data, key, default)


class ExpressionAnalyzer:
    """Analyzes mathematical expressions to determine what computations to perform."""

    def __init__(self):
        self.operation_keywords = GOAL_KEYWORDS
        self._compiled = {
            goal: [re.compile(pattern, re.IGNORECASE) for pattern in patterns]
            for goal, patterns in GOAL_KEYWORDS.items()
        }

    # ------------------------------------------------------------------ public
    def analyze_expressions(self, expressions: Sequence[Any], context: Optional[Dict[str, Any]] = None) -> List[ComputationTask]:
        """
        Analyze expressions to determine computation tasks.

        Args:
            expressions: Parsed expressions (dicts from the parser, or objects
                with the same attributes).  Only ``sympy_expr`` is required.
            context: Optional ``goals``, ``methods``, ``parameters`` and
                ``assignments`` (``{symbol: value}``) extracted from the document.

        Returns:
            List of computation tasks to perform.
        """
        context = context or {}
        global_text = " ".join(list(context.get("goals", []) or []) + list(context.get("methods", []) or []))
        assignments = {str(k): float(v) for k, v in (context.get("assignments") or {}).items()}
        constants = {
            str(name): value
            for name, value in ((k, self._as_sympy(v)) for k, v in (context.get("constants") or {}).items())
            if value is not None
        }

        items = []
        for expr_data in expressions or []:
            expr = self._as_sympy(_get(expr_data, "sympy_expr"))
            if expr is None or _get(expr_data, "kind") == "assignment":
                continue
            if isinstance(expr, Relational) and not isinstance(expr, sp.Equality):
                continue  # inequalities/conditions are not computed
            if constants:
                expr = expr.subs({sp.Symbol(name): value for name, value in constants.items()})
            items.append((expr_data, expr))

        # Definitions made in the document are used throughout the analysis:
        # F(x) = ... expands later uses of F, and y = ... fixes the value of y.
        self._function_defs = self._collect_function_definitions(items)
        self._symbol_defs = self._collect_symbol_definitions(items)
        self._usable_cache = {}

        tasks: List[ComputationTask] = []
        seen = set()
        first_definition: Dict[Tuple[str, int], Tuple[Tuple[sp.Symbol, ...], sp.Basic, Any]] = {}
        for expr_data, expr in items:
            task = None
            function_def = self._as_function_definition(expr)
            if function_def is not None:
                name, params, rhs = function_def
                expanded_rhs = self._expand_functions(rhs, exclude=frozenset([name]))
                key = (name, len(params))
                if key in first_definition and not expanded_rhs.atoms(AppliedUndef):
                    task = self._definition_check_task(first_definition[key], (params, expanded_rhs, expr_data),
                                                       expr.lhs, global_text, assignments)
                else:
                    if key not in first_definition and not expanded_rhs.atoms(AppliedUndef):
                        first_definition[key] = (params, expanded_rhs, expr_data)
                    expr = sp.Eq(expr.lhs, expanded_rhs, evaluate=False)
            elif isinstance(expr, sp.Equality):
                # expand each side separately: Eq(a, a) must not collapse to True
                expr = sp.Eq(self._expand_functions(expr.lhs), self._expand_functions(expr.rhs), evaluate=False)
            else:
                expr = self._expand_functions(expr)
            if task is None:
                task = self._build_task(expr_data, expr, global_text, assignments)
            if task is None:
                continue
            key = (task.goal_type, sp.srepr(task.sympy_expr), task.equation and task.equation.get("lhs"))
            if key in seen:
                continue
            seen.add(key)
            tasks.append(task)
        return tasks

    # ------------------------------------------------------------ definitions
    @staticmethod
    def _as_function_definition(expr: sp.Basic):
        """``F(x, y) = rhs`` with distinct symbol arguments -> ``(name, params, rhs)``."""
        if not isinstance(expr, sp.Equality) or not isinstance(expr.lhs, AppliedUndef):
            return None
        params = expr.lhs.args
        if not all(arg.is_Symbol for arg in params) or len(set(params)) != len(params):
            return None
        if expr.lhs.func in {app.func for app in expr.rhs.atoms(AppliedUndef)}:
            return None
        return expr.lhs.func.__name__, tuple(params), expr.rhs

    def _collect_function_definitions(self, items) -> Dict[str, List[Tuple[Tuple[sp.Symbol, ...], sp.Basic]]]:
        definitions: Dict[str, List[Tuple[Tuple[sp.Symbol, ...], sp.Basic]]] = {}
        for _, expr in items:
            found = self._as_function_definition(expr)
            if found is not None:
                name, params, rhs = found
                definitions.setdefault(name, []).append((params, rhs))
        return definitions

    @staticmethod
    def _collect_symbol_definitions(items) -> Dict[str, sp.Basic]:
        """
        Parameter definitions such as ``theta = alpha + (b + 1)/2``: first definition of each symbol.

        Definitions in terms of coordinate-like variables (``x = r cos(phi)``, ``y = x tan(theta)``)
        describe curves or coordinate changes, not parameter values, and are not used.
        """
        definitions: Dict[str, sp.Basic] = {}
        for _, expr in items:
            if not (isinstance(expr, sp.Equality) and expr.lhs.is_Symbol and expr.rhs.free_symbols
                    and expr.lhs not in expr.rhs.free_symbols):
                continue
            if any(base_name(symbol.name) in INDEPENDENT_PREFERENCE for symbol in expr.rhs.free_symbols):
                continue
            definitions.setdefault(expr.lhs.name, expr.rhs)
        return definitions

    def _usable_definition(self, name: str, arity: int, exclude: frozenset):
        """First definition of ``name`` that expands into something computable."""
        cache_key = (name, arity, exclude)
        if cache_key in self._usable_cache:
            return self._usable_cache[cache_key]
        result = None
        candidates = sorted(self._function_defs.get(name, []), key=lambda entry: len(entry[0]) != arity)
        for params, rhs in candidates:
            if len(params) < arity:
                continue
            expanded = self._expand_functions(rhs, exclude=exclude | {name})
            if not expanded.atoms(AppliedUndef):
                result = (params, expanded)
                break
        self._usable_cache[cache_key] = result
        return result

    def _expand_functions(self, expr: sp.Basic, exclude: frozenset = frozenset(), depth: int = 0) -> sp.Basic:
        """Replace applications of functions defined in the document by their definitions."""
        if depth > 5 or not getattr(self, "_function_defs", None):
            return expr

        def defined(node: sp.Basic) -> bool:
            return (isinstance(node, AppliedUndef) and node.func.__name__ in self._function_defs
                    and node.func.__name__ not in exclude)

        def substitute(node: sp.Basic) -> sp.Basic:
            entry = self._usable_definition(node.func.__name__, len(node.args), exclude)
            if entry is None:
                return node
            params, rhs = entry
            args = tuple(node.args)
            if len(args) < len(params):
                # w(z) used for w_alpha(z): the omitted leading indices stay symbolic
                args = tuple(params[: len(params) - len(args)]) + args
            return rhs.xreplace(dict(zip(params, args)))

        expanded = expr.replace(defined, substitute)
        if expanded != expr:
            return self._expand_functions(expanded, exclude, depth + 1)
        return expanded

    def _definition_check_task(self, first, current, lhs: sp.Basic, global_text: str,
                               assignments: Dict[str, float]) -> Optional[ComputationTask]:
        """Two definitions of the same function: check numerically that they agree."""
        params0, rhs0, data0 = first
        params1, rhs1, data1 = current
        rhs1 = rhs1.xreplace(dict(zip(params1, params0)))
        label0, label1 = _get(data0, "label"), _get(data1, "label")
        name = f"{lhs.func.__name__}({', '.join(map(str, params0))})"
        refs = " and ".join(f"({label})" for label in (label0, label1) if label) or "two definitions"
        constraints = dict(_get(data0, "constraints", {}) or {})
        constraints.update(_get(data1, "constraints", {}) or {})
        synthetic = {
            "sympy_expr": sp.Eq(rhs0, rhs1, evaluate=False),
            "goal_type": "verify",
            "constraints": constraints,
            "context": _get(data1, "context", ""),
            "latex": _get(data1, "latex", ""),
            "label": label1,
            "independent": [str(params0[-1])] if params0 else [],
            "title": f"that equations {refs} give the same {name}",
        }
        return self._build_task(synthetic, synthetic["sympy_expr"], global_text, assignments)

    # ---------------------------------------------------------- task building
    @staticmethod
    def _as_sympy(value: Any) -> Optional[sp.Basic]:
        if value is None:
            return None
        if isinstance(value, sp.Basic):
            return value
        try:
            return sp.sympify(value)
        except (sp.SympifyError, TypeError, ValueError, SyntaxError):
            return None

    @staticmethod
    def _is_definition(expr: sp.Basic) -> bool:
        """``y = f(x)`` or ``F(x, y) = ...``: the left side names the right side."""
        if not isinstance(expr, sp.Equality):
            return False
        lhs, rhs = expr.lhs, expr.rhs
        if lhs.is_Symbol:
            return lhs not in rhs.free_symbols
        if isinstance(lhs, AppliedUndef) and all(arg.is_Symbol for arg in lhs.args):
            return lhs.func not in {app.func for app in rhs.atoms(AppliedUndef)}
        return False

    def _build_task(self, expr_data: Any, expr: sp.Basic, global_text: str,
                    assignments: Dict[str, float]) -> Optional[ComputationTask]:
        is_equation = isinstance(expr, sp.Equality)
        definition = self._is_definition(expr) and _get(expr_data, "goal_type") != "verify"
        label: Optional[str] = None
        equation: Optional[Dict[str, str]] = None

        if definition:
            target = expr.rhs
            label = str(expr.lhs)
        elif is_equation:
            target = expr.lhs - expr.rhs
            equation = {
                "lhs": sp.srepr(expr.lhs), "rhs": sp.srepr(expr.rhs),
                "lhs_str": str(expr.lhs), "rhs_str": str(expr.rhs),
            }
        else:
            target = expr

        local_text = self._local_context(_get(expr_data, "context", "") or "")
        goal_type = self._determine_goal_type(
            expr_data, target, expr, is_equation and not definition, local_text, global_text
        )
        if goal_type == "symbolic":
            target = expr  # keep the whole statement for symbolic tasks
            equation = None
            label = None

        free = expr.free_symbols if equation is not None else target.free_symbols
        variables = self._order_variables([str(symbol) for symbol in free], assignments)
        constraints = _get(expr_data, "constraints", {}) or {}
        ranges = {var: self._range_for(var, constraints) for var in variables}
        independent = self._choose_independent(goal_type, variables, assignments, local_text + " " + global_text)
        requested = [var for var in (_get(expr_data, "independent") or []) if var in variables]
        if requested and goal_type not in ("symbolic", "solve"):
            independent = requested + [var for var in independent if var not in requested][: max(0, len(independent) - len(requested))]
        fixed = {
            var: self._fixed_value(var, ranges[var], assignments)
            for var in variables if var not in independent and goal_type != "symbolic"
        }
        options = self._goal_options(goal_type, local_text + " " + global_text, independent)

        sampling = self._suggest_sampling_strategy(target, independent, goal_type)
        sampling["ranges"] = {var: ranges[var] for var in variables}

        parameters = {}
        for var in variables:
            ptype = parameter_hint(var)[0]
            parameters[var] = {
                "type": ptype,
                "range": list(ranges[var]),
                "default": fixed.get(var, self._fixed_value(var, ranges[var], assignments)),
                "role": "independent" if var in independent else "fixed",
            }

        task = ComputationTask(
            expression=str(target),
            sympy_expr=target,
            variables=variables,
            goal_type=goal_type,
            parameters=parameters,
            suggested_sampling=sampling,
            expected_output_type=self._determine_output_type(target, variables, goal_type),
            independent_variables=independent,
            fixed_parameters=fixed,
            options=options,
            label=label,
            equation=equation,
            source_latex=_get(expr_data, "latex", "") or _get(expr_data, "raw_latex", "") or "",
            source_label=_get(expr_data, "label"),
        )
        task.description = self._describe(task, _get(expr_data, "title"))
        return task

    # ------------------------------------------------------------ goal logic
    @staticmethod
    def _local_context(context: str) -> str:
        """Text written since the previous display equation (where intent is stated)."""
        parts = re.split(r"\[equation\]\.?", context)
        return parts[-1][-300:] if parts else ""

    def _keyword_scores(self, text: str) -> Dict[str, int]:
        return {
            goal: sum(len(pattern.findall(text)) for pattern in patterns)
            for goal, patterns in self._compiled.items()
        }

    def _keyword_goal(self, local_text: str, global_text: str) -> Optional[str]:
        local = self._keyword_scores(local_text)
        global_ = self._keyword_scores(global_text)
        scores = {goal: 2 * local[goal] + global_[goal] for goal in GOAL_PRIORITY}
        best = max(scores.values()) if scores else 0
        if best <= 0:
            return None
        for goal in GOAL_PRIORITY:
            if scores[goal] == best:
                return goal
        return None

    def _determine_goal_type(self, expr_data: Any, target: sp.Basic, expr: sp.Basic,
                             plain_equation: bool, local_text: str = "",
                             global_text: str = "") -> str:
        """Determine what type of computation to perform."""
        explicit = _get(expr_data, "goal_type")
        if explicit in GOAL_TYPES:
            return explicit
        if expr.atoms(AppliedUndef) and (plain_equation or target.atoms(AppliedUndef)):
            return "symbolic"  # unknown functions cannot be evaluated numerically

        keyword_goal = self._keyword_goal(local_text, global_text)
        has_calculus = target.has(sp.Integral, sp.Sum, sp.Product)

        if plain_equation:
            if keyword_goal == "solve":
                return "solve"
            lhs, rhs = expr.lhs, expr.rhs
            identity_like = (
                expr.has(sp.Integral, sp.Sum, sp.Product, sp.Derivative)
                or isinstance(rhs, sp.Function)
                or lhs == rhs
                or (isinstance(lhs, sp.Function) and not lhs.is_Pow)
                or bool(target.atoms(sp.Function) - target.atoms(AppliedUndef))
                and not target.is_polynomial(*target.free_symbols)
            )
            if identity_like and (lhs.free_symbols or rhs.free_symbols):
                return "verify"
            return "solve"

        if keyword_goal == "solve":
            if target.free_symbols and not has_calculus:
                return "solve"
            keyword_goal = None if has_calculus else "evaluate"
        if keyword_goal in ("series",) and target.has(sp.Sum):
            keyword_goal = None  # already a series: evaluate it instead
        if keyword_goal in ("plot", "optimize", "integrate", "differentiate", "series") and not target.free_symbols:
            keyword_goal = "evaluate"
        if keyword_goal is not None:
            return keyword_goal

        if target.has(sp.Derivative):
            return "differentiate"
        if target.has(sp.Integral):
            return "integrate"
        nvars = len(target.free_symbols)
        if nvars == 0:
            return "evaluate"
        if nvars <= 2:
            return "plot"
        return "evaluate"

    @staticmethod
    def _goal_options(goal_type: str, text: str, independent: List[str]) -> Dict[str, Any]:
        options: Dict[str, Any] = {}
        lowered = text.lower()
        if goal_type == "optimize":
            wants_max = bool(re.search(r"\bmaxim\w*", lowered))
            wants_min = bool(re.search(r"\bminim\w*", lowered))
            if wants_max and not wants_min:
                options["direction"] = "maximize"
            elif wants_min and not wants_max:
                options["direction"] = "minimize"
            else:
                options["direction"] = "both"
        if goal_type == "solve" and independent:
            options["solve_for"] = independent[0]
        if goal_type == "series":
            options["order"] = 6
            options["point"] = 0
        return options

    # ------------------------------------------------------- variable roles
    @staticmethod
    def _preference_key(name: str) -> Tuple[int, int, str]:
        base = base_name(name)
        rank = INDEPENDENT_PREFERENCE.index(base) if base in INDEPENDENT_PREFERENCE else len(INDEPENDENT_PREFERENCE)
        integer = 1 if parameter_hint(name)[0] == "integer" else 0
        return (integer, rank, name)

    def _order_variables(self, names: List[str], assignments: Dict[str, float]) -> List[str]:
        """Order variables: free ones before assigned/defined ones, then by preference."""
        defined = getattr(self, "_symbol_defs", {})
        return sorted(set(names), key=lambda n: ((1 if n in assignments or n in defined else 0),)
                      + self._preference_key(n))

    @staticmethod
    def _solve_for_hint(text: str, variables: List[str]) -> Optional[str]:
        for match in re.finditer(r"\bsolv\w*\s+(?:it\s+|this\s+|the\s+equation\s+)?for\s+\$?\\?([A-Za-z]\w*)", text, re.IGNORECASE):
            candidate = match.group(1)
            if candidate in variables:
                return candidate
        return None

    def _choose_independent(self, goal_type: str, variables: List[str],
                            assignments: Dict[str, float], text: str) -> List[str]:
        if not variables or goal_type == "symbolic":
            return []
        # Values stated in the document (g = 9.81) stay fixed unless nothing else varies
        defined = getattr(self, "_symbol_defs", {})
        candidates = [var for var in variables if var not in assignments and var not in defined] or list(variables)
        if goal_type == "solve":
            hinted = self._solve_for_hint(text, variables)
            return [hinted or candidates[0]]
        if goal_type == "plot" and len(candidates) == 2:
            return list(candidates[:2])
        return [candidates[0]]

    @staticmethod
    def _range_for(name: str, constraints: Dict[str, Dict[str, float]]) -> Tuple[float, float]:
        low, high = parameter_hint(name)[1]
        bounds = constraints.get(name) or constraints.get(base_name(name)) or {}
        if "min" in bounds:
            minimum = float(bounds["min"])
            if minimum >= high:
                high = minimum + 10.0
            low = max(low, minimum + 0.01 * (high - minimum))
        if "max" in bounds:
            maximum = float(bounds["max"])
            if maximum <= low:
                low = maximum - 10.0
            high = min(high, maximum - 0.01 * (maximum - low))
        return (round(float(low), 6), round(float(high), 6))

    def _fixed_value(self, name: str, value_range: Tuple[float, float], assignments: Dict[str, float]) -> float:
        if name in assignments:
            return float(assignments[name])
        derived = self._value_from_definition(name, assignments)
        if derived is not None:
            return round(derived, 6)
        default = float(parameter_hint(name)[2])
        low, high = value_range
        if not low <= default <= high:
            default = low + 0.25 * (high - low)
        return round(default, 6)

    def _value_from_definition(self, name: str, assignments: Dict[str, float], depth: int = 0) -> Optional[float]:
        """Value of a symbol defined in the document (e.g. theta = alpha + (b+1)/2)."""
        definition = getattr(self, "_symbol_defs", {}).get(name)
        if definition is None or depth > 5:
            return None
        values = {}
        for symbol in definition.free_symbols:
            if symbol.name in assignments:
                values[symbol] = assignments[symbol.name]
            else:
                nested = self._value_from_definition(symbol.name, assignments, depth + 1)
                values[symbol] = nested if nested is not None else parameter_hint(symbol.name)[2]
        try:
            number = complex(definition.subs(values).evalf())
        except (TypeError, ValueError):
            return None
        if abs(number.imag) > 1e-12 or number.real != number.real:
            return None
        return float(number.real)

    # --------------------------------------------------------------- sampling
    def _extract_parameters_from_expr(self, expr: sp.Basic) -> Dict[str, Any]:
        """Extract parameter information from a SymPy expression (JSON-friendly)."""
        params = {}
        for symbol in expr.free_symbols:
            name = str(symbol)
            ptype, value_range, default = parameter_hint(name)
            params[name] = {
                "type": ptype,
                "range": list(value_range),
                "default": default,
                "assumptions": {k: v for k, v in symbol.assumptions0.items() if v is not None},
            }
        return params

    def _suggest_sampling_strategy(self, expr: sp.Basic, variables: List[str], goal_type: str) -> Dict[str, Any]:
        """Suggest a sampling strategy for numerical evaluation."""
        sampling: Dict[str, Any] = {"method": "uniform", "points": DEFAULT_POINTS.get(goal_type, 100), "ranges": {}}
        for var in variables:
            sampling["ranges"][var] = parameter_hint(var)[1]
        if goal_type == "plot" and len(variables) >= 2:
            sampling["method"] = "meshgrid"
            sampling["points"] = DEFAULT_POINTS["plot2d"]
        elif goal_type == "optimize":
            sampling["method"] = "grid+refine"
        elif goal_type == "symbolic":
            sampling["method"] = "none"
        return sampling

    @staticmethod
    def _determine_output_type(expr: sp.Basic, variables: List[str], goal_type: str) -> str:
        """Determine what type of output to expect."""
        if goal_type == "symbolic":
            return "symbolic"
        if not variables:
            return "scalar"
        if goal_type in ("plot", "verify", "optimize"):
            return "array"
        return "function"

    # ------------------------------------------------------------ description
    @staticmethod
    def _describe(task: ComputationTask, title: Optional[str] = None) -> str:
        subject = f"{task.label} = {task.expression}" if task.label else task.expression
        if task.equation:
            subject = f"{task.equation['lhs_str']} = {task.equation['rhs_str']}"
        if len(subject) > 90:
            subject = subject[:87] + "..."
        if title:
            subject = title
        verbs = {
            "evaluate": "Evaluate", "plot": "Plot", "solve": "Solve", "optimize": "Find extrema of",
            "integrate": "Integrate", "differentiate": "Differentiate", "series": "Series-expand",
            "verify": "Numerically verify", "symbolic": "Record symbolic relation",
        }
        text = f"{verbs.get(task.goal_type, task.goal_type.title())} {subject}"
        ranges = task.suggested_sampling.get("ranges", {})
        if task.independent_variables:
            spans = ", ".join(
                f"{var} in [{ranges[var][0]:g}, {ranges[var][1]:g}]" for var in task.independent_variables
            )
            text += f" for {spans}"
        if task.fixed_parameters:
            fixed = ", ".join(f"{name}={value:g}" for name, value in task.fixed_parameters.items())
            text += f" with {fixed}"
        return text


# Convenience function
def analyze_expressions(expressions: Sequence[Any], context: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
    """Analyze expressions and return computation tasks as JSON-serialisable dictionaries."""
    analyzer = ExpressionAnalyzer()
    return [task.to_dict() for task in analyzer.analyze_expressions(expressions, context)]
