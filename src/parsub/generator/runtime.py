"""
ParSub runtime helpers.

This module is copied verbatim into every generated computation script so that
the scripts are self-contained: they only need NumPy, SciPy, SymPy, Matplotlib
and pandas.  It can also be imported directly (``parsub.generator.runtime``).

Each ``*_task`` function performs one kind of computation, writes its plots to
``<output>/plots`` and its data to ``<output>/data`` and returns a JSON-friendly
summary.  :func:`run_tasks` executes a list of tasks, isolating failures and
time-outs so that one difficult expression never prevents the others from
producing results.
"""

import argparse
import json
import math
import os
import signal
import sys
import threading
import time
import traceback
import warnings
from contextlib import contextmanager

import matplotlib

matplotlib.use("Agg")  # headless, file-only backend

import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
import pandas as pd  # noqa: E402
import sympy as sp  # noqa: E402
from mpl_toolkits.mplot3d import Axes3D  # noqa: E402,F401  (registers the 3d projection)
from scipy import integrate as sci_integrate  # noqa: E402
from scipy import optimize  # noqa: E402

warnings.filterwarnings("ignore")
plt.rcParams["figure.dpi"] = 100
plt.rcParams["savefig.dpi"] = 300  # publication quality output
plt.rcParams["font.size"] = 10

POINTWISE_LIMIT_1D = 120  # max samples when every point needs a SymPy evalf
POINTWISE_LIMIT_2D = 25   # max samples per axis for pointwise surface plots
SYMBOLIC_TIME_LIMIT = 20  # seconds allowed for symbolic solve/integrate/simplify


# --------------------------------------------------------------------- output
class OutputContext:
    """Where a run writes its files, plus the list of files written."""

    def __init__(self, output_dir):
        self.output_dir = os.path.abspath(output_dir)
        self.plots_dir = os.path.join(self.output_dir, "plots")
        self.data_dir = os.path.join(self.output_dir, "data")
        os.makedirs(self.plots_dir, exist_ok=True)
        os.makedirs(self.data_dir, exist_ok=True)
        self.files = []

    def relative(self, path):
        return os.path.relpath(path, self.output_dir).replace(os.sep, "/")


def _json_default(value):
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (np.floating,)):
        return None if not np.isfinite(value) else float(value)
    if isinstance(value, np.ndarray):
        return value.tolist()
    if isinstance(value, (np.bool_,)):
        return bool(value)
    if isinstance(value, complex):
        return {"real": value.real, "imag": value.imag}
    if isinstance(value, sp.Basic):
        return str(value)
    return str(value)


