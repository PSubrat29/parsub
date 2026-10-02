# Validation: the example paper

This page records what ParSub 0.2.0 does with
[`examples/sample.tex`](https://github.com/PSubrat29/parsub/blob/master/examples/sample.tex),
*A Note on Generalized Bessel Function*. The note has 25 numbered equations involving the
Gamma and Beta functions, hypergeometric functions, the generalized Bessel function w_α(z),
the Bessel-Clifford function and Laguerre polynomials.

```bash
parsub analyze examples/sample.tex -o results --run
```

## What is extracted

- 39 formulas are found. 38 are converted to SymPy; the only exception is the generic
  definition (4) of ₚFq, which is written with "…" and cannot be computed.
- `i = √−1` is recognised as the imaginary unit. Statements such as `b = 1` and `c = 1`
  become parameter values (they turn w_α into the classical Bessel function J_α).
  ϑ = α + (b+1)/2 is applied everywhere ϑ appears.
- Functions defined in the paper are substituted where they are used: π(x) = 1/Γ(x+1) in (11) and (16),
  C_ϑ in (14), (15) and (17), w_α in (8), (25) and (b), and M_{k,ϑ} in (b).

## Results

28 computations run in about 90 seconds, with no failures. Each check compares both sides at 20–100
points; "max. rel. difference" is the largest relative difference found.

| Eq. | What is checked | Verdict | Max. rel. difference |
|-----|-----------------|---------|----------------------|
| (1) | Γ(z) = ∫₀^∞ e^{−l} l^{z−1} dl | holds | 1.5e−08 |
| (2), (3) | the two definitions of B(ζ, η) agree | holds | 2.8e−16 |
| (5) | (ϖ)ₙ = Γ(ϖ+n)/Γ(ϖ) | holds | 5.2e−16 |
| (6) | Kummer's first transformation as printed | **does not hold** | 1.8 |
| (7) | Kummer's second transformation | holds | 3.3e−16 |
| (8)+(9) | the series (9) solves the differential equation (8) | holds | 3.2e−11 |
| — | w_α(0) = 0 | holds for α > 0 (fails at α = 0) | — |
| (9), (10) | both series for w_α(z) agree | holds | 1.6e−13 |
| (11), (13) | both series for C_ϑ(z) agree (after substituting (12)) | holds | 0 |
| (14) | C_{ϑ−1}(−cz²/4) series | holds | 0 |
| (11), (16) | C_ϑ(z) = π(ϑ) ₀F₁(−; ϑ+1; z) | holds | 5.0e−16 |
| (17) | C_{ϑ−1}(−cz²/4) = ₀F₁(−; ϑ; −cz²/4)/Γ(ϑ) | holds | 4.0e−14 |
| (9), (18) | hypergeometric form of w_α(z) | holds | 1.7e−13 |
| (19) | ₀F₁ written with ₁F₁ (with i = √−1) | holds | 5.6e−17 |
| (9), (20) | ₁F₁ form of w_α(z) | holds | 1.7e−13 |
| (21) | series of the Laguerre polynomial | holds | 3.3e−16 |
| (22) | generating relation as printed | **does not hold** | 0.25 |
| (23) | generating relation with ϑ − 1 | holds | 4.4e−16 |
| — | (ϑ)_k = Γ(ϑ+k)/Γ(ϑ) | holds | 4.6e−15 |
| (9), (24) | Laguerre form of w_α(z) | holds | 2.0e−13 |
| (25) | Laguerre generating function of w_α | holds | 5.8e−13 |
| (b) | the final result with M_{k,ϑ−1} | holds | 5.8e−13 |

Parameter values used: α = 0.5, b = 1, c = 1 (so ϑ = 1.5), ε = 0.1, ϱ = 1, t = 1 or
z = 1 when held fixed, and k = 1 in (21). Edit the `fixed` values in the generated script to test
others.

Plots are produced for B(ζ, η) as a surface, and for π(x), C_ϑ(z), M_{k,ϑ}(z) and w_α(z).
For c = 1, b = 1, α = ½ the computed w_α(z) agrees with SciPy's J_½(z) to 1.7e−13.

## Findings

**Equation (6).** As printed:

> ₁F₁(ε; ϱ; z) = e^z ₁F₁(ϱ − ε; ε; z)

This does not hold; with ε = 0.1, ϱ = 1 the two sides differ by about 61 at z = 1.
Kummer's first transformation is

> ₁F₁(ε; ϱ; z) = e^z ₁F₁(ϱ − ε; **ϱ**; **−z**)

which mpmath confirms to 30 digits.

**Equation (22).** As printed:

> ₀F₁(−; 1+ϑ; −zt) = e^{−t} Σ_k L_k^{(ϑ−1)}(z) t^k / (1+ϑ)_k

This does not hold; the two sides differ by 0.15–0.25 for t = 0.5–2. The known generating
relation has L_k^{(ϑ)}(z) instead of L_k^{(ϑ−1)}(z), and with that index it holds to 30
digits. Equation (23) follows from the corrected (22) by replacing ϑ with ϑ − 1, and (23) is correct.
So the error is confined to the printed (22).

**w_α(0) = 0.** This holds for Re α > 0. At α = 0 the first term of the series is
1/Γ((b+1)/2) ≠ 0.

## Reproducing the independent checks

```python
import mpmath as mp
mp.mp.dps = 30
eps, rho = mp.mpf("0.1"), mp.mpf(1)
for z in (-2, 1, 3):
    printed = mp.hyp1f1(eps, rho, z) - mp.e**z * mp.hyp1f1(rho - eps, eps, z)
    kummer = mp.hyp1f1(eps, rho, z) - mp.e**z * mp.hyp1f1(rho - eps, rho, -z)
    print(z, printed, kummer)          # printed form differs, Kummer's form is 0
```
