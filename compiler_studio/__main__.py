"""Desktop and command-line entry points; no compiler toolchain required."""

import argparse
import json
from pathlib import Path
import sys

from .profiles import Profile, ricepy_profile, calculator_profile


def main(argv=None):
    # Deterministic Unicode for redirected JSON and stdin on Windows too.
    for stream in (sys.stdin, sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Compiler Studio — Python lexer and grammar workbench")
    parser.add_argument("source", nargs="?", help="UTF-8 source file; omit to launch desktop UI")
    parser.add_argument("--profile", help="JSON language profile")
    parser.add_argument("--preset", choices=["ricepy", "calculator"], default="ricepy")
    parser.add_argument("--mode", choices=["pipeline", "lexer", "validate"], default="pipeline")
    parser.add_argument("--json", metavar="PATH", help="write a full report to a NEW file; '-' prints JSON")
    parser.add_argument("--save-preset", metavar="PATH", help="save the selected profile to a NEW JSON file")
    parser.add_argument('--explain', action='store_true', help='show source context and plain-language diagnostic hints')
    args = parser.parse_args(argv)
    try:
        profile = Profile.load(args.profile) if args.profile else ricepy_profile() if args.preset == "ricepy" else calculator_profile()
        if args.save_preset:
            with open(args.save_preset, "x", encoding="utf-8") as stream:
                stream.write(profile.to_json() + "\n")
            return 0
        if not args.source and args.mode != "validate":
            if args.profile or args.json or args.preset != "ricepy" or args.mode != "pipeline":
                parser.error("Provide a source file, or use --mode validate without a source.")
            try:
                from .gui import launch
            except ImportError as exc:
                print(f"Desktop UI requires Tkinter: {exc}", file=sys.stderr)
                return 2
            launch()
            return 0
        if args.source and args.source != "-" and Path(args.source).stat().st_size > 1_000_000:
            raise ValueError("Source file exceeds 1 MB.")
        source = sys.stdin.read(250_001) if args.source == "-" else Path(args.source).read_text(encoding="utf-8-sig") if args.source else ""
        from .worker import run_isolated
        result = run_isolated(source, profile, args.mode)
        if args.json:
            report = json.dumps(result, indent=2, ensure_ascii=False)
            if args.json == "-":
                print(report)
            else:
                # Never overwrite source, profiles, or existing reports.
                with open(args.json, "x", encoding="utf-8") as stream:
                    stream.write(report + "\n")
        if args.json != "-":
            if args.mode == "lexer":
                for token in result["tokens"]:
                    if token["kind"] in {"COMMENT", "UNCLOSED_COMMENT"}:
                        value = token["value"]
                        closed = token["kind"] == "COMMENT"
                        print("multi-line comment: " + value[3:-3] if closed else "multi-line comment: " + value[3:])
                        print("multi-line comment end" if closed else "malformed multi-line comment")
                    else:
                        print(f"{token['label']}: {token['value']}")
            print(f"{'VALID' if result['ok'] else 'INVALID'} | {args.mode} | "
                  f"{len(result['tokens'])} tokens | {result['timings']['total_ms']:.2f} ms")
            for diagnostic in result["diagnostics"]:
                print(f"{diagnostic['stage']} {diagnostic['line']}:{diagnostic['column']}: "
                      f"{diagnostic['message']}", file=sys.stderr)
                if args.explain:
                    from .presentation import explain_diagnostic
                    message, hint = explain_diagnostic(diagnostic, source)
                    lines = source.splitlines()
                    line = diagnostic.get('line', 1)
                    column = max(1, diagnostic.get('column', 1))
                    if 1 <= line <= len(lines):
                        start = max(0, column - 81)
                        print('  ' + lines[line - 1][start:start + 160].expandtabs(4), file=sys.stderr)
                        print('  ' + ' ' * len(lines[line - 1][start:column - 1].expandtabs(4)) + '^', file=sys.stderr)
                    print('  ' + message, file=sys.stderr)
                    if hint:
                        print('  Next: ' + hint, file=sys.stderr)
        return 0 if result["ok"] else 1
    except (OSError, UnicodeError, ValueError, TimeoutError, RuntimeError) as exc:
        print(f"Compiler Studio: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    import multiprocessing
    multiprocessing.freeze_support()
    sys.exit(main())
