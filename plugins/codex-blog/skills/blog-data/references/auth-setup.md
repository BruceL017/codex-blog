# Blog Data - Google Authentication Setup

## Overview

Four credential tiers serve different API combinations:

| Tier | Credentials | APIs Unlocked |
|------|------------|---------------|
| **0** | API Key only | PageSpeed Insights, CrUX, CrUX History, YouTube Data, Cloud Natural Language |
| **1** | + Service Account | + Search Console, Indexing API |
| **2** | + GA4 property ID | + GA4 Data API |
| **3** | + Google Ads tokens | + Keyword Planner |

## Step 1: Create a Google Cloud Project

1. Go to [console.cloud.google.com](https://console.cloud.google.com)
2. Click **Select a project** > **New Project**
3. Name it (e.g., "Codex Blog") and note the project ID
4. Select the project after creation

## Step 2: Enable APIs

Navigate to **APIs & Services > Library** and enable:

| API | Required For |
|-----|-------------|
| PageSpeed Insights API | Lighthouse lab data, CWV scores |
| Chrome UX Report API | CrUX field data + History |
| Google Search Console API | Search Analytics, URL Inspection, Sitemaps |
| Web Search Indexing API | Indexing API v3 (new post notifications) |
| Google Analytics Data API | GA4 organic traffic analysis |
| YouTube Data API v3 | Video research for AI-search SEO visibility |
| Cloud Natural Language API | Entity salience, sentiment, classification |

## Step 3: Create an API Key (Tier 0)

1. **APIs & Services > Credentials > Create Credentials > API key**
2. Click **Restrict key** > under **API restrictions**, select the APIs above
3. Copy the key (starts with `AIzaSy...`)

## Step 4: Create a Service Account (Tier 1)

1. **IAM & Admin > Service Accounts > Create Service Account**
2. Name: `codex-blog` (or similar)
3. Skip optional permissions steps
4. Click on the created service account > **Keys > Add Key > Create new key > JSON**
5. Download and store securely (e.g., `~/.config/codex-blog/service_account.json`)

### Grant Search Console Access

1. Go to [Google Search Console](https://search.google.com/search-console)
2. Select your property > **Settings > Users and permissions > Add user**
3. Paste the service account `client_email` from the JSON file
4. Set permission: **Full** (read-only) or **Owner** (if using Indexing API)

## Step 5: Set Up OAuth for Interactive Flows

1. **APIs & Services > Credentials > Create Credentials > OAuth client ID**
2. Application type: **Desktop app**
3. Download the `client_secret_*.json` file
4. Store at `~/.config/codex-blog/oauth_client.json`

OAuth is needed for Keyword Planner and any user-consent flows.

## Step 6: GA4 Property ID (Tier 2)

1. Go to [Google Analytics](https://analytics.google.com)
2. **Admin > Property Access Management > Add users** (+ icon)
3. Paste the service account `client_email`, set role: **Viewer**
4. Note the numeric property ID from **Admin > Property Details** (e.g., `123456789`)

## Step 7: Google Ads Credentials (Tier 3)

1. Create a Google Ads Manager Account at ads.google.com
2. Apply for a Developer Token at Google Ads API Center
3. Note: Without active ad spend, Keyword Planner returns bucketed ranges ("1K-10K")

## Config File

Codex Blog stores its own configuration at `~/.config/codex-blog/google-api.json`:

```json
{
  "service_account_path": "~/.config/codex-blog/service_account.json",
  "api_key": "AIzaSy...",
  "oauth_client_path": "~/.config/codex-blog/oauth_client.json",
  "default_property": "sc-domain:example.com",
  "ga4_property_id": "properties/123456789",
  "ads_developer_token": "YOUR_DEV_TOKEN",
  "ads_customer_id": "123-456-7890",
  "ads_login_customer_id": "123-456-7890"
}
```

Protect the config and downloaded credential files:

```bash
chmod 700 ~/.config/codex-blog
chmod 600 ~/.config/codex-blog/google-api.json
chmod 600 ~/.config/codex-blog/service_account.json ~/.config/codex-blog/oauth_client.json
```

### GSC Property URL Formats

| Format | Example | When to Use |
|--------|---------|-------------|
| Domain property | `sc-domain:example.com` | All URLs on the domain (recommended) |
| URL-prefix property | `https://example.com/` | Only that specific prefix |

## Environment Variable Fallbacks

| Variable | Purpose |
|----------|---------|
| `CODEX_BLOG_GOOGLE_CONFIG` | Override the Codex Blog Google config-file path |
| `CODEX_BLOG_GOOGLE_TOKEN` | Override the Codex Blog OAuth token-file path |
| `GOOGLE_API_KEY` | API key for PSI/CrUX/YouTube/NLP |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to service account JSON |
| `GOOGLE_OAUTH_CLIENT_PATH` | Path to OAuth client JSON |
| `GA4_PROPERTY_ID` | GA4 property (e.g., `properties/123456789`) |
| `GSC_PROPERTY` | Default GSC property (e.g., `sc-domain:example.com`) |
| `GOOGLE_ADS_DEVELOPER_TOKEN` | Google Ads developer token |
| `GOOGLE_ADS_CUSTOMER_ID` | Google Ads customer ID |
| `GOOGLE_ADS_LOGIN_CUSTOMER_ID` | Optional manager account login customer ID |

## Verify Setup

```bash
codex-blog run blog-data/run.py google_auth --check
```

## Quick Troubleshooting

| Error | Fix |
|-------|-----|
| `403 Forbidden` on GSC | Service account email not added to property, or wrong permission level |
| `403 Forbidden` on GA4 | Service account not added as Viewer in GA4 property |
| `404 Not Found` on GSC | Wrong property URL format: use `sc-domain:` or include trailing slash |
| `404 Not Found` on CrUX | Site has insufficient Chrome traffic (not a credentials issue) |
| `429 Rate Limit` | Wait and retry with backoff. See rate-limits-quotas.md |
| `API not enabled` | Enable the specific API in GCP Console > APIs & Services > Library |
| `Billing required` | NLP API requires billing enabled (free tier still applies) |
