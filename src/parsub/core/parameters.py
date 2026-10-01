"""
Shared knowledge about common mathematical/physical symbol names.

Both the parser (parameter inference) and the analyzer (sampling strategy) use
this table so that the type, range and default value suggested for a symbol
are always consistent.
"""

import math
import re
from typing import Any, Dict, Tuple

# name -> (type, (min, max), default value)
PARAMETER_HINTS: Dict[str, Tuple[str, Tuple[float, float], float]] = {
    # Coordinates and independent variables
    "x": ("continuous", (-10.0, 10.0), 1.0),
    "y": ("continuous", (-10.0, 10.0), 1.0),
    "z": ("continuous", (-10.0, 10.0), 1.0),
    "t": ("continuous", (0.0, 10.0), 1.0),
    "s": ("continuous", (0.0, 10.0), 1.0),
    "u": ("continuous", (-10.0, 10.0), 1.0),
    "r": ("continuous", (0.0, 10.0), 1.0),
    "rho": ("continuous", (0.0, 5.0), 1.0),
    "theta": ("angle", (0.0, 2 * math.pi), math.pi / 4),
    "phi": ("angle", (0.0, 2 * math.pi), math.pi / 4),
    "psi": ("continuous", (-5.0, 5.0), 1.0),
    "xi": ("continuous", (-5.0, 5.0), 1.0),
    "eta": ("continuous", (0.1, 5.0), 1.0),
    "zeta": ("continuous", (0.1, 5.0), 1.0),
    "tau": ("continuous", (0.0, 10.0), 1.0),
    # Small parameters / coefficients
    "alpha": ("continuous", (0.0, 1.0), 0.5),
    "beta": ("continuous", (0.0, 1.0), 0.5),
    "gamma": ("continuous", (0.0, 1.0), 0.5),
    "delta": ("continuous", (-1.0, 1.0), 0.5),
    "epsilon": ("continuous", (0.0, 1.0), 0.1),
    "mu": ("continuous", (0.0, 1.0), 0.5),
    "nu": ("continuous", (0.0, 5.0), 1.0),
    "sigma": ("continuous", (0.1, 5.0), 1.0),
    "kappa": ("continuous", (0.0, 5.0), 1.0),
    # Physics
    "omega": ("frequency", (0.0, 10.0), 1.0),
    "f": ("frequency", (0.0, 10.0), 1.0),
    "lambda": ("wavelength", (0.1, 10.0), 1.0),
    "k": ("wave_number", (0.0, 10.0), 1.0),
    "g": ("constant", (9.0, 10.0), 9.81),
    "v": ("continuous", (0.0, 20.0), 10.0),
    "m": ("constant", (0.1, 10.0), 1.0),
    "A": ("constant", (0.0, 5.0), 1.0),
    # Integer-like indices
    "n": ("integer", (0.0, 10.0), 2.0),
    "j": ("integer", (0.0, 10.0), 2.0),
    "l": ("integer", (0.0, 10.0), 2.0),
    "i": ("integer", (0.0, 10.0), 2.0),
    # Generic constants
    "a": ("constant", (-5.0, 5.0), 1.0),
    "b": ("constant", (-5.0, 5.0), 1.0),
    "c": ("constant", (-5.0, 5.0), 1.0),
    "d": ("constant", (-5.0, 5.0), 1.0),
    "h": ("constant", (-5.0, 5.0), 1.0),
}

DEFAULT_HINT: Tuple[str, Tuple[float, float], float] = ("unknown", (-5.0, 5.0), 1.0)

# LaTeX variant spellings that mean the same symbol
_VARIANTS = {
    "vartheta": "theta",
    "varphi": "phi",
    "varepsilon": "epsilon",
    "varrho": "rho",
    "varsigma": "sigma",
    "varpi": "pi",
    "varkappa": "kappa",
}

# Preferred order when choosing which variables to sweep (independent variables)
INDEPENDENT_PREFERENCE = [
    "x", "t", "z", "r", "s", "theta", "phi", "y", "u", "rho", "tau",
    "omega", "zeta", "eta", "xi", "v", "k", "lambda",
]


def base_name(name: str) -> str:
    """Return the base of a symbol name: ``v_0`` -> ``v``, ``vartheta`` -> ``theta``."""
    base = re.split(r"[_^{]", str(name), maxsplit=1)[0].lstrip("\\")
    base = _VARIANTS.get(base, base)
    return base or str(name)


def parameter_hint(name: str) -> Tuple[str, Tuple[float, float], float]:
    """Return ``(type, (min, max), default)`` for a symbol name."""
    if name in PARAMETER_HINTS:
        return PARAMETER_HINTS[name]
    return PARAMETER_HINTS.get(base_name(name), DEFAULT_HINT)


def infer_parameter_type(name: str) -> str:
    """Infer the type of a parameter from its name."""
    return parameter_hint(name)[0]


def infer_parameter_range(name: str) -> Dict[str, float]:
    """Infer a reasonable sampling range for a parameter."""
    low, high = parameter_hint(name)[1]
    return {"min": low, "max": high}


def default_value(name: str) -> float:
    """Typical value used when a parameter is held fixed."""
    return parameter_hint(name)[2]


def describe_parameter(name: str, frequency: int = 1) -> Dict[str, Any]:
    """Build the JSON-friendly parameter record used throughout ParSub."""
    ptype, (low, high), default = parameter_hint(name)
    return {
        "name": name,
        "frequency": frequency,
        "type": ptype,
        "suggested_range": {"min": low, "max": high},
        "default": default,
    }
