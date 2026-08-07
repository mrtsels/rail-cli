#!/usr/bin/env python3
"""Regenerate rail_cli/stations.json (station name -> telecode).

Source: 12306 official station table
  https://kyfw.12306.cn/otn/resources/js/framework/station_name.js

Entry format per station: @<key>|<name>|<telecode>|<pinyin>|...
Run: python3 tools/gen_stations.py   (writes rail_cli/stations.json)
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

SOURCE_URL = "https://kyfw.12306.cn/otn/resources/js/framework/station_name.js"
OUT_PATH = Path(__file__).resolve().parent.parent / "rail_cli" / "stations.json"

STATION_RE = re.compile(r"@[^@]*?\|([^|]+)\|([A-Za-z0-9]{3})\|")


def fetch_stations() -> dict[str, str]:
    """Fetch the 12306 station table, return {name: telecode}."""
    with urllib.request.urlopen(SOURCE_URL, timeout=30) as resp:
        body = resp.read().decode("utf-8")
    mapping: dict[str, str] = {}
    for name, telecode in STATION_RE.findall(body):
        mapping.setdefault(name, telecode)
    return mapping


def main() -> int:
    mapping = fetch_stations()
    if not mapping:
        print(f"error: no stations parsed from {SOURCE_URL}", file=sys.stderr)
        return 1
    OUT_PATH.write_text(json.dumps(mapping, ensure_ascii=False, separators=(",", ":")), "utf-8")
    print(f"wrote {OUT_PATH} ({len(mapping)} stations, {OUT_PATH.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