def _clean_json(value):
    """Replace NaN/inf (invalid JSON) by None, recursively."""
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, dict):
        return {str(k): _clean_json(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_clean_json(v) for v in value]
    return value


def save_plot(fig, filename, output_dir="./output/plots", ctx=None):
    """Save a Matplotlib figure at high resolution and close it."""
    if ctx is not None:
        output_dir = ctx.plots_dir
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    fig.savefig(filepath, dpi=300, bbox_inches="tight")
    plt.close(fig)
    if ctx is not None:
        ctx.files.append(ctx.relative(filepath))
    return filepath


def save_data(data, filename, output_dir="./output/data", ctx=None):
    """
    Save data as CSV, TSV, Excel (.xlsx) or JSON, chosen by the file extension.

    Tabular formats accept a dict of equal-length columns, a 2-D array or a
    DataFrame; JSON accepts any (nested) dict/list.
    """
    if ctx is not None:
        output_dir = ctx.data_dir
    os.makedirs(output_dir, exist_ok=True)
    filepath = os.path.join(output_dir, filename)
    if filename.endswith(".json"):
        payload = json.loads(json.dumps(data, default=_json_default))
        with open(filepath, "w", encoding="utf-8") as handle:
            json.dump(_clean_json(payload), handle, indent=2)
    else:
        if isinstance(data, pd.DataFrame):
            frame = data
        elif isinstance(data, dict):
            columns = {key: np.ravel(np.asarray(value)) if np.ndim(value) else [value] for key, value in data.items()}
            frame = pd.DataFrame(columns)
        else:
            frame = pd.DataFrame(np.atleast_2d(np.asarray(data)))
        if filename.endswith(".tsv"):
            frame.to_csv(filepath, sep="\t", index=False)
        elif filename.endswith((".xlsx", ".xls")):
            if filename.endswith(".xls"):
                filepath = filepath + "x"
            frame.to_excel(filepath, index=False)
        else:
            if not filename.endswith(".csv"):
                filepath = filepath + ".csv"
            frame.to_csv(filepath, index=False)
    if ctx is not None:
        ctx.files.append(ctx.relative(filepath))
    return filepath


# ------------------------------------------------------------------ time-outs
class TaskTimeout(Exception):
    """Raised when a computation exceeds its time budget."""


def _alarm_supported():
    return hasattr(signal, "SIGALRM") and threading.current_thread() is threading.main_thread()


@contextmanager
def time_limit(seconds):
    """Limit the wall time of a block (Unix main thread only; no-op elsewhere)."""
    if not seconds or not _alarm_supported():
        yield
        return
    outer_remaining = signal.getitimer(signal.ITIMER_REAL)[0]
    budget = seconds if not outer_remaining else min(seconds, outer_remaining)
    previous_handler = signal.getsignal(signal.SIGALRM)
    started = time.monotonic()

    def handler(signum, frame):
        raise TaskTimeout("computation timed out after %.0f s" % budget)

    signal.signal(signal.SIGALRM, handler)
    signal.setitimer(signal.ITIMER_REAL, budget)
    try:
        yield
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)
        signal.signal(signal.SIGALRM, previous_handler)
        if outer_remaining:
            remaining = outer_remaining - (time.monotonic() - started)
            signal.setitimer(signal.ITIMER_REAL, max(remaining, 0.001))


def attempt(func, seconds=SYMBOLIC_TIME_LIMIT):
    """Run ``func()``; return ``(True, result)`` or ``(False, error message)``."""
    try:
        with time_limit(seconds):
            return True, func()
    except TaskTimeout as exc:
        return False, str(exc)
    except Exception as exc:  # noqa: BLE001 - report every failure
        return False, "%s: %s" % (type(exc).__name__, exc)


# ----------------------------------------------------------- numeric helpers
def parse_sympy(text):
    """Rebuild a SymPy expression from its ``srepr`` (or plain string) form."""
    return sp.sympify(text)


def symbol_map(expr):
    return {symbol.name: symbol for symbol in expr.free_symbols}


def substitute(expr, values):
    """Substitute ``{name: value}`` into ``expr`` (matching symbols by name)."""
    if not values:
        return expr
    symbols = symbol_map(expr)
    mapping = {symbols[name]: sp.nsimplify(value) if float(value).is_integer() else sp.Float(value)
               for name, value in values.items() if name in symbols}
    return expr.subs(mapping)


def to_real(values, tol=1e-9):
    """Convert values to a float array; non-real entries become NaN."""
    array = np.asarray(values)
    if array.dtype == object:
        flat = []
        for item in array.ravel():
            try:
                flat.append(complex(item))
            except (TypeError, ValueError):
                flat.append(complex(np.nan))
        array = np.array(flat, dtype=complex).reshape(array.shape)
    if np.iscomplexobj(array):
        real = array.real.astype(float)
        bad = np.abs(array.imag) > tol * np.maximum(1.0, np.abs(real))
        return np.where(bad, np.nan, real)
    return array.astype(float)


def _needs_pointwise(expr):
    return expr.has(sp.Integral, sp.Sum, sp.Product, sp.Limit)


