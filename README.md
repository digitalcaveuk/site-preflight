# site-preflight

A small command line tool that checks a website before launch and prints a clear, plain report.
It catches the boring mistakes that slip through on launch day: broken links, a missing
https redirect, a page title left as "Home", a `noindex` left over from staging, no sitemap,
or a footer that still says 2019.

No dependencies beyond the Python standard library. Runs anywhere Python 3.8+ runs, or as a
Docker image.

## What it checks

| Check | What passes |
| --- | --- |
| Home page | returns HTTP 2xx (redirects are followed and shown) |
| Internal links | up to `--max-links` links from the home page return 2xx or 3xx (HEAD, falling back to GET) |
| HTTPS | the final home page URL is https |
| HSTS | a `Strict-Transport-Security` header with max-age of 180 days or more |
| http:// to https:// | `http://` redirects permanently (301 or 308) to https |
| www / non-www | the other variant (www or bare domain) resolves and redirects to the main one |
| Page title | present, 10 to 65 characters |
| Meta description | present, 50 to 165 characters |
| Mobile viewport | `<meta name="viewport" content="width=device-width, ...">` is present |
| Indexable | no `noindex` in meta robots or the `X-Robots-Tag` header |
| robots.txt | exists and does not block every crawler |
| XML sitemap | found via robots.txt, `/sitemap.xml` or `/sitemap_index.xml` |
| Copyright year | the newest year next to a copyright sign in the footer is the current year |

Each line is marked `PASS`, `WARN`, `FAIL` or `INFO`. The exit code is `1` if anything
failed, `0` otherwise, so it drops straight into a CI pipeline or a deploy script.

## Install

```sh
pip install git+https://github.com/digitalcaveuk/site-preflight
```

Or run it without installing, from a clone:

```sh
git clone https://github.com/digitalcaveuk/site-preflight
cd site-preflight
python3 -m site_preflight --url https://example.com
```

Or with Docker:

```sh
docker build -t site-preflight .
docker run --rm site-preflight --url https://example.com
```

## Usage

```
site-preflight --url https://example.com [--max-links 25] [--timeout 10] [--json]
```

| Option | Meaning |
| --- | --- |
| `--url` | the site to check (`example.com` works too, https is assumed) |
| `--max-links N` | how many internal links from the home page to test (default 25, `0` skips the link check) |
| `--timeout S` | seconds to wait for each request (default 10) |
| `--json` | print the full report as JSON instead of text |
| `--version` | print the version |

## Example output

```
$ site-preflight --url example.com
site-preflight 0.1.0  https://example.com/
checked at 2026-11-25T13:05:37Z

[PASS] Home page            HTTP 200
[PASS] HTTPS                served over https
[WARN] HSTS header          no Strict-Transport-Security header
[FAIL] http:// to https://  http://example.com/ does not redirect to https (status 200)
[WARN] www / non-www        https://www.example.com/ serves a page but does not redirect to example.com (duplicate content)
[PASS] Page title           14 characters: Example Domain
[FAIL] Meta description     missing
[PASS] Mobile viewport      width=device-width,initial-scale=1
[PASS] Indexable            no noindex in meta robots or X-Robots-Tag
[WARN] robots.txt           not found (status 404)
[WARN] XML sitemap          no sitemap found at robots.txt, /sitemap.xml or /sitemap_index.xml
[INFO] Copyright year       no copyright notice found (or it is added by JavaScript)
[INFO] Internal links       no internal links found on the home page

5 passed, 4 warnings, 2 failed, 2 info
Not ready: fix the FAIL items before launch.
```

With `--json` every check has an `id`, `label`, `status` (`pass`, `warn`, `fail`, `info`) and
`detail`, plus a `links` list with the status of every link tested and a `summary` count:

```json
{
  "tool": "site-preflight",
  "url": "https://example.com/",
  "checks": [
    {"id": "home_status", "label": "Home page", "status": "pass", "detail": "HTTP 200", "value": 200},
    {"id": "hsts", "label": "HSTS header", "status": "warn", "detail": "no Strict-Transport-Security header"}
  ],
  "summary": {"pass": 5, "warn": 4, "fail": 2, "info": 2}
}
```

## Why it exists

In our [West Midlands small business website study](https://digitalcave.uk/blog/west-midlands-small-business-website-study-2026)
we found that 1 in 5 small business websites in the region were broken or failing a basic check.
Most of those faults are not hard to fix. They just never got checked: a site goes live, the
developer moves on, and nobody notices that the http version never redirected or that half the
footer links point to pages that no longer exist.

site-preflight is the checklist we wanted to run on every site before handing it over. It is
deliberately small: one command, a readable report, a sensible exit code.

## Limits

- It looks at the home page and the links on it, not the whole site. Raise `--max-links` for more.
- It reads the HTML the server sends. Text added later by JavaScript (some footers, some titles) is not seen.
- It is polite: requests are made with a clear user agent and at most 8 at a time.

## Development

```sh
python3 -m unittest discover -s tests -v
```

The tests start a small local web server, so they need no internet access.

## Credits

Built by [DigitalCave](https://digitalcave.uk), an all-in-one web design, SEO and digital marketing
agency. If you need a site built properly from the start, see our
[web design service in Birmingham](https://digitalcave.uk/web-design-service-birmingham).

Author: DigitalCave (Rocky V). Released under the [MIT licence](LICENSE).
