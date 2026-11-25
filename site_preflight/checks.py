"""Pre-launch checks for a website. Standard library only."""

import datetime
import re
import socket
import ssl
import urllib.error
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser

from . import __version__

USER_AGENT = (
    "site-preflight/%s (+https://github.com/digitalcaveuk/site-preflight)" % __version__
)
MAX_BODY = 3 * 1024 * 1024  # never read more than 3 MB of one page

PASS, WARN, FAIL, INFO = "pass", "warn", "fail", "info"


# --------------------------------------------------------------------------
# HTTP helpers
# --------------------------------------------------------------------------

class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def _make_ssl_context():
    """Default context, with a fallback for Python builds that ship without CA certs."""
    ctx = ssl.create_default_context()
    if ctx.cert_store_stats().get("x509_ca", 0) == 0:
        try:
            import certifi  # optional
            ctx.load_verify_locations(certifi.where())
        except Exception:
            for path in ("/etc/ssl/cert.pem", "/etc/ssl/certs/ca-certificates.crt"):
                try:
                    ctx.load_verify_locations(path)
                    break
                except Exception:
                    continue
    return ctx


_ssl_ctx = _make_ssl_context()
_opener_follow = urllib.request.build_opener(
    urllib.request.HTTPSHandler(context=_ssl_ctx)
)
_opener_nofollow = urllib.request.build_opener(
    _NoRedirect, urllib.request.HTTPSHandler(context=_ssl_ctx)
)


class Response:
    def __init__(self, url, status=None, headers=None, body=b"", error=None, final_url=None):
        self.url = url
        self.status = status
        self.headers = headers or {}
        self.body = body
        self.error = error
        self.final_url = final_url or url

    @property
    def text(self):
        charset = "utf-8"
        ctype = self.headers.get("content-type", "")
        m = re.search(r"charset=([\w-]+)", ctype, re.I)
        if m:
            charset = m.group(1)
        try:
            return self.body.decode(charset, errors="replace")
        except LookupError:
            return self.body.decode("utf-8", errors="replace")


def fetch(url, method="GET", follow=True, timeout=10.0, read_body=True):
    """Fetch a URL and return a Response. Never raises for HTTP or network errors."""
    req = urllib.request.Request(url, method=method, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    })
    opener = _opener_follow if follow else _opener_nofollow
    try:
        with opener.open(req, timeout=timeout) as r:
            body = r.read(MAX_BODY) if (read_body and method != "HEAD") else b""
            headers = {k.lower(): v for k, v in r.headers.items()}
            return Response(url, r.status, headers, body, final_url=r.geturl())
    except urllib.error.HTTPError as e:
        headers = {k.lower(): v for k, v in (e.headers or {}).items()}
        body = b""
        if read_body and method != "HEAD":
            try:
                body = e.read(MAX_BODY)
            except Exception:
                pass
        return Response(url, e.code, headers, body, final_url=e.geturl() or url)
    except urllib.error.URLError as e:
        return Response(url, error=_reason(e.reason))
    except (socket.timeout, TimeoutError):
        return Response(url, error="timed out")
    except Exception as e:  # ssl errors, connection resets, bad URLs
        return Response(url, error=_reason(e))


def _reason(err):
    if isinstance(err, ssl.SSLCertVerificationError):
        return "SSL certificate problem: %s" % (err.verify_message or err)
    if isinstance(err, socket.gaierror):
        return "domain does not resolve"
    if isinstance(err, (socket.timeout, TimeoutError)):
        return "timed out"
    return str(err) or err.__class__.__name__


# --------------------------------------------------------------------------
# HTML parsing
# --------------------------------------------------------------------------

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = None
        self._in_title = False
        self._title_parts = []
        self.meta = {}
        self.links = []
        self.lang = None
        self.canonical = None
        self.text_parts = []
        self.footer_parts = []
        self._footer_tag = None   # tag name of the footer element we are inside
        self._footer_nest = 0     # nesting of that tag name inside the footer
        self._skip = 0

    def handle_starttag(self, tag, attrs):
        a = {k.lower(): (v or "") for k, v in attrs}
        if tag == "html" and a.get("lang"):
            self.lang = a["lang"]
        elif tag == "title" and self.title is None:
            self._in_title = True
        elif tag == "meta":
            name = (a.get("name") or a.get("property") or "").lower()
            if name and name not in self.meta:
                self.meta[name] = a.get("content", "")
        elif tag == "a" and a.get("href"):
            self.links.append(a["href"].strip())
        elif tag == "link" and "canonical" in a.get("rel", "").lower().split():
            self.canonical = a.get("href")
        elif tag in ("script", "style", "noscript"):
            self._skip += 1
        if self._footer_tag:
            if tag == self._footer_tag:
                self._footer_nest += 1
        elif tag == "footer" or (
            tag in ("div", "section") and "footer" in (a.get("id", "") + " " + a.get("class", "")).lower()
        ):
            self._footer_tag, self._footer_nest = tag, 1

    def handle_endtag(self, tag):
        if tag == "title" and self._in_title:
            self._in_title = False
            self.title = "".join(self._title_parts).strip()
        elif tag in ("script", "style", "noscript") and self._skip:
            self._skip -= 1
        if self._footer_tag and tag == self._footer_tag:
            self._footer_nest -= 1
            if self._footer_nest <= 0:
                self._footer_tag = None

    def handle_data(self, data):
        if self._in_title:
            self._title_parts.append(data)
        if self._skip:
            return
        self.text_parts.append(data)
        if self._footer_tag:
            self.footer_parts.append(data)


