"""Per-provider live connectivity check for the literature-search layer.

Usage: uv run python tests/manual/check_literature_providers.py "synaptic plasticity"
Prints one line per active provider: name, status (ok/error), count, error.
Exit code 0 if every active provider returned status ok, else 1.
"""
from __future__ import annotations

import sys

from dotenv import load_dotenv

from neurodb.literature import registry


def main() -> int:
    load_dotenv()
    query = sys.argv[1] if len(sys.argv) > 1 else "synaptic plasticity"
    import httpx

    http = httpx.Client(timeout=15.0, follow_redirects=True)
    providers = registry.build_active_providers(http, timeout=15.0)
    if not providers:
        print("No active providers (check LITERATURE_PROVIDERS_DISABLED).")
        return 1
    all_ok = True
    for provider in providers:
        results, error = provider.search(query, 3)
        status = "ok" if error is None else "error"
        if error is not None:
            all_ok = False
        print(f"{provider.name:16} {status:6} count={len(results):<3} {error or ''}")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
