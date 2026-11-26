# Install

site-preflight needs Python 3.8 or newer and has no third party dependencies. Pick whichever
method suits you.

## pip

Install the latest version straight from the GitHub repository:

```sh
pip install git+https://github.com/digitalcaveuk/site-preflight
```

This adds a `site-preflight` command to your path. Check it worked:

```sh
site-preflight --version
```

## pipx

If you prefer to keep command line tools in their own isolated environments, use
[pipx](https://pipx.pypa.io/):

```sh
pipx install git+https://github.com/digitalcaveuk/site-preflight
```

To upgrade later:

```sh
pipx upgrade site-preflight
```

## From a clone, without installing

```sh
git clone https://github.com/digitalcaveuk/site-preflight
cd site-preflight
python3 -m site_preflight --url https://example.com
```

## Docker

A ready-built image is published on Docker Hub as
[digitalcave/site-preflight](https://hub.docker.com/r/digitalcave/site-preflight).

```sh
docker run --rm digitalcave/site-preflight --url https://example.com
```

The image is based on `python:3.12-alpine` and runs as a non-root user. With no arguments it
prints the help text.

You can also build the image yourself from a clone:

```sh
docker build -t site-preflight .
docker run --rm site-preflight --url https://example.com
```

## Running the tests

From a clone:

```sh
python3 -m unittest discover -s tests -v
```

The tests start a small local web server, so they need no internet access.