def parse_html(html):
    p = PageParser()
    try:
        p.feed(html)
        p.close()
    except Exception:
        pass
    if p._in_title and p.title is None:
        p.title = "".join(p._title_parts).strip()
    return p


# --------------------------------------------------------------------------
# Individual checks. Each returns a dict: id, label, status, detail.
# --------------------------------------------------------------------------

def result(cid, label, status, detail, **extra):
    d = {"id": cid, "label": label, "status": status, "detail": detail}
    d.update(extra)
    return d


def check_title(page):
    t = (page.title or "").strip()
    if not t:
        return result("title", "Page title", FAIL, "no <title> found")
    n = len(t)
    if n < 10 or n > 65:
        return result("title", "Page title", WARN, "%d characters (aim for 10 to 65): %s" % (n, t), value=t)
    return result("title", "Page title", PASS, "%d characters: %s" % (n, t), value=t)


def check_description(page):
    d = (page.meta.get("description") or "").strip()
    if not d:
        return result("meta_description", "Meta description", FAIL, "missing")
    n = len(d)
    if n < 50 or n > 165:
        return result("meta_description", "Meta description", WARN,
                      "%d characters (aim for 50 to 165)" % n, value=d)
    return result("meta_description", "Meta description", PASS, "%d characters" % n, value=d)


def check_viewport(page):
    v = page.meta.get("viewport", "")
    if not v:
        return result("viewport", "Mobile viewport", FAIL,
                      "no <meta name=\"viewport\">, the site will look zoomed out on phones")
    if "width=device-width" not in v.replace(" ", "").lower():
        return result("viewport", "Mobile viewport", WARN, "viewport set but not width=device-width: %s" % v, value=v)
    return result("viewport", "Mobile viewport", PASS, v, value=v)


def check_robots_meta(page, headers):
    m = (page.meta.get("robots", "") + " " + headers.get("x-robots-tag", "")).lower()
    if "noindex" in m:
        return result("indexable", "Indexable", FAIL,
                      "page says noindex, search engines will drop it (left over from staging?)")
    return result("indexable", "Indexable", PASS, "no noindex in meta robots or X-Robots-Tag")


YEAR_RE = re.compile(r"(?:\u00a9|\(c\)|copyright)[^0-9]{0,40}((?:19|20)\d{2})(?:\s*[-\u2013]\s*((?:19|20)\d{2}))?", re.I)


def find_copyright_year(page):
    """Return the newest year that follows a copyright sign, preferring footer text."""
    for parts in (page.footer_parts, page.text_parts):
        text = " ".join(" ".join(parts).split())
        years = []
        for m in YEAR_RE.finditer(text):
            years.extend(int(y) for y in m.groups() if y)
        if years:
            return max(years)
    return None


def check_copyright(page, this_year=None):
    this_year = this_year or datetime.date.today().year
    y = find_copyright_year(page)
    if y is None:
        return result("copyright_year", "Copyright year", INFO,
                      "no copyright notice found (or it is added by JavaScript)")
    if y < this_year:
        return result("copyright_year", "Copyright year", WARN,
                      "footer says %d, now %d: an old year makes a site look abandoned" % (y, this_year), value=y)
    return result("copyright_year", "Copyright year", PASS, "footer says %d" % y, value=y)


def check_https(home):
    final = urllib.parse.urlsplit(home.final_url)
    if final.scheme != "https":
        return result("https", "HTTPS", FAIL, "home page is served over plain http")
    return result("https", "HTTPS", PASS, "served over https")


def check_hsts(home):
    h = home.headers.get("strict-transport-security", "")
    if not h:
        return result("hsts", "HSTS header", WARN, "no Strict-Transport-Security header")
    m = re.search(r"max-age=(\d+)", h)
    age = int(m.group(1)) if m else 0
    if age < 15552000:  # 180 days
        return result("hsts", "HSTS header", WARN, "max-age is %d seconds (180 days or more is usual): %s" % (age, h), value=h)
    return result("hsts", "HSTS header", PASS, h, value=h)


