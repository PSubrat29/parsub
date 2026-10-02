---
title: ParSub Documentation
---

# ParSub Documentation

![ParSub Logo](logo.png)

**ParSub** reads the mathematics in a LaTeX document, works out what can be computed from it, and
writes a ready-to-run Python script that evaluates, plots, solves, optimizes, integrates,
differentiates or numerically verifies every formula it understands.

```
paper.tex ──parse──► expressions ──analyze──► tasks ──generate──► generated_computation.py ──run──► plots/ + data/
```

## Guides

- [User Guide](user_guide.md) – installation, command line, Python API, REST API, the generated
  script and troubleshooting
- [API Reference](api_reference.md) – modules, functions and data formats
- [Development Guide](development_guide.md) – project layout, tests, CI and releases
- [Validation report](validation.md) – the example paper checked equation by equation

## Quick start

```bash
pip install parsub

parsub demo --run                                  # built-in projectile-motion demo
parsub analyze paper.tex -o results --run
```

## Links

- [Source code on GitHub](https://github.com/PSubrat29/parsub)
- [Example LaTeX files](https://github.com/PSubrat29/parsub/tree/master/examples)
- [Issue tracker](https://github.com/PSubrat29/parsub/issues)
- [Contributing](https://github.com/PSubrat29/parsub/blob/master/CONTRIBUTING.md)
- [MIT License](https://github.com/PSubrat29/parsub/blob/master/LICENSE)
