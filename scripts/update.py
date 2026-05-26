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


CONFIG = ROOT / "config" / "sources.json"


def load_sources():
    config = read_json(CONFIG, {})
    sources = config.get("sources", [])
    if not isinstance(sources, list) or not sources:
        raise ValueError(f"no sources configured in {CONFIG}")
    ids = [source.get("id") for source in sources]
    duplicates = sorted({source_id for source_id in ids if ids.count(source_id) > 1})
    if duplicates:
        raise ValueError(f"duplicate source ids: {', '.join(duplicates)}")
    return sources


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
    for source in load_sources():
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