def lambdify_expr(expr, variables, fixed=None):
    """
    Convert a SymPy expression into a vectorised NumPy function of ``variables``.

    Parameters listed in ``fixed`` are substituted first.  Expressions that NumPy
    cannot evaluate directly (integrals, infinite sums, ...) fall back to
    point-by-point evaluation with SymPy/mpmath.  The returned callable has an
    attribute ``pointwise`` telling which strategy is used.
    """
    expr = substitute(expr, fixed or {})
    expr = expr.replace(lambda node: isinstance(node, sp.Derivative), lambda node: node.doit())
    symbols = symbol_map(expr)
    args = [symbols.get(name, sp.Symbol(name)) for name in variables]
    leftover = expr.free_symbols - set(args)
    if leftover:
        expr = expr.subs({symbol: 1 for symbol in leftover})

    if not _needs_pointwise(expr):
        try:
            compiled = sp.lambdify(args, expr, modules=["scipy", "numpy"])
            probe = [np.linspace(0.3, 0.7, 3) for _ in args]
            with np.errstate(all="ignore"):
                np.asarray(compiled(*probe), dtype=complex)

            def vectorised(*arrays):
                arrays = [np.asarray(a, dtype=float) for a in arrays]
                shape = np.broadcast(*arrays).shape if arrays else ()
                with np.errstate(all="ignore"):
                    result = np.asarray(compiled(*arrays))
                return to_real(np.broadcast_to(result, shape))

            vectorised.pointwise = False
            return vectorised
        except Exception:  # noqa: BLE001 - fall back to SymPy evaluation
            pass

    def scalar(*values):
        try:
            value = expr.subs(dict(zip(args, [sp.Float(v) for v in values]))).evalf(15)
            return complex(value)
        except Exception:  # noqa: BLE001
            return complex(np.nan)

    vector = np.vectorize(scalar, otypes=[complex])

    def pointwise(*arrays):
        arrays = [np.asarray(a, dtype=float) for a in arrays]
        if not arrays:
            return to_real(scalar())
        return to_real(vector(*arrays))

    pointwise.pointwise = True
    return pointwise


def evaluate_expression(expr, variables=None, values_dict=None):
    """Evaluate ``expr`` at ``values_dict`` and return a float (NaN if not real)."""
    value = substitute(expr, values_dict or {})
    try:
        number = complex(value.evalf(15))
    except (TypeError, ValueError):
        return float("nan")
    return float(to_real(number))


def sample_axis(value_range, points, pointwise, limit=POINTWISE_LIMIT_1D):
    low, high = value_range
    count = min(points, limit) if pointwise else points
    return np.linspace(float(low), float(high), max(int(count), 2))


def finite_stats(values):
    finite = np.asarray(values, dtype=float)
    finite = finite[np.isfinite(finite)]
    if finite.size == 0:
        return {"finite_points": 0, "min": None, "max": None, "mean": None}
    return {
        "finite_points": int(finite.size),
        "min": float(finite.min()),
        "max": float(finite.max()),
        "mean": float(finite.mean()),
    }


def short(text, limit=80):
    text = str(text)
    return text if len(text) <= limit else text[: limit - 3] + "..."


def _fixed_note(fixed):
    if not fixed:
        return ""
    return " (" + ", ".join("%s=%g" % (name, value) for name, value in fixed.items()) + ")"


def _line_plot(ctx, filename, x, series, xlabel, ylabel, title, markers=None):
    fig, ax = plt.subplots(figsize=(10, 6))
    for label, values, style in series:
        ax.plot(x, values, style, linewidth=2, label=label)
    for position, label in markers or []:
        ax.axvline(x=position, color="red", linestyle="--", alpha=0.7)
        ax.annotate(label, (position, 0), xytext=(4, 8), textcoords="offset points", color="red", fontsize=8)
    ax.set_xlabel(xlabel)
    ax.set_ylabel(ylabel)
    ax.set_title(short(title, 90))
    ax.grid(True, alpha=0.3)
    if len(series) > 1:
        ax.legend()
    return save_plot(fig, filename, ctx=ctx)


# ------------------------------------------------------------------ the tasks
def evaluate_task(ctx, task_id, expr, independent=(), fixed=None, ranges=None, points=100, label="f", point=None):
    """Evaluate an expression: a single value at ``point``, plus a sweep over the first variable."""
    fixed = dict(fixed or {})
    ranges = ranges or {}
    summary = {"expression": str(expr), "latex": sp.latex(expr), "fixed_parameters": fixed}
    defaults = dict(fixed)
    defaults.update(point or {})
    for name in independent:
        low, high = ranges.get(name, (-5, 5))
        defaults.setdefault(name, (low + high) / 2.0)
    summary["evaluation_point"] = defaults
    summary["value_at_point"] = evaluate_expression(expr, None, defaults)
    if independent:
        var = independent[0]
        f = lambdify_expr(expr, [var], fixed)
        x = sample_axis(ranges.get(var, (-5, 5)), points, f.pointwise)
        y = f(x)
        save_data({var: x, label: y}, "task_%d_evaluation.csv" % task_id, ctx=ctx)
        _line_plot(ctx, "task_%d_evaluation.png" % task_id, x, [(label, y, "b-")], var,
                   label, "%s = %s%s" % (label, short(expr, 60), _fixed_note(fixed)))
        summary["sweep"] = dict(variable=var, points=int(len(x)), **finite_stats(y))
    save_data(summary, "task_%d_evaluation.json" % task_id, ctx=ctx)
    return summary


