"""Scripted pilot demo: python -m scripts.demo

Demo craft rules this script follows:
- run the real API, not slides (in-process TestClient);
- freeze the clock and use fixed samples, so every run is identical;
- show the messy cases on purpose and say what happens to them;
- end on the business metric the sponsor cares about.
"""

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app

SAMPLES = Path(__file__).resolve().parent.parent / "data" / "samples"
FROZEN_NOW = datetime(2026, 10, 14, 9, 0, tzinfo=UTC)

# What the front-desk reviewer does with each queued sample. In the
# live demo, a Northwind staff member clicks these, not the engineer.
REVIEW_SCRIPT: dict[str, dict[str, Any]] = {
    "03_missing_dob.txt": {
        "corrections": {"date_of_birth": "1991-06-02"},
        "note": "called patient for DOB",
    },
    "04_two_phones.txt": {
        "corrections": {"phone": "+15550103333"},
        "note": "patient asked for the daytime number",
    },
    "05_messy_forwarded.txt": {
        "corrections": {
            "email": "ana.silva@example.com",
            "reason_for_visit": "lower back pain for one month",
        },
    },
    "06_future_dob.txt": {"reject": "DOB typo; desk will call patient"},
}


def row(*cols: object) -> str:
    widths = (24, 12, 38)
    return " ".join(
        str(c)[: w - 1].ljust(w) for c, w in zip(cols, widths, strict=True)
    ).rstrip()


def main() -> None:
    settings = Settings(env="dev", auto_accept_threshold=0.85)
    client = TestClient(create_app(settings, clock=lambda: FROZEN_NOW))
    ids: dict[str, int] = {}

    print("Step 1 - intake: six real-shaped messages (fictional data)\n")
    print(row("sample", "route", "first reason"))
    print("-" * 74)
    for path in sorted(SAMPLES.glob("*.txt")):
        resp = client.post("/intake", json={"text": path.read_text()})
        resp.raise_for_status()
        sub = resp.json()
        ids[path.name] = sub["id"]
        reason = sub["reasons"][0] if sub["reasons"] else "-"
        print(row(path.name, sub["route"], reason))

    queue = client.get("/review-queue").json()
    print(f"\nStep 2 - review queue: {len(queue)} waiting for a person\n")
    for name, action in REVIEW_SCRIPT.items():
        sid = ids[name]
        if "reject" in action:
            client.post(
                f"/review/{sid}/reject",
                json={"reviewer": "desk.jo", "reason": action["reject"]},
            ).raise_for_status()
            print(f"  #{sid} {name}: rejected ({action['reject']})")
            continue
        client.post(
            f"/review/{sid}/approve",
            json={
                "reviewer": "desk.jo",
                "corrections": action["corrections"],
                "note": action.get("note"),
            },
        ).raise_for_status()
        fixed = ", ".join(action["corrections"])
        print(f"  #{sid} {name}: approved, corrected {fixed}")

    m = client.get("/metrics/summary").json()
    print("\nStep 3 - pilot metrics (GET /metrics/summary)\n")
    print(f"  total intakes         {m['total']}")
    print(f"  auto-accepted         {m['auto_accepted']}")
    print(f"  sent to review        {m['sent_to_review']}")
    print(f"  approved / rejected   {m['approved']} / {m['rejected']}")
    print(f"  auto-accept rate      {m['auto_accept_rate']:.0%}")
    print("  field correction rate (of approved reviews):")
    for field, rate in m["field_correction_rates"].items():
        if rate:
            print(f"    {field:<24} {rate:.0%}")
    print(
        "\nTalking point: every correction above is in the audit log"
        "\n(GET /intake/{id}/audit) and feeds next week's tuning."
    )


if __name__ == "__main__":
    main()
