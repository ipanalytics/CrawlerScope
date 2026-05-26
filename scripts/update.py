#!/usr/bin/env python3
import csv
import hashlib
import ipaddress
import json
import os
import re
import sys
import urllib.error
import urllib.request
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
CURRENT = DATA / "current"
SNAPSHOTS = DATA / "snapshots"
HISTORY = DATA / "history"

USER_AGENT = os.environ.get(
    "CRAWLER_SCOPE_USER_AGENT",
    "CrawlerScope/0.1 (+https://github.com/ipanalytics/CrawlerScope/; public-data collector)",
)
RETENTION_SNAPSHOTS = int(os.environ.get("CRAWLER_SCOPE_SNAPSHOT_RETENTION", "168"))
RETENTION_HISTORY_ROWS = int(os.environ.get("CRAWLER_SCOPE_HISTORY_RETENTION", "720"))


SOURCES = [
    {
        "id": "google-common",
        "service": "Google common crawlers",
        "operator": "Google",
        "category": "search",
        "operatorCountry": "US",
        "sourceType": "official_json",
        "sourceUrl": "https://developers.google.com/static/crawling/ipranges/common-crawlers.json",
        "userAgentPatterns": ["Googlebot", "Googlebot-Image", "Googlebot-News", "Googlebot-Video"],
        "rdnsPatterns": ["*.googlebot.com", "*.google.com"],
        "authoritative": True,
    },
    {
        "id": "google-special",
        "service": "Google special crawlers",
        "operator": "Google",
        "category": "search",
        "operatorCountry": "US",
        "sourceType": "official_json",
        "sourceUrl": "https://developers.google.com/static/crawling/ipranges/special-crawlers.json",
        "userAgentPatterns": ["AdsBot-Google", "APIs-Google", "Mediapartners-Google"],
        "rdnsPatterns": ["*.google.com"],
        "authoritative": True,
    },
    {
        "id": "google-user-triggered",
        "service": "Google user-triggered fetchers",
        "operator": "Google",
        "category": "fetcher",
        "operatorCountry": "US",
        "sourceType": "official_json",
        "sourceUrl": "https://developers.google.com/static/crawling/ipranges/user-triggered-fetchers.json",
        "userAgentPatterns": ["Google-InspectionTool", "GoogleOther"],
        "rdnsPatterns": ["*.google.com"],
        "authoritative": True,
    },
    {
        "id": "bingbot",
        "service": "Bingbot",
        "operator": "Microsoft",
        "category": "search",
        "operatorCountry": "US",
        "sourceType": "official_json",
        "sourceUrl": "https://www.bing.com/toolbox/bingbot.json",
        "userAgentPatterns": ["bingbot", "adidxbot"],
        "rdnsPatterns": ["*.search.msn.com"],
        "authoritative": True,
    },
    {
        "id": "duckduckbot",
        "service": "DuckDuckBot",
        "operator": "DuckDuckGo",
        "category": "search",
        "operatorCountry": "US",
        "sourceType": "official_json",
        "sourceUrl": "https://duckduckgo.com/duckduckbot.json",
        "userAgentPatterns": ["DuckDuckBot"],
        "rdnsPatterns": ["*.duckduckgo.com"],
        "authoritative": True,
    },
    {
        "id": "duckassistbot",
        "service": "DuckAssistBot",
        "operator": "DuckDuckGo",
        "category": "ai",
        "operatorCountry": "US",
        "sourceType": "official_json",
        "sourceUrl": "https://duckduckgo.com/duckassistbot.json",
        "userAgentPatterns": ["DuckAssistBot"],
        "rdnsPatterns": ["*.duckduckgo.com"],
        "authoritative": True,
    },
    {
        "id": "applebot",
        "service": "Applebot",
        "operator": "Apple",
        "category": "search",
        "operatorCountry": "US",
        "sourceType": "official_json",
        "sourceUrl": "https://search.developer.apple.com/applebot.json",
        "userAgentPatterns": ["Applebot"],
        "rdnsPatterns": ["*.applebot.apple.com"],
        "authoritative": True,
        "documentationUrl": "https://support.apple.com/en-us/119829",
    },
    {
        "id": "mojeekbot",
        "service": "MojeekBot",
        "operator": "Mojeek",
        "category": "search",
        "operatorCountry": "GB",
        "sourceType": "official_json",
        "sourceUrl": "https://www.mojeek.com/mojeekbot.json",
        "userAgentPatterns": ["MojeekBot"],
        "rdnsPatterns": ["*.mojeek.com"],
        "authoritative": True,
    },
    {
        "id": "naver-yeti",
        "service": "Naver Yeti",
        "operator": "Naver",
        "category": "search",
        "operatorCountry": "KR",
        "sourceType": "official_json",
        "sourceUrl": "https://searchadvisor.naver.com/doc/naverbot.json",
        "userAgentPatterns": ["Yeti"],
        "rdnsPatterns": ["*.naver.com"],
        "authoritative": True,
    },
    {
        "id": "yandexbot",
        "service": "YandexBot",
        "operator": "Yandex",
        "category": "search",
        "operatorCountry": "RU",
        "sourceType": "known_static",
        "sourceUrl": "https://yandex.com/support/webmaster/robot-workings/check-yandex-robots.html",
        "userAgentPatterns": ["YandexBot"],
        "rdnsPatterns": ["*.spider.yandex.com", "*.yandex.com"],
        "authoritative": False,
        "staticPrefixes": [
            "5.45.192.0/18", "5.255.0.0/16", "37.9.0.0/16", "37.140.0.0/17",
            "77.88.0.0/18", "84.201.0.0/16", "87.250.0.0/17", "93.158.0.0/16",
            "95.108.0.0/16", "141.8.0.0/16", "178.154.0.0/17", "199.21.96.0/22",
            "213.180.192.0/19",
        ],
        "note": "Static known ranges; verify live requests with reverse DNS and forward-confirmation.",
    },
    {
        "id": "baiduspider",
        "service": "Baiduspider",
        "operator": "Baidu",
        "category": "search",
        "operatorCountry": "CN",
        "sourceType": "known_static",
        "sourceUrl": "https://www.baidu.com/search/spider.html",
        "userAgentPatterns": ["Baiduspider"],
        "rdnsPatterns": ["*.baidu.com", "*.baidu.jp"],
        "authoritative": False,
        "staticPrefixes": ["220.181.32.0/19", "61.135.168.0/21"],
        "note": "Small static seed list; not a complete authoritative Baidu crawler range list.",
    },
    {
        "id": "openai-gptbot",
        "service": "GPTBot",
        "operator": "OpenAI",
        "category": "ai",
        "operatorCountry": "US",
        "sourceType": "official_json",
        "sourceUrl": "https://openai.com/gptbot.json",
        "userAgentPatterns": ["GPTBot"],
        "rdnsPatterns": [],
        "authoritative": True,
    },
    {
        "id": "openai-searchbot",
        "service": "OAI-SearchBot",
        "operator": "OpenAI",
        "category": "ai",
        "operatorCountry": "US",
        "sourceType": "official_json",
        "sourceUrl": "https://openai.com/searchbot.json",
        "userAgentPatterns": ["OAI-SearchBot"],
        "rdnsPatterns": [],
        "authoritative": True,
    },
    {
        "id": "openai-chatgpt-user",
        "service": "ChatGPT-User",
        "operator": "OpenAI",
        "category": "ai",
        "operatorCountry": "US",
        "sourceType": "official_json",
        "sourceUrl": "https://openai.com/chatgpt-user.json",
        "userAgentPatterns": ["ChatGPT-User"],
        "rdnsPatterns": [],
        "authoritative": True,
    },
    {
        "id": "openai-adsbot",
        "service": "OAI-AdsBot",
        "operator": "OpenAI",
        "category": "ai",
        "operatorCountry": "US",
        "sourceType": "documented_user_agent",
        "sourceUrl": "https://platform.openai.com/docs/bots",
        "userAgentPatterns": ["OAI-AdsBot"],
        "rdnsPatterns": [],
        "authoritative": False,
        "note": "OpenAI documents this user-agent but does not publish a separate IP JSON list for it.",
    },
    {
        "id": "perplexitybot",
        "service": "PerplexityBot",
        "operator": "Perplexity",
        "category": "ai",
        "operatorCountry": "US",
        "sourceType": "official_json",
        "sourceUrl": "https://www.perplexity.ai/perplexitybot.json",
        "userAgentPatterns": ["PerplexityBot"],
        "rdnsPatterns": [],
        "authoritative": True,
    },
    {
        "id": "perplexity-user",
        "service": "Perplexity-User",
        "operator": "Perplexity",
        "category": "ai",
        "operatorCountry": "US",
        "sourceType": "official_json",
        "sourceUrl": "https://www.perplexity.ai/perplexity-user.json",
        "userAgentPatterns": ["Perplexity-User"],
        "rdnsPatterns": [],
        "authoritative": True,
        "note": "Official ranges may not cover stealth or browser-like crawler behavior reported by third parties.",
    },
    {
        "id": "claudebot",
        "service": "ClaudeBot / Claude-SearchBot",
        "operator": "Anthropic",
        "category": "ai",
        "operatorCountry": "US",
        "sourceType": "documented_user_agent",
        "sourceUrl": "https://support.claude.com/en/articles/8896518-what-is-claudebot",
        "userAgentPatterns": ["ClaudeBot", "Claude-SearchBot", "Claude-User"],
        "rdnsPatterns": [],
        "authoritative": False,
        "note": "Anthropic documents crawler user-agents but says it does not publish stable IP ranges.",
    },
    {
        "id": "amazonbot",
        "service": "Amazonbot",
        "operator": "Amazon",
        "category": "ai",
        "operatorCountry": "US",
        "sourceType": "official_embedded_json",
        "sourceUrl": "https://developer.amazon.com/amazonbot/ip-addresses",
        "userAgentPatterns": ["Amazonbot"],
        "rdnsPatterns": ["*.crawl.amazonbot.amazon"],
        "authoritative": True,
        "documentationUrl": "https://developer.amazon.com/support/amazonbot",
        "note": "Amazon publishes the list embedded in its developer page rather than as a standalone JSON endpoint.",
    },
    {
        "id": "amazon-searchbot",
        "service": "Amzn-SearchBot",
        "operator": "Amazon",
        "category": "ai",
        "operatorCountry": "US",
        "sourceType": "official_embedded_json",
        "sourceUrl": "https://developer.amazon.com/amazonbot/searchbot-ip-addresses",
        "userAgentPatterns": ["Amzn-SearchBot"],
        "rdnsPatterns": ["*.crawl.amazonbot.amazon"],
        "authoritative": True,
        "documentationUrl": "https://developer.amazon.com/support/amazonbot",
        "note": "Amazon publishes the list embedded in its developer page rather than as a standalone JSON endpoint.",
    },
    {
        "id": "amazon-amzn-user",
        "service": "Amzn-User",
        "operator": "Amazon",
        "category": "fetcher",
        "operatorCountry": "US",
        "sourceType": "official_embedded_json",
        "sourceUrl": "https://developer.amazon.com/amazonbot/live-ip-addresses",
        "userAgentPatterns": ["Amzn-User"],
        "rdnsPatterns": ["*.crawl.amazonbot.amazon"],
        "authoritative": True,
        "documentationUrl": "https://developer.amazon.com/support/amazonbot",
        "note": "Amazon publishes the live crawl list embedded in its developer page rather than as a standalone JSON endpoint.",
    },
    {
        "id": "meta-ai-crawlers",
        "service": "Meta-ExternalAgent / Meta-WebIndexer",
        "operator": "Meta",
        "category": "ai",
        "operatorCountry": "US",
        "sourceType": "known_static",
        "sourceUrl": "https://developers.facebook.com/docs/sharing/webmasters/crawler",
        "userAgentPatterns": ["meta-externalagent", "meta-webindexer"],
        "rdnsPatterns": [],
        "authoritative": False,
        "staticPrefixes": ["66.220.144.0/20", "69.171.224.0/19", "173.252.64.0/18", "2a03:2880::/29"],
        "note": "Static Meta platform ranges, not crawler-specific authoritative ranges.",
    },
    {
        "id": "bytespider",
        "service": "Bytespider",
        "operator": "ByteDance",
        "category": "ai",
        "operatorCountry": "CN",
        "sourceType": "documented_user_agent",
        "sourceUrl": "https://zhanzhang.toutiao.com/",
        "userAgentPatterns": ["Bytespider"],
        "rdnsPatterns": [],
        "authoritative": False,
    },
    {
        "id": "mistralai-user",
        "service": "MistralAI-User",
        "operator": "Mistral AI",
        "category": "ai",
        "operatorCountry": "FR",
        "sourceType": "official_json",
        "sourceUrl": "https://mistral.ai/mistralai-user-ips.json",
        "userAgentPatterns": ["MistralAI-User"],
        "rdnsPatterns": [],
        "authoritative": True,
    },
    {
        "id": "ahrefsbot",
        "service": "AhrefsBot",
        "operator": "Ahrefs",
        "category": "seo",
        "operatorCountry": "SG",
        "sourceType": "official_json",
        "sourceUrl": "https://api.ahrefs.com/v3/public/crawler-ip-ranges",
        "userAgentPatterns": ["AhrefsBot"],
        "rdnsPatterns": ["*.ahrefs.com", "*.ahrefs.net"],
        "authoritative": True,
        "documentationUrl": "https://help.ahrefs.com/articles/78658-what-is-the-list-of-your-ip-ranges",
    },
    {
        "id": "lumar-crawler",
        "service": "Lumar crawler",
        "operator": "Lumar",
        "category": "seo",
        "operatorCountry": "GB",
        "sourceType": "official_json",
        "sourceUrl": "https://www.lumar.io/wp-content/uploads/2026/02/lumar_ip_list_feb_2026.json",
        "userAgentPatterns": ["Lumar"],
        "rdnsPatterns": [],
        "authoritative": True,
    },
    {
        "id": "semrushbot",
        "service": "SemrushBot",
        "operator": "Semrush",
        "category": "seo",
        "operatorCountry": "US",
        "sourceType": "documented_user_agent",
        "sourceUrl": "https://www.semrush.com/bot.html",
        "userAgentPatterns": ["SemrushBot"],
        "rdnsPatterns": ["*.bot.semrush.com"],
        "authoritative": False,
    },
    {
        "id": "censys",
        "service": "Censys scanners",
        "operator": "Censys",
        "category": "security-scanner",
        "operatorCountry": "US",
        "sourceType": "known_static",
        "sourceUrl": "https://support.censys.io/",
        "userAgentPatterns": ["CensysInspect"],
        "rdnsPatterns": ["*.censys-scanner.com"],
        "authoritative": False,
        "staticPrefixes": ["198.108.66.0/23", "162.142.125.0/24"],
    },
    {
        "id": "shodan",
        "service": "Shodan scanners",
        "operator": "Shodan",
        "category": "security-scanner",
        "operatorCountry": "US",
        "sourceType": "known_static",
        "sourceUrl": "https://www.shodan.io/",
        "userAgentPatterns": ["Shodan"],
        "rdnsPatterns": ["*.shodan.io", "*.census.shodan.io"],
        "authoritative": False,
        "staticPrefixes": [
            "198.20.69.0/24", "198.20.70.0/24", "198.20.99.0/24", "71.6.0.0/16",
            "66.240.192.0/19", "82.221.105.0/24", "93.120.27.0/24",
            "185.142.236.0/24", "207.90.244.0/24",
        ],
        "note": "Community-known/static ranges; verify with reverse DNS and current Shodan documentation.",
    },
    {
        "id": "datadog-synthetics",
        "service": "Datadog Synthetics",
        "operator": "Datadog",
        "category": "monitoring",
        "operatorCountry": "US",
        "sourceType": "official_json",
        "sourceUrl": "https://ip-ranges.datadoghq.com/synthetics.json",
        "userAgentPatterns": ["Datadog/Synthetics"],
        "rdnsPatterns": [],
        "authoritative": True,
    },
    {
        "id": "ias-crawler",
        "service": "IAS crawler",
        "operator": "Integral Ad Science",
        "category": "ad-verification",
        "operatorCountry": "US",
        "sourceType": "official_json",
        "sourceUrl": "https://integralads.com/policy-docs/iasbot.json",
        "userAgentPatterns": ["IASBot"],
        "rdnsPatterns": [],
        "authoritative": True,
    },
    {
        "id": "ttd-content",
        "service": "TTD-Content crawler",
        "operator": "The Trade Desk",
        "category": "ad-verification",
        "operatorCountry": "US",
        "sourceType": "official_text",
        "sourceUrl": "https://ttd-content.adsrvr.org/ips",
        "userAgentPatterns": ["TTD-Content"],
        "rdnsPatterns": [],
        "authoritative": True,
    },
    {
        "id": "uptimerobot",
        "service": "UptimeRobot",
        "operator": "UptimeRobot",
        "category": "monitoring",
        "operatorCountry": "US",
        "sourceType": "official_text",
        "sourceUrl": "https://uptimerobot.com/inc/files/ips/IPv4andIPv6.txt",
        "userAgentPatterns": ["UptimeRobot"],
        "rdnsPatterns": [],
        "authoritative": True,
        "documentationUrl": "https://uptimerobot.com/locations",
    },
    {
        "id": "pingdom",
        "service": "Pingdom probes",
        "operator": "SolarWinds Pingdom",
        "category": "monitoring",
        "operatorCountry": "US",
        "sourceType": "official_text",
        "sourceUrl": "https://my.pingdom.com/probes/ipv4",
        "sourceUrls": [
            "https://my.pingdom.com/probes/ipv4",
            "https://my.pingdom.com/probes/ipv6",
        ],
        "userAgentPatterns": ["Pingdom.com_bot_version_1.4"],
        "rdnsPatterns": [],
        "authoritative": True,
    },
    {
        "id": "statuscake",
        "service": "StatusCake probes",
        "operator": "StatusCake",
        "category": "monitoring",
        "operatorCountry": "GB",
        "sourceType": "official_json",
        "sourceUrl": "https://app.statuscake.com/Workfloor/Locations.php?format=json",
        "userAgentPatterns": ["StatusCake"],
        "rdnsPatterns": [],
        "authoritative": True,
        "documentationUrl": "https://www.statuscake.com/kb/knowledge-base/what-are-your-ips/",
    },
    {
        "id": "better-stack",
        "service": "Better Stack probes",
        "operator": "Better Stack",
        "category": "monitoring",
        "operatorCountry": "CZ",
        "sourceType": "documented_user_agent",
        "sourceUrl": "https://betterstack.com/docs/uptime/frequently-asked-questions/",
        "userAgentPatterns": ["Better Uptime Bot"],
        "rdnsPatterns": [],
        "authoritative": False,
        "note": "Better Stack recommends user-agent identification because probe IPs may change.",
    },
    {
        "id": "ccbot",
        "service": "Common Crawl CCBot",
        "operator": "Common Crawl",
        "category": "archive",
        "operatorCountry": "US",
        "sourceType": "official_json",
        "sourceUrl": "https://index.commoncrawl.org/ccbot.json",
        "userAgentPatterns": ["CCBot"],
        "rdnsPatterns": [],
        "authoritative": True,
    },
    {
        "id": "flipboard-crawler",
        "service": "Flipboard crawler",
        "operator": "Flipboard",
        "category": "social",
        "operatorCountry": "US",
        "sourceType": "official_text",
        "sourceUrl": "https://cdn.flipboard.com/flipboard_ip.txt",
        "userAgentPatterns": ["FlipboardProxy"],
        "rdnsPatterns": [],
        "authoritative": True,
    },
    {
        "id": "parsely-crawler",
        "service": "Parse.ly crawler",
        "operator": "Parse.ly",
        "category": "analytics",
        "operatorCountry": "US",
        "sourceType": "official_json",
        "sourceUrl": "https://www.parse.ly/static/data/crawler-ips.json",
        "userAgentPatterns": ["Parsely"],
        "rdnsPatterns": [],
        "authoritative": True,
    },
    {
        "id": "pinterestbot",
        "service": "Pinterestbot",
        "operator": "Pinterest",
        "category": "social",
        "operatorCountry": "US",
        "sourceType": "documented_user_agent",
        "sourceUrl": "https://help.pinterest.com/",
        "userAgentPatterns": ["Pinterestbot"],
        "rdnsPatterns": ["*.pinterest.com"],
        "authoritative": False,
    },
    {
        "id": "linkedinbot",
        "service": "LinkedInBot",
        "operator": "LinkedIn",
        "category": "social",
        "operatorCountry": "US",
        "sourceType": "documented_user_agent",
        "sourceUrl": "https://www.linkedin.com/legal/lad",
        "userAgentPatterns": ["LinkedInBot"],
        "rdnsPatterns": [],
        "authoritative": False,
    },
]


