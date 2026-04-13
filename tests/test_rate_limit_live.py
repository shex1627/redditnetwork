"""Live test: hit the running API to verify rate limiting works.

Usage:
    python tests/test_rate_limit_live.py [--base-url http://localhost:8550]

Sends 7 rapid POST requests to /discover. The first 5 should return 200 (or
a normal pipeline error like 400/500), and requests 6+ should return 429.
Also verifies /health is NOT rate-limited.
"""

from __future__ import annotations

import argparse
import sys
import time

import requests

DISCOVER_PAYLOAD = {
    "post_url": "https://www.reddit.com/r/Python/comments/test123/fake_post",
    "top_n_commenters": 5,
    "min_relevance": 5,
}


def test_discover_rate_limit(base_url: str, total: int = 7, limit: int = 5) -> bool:
    """Fire `total` requests and assert that request `limit+1` gets 429."""
    url = f"{base_url}/discover"
    print(f"\n--- /discover rate limit test ({limit}/min limit) ---")
    print(f"Sending {total} rapid requests to {url}\n")

    codes: list[int] = []
    for i in range(1, total + 1):
        resp = requests.post(url, json=DISCOVER_PAYLOAD, timeout=10)
        codes.append(resp.status_code)
        tag = "OK" if resp.status_code != 429 else "RATE LIMITED"
        print(f"  [{i}] {resp.status_code} {tag}")

    got_429 = any(c == 429 for c in codes)
    first_five_ok = all(c != 429 for c in codes[:limit])

    print()
    if first_five_ok and got_429:
        print("PASS: first 5 requests allowed, subsequent requests got 429")
        return True
    elif not got_429:
        print("FAIL: never received 429 — rate limiting may not be active")
        return False
    else:
        print(f"FAIL: unexpected pattern — {codes}")
        return False


def test_health_not_limited(base_url: str, total: int = 10) -> bool:
    """Verify /health is not rate-limited."""
    url = f"{base_url}/health"
    print(f"\n--- /health not-rate-limited test ---")
    print(f"Sending {total} rapid requests to {url}\n")

    codes: list[int] = []
    for i in range(1, total + 1):
        resp = requests.get(url, timeout=5)
        codes.append(resp.status_code)
        print(f"  [{i}] {resp.status_code}")

    all_ok = all(c == 200 for c in codes)
    print()
    if all_ok:
        print("PASS: /health is not rate-limited")
    else:
        print(f"FAIL: got non-200 responses — {codes}")
    return all_ok


def main() -> None:
    parser = argparse.ArgumentParser(description="Live rate-limit test")
    parser.add_argument("--base-url", default="http://localhost:8550")
    args = parser.parse_args()

    # Check the API is reachable first
    try:
        r = requests.get(f"{args.base_url}/health", timeout=5)
        r.raise_for_status()
    except requests.ConnectionError:
        print(f"ERROR: cannot connect to {args.base_url} — is the API running?")
        sys.exit(1)

    print(f"API is up at {args.base_url}")

    results = []
    results.append(test_discover_rate_limit(args.base_url))
    results.append(test_health_not_limited(args.base_url))

    print("\n" + "=" * 40)
    passed = sum(results)
    total = len(results)
    print(f"Results: {passed}/{total} passed")

    if all(results):
        print("All tests passed.")
    else:
        print("Some tests failed.")
        sys.exit(1)


if __name__ == "__main__":
    main()
