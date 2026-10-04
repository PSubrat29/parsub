"""
Integration tests: the Python API, the command-line interface and the REST API.
"""

import json
import os
import shutil
import tempfile
import unittest
import inspect
from pathlib import Path

from fastapi.testclient import TestClient
from typer.testing import CliRunner

import parsub
from parsub.api.main import app as api_app
from parsub.cli.main import app as cli_app
from parsub.core.pipeline import analyze_latex, read_run_summary, run_generated_code

EXAMPLES = Path(__file__).resolve().parent.parent / "examples"
PROJECTILE = r"""
We aim to compute the trajectory of a projectile with $g = 9.81$.
\begin{equation} y = x \tan(\theta) - \frac{g x^2}{2 v_0^2 \cos^2(\theta)} \end{equation}
We want to find the maximum range.
\begin{equation} R = \frac{v_0^2 \sin(2\theta)}{g} \end{equation}
"""


class TempDirTestCase(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="parsub_it_")

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)


class TestPipeline(TempDirTestCase):
    def test_version(self):
        self.assertRegex(parsub.__version__, r"^\d+\.\d+\.\d+$")

    def test_analyze_and_run(self):
        result = analyze_latex(PROJECTILE, self.test_dir, source_name="projectile")
        self.assertEqual(len(result.tasks), 2)
        self.assertTrue(os.path.isfile(result.code_path))
        self.assertTrue(os.path.isfile(result.poster_path))
        with open(result.poster_path, encoding="utf-8") as handle:
            poster = handle.read()
        self.assertIn(r"\usepackage[paperwidth=841mm,paperheight=1189mm,margin=22mm]{geometry}", poster)
        self.assertIn(r"\documentclass{article}", poster)
        with open(result.analysis_path) as handle:
            analysis = json.load(handle)
        self.assertEqual(analysis["assignments"], {"g": 9.81})
        self.assertEqual(len(analysis["tasks"]), 2)
        self.assertEqual(analysis["generated_poster"], "generated_poster.tex")

        process = run_generated_code(result.code_path, timeout=300)
        self.assertEqual(process.returncode, 0, process.stdout + process.stderr)
        summary = read_run_summary(self.test_dir)
        self.assertEqual(summary["failed"], 0)
        with open(os.path.join(self.test_dir, "data", "task_2_optimization.json")) as handle:
            optimum = json.load(handle)
        self.assertAlmostEqual(optimum["maximum"]["point"]["theta"], 0.785398, places=4)
        self.assertAlmostEqual(optimum["maximum"]["value"], 100 / 9.81, places=6)

    def test_analyze_latex_file(self):
        code_path = parsub.analyze_latex_file(str(EXAMPLES / "projectile.tex"), self.test_dir)
        self.assertTrue(code_path.endswith("generated_computation.py"))

    def test_sample_paper_identities(self):
        """The example paper: every identity checks out except the two misprinted ones."""
        result = analyze_latex((EXAMPLES / "sample.tex").read_text(encoding="utf-8"), self.test_dir)
        process = run_generated_code(result.code_path, timeout=1200)
        self.assertEqual(process.returncode, 0, process.stdout[-3000:] + process.stderr[-3000:])
        summary = read_run_summary(self.test_dir)
        verdicts = {}
        for record, task in zip(summary["tasks"], result.tasks):
            if task["goal_type"] == "verify":
                label = task["source_label"] or "inline"
                verdicts.setdefault(label, []).append(record["summary"]["identity_holds_numerically"])
        failing = {label for label, values in verdicts.items() if not all(values)}
        # (6): Kummer's first formula is misprinted; (22): L^(theta-1) should be L^(theta);
        # inline: w_alpha(0) = 0 holds only for alpha > 0 (it fails at alpha = 0).
        self.assertEqual(failing, {"6", "22", "inline"})
        for label in ("1", "3", "7", "8", "10", "13", "14", "16", "17", "18", "19", "20", "21", "23", "24", "25", "b"):
            self.assertTrue(all(verdicts[label]), label)

    def test_no_math_gives_warning(self):
        result = analyze_latex("Just prose, no mathematics.", self.test_dir)
        self.assertEqual(result.tasks, [])
        self.assertTrue(result.warnings)

    def test_30000_word_latex_document(self):
        source = ("word " * 30000) + r" We plot $y = \sin(x)$."
        result = analyze_latex(source, self.test_dir)
        self.assertGreaterEqual(len(source.split()), 30000)
        self.assertEqual(result.summary()["expressions_found"], 1)
        self.assertEqual(result.tasks[0]["goal_type"], "plot")

    def test_execution_timeout_is_opt_in(self):
        self.assertIsNone(inspect.signature(run_generated_code).parameters["timeout"].default)


