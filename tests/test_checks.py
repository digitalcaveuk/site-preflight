import json
import threading
import unittest
from http.server import BaseHTTPRequestHandler, HTTPServer

from site_preflight import checks, cli

HOME = """<!doctype html><html lang="en"><head>
<title>Acme Plumbing | Emergency plumber in Leeds</title>
<meta name="description" content="Family run plumbing firm covering Leeds and Bradford, open 24 hours for leaks, boilers and blocked drains.">
<meta name="viewport" content="width=device-width, initial-scale=1">
</head><body>
<a href="/about">About</a> <a href="/missing">Old page</a> <a href="/about#team">Team</a>
<a href="mailto:hi@example.com">Mail</a> <a href="https://other.example/">Elsewhere</a>
<p>Established 2004.</p>
<footer><div><p>&copy; 2019 - 2021 Acme Plumbing</p></div></footer>
<script>var y = "© 2030";</script>
</body></html>"""


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def _send(self, code, body=b"", ctype="text/html; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        if self.command != "HEAD":
            self.wfile.write(body)

    def do_HEAD(self):
        self.do_GET()

    def do_GET(self):
        if self.path == "/":
            self._send(200, HOME.encode())
        elif self.path == "/about":
            self._send(200, b"<title>About</title>")
        elif self.path == "/robots.txt":
            self._send(200, b"User-agent: *\nDisallow: /admin\nSitemap: http://127.0.0.1:%d/sm.xml\n"
                       % self.server.server_port, "text/plain")
        elif self.path == "/sm.xml":
            self._send(200, b'<?xml version="1.0"?><urlset></urlset>', "application/xml")
        else:
            self._send(404, b"not found")


class LocalServer(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server = HTTPServer(("127.0.0.1", 0), Handler)
        cls.port = cls.server.server_port
        threading.Thread(target=cls.server.serve_forever, daemon=True).start()
        cls.base = "http://127.0.0.1:%d/" % cls.port

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown()

    def test_full_run(self):
        report = checks.run(self.base, max_links=10, timeout=5)
        by_id = {c["id"]: c for c in report["checks"]}
        self.assertEqual(by_id["home_status"]["status"], checks.PASS)
        self.assertEqual(by_id["https"]["status"], checks.FAIL)
        self.assertEqual(by_id["title"]["status"], checks.PASS)
        self.assertEqual(by_id["meta_description"]["status"], checks.PASS)
        self.assertEqual(by_id["viewport"]["status"], checks.PASS)
        self.assertEqual(by_id["robots_txt"]["status"], checks.PASS)
        self.assertEqual(by_id["sitemap"]["status"], checks.PASS)
        self.assertEqual(by_id["copyright_year"]["value"], 2021)
        self.assertEqual(by_id["copyright_year"]["status"], checks.WARN)
        links = by_id["links"]
        self.assertEqual(links["checked"], 2)  # /about (fragment dropped) and /missing
        self.assertEqual([b["url"] for b in links["broken"]], [self.base + "missing"])
        self.assertEqual(links["status"], checks.FAIL)

    def test_max_links_zero(self):
        report = checks.run(self.base, max_links=0, timeout=5)
        links = [c for c in report["checks"] if c["id"] == "links"][0]
        self.assertEqual(links["status"], checks.INFO)

    def test_cli_json(self):
        import io
        from contextlib import redirect_stdout
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = cli.main(["--url", self.base, "--max-links", "5", "--json"])
        data = json.loads(buf.getvalue())
        self.assertEqual(code, 1)
        self.assertEqual(data["tool"], "site-preflight")
        self.assertIn("summary", data)


class Parsing(unittest.TestCase):
    def test_parse(self):
        p = checks.parse_html(HOME)
        self.assertTrue(p.title.startswith("Acme Plumbing"))
        self.assertIn("viewport", p.meta)
        self.assertEqual(checks.find_copyright_year(p), 2021)

    def test_missing_bits(self):
        p = checks.parse_html("<html><body><p>Copyright 2025</p></body></html>")
        self.assertEqual(checks.check_title(p)["status"], checks.FAIL)
        self.assertEqual(checks.check_description(p)["status"], checks.FAIL)
        self.assertEqual(checks.check_viewport(p)["status"], checks.FAIL)
        self.assertEqual(checks.check_copyright(p, this_year=2025)["status"], checks.PASS)
        self.assertEqual(checks.check_copyright(p, this_year=2026)["status"], checks.WARN)

    def test_noindex(self):
        p = checks.parse_html('<meta name="robots" content="noindex,nofollow">')
        self.assertEqual(checks.check_robots_meta(p, {})["status"], checks.FAIL)
        p = checks.parse_html("<title>x</title>")
        self.assertEqual(checks.check_robots_meta(p, {"x-robots-tag": "noindex"})["status"], checks.FAIL)

    def test_normalise(self):
        self.assertEqual(checks.normalise_url("example.com"), "https://example.com/")
        self.assertEqual(checks.normalise_url("https://example.com/a#x"), "https://example.com/a")
        with self.assertRaises(ValueError):
            checks.normalise_url("https://")

    def test_is_apex(self):
        self.assertTrue(checks.is_apex("example.com"))
        self.assertTrue(checks.is_apex("example.co.uk"))
        self.assertFalse(checks.is_apex("blog.example.com"))


if __name__ == "__main__":
    unittest.main()
