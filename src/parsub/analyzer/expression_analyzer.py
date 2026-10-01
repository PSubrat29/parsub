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

        tasks: List[ComputationTask] = []
        seen = set()
        for expr_data in expressions or []:
            expr = self._as_sympy(_get(expr_data, "sympy_expr"))
            if expr is None or _get(expr_data, "kind") == "assignment":
                continue
            if isinstance(expr, Relational) and not isinstance(expr, sp.Equality):
                continue  # inequalities/conditions are not computed
            task = self._build_task(expr_data, expr, global_text, assignments)
            if task is None:
                continue
            key = (task.goal_type, sp.srepr(task.sympy_expr), task.equation and task.equation.get("lhs"))
            if key in seen:
                continue
            seen.add(key)
            tasks.append(task)
        return tasks

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
        definition = self._is_definition(expr)
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

        variables = self._order_variables(
            [str(symbol) for symbol in target.free_symbols], assignments
        )
        constraints = _get(expr_data, "constraints", {}) or {}
        ranges = {var: self._range_for(var, constraints) for var in variables}
        independent = self._choose_independent(goal_type, variables, assignments, local_text + " " + global_text)
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
        task.description = self._describe(task)
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
                has_calculus
                or (isinstance(lhs, sp.Function) and not lhs.is_Pow)
                or bool(target.atoms(sp.Function) - target.atoms(AppliedUndef))
                and not target.is_polynomial(*target.free_symbols)
            )
            if identity_like and lhs.free_symbols and rhs.free_symbols:
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
        """Order variables: unassigned before assigned, then by preference."""
        return sorted(set(names), key=lambda n: ((1 if n in assignments else 0),) + self._preference_key(n))

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
        candidates = [var for var in variables if var not in assignments] or list(variables)
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

    @staticmethod
    def _fixed_value(name: str, value_range: Tuple[float, float], assignments: Dict[str, float]) -> float:
        if name in assignments:
            return float(assignments[name])
        default = float(parameter_hint(name)[2])
        low, high = value_range
        if not low <= default <= high:
            default = low + 0.25 * (high - low)
        return round(default, 6)

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
    def _describe(task: ComputationTask) -> str:
        subject = f"{task.label} = {task.expression}" if task.label else task.expression
        if task.equation:
            subject = f"{task.equation['lhs_str']} = {task.equation['rhs_str']}"
        if len(subject) > 90:
            subject = subject[:87] + "..."
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
