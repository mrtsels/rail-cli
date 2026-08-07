"""Station name <-> telecode resolution.

Station params across the CLI accept either a 3-letter telecode (e.g. IOQ)
or a Chinese station name (e.g. 深圳北). Resolution order:

1. Already a telecode (3 ASCII letters) -> pass through unchanged
2. Exact match in the bundled mapping (rail_cli/stations.json, 3382 stations)
3. Live fallback: RailGo station/preselect fuzzy search (handles new stations,
   and names with a trailing 站 suffix)

Lookup failures raise RuntimeError with a clear message so the CLI exits 1.
"""
import json
import re
import sys
from pathlib import Path

TELECODE_RE = re.compile(r"^[A-Za-z]{3}$")

_mapping: dict[str, str] | None = None


def load_mapping() -> dict[str, str]:
    """Load {name: telecode} from stations.json (lazily, once)."""
    global _mapping
    if _mapping is None:
        path = Path(__file__).resolve().parent / "stations.json"
        _mapping = json.loads(path.read_text("utf-8"))
    return _mapping


def telecode_of(name: str) -> str | None:
    """Exact lookup in the bundled mapping; also tolerates a trailing 站."""
    mapping = load_mapping()
    if name in mapping:
        return mapping[name]
    if name.endswith("站") and name[:-1] in mapping:
        return mapping[name[:-1]]
    return None


def is_telecode(arg: str) -> bool:
    """True when the argument is a bare 3-letter telecode like SZQ."""
    return bool(TELECODE_RE.match(arg.strip()))


def resolve(client, arg: str) -> str:
    """Resolve a station argument to a telecode.

    Returns the input unchanged when it is already a telecode, otherwise
    consults the bundled mapping and falls back to the live preselect API.
    """
    arg = arg.strip()
    if not arg:
        raise RuntimeError("station name/telecode cannot be empty")

    if is_telecode(arg):
        return arg.upper()

    code = telecode_of(arg)
    if code:
        if client.verbose:
            print(f"→ station: {arg} = {code} (mapping)", file=sys.stderr)
        return code

    # Live fallback: preselect returns exact-name matches first.
    try:
        hits = client.get_v1("/api/station/preselect", {"keyword": arg})
    except RuntimeError as e:
        raise RuntimeError(f"cannot resolve station {arg!r}: {e}") from None

    if not hits:
        raise RuntimeError(
            f"station not found: {arg!r}（不知道电报码？直接输站名即可，如 深圳北）"
        )

    exact = [h for h in hits if h.get("name") == arg]
    candidates = exact or hits
    if len(candidates) == 1:
        code = candidates[0]["telecode"]
        if client.verbose:
            print(f"→ station: {arg} = {code} (preselect)", file=sys.stderr)
        return code

    listed = "、".join(f"{h.get('name')}({h.get('telecode')})" for h in candidates)
    raise RuntimeError(f"station {arg!r} is ambiguous, pick one: {listed}")