def plot_task(ctx, task_id, expr, independent, fixed=None, ranges=None, points=200, label="f"):
    """Line plot (one variable) or surface plot (two variables) of an expression."""
    fixed = dict(fixed or {})
    ranges = ranges or {}
    if not independent:
        return evaluate_task(ctx, task_id, expr, (), fixed, ranges, points, label)
    if len(independent) == 1:
        var = independent[0]
        f = lambdify_expr(expr, [var], fixed)
        x = sample_axis(ranges.get(var, (-5, 5)), points, f.pointwise)
        y = f(x)
        _line_plot(ctx, "task_%d_plot.png" % task_id, x, [(label, y, "b-")], var, label,
                   "%s = %s%s" % (label, short(expr, 60), _fixed_note(fixed)))
        save_data({var: x, label: y}, "task_%d_plot_data.csv" % task_id, ctx=ctx)
        return dict(expression=str(expr), variable=var, fixed_parameters=fixed, **finite_stats(y))

    var1, var2 = independent[0], independent[1]
    f = lambdify_expr(expr, [var1, var2], fixed)
    x1 = sample_axis(ranges.get(var1, (-5, 5)), points, f.pointwise, POINTWISE_LIMIT_2D)
    x2 = sample_axis(ranges.get(var2, (-5, 5)), points, f.pointwise, POINTWISE_LIMIT_2D)
    X1, X2 = np.meshgrid(x1, x2)
    Y = f(X1, X2)
    fig = plt.figure(figsize=(12, 9))
    ax = fig.add_subplot(111, projection="3d")
    surface = ax.plot_surface(X1, X2, np.ma.masked_invalid(Y), cmap="viridis", alpha=0.9)
    ax.set_xlabel(var1)
    ax.set_ylabel(var2)
    ax.set_zlabel(label)
    ax.set_title(short("%s = %s%s" % (label, short(expr, 60), _fixed_note(fixed)), 90))
    fig.colorbar(surface, shrink=0.5, aspect=5)
    save_plot(fig, "task_%d_surface_plot.png" % task_id, ctx=ctx)
    save_data({var1: X1, var2: X2, label: Y}, "task_%d_surface_data.csv" % task_id, ctx=ctx)
    return dict(expression=str(expr), variables=[var1, var2], fixed_parameters=fixed, **finite_stats(Y))


def _numeric_roots(g, low, high, samples=2000):
    """Real roots of a 1-D function on [low, high] via sign changes + brentq."""
    x = np.linspace(low, high, samples)
    y = g(x)
    roots = []
    for i in range(len(x) - 1):
        a, b, fa, fb = x[i], x[i + 1], y[i], y[i + 1]
        if not (np.isfinite(fa) and np.isfinite(fb)):
            continue
        if fa == 0:
            roots.append(float(a))
        elif fa * fb < 0:
            try:
                root = optimize.brentq(lambda t: float(g(np.array([t]))[0]), a, b)
            except (ValueError, RuntimeError):
                continue
            # reject poles (sign change through infinity)
            if abs(float(g(np.array([root]))[0])) < 1e-6 * max(1.0, abs(fa), abs(fb)):
                roots.append(float(root))
    unique = []
    for root in sorted(roots):
        if not unique or abs(root - unique[-1]) > 1e-8 * max(1.0, abs(root)):
            unique.append(root)
    return unique


