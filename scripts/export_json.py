#!/usr/bin/env python3
"""Export the Xenari SQLite DB to data/xenari-dict.json."""

from pathlib import Path
import sys

REPO = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO))

from xenari_db import XenariDB


def main() -> None:
    db = XenariDB(REPO / "xenari.db")
    out_path = REPO / "data" / "xenari-dict.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(db.export_json(), encoding="utf-8")
    root_count = db.conn.execute("SELECT COUNT(*) FROM roots").fetchone()[0]
    map_count = db.conn.execute("SELECT COUNT(*) FROM english_map").fetchone()[0]
    db.close()
    print(f"Exported {root_count} roots and {map_count} mappings to {out_path}")


if __name__ == "__main__":
    main()
