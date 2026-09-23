# Hosting the polling JSON

The plugin needs one public, unauthenticated URL that answers with the payload
JSON. Nothing in the plugin or the Liquid markup cares who serves it.

**Live host: GitHub Pages**, serving the `gh-pages` branch that
[`../../.github/workflows/publish-json.yml`](../../.github/workflows/publish-json.yml)
force-pushes every 15 minutes:

```
https://www.pedro-muller.com/trmnl-omie/prices-pt.json
https://www.pedro-muller.com/trmnl-omie/prices-es.json
```

This required the repository to be public: a free plan refuses Pages on a
private repository (`422: Your current plan does not support GitHub Pages for
this repository`). The account's custom domain means project paths are served
under `www.pedro-muller.com`, and every `pmagnomuller.github.io/...` URL
301-redirects there — always verify with `curl -sL`, never assume the
`github.io` form.

`POLLING_URL` in repository variables points at the PT file, so each deploy
compares what the host serves against what it just built and fails if they
differ (12 attempts, 15 s apart, then 20 × 15 s). If the host lags or breaks,
the run goes red instead of silently freezing every install.

## Verify

```bash
curl -sL -o /dev/null -w '%{http_code}\n' https://www.pedro-muller.com/trmnl-omie/prices-pt.json   # want 200
curl -sL https://www.pedro-muller.com/trmnl-omie/prices-pt.json | head -c 120                      # want {"area"
```

A 404 right after enabling Pages usually means the first build is still
running; check `gh api repos/pmagnomuller/trmnl-omie/pages/builds`.

## Custom domain per project

Pages -> the repository's site is already served under the account custom
domain. To give it its own hostname instead (`prices.pedro-muller.com`), add a
CNAME record, then put that hostname in `trmnl/polling/CNAME` so the workflow
copies it onto `gh-pages`, and update `POLLING_URL` to match. Note the
`gh-pages` branch is workflow-owned and force-pushed, so a CNAME added by hand
disappears on the next run.

## Alternative hosts

Anything that serves a directory works; the payload, the plugin and the Liquid
markup are host-agnostic. Two ready-made swaps:

**Cloudflare Pages** (free, works with a private repository). Add to the
workflow after the build step:

```yaml
      - name: Deploy to Cloudflare Pages
        env:
          CLOUDFLARE_API_TOKEN: ${{ secrets.CLOUDFLARE_API_TOKEN }}
          CLOUDFLARE_ACCOUNT_ID: ${{ secrets.CLOUDFLARE_ACCOUNT_ID }}
          PROJECT: ${{ vars.CF_PAGES_PROJECT || 'trmnl-omie' }}
        run: |
          set -euo pipefail
          if [ -z "${CLOUDFLARE_API_TOKEN}" ]; then
            echo "::notice::Cloudflare secrets not set; skipping."
            exit 0
          fi
          npx --yes wrangler@4 pages project create "${PROJECT}" --production-branch main || true
          npx --yes wrangler@4 pages deploy dist --project-name "${PROJECT}" \
            --branch main --commit-dirty=true
```

Secrets: `CLOUDFLARE_API_TOKEN` (token with Account -> Cloudflare Pages ->
Edit) and `CLOUDFLARE_ACCOUNT_ID`. Files land at
`https://<project>.pages.dev/prices-pt.json`.

**Netlify**:

```bash
npm install -g netlify-cli
netlify deploy --prod --dir=dist --site="$NETLIFY_SITE_ID"
```

Secrets: `NETLIFY_AUTH_TOKEN` and `NETLIFY_SITE_ID`.

**Your own server**: `scp dist/prices-pt.json host:/var/www/...` from a step,
with an SSH key in secrets.

Whichever host you pick, set `POLLING_URL` to the address you verified so the
deploy keeps checking itself.

## What is public

The published files are the payload only: prices, slot labels, timestamps. No
credentials, no UUID, no usage data. The endpoint is meant to be readable by
anyone -- that is what makes a one-click recipe install possible. The plugin
UUID stays in repository secrets.