def solve_task(ctx, task_id, lhs, rhs=0, solve_for=None, fixed=None, ranges=None, points=400):
    """Solve ``lhs = rhs`` symbolically and numerically for one variable."""
    fixed = dict(fixed or {})
    ranges = ranges or {}
    lhs, rhs = sp.sympify(lhs), sp.sympify(rhs)
    equation = sp.Eq(lhs, rhs, evaluate=False)
    difference = lhs - rhs
    summary = {"equation": "%s = %s" % (lhs, rhs), "latex": sp.latex(equation), "fixed_parameters": fixed}
    symbols = symbol_map(difference)
    if not solve_for or solve_for not in symbols:
        summary["holds"] = bool(abs(evaluate_expression(difference, None, fixed)) < 1e-9)
        save_data(summary, "task_%d_solutions.json" % task_id, ctx=ctx)
        return summary

    target = symbols[solve_for]
    summary["solve_for"] = solve_for
    ok, solutions = attempt(lambda: sp.solve(equation, target))
    if ok:
        summary["symbolic_solutions"] = [str(sol) for sol in solutions]
        summary["symbolic_solutions_latex"] = [sp.latex(sol) for sol in solutions]
        numeric = []
        for sol in solutions:
            value = evaluate_expression(sol, None, fixed)
            if np.isfinite(value):
                numeric.append(value)
        summary["solutions_at_fixed_parameters"] = numeric
    else:
        summary["symbolic_solutions"] = None
        summary["symbolic_error"] = solutions

    low, high = ranges.get(solve_for, (-5, 5))
    g = lambdify_expr(difference, [solve_for], fixed)
    roots = _numeric_roots(g, low, high, samples=500 if g.pointwise else 4000)
    summary["numeric_roots_in_range"] = roots
    summary["search_range"] = [low, high]
    summary["num_solutions"] = len(summary.get("symbolic_solutions") or roots)

    x = sample_axis((low, high), points, g.pointwise)
    y = g(x)
    _line_plot(ctx, "task_%d_solutions_plot.png" % task_id, x,
               [("%s - (%s)" % (short(lhs, 30), short(rhs, 30)), y, "b-")], solve_for, "lhs - rhs",
               "Roots of %s = %s%s" % (short(lhs, 40), short(rhs, 40), _fixed_note(fixed)),
               markers=[(root, "%.4g" % root) for root in roots[:10]])
    save_data(summary, "task_%d_solutions.json" % task_id, ctx=ctx)
    return summary


def optimize_task(ctx, task_id, expr, independent, fixed=None, ranges=None, direction="both", points=1000):
    """Find the minimum and/or maximum of an expression over a bounded region."""
    fixed = dict(fixed or {})
    ranges = ranges or {}
    summary = {"expression": str(expr), "fixed_parameters": fixed, "direction": direction}
    if not independent:
        summary["value"] = evaluate_expression(expr, None, fixed)
        save_data(summary, "task_%d_optimization.json" % task_id, ctx=ctx)
        return summary

    names = list(independent[:2])
    f = lambdify_expr(expr, names, fixed)
    bounds = [tuple(float(v) for v in ranges.get(name, (-5, 5))) for name in names]
    per_axis = int(points) if len(names) == 1 else int(math.sqrt(points)) + 1
    if f.pointwise:
        per_axis = min(per_axis, POINTWISE_LIMIT_1D if len(names) == 1 else POINTWISE_LIMIT_2D)
    axes = [np.linspace(low, high, per_axis) for low, high in bounds]
    grids = np.meshgrid(*axes, indexing="ij")
    values = f(*grids)

    def refine(sign):
        masked = np.where(np.isfinite(values), sign * values, np.inf)
        if not np.isfinite(masked).any():
            return None
        index = np.unravel_index(np.argmin(masked), masked.shape)
        start = [grid[index] for grid in grids]

        def objective(point):
            value = f(*[np.array([p]) for p in point])[0]
            return sign * value if np.isfinite(value) else 1e300

        best_point, best_value = start, sign * masked[index]
        if not f.pointwise:
            result = optimize.minimize(objective, x0=start, bounds=bounds, method="L-BFGS-B")
            if result.success and result.fun <= best_value:
                best_point, best_value = list(result.x), result.fun
        return {
            "point": {name: float(value) for name, value in zip(names, best_point)},
            "value": float(sign * best_value),
        }

    if direction in ("minimize", "both"):
        summary["minimum"] = refine(1.0)
    if direction in ("maximize", "both"):
        summary["maximum"] = refine(-1.0)
    summary["bounds"] = {name: list(bound) for name, bound in zip(names, bounds)}

    if len(names) == 1:
        markers = []
        for key in ("minimum", "maximum"):
            if summary.get(key):
                markers.append((summary[key]["point"][names[0]], key[:3]))
        _line_plot(ctx, "task_%d_optimization_plot.png" % task_id, axes[0], [("f", values, "b-")], names[0],
                   "f", "Extrema of %s%s" % (short(expr, 60), _fixed_note(fixed)), markers=markers)
    save_data(summary, "task_%d_optimization.json" % task_id, ctx=ctx)
    return summary


