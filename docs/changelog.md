# Changelog

All notable changes to ParSub. Versions follow [Semantic Versioning](https://semver.org/).

## 0.2.0 — 2 October 2026

First release on PyPI: `pip install parsub` ([PyPI page](https://pypi.org/project/parsub/0.2.0/),
[GitHub release](https://github.com/PSubrat29/parsub/releases/tag/v0.2.0)).

### Working pipeline
- LaTeX parsing with pylatexenc: inline and display math, align-like environments split into
  lines, equation labels, prose context, side conditions such as `(\Re(z) > 0)` turned into
  sampling ranges, statements such as `g = 9.81` used as parameter values.
- Strict LaTeX → SymPy conversion: a formula is converted completely or reported, never truncated.
- Goal detection from the prose: evaluate, plot, solve, optimize, integrate, differentiate,
  series, verify, symbolic.
- Self-contained generated scripts: one editable function per task, isolated with time limits,
  300 DPI plots, CSV/TSV/Excel/JSON data and `summary.json`.
- Command line (`parsub analyze / run / demo / version`), Python API (`parsub.analyze_latex`) and
  REST API (`parsub-api`) with sandboxed paths and `POST /run`.

### Mathematics
- Special-function notation: `{}_pF_q(a; b; z)`, Pochhammer `(a)_n`, Laguerre/Gegenbauer/Jacobi
  polynomials, Bessel functions `J_\nu(x)`, indexed functions `w_{\alpha}(z)`, primes `w''(z)`.
- The document's own definitions are applied: function definitions are substituted where the
  function is used, parameter definitions give consistent values, `i = \sqrt{-1}` is honoured.
- Identities, repeated definitions of a function and differential equations are verified
  numerically, with a verdict, the agreeing points and where they disagree.
- Validated on the example paper: 19 of 22 identities confirmed, two misprints found
  (see the [validation report](validation.md)).

### Project
- Documentation and website at https://psubrat29.github.io/parsub/
- Automated tests on Python 3.9, 3.11 and 3.13; automated website checks; PyPI releases with
  Trusted Publishing and a post-upload installation test.

## 0.1.0 — June 2026

Initial prototype, published as a GitHub tag only (not on PyPI). Its parser did not extract any
expressions and the generated code did not run; 0.2.0 replaces it completely.
