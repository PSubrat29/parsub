# Changelog

All notable changes to ParSub. Versions follow [Semantic Versioning](https://semver.org/).

## 0.2.2 - 5 October 2026 

([PyPI page](https://pypi.org/project/parsub/0.2.2/),
[GitHub release](https://github.com/PSubrat29/parsub/releases/tag/v0.2.2)).
- Generate an editable A0 portrait poster in LaTeX from each analyzed manuscript,
  with source metadata, selected equations, analysis summaries, and embedded model curves.
- Add spectral-analysis tasks using a Hann-windowed, one-sided FFT amplitude spectrum.
- Improve plot color cycling, mathematical legends and 400-DPI output.
- Make execution unlimited by default; overall and per-task time limits remain opt-in.
- Add responsive sidebar navigation to the documentation website.
- Document the 30,000-word LaTeX input capacity and scientific-package integration boundaries.

## 0.2.1 — 2 October 2026

Packaging and documentation release; ParSub's code is unchanged from 0.2.0
([PyPI page](https://pypi.org/project/parsub/0.2.1/),
[GitHub release](https://github.com/PSubrat29/parsub/releases/tag/v0.2.1)).

- **Docker image** of the REST API: `ghcr.io/psubrat29/parsub` for amd64 and arm64, built, tested and
  published by GitHub Actions; tags `0.2.1`, `0.2` and `latest`.
- `compose.yaml` to start the API with `docker compose up -d`, and a new [Docker page](docker.md).
- The PyPI page now shows the current README, with links to the website, the Docker image and the
  changelog.
- Release workflow: TestPyPI rehearsals can be repeated (unique `.devN` versions), PyPI uploads
  check the version first, and every upload is followed by installing it from the index.

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