def integrate_task(ctx, task_id, expr, independent=(), fixed=None, ranges=None, points=200):
    """Integrate an expression (or evaluate the integral it already contains)."""
    fixed = dict(fixed or {})
    ranges = ranges or {}
    summary = {"expression": str(expr), "latex": sp.latex(expr), "fixed_parameters": fixed}
    if expr.has(sp.Integral):
        # The expression *is* an integral: evaluate it numerically.
        summary["mode"] = "evaluate integral"
        if independent:
            var = independent[0]
            f = lambdify_expr(expr, [var], fixed)
            x = sample_axis(ranges.get(var, (-5, 5)), points, f.pointwise)
            y = f(x)
            _line_plot(ctx, "task_%d_integration_plot.png" % task_id, x, [("integral", y, "b-")], var,
                       "value", "%s%s" % (short(expr, 70), _fixed_note(fixed)))
            save_data({var: x, "integral": y}, "task_%d_integration.csv" % task_id, ctx=ctx)
            summary["sweep"] = dict(variable=var, **finite_stats(y))
        else:
            summary["value"] = evaluate_expression(expr, None, fixed)
        save_data(summary, "task_%d_integration.json" % task_id, ctx=ctx)
        return summary

    if not independent:
        summary["value"] = evaluate_expression(expr, None, fixed)
        save_data(summary, "task_%d_integration.json" % task_id, ctx=ctx)
        return summary

    var = independent[0]
    symbol = symbol_map(expr).get(var, sp.Symbol(var))
    low, high = (float(v) for v in ranges.get(var, (-5, 5)))
    summary["mode"] = "integrate with respect to %s" % var
    ok, antiderivative = attempt(lambda: sp.integrate(expr, symbol))
    if ok and not antiderivative.has(sp.Integral):
        summary["antiderivative"] = str(antiderivative)
        summary["antiderivative_latex"] = sp.latex(antiderivative)
    else:
        summary["antiderivative"] = None
    f = lambdify_expr(expr, [var], fixed)
    value, error = sci_integrate.quad(lambda t: float(f(np.array([t]))[0]), low, high, limit=200)
    summary["definite_integral"] = {"variable": var, "lower": low, "upper": high,
                                    "value": float(value), "abs_error_estimate": float(error)}
    x = sample_axis((low, high), points, f.pointwise)
    y = f(x)
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.plot(x, y, "b-", linewidth=2)
    ax.fill_between(x, np.nan_to_num(y), alpha=0.3)
    ax.set_xlabel(var)
    ax.set_ylabel("integrand")
    ax.set_title(short("Integral over [%g, %g] = %.6g%s" % (low, high, value, _fixed_note(fixed)), 90))
    ax.grid(True, alpha=0.3)
    save_plot(fig, "task_%d_integration_plot.png" % task_id, ctx=ctx)
    save_data(summary, "task_%d_integration.json" % task_id, ctx=ctx)
    return summary


