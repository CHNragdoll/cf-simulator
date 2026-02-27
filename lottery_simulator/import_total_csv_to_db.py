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


def table_columns(conn, table: str):
    return [r[1] for r in conn.execute(f"PRAGMA table_info('{table}')").fetchall()]


def main():
    if len(sys.argv) != 2:
        print("用法: python3 import_total_csv_to_db.py <total_csv_path>")
        print("示例: python3 import_total_csv_to_db.py docs/templates/快速填写总模板.csv")
        raise SystemExit(1)

    csv_path = Path(sys.argv[1]).resolve()
    if not csv_path.exists():
        raise SystemExit(f"CSV 不存在: {csv_path}")

    conn = sqlite3.connect(DB_PATH)
    try:
        with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
            reader = csv.DictReader(f)
            if not reader.fieldnames:
                raise SystemExit("CSV 表头为空")

            mapped = [parse_header(h) for h in reader.fieldnames]
            if "table" not in mapped:
                raise SystemExit("CSV 必须包含 表名(table) 列")
            table_idx = mapped.index("table")
            raw_table_header = reader.fieldnames[table_idx]

            schema_cache = {}
            inserted = 0

            for row in reader:
                table = (row.get(raw_table_header) or "").strip()
                if not table:
                    continue

                if table not in schema_cache:
                    cols = table_columns(conn, table)
                    if not cols:
                        raise SystemExit(f"未知数据表: {table}")
                    schema_cache[table] = set(cols)

                table_cols = schema_cache[table]
                data = {}
                for raw_h, key in zip(reader.fieldnames, mapped):
                    if key == "table":
                        continue
                    if key not in table_cols:
                        continue
                    data[key] = cast_value(row.get(raw_h))

                use_cols = [k for k, v in data.items() if v is not None]
                if not use_cols:
                    continue

                vals = [data[k] for k in use_cols]
                sql = f"INSERT OR REPLACE INTO {table}({', '.join(use_cols)}) VALUES({', '.join(['?' for _ in use_cols])})"
                conn.execute(sql, vals)
                inserted += 1

        conn.commit()
        print(f"导入完成: rows={inserted}, csv={csv_path}")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
