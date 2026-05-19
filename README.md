# CrawlerScope

CrawlerScope is a static GitHub Pages dashboard and dataset for public crawler,
AI bot, SEO bot, security scanner, and monitoring probe network ranges.

It collects public operator-published sources, normalizes IPs into CIDR prefixes,
tracks source health, and ships an interactive browser UI with filters, maps,
charts, filtered exports, robots.txt snippets, and Nginx user-agent maps.

Live demo:

`https://YOUR_GITHUB_USERNAME.github.io/CrawlerScope/`

Replace the URL above after enabling GitHub Pages for your repository.

## What It Tracks

CrawlerScope separates sources by trust level:

- `official_json`: machine-readable JSON published by the operator.
- `official_text`: machine-readable plain text list published by the operator.
- `documented_user_agent`: documented crawler identity, but no official IP feed.
- `known_static`: useful public/static seed ranges, not treated as complete authority.

Current tracked groups include:

- Search crawlers: Google, Bing, DuckDuckGo, Applebot, YandexBot, Baiduspider
- AI crawlers/fetchers: OpenAI, Perplexity, Anthropic, Amazonbot, Meta, Bytespider
- SEO crawlers: AhrefsBot, SemrushBot
- Security scanners: Censys, Shodan
- Monitoring probes: Datadog Synthetics, UptimeRobot, Pingdom, Better Stack, StatusCake
- Archive/social: Common Crawl, Pinterestbot, LinkedInBot

## Dashboard Features

- Country choropleth map by operator country
- Category mix chart
- Top operators by prefix count
- Cascading filters for category, operator, source type, and service
- Search across service, operator, URL, user-agent, and category
- Quick presets for AI, official lists, and monitoring probes
- Sortable service table
- Filtered exports:
  - JSON
  - CSV
  - CIDR text list
  - robots.txt
  - Nginx map
- Copy current CIDR selection to clipboard

## Data Outputs

The collector writes:

- `data/current/crawlers.json`
- `data/current/robots-ai.txt`
- `data/current/nginx-ai-map.conf`
- `data/history/summary.csv`
- `data/snapshots/*.json`

The GitHub Pages workflow publishes:

- `public/index.html`
- `public/assets/*`
- `data/current/*`
- `data/history/*`
- `data/snapshots/*`

## Repository Structure

```text
CrawlerScope/
  .github/
    workflows/
      crawler-scope.yml
  data/
    current/
      crawlers.json
      nginx-ai-map.conf
      robots-ai.txt
    history/
      summary.csv
    snapshots/
      *.json
  public/
    assets/
      app.js
      styles.css
    index.html
  scripts/
    update.py
  .gitignore
  .nojekyll
  LICENSE
  README.md
```

Do not commit the generated `site/` directory. GitHub Actions builds it during
deployment.

## Local Preview

```bash
python3 scripts/update.py
rm -rf site
cp -R public site
cp -R data site/data
python3 -m http.server 8080 --directory site
```

Open:

```text
http://127.0.0.1:8080/
```

## GitHub Pages Setup

1. Create a new GitHub repository, for example `CrawlerScope`.
2. Upload this folder as the repository root.
3. Go to `Settings -> Pages`.
4. Set `Source` to `GitHub Actions`.
5. Go to `Actions`.
6. Run the `CrawlerScope` workflow manually once.

After the first successful run, the site will be available at:

```text
https://YOUR_GITHUB_USERNAME.github.io/CrawlerScope/
```

## Update Schedule

The workflow runs every 6 hours by default:

```yaml
schedule:
  - cron: "23 */6 * * *"
```

You can change it to every 2 hours:

```yaml
schedule:
  - cron: "23 */2 * * *"
```

Hourly updates are usually unnecessary because many sources update daily or less
often.

## Notes

- IP ranges are only as complete as the upstream source.
- User-Agent strings can be spoofed.
- Some operators document crawler names but do not publish stable IP ranges.
- Known/static ranges should be treated as operational hints, not complete truth.
- Review upstream source terms before redistributing or selling derived datasets.

## License

This repository uses CC0-1.0. See `LICENSE`.