def differentiate_task(ctx, task_id, expr, independent=(), fixed=None, ranges=None, points=200):
    """Symbolic partial derivatives, plus a plot of f and df/dx along one variable."""
    fixed = dict(fixed or {})
    ranges = ranges or {}
    summary = {"expression": str(expr), "latex": sp.latex(expr), "fixed_parameters": fixed}
    if expr.has(sp.Derivative):
        expr = expr.doit()
        summary["evaluated_derivative"] = str(expr)
        summary["evaluated_derivative_latex"] = sp.latex(expr)
        return dict(summary, **evaluate_task(ctx, task_id, expr, independent, fixed, ranges, points, "derivative"))

    symbols = symbol_map(expr)
    derivatives = {name: sp.diff(expr, symbol) for name, symbol in sorted(symbols.items())}
    summary["partial_derivatives"] = {name: str(d) for name, d in derivatives.items()}
    summary["partial_derivatives_latex"] = {name: sp.latex(d) for name, d in derivatives.items()}
    if independent:
        var = independent[0]
        f = lambdify_expr(expr, [var], fixed)
        df = lambdify_expr(derivatives.get(var, sp.Integer(0)), [var], fixed)
        x = sample_axis(ranges.get(var, (-5, 5)), points, f.pointwise or df.pointwise)
        y, dy = f(x), df(x)
        _line_plot(ctx, "task_%d_differentiation_plot.png" % task_id, x,
                   [("f", y, "b-"), ("df/d%s" % var, dy, "r--")], var, "value",
                   "%s and its derivative%s" % (short(expr, 50), _fixed_note(fixed)))
        save_data({var: x, "f": y, "df_d%s" % var: dy}, "task_%d_differentiation.csv" % task_id, ctx=ctx)
    save_data(summary, "task_%d_differentiation.json" % task_id, ctx=ctx)
    return summary


def series_task(ctx, task_id, expr, independent=(), fixed=None, ranges=None, order=6, point=0, points=200):
    """Taylor/Laurent expansion about ``point`` and comparison with the function."""
    fixed = dict(fixed or {})
    ranges = ranges or {}
    summary = {"expression": str(expr), "fixed_parameters": fixed}
    if not independent:
        summary["value"] = evaluate_expression(expr, None, fixed)
        save_data(summary, "task_%d_series.json" % task_id, ctx=ctx)
        return summary
    var = independent[0]
    symbol = symbol_map(expr).get(var, sp.Symbol(var))
    low, high = ranges.get(var, (-5, 5))
    candidates = [point] if point is not None else []
    candidates.append(round((low + high) / 2.0, 6))
    expansion, used, error = None, None, None
    for x0 in candidates:
        ok, result = attempt(lambda: sp.series(expr, symbol, x0, order).removeO())
        if ok and not result.has(sp.Order):
            expansion, used = result, x0
            break
        error = result
    if expansion is None:
        raise RuntimeError("series expansion failed: %s" % error)
    summary.update({"variable": var, "point": used, "order": order,
                    "series": str(expansion), "series_latex": sp.latex(expansion)})
    f = lambdify_expr(expr, [var], fixed)
    s = lambdify_expr(expansion, [var], fixed)
    x = sample_axis((low, high), points, f.pointwise or s.pointwise)
    _line_plot(ctx, "task_%d_series_plot.png" % task_id, x,
               [("f", f(x), "b-"), ("series (order %d)" % order, s(x), "r--")], var, "value",
               "Series of %s about %s = %g" % (short(expr, 50), var, used))
    save_data(summary, "task_%d_series.json" % task_id, ctx=ctx)
    return summary


def verify_task(ctx, task_id, lhs, rhs, independent=(), fixed=None, ranges=None, points=100, rtol=1e-6):
    """Numerically check an identity ``lhs = rhs`` by sampling both sides."""
    fixed = dict(fixed or {})
    ranges = ranges or {}
    lhs, rhs = sp.sympify(lhs), sp.sympify(rhs)
    summary = {"equation": "%s = %s" % (lhs, rhs), "latex": "%s = %s" % (sp.latex(lhs), sp.latex(rhs)),
               "fixed_parameters": fixed}
    if independent:
        var = independent[0]
        fl = lambdify_expr(lhs, [var], fixed)
        fr = lambdify_expr(rhs, [var], fixed)
        x = sample_axis(ranges.get(var, (-5, 5)), points, fl.pointwise or fr.pointwise)
        left, right = fl(x), fr(x)
        _line_plot(ctx, "task_%d_verification_plot.png" % task_id, x,
                   [("left: %s" % short(lhs, 40), left, "b-"), ("right: %s" % short(rhs, 40), right, "r--")],
                   var, "value", "Check of %s = %s%s" % (short(lhs, 30), short(rhs, 30), _fixed_note(fixed)))
        save_data({var: x, "lhs": left, "rhs": right, "abs_difference": np.abs(left - right)},
                  "task_%d_verification.csv" % task_id, ctx=ctx)
    else:
        left = np.array([evaluate_expression(lhs, None, fixed)])
        right = np.array([evaluate_expression(rhs, None, fixed)])
    mask = np.isfinite(left) & np.isfinite(right)
    difference = np.abs(left - right)[mask]
    scale = np.maximum(1.0, np.abs(right[mask]))
    summary["compared_points"] = int(mask.sum())
    summary["max_abs_difference"] = float(difference.max()) if difference.size else None
    summary["max_rel_difference"] = float((difference / scale).max()) if difference.size else None
    summary["identity_holds_numerically"] = bool(difference.size and (difference / scale).max() < rtol)
    save_data(summary, "task_%d_verification.json" % task_id, ctx=ctx)
    return summary


