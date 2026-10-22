"""Plain-language explanations without changing compiler results or exports."""

TOKEN_NAMES = {
    "IDENT": "Name", "INTEGER": "Whole number", "NUMBER": "Number",
    "FLOAT": "Decimal number", "HEX": "Hexadecimal number", "TEXT": "Text",
    "TRUE": "True / false value", "FALSE": "True / false value",
    "SPACE": "Whitespace", "COMMENT": "Comment", "LINE_COMMENT": "Comment",
    "ASSIGN": "Assignment (=)", "CALL_ASSIGN": "Function assignment (:=)",
    "SEMI": "Semicolon (;)", "LPAR": "Opening parenthesis", "RPAR": "Closing parenthesis",
    "LBRACE": "Opening brace", "RBRACE": "Closing brace", "LBRACKET": "Opening bracket",
    "RBRACKET": "Closing bracket", "PLUS": "Addition (+)", "MINUS": "Subtraction (-)",
    "STAR": "Multiplication (*)", "SLASH": "Division (/)", "MOD": "Remainder (%)",
    "EQ": "Equal to (==)", "NE": "Not equal to (!=)", "LT": "Less than (<)",
    "GT": "Greater than (>)", "LE": "Less than or equal", "GE": "Greater than or equal",
    "AND": "Both conditions (&&)", "OR": "Either condition (||)", "NOT": "Not (!)",
    "DOT": "Dot (.)", "COMMA": "Comma (,)", "COLON": "Colon (:)", "CARET": "Caret (^)",
}
STAGES = {"lexer": "Tokens", "parser": "Grammar", "context": "Usage",
          "configuration": "Rules", "limit": "Size limit"}


def token_name(token):
    if token["channel"] == "error":
        return "Needs fixing"
    if token["label"] == "keyword":
        return "Keyword"
    return TOKEN_NAMES.get(token["kind"], token["label"] or token["kind"])


def token_group(token):
    if token["channel"] == "error":
        return "Needs fixing"
    if token["channel"] == "comment":
        return "Comments"
    if token["label"] == "keyword":
        return "Keywords"
    if token["label"] == "identifier" or token["kind"] == "IDENT":
        return "Names"
    if "literal" in token["label"] or token["kind"] in {"NUMBER", "INTEGER", "FLOAT", "HEX", "TEXT", "TRUE", "FALSE"}:
        return "Values"
    if token["kind"] in TOKEN_NAMES:
        return "Operators & symbols"
    return "Other tokens"


def report_summary(report):
    """Do not describe skipped/failed stages as having passed."""
    stages = {d["stage"] for d in report["diagnostics"]}
    if report["mode"] == "validate":
        return dict(title="Language settings are ready" if report["ok"] else "Language settings need attention",
                    detail="Your rules can build a parser. Check an example to test how they behave." if report["ok"] else "Open Language settings to correct the rules.",
                    lexer="Not checked", parser="Not checked", tone="success" if report["ok"] else "warning")
    lexer = "Passed" if "lexer_ms" in report["timings"] and "lexer" not in stages else "Not checked"
    if "lexer" in stages:
        lexer = "Needs fixing"
    if "limit" in stages and "lexer_ms" not in report["timings"]:
        lexer = "Stopped"
    parser = "Not checked"
    if report["tree"] is not None:
        parser = "Passed"
    elif "parser" in stages:
        parser = "Needs fixing"
    elif "limit" in stages and report["mode"] == "pipeline" and lexer == "Passed":
        parser = "Stopped"
    if report["ok"]:
        title = "Your code looks good" if report["mode"] == "pipeline" else "Token check passed"
        detail = "Token, grammar and enabled usage checks passed. Your code was checked, not executed." if report["mode"] == "pipeline" else "Words and symbols were checked. Choose Analyze code to check grammar too."
    else:
        count = len(report["diagnostics"])
        title = f"{count} issue{'s' if count != 1 else ''} to fix"
        detail = "Select a problem to see where it is and what to try next. Your code has not been changed."
    return dict(title=title, detail=detail, lexer=lexer, parser=parser,
                tone="success" if report["ok"] else "warning")


def explain_diagnostic(diagnostic, source):
    message = diagnostic["message"].replace("Identifiers", "Names").replace("identifier", "name")
    hint = diagnostic.get("hint", "")
    if diagnostic["stage"] == "parser":
        text = source[diagnostic["offset"]:diagnostic["end"]]
        message = f"The grammar could not continue at {text[:60]!r}." if text else "Something is missing at the end of the code."
        if diagnostic.get("expected") == ["SEMI"]:
            message = "This statement needs a semicolon (;) at the end."
        if not hint:
            hint = "Compare this line with an example in the Examples tab."
    elif diagnostic["stage"] == "configuration":
        message = "The language rules could not be used for this check."
        hint = "Open Language settings to review the rules. Technical details show the original message."
    elif diagnostic["stage"] == "limit":
        hint = "Try a smaller file or simplify deeply nested expressions."
    elif diagnostic["stage"] == "lexer" and not hint:
        hint = "Check the highlighted text. Examples shows valid names, numbers, strings and comments."
    return message, hint
