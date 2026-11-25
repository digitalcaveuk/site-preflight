FROM python:3.12-alpine
LABEL org.opencontainers.image.title="site-preflight" \
      org.opencontainers.image.description="Check a website before launch: broken links, HTTPS, redirects, title, meta description, viewport, robots.txt, sitemap and footer year." \
      org.opencontainers.image.url="https://digitalcave.uk" \
      org.opencontainers.image.source="https://github.com/digitalcaveuk/site-preflight" \
      org.opencontainers.image.licenses="MIT" \
      org.opencontainers.image.vendor="DigitalCave"
WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY site_preflight ./site_preflight
RUN pip install --no-cache-dir . && rm -rf /app
RUN adduser -D -H preflight
USER preflight
ENTRYPOINT ["site-preflight"]
CMD ["--help"]
