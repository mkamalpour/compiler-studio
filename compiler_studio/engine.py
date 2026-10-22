"""One token stream drives both the lexer view and the LALR parser."""

from bisect import bisect_right
from functools import lru_cache
import re
import time

from lark import Lark, Token, Tree
from lark.exceptions import GrammarError, UnexpectedToken, LarkError
from lark.lexer import Lexer as LarkLexer

from .profiles import Profile

MAX_SOURCE = 250_000
MAX_TOKENS = 40_000
MAX_TREE_DEPTH = 150


class TokenStreamLexer(LarkLexer):
    """Lark receives our already-scanned tokens through its interactive API."""

    def __init__(self, lexer_conf):
        pass

    def lex(self, data):
        raise RuntimeError("Use the shared scanner and interactive token stream.")


@lru_cache(maxsize=8)
def compile_profile(profile, parse=True):
    rules = tuple((rule, re.compile(rule.pattern)) for rule in profile.rules)
    parser = None
    if parse:
        declarations = "\n%declare " + " ".join(rule.name for rule in profile.rules)
        parser = Lark(profile.grammar + declarations, parser="lalr", lexer=TokenStreamLexer,
                      propagate_positions=True, maybe_placeholders=False, strict=True)
        # The scanner uses explicit named tokens. Inline literal terminals would
        # create a second, inconsistent token vocabulary.
        if parser.terminals:
            raise ValueError("Use named tokens from the token table in grammar rules, not inline literals or regexes.")
    return rules, parser


def analyze(source, profile, mode="pipeline"):
    """Run directly for trusted tests; UI/CLI use an interruptible worker process."""
    started = time.perf_counter()
    result = {"profile": profile.name, "mode": mode, "tokens": [], "tree": None,
              "diagnostics": [], "timings": {}, "ok": False, "source_length": len(source)}
    diagnostics = result["diagnostics"]

    def error(stage, code, message, offset=0, end=None, line=1, column=1):
        diagnostics.append(dict(stage=stage, code=code, message=message, offset=offset,
                                end=offset if end is None else end, line=line, column=column))

    def finish():
        result["ok"] = not diagnostics
        result["timings"]["total_ms"] = round((time.perf_counter() - started) * 1000, 3)
        return result

    if mode not in {"pipeline", "lexer", "validate"}:
        error("configuration", "C001", "Unknown analysis mode.")
        return finish()
    if len(source) > MAX_SOURCE:
        error("limit", "R001", f"Source exceeds {MAX_SOURCE:,} characters; split it into smaller files.")
        return finish()
    try:
        profile = Profile.from_dict(profile.to_dict())
        rules, parser = compile_profile(profile, mode != "lexer")
    except (ValueError, GrammarError, LarkError, re.error, RecursionError) as exc:
        error("configuration", "C001", str(exc))
        return finish()
    result["timings"]["grammar_ms"] = round((time.perf_counter() - started) * 1000, 3)
    if mode == "validate":
        return finish()

    line_starts = [0] + [m.end() for m in re.finditer(r"\r\n|\r|\n", source)]

    def location(offset):
        index = bisect_right(line_starts, offset) - 1
        return index + 1, offset - line_starts[index] + 1

    parser_tokens = []
    pos = 0
    lex_start = time.perf_counter()
    while pos < len(source):
        best_rule, best_match = None, None
        for rule, pattern in rules:
            match = pattern.match(source, pos)
            if match is not None:
                if match.end() == pos:
                    line, column = location(pos)
                    error("configuration", "C002", f"{rule.name} matched empty text at this position.", pos, pos, line, column)
                    return finish()
                # Priority, then longest match, then earlier row wins ties.
                if best_match is None or (rule.priority, match.end()) > (best_rule.priority, best_match.end()):
                    best_rule, best_match = rule, match
        end = best_match.end() if best_match else pos + 1
        line, column = location(pos)
        if best_rule is None:
            record = dict(kind="UNRECOGNIZED", label="Unrecognized character", value=source[pos:end],
                          line=line, column=column, offset=pos, end=end, channel="error")
            result["tokens"].append(record)
            error("lexer", "L001", f"Unrecognized character {source[pos:end]!r}.", pos, end, line, column)
        elif best_rule.channel != "skip":
            record = dict(kind=best_rule.name, label=best_rule.label or best_rule.name, value=source[pos:end],
                          line=line, column=column, offset=pos, end=end, channel=best_rule.channel)
            result["tokens"].append(record)
            if best_rule.channel == "error":
                error("lexer", "L002", best_rule.label or f"Invalid {best_rule.name}.", pos, end, line, column)
            elif best_rule.channel == "token":
                end_line, end_column = location(end)
                parser_tokens.append(Token(best_rule.name, source[pos:end], start_pos=pos, line=line,
                                           column=column, end_pos=end, end_line=end_line, end_column=end_column))
        pos = end
        if len(result["tokens"]) >= MAX_TOKENS and pos < len(source):
            error("limit", "R002", f"Token limit of {MAX_TOKENS:,} reached.", pos, pos, *location(pos))
            return finish()
    result["timings"]["lexer_ms"] = round((time.perf_counter() - lex_start) * 1000, 3)
    if diagnostics or mode == "lexer":
        return finish()

    parse_start = time.perf_counter()
    try:
        interactive = parser.parse_interactive("")
        for token in parser_tokens:
            interactive.feed_token(token)
        tree = interactive.feed_eof(parser_tokens[-1] if parser_tokens else None)
    except UnexpectedToken as exc:
        token = exc.token
        eof = token.type == "$END"
        offset = len(source) if eof else token.start_pos
        line, column = location(offset)
        expected = ", ".join(sorted(exc.expected))
        actual = "end of source" if eof else f"{token.type} {str(token)!r}"
        error("parser", "P001", f"Unexpected {actual}. Expected: {expected}.", offset,
              offset if eof else token.end_pos, line, column)
        return finish()
    result["timings"]["parser_ms"] = round((time.perf_counter() - parse_start) * 1000, 3)
    if profile.context_checks:
        _check_context(tree, error)
    try:
        result["tree"] = tree_to_dict(tree)
    except ValueError as exc:
        error("limit", "R003", str(exc))
    return finish()


