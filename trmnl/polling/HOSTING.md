# Hosting the polling JSON

The plugin needs one public, unauthenticated URL that answers with the payload
JSON. Nothing in the plugin or the Liquid markup cares who serves it.

**This repo serves it from Cloudflare Pages** (free, works with a private
GitHub repository, no plan wall). The `gh-pages` push in
[`../../.github/workflows/publish-json.yml`](../../.github/workflows/publish-json.yml)
is kept as a fallback for the day the GitHub repository goes public; ignore it
until then.

## Cloudflare Pages, direct upload

Files land at `https://<project>.pages.dev/`:

```
https://trmnl-omie.pages.dev/prices-pt.json
https://trmnl-omie.pages.dev/prices-es.json
```

### 1. Create the Pages project

Cloudflare dashboard -> **Workers & Pages** -> **Create** -> **Pages** ->
**Upload assets**. Name it `trmnl-omie`, production branch `main`. Deploy
anything once (the workflow replaces it). The workflow also tries to create the
project itself, so this step only exists to claim the name.

### 2. Create an API token

**My Profile** -> **API Tokens** -> **Create Token** -> **Custom token**:

| Field | Value |
|---|---|
| Permissions | Account -> **Cloudflare Pages** -> **Edit** |
| Account resources | Include -> your account |

Copy the token; Cloudflare shows it once.

### 3. Find the account ID

**Workers & Pages** overview, right sidebar, **Account ID** (also in the
dashboard URL after `/accounts/`).

### 4. Put both in the repository

```bash
gh secret set CLOUDFLARE_API_TOKEN -R pmagnomuller/trmnl-omie
gh secret set CLOUDFLARE_ACCOUNT_ID -R pmagnomuller/trmnl-omie
# optional, defaults to trmnl-omie:
gh variable set CF_PAGES_PROJECT -b trmnl-omie -R pmagnomuller/trmnl-omie
```

Until both secrets exist the deploy step prints a notice and skips, so the
workflow stays green.

### 5. Run it and verify

```bash
gh workflow run publish-json.yml -R pmagnomuller/trmnl-omie
gh run watch -R pmagnomuller/trmnl-omie
curl -sL -o /dev/null -w '%{http_code}\n' https://trmnl-omie.pages.dev/prices-pt.json   # want 200
curl -sL https://trmnl-omie.pages.dev/prices-pt.json | head -c 120                      # want {"area"
```

Then point the deploy at it so every run self-checks:

```bash
gh variable set POLLING_URL -b "https://trmnl-omie.pages.dev/prices-pt.json" -R pmagnomuller/trmnl-omie
```

### 6. Custom domain (optional)

Pages -> your project -> **Custom domains** -> add e.g.
`prices.pedro-muller.com`. Keep `POLLING_URL` in sync with whatever hostname
you settle on -- the workflow compares against the file the URL names.

## Other hosts

Anything that serves a directory works.

**Netlify** (drop-in replacement for the Cloudflare step):

```bash
npm install -g netlify-cli
netlify deploy --prod --dir=dist --site="$NETLIFY_SITE_ID"
```

Secrets: `NETLIFY_AUTH_TOKEN` (User settings -> Applications -> personal access
token) and `NETLIFY_SITE_ID` (Site configuration -> Site ID).

**GitHub Pages** needs a public repository or a paid plan, and on this account
every `pmagnomuller.github.io/...` path 301-redirects to `www.pedro-muller.com`,
so the working URL would be
`https://www.pedro-muller.com/trmnl-omie/prices-pt.json`. Verify with
`curl -sL`; never assume the `github.io` form.

**Your own server**: `scp dist/prices-pt.json host:/var/www/...` from a step,
with an SSH key in secrets.

## What is public

The published files are the payload only: prices, slot labels, timestamps.
No credentials, no UUID, no usage data. The endpoint is meant to be readable by
anyone -- that is what makes a one-click recipe install possible.
