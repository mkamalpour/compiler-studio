"""Portable language profiles: regex token rules plus an editable LALR grammar."""

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path


def _unique_fields(pairs):
    result = {}
    for name, value in pairs:
        if name in result:
            raise ValueError(f'Duplicate JSON profile field: {name}')
        result[name] = value
    return result


@dataclass(frozen=True)
class Rule:
    name: str
    pattern: str
    priority: int = 0
    channel: str = "token"
    label: str = ""


@dataclass(frozen=True)
class Profile:
    name: str
    rules: tuple[Rule, ...]
    grammar: str
    context_checks: bool = False
    version: int = 1

    def to_dict(self):
        data = asdict(self)
        data["rules"] = list(data["rules"])
        return data

    def to_json(self):
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or type(data.get("version")) is not int or data.get("version") != 1:
            raise ValueError("Expected a version 1 language profile.")
        if set(data) - {"name", "rules", "grammar", "context_checks", "version"}:
            raise ValueError("Unknown profile fields.")
        if not isinstance(data.get("name"), str) or not data["name"].strip():
            raise ValueError("Profile name must be nonempty text.")
        if not isinstance(data.get("grammar"), str):
            raise ValueError("Grammar must be text.")
        if type(data.get("context_checks", False)) is not bool:
            raise ValueError("Context checks must be true or false.")
        raw = data.get("rules")
        if not isinstance(raw, list) or not 1 <= len(raw) <= 256:
            raise ValueError("A profile needs 1–256 token rules.")
        rules = []
        names = set()
        for item in raw:
            if not isinstance(item, dict):
                raise ValueError("Each token rule must be an object.")
            try:
                rule = Rule(**item)
            except TypeError as exc:
                raise ValueError("Invalid token rule fields.") from exc
            if not isinstance(rule.name, str) or not re.fullmatch(r"[A-Z][A-Z0-9_]*", rule.name):
                raise ValueError("Token names use uppercase letters, digits and underscores.")
            if rule.name in names:
                raise ValueError(f"Duplicate token name: {rule.name}")
            names.add(rule.name)
            if not isinstance(rule.pattern, str) or not 1 <= len(rule.pattern) <= 4096:
                raise ValueError(f"{rule.name}: pattern must contain 1–4096 characters.")
            if type(rule.priority) is not int or not -100 <= rule.priority <= 100:
                raise ValueError(f"{rule.name}: priority must be an integer from -100 to 100.")
            if not isinstance(rule.channel, str) or rule.channel not in {"token", "skip", "comment", "error"}:
                raise ValueError(f"{rule.name}: invalid channel.")
            if not isinstance(rule.label, str):
                raise ValueError(f"{rule.name}: label must be text.")
            try:
                pattern = re.compile(rule.pattern)
            except (re.error, OverflowError, RecursionError) as exc:
                raise ValueError(f"{rule.name}: {exc}") from exc
            if pattern.match(""):
                raise ValueError(f"{rule.name}: patterns must consume at least one character.")
            rules.append(rule)
        if len(data["grammar"]) > 100_000:
            raise ValueError("Grammar exceeds 100,000 characters.")
        # Profiles are self-contained; loading one must not read arbitrary files.
        if re.search(r"(?m)^\s*%", data["grammar"]):
            raise ValueError("Grammar directives are disabled. Define tokens in the rule table.")
        return cls(data["name"], tuple(rules), data["grammar"], data.get("context_checks", False))

    @classmethod
    def load(cls, path):
        if Path(path).stat().st_size > 1_000_000:
            raise ValueError("Profile exceeds 1 MB.")
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8-sig"), object_pairs_hook=_unique_fields))


RICEPY_GRAMMAR = """start: statement*
?statement: declaration SEMI
          | assignment SEMI
          | call_assignment SEMI
          | call SEMI                    -> call_statement
          | function_definition
          | class_definition
          | if_statement
          | while_statement
          | RETURN expr? SEMI            -> return_statement
          | BREAK SEMI                   -> break_statement
          | CONTINUE SEMI                -> continue_statement
          | block
          | SEMI                         -> empty_statement
declaration: modifier? data_type IDENT array_size? initializer?
modifier: GLOBAL | CONST
data_type: (INT | DOUBLE | STRING | BOOL) STAR*
return_type: data_type | VOID
array_size: LBRACKET expr RBRACKET
initializer: ASSIGN expr
assignment: target ASSIGN expr
target: IDENT (LBRACKET expr RBRACKET)?
call_assignment: IDENT CALL_ASSIGN call
function_definition: return_type FUNCTION IDENT LPAR parameters? RPAR block
parameters: parameter (COMMA parameter)*
parameter: IDENT COLON data_type
class_definition: CLASS IDENT BEGIN class_member* END
?class_member: declaration SEMI | function_definition
block: LBRACE statement* RBRACE
if_statement: IF LPAR expr RPAR block elif_clause* else_clause? SEMI
elif_clause: ELIF LPAR expr RPAR block
else_clause: ELSE block
while_statement: WHILE LPAR expr RPAR block SEMI
?expr: logical_or
?logical_or: logical_or OR logical_and    -> binary
           | logical_and
?logical_and: logical_and AND equality    -> binary
            | equality
?equality: equality (EQ | NE) comparison  -> binary
         | comparison
?comparison: comparison (LT | GT | LE | GE) sum -> binary
           | sum
?sum: sum (PLUS | MINUS) product          -> binary
    | product
?product: product (STAR | SLASH | MOD) unary -> binary
        | unary
?unary: (NOT | MINUS) unary               -> unary
      | atom
?atom: INTEGER | FLOAT | HEX | TEXT | TRUE | FALSE | NULL
     | IDENT LBRACKET expr RBRACKET      -> index
     | IDENT DOT IDENT                  -> member
     | call
     | IDENT                            -> identifier
     | LPAR expr RPAR                    -> grouped
call: IDENT LPAR arguments? RPAR
arguments: expr (COMMA expr)*
"""


