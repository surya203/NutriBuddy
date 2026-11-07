"""Check that .env can reach the NutriBuddy Supabase project."""

from __future__ import annotations

import os
import sys

import httpx
from dotenv import load_dotenv

PLACEHOLDERS = {
    "",
    "your_supabase_project_url",
    "your_server_side_key",
}


def main() -> int:
    load_dotenv()
    url = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
    key = os.getenv("SUPABASE_KEY", "").strip()
    missing = [
        name
        for name, value in (("SUPABASE_URL", url), ("SUPABASE_KEY", key))
        if value in PLACEHOLDERS or value.startswith("your_")
    ]
    if missing:
        joined = ", ".join(missing)
        print(
            f"Missing Supabase settings: {joined}. "
            "Copy .env.example to .env and set the project URL and anon key."
        )
        return 1

    headers = {
        "apikey": key,
        "Authorization": f"Bearer {key}",
    }
    try:
        with httpx.Client(timeout=20.0) as client:
            health = client.get(f"{url}/auth/v1/health", headers=headers)
            parents = client.get(
                f"{url}/rest/v1/parents",
                headers={**headers, "Accept": "application/json"},
                params={"select": "id", "limit": "1"},
            )
    except httpx.HTTPError as exc:
        print(f"Could not reach Supabase: {exc}")
        return 1

    if health.status_code != 200:
        print(
            f"Auth health check failed ({health.status_code}). "
            "Check SUPABASE_URL and SUPABASE_KEY."
        )
        return 1

    if parents.status_code == 200:
        rows = parents.json()
        visible = len(rows) if isinstance(rows, list) else 0
        print(f"Connected. parents query returned {visible} visible row(s).")
        return 0

    body = parents.text.lower()
    if parents.status_code in (401, 403) and "permission denied" in body:
        print("Connected. The anon key is accepted and the parents table exists.")
        print(
            "The anon role cannot read rows. That is expected: "
            "only a signed-in parent can."
        )
        return 0

    print(f"parents query failed ({parents.status_code}): {parents.text}")
    return 1


if __name__ == "__main__":
    sys.exit(main())