def symbolic_task(ctx, task_id, expr):
    """Record a relation that involves unknown functions (no numerics possible)."""
    summary = {
        "expression": str(expr),
        "latex": sp.latex(expr),
        "free_symbols": sorted(str(s) for s in expr.free_symbols),
        "unknown_functions": sorted({str(f.func) for f in expr.atoms(sp.core.function.AppliedUndef)}),
    }
    ok, simplified = attempt(lambda: sp.simplify(expr), seconds=10)
    summary["simplified"] = str(simplified) if ok else None
    save_data(summary, "task_%d_symbolic.json" % task_id, ctx=ctx)
    return summary


# ----------------------------------------------------------------- the runner
def run_tasks(tasks, argv=None, default_output_dir=None):
    """
    Execute ``tasks`` (a list of ``(task_id, goal, description, function)``).

    Command line options: ``--output-dir DIR``, ``--timeout SECONDS`` (per task)
    and ``--tasks 1,3`` (run a subset).  The output directory defaults to the
    ``PARSUB_OUTPUT_DIR`` environment variable, then to ``default_output_dir``.
    Returns the process exit code (0 if every task succeeded).
    """
    parser = argparse.ArgumentParser(description="Run ParSub generated computations.")
    parser.add_argument("--output-dir", default=os.environ.get("PARSUB_OUTPUT_DIR") or default_output_dir or ".")
    parser.add_argument("--timeout", type=float, default=float(os.environ.get("PARSUB_TASK_TIMEOUT", 120)),
                        help="time limit per task in seconds (0 = unlimited)")
    parser.add_argument("--tasks", default="", help="comma separated task numbers to run (default: all)")
    args = parser.parse_args(argv)

    selected = {int(item) for item in args.tasks.split(",") if item.strip()} if args.tasks else None
    ctx = OutputContext(args.output_dir)
    print("ParSub Mathematical Computation Suite")
    print("=" * 50)
    print("Output directory: %s" % ctx.output_dir)
    results = []
    for task_id, goal, description, func in tasks:
        if selected and task_id not in selected:
            continue
        print("[task %d] %s: %s" % (task_id, goal, short(description, 100)))
        started = time.time()
        before = len(ctx.files)
        record = {"task": task_id, "goal": goal, "description": description}
        try:
            with time_limit(args.timeout):
                summary = func(ctx)
            record.update(status="ok", summary=summary)
            print("    ok (%.1f s)" % (time.time() - started))
        except Exception as exc:  # noqa: BLE001 - isolate every task
            record.update(status="failed", error="%s: %s" % (type(exc).__name__, exc),
                          traceback=traceback.format_exc())
            print("    FAILED: %s" % record["error"])
        record["seconds"] = round(time.time() - started, 3)
        record["files"] = ctx.files[before:]
        results.append(record)

    failed = [r for r in results if r["status"] != "ok"]
    save_data({"tasks": results, "succeeded": len(results) - len(failed), "failed": len(failed)},
              "summary.json", ctx=ctx)
    print("=" * 50)
    print("Tasks completed: %d succeeded, %d failed" % (len(results) - len(failed), len(failed)))
    print("- Plots saved to %s" % ctx.plots_dir)
    print("- Data saved to %s" % ctx.data_dir)
    return 1 if failed else 0