def _redirect_target(url, timeout):
    r = fetch(url, method="GET", follow=False, timeout=timeout, read_body=False)
    loc = r.headers.get("location")
    if loc:
        loc = urllib.parse.urljoin(url, loc)
    return r, loc


def _resolve(url, timeout, hops=6):
    """Follow redirects by hand. Returns (chain, final_response)."""
    chain = []
    r = None
    for _ in range(hops):
        r, loc = _redirect_target(url, timeout)
        chain.append((url, r.status, r.error))
        if r.status in (301, 302, 303, 307, 308) and loc:
            url = loc
            continue
        break
    return chain, r


def check_http_redirect(host, canonical, timeout):
    chain, final = _resolve("http://%s/" % host, timeout)
    first = chain[0]
    if first[2]:
        return result("http_redirect", "http:// to https://", WARN,
                      "http://%s/ failed: %s" % (host, first[2]))
    end = chain[-1][0]
    if urllib.parse.urlsplit(end).scheme == "https" and final is not None and final.status and final.status < 400:
        codes = " > ".join(str(c[1]) for c in chain)
        status = PASS if first[1] in (301, 308) else WARN
        note = "" if status == PASS else " (use a permanent 301 or 308)"
        return result("http_redirect", "http:// to https://", status,
                      "http://%s/ redirects to %s [%s]%s" % (host, end, codes, note))
    return result("http_redirect", "http:// to https://", FAIL,
                  "http://%s/ does not redirect to https (status %s)" % (host, first[1]))


SECOND_LEVEL = {"co", "com", "org", "net", "ac", "gov", "edu", "ltd", "plc", "me", "sch", "nhs"}


def is_apex(host):
    labels = host.split(".")
    return len(labels) <= 2 or (len(labels) == 3 and labels[1] in SECOND_LEVEL)


def check_www(host, canonical_host, timeout):
    if not host.startswith("www.") and not is_apex(host):
        return result("www_redirect", "www / non-www", INFO, "skipped: %s is a subdomain" % host)
    alt = host[4:] if host.startswith("www.") else "www." + host
    chain, final = _resolve("https://%s/" % alt, timeout)
    first = chain[0]
    if first[2]:
        if "resolve" in first[2]:
            return result("www_redirect", "www / non-www", WARN,
                          "%s does not resolve: visitors who type it get an error" % alt)
        return result("www_redirect", "www / non-www", WARN, "https://%s/ failed: %s" % (alt, first[2]))
    end_host = urllib.parse.urlsplit(chain[-1][0]).hostname or ""
    if end_host == canonical_host and final is not None and final.status and final.status < 400:
        if len(chain) == 1:
            return result("www_redirect", "www / non-www", WARN,
                          "https://%s/ serves the page without redirecting (duplicate content)" % alt)
        return result("www_redirect", "www / non-www", PASS,
                      "https://%s/ redirects to %s" % (alt, canonical_host))
    if final is not None and final.status and final.status < 400:
        return result("www_redirect", "www / non-www", WARN,
                      "https://%s/ serves a page but does not redirect to %s (duplicate content)" % (alt, canonical_host))
    return result("www_redirect", "www / non-www", WARN,
                  "https://%s/ returns status %s" % (alt, final.status if final else "?"))


def check_robots_txt(origin, timeout):
    r = fetch(origin + "/robots.txt", timeout=timeout)
    sitemaps = []
    if r.status == 200 and "<html" not in r.text[:500].lower():
        body = r.text
        sitemaps = [l.split(":", 1)[1].strip() for l in body.splitlines()
                    if l.lower().startswith("sitemap:")]
        blocks_all = re.search(r"(?im)^user-agent:\s*\*\s*$(?:\n(?!user-agent).*)*?\n\s*disallow:\s*/\s*$", body)
        if blocks_all:
            return result("robots_txt", "robots.txt", FAIL,
                          "robots.txt blocks every crawler (Disallow: /)", sitemaps=sitemaps), sitemaps
        return result("robots_txt", "robots.txt", PASS,
                      "found%s" % (", lists %d sitemap(s)" % len(sitemaps) if sitemaps else ""),
                      sitemaps=sitemaps), sitemaps
    why = r.error or "status %s" % r.status
    return result("robots_txt", "robots.txt", WARN, "not found (%s)" % why), sitemaps


def check_sitemap(origin, listed, timeout):
    candidates = list(listed) + [origin + "/sitemap.xml", origin + "/sitemap_index.xml"]
    seen = set()
    for url in candidates:
        if url in seen:
            continue
        seen.add(url)
        r = fetch(url, timeout=timeout)
        head = r.text[:2000].lower() if r.status == 200 else ""
        if "<urlset" in head or "<sitemapindex" in head:
            kind = "index" if "<sitemapindex" in head else "urlset"
            return result("sitemap", "XML sitemap", PASS, "%s (%s)" % (url, kind), value=url)
    return result("sitemap", "XML sitemap", WARN, "no sitemap found at robots.txt, /sitemap.xml or /sitemap_index.xml")


