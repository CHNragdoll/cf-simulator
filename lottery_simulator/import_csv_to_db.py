#!/usr/bin/env python3
import csv
import re
import sqlite3
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "lottery.db"


def parse_header(cell: str) -> str:
    m = re.search(r"\(([^()]+)\)", cell or "")
    if m:
        return m.group(1).strip().split(":", 1)[0]
    return (cell or "").strip()


def cast_value(v: str):
    if v is None:
        return None
    s = str(v).strip()
    if s == "":
        return None
    if re.fullmatch(r"[-+]?\d+", s):
        return int(s)
    if re.fullmatch(r"[-+]?\d*\.\d+", s):
        return float(s)
    return s


def table_exists(conn, table: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type='table' AND name=? LIMIT 1",
        (table,),
    ).fetchone()
    return row is not None


def table_columns(conn, table: str):
    return [r[1] for r in conn.execute(f"PRAGMA table_info('{table}')").fetchall()]


def main():
    if len(sys.argv) != 3:
        print("用法: python3 import_csv_to_db.py <table_name> <csv_path>")
        print("示例: python3 import_csv_to_db.py prize_items docs/templates/快速填写模板_奖品主表.csv")
        raise SystemExit(1)

    table = sys.argv[1].strip()
    csv_path = Path(sys.argv[2]).resolve()
    if not csv_path.exists():
        raise SystemExit(f"CSV 不存在: {csv_path}")

    conn = sqlite3.connect(DB_PATH)
    try:
        if not table_exists(conn, table):
            raise SystemExit(f"数据表不存在: {table}")

        cols = set(table_columns(conn, table))

        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise SystemExit("CSV 表头为空")

            mapped = [parse_header(h) for h in reader.fieldnames]
            unknown = [c for c in mapped if c not in cols]
            if unknown:
                raise SystemExit(f"CSV 含未知字段: {unknown}")

            inserted = 0
            for row in reader:
                data = {}
                for raw_h, db_col in zip(reader.fieldnames, mapped):
                    data[db_col] = cast_value(row.get(raw_h))
                use_cols = [k for k, v in data.items() if v is not None]
                if not use_cols:
                    continue
                vals = [data[k] for k in use_cols]
                sql = f"INSERT OR REPLACE INTO {table}({', '.join(use_cols)}) VALUES({', '.join(['?' for _ in use_cols])})"
                conn.execute(sql, vals)
                inserted += 1

        conn.commit()
        print(f"导入完成: table={table}, rows={inserted}, csv={csv_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
