import unittest

from compiler_studio.engine import analyze
from compiler_studio.example_library import STARTER, TOPICS, LEVELS, make_example
from compiler_studio.presentation import report_summary, token_group, explain_diagnostic
from compiler_studio.profiles import ricepy_profile, calculator_profile


class BeginnerTests(unittest.TestCase):
    def test_every_example_topic_and_difficulty_produces_valid_code(self):
        profile = ricepy_profile()
        self.assertTrue(analyze(STARTER, profile)["ok"])
        for topic in TOPICS:
            for level in LEVELS:
                for seed in range(5):
                    with self.subTest(topic=topic, level=level, seed=seed):
                        report = analyze(make_example("RicePy++", topic, level, seed), profile)
                        self.assertTrue(report["ok"], report["diagnostics"])
            variants = [make_example("RicePy++", topic, level, 1) for level in LEVELS]
            self.assertEqual(len(set(variants)), 3, topic)
        for level in LEVELS:
            for seed in range(5):
                self.assertTrue(analyze(make_example("MiniCalc", "Arithmetic", level, seed), calculator_profile())["ok"])

    def test_summary_never_says_a_skipped_or_failed_check_passed(self):
        profile = ricepy_profile()
        complete = analyze(STARTER, profile)
        self.assertEqual(report_summary(complete)["parser"], "Passed")
        lexical = analyze(STARTER, profile, "lexer")
        summary = report_summary(lexical)
        self.assertEqual(summary["lexer"], "Passed")
        self.assertEqual(summary["parser"], "Not checked")
        lexical_error = analyze("int _bad = .5;", profile)
        self.assertEqual(report_summary(lexical_error)["lexer"], "Needs fixing")
        self.assertEqual(report_summary(lexical_error)["parser"], "Not checked")
        syntax_error = analyze("int value", profile)
        self.assertEqual(report_summary(syntax_error)["lexer"], "Passed")
        self.assertEqual(report_summary(syntax_error)["parser"], "Needs fixing")
        validation = analyze("", profile, "validate")
        self.assertEqual(report_summary(validation)["parser"], "Not checked")
        self.assertIn("Language", report_summary(validation)["title"])

    def test_plain_explanations_preserve_technical_report_and_group_counts(self):
        report = analyze("int value", ricepy_profile())
        original = dict(report["diagnostics"][0])
        message, hint = explain_diagnostic(original, "int value")
        self.assertNotIn("Expected:", message)
        self.assertIn("semicolon", hint)
        self.assertEqual(report["diagnostics"][0], original)
        unknown = dict(kind="CUSTOM", label="My token", channel="token", value="text")
        self.assertEqual(token_group(unknown), "Other tokens")
        source = 'int x = 3; # comment\nstring text = "Hi";'
        tokens = analyze(source, ricepy_profile())["tokens"]
        groups = [token_group(token) for token in tokens]
        self.assertIn("Comments", groups)
        self.assertIn("Values", groups)
        self.assertEqual(len(groups), len(tokens))