def internal_links(page, base_url, hosts, limit):
    out, seen = [], set()
    if limit <= 0:
        return out
    for href in page.links:
        if href.startswith(("mailto:", "tel:", "javascript:", "#", "data:", "sms:")):
            continue
        url = urllib.parse.urljoin(base_url, href)
        parts = urllib.parse.urlsplit(url)
        if parts.scheme not in ("http", "https") or (parts.hostname or "").lower() not in hosts:
            continue
        url = urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path or "/", parts.query, ""))
        if url in seen or url.rstrip("/") == base_url.rstrip("/"):
            continue
        seen.add(url)
        out.append(url)
        if len(out) >= limit:
            break
    return out


def _link_status(url, timeout):
    r = fetch(url, method="HEAD", timeout=timeout)
    # Some servers refuse HEAD or fail it oddly: retry those with GET.
    if r.status is None or r.status in (403, 405, 501):
        r = fetch(url, method="GET", timeout=timeout, read_body=False)
    return {"url": url, "status": r.status, "error": r.error}


def check_links(urls, timeout, workers=8):
    if not urls:
        return result("links", "Internal links", INFO, "no internal links found on the home page", checked=0, broken=[]), []
    with ThreadPoolExecutor(max_workers=workers) as ex:
        rows = list(ex.map(lambda u: _link_status(u, timeout), urls))
    broken = [r for r in rows if r["error"] or (r["status"] or 0) >= 400]
    if broken:
        return result("links", "Internal links", FAIL,
                      "%d of %d broken" % (len(broken), len(rows)), checked=len(rows), broken=broken), rows
    return result("links", "Internal links", PASS, "%d checked, none broken" % len(rows),
                  checked=len(rows), broken=[]), rows


# --------------------------------------------------------------------------
# Runner
# --------------------------------------------------------------------------

def normalise_url(url):
    url = url.strip()
    if "://" not in url:
        url = "https://" + url
    parts = urllib.parse.urlsplit(url)
    if not parts.hostname:
        raise ValueError("not a valid URL: %s" % url)
    return urllib.parse.urlunsplit((parts.scheme, parts.netloc, parts.path or "/", parts.query, ""))


def run(url, max_links=25, timeout=10.0):
    url = normalise_url(url)
    started = datetime.datetime.now(datetime.timezone.utc)
    home = fetch(url, timeout=timeout)
    report = {
        "tool": "site-preflight",
        "version": __version__,
        "url": url,
        "final_url": home.final_url,
        "checked_at": started.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "checks": [],
        "links": [],
    }
    checks = report["checks"]
    if home.error or not home.status or home.status >= 400:
        checks.append(result("home_status", "Home page", FAIL,
                             home.error or "HTTP %s" % home.status, value=home.status))
        report["summary"] = summarise(checks)
        return report
    checks.append(result("home_status", "Home page", PASS,
                         "HTTP %s%s" % (home.status, "" if home.final_url == url else " (after redirect to %s)" % home.final_url),
                         value=home.status))
    page = parse_html(home.text)
    final = urllib.parse.urlsplit(home.final_url)
    host = (final.hostname or "").lower()
    origin = "%s://%s" % (final.scheme, final.netloc)
    bare = host[4:] if host.startswith("www.") else host
    hosts = {bare, "www." + bare}

    checks.append(check_https(home))
    checks.append(check_hsts(home) if final.scheme == "https" else
                  result("hsts", "HSTS header", INFO, "skipped: needs https first"))
    checks.append(check_http_redirect(host, home.final_url, timeout))
    checks.append(check_www(host, host, timeout))
    checks.append(check_title(page))
    checks.append(check_description(page))
    checks.append(check_viewport(page))
    checks.append(check_robots_meta(page, home.headers))
    robots, listed = check_robots_txt(origin, timeout)
    checks.append(robots)
    checks.append(check_sitemap(origin, listed, timeout))
    checks.append(check_copyright(page))
    if max_links <= 0:
        rows = []
        checks.append(result("links", "Internal links", INFO, "skipped (--max-links 0)", checked=0, broken=[]))
    else:
        links = internal_links(page, home.final_url, hosts, max_links)
        link_result, rows = check_links(links, timeout)
        checks.append(link_result)
    report["links"] = rows
    report["summary"] = summarise(checks)
    return report


def summarise(checks):
    counts = {PASS: 0, WARN: 0, FAIL: 0, INFO: 0}
    for c in checks:
        counts[c["status"]] += 1
    return counts
