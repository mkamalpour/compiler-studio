import json
from pathlib import Path
import unittest
import random
from unittest.mock import patch

from compiler_studio.engine import analyze, compile_profile, MAX_SOURCE
from compiler_studio.engine import ScannerPlan
from compiler_studio.profiles import Profile, Rule, ricepy_profile, calculator_profile
from compiler_studio.samples import ricepy_sample, calculator_sample

ROOT = Path(__file__).resolve().parent.parent


class EngineTests(unittest.TestCase):
    def setUp(self):
        self.profile = ricepy_profile()

    def analyze(self, text, mode="pipeline"):
        return analyze(text, self.profile, mode)

    def test_original_assignment_two_and_generated_programs(self):
        source = (ROOT / "examples/assignment2.ricepy").read_text(encoding="utf-8")
        self.assertTrue(self.analyze(source)["ok"])
        for seed in range(30):
            with self.subTest(seed=seed):
                report = self.analyze(ricepy_sample(seed))
                self.assertTrue(report["ok"], report["diagnostics"])

    def test_all_assignment_one_tokens_and_longest_operator(self):
        result = self.analyze((ROOT / "examples/lexical.ricepy").read_text(encoding="utf-8"), "lexer")
        self.assertTrue(result["ok"], result["diagnostics"])
        self.assertIn("CARET", [t["kind"] for t in result["tokens"]])
        self.assertEqual([t["kind"] for t in self.analyze("<= < >= > == = != ! := :", "lexer")["tokens"]],
                         ["LE", "LT", "GE", "GT", "EQ", "ASSIGN", "NE", "NOT", "CALL_ASSIGN", "COLON"])

    def test_keywords_do_not_split_identifiers(self):
        report = self.analyze("intValue trueValue globalCount int true", "lexer")
        self.assertEqual([t["kind"] for t in report["tokens"]], ["IDENT", "IDENT", "IDENT", "INT", "TRUE"])

    def test_valid_numeric_literals(self):
        for value in ["0", "022", "123", "4.1", "0x1", "0Xaaff22", "0x0", "0xDEAD"]:
            with self.subTest(value=value):
                report = self.analyze(value, "lexer")
                self.assertTrue(report["ok"], report["diagnostics"])
                self.assertEqual(len(report["tokens"]), 1)

    def test_malformed_input_never_becomes_success(self):
        for value in [".2", "2.", "0x", "0xZZ", "0x12G", "22hello", "2.3abc", "_name", "@", "é", "۱۲", '"unterminated', '"bad\\"quote"', '"""unfinished']:
            with self.subTest(value=value):
                report = self.analyze(value, "lexer")
                self.assertFalse(report["ok"])
                self.assertTrue(report["diagnostics"])

    def test_comments_strings_locations_and_line_endings(self):
        for newline in ["\n", "\r\n", "\r"]:
            source = '# heading' + newline + '"""one' + newline + 'two"""' + newline + 'int x = 1;'
            report = self.analyze(source)
            self.assertTrue(report["ok"], report["diagnostics"])
            token = next(t for t in report["tokens"] if t["kind"] == "INT")
            self.assertEqual((token["line"], token["column"]), (4, 1))
            self.assertEqual(source[token["offset"]:token["end"]], "int")
        self.assertTrue(self.analyze('string text = "hello # world";')["ok"])

    def test_unclosed_comment_reports_opening_position(self):
        report = self.analyze("int x;\n  \"\"\"\nmissing")
        self.assertEqual((report["diagnostics"][0]["line"], report["diagnostics"][0]["column"]), (2, 3))
        self.assertIsNone(report["tree"])

    def test_syntax_errors_expected_tokens_and_eof(self):
        for source in ["int x = ;", "int x", "while (true) {}", "if (true) {}", "void x;", "int x[2][3];", "x := 1;", "x + 2;", "class X begin x = 2; end"]:
            with self.subTest(source=source):
                report = self.analyze(source)
                self.assertFalse(report["ok"])
                self.assertEqual(report["diagnostics"][0]["stage"], "parser")
                self.assertIn("Expected:", report["diagnostics"][0]["message"])
        eof = self.analyze("int x\n")["diagnostics"][0]
        self.assertEqual((eof["line"], eof["column"], eof["offset"]), (2, 1, 6))

    def test_empty_program_and_blocks(self):
        for source in ["", "# comment", "{}", "while (true) {};", "if (true) {} else {};", "void function f() {}", "class X begin end"]:
            self.assertTrue(self.analyze(source)["ok"], source)

    def test_context_rules_and_function_scope(self):
        for source in ["break;", "continue;", "return;", "while (true) { void function f() { break; } };", "while (true) { class X begin void function f() { continue; } end }; "]:
            with self.subTest(source=source):
                report = self.analyze(source)
                self.assertFalse(report["ok"])
                self.assertEqual(report["diagnostics"][0]["stage"], "context")
        self.assertTrue(self.analyze("void function f() { while (true) { if (false) { break; } else { continue; }; }; return; }")["ok"])

    def test_precedence_and_associativity_are_structural(self):
        tree = analyze("1 + 2 * 3", calculator_profile())["tree"]
        addition = tree["children"][0]
        self.assertEqual(addition["kind"], "addition")
        self.assertEqual(addition["children"][2]["kind"], "multiplication")
        tree = analyze("1 + 2 + 3", calculator_profile())["tree"]["children"][0]
        self.assertEqual(tree["children"][0]["kind"], "addition")

    def test_user_can_change_lexer_and_grammar_without_python_changes(self):
        data = calculator_profile().to_dict()
        data["name"] = "My language"
        data["rules"].append(dict(name="MINUS", pattern=r"\-", channel="token", priority=0))
        data["grammar"] = data["grammar"].replace("| product\n", "| sum MINUS product -> subtraction\n    | product\n", 1)
        custom = Profile.from_dict(data)
        result = analyze("9 - 2 * 3", custom)
        self.assertTrue(result["ok"], result["diagnostics"])
        self.assertEqual(result["tree"]["children"][0]["kind"], "subtraction")
        self.assertFalse(analyze("9 - 2", calculator_profile())["ok"])

    def test_profile_round_trip_and_examples(self):
        for profile in [self.profile, calculator_profile()]:
            restored = Profile.from_dict(json.loads(profile.to_json()))
            self.assertEqual(restored, profile)
            self.assertTrue(analyze("", restored, "validate")["ok"])
        for seed in range(10):
            self.assertTrue(analyze(calculator_sample(seed), calculator_profile())["ok"])

    def test_bad_profile_and_grammar(self):
        for mutate in [lambda d: d.update(version=2), lambda d: d["rules"].append(d["rules"][0]),
                       lambda d: d["rules"][0].update(pattern="["), lambda d: d["rules"][0].update(pattern="a*"),
                       lambda d: d.update(grammar="%import some.private.file\nstart:"),
                       lambda d: d["rules"][0].update(priority=True)]:
            data = calculator_profile().to_dict()
            mutate(data)
            with self.assertRaises(ValueError):
                Profile.from_dict(data)
        for grammar in ["start: missing", 'start: "literal"', "start: start start | NUMBER"]:
            data = calculator_profile().to_dict()
            data["grammar"] = grammar
            report = analyze("1", Profile.from_dict(data))
            self.assertFalse(report["ok"])
            self.assertEqual(report["diagnostics"][0]["stage"], "configuration")

    def test_lexer_mode_is_independent_of_invalid_grammar(self):
        profile = Profile("Lexer", (Rule("IDENT", "[a-z]+"),), "start: missing")
        self.assertTrue(analyze("word", profile, "lexer")["ok"])
        self.assertFalse(analyze("word", profile)["ok"])

    def test_position_dependent_empty_rule_is_rejected_at_runtime(self):
        profile = Profile("Bad", (Rule("ZERO", r"(?=a)"),), "start: ZERO")
        report = analyze("a", profile, "lexer")
        self.assertFalse(report["ok"])
        self.assertEqual(report["diagnostics"][0]["code"], "C002")

    def test_resource_limits_and_large_flat_input(self):
        self.assertFalse(self.analyze(" " * (MAX_SOURCE + 1))["ok"])
        self.assertTrue(self.analyze("int x;\n" * 1500)["ok"])
        deep = analyze("+".join(["1"] * 180), calculator_profile())
        self.assertFalse(deep["ok"])
        self.assertEqual(deep["diagnostics"][0]["stage"], "limit")

    def test_offsets_and_tokens_cover_every_non_skipped_character(self):
        source = 'int x=1;\n# note\n@ "hello"'
        report = self.analyze(source, "lexer")
        last = 0
        for token in report["tokens"]:
            self.assertTrue(token["offset"] >= last)
            self.assertEqual(source[token["offset"]:token["end"]], token["value"])
            self.assertTrue(not source[last:token["offset"]].strip())
            last = token["end"]

    def test_optimized_scanner_matches_exhaustive_matching(self):
        rng = random.Random(7)
        alphabet = 'abc01_ +-*/:=<>!&|()[]{}.;#"\\\n\té'
        samples = [ricepy_sample(4), 'intValue := f(0xFF, 12.3);', '0x12G 2. _bad "oops']
        samples += ["".join(rng.choice(alphabet) for _ in range(100)) for _ in range(100)]
        for text in samples:
            optimized = self.analyze(text, "lexer")
            with patch.object(ScannerPlan, "candidates", lambda plan, char: plan.rules):
                exhaustive = self.analyze(text, "lexer")
            self.assertEqual(optimized["tokens"], exhaustive["tokens"])
            self.assertEqual(optimized["diagnostics"], exhaustive["diagnostics"])
        # Optional prefixes, alternatives, flags and backreferences must remain general.
        for pattern in [r"a?b", r"a*b", r"a{0,2}b", r"a|b", r"(?i)a", r"(a)\1", r"\w+", r"(?=a)"]:
            profile = Profile("Custom", (Rule("CUSTOM", pattern),), "start: CUSTOM")
            for text in ["a", "b", "aa", "A"]:
                optimized = analyze(text, profile, "lexer")
                with patch.object(ScannerPlan, "candidates", lambda plan, char: plan.rules):
                    exhaustive = analyze(text, profile, "lexer")
                self.assertEqual(optimized["tokens"], exhaustive["tokens"])
                self.assertEqual(optimized["diagnostics"], exhaustive["diagnostics"])

    def test_syntax_error_includes_structured_expected_tokens_and_hint(self):
        diagnostic = self.analyze("int value\n")["diagnostics"][0]
        self.assertIn("SEMI", diagnostic["expected"])
        self.assertIn("semicolon", diagnostic["hint"])

    def test_custom_grammar_context_alias_mismatch_reports_configuration_error(self):
        profile = Profile("Custom", (Rule("NUMBER", r"[0-9]+"),), "start: return_statement\nreturn_statement: NUMBER", True)
        report = analyze("5", profile)
        self.assertFalse(report["ok"])
        self.assertEqual(report["diagnostics"][0]["code"], "C003")


if __name__ == "__main__":
    unittest.main()
