"""Verify Phase 4 chat SSE emits context_summary before model text."""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Post a Phase 4 chat turn and stop after the context_summary SSE event."
    )
    parser.add_argument(
        "--url",
        default="http://127.0.0.1:8001/api/chat/turn",
        help="Chat turn endpoint.",
    )
    parser.add_argument("--active-focus-id", type=int, default=1)
    parser.add_argument(
        "--message",
        default="Explain cortical remapping after stroke.",
    )
    parser.add_argument("--max-events", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=20.0)
    args = parser.parse_args()

    body = {
        "agent_mode": "neuro_tutor",
        "context_mode": "contextual",
        "active_focus_type": "topic",
        "active_focus_id": args.active_focus_id,
        "history": [],
        "message": args.message,
    }
    request = urllib.request.Request(
        args.url,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    started = time.monotonic()
    event_count = 0
    first_event_type: str | None = None
    saw_context_summary = False

    try:
        with urllib.request.urlopen(request, timeout=args.timeout) as response:
            while event_count < args.max_events and time.monotonic() - started < args.timeout:
                raw = response.readline()
                if not raw:
                    break
                line = raw.decode("utf-8").strip()
                if not line.startswith("data: "):
                    continue
                payload = line.removeprefix("data: ").strip()
                if not payload:
                    continue
                event = json.loads(payload)
                event_type = event.get("type")
                first_event_type = first_event_type or event_type
                event_count += 1
                print(json.dumps(event, sort_keys=True))
                if event_type == "context_summary":
                    saw_context_summary = True
                    break
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        print(f"HTTP error: {exc.code} {detail}", file=sys.stderr)
        return 1
    except TimeoutError:
        print("Timed out waiting for SSE events.", file=sys.stderr)
        return 1

    if not saw_context_summary:
        print(
            f"FAIL: no context_summary seen in first {event_count} SSE events.",
            file=sys.stderr,
        )
        return 1
    if first_event_type != "context_summary":
        print(
            f"FAIL: first SSE event was {first_event_type!r}, expected 'context_summary'.",
            file=sys.stderr,
        )
        return 1

    print("PASS: context_summary was the first SSE event.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