def ricepy_profile():
    rules = [
        Rule("SPACE", r"[ \t\r\n]+", channel="skip"),
        Rule("COMMENT", r'"""[\s\S]*?"""', 30, "comment", "multi-line comment"),
        Rule("UNCLOSED_COMMENT", r'"""(?:(?!""")[\s\S])*\Z', 30, "error", "Unclosed multi-line comment"),
        Rule("LINE_COMMENT", r"#[^\r\n]*", 20, "comment", "single-line comment"),
        Rule("TEXT", r'"(?:[^"\\\r\n]|\\[^"\r\n])*"', 10, label="string literal"),
        Rule("BAD_TEXT", r'"[^\r\n]*', -1, "error", "Invalid string: close quotes on the same line; embedded quotes are forbidden"),
        Rule("BAD_NUMBER", r"0[xX](?:[0-9A-Fa-f]*[G-Zg-z_][A-Za-z0-9_]*|(?=[^A-Za-z0-9_]|$))|(?!(?:0[xX]))[0-9]+[A-Za-z_][A-Za-z0-9_]*|[0-9]+\.(?![0-9])|\.[0-9]+|[0-9]+\.[0-9]+[A-Za-z_][A-Za-z0-9_]*", 15, "error", "Malformed number or identifier starting with a digit"),
        Rule("BAD_IDENT", r"_[A-Za-z0-9_]*", 5, "error", "Identifiers cannot start with underscore"),
        Rule("HEX", r"0[xX][0-9a-fA-F]+", 3, label="hexadecimal literal"),
        Rule("FLOAT", r"[0-9]+\.[0-9]+", 3, label="double literal"),
        Rule("INTEGER", r"[0-9]+", 1, label="integer literal"),
        Rule("IDENT", r"[A-Za-z][A-Za-z0-9_]*", label="identifier"),
    ]
    keywords = "string int double bool void break continue class derives return null self for while if else elif begin end global const function true false".split()
    for word in keywords:
        rules.append(Rule(word.upper(), word + r"(?![A-Za-z0-9_])", 5,
                          label="boolean literal" if word in {"true", "false"} else "keyword"))
    operators = {
        "CALL_ASSIGN": ":=", "COLON": ":", "EQ": "==", "NE": "!=", "LE": "<=", "GE": ">=",
        "AND": "&&", "OR": "||", "LBRACKET": "[", "RBRACKET": "]", "LPAR": "(", "RPAR": ")",
        "LBRACE": "{", "RBRACE": "}", "PLUS": "+", "MINUS": "-", "STAR": "*", "SLASH": "/",
        "MOD": "%", "LT": "<", "GT": ">", "ASSIGN": "=", "NOT": "!", "SEMI": ";", "DOT": ".", "COMMA": ",", "CARET": "^",
    }
    labels = {"LPAR": "left parentheses", "RPAR": "right parentheses", "LT": "lower than", "GT": "greater than",
              "LE": "lower equal", "GE": "greater equal", "LBRACKET": "left bracket", "RBRACKET": "right bracket",
              "LBRACE": "left curly bracket", "RBRACE": "right curly bracket", "ASSIGN": "equal", "EQ": "check equal",
              "NE": "not equal", "STAR": "multiply", "SLASH": "divide", "MOD": "modulo", "SEMI": "semicolon"}
    for name, value in operators.items():
        rules.append(Rule(name, re.escape(value), 2, label=labels.get(name, name.lower().replace("_", " "))))
    return Profile("RicePy++ · Assignments 1 + 2", tuple(rules), RICEPY_GRAMMAR, True)


def calculator_profile():
    return Profile("MiniCalc · Custom language example", (
        Rule("SPACE", r"\s+", channel="skip"),
        Rule("NUMBER", r"[0-9]+(?:\.[0-9]+)?"),
        Rule("PLUS", r"\+"), Rule("STAR", r"\*"),
        Rule("LPAR", r"\("), Rule("RPAR", r"\)"),
    ), """start: sum
?sum: sum PLUS product -> addition
    | product
?product: product STAR atom -> multiplication
        | atom
?atom: NUMBER -> number
     | LPAR sum RPAR -> grouped
""")
