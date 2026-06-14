# Contributing to ParSub

Thank you for considering contributing to ParSub! We welcome contributions from the community.

## 📋 How to Contribute

There are many ways to contribute to ParSub:

1. **Report bugs** - Open an issue describing the problem
2. **Suggest features** - Share your ideas for new functionality
3. **Improve documentation** - Help make our docs clearer and more comprehensive
4. **Fix issues** - Pick up an open issue and submit a pull request
5. **Add examples** - Contribute sample LaTeX files that demonstrate ParSub's capabilities

## 🛠️ Development Setup

1. Fork the repository on GitHub
2. Clone your fork locally:
   ```bash
   git clone https://github.com/yourusername/parsub.git
   cd parsub
   ```

3. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

4. Install development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

5. Install pre-commit hooks (optional but recommended):
   ```bash
   pre-commit install
   ```

## 📝 Coding Standards

- Follow [PEP 8](https://pep8.org/) for Python code style
- Use type hints for function parameters and return values
- Write docstrings for all public classes and methods
- Keep functions focused and under 50 lines when possible
- Add unit tests for new functionality

## 🧪 Testing

Run the test suite:
```bash
pytest
```

Run tests with coverage:
```bash
pytest --cov=parsub tests/
```

## 🔄 Pull Request Process

1. Create a new branch for your feature or fix:
   ```bash
   git checkout -b feature/amazing-feature
   ```

2. Make your changes, following the coding standards above

3. Add or update tests as needed

4. Ensure all tests pass:
   ```bash
   pytest
   ```

5. Commit your changes:
   ```bash
   git commit -m "Add amazing feature"
   ```

6. Push to your fork:
   ```bash
   git push origin feature/amazing-feature
   ```

7. Open a pull request against the `main` branch

## 🐛 Bug Reports

When reporting a bug, please include:
- ParSub version (`parsub --version`)
- Operating system and Python version
- LaTeX source that triggers the bug (if applicable)
- Expected behavior vs. actual behavior
- Steps to reproduce the issue
- Any error messages or tracebacks

## 💡 Feature Requests

When suggesting a feature, please consider:
- Is this related to a problem you're experiencing?
- How would this feature improve ParSub?
- Are there alternative approaches or workarounds?
- Any relevant examples or use cases?

## 📚 Documentation

Help us improve our documentation! Good documentation makes ParSub accessible to more users.

- User guides and tutorials
- API documentation
- Code comments and docstrings
- Examples and use cases

## 🙏 Recognition

Contributors will be recognized in:
- The README.md contributors section
- Release notes
- GitHub contributors list

## 📄 License

By contributing to ParSub, you agree that your contributions will be licensed under the MIT License.

---

Happy coding! 🚀