def fetch_json(url, timeout=60):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "application/json,text/plain,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8", "replace"))


def fetch_text(url, timeout=60):
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/plain,application/json,*/*",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return response.read().decode("utf-8", "replace")


def read_json(path, default):
    try:
        with path.open() as f:
            return json.load(f)
    except FileNotFoundError:
        return default


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w") as f:
        json.dump(value, f, indent=2, sort_keys=True)
        f.write("\n")
    tmp.replace(path)


def extract_prefixes(payload):
    prefixes = []
    if isinstance(payload, dict):
        for key in ("ipv4Prefix", "ipv6Prefix", "prefix", "cidr", "ip", "ipv4", "ipv6", "ip_address", "ip_prefix"):
            value = payload.get(key)
            if value:
                prefixes.append(value)
        for item in payload.get("prefixes", []):
            if isinstance(item, str):
                prefixes.append(item)
            elif isinstance(item, dict):
                for key in ("ipv4Prefix", "ipv6Prefix", "prefix", "cidr", "ip", "ipv4", "ipv6", "ip_address", "ip_prefix"):
                    value = item.get(key)
                    if value:
                        prefixes.append(value)
        for key in ("ipv4", "ipv6", "ranges", "ips"):
            value = payload.get(key)
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        prefixes.extend(extract_prefixes(item))
                    else:
                        prefixes.append(str(item))
        for key in ("prefixes_ipv4", "prefixes_ipv6"):
            value = payload.get(key)
            if isinstance(value, list):
                prefixes.extend(str(item) for item in value)
        for value in payload.values():
            if isinstance(value, dict):
                prefixes.extend(extract_prefixes(value))
            elif isinstance(value, list):
                prefixes.extend(extract_prefixes(value))
    elif isinstance(payload, list):
        for item in payload:
            if isinstance(item, str):
                prefixes.append(item)
            else:
                prefixes.extend(extract_prefixes(item))
    return normalize_prefixes(prefixes)


def extract_text_prefixes(text):
    ipv4 = r"(?:25[0-5]|2[0-4]\d|1?\d?\d)(?:\.(?:25[0-5]|2[0-4]\d|1?\d?\d)){3}(?:/\d{1,2})?"
    ipv6 = r"(?:[0-9A-Fa-f]{0,4}:){2,}[0-9A-Fa-f:.]{0,39}(?:/\d{1,3})?"
    candidates = re.findall(rf"(?<![A-Za-z0-9_.:-])(?:{ipv4}|{ipv6})(?![A-Za-z0-9_.:-])", text)
    return normalize_prefixes(candidates)


def extract_embedded_prefixes(text):
    fields = r"(?:ipv4Prefix|ipv6Prefix|ip_prefix|prefix|cidr|ip|ipv4|ipv6|ip_address)"
    candidates = re.findall(rf'"{fields}"\s*:\s*"([^"]+)"', text)
    return normalize_prefixes(candidates)


def normalize_prefixes(prefixes):
    networks = []
    for prefix in prefixes:
        try:
            networks.append(ipaddress.ip_network(str(prefix).strip(), strict=False))
        except ValueError:
            continue
    ipv4 = [network for network in networks if network.version == 4]
    ipv6 = [network for network in networks if network.version == 6]
    collapsed = list(ipaddress.collapse_addresses(ipv4)) + list(ipaddress.collapse_addresses(ipv6))
    return [str(network) for network in collapsed]


def split_families(prefixes):
    ipv4, ipv6 = [], []
    for prefix in prefixes:
        network = ipaddress.ip_network(prefix)
        if network.version == 4:
            ipv4.append(prefix)
        else:
            ipv6.append(prefix)
    return ipv4, ipv6


def prefix_hash(prefixes):
    digest = hashlib.sha256("\n".join(sorted(prefixes)).encode()).hexdigest()
    return digest[:16]


def service_record(source, prefixes, generated_at, error=None):
    ipv4, ipv6 = split_families(prefixes)
    record = {
        "id": source["id"],
        "service": source["service"],
        "operator": source["operator"],
        "category": source["category"],
        "operatorCountry": source["operatorCountry"],
        "sourceType": source["sourceType"],
        "sourceUrl": source["sourceUrl"],
        "sourceUrls": source.get("sourceUrls", [source["sourceUrl"]]),
        "documentationUrl": source.get("documentationUrl"),
        "sourceOk": error is None,
        "sourceError": error,
        "ipListAuthoritative": bool(source.get("authoritative")),
        "userAgentPatterns": source.get("userAgentPatterns", []),
        "rdnsPatterns": source.get("rdnsPatterns", []),
        "note": source.get("note"),
        "lastCheckedAt": generated_at,
        "prefixHash": prefix_hash(prefixes),
        "counts": {
            "prefixes": len(prefixes),
            "ipv4": len(ipv4),
            "ipv6": len(ipv6),
        },
        "prefixes": {
            "ipv4": ipv4,
            "ipv6": ipv6,
        },
    }
    return record


def append_csv(path, fieldnames, row, max_rows):
    old_rows = []
    if path.exists():
        with path.open() as f:
            old_rows = list(csv.DictReader(f))
    old_rows.append({key: row.get(key, "") for key in fieldnames})
    old_rows = old_rows[-max_rows:]
    with path.open("w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(old_rows)


def build_robots(services):
    lines = [
        "# Generated by CrawlerScope",
        "# Review before deploying. Some bots are useful for search visibility.",
        "",
    ]
    for service in services:
        if service["category"] != "ai":
            continue
        for ua in service["userAgentPatterns"]:
            lines.extend([f"User-agent: {ua}", "Disallow: /", ""])
    return "\n".join(lines).rstrip() + "\n"


def build_nginx_map(services):
    lines = [
        "# Generated by CrawlerScope",
        "map $http_user_agent $crawler_scope_ai_bot {",
        "    default 0;",
    ]
    for service in services:
        if service["category"] != "ai":
            continue
        for ua in service["userAgentPatterns"]:
            safe = ua.replace("/", "\\/")
            lines.append(f"    ~*{safe} 1;")
    lines.append("}")
    return "\n".join(lines) + "\n"


def build_insights(summary, previous, services):
    previous_summary = previous.get("summary", {})
    delta_prefixes = summary["prefixes"] - int(previous_summary.get("prefixes", summary["prefixes"]) or 0)
    ai_prefixes = sum(s["counts"]["prefixes"] for s in services if s["category"] == "ai")
    official = sum(1 for s in services if s["sourceOk"] and s["ipListAuthoritative"])
    top_service = max(services, key=lambda item: item["counts"]["prefixes"], default=None)
    insights = [
        {
            "title": "Prefix movement",
            "value": f"{delta_prefixes:+d}",
            "detail": "Total CIDR prefix change since the previous snapshot.",
        },
        {
            "title": "AI crawler footprint",
            "value": str(ai_prefixes),
            "detail": "CIDR prefixes currently attributed to AI crawler/fetcher services.",
        },
        {
            "title": "Official coverage",
            "value": f"{official}/{len(services)}",
            "detail": "Services with authoritative published IP lists available in this run.",
        },
    ]
    if top_service:
        insights.append(
            {
                "title": "Largest source",
                "value": top_service["service"],
                "detail": f"{top_service['counts']['prefixes']} CIDR prefixes after aggregation.",
            }
        )
    return insights


def main():
    now = datetime.now(timezone.utc).replace(microsecond=0)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    generated_at = now.isoformat().replace("+00:00", "Z")
    CURRENT.mkdir(parents=True, exist_ok=True)
    SNAPSHOTS.mkdir(parents=True, exist_ok=True)
    HISTORY.mkdir(parents=True, exist_ok=True)

    previous = read_json(CURRENT / "crawlers.json", {})
    previous_services = {service["id"]: service for service in previous.get("services", [])}
    services = []
    for source in SOURCES:
        prefixes = normalize_prefixes(source.get("staticPrefixes", []))
        error = None
        if source["sourceType"] == "official_json":
            try:
                prefixes = extract_prefixes(fetch_json(source["sourceUrl"]))
            except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
                error = str(exc)
                cached = previous_services.get(source["id"])
                if cached:
                    prefixes = cached["prefixes"]["ipv4"] + cached["prefixes"]["ipv6"]
        elif source["sourceType"] == "official_text":
            try:
                text = "\n".join(fetch_text(url) for url in source.get("sourceUrls", [source["sourceUrl"]]))
                prefixes = extract_text_prefixes(text)
            except (urllib.error.URLError, TimeoutError) as exc:
                error = str(exc)
                cached = previous_services.get(source["id"])
                if cached:
                    prefixes = cached["prefixes"]["ipv4"] + cached["prefixes"]["ipv6"]
        elif source["sourceType"] == "official_embedded_json":
            try:
                text = fetch_text(source["sourceUrl"])
                prefixes = extract_embedded_prefixes(text)
            except (urllib.error.URLError, TimeoutError) as exc:
                error = str(exc)
                cached = previous_services.get(source["id"])
                if cached:
                    prefixes = cached["prefixes"]["ipv4"] + cached["prefixes"]["ipv6"]
        services.append(service_record(source, prefixes, generated_at, error))

    category_counts = Counter(service["category"] for service in services)
    operator_counts = Counter()
    country_counts = Counter()
    prefix_total = 0
    ipv4_total = 0
    ipv6_total = 0
    for service in services:
        count = service["counts"]["prefixes"]
        prefix_total += count
        ipv4_total += service["counts"]["ipv4"]
        ipv6_total += service["counts"]["ipv6"]
        operator_counts[service["operator"]] += count
        country_counts[service["operatorCountry"]] += count

    summary = {
        "services": len(services),
        "sourcesOk": sum(1 for service in services if service["sourceOk"]),
        "authoritativeLists": sum(1 for service in services if service["ipListAuthoritative"]),
        "prefixes": prefix_total,
        "ipv4": ipv4_total,
        "ipv6": ipv6_total,
        "aiPrefixes": sum(s["counts"]["prefixes"] for s in services if s["category"] == "ai"),
    }
    output = {
        "generatedAt": generated_at,
        "summary": summary,
        "aggregates": {
            "categories": dict(category_counts),
            "operators": [{"key": k, "count": v} for k, v in operator_counts.most_common()],
            "operatorCountries": [{"key": k, "count": v} for k, v in country_counts.most_common()],
        },
        "insights": build_insights(summary, previous, services),
        "services": services,
    }

    write_json(CURRENT / "crawlers.json", output)
    write_json(SNAPSHOTS / f"{stamp}.json", output)
    (CURRENT / "robots-ai.txt").write_text(build_robots(services))
    (CURRENT / "nginx-ai-map.conf").write_text(build_nginx_map(services))
    append_csv(
        HISTORY / "summary.csv",
        ["generatedAt", *summary.keys()],
        {"generatedAt": generated_at, **summary},
        RETENTION_HISTORY_ROWS,
    )

    snapshots = sorted(SNAPSHOTS.glob("*.json"))
    for path in snapshots[:-RETENTION_SNAPSHOTS]:
        path.unlink()
    print(f"generated services={summary['services']} prefixes={summary['prefixes']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"update failed: {exc}", file=sys.stderr)
        sys.exit(1)
