"""Command line interface for site-preflight."""

import argparse
import json
import os
import sys

from . import __version__
from .checks import FAIL, INFO, PASS, WARN, run

MARK = {PASS: "PASS", WARN: "WARN", FAIL: "FAIL", INFO: "INFO"}
COLOUR = {PASS: "\033[32m", WARN: "\033[33m", FAIL: "\033[31m", INFO: "\033[36m"}
RESET = "\033[0m"


def _use_colour(stream):
    return stream.isatty() and os.environ.get("NO_COLOR") is None and os.environ.get("TERM") != "dumb"


def format_text(report, colour=False):
    lines = []
    lines.append("site-preflight %s  %s" % (report["version"], report["url"]))
    if report.get("final_url") and report["final_url"] != report["url"]:
        lines.append("final URL: %s" % report["final_url"])
    lines.append("checked at %s" % report["checked_at"])
    lines.append("")
    width = max(len(c["label"]) for c in report["checks"])
    for c in report["checks"]:
        mark = "[%s]" % MARK[c["status"]]
        if colour:
            mark = COLOUR[c["status"]] + mark + RESET
        lines.append("%s %s  %s" % (mark, c["label"].ljust(width), c["detail"]))
        for b in c.get("broken", []):
            lines.append("       %s  %s" % (b["error"] or b["status"], b["url"]))
    s = report["summary"]
    lines.append("")
    lines.append("%d passed, %d warnings, %d failed, %d info" % (s[PASS], s[WARN], s[FAIL], s[INFO]))
    if s[FAIL]:
        lines.append("Not ready: fix the FAIL items before launch.")
    elif s[WARN]:
        lines.append("Nearly there: the WARN items are worth a look.")
    else:
        lines.append("Ready for launch.")
    return "\n".join(lines)


def build_parser():
    p = argparse.ArgumentParser(
        prog="site-preflight",
        description="Check a website before launch: broken links, HTTPS, redirects, "
                    "title, meta description, mobile viewport, robots.txt, sitemap and footer year.",
    )
    p.add_argument("--url", help="website to check, for example https://example.com")
    p.add_argument("target", nargs="?", help=argparse.SUPPRESS)
    p.add_argument("--max-links", type=int, default=25, metavar="N",
                   help="internal links from the home page to test (default 25, 0 to skip)")
    p.add_argument("--timeout", type=float, default=10.0, metavar="SECONDS",
                   help="timeout for each request (default 10)")
    p.add_argument("--json", action="store_true", help="print the report as JSON")
    p.add_argument("--version", action="version", version="site-preflight %s" % __version__)
    return p


def main(argv=None):
    args = build_parser().parse_args(argv)
    url = args.url or args.target
    if not url:
        build_parser().print_usage(sys.stderr)
        print("site-preflight: error: --url is required", file=sys.stderr)
        return 2
    try:
        report = run(url, max_links=args.max_links, timeout=args.timeout)
    except ValueError as e:
        print("site-preflight: error: %s" % e, file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print(format_text(report, colour=_use_colour(sys.stdout)))
    return 1 if report["summary"][FAIL] else 0
