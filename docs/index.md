# site-preflight

**site-preflight** is a small, free command line tool that checks a website before launch and
prints a clear report. It catches the mistakes that slip through on launch day: broken links,
a missing https redirect, a page title left as "Home", a `noindex` left over from staging, no
sitemap, or a footer that still says 2019.

- No dependencies beyond the Python standard library.
- Runs anywhere Python 3.8 or newer runs, or as a Docker image.
- One command, a readable report and a sensible exit code, so it fits into CI and deploy scripts.
- Open source under the MIT licence.

## Why it exists

A study of small business websites in the West Midlands found that about 1 in 5 were broken or
failing a basic check. Most of those faults are not hard to fix. They just never got checked: a
site goes live, the developer moves on, and nobody notices that the http version never
redirected or that half the footer links point to pages that no longer exist.

site-preflight is the checklist you can run on every site before handing it over. It is
deliberately small and does not try to replace a full crawler or an SEO suite.

## Quick start

Install it from GitHub with pip:

```sh
pip install git+https://github.com/digitalcaveuk/site-preflight
```

Then point it at a site:

```sh
site-preflight --url https://example.com
```

Or run it with Docker, without installing anything:

```sh
docker run --rm digitalcave/site-preflight --url https://example.com
```

You get one line per check, marked `PASS`, `WARN`, `FAIL` or `INFO`, and a summary. The exit
code is `1` if anything failed and `0` otherwise.

## What it checks

| Check | What passes |
| --- | --- |
| Home page | returns HTTP 2xx (redirects are followed and shown) |
| Internal links | up to `--max-links` links from the home page return 2xx or 3xx |
| HTTPS | the final home page URL is https |
| HSTS | a `Strict-Transport-Security` header with max-age of 180 days or more |
| http:// to https:// | `http://` redirects permanently (301 or 308) to https |
| www / non-www | the other variant resolves and redirects to the main one |
| Page title | present, 10 to 65 characters |
| Meta description | present, 50 to 165 characters |
| Mobile viewport | a `width=device-width` viewport meta tag is present |
| Indexable | no `noindex` in meta robots or the `X-Robots-Tag` header |
| robots.txt | exists and does not block every crawler |
| XML sitemap | found via robots.txt, `/sitemap.xml` or `/sitemap_index.xml` |
| Copyright year | the newest year next to a copyright sign in the footer is the current year |

See [Usage](usage.md) for every option, the JSON output and a CI example.

## Next steps

- [Install](install.md): pip, pipx, a local clone or Docker.
- [Usage](usage.md): options, checks, exit codes and CI.
- [About](about.md): who builds it and how to contribute.