class TestCLI(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.runner = CliRunner()

    def test_version(self):
        for args in (["--version"], ["version"]):
            result = self.runner.invoke(cli_app, args)
            self.assertEqual(result.exit_code, 0)
            self.assertIn(parsub.__version__, result.output)

    def test_analyze_then_run(self):
        out = os.path.join(self.test_dir, "results")
        result = self.runner.invoke(cli_app, ["analyze", str(EXAMPLES / "projectile.tex"), "-o", out])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertIn("Computation tasks", result.output)
        code = os.path.join(out, "generated_computation.py")
        self.assertTrue(os.path.isfile(code))
        self.assertTrue(os.path.isfile(os.path.join(out, "generated_poster.tex")))
        self.assertIn("A0 poster (LaTeX)", result.output)

        # Relative paths must work from any working directory
        cwd = os.getcwd()
        os.chdir(self.test_dir)
        try:
            result = self.runner.invoke(cli_app, ["run", "results/generated_computation.py"])
        finally:
            os.chdir(cwd)
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue(os.path.isfile(os.path.join(out, "data", "summary.json")))
        self.assertTrue(os.listdir(os.path.join(out, "plots")))

    def test_analyze_missing_file(self):
        result = self.runner.invoke(cli_app, ["analyze", os.path.join(self.test_dir, "missing.tex")])
        self.assertEqual(result.exit_code, 1)
        self.assertIn("not found", result.output)

    def test_run_missing_file(self):
        result = self.runner.invoke(cli_app, ["run", os.path.join(self.test_dir, "missing.py")])
        self.assertEqual(result.exit_code, 1)

    def test_demo(self):
        out = os.path.join(self.test_dir, "demo")
        result = self.runner.invoke(cli_app, ["demo", "-o", out, "--run"])
        self.assertEqual(result.exit_code, 0, result.output)
        self.assertTrue(os.path.isfile(os.path.join(out, "data", "summary.json")))


class TestAPI(TempDirTestCase):
    def setUp(self):
        super().setUp()
        self.root = os.path.join(self.test_dir, "output")
        os.environ["PARSUB_OUTPUT_ROOT"] = self.root
        self.client = TestClient(api_app)

    def tearDown(self):
        os.environ.pop("PARSUB_OUTPUT_ROOT", None)
        super().tearDown()

    def test_health_and_root(self):
        self.assertEqual(self.client.get("/health").json()["status"], "healthy")
        response = self.client.get("/", follow_redirects=False)
        self.assertEqual(response.status_code, 307)
        self.assertEqual(response.headers["location"], "/docs")

    def test_analyze_run_download(self):
        response = self.client.post("/analyze", json={"latex_source": PROJECTILE, "output_dir": "./api_results"})
        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["tasks_generated"], 2)
        self.assertEqual(body["generated_code_path"], "api_results/generated_computation.py")
        self.assertEqual(body["poster_path"], "api_results/generated_poster.tex")
        self.assertTrue(os.path.isfile(os.path.join(self.root, "api_results", "generated_computation.py")))
        self.assertTrue(os.path.isfile(os.path.join(self.root, body["poster_path"])))

        response = self.client.get("/execute/" + body["generated_code_path"])
        self.assertEqual(response.status_code, 200)
        self.assertIn("parsub run", response.json()["instructions"])

        response = self.client.post("/run", json={"code_path": body["generated_code_path"]})
        self.assertEqual(response.status_code, 200, response.text)
        run = response.json()
        self.assertTrue(run["success"], run)
        self.assertEqual(run["tasks_failed"], 0)
        plot = next(path for path in run["output_files"] if path.endswith(".png"))
        response = self.client.get("/download/" + plot)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "image/png")
        poster_response = self.client.get("/download/" + body["poster_path"])
        self.assertEqual(poster_response.status_code, 200)
        self.assertIn(r"\documentclass{article}", poster_response.text)
        # the root directory name may be used as a prefix
        self.assertEqual(self.client.get("/download/output/" + plot).status_code, 200)

    def test_upload(self):
        files = {"file": ("projectile.tex", PROJECTILE.encode("utf-8"), "text/plain")}
        response = self.client.post("/upload", files=files, data={"output_dir": "uploads"})
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["generated_code_path"], "uploads/generated_computation.py")

    def test_upload_rejects_non_latex(self):
        files = {"file": ("notes.txt", b"$x$", "text/plain")}
        self.assertEqual(self.client.post("/upload", files=files).status_code, 400)

    def test_path_traversal_is_rejected(self):
        response = self.client.post("/analyze", json={"latex_source": "$x+1$", "output_dir": "../escape"})
        self.assertEqual(response.status_code, 403)
        self.assertEqual(self.client.post("/analyze", json={"latex_source": "$x+1$", "output_dir": "/tmp/x"}).status_code, 403)
        self.assertIn(self.client.get("/download/..%2F..%2Fetc%2Fpasswd").status_code, (403, 404))
        self.assertEqual(self.client.get("/download/missing.png").status_code, 404)

    def test_run_rejects_arbitrary_scripts(self):
        os.makedirs(self.root, exist_ok=True)
        with open(os.path.join(self.root, "evil.py"), "w") as handle:
            handle.write("print('hi')\n")
        response = self.client.post("/run", json={"code_path": "evil.py"})
        self.assertEqual(response.status_code, 400)


if __name__ == "__main__":
    unittest.main()
