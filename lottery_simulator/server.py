#!/usr/bin/env python3
import json
import math
import os
import random
import re
import sqlite3
import threading
import time
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

BASE_DIR = Path(__file__).resolve().parent
STATIC_DIR = BASE_DIR / "static"
STATE_PATH = BASE_DIR / "data" / "state.json"
DB_PATH = BASE_DIR / "data" / "lottery.db"
HOST = "127.0.0.1"
PORT = int(os.environ.get("CF_SIM_PORT", "18081"))

LOCK = threading.Lock()
SIM_JOBS = {}
SIM_JOBS_LOCK = threading.Lock()

DB_ADMIN_TABLE_LABELS = {
    "purchase_options": "购买选项",
    "points_groups": "积分组",
    "prize_items": "奖品主表",
    "pool_layout_settings": "奖池布局设置",
    "pool_palette_priority": "颜色优先级",
    "popup_highlight_rules": "弹窗高亮规则",
    "system_settings": "系统全局设置",
    "schema_migrations": "迁移记录",
}

DB_ADMIN_COLUMN_LABELS = {
    "option_key": "选项键",
    "label": "显示名称",
    "price": "价格(元)",
    "keys_count": "钥匙数量",
    "group_key": "积分组键",
    "name": "名称",
    "image_url": "图片地址",
    "card_bg_color": "卡片背景",
    "palette_key": "颜色等级",
    "sort_order": "排序",
    "item_id": "道具ID",
    "item_type": "道具类型",
    "in_pool": "是否进奖池(0/1)",
    "pool_weight": "奖池权重",
    "points_value": "积分值",
    "exchange_points": "兑换积分",
    "decompose_points": "分解得积分",
    "decompose_keys": "分解得钥匙",
    "direct_to_warehouse": "直发仓库(0/1)",
    "popup_image_url": "弹窗图片",
    "redeem_limit_enabled": "限兑开关(0/1)",
    "redeem_limit_count": "限兑数量",
    "redeem_tag_left": "兑换左标签",
    "redeem_tag_right": "兑换右标签",
    "setting_key": "配置键",
    "setting_value": "配置值",
    "priority": "优先级",
    "enabled": "启用(0/1)",
    "migration_key": "迁移键",
    "applied_at": "执行时间戳",
}

DB_ADMIN_BOOLEAN_COLUMNS = {
    "in_pool",
    "direct_to_warehouse",
    "redeem_limit_enabled",
    "enabled",
}


def _db_admin_tables(conn):
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
    ).fetchall()
    return [r["name"] for r in rows]


def _db_admin_schema(conn, table_name):
    return [
        {
            "name": r["name"],
            "type": (r["type"] or "TEXT").upper(),
            "notnull": int(r["notnull"]),
            "default": r["dflt_value"],
            "pk": int(r["pk"]),
            "label_zh": DB_ADMIN_COLUMN_LABELS.get(r["name"], r["name"]),
        }
        for r in conn.execute(f"PRAGMA table_info('{table_name}')").fetchall()
    ]


def _db_admin_validate_table(conn, table_name):
    if not isinstance(table_name, str) or not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", table_name):
        return False
    return table_name in set(_db_admin_tables(conn))


def _default_state():
    return {
        "money_spent": 0,
        "keys": 0,
        "points": 0,
        "total_draws": 0,
        "draw_counts": {},
        "redeem_counts": {},
        "redeem_item_counts": {},
        "decompose_counts": {},
        "stash": {},
        "stash_records": [],
        "stash_record_seq": 0,
        "warehouse": {},
        "warehouse_draw": {},
        "redeem_logs": [],
        "history": [],
    }


def _read_json(path: Path, default):
    if not path.exists():
        return json.loads(json.dumps(default))
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_state():
    state = _read_json(STATE_PATH, _default_state())
    # Backward compatibility with older state file.
    if "warehouse" not in state:
        state["warehouse"] = {}
    if "decompose_counts" not in state:
        state["decompose_counts"] = {}
    if "redeem_item_counts" not in state:
        state["redeem_item_counts"] = {}
    if "stash_records" not in state:
        state["stash_records"] = []
    if "stash_record_seq" not in state:
        state["stash_record_seq"] = 0
    if "redeem_logs" not in state:
        state["redeem_logs"] = []
    if "warehouse_draw" not in state:
        state["warehouse_draw"] = {}
        for h in state.get("history", []):
            if h.get("type") == "item" and h.get("destination") == "warehouse" and h.get("id"):
                bump(state["warehouse_draw"], h["id"], 1)
    return state


def save_state(state):
    _write_json(STATE_PATH, state)


def bump(counter, key, amount=1):
    counter[key] = int(counter.get(key, 0)) + int(amount)


def append_stash_record(state, item_id, name):
    seq = int(state.get("stash_record_seq", 0)) + 1
    state["stash_record_seq"] = seq
    state.setdefault("stash_records", []).append(
        {
            "record_id": seq,
            "item_id": item_id,
            "name": name,
            "status": "pending",
            "created_ts": __import__("time").time(),
        }
    )


def db_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def _migration_done(cur, migration_key):
    row = cur.execute(
        "SELECT 1 FROM schema_migrations WHERE migration_key=? LIMIT 1",
        (migration_key,),
    ).fetchone()
    return row is not None


def _mark_migration_done(cur, migration_key):
    cur.execute(
        "INSERT OR IGNORE INTO schema_migrations(migration_key,applied_at) VALUES(?,?)",
        (migration_key, int(time.time())),
    )


