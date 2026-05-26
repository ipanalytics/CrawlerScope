#!/usr/bin/env python3
import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DATASET = ROOT / "data" / "current" / "crawlers.json"


def main():
    data = json.loads(DATASET.read_text())
    summary = data["summary"]
    print(f"CrawlerScope dataset generated at {data['generatedAt']}.")
    print()
    print(f"- Services: {summary['services']}")
    print(f"- Sources OK: {summary['sourcesOk']}")
    print(f"- Authoritative IP lists: {summary['authoritativeLists']}")
    print(f"- CIDR prefixes: {summary['prefixes']}")
    print(f"- IPv4 prefixes: {summary['ipv4']}")
    print(f"- IPv6 prefixes: {summary['ipv6']}")
    print(f"- AI prefixes: {summary['aiPrefixes']}")


if __name__ == "__main__":
    main()
