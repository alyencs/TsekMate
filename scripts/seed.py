"""Seed or reset the database. One command: python scripts/seed.py --reset

Uses Supabase when SUPABASE_URL and SUPABASE_SERVICE_KEY are set (run apps/api/db/schema.sql first).
Without them it only checks that the seed builds (the in-memory store seeds itself when the API starts).
"""
import argparse

import _path  # noqa: F401
from app.seed import build, reset_and_seed
from app.store import get_store


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reset", action="store_true", help="delete all rows and images first")
    ap.add_argument("--no-images", action="store_true", help="skip rendering the synthetic paper images")
    a = ap.parse_args()
    store = get_store()
    counts = reset_and_seed(store, with_images=not a.no_images) if a.reset else build(store, with_images=not a.no_images)
    print(f"Seeded {store.kind} store:")
    for k, v in counts.items():
        print(f"  {k:10s} needs_review={v['needs_review']:2d} ready={v['ready']:2d} approved={v['approved']:2d}")
    if store.kind == "memory":
        print("Note: no SUPABASE_URL set, so this only validated the seed. Start the API to use the in-memory store.")


if __name__ == "__main__":
    main()