def get_system_setting(conn, key, default_value=""):
    row = conn.execute(
        "SELECT setting_value FROM system_settings WHERE setting_key=?",
        (key,),
    ).fetchone()
    if not row:
        return default_value
    return row["setting_value"]


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = db_conn()
    cur = conn.cursor()

    cur.executescript(
        """
        CREATE TABLE IF NOT EXISTS purchase_options (
          option_key TEXT PRIMARY KEY,
          label TEXT NOT NULL,
          price INTEGER NOT NULL,
          keys_count INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS points_groups (
          group_key TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          image_url TEXT NOT NULL DEFAULT '',
          card_bg_color TEXT NOT NULL DEFAULT '',
          palette_key TEXT NOT NULL DEFAULT 'gray',
          sort_order INTEGER NOT NULL DEFAULT 100
        );

        CREATE TABLE IF NOT EXISTS prize_items (
          item_id TEXT PRIMARY KEY,
          name TEXT NOT NULL,
          item_type TEXT NOT NULL CHECK(item_type IN ('item','points_child')),
          in_pool INTEGER NOT NULL DEFAULT 1,
          pool_weight REAL NOT NULL DEFAULT 0,
          group_key TEXT,
          points_value INTEGER NOT NULL DEFAULT 0,
          exchange_points INTEGER NOT NULL DEFAULT 0,
          decompose_points INTEGER NOT NULL DEFAULT 0,
          decompose_keys INTEGER NOT NULL DEFAULT 0,
          direct_to_warehouse INTEGER NOT NULL DEFAULT 0,
          image_url TEXT NOT NULL DEFAULT '',
          popup_image_url TEXT NOT NULL DEFAULT '',
          card_bg_color TEXT NOT NULL DEFAULT '',
          palette_key TEXT NOT NULL DEFAULT 'orange',
          redeem_limit_enabled INTEGER NOT NULL DEFAULT 0,
          redeem_limit_count INTEGER NOT NULL DEFAULT 0,
          redeem_tag_left TEXT NOT NULL DEFAULT '',
          redeem_tag_right TEXT NOT NULL DEFAULT '不可交易',
          sort_order INTEGER NOT NULL DEFAULT 100,
          FOREIGN KEY(group_key) REFERENCES points_groups(group_key)
        );

        CREATE TABLE IF NOT EXISTS pool_layout_settings (
          setting_key TEXT PRIMARY KEY,
          setting_value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS pool_palette_priority (
          palette_key TEXT PRIMARY KEY,
          priority INTEGER NOT NULL
        );

        CREATE TABLE IF NOT EXISTS popup_highlight_rules (
          palette_key TEXT PRIMARY KEY,
          enabled INTEGER NOT NULL DEFAULT 0
        );

        CREATE TABLE IF NOT EXISTS system_settings (
          setting_key TEXT PRIMARY KEY,
          setting_value TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS schema_migrations (
          migration_key TEXT PRIMARY KEY,
          applied_at INTEGER NOT NULL
        );
        """
    )

    # Backward migration for old DB schema.
    cols = {r["name"] for r in cur.execute("PRAGMA table_info(prize_items)").fetchall()}
    if "popup_image_url" not in cols:
        cur.execute("ALTER TABLE prize_items ADD COLUMN popup_image_url TEXT NOT NULL DEFAULT ''")
    if "palette_key" not in cols:
        cur.execute("ALTER TABLE prize_items ADD COLUMN palette_key TEXT NOT NULL DEFAULT 'orange'")
    if "redeem_limit_enabled" not in cols:
        cur.execute("ALTER TABLE prize_items ADD COLUMN redeem_limit_enabled INTEGER NOT NULL DEFAULT 0")
    if "redeem_limit_count" not in cols:
        cur.execute("ALTER TABLE prize_items ADD COLUMN redeem_limit_count INTEGER NOT NULL DEFAULT 0")
    if "redeem_tag_left" not in cols:
        cur.execute("ALTER TABLE prize_items ADD COLUMN redeem_tag_left TEXT NOT NULL DEFAULT ''")
    if "redeem_tag_right" not in cols:
        cur.execute("ALTER TABLE prize_items ADD COLUMN redeem_tag_right TEXT NOT NULL DEFAULT '不可交易'")

    group_cols = {r["name"] for r in cur.execute("PRAGMA table_info(points_groups)").fetchall()}
    if "palette_key" not in group_cols:
        cur.execute("ALTER TABLE points_groups ADD COLUMN palette_key TEXT NOT NULL DEFAULT 'gray'")

    cur.execute("SELECT COUNT(*) AS c FROM purchase_options")
    if cur.fetchone()["c"] == 0:
        cur.executemany(
            "INSERT INTO purchase_options(option_key,label,price,keys_count) VALUES(?,?,?,?)",
            [
                ("single", "10元1抽", 10, 1),
                ("bundle", "100元11抽", 100, 11),
            ],
        )

    cur.execute("SELECT COUNT(*) AS c FROM points_groups")
    if cur.fetchone()["c"] == 0:
        cur.execute(
            "INSERT INTO points_groups(group_key,name,image_url,card_bg_color,palette_key,sort_order) VALUES(?,?,?,?,?,?)",
            ("points_pool", "积分", "", "linear-gradient(180deg,#dcdcdc 0%,#c5c5c5 66%,#efefef 66%,#efefef 100%)", "gray", 99),
        )

    cur.execute("SELECT COUNT(*) AS c FROM prize_items")
    if cur.fetchone()["c"] == 0:
        cur.executemany(
            """
            INSERT INTO prize_items(
              item_id,name,item_type,in_pool,pool_weight,group_key,points_value,
              exchange_points,decompose_points,decompose_keys,direct_to_warehouse,
              image_url,popup_image_url,card_bg_color,palette_key,sort_order
            ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                ("legend_haojie", "传说浩劫", "item", 1, 0.08, None, 0, 2000, 200, 0, 0, "/images/dhdj1_d58213e7ca.png", "/images/dhdj1_d58213e7ca.png", "linear-gradient(180deg,#ff5a43 0%,#db2a16 66%,#ffc1b9 66%,#ffc1b9 100%)", "red", 1),
                ("legend_elisha", "传说艾丽莎", "item", 1, 0.08, None, 0, 2000, 200, 0, 0, "/images/dhdj2_d678bb03ee.png", "/images/dhdj2_d678bb03ee.png", "linear-gradient(180deg,#ff5a43 0%,#db2a16 66%,#ffc1b9 66%,#ffc1b9 100%)", "red", 2),
                ("king_yanwu", "王者炎武", "item", 1, 0.25, None, 0, 1200, 120, 0, 0, "/images/dhdj3_34c4f9c45b.png", "/images/dhdj3_34c4f9c45b.png", "linear-gradient(180deg,#ff9d00 0%,#f78b00 66%,#f3d8b2 66%,#f3d8b2 100%)", "orange", 3),
                ("usp_mingwang", "USP-冥王", "item", 1, 0.45, None, 0, 900, 90, 0, 0, "/images/dhdj4_230a77a4de.png", "/images/dhdj4_230a77a4de.png", "linear-gradient(180deg,#ff9d00 0%,#f78b00 66%,#f3d8b2 66%,#f3d8b2 100%)", "orange", 4),
                ("g36c_sound_card", "G36C-幻影音效卡", "item", 1, 0.9, None, 0, 600, 60, 0, 0, "/images/dhdj5_5f3158a869.png", "/images/dhdj5_5f3158a869.png", "linear-gradient(180deg,#8f59e2 0%,#7a44c8 66%,#c8b6ea 66%,#c8b6ea 100%)", "purple", 5),
                ("leishen_ziyi_skin", "雷神-紫意 皮肤", "item", 1, 1.2, None, 0, 700, 70, 0, 0, "/images/dhdj6_e786a708f7.png", "/images/dhdj6_e786a708f7.png", "linear-gradient(180deg,#8f59e2 0%,#7a44c8 66%,#c8b6ea 66%,#c8b6ea 100%)", "purple", 6),
                ("longxiao_ziyi_skin", "龙啸-紫意 皮肤", "item", 1, 1.3, None, 0, 700, 70, 0, 0, "/images/dhdj7_cff238656c.png", "/images/dhdj7_cff238656c.png", "linear-gradient(180deg,#8f59e2 0%,#7a44c8 66%,#c8b6ea 66%,#c8b6ea 100%)", "purple", 7),
                ("longxiao_sound_card", "龙啸音效卡", "item", 1, 1.5, None, 0, 500, 50, 0, 0, "/images/dhdj8_35ca1762e7.png", "/images/dhdj8_35ca1762e7.png", "linear-gradient(180deg,#8f59e2 0%,#7a44c8 66%,#c8b6ea 66%,#c8b6ea 100%)", "purple", 8),
                ("m4a1_leishen", "M4A1-雷神", "item", 1, 1.8, None, 0, 550, 55, 0, 0, "/images/dhdj9_75df578690.png", "/images/dhdj9_75df578690.png", "linear-gradient(180deg,#8f59e2 0%,#7a44c8 66%,#c8b6ea 66%,#c8b6ea 100%)", "purple", 9),
                ("longxiao", "龙啸", "item", 1, 2.1, None, 0, 450, 45, 0, 0, "/images/dhdj10_87dfdc4d4e.png", "/images/dhdj10_87dfdc4d4e.png", "linear-gradient(180deg,#8f59e2 0%,#7a44c8 66%,#c8b6ea 66%,#c8b6ea 100%)", "purple", 10),
                ("xuanwu_projection", "玄武投影", "item", 1, 2.4, None, 0, 300, 30, 0, 0, "/images/dhdj11_2dcf084298.png", "/images/dhdj11_2dcf084298.png", "linear-gradient(180deg,#4f93ff 0%,#367af0 66%,#bfd7ff 66%,#bfd7ff 100%)", "blue", 11),
                ("king_stone", "王者之石×1", "item", 1, 5.5, None, 0, 0, 0, 0, 1, "/cf_images/lot/lot10.png", "/cf_images/lot/lot10.png", "linear-gradient(180deg,#dcdcdc 0%,#c5c5c5 66%,#efefef 66%,#efefef 100%)", "gray", 12),
                ("points_18", "18积分", "points_child", 1, 2.0, "points_pool", 18, 0, 0, 0, 0, "", "", "", "gray", 200),
                ("points_8", "8积分", "points_child", 1, 8.0, "points_pool", 8, 0, 0, 0, 0, "", "", "", "gray", 201),
                ("points_7", "7积分", "points_child", 1, 15.0, "points_pool", 7, 0, 0, 0, 0, "", "", "", "gray", 202),
                ("points_6", "6积分", "points_child", 1, 30.0, "points_pool", 6, 0, 0, 0, 0, "", "", "", "gray", 203),
                ("points_5", "5积分", "points_child", 1, 45.0, "points_pool", 5, 0, 0, 0, 0, "", "", "", "gray", 204),
                ("redeem_trade_key_x5", "交易专用钥匙×5", "item", 0, 0, None, 0, 25, 0, 0, 0, "/images/dhdj12_1fc241fca7.png", "/images/dhdj12_1fc241fca7.png", "linear-gradient(180deg,#e5e5e5 0%,#d1d1d1 66%,#f4f4f4 66%,#f4f4f4 100%)", "gray", 300),
                ("redeem_attr_ticket_x5", "属性变更券×5", "item", 0, 0, None, 0, 30, 0, 0, 0, "/images/dhdj13_cae378856f.png", "/images/dhdj13_cae378856f.png", "linear-gradient(180deg,#e5e5e5 0%,#d1d1d1 66%,#f4f4f4 66%,#f4f4f4 100%)", "gray", 301),
                ("redeem_trade_key_x1", "交易专用钥匙×1", "item", 0, 0, None, 0, 5, 0, 0, 0, "/images/dhdj14_e7a6568317.png", "/images/dhdj14_e7a6568317.png", "linear-gradient(180deg,#e5e5e5 0%,#d1d1d1 66%,#f4f4f4 66%,#f4f4f4 100%)", "gray", 302),
                ("redeem_attr_ticket_x1", "属性变更券×1", "item", 0, 0, None, 0, 8, 0, 0, 0, "/images/dhdj15_cec6d0990e.png", "/images/dhdj15_cec6d0990e.png", "linear-gradient(180deg,#e5e5e5 0%,#d1d1d1 66%,#f4f4f4 66%,#f4f4f4 100%)", "gray", 303),
            ],
        )

    cur.execute("SELECT COUNT(*) AS c FROM pool_layout_settings")
    if cur.fetchone()["c"] == 0:
        cur.execute("INSERT INTO pool_layout_settings(setting_key,setting_value) VALUES(?,?)", ("ring_rows", "3"))

    cur.execute("SELECT COUNT(*) AS c FROM pool_palette_priority")
    if cur.fetchone()["c"] == 0:
        cur.executemany(
            "INSERT INTO pool_palette_priority(palette_key,priority) VALUES(?,?)",
            [("red", 1), ("orange", 2), ("purple", 3), ("blue", 4), ("gray", 5)],
        )

    cur.execute("SELECT COUNT(*) AS c FROM popup_highlight_rules")
    if cur.fetchone()["c"] == 0:
        cur.executemany(
            "INSERT INTO popup_highlight_rules(palette_key,enabled) VALUES(?,?)",
            [("red", 1), ("orange", 1), ("purple", 1), ("blue", 1), ("gray", 0)],
        )

    cur.executemany(
        "INSERT OR IGNORE INTO system_settings(setting_key,setting_value) VALUES(?,?)",
        [
            ("points_image_url", "/cf_images/jifen.png"),
            ("redeem_destination", "warehouse"),
        ],
    )

    # Backfill defaults only for blank values so DB edits remain authoritative.
    cur.execute("UPDATE prize_items SET palette_key='orange' WHERE item_type='item' AND palette_key=''")
    cur.execute("UPDATE points_groups SET palette_key='gray' WHERE palette_key=''")

    # One-time migration for old datasets that had no redeem limits configured.
    migration_key = "redeem_limit_default_v1"
    if not _migration_done(cur, migration_key):
        stat = cur.execute(
            """
            SELECT
              SUM(CASE WHEN exchange_points>0 THEN 1 ELSE 0 END) AS total_redeemable,
              SUM(CASE WHEN exchange_points>0 AND redeem_limit_enabled=1 THEN 1 ELSE 0 END) AS limited_redeemable
            FROM prize_items
            """
        ).fetchone()
        total_redeemable = int(stat["total_redeemable"] or 0)
        limited_redeemable = int(stat["limited_redeemable"] or 0)
        if total_redeemable > 0 and limited_redeemable == 0:
            cur.execute("UPDATE prize_items SET redeem_limit_enabled=1, redeem_limit_count=1 WHERE exchange_points>0")
            cur.execute(
                "UPDATE prize_items SET redeem_limit_enabled=0, redeem_limit_count=0 WHERE item_id IN ('redeem_only_m4','redeem_key_trade','redeem_trade_key_x5','redeem_attr_ticket_x5','redeem_trade_key_x1','redeem_attr_ticket_x1')"
            )
        _mark_migration_done(cur, migration_key)

    # Backfill redeem corner tags from limit settings when DB tag is empty.
    cur.execute(
        """
        UPDATE prize_items
        SET redeem_tag_left = CASE
          WHEN redeem_limit_enabled=1 AND redeem_limit_count>0 THEN '单大区限兑' || redeem_limit_count
          ELSE '不限兑'
        END
        WHERE exchange_points>0 AND (redeem_tag_left IS NULL OR redeem_tag_left='')
        """
    )
    cur.execute(
        "UPDATE prize_items SET redeem_tag_right='不可交易' WHERE exchange_points>0 AND (redeem_tag_right IS NULL OR redeem_tag_right='')"
    )

    conn.commit()
    conn.close()


def get_purchase_options(conn):
    rows = conn.execute("SELECT option_key,label,price,keys_count FROM purchase_options ORDER BY option_key").fetchall()
    return {
        r["option_key"]: {
            "label": r["label"],
            "price": int(r["price"]),
            "keys": int(r["keys_count"]),
        }
        for r in rows
    }


def get_layout_rows(conn):
    row = conn.execute(
        "SELECT setting_value FROM pool_layout_settings WHERE setting_key='ring_rows'"
    ).fetchone()
    if not row:
        return 3
    try:
        return max(3, int(row["setting_value"]))
    except ValueError:
        return 3


def get_palette_priorities(conn):
    rows = conn.execute("SELECT palette_key,priority FROM pool_palette_priority").fetchall()
    if not rows:
        return {"red": 1, "orange": 2, "purple": 3, "blue": 4, "gray": 5}
    return {r["palette_key"]: int(r["priority"]) for r in rows}


def get_popup_highlight_palettes(conn):
    rows = conn.execute(
        "SELECT palette_key FROM popup_highlight_rules WHERE enabled=1 ORDER BY palette_key"
    ).fetchall()
    if not rows:
        return ["red", "orange", "purple", "blue"]
    return [r["palette_key"] for r in rows]


def get_redeem_destination(conn):
    value = (get_system_setting(conn, "redeem_destination", "warehouse") or "warehouse").strip().lower()
    if value not in ("warehouse", "stash"):
        return "warehouse"
    return value


def get_pool_data(conn):
    palette_priority = get_palette_priorities(conn)
    groups = {
        r["group_key"]: {
            "group_key": r["group_key"],
            "name": r["name"],
            "image_url": r["image_url"],
            "card_bg_color": r["card_bg_color"],
            "palette_key": r["palette_key"] or "gray",
            "palette_priority": int(palette_priority.get((r["palette_key"] or "gray"), 999)),
            "children": [],
            "sort_order": int(r["sort_order"]),
        }
        for r in conn.execute("SELECT * FROM points_groups ORDER BY sort_order")
    }

    item_rows = list(
        conn.execute(
        """
        SELECT * FROM prize_items
        WHERE in_pool=1 AND item_type='item'
        ORDER BY sort_order, item_id
        """
    ).fetchall()
    )
    item_rows.sort(
        key=lambda r: (
            int(palette_priority.get((r["palette_key"] or "orange"), 999)),
            int(r["sort_order"]),
            r["item_id"],
        )
    )

    child_rows = conn.execute(
        """
        SELECT * FROM prize_items
        WHERE in_pool=1 AND item_type='points_child'
        ORDER BY sort_order, item_id
        """
    ).fetchall()

    for c in child_rows:
        if c["group_key"] in groups:
            groups[c["group_key"]]["children"].append(
                {
                    "item_id": c["item_id"],
                    "name": c["name"],
                    "points": int(c["points_value"]),
                    "weight": float(c["pool_weight"]),
                }
            )

    pool = []
    for r in item_rows:
        pool.append(
            {
                "id": r["item_id"],
                "name": r["name"],
                "type": "item",
                "weight": float(r["pool_weight"]),
                "decompose_points": int(r["decompose_points"]),
                "decompose_keys": int(r["decompose_keys"]),
                "exchange_points": int(r["exchange_points"]),
                "direct_to_warehouse": int(r["direct_to_warehouse"]),
                "image_url": r["image_url"],
                "popup_image_url": r["popup_image_url"],
                "card_bg_color": r["card_bg_color"],
                "palette_key": r["palette_key"] or "orange",
                "palette_priority": int(palette_priority.get((r["palette_key"] or "orange"), 999)),
                "sort_order": int(r["sort_order"]),
            }
        )

    for g in sorted(groups.values(), key=lambda x: x["sort_order"]):
        if not g["children"]:
            continue
        g_weight = sum(c["weight"] for c in g["children"])
        pool.append(
            {
                "id": g["group_key"],
                "name": g["name"],
                "type": "points_group",
                "weight": g_weight,
                "children": g["children"],
                "image_url": g["image_url"],
                "card_bg_color": g["card_bg_color"],
                "palette_key": g.get("palette_key", "gray"),
                "palette_priority": int(g.get("palette_priority", 999)),
                "sort_order": int(g["sort_order"]),
            }
        )

    return pool


def build_pool_view(pool):
    total = sum(float(i["weight"]) for i in pool)
    if total <= 0:
        raise ValueError("奖池总权重必须大于0")

    rows = []
    for item in pool:
        row = {
            "id": item.get("id"),
            "name": item["name"],
            "type": item["type"],
            "weight": float(item["weight"]),
            "probability": float(item["weight"]) / total,
            "decompose_points": int(item.get("decompose_points", 0)),
            "decompose_keys": int(item.get("decompose_keys", 0)),
            "exchange_points": int(item.get("exchange_points", 0)),
            "direct_to_warehouse": int(item.get("direct_to_warehouse", 0)),
            "image_url": item.get("image_url", ""),
            "popup_image_url": item.get("popup_image_url", ""),
            "card_bg_color": item.get("card_bg_color", ""),
            "palette_key": item.get("palette_key", "orange"),
            "palette_priority": int(item.get("palette_priority", 999)),
            "sort_order": int(item.get("sort_order", 9999)),
        }
        if item["type"] == "points_group":
            child_total = sum(float(c["weight"]) for c in item["children"])
            row["children"] = [
                {
                    "item_id": c.get("item_id", ""),
                    "name": c["name"],
                    "points": int(c["points"]),
                    "weight": float(c["weight"]),
                    "probability_global": float(c["weight"]) / total,
                    "probability_in_group": float(c["weight"]) / child_total,
                }
                for c in item["children"]
            ]
        rows.append(row)

    return rows


def get_item_meta(conn):
    rows = conn.execute(
        """
        SELECT item_id,name,decompose_points,decompose_keys,exchange_points,
               direct_to_warehouse,image_url,popup_image_url,card_bg_color,in_pool,
               redeem_limit_enabled,redeem_limit_count,redeem_tag_left,redeem_tag_right
        FROM prize_items
        WHERE item_type='item'
        """
    ).fetchall()
    return {
        r["item_id"]: {
            "id": r["item_id"],
            "name": r["name"],
            "decompose_points": int(r["decompose_points"]),
            "decompose_keys": int(r["decompose_keys"]),
            "exchange_points": int(r["exchange_points"]),
            "direct_to_warehouse": int(r["direct_to_warehouse"]),
            "image_url": r["image_url"],
            "popup_image_url": r["popup_image_url"],
            "card_bg_color": r["card_bg_color"],
            "in_pool": int(r["in_pool"]),
            "redeem_limit_enabled": int(r["redeem_limit_enabled"]),
            "redeem_limit_count": int(r["redeem_limit_count"]),
            "redeem_tag_left": r["redeem_tag_left"] or "",
            "redeem_tag_right": r["redeem_tag_right"] or "不可交易",
        }
        for r in rows
    }


def build_shop_items(conn):
    rows = conn.execute(
        """
        SELECT item_id,name,decompose_points,decompose_keys,exchange_points,
               direct_to_warehouse,image_url,popup_image_url,card_bg_color,in_pool
               ,palette_key,redeem_limit_enabled,redeem_limit_count,redeem_tag_left,redeem_tag_right
        FROM prize_items
        WHERE item_type='item' AND exchange_points>0
        ORDER BY in_pool DESC, exchange_points DESC, item_id
        """
    ).fetchall()
    return [
        {
            "id": r["item_id"],
            "name": r["name"],
            "decompose_points": int(r["decompose_points"]),
            "decompose_keys": int(r["decompose_keys"]),
            "exchange_points": int(r["exchange_points"]),
            "direct_to_warehouse": int(r["direct_to_warehouse"]),
            "image_url": r["image_url"],
            "popup_image_url": r["popup_image_url"],
            "card_bg_color": r["card_bg_color"],
            "in_pool": int(r["in_pool"]),
            "palette_key": r["palette_key"] or "gray",
            "redeem_limit_enabled": int(r["redeem_limit_enabled"]),
            "redeem_limit_count": int(r["redeem_limit_count"]),
            "redeem_tag_left": r["redeem_tag_left"] or "",
            "redeem_tag_right": r["redeem_tag_right"] or "不可交易",
        }
        for r in rows
    ]


def infer_decompose_mode(items):
    has_points = any(int(i.get("decompose_points", 0)) > 0 for i in items)
    has_keys = any(int(i.get("decompose_keys", 0)) > 0 for i in items)
    if has_keys and not has_points:
        return "keys"
    if has_points and not has_keys:
        return "points"
    return "both"


def build_stash_view(state, meta):
    rows = []
    for item_id, qty in state["stash"].items():
        qty = int(qty)
        if qty <= 0 or item_id not in meta:
            continue
        m = meta[item_id]
        rows.append(
            {
                "id": item_id,
                "name": m["name"],
                "qty": qty,
                "decompose_points": m["decompose_points"],
                "decompose_keys": m["decompose_keys"],
                "image_url": m["image_url"],
            }
        )
    rows.sort(key=lambda x: x["name"])
    return rows


def build_warehouse_view(state, meta):
    rows = []
    for item_id, qty in state.get("warehouse_draw", {}).items():
        qty = int(qty)
        if qty <= 0 or item_id not in meta:
            continue
        m = meta[item_id]
        rows.append(
            {
                "id": item_id,
                "name": m["name"],
                "qty": qty,
                "image_url": m["image_url"],
            }
        )
    rows.sort(key=lambda x: x["name"])
    return rows


def weighted_pick(entries):
    total = sum(float(e["weight"]) for e in entries)
    r = random.random() * total
    cur = 0.0
    for e in entries:
        cur += float(e["weight"])
        if r <= cur:
            return e
    return entries[-1]


def draw_once(state, pool):
    top = weighted_pick(pool)

    if top["type"] == "points_group":
        child = weighted_pick(top["children"])
        points = int(child["points"])
        display = f"{points}积分"
        state["points"] += points
        bump(state["draw_counts"], display)
        result = {
            "type": "points",
            "name": display,
            "points": points,
            "group": top["name"],
            "child": child["name"],
        }
    else:
        item_id = top["id"]
        display = top["name"]
        direct = int(top.get("direct_to_warehouse", 0))
        if direct == 1:
            bump(state["warehouse"], item_id)
            bump(state["warehouse_draw"], item_id)
            destination = "warehouse"
        else:
            bump(state["stash"], item_id)
            append_stash_record(state, item_id, display)
            destination = "stash"

        bump(state["draw_counts"], display)
        result = {
            "type": "item",
            "id": item_id,
            "name": display,
            "destination": destination,
            "decompose_points": int(top.get("decompose_points", 0)),
            "decompose_keys": int(top.get("decompose_keys", 0)),
            "exchange_points": int(top.get("exchange_points", 0)),
            "image_url": top.get("image_url", ""),
            "popup_image_url": top.get("popup_image_url", ""),
        }

    state["total_draws"] += 1
    result["ts"] = __import__("time").time()
    result["draw_index"] = state["total_draws"]
    state["history"].append(result)
    if len(state["history"]) > 300:
        state["history"] = state["history"][-300:]
    return result


def build_analysis(state, pool_view):
    total_draws = int(state.get("total_draws", 0))
    draw_counts = state.get("draw_counts", {})
    history = state.get("history", [])

    points_total = 0
    points_hits = 0
    item_hits = 0
    warehouse_hits = 0
    stash_hits = 0

    timeline = []
    cumulative_points = 0
    cumulative_items = 0
    cumulative_points_hits = 0

    for idx, h in enumerate(history, start=1):
        if h.get("type") == "points":
            p = int(h.get("points", 0))
            points_total += p
            points_hits += 1
            cumulative_points += p
            cumulative_points_hits += 1
        elif h.get("type") == "item":
            item_hits += 1
            cumulative_items += 1
            if h.get("destination") == "warehouse":
                warehouse_hits += 1
            else:
                stash_hits += 1

        timeline.append(
            {
                "x": idx,
                "total_points": cumulative_points,
                "items_hit": cumulative_items,
                "points_hit": cumulative_points_hits,
            }
        )

    distribution = sorted(
        [
            {
                "name": name,
                "count": int(cnt),
                "rate": (int(cnt) / total_draws) if total_draws > 0 else 0,
            }
            for name, cnt in draw_counts.items()
        ],
        key=lambda x: x["count"],
        reverse=True,
    )

    expected_compare = []
    confidence_rows = []
    flat_prob_rows = []

    def _wilson(k, n, z=1.96):
        if n <= 0:
            return (0.0, 0.0)
        phat = k / n
        denom = 1 + (z * z) / n
        center = (phat + (z * z) / (2 * n)) / denom
        half = (z * math.sqrt((phat * (1 - phat) / n) + ((z * z) / (4 * n * n)))) / denom
        return (max(0.0, center - half), min(1.0, center + half))
    for row in pool_view:
        if row["type"] == "item":
            actual = int(draw_counts.get(row["name"], 0))
            expected = row["probability"] * total_draws
            flat_prob_rows.append((row["name"], row["probability"], actual))
            expected_compare.append(
                {
                    "name": row["name"],
                    "actual": actual,
                    "expected": expected,
                    "deviation": actual - expected,
                    "probability": row["probability"],
                }
            )
        elif row["type"] == "points_group":
            for c in row.get("children", []):
                actual = int(draw_counts.get(c["name"], 0))
                expected = c["probability_global"] * total_draws
                flat_prob_rows.append((c["name"], c["probability_global"], actual))
                expected_compare.append(
                    {
                        "name": c["name"],
                        "actual": actual,
                        "expected": expected,
                        "deviation": actual - expected,
                        "probability": c["probability_global"],
                    }
                )

    expected_compare.sort(key=lambda x: abs(x["deviation"]), reverse=True)

    chi_square = 0.0
    for _, p, actual in flat_prob_rows:
        e = p * total_draws
        if e > 1e-9:
            chi_square += ((actual - e) ** 2) / e

    for name, p, actual in flat_prob_rows:
        ci_low, ci_high = _wilson(actual, max(total_draws, 1))
        sd = math.sqrt(max(total_draws * p * (1 - p), 1e-9))
        z_score = (actual - total_draws * p) / sd if total_draws > 0 else 0.0
        confidence_rows.append(
            {
                "name": name,
                "observed_rate": (actual / total_draws) if total_draws > 0 else 0,
                "ci_low": ci_low,
                "ci_high": ci_high,
                "z_score": z_score,
                "probability": p,
            }
        )
    confidence_rows.sort(key=lambda x: abs(x["z_score"]), reverse=True)

    # Recent-vs-global comparison
    recent_window = 50
    recent_hist = history[-recent_window:] if len(history) > recent_window else history[:]
    recent_counts = {}
    for h in recent_hist:
        bump(recent_counts, h.get("name", ""), 1)

    recent_rows = []
    for name, p, actual in flat_prob_rows:
        global_rate = (actual / total_draws) if total_draws > 0 else 0
        recent_rate = (recent_counts.get(name, 0) / len(recent_hist)) if recent_hist else 0
        recent_rows.append(
            {
                "name": name,
                "global_rate": global_rate,
                "recent_rate": recent_rate,
                "diff_abs": abs(recent_rate - global_rate),
            }
        )
    recent_rows.sort(key=lambda x: x["diff_abs"], reverse=True)

    # Daily trend
    by_day = {}
    for h in history:
        ts = h.get("ts")
        if ts is None:
            day = "unknown"
        else:
            day = datetime.fromtimestamp(float(ts)).strftime("%Y-%m-%d")
        if day not in by_day:
            by_day[day] = {"day": day, "draws": 0, "points": 0, "items": 0}
        by_day[day]["draws"] += 1
        if h.get("type") == "points":
            by_day[day]["points"] += int(h.get("points", 0))
        else:
            by_day[day]["items"] += 1
    daily_trend = [by_day[k] for k in sorted(by_day.keys())]

    alerts = []
    for r in confidence_rows[:8]:
        if abs(r["z_score"]) >= 2.5 and total_draws >= 30:
            direction = "高于" if r["z_score"] > 0 else "低于"
            alerts.append(f"{r['name']} 命中显著{direction}理论值（Z={r['z_score']:.2f}）")
    for r in recent_rows[:5]:
        if r["diff_abs"] >= 0.05 and len(recent_hist) >= 20:
            alerts.append(
                f"最近{len(recent_hist)}抽中 {r['name']} 与全局差异较大（差值{(r['diff_abs']*100):.2f}%）"
            )

    # Linear regression for cumulative points: y = a*x + b
    linear_fit = {"slope": 0.0, "intercept": 0.0, "r2": 0.0}
    if timeline:
        n = len(timeline)
        xs = [float(p["x"]) for p in timeline]
        ys = [float(p["total_points"]) for p in timeline]
        sum_x = sum(xs)
        sum_y = sum(ys)
        sum_xx = sum(x * x for x in xs)
        sum_xy = sum(x * y for x, y in zip(xs, ys))
        denom = n * sum_xx - sum_x * sum_x
        if abs(denom) > 1e-9:
            a = (n * sum_xy - sum_x * sum_y) / denom
            b = (sum_y - a * sum_x) / n
            mean_y = sum_y / n
            ss_tot = sum((y - mean_y) ** 2 for y in ys)
            ss_res = sum((y - (a * x + b)) ** 2 for x, y in zip(xs, ys))
            r2 = 1 - (ss_res / ss_tot) if ss_tot > 1e-9 else 1.0
            linear_fit = {"slope": a, "intercept": b, "r2": r2}

    # Value-frequency distribution for points hits
    points_value_dist = {}
    for h in history:
        if h.get("type") == "points":
            name = h.get("name", "")
            bump(points_value_dist, name, 1)
    points_value_dist_rows = sorted(
        [{"name": k, "count": int(v)} for k, v in points_value_dist.items()],
        key=lambda x: x["count"],
        reverse=True,
    )

    return {
        "summary": {
            "total_draws": total_draws,
            "item_hits": item_hits,
            "points_hits": points_hits,
            "points_total_from_draw": points_total,
            "avg_points_per_draw": (points_total / total_draws) if total_draws > 0 else 0,
            "warehouse_hits": warehouse_hits,
            "stash_hits": stash_hits,
            "money_spent": int(state.get("money_spent", 0)),
            "current_points": int(state.get("points", 0)),
            "current_keys": int(state.get("keys", 0)),
        },
        "distribution_top": distribution,
        "distribution_all": distribution,
        "expected_compare_top": expected_compare,
        "expected_compare_all": expected_compare,
        "timeline": timeline,
        "confidence_rows": confidence_rows,
        "recent_vs_global": {"window": len(recent_hist), "rows": recent_rows},
        "daily_trend": daily_trend[-30:],
        "global_fit": {"chi_square": chi_square, "dof": max(len(flat_prob_rows) - 1, 0)},
        "alerts": alerts[:20],
        "linear_fit": linear_fit,
        "points_value_distribution": points_value_dist_rows,
    }


def _percentile(values, q):
    if not values:
        return 0.0
    if len(values) == 1:
        return float(values[0])
    s = sorted(float(v) for v in values)
    idx = (len(s) - 1) * float(q)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return s[lo]
    w = idx - lo
    return s[lo] * (1 - w) + s[hi] * w


def build_simulation(pool, shop_items, purchase_options, runs, strategy="min_unit", progress_cb=None):
    runs = max(10, int(runs))
    if not pool:
        return {"runs": runs, "rows": [], "model": {}, "summary": {}}
    if not shop_items:
        return {"runs": runs, "rows": [], "model": {}, "summary": {}}
    if not purchase_options:
        return {"runs": runs, "rows": [], "model": {}, "summary": {}}

    options = [
        {
            "key": k,
            "label": x.get("label", ""),
            "price": int(x.get("price", 0)),
            "keys": int(x.get("keys", 0)),
            "unit": (int(x.get("price", 0)) / max(int(x.get("keys", 0)), 1)),
        }
        for k, x in purchase_options.items()
        if int(x.get("keys", 0)) > 0
    ]
    options.sort(key=lambda x: (x["unit"], x["price"]))
    if not options:
        return {"runs": runs, "rows": [], "model": {}, "summary": {}}
    strategy = (strategy or "min_unit").strip()
    if strategy == "single_first":
        buy_opt = next((x for x in options if x["key"] == "single"), options[0])
        strategy_label = "优先10元1抽"
    elif strategy == "bundle_first":
        buy_opt = next((x for x in options if x["key"] == "bundle"), options[0])
        strategy_label = "优先100元11抽"
    else:
        buy_opt = options[0]
        strategy_label = "最低单钥匙成本"

    draw_item_rows = [x for x in pool if x.get("type") == "item"]
    prob_by_item = {x.get("id"): float(x.get("probability", 0.0)) for x in draw_item_rows}
    total_weight = sum(float(x["weight"]) for x in pool)
    if total_weight <= 0:
        return {"runs": runs, "rows": [], "model": {}, "summary": {}}

    rows = []
    total_iters = max(len(shop_items) * runs, 1)
    done_iters = 0
    for target in shop_items:
        target_id = target.get("id")
        exchange_points = int(target.get("exchange_points", 0))
        full_costs, full_draws = [], []
        pure_costs, pure_draws = [], []
        full_hit_by_draw, full_hit_by_redeem = 0, 0
        max_steps = 100000

        for _ in range(runs):
            # Strategy A: full decomposition (all stash items are decomposed),
            # acquisition can be direct hit OR redeem once points are enough.
            keys = 0
            points = 0
            spent = 0
            draws = 0
            got = False
            while draws < max_steps and not got:
                if exchange_points > 0 and points >= exchange_points:
                    got = True
                    full_hit_by_redeem += 1
                    break
                if keys <= 0:
                    keys += buy_opt["keys"]
                    spent += buy_opt["price"]
                keys -= 1
                draws += 1
                picked = weighted_pick(pool)
                if picked["type"] == "points_group":
                    child = weighted_pick(picked["children"])
                    points += int(child["points"])
                else:
                    if picked.get("id") == target_id:
                        got = True
                        full_hit_by_draw += 1
                        break
                    if int(picked.get("direct_to_warehouse", 0)) == 0:
                        points += int(picked.get("decompose_points", 0))
                        keys += int(picked.get("decompose_keys", 0))
            full_costs.append(float(spent))
            full_draws.append(float(draws))

            # Strategy B: pure guarantee (ignore direct hits / item decomposition),
            # only accumulate points outcomes until redeem threshold.
            if exchange_points > 0:
                keys = 0
                points = 0
                spent = 0
                draws = 0
                while draws < max_steps and points < exchange_points:
                    if keys <= 0:
                        keys += buy_opt["keys"]
                        spent += buy_opt["price"]
                    keys -= 1
                    draws += 1
                    picked = weighted_pick(pool)
                    if picked["type"] == "points_group":
                        child = weighted_pick(picked["children"])
                        points += int(child["points"])
                pure_costs.append(float(spent))
                pure_draws.append(float(draws))

            done_iters += 1
            if progress_cb and (done_iters == total_iters or done_iters % max(1, total_iters // 200) == 0):
                progress_cb(done_iters / total_iters, f"训练中: {target.get('name', '')} {done_iters}/{total_iters}")

        avg_full_cost = sum(full_costs) / len(full_costs) if full_costs else 0.0
        avg_full_draws = sum(full_draws) / len(full_draws) if full_draws else 0.0
        avg_pure_cost = (sum(pure_costs) / len(pure_costs)) if pure_costs else None
        avg_pure_draws = (sum(pure_draws) / len(pure_draws)) if pure_draws else None
        sd_full = (
            math.sqrt(sum((x - avg_full_cost) ** 2 for x in full_costs) / max(len(full_costs) - 1, 1))
            if full_costs
            else 0.0
        )
        ci95_half = 1.96 * (sd_full / math.sqrt(max(len(full_costs), 1))) if full_costs else 0.0

        row = {
            "id": target_id,
            "name": target.get("name", ""),
            "palette_key": target.get("palette_key", "gray"),
            "exchange_points": exchange_points,
            "probability": prob_by_item.get(target_id, 0.0),
            "full_decompose": {
                "avg_cost": avg_full_cost,
                "p50_cost": _percentile(full_costs, 0.5),
                "p90_cost": _percentile(full_costs, 0.9),
                "ci95_low_quantile": _percentile(full_costs, 0.025),
                "ci95_high_quantile": _percentile(full_costs, 0.975),
                "avg_draws": avg_full_draws,
                "ci95_low": max(0.0, avg_full_cost - ci95_half),
                "ci95_high": avg_full_cost + ci95_half,
                "hit_by_draw_rate": (full_hit_by_draw / runs),
                "hit_by_redeem_rate": (full_hit_by_redeem / runs),
                "cdf_points": [],
            },
            "pure_guarantee": {
                "enabled": exchange_points > 0,
                "avg_cost": avg_pure_cost,
                "p50_cost": _percentile(pure_costs, 0.5) if pure_costs else None,
                "p90_cost": _percentile(pure_costs, 0.9) if pure_costs else None,
                "avg_draws": avg_pure_draws,
            },
        }
        # Build compact empirical CDF points for charting
        if full_costs:
            sorted_costs = sorted(float(v) for v in full_costs)
            n_cost = len(sorted_costs)
            cdf_points = []
            bins = min(40, n_cost)
            for bi in range(bins):
                idx = int(round((bi / max(bins - 1, 1)) * (n_cost - 1)))
                cdf_points.append({"cost": sorted_costs[idx], "cdf": (idx + 1) / n_cost})
            row["full_decompose"]["cdf_points"] = cdf_points
        rows.append(row)

    rows.sort(key=lambda r: (-int(r.get("exchange_points", 0)), r.get("name", "")))

    # Modeling: avg_full_cost ~ a*(1/p) + b
    model_rows = [r for r in rows if float(r.get("probability", 0)) > 0 and r["full_decompose"]["avg_cost"] > 0]
    model = {"equation": "", "r2": 0.0, "correlation": 0.0}
    model_eval = {
        "sample_size": 0,
        "train_size": 0,
        "test_size": 0,
        "train_mae": 0.0,
        "test_mae": 0.0,
        "train_rmse": 0.0,
        "test_rmse": 0.0,
        "train_r2": 0.0,
        "test_r2": 0.0,
    }
    if len(model_rows) >= 2:
        xs = [1.0 / float(r["probability"]) for r in model_rows]
        ys = [float(r["full_decompose"]["avg_cost"]) for r in model_rows]
        n = len(xs)
        sx = sum(xs)
        sy = sum(ys)
        sxx = sum(x * x for x in xs)
        sxy = sum(x * y for x, y in zip(xs, ys))
        syy = sum(y * y for y in ys)
        den = n * sxx - sx * sx
        if abs(den) > 1e-9:
            a = (n * sxy - sx * sy) / den
            b = (sy - a * sx) / n
            mean_y = sy / n
            ss_tot = sum((y - mean_y) ** 2 for y in ys)
            ss_res = sum((y - (a * x + b)) ** 2 for x, y in zip(xs, ys))
            r2 = 1 - (ss_res / ss_tot) if ss_tot > 1e-9 else 1.0
            corr_den = math.sqrt(max((n * sxx - sx * sx) * (n * syy - sy * sy), 1e-9))
            corr = ((n * sxy - sx * sy) / corr_den) if corr_den > 1e-9 else 0.0
            model = {
                "equation": f"avg_cost ≈ {a:.4f}*(1/p) + {b:.2f}",
                "r2": r2,
                "correlation": corr,
            }
    # Train/Test split evaluation on item-level samples.
    eval_rows = [r for r in rows if float(r.get("probability", 0.0)) > 0 and float(r["full_decompose"]["avg_cost"]) > 0]
    if len(eval_rows) >= 4:
        # deterministic split: 70/30 (test at least 2)
        n_eval = len(eval_rows)
        test_n = max(2, int(round(n_eval * 0.3)))
        test_n = min(test_n, n_eval - 2)
        train = eval_rows[: n_eval - test_n]
        test = eval_rows[n_eval - test_n :]

        if len(train) >= 2:
            x_train = [1.0 / float(r["probability"]) for r in train]
            y_train = [float(r["full_decompose"]["avg_cost"]) for r in train]
            n = len(train)
            sx = sum(x_train)
            sy = sum(y_train)
            sxx = sum(x * x for x in x_train)
            sxy = sum(x * y for x, y in zip(x_train, y_train))
            den = n * sxx - sx * sx
            if abs(den) > 1e-9:
                a_tt = (n * sxy - sx * sy) / den
                b_tt = (sy - a_tt * sx) / n

                def _metrics(dataset):
                    xs = [1.0 / float(r["probability"]) for r in dataset]
                    ys = [float(r["full_decompose"]["avg_cost"]) for r in dataset]
                    preds = [a_tt * x + b_tt for x in xs]
                    errs = [y - p for y, p in zip(ys, preds)]
                    mae = sum(abs(e) for e in errs) / len(errs) if errs else 0.0
                    rmse = math.sqrt(sum(e * e for e in errs) / len(errs)) if errs else 0.0
                    mean_y = sum(ys) / len(ys) if ys else 0.0
                    ss_tot = sum((y - mean_y) ** 2 for y in ys)
                    ss_res = sum((y - p) ** 2 for y, p in zip(ys, preds))
                    r2v = (1 - ss_res / ss_tot) if ss_tot > 1e-9 else 1.0
                    return mae, rmse, r2v

                tr_mae, tr_rmse, tr_r2 = _metrics(train)
                te_mae, te_rmse, te_r2 = _metrics(test)
                model_eval = {
                    "sample_size": len(eval_rows),
                    "train_size": len(train),
                    "test_size": len(test),
                    "train_mae": tr_mae,
                    "test_mae": te_mae,
                    "train_rmse": tr_rmse,
                    "test_rmse": te_rmse,
                    "train_r2": tr_r2,
                    "test_r2": te_r2,
                }

    full_cost_all = [r["full_decompose"]["avg_cost"] for r in rows if r["full_decompose"]["avg_cost"] > 0]
    pure_cost_all = [
        r["pure_guarantee"]["avg_cost"]
        for r in rows
        if r["pure_guarantee"]["enabled"] and r["pure_guarantee"]["avg_cost"] is not None
    ]
    # Analytic expectations from configured probabilities.
    expected_points_no_decompose = 0.0
    expected_keys_full_decompose = 0.0
    for r in pool:
        p = float(r.get("probability", 0.0))
        if r.get("type") == "points_group":
            for c in r.get("children", []):
                expected_points_no_decompose += float(c.get("probability_global", 0.0)) * float(c.get("points", 0))
            continue
        if int(r.get("direct_to_warehouse", 0)) == 0:
            expected_keys_full_decompose += p * float(r.get("decompose_keys", 0))

    summary = {
        "runs": runs,
        "buy_option": {
            "label": buy_opt["label"],
            "price": buy_opt["price"],
            "keys": buy_opt["keys"],
            "unit_cost_per_key": buy_opt["unit"],
        },
        "strategy": strategy,
        "strategy_label": strategy_label,
        "item_count": len(rows),
        "avg_full_cost_all_items": (sum(full_cost_all) / len(full_cost_all)) if full_cost_all else 0.0,
        "avg_pure_cost_all_items": (sum(pure_cost_all) / len(pure_cost_all)) if pure_cost_all else 0.0,
        "expected_points_per_draw_no_decompose": expected_points_no_decompose,
        "expected_keys_per_draw_full_decompose": expected_keys_full_decompose,
    }

    return {"runs": runs, "rows": rows, "model": model, "model_eval": model_eval, "summary": summary}


def _sim_job_update(job_id, **kwargs):
    with SIM_JOBS_LOCK:
        job = SIM_JOBS.get(job_id)
        if not job:
            return
        job.update(kwargs)
        job["updated_at"] = time.time()


def _sim_job_worker(job_id, pool_view, shop_items, purchase_options, runs, strategy):
    try:
        _sim_job_update(job_id, status="running", progress=0.0, message="训练启动")
        result = build_simulation(
            pool_view,
            shop_items,
            purchase_options,
            runs,
            strategy,
            progress_cb=lambda p, m: _sim_job_update(job_id, progress=float(p), message=m),
        )
        _sim_job_update(job_id, status="done", progress=1.0, message="训练完成", result=result)
    except Exception as e:
        _sim_job_update(job_id, status="failed", error=str(e), message="训练失败")


def response_json(handler, code, payload):
    body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    handler.send_response(code)
    handler.send_header("Content-Type", "application/json; charset=utf-8")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


class Handler(BaseHTTPRequestHandler):
    def _body_json(self):
        length = int(self.headers.get("Content-Length", "0"))
        raw = self.rfile.read(length) if length > 0 else b"{}"
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def _send_file(self, path: Path):
        if not path.exists() or not path.is_file():
            self.send_error(404)
            return

        ext = path.suffix.lower()
        ctype = {
            ".html": "text/html; charset=utf-8",
            ".css": "text/css; charset=utf-8",
            ".js": "application/javascript; charset=utf-8",
            ".json": "application/json; charset=utf-8",
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
        }.get(ext, "application/octet-stream")

        data = path.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/":
            return self._send_file(STATIC_DIR / "index.html")

        if path == "/admin":
            return self._send_file(STATIC_DIR / "admin.html")

        if path.startswith("/static/"):
            rel = path[len("/static/"):]
            return self._send_file(STATIC_DIR / rel)

        if path.startswith("/cfimages/"):
            rel = path[len("/cfimages/"):]
            return self._send_file(BASE_DIR / "cfimages" / rel)

        if path.startswith("/cf_images/"):
            rel = path[len("/cf_images/"):]
            return self._send_file(BASE_DIR.parent / "cf_images" / rel)

        if path.startswith("/images/"):
            rel = path[len("/images/"):]
            return self._send_file(BASE_DIR.parent / "images" / rel)

        if path == "/api/config":
            with LOCK:
                conn = db_conn()
                pool = get_pool_data(conn)
                shop = build_shop_items(conn)
                points_image_url = (
                    get_system_setting(conn, "points_image_url", "/cf_images/jifen.png")
                    or "/cf_images/jifen.png"
                )
                payload = {
                    "purchase_options": get_purchase_options(conn),
                    "pool": build_pool_view(pool),
                    "shop_items": shop,
                    "decompose_mode": infer_decompose_mode(shop),
                    "points_image_url": points_image_url,
                    "layout_rows": get_layout_rows(conn),
                    "popup_highlight_palettes": get_popup_highlight_palettes(conn),
                }
                conn.close()
            return response_json(self, 200, payload)

        if path == "/api/state":
            with LOCK:
                conn = db_conn()
                meta = get_item_meta(conn)
                conn.close()
                state = load_state()
                payload = {
                    **state,
                    "stash_detail": build_stash_view(state, meta),
                    "warehouse_detail": build_warehouse_view(state, meta),
                }
            return response_json(self, 200, payload)

        if path == "/api/analysis":
            with LOCK:
                conn = db_conn()
                pool = get_pool_data(conn)
                pool_view = build_pool_view(pool)
                conn.close()
                state = load_state()
                payload = build_analysis(state, pool_view)
            return response_json(self, 200, payload)

        if path == "/api/simulate":
            with LOCK:
                conn = db_conn()
                pool = get_pool_data(conn)
                pool_view = build_pool_view(pool) if pool else []
                shop_items = build_shop_items(conn)
                purchase_options = get_purchase_options(conn)
                conn.close()
            payload = build_simulation(pool_view, shop_items, purchase_options, 500, "min_unit")
            return response_json(self, 200, {"ok": True, **payload})

        if path == "/api/simulate/status":
            job_id = (query.get("job_id") or [""])[0]
            if not job_id:
                return response_json(self, 400, {"ok": False, "error": "missing job_id"})
            with SIM_JOBS_LOCK:
                job = SIM_JOBS.get(job_id)
                if not job:
                    return response_json(self, 404, {"ok": False, "error": "job not found"})
                payload = {
                    "ok": True,
                    "job_id": job_id,
                    "status": job.get("status"),
                    "progress": float(job.get("progress", 0.0)),
                    "message": job.get("message", ""),
                    "error": job.get("error", ""),
                    "result": job.get("result") if job.get("status") == "done" else None,
                }
            return response_json(self, 200, payload)

        if path == "/api/db/items":
            with LOCK:
                conn = db_conn()
                rows = conn.execute("SELECT * FROM prize_items ORDER BY sort_order,item_id").fetchall()
                conn.close()
            return response_json(self, 200, {"rows": [dict(r) for r in rows]})

        if path == "/api/db/meta":
            with LOCK:
                conn = db_conn()
                tables = _db_admin_tables(conn)
                conn.close()
            payload = {
                "tables": [
                    {"name": t, "label_zh": DB_ADMIN_TABLE_LABELS.get(t, t)}
                    for t in tables
                ],
                "column_labels_zh": DB_ADMIN_COLUMN_LABELS,
                "boolean_columns": sorted(DB_ADMIN_BOOLEAN_COLUMNS),
            }
            return response_json(self, 200, payload)

        if path == "/api/db/schema":
            table = (query.get("table") or [""])[0]
            with LOCK:
                conn = db_conn()
                if not _db_admin_validate_table(conn, table):
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": "invalid table"})
                schema = _db_admin_schema(conn, table)
                conn.close()
            return response_json(self, 200, {"ok": True, "table": table, "schema": schema})

        if path == "/api/db/rows":
            table = (query.get("table") or [""])[0]
            with LOCK:
                conn = db_conn()
                if not _db_admin_validate_table(conn, table):
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": "invalid table"})
                schema = _db_admin_schema(conn, table)
                rows = conn.execute(f"SELECT rowid AS _rowid_, * FROM {table}").fetchall()
                conn.close()
            return response_json(
                self,
                200,
                {"ok": True, "table": table, "schema": schema, "rows": [dict(r) for r in rows]},
            )

        self.send_error(404)

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._body_json()

        if path == "/api/config/reload":
            return response_json(self, 200, {"ok": True})

        if path == "/api/db/insert":
            table = body.get("table")
            data = body.get("data") or {}
            if not isinstance(data, dict):
                return response_json(self, 400, {"ok": False, "error": "invalid data"})
            with LOCK:
                conn = db_conn()
                if not _db_admin_validate_table(conn, table):
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": "invalid table"})
                schema = _db_admin_schema(conn, table)
                cols = {c["name"]: c for c in schema}
                use_cols, use_vals = [], []
                for name in cols:
                    if name in data and data[name] is not None:
                        use_cols.append(name)
                        use_vals.append(data[name])
                if not use_cols:
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": "no values to insert"})
                sql = f"INSERT INTO {table}({', '.join(use_cols)}) VALUES({', '.join(['?' for _ in use_cols])})"
                try:
                    conn.execute(sql, use_vals)
                    conn.commit()
                except Exception as e:
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": str(e)})
                conn.close()
            return response_json(self, 200, {"ok": True})

        if path == "/api/db/update":
            table = body.get("table")
            data = body.get("data") or {}
            pk = body.get("pk") or {}
            if not isinstance(data, dict) or not isinstance(pk, dict):
                return response_json(self, 400, {"ok": False, "error": "invalid params"})
            with LOCK:
                conn = db_conn()
                if not _db_admin_validate_table(conn, table):
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": "invalid table"})
                schema = _db_admin_schema(conn, table)
                pk_cols = [c["name"] for c in sorted(schema, key=lambda x: x["pk"]) if c["pk"] > 0]
                if not pk_cols and schema:
                    pk_cols = [schema[0]["name"]]
                if any(k not in pk for k in pk_cols):
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": "missing pk fields"})
                set_cols = [c["name"] for c in schema if c["name"] not in pk_cols and c["name"] in data]
                if not set_cols:
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": "no fields to update"})
                set_clause = ", ".join([f"{c}=?" for c in set_cols])
                where_clause = " AND ".join([f"{c}=?" for c in pk_cols])
                params = [data[c] for c in set_cols] + [pk[c] for c in pk_cols]
                sql = f"UPDATE {table} SET {set_clause} WHERE {where_clause}"
                try:
                    cur = conn.execute(sql, params)
                    conn.commit()
                except Exception as e:
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": str(e)})
                affected = cur.rowcount
                conn.close()
            return response_json(self, 200, {"ok": True, "affected": int(affected)})

        if path == "/api/db/delete":
            table = body.get("table")
            pk = body.get("pk") or {}
            if not isinstance(pk, dict):
                return response_json(self, 400, {"ok": False, "error": "invalid pk"})
            with LOCK:
                conn = db_conn()
                if not _db_admin_validate_table(conn, table):
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": "invalid table"})
                schema = _db_admin_schema(conn, table)
                pk_cols = [c["name"] for c in sorted(schema, key=lambda x: x["pk"]) if c["pk"] > 0]
                if not pk_cols and schema:
                    pk_cols = [schema[0]["name"]]
                if any(k not in pk for k in pk_cols):
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": "missing pk fields"})
                where_clause = " AND ".join([f"{c}=?" for c in pk_cols])
                params = [pk[c] for c in pk_cols]
                sql = f"DELETE FROM {table} WHERE {where_clause}"
                try:
                    cur = conn.execute(sql, params)
                    conn.commit()
                except Exception as e:
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": str(e)})
                affected = cur.rowcount
                conn.close()
            return response_json(self, 200, {"ok": True, "affected": int(affected)})

        if path == "/api/buy":
            option = body.get("option")
            with LOCK:
                conn = db_conn()
                options = get_purchase_options(conn)
                opt = options.get(option)
                if not opt:
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": "invalid option"})

                state = load_state()
                state["money_spent"] += int(opt["price"])
                state["keys"] += int(opt["keys"])

                meta = get_item_meta(conn)
                shop = build_shop_items(conn)
                conn.close()
                save_state(state)

                payload = {
                    "ok": True,
                    "state": {
                        **state,
                        "stash_detail": build_stash_view(state, meta),
                        "warehouse_detail": build_warehouse_view(state, meta),
                    },
                    "shop_items": shop,
                }
            return response_json(self, 200, payload)

        if path == "/api/draw":
            count = int(body.get("count", 1))
            if count not in (1, 10):
                return response_json(self, 400, {"ok": False, "error": "count must be 1 or 10"})

            with LOCK:
                conn = db_conn()
                pool = get_pool_data(conn)
                if not pool:
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": "奖池为空"})

                state = load_state()
                if state["keys"] < count:
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": "钥匙不足"})

                state["keys"] -= count
                results = [draw_once(state, pool) for _ in range(count)]

                meta = get_item_meta(conn)
                conn.close()
                save_state(state)

                payload = {
                    "ok": True,
                    "results": results,
                    "state": {
                        **state,
                        "stash_detail": build_stash_view(state, meta),
                        "warehouse_detail": build_warehouse_view(state, meta),
                    },
                }
            return response_json(self, 200, payload)

        if path == "/api/stash/decompose":
            item_id = body.get("item_id")
            qty = int(body.get("qty", 1))
            if qty <= 0:
                return response_json(self, 400, {"ok": False, "error": "qty must be > 0"})

            with LOCK:
                conn = db_conn()
                meta = get_item_meta(conn)
                item_meta = meta.get(item_id)
                if not item_meta:
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": "invalid item"})

                state = load_state()
                have = int(state["stash"].get(item_id, 0))
                if have < qty:
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": "暂存箱数量不足"})

                state["stash"][item_id] = have - qty
                if state["stash"][item_id] <= 0:
                    del state["stash"][item_id]

                gain_points = int(item_meta["decompose_points"]) * qty
                gain_keys = int(item_meta["decompose_keys"]) * qty
                state["points"] += gain_points
                state["keys"] += gain_keys
                bump(state["decompose_counts"], item_meta["name"], qty)

                shop = build_shop_items(conn)
                conn.close()
                save_state(state)

                payload = {
                    "ok": True,
                    "gain_points": gain_points,
                    "gain_keys": gain_keys,
                    "state": {
                        **state,
                        "stash_detail": build_stash_view(state, meta),
                        "warehouse_detail": build_warehouse_view(state, meta),
                    },
                    "shop_items": shop,
                }
            return response_json(self, 200, payload)

        if path == "/api/stash/send":
            item_id = body.get("item_id")
            qty = int(body.get("qty", 1))
            if qty <= 0:
                return response_json(self, 400, {"ok": False, "error": "qty must be > 0"})

            with LOCK:
                conn = db_conn()
                meta = get_item_meta(conn)
                item_meta = meta.get(item_id)
                if not item_meta:
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": "invalid item"})

                state = load_state()
                have = int(state["stash"].get(item_id, 0))
                if have < qty:
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": "暂存箱数量不足"})

                state["stash"][item_id] = have - qty
                if state["stash"][item_id] <= 0:
                    del state["stash"][item_id]
                bump(state["warehouse"], item_id, qty)

                conn.close()
                save_state(state)
                payload = {
                    "ok": True,
                    "state": {
                        **state,
                        "stash_detail": build_stash_view(state, meta),
                        "warehouse_detail": build_warehouse_view(state, meta),
                    },
                }
            return response_json(self, 200, payload)

        if path == "/api/stash/record-action":
            record_id = int(body.get("record_id", 0))
            action = body.get("action")
            if record_id <= 0 or action not in ("send", "decompose"):
                return response_json(self, 400, {"ok": False, "error": "invalid params"})

            with LOCK:
                conn = db_conn()
                meta = get_item_meta(conn)
                state = load_state()
                records = state.get("stash_records", [])
                rec = next((x for x in records if int(x.get("record_id", 0)) == record_id), None)
                if not rec:
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": "记录不存在"})
                if rec.get("status") != "pending":
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": "该记录已处理"})

                item_id = rec.get("item_id")
                item_meta = meta.get(item_id)
                if not item_meta:
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": "道具不存在"})

                have = int(state["stash"].get(item_id, 0))
                if have <= 0:
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": "暂存箱数量不足"})

                state["stash"][item_id] = have - 1
                if state["stash"][item_id] <= 0:
                    del state["stash"][item_id]

                gain_points = 0
                gain_keys = 0
                if action == "send":
                    bump(state["warehouse"], item_id, 1)
                    rec["status"] = "sent"
                    state.setdefault("redeem_logs", []).append(
                        {
                            "ts": __import__("time").time(),
                            "item_id": item_id,
                            "name": item_meta["name"],
                            "qty": 1,
                            "cost": 0,
                            "source": "stash_send",
                        }
                    )
                else:
                    gain_points = int(item_meta["decompose_points"])
                    gain_keys = int(item_meta["decompose_keys"])
                    state["points"] += gain_points
                    state["keys"] += gain_keys
                    bump(state["decompose_counts"], item_meta["name"], 1)
                    rec["status"] = "decomposed"
                rec["action_ts"] = __import__("time").time()

                conn.close()
                save_state(state)
                payload = {
                    "ok": True,
                    "gain_points": gain_points,
                    "gain_keys": gain_keys,
                    "state": {
                        **state,
                        "stash_detail": build_stash_view(state, meta),
                        "warehouse_detail": build_warehouse_view(state, meta),
                    },
                }
            return response_json(self, 200, payload)

        if path == "/api/redeem":
            item_id = body.get("item_id")
            qty = int(body.get("qty", 1))
            if qty <= 0:
                return response_json(self, 400, {"ok": False, "error": "qty must be > 0"})

            with LOCK:
                conn = db_conn()
                meta = get_item_meta(conn)
                item_meta = meta.get(item_id)
                if not item_meta:
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": "invalid item"})

                state = load_state()
                cost = int(item_meta["exchange_points"]) * qty
                if cost <= 0:
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": "该道具不可兑换"})
                if state["points"] < cost:
                    conn.close()
                    return response_json(self, 400, {"ok": False, "error": "积分不足"})

                limit_enabled = int(item_meta.get("redeem_limit_enabled", 0))
                limit_count = int(item_meta.get("redeem_limit_count", 0))
                redeemed_now = int(state.get("redeem_item_counts", {}).get(item_id, 0))
                if limit_enabled == 1 and limit_count > 0 and redeemed_now + qty > limit_count:
                    conn.close()
                    return response_json(
                        self,
                        400,
                        {"ok": False, "error": f"该道具限兑{limit_count}个，已兑换{redeemed_now}个"},
                    )

                state["points"] -= cost
                bump(state["redeem_counts"], item_meta["name"], qty)
                bump(state["redeem_item_counts"], item_id, qty)
                state.setdefault("redeem_logs", []).append(
                    {
                        "ts": __import__("time").time(),
                        "item_id": item_id,
                        "name": item_meta["name"],
                        "qty": qty,
                        "cost": cost,
                        "source": "redeem",
                    }
                )

                destination = get_redeem_destination(conn)
                if destination == "stash":
                    bump(state["stash"], item_id, qty)
                    for _ in range(qty):
                        append_stash_record(state, item_id, item_meta["name"])
                else:
                    destination = "warehouse"
                    bump(state["warehouse"], item_id, qty)

                shop = build_shop_items(conn)
                conn.close()
                save_state(state)

                payload = {
                    "ok": True,
                    "cost": cost,
                    "destination": destination,
                    "state": {
                        **state,
                        "stash_detail": build_stash_view(state, meta),
                        "warehouse_detail": build_warehouse_view(state, meta),
                    },
                    "shop_items": shop,
                }
            return response_json(self, 200, payload)

        if path == "/api/state/reset":
            with LOCK:
                state = _default_state()
                save_state(state)
            return response_json(
                self,
                200,
                {"ok": True, "state": {**state, "stash_detail": [], "warehouse_detail": []}},
            )

        if path == "/api/simulate":
            runs = int(body.get("runs", 500))
            strategy = body.get("strategy", "min_unit")
            with LOCK:
                conn = db_conn()
                pool = get_pool_data(conn)
                pool_view = build_pool_view(pool) if pool else []
                shop_items = build_shop_items(conn)
                purchase_options = get_purchase_options(conn)
                conn.close()
            payload = build_simulation(pool_view, shop_items, purchase_options, runs, strategy)
            return response_json(self, 200, {"ok": True, **payload})

        if path == "/api/simulate/start":
            runs = int(body.get("runs", 500))
            strategy = body.get("strategy", "min_unit")
            with LOCK:
                conn = db_conn()
                pool = get_pool_data(conn)
                pool_view = build_pool_view(pool) if pool else []
                shop_items = build_shop_items(conn)
                purchase_options = get_purchase_options(conn)
                conn.close()
            job_id = uuid.uuid4().hex
            with SIM_JOBS_LOCK:
                SIM_JOBS[job_id] = {
                    "status": "queued",
                    "progress": 0.0,
                    "message": "排队中",
                    "error": "",
                    "result": None,
                    "created_at": time.time(),
                    "updated_at": time.time(),
                }
                # keep job cache bounded
                if len(SIM_JOBS) > 40:
                    old = sorted(SIM_JOBS.items(), key=lambda kv: kv[1].get("updated_at", 0))[:10]
                    for k, _ in old:
                        SIM_JOBS.pop(k, None)
            t = threading.Thread(
                target=_sim_job_worker,
                args=(job_id, pool_view, shop_items, purchase_options, runs, strategy),
                daemon=True,
            )
            t.start()
            return response_json(self, 200, {"ok": True, "job_id": job_id})

        self.send_error(404)

    def log_message(self, fmt, *args):
        return


def main():
    init_db()
    if not STATE_PATH.exists():
        save_state(_default_state())

    server = ThreadingHTTPServer((HOST, PORT), Handler)
    print(f"Simulator running: http://{HOST}:{PORT}")
    print(f"Admin running: http://{HOST}:{PORT}/admin")
    print(f"DB path: {DB_PATH}")
    server.serve_forever()


if __name__ == "__main__":
    main()