def _check_context(root, error):
    pending = [(root, 0, 0)]
    while pending:
        node, loops, functions = pending.pop()
        if not isinstance(node, Tree):
            continue
        name = str(node.data)
        if name in {"break_statement", "continue_statement", "return_statement"}:
            if (name == "return_statement" and not functions) or (name != "return_statement" and not loops):
                token = next(child for child in node.children if isinstance(child, Token))
                needed = "a function" if name == "return_statement" else "a loop body"
                error("context", "S001", f"{str(token)} is only valid inside {needed}.",
                      token.start_pos, token.end_pos, token.line, token.column)
        if name == "function_definition":
            loops, functions = 0, functions + 1
        elif name == "class_definition":
            loops, functions = 0, 0
        elif name == "while_statement":
            loops += 1
        pending.extend((child, loops, functions) for child in reversed(node.children))


def tree_to_dict(root):
    target = {}
    stack = [(root, target, 0)]
    while stack:
        node, record, depth = stack.pop()
        if depth > MAX_TREE_DEPTH:
            raise ValueError(f"Syntax tree exceeds {MAX_TREE_DEPTH} levels; simplify deeply nested expressions.")
        if isinstance(node, Token):
            record.update(kind=node.type, value=str(node), line=node.line, column=node.column,
                          offset=node.start_pos, end=node.end_pos, children=[])
        else:
            meta = node.meta
            record.update(kind=str(node.data), value=None, line=getattr(meta, "line", 1),
                          column=getattr(meta, "column", 1), offset=getattr(meta, "start_pos", 0),
                          end=getattr(meta, "end_pos", 0), children=[{} for _ in node.children])
            stack.extend((child, record["children"][index], depth + 1)
                         for index, child in enumerate(node.children))
    return target
