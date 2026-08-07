"""HTTP client for RailGo API.

V1 and V2 endpoints live on different hosts (see docs/PLAN.md §0):
  V1: https://data.railgo.zenglingkun.cn/api/*
  V2: https://rg-api.zenglingkun.cn/api/v2/*
Both are overridable via environment variables.
"""
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request

V1_BASE_URL = os.environ.get("RAILGO_BASE_URL", "https://data.railgo.zenglingkun.cn")
V2_BASE_URL = os.environ.get("RAILGO_V2_BASE_URL", "https://rg-api.zenglingkun.cn")
TIMEOUT = 30  # seconds; V2 endpoints ~0.4s, generous buffer


def _log(msg: str) -> None:
    print(msg, file=sys.stderr)


class RailGoClient:
    """Lightweight HTTP client with per-version base URLs."""

    def __init__(self, verbose: bool = False):
        self.verbose = verbose

    def _request(self, base: str, path: str, params: dict | None = None) -> dict:
        url = base + path
        if params:
            cleaned = {k: v for k, v in params.items() if v is not None}
            if cleaned:
                url += "?" + urllib.parse.urlencode(cleaned)

        if self.verbose:
            _log(f"→ GET {url}")

        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as resp:
                body = resp.read().decode("utf-8")
                if self.verbose:
                    _log(f"← HTTP {resp.status} ({len(body)} bytes)")
                return json.loads(body)
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"HTTP {e.code}: {body[:300]}") from None
        except urllib.error.URLError as e:
            raise RuntimeError(f"Network error: {e.reason}") from None
        except json.JSONDecodeError:
            raise RuntimeError("Invalid JSON response") from None

    def get_v1(self, path: str, params: dict | None = None) -> dict:
        """GET a V1 endpoint (raw JSON, no wrapper)."""
        return self._request(V1_BASE_URL, path, params)

    def get_v2(self, path: str, params: dict | None = None, raw: bool = False) -> dict:
        """GET a V2 endpoint.

        By default checks the {success, msg, data} wrapper and returns `data`.
        With raw=True, returns the full response untouched (no wrapper check).
        """
        data = self._request(V2_BASE_URL, path, params)
        if raw:
            return data
        if not data.get("success", False):
            msg = data.get("msg") or "unknown error"
            raise RuntimeError(f"API error: {msg}")
        return data.get("data")
