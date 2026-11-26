# Usage

```text
site-preflight --url https://example.com [--max-links 25] [--timeout 10] [--json]
```

## Options

| Option | Meaning |
| --- | --- |
| `--url URL` | the site to check. `example.com` works too, https is assumed |
| `--max-links N` | how many internal links from the home page to test (default 25, `0` skips the link check) |
| `--timeout SECONDS` | seconds to wait for each request (default 10) |
| `--json` | print the full report as JSON instead of text |
| `--version` | print the version and exit |
| `-h`, `--help` | show the help text and exit |

## Example output

```text
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

The last line sums up the result: "Not ready" if anything failed, "Nearly there" if there are
only warnings, and "Ready for launch" if everything passed. Broken internal links are listed
under the "Internal links" line with their status or error.

Colour is used when the output is a terminal. Set `NO_COLOR` (or `TERM=dumb`) to turn it off.

## Checks

| ID | Label | What passes |
| --- | --- | --- |
| `home_status` | Home page | returns HTTP 2xx (redirects are followed and shown) |
| `https` | HTTPS | the final home page URL is https |
| `hsts` | HSTS header | a `Strict-Transport-Security` header with max-age of 180 days or more |
| `http_redirect` | http:// to https:// | `http://` redirects permanently (301 or 308) to https |
| `www_redirect` | www / non-www | the other variant (www or bare domain) resolves and redirects to the main one |
| `title` | Page title | present, 10 to 65 characters |
| `meta_description` | Meta description | present, 50 to 165 characters |
| `viewport` | Mobile viewport | `<meta name="viewport" content="width=device-width, ...">` is present |
| `indexable` | Indexable | no `noindex` in meta robots or the `X-Robots-Tag` header |
| `robots_txt` | robots.txt | exists and does not block every crawler |
| `sitemap` | XML sitemap | found via robots.txt, `/sitemap.xml` or `/sitemap_index.xml` |
| `copyright_year` | Copyright year | the newest year next to a copyright sign in the footer is the current year |
| `links` | Internal links | up to `--max-links` links from the home page return 2xx or 3xx (HEAD, falling back to GET) |

If the home page itself fails to load (an error or HTTP 400 or above), the report stops after
the "Home page" check, because the other checks depend on it.

## JSON output

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

The full report also includes `version`, `final_url` and `checked_at`.

## Exit codes

| Code | Meaning |
| --- | --- |
| `0` | no check failed (warnings and info lines are allowed) |
| `1` | at least one check failed |
| `2` | usage error: no URL given, or the URL is not valid |
| `130` | interrupted with Ctrl+C |

## Using it in CI

Because a failed check returns exit code `1`, you can stop a deploy or fail a pipeline when a
site is not ready. Here is a GitHub Actions job that checks a staging site:

```yaml
name: preflight
on:
  workflow_dispatch:
  push:
    branches: [main]
jobs:
  preflight:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install git+https://github.com/digitalcaveuk/site-preflight
      - run: site-preflight --url https://staging.example.com --max-links 50
```

The same job with Docker instead of pip:

```yaml
      - run: docker run --rm digitalcave/site-preflight --url https://staging.example.com
```

To keep the report as a build artefact, write the JSON to a file:

```sh
site-preflight --url https://staging.example.com --json > preflight.json
```

Note that a staging site is often meant to be `noindex`. In that case the "Indexable" check
fails by design, so run the check against the live URL just before or after launch, or treat
exit code `1` as a warning in that one job.

## Limits

- It looks at the home page and the links on it, not the whole site. Raise `--max-links` for more.
- It reads the HTML the server sends. Text added later by JavaScript (some footers, some
  titles) is not seen.
- It is polite: requests are made with a clear user agent and at most 8 at a time.
