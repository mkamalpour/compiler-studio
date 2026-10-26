import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from compiler_studio.profiles import Profile, Rule, calculator_profile
from compiler_studio.worker import run_isolated, AnalysisWorker
import time

ROOT = Path(__file__).resolve().parent.parent


class WorkflowTests(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, "-m", "compiler_studio", *map(str, args)],
                              cwd=ROOT, capture_output=True, text=True, encoding="utf-8", timeout=25,
                              env={**os.environ, "PYTHONIOENCODING": "utf-8"})

    def test_cli_original_fixture_and_json(self):
        result = self.cli("examples/assignment2.ricepy", "--json", "-")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["ok"])

    def test_cli_invalid_source_and_missing_file(self):
        self.assertEqual(self.cli("examples/invalid.ricepy").returncode, 1)
        missing = self.cli("missing-file.ricepy")
        self.assertEqual(missing.returncode, 2)
        self.assertNotIn("Traceback", missing.stderr)

    def test_cli_explanation_preserves_json_and_failure_status(self):
        result = self.cli('examples/invalid.ricepy', '--explain')
        self.assertEqual(result.returncode, 1)
        self.assertIn('^', result.stderr)
        self.assertIn('Next:', result.stderr)
        machine = self.cli('examples/invalid.ricepy', '--explain', '--json', '-')
        self.assertEqual(machine.returncode, 1)
        self.assertFalse(json.loads(machine.stdout)['ok'])

    def test_cli_export_never_overwrites_input_or_existing_report(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "source.src"
            source.write_text("1 + 2", encoding="utf-8")
            result = self.cli(source, "--preset", "calculator", "--json", source)
            self.assertEqual(result.returncode, 2)
            self.assertEqual(source.read_text(), "1 + 2")
            report = Path(directory) / "report.json"
            self.assertEqual(self.cli(source, "--preset", "calculator", "--json", report).returncode, 0)
            self.assertTrue(json.loads(report.read_text())["ok"])
            self.assertEqual(self.cli(source, "--preset", "calculator", "--json", report).returncode, 2)

    def test_cli_profile_roundtrip_and_lexical_only(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "language.json"
            self.assertEqual(self.cli("--preset", "calculator", "--save-preset", path).returncode, 0)
            self.assertEqual(self.cli("--profile", path, "--mode", "validate").returncode, 0)
        self.assertEqual(self.cli("examples/lexical.ricepy", "--mode", "lexer").returncode, 0)

    def test_worker_success_and_hard_timeout(self):
        report = run_isolated("1 + 2 * 3", calculator_profile())
        self.assertTrue(report["ok"])
        pathological = Profile("Slow regex", (Rule("BAD", r"(a+)+$"),), "start: BAD")
        with self.assertRaises(TimeoutError):
            run_isolated("a" * 35 + "!", pathological, "lexer", timeout=0.7)

    def test_cli_stdin_and_utf8_bom(self):
        result = subprocess.run([sys.executable, "-m", "compiler_studio", "-", "--preset", "calculator", "--json", "-"],
                                input="1 + 2 * 3", capture_output=True, text=True, encoding="utf-8", cwd=ROOT, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertTrue(json.loads(result.stdout)["ok"])
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "bom.ricepy"
            source.write_text('string message = "سلام";', encoding="utf-8-sig")
            self.assertEqual(self.cli(source).returncode, 0)

    def test_reusable_worker_cache_timeout_and_restart(self):
        worker = AnalysisWorker()
        def wait(job):
            while True:
                result = job.poll()
                if result is not None:
                    return result
                time.sleep(0.01)
        try:
            first = worker.submit("1 + 2", calculator_profile())
            process = first.process
            self.assertTrue(wait(first)["ok"])
            second = worker.submit("3 * 4", calculator_profile())
            self.assertIs(second.process, process)
            self.assertTrue(wait(second)["ok"])
            slow = Profile("Slow", (Rule("BAD", r"(a+)+$"),), "start: BAD")
            with self.assertRaises(TimeoutError):
                wait(worker.submit("a" * 35 + "!", slow, "lexer", timeout=0.3))
            self.assertFalse(process.is_alive())
            restarted = worker.submit("5 + 6", calculator_profile())
            self.assertIsNot(restarted.process, process)
            self.assertTrue(wait(restarted)["ok"])
        finally:
            worker.close()


if __name__ == "__main__":
    unittest.main()
