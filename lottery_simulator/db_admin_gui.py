#!/usr/bin/env python3
import sqlite3
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "data" / "lottery.db"

TABLE_LABELS = {
    "purchase_options": "购买选项",
    "points_groups": "积分组",
    "prize_items": "奖品主表",
    "pool_layout_settings": "奖池布局设置",
    "pool_palette_priority": "颜色优先级",
    "popup_highlight_rules": "弹窗高亮规则",
    "system_settings": "系统全局设置",
    "schema_migrations": "迁移记录",
}

COLUMN_LABELS = {
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

BOOLEAN_LIKE_COLUMNS = {
    "in_pool",
    "direct_to_warehouse",
    "redeem_limit_enabled",
    "enabled",
}


class DbAdminApp:
    def __init__(self, root):
        self.root = root
        self.root.title("CF 模拟器数据库可视化管理")
        self.root.geometry("1450x860")

        self.current_table = None
        self.columns = []
        self.pk_columns = []
        self.rows = []
        self.form_widgets = {}
        self.original_pk_values = None

        self._build_ui()
        self._init_table_list()

    def _db(self):
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        return conn

    def _build_ui(self):
        top = ttk.Frame(self.root, padding=10)
        top.pack(fill=tk.X)

        ttk.Label(top, text="数据表：").pack(side=tk.LEFT)
        self.table_var = tk.StringVar()
        self.table_combo = ttk.Combobox(top, textvariable=self.table_var, state="readonly", width=50)
        self.table_combo.pack(side=tk.LEFT, padx=(0, 8))
        self.table_combo.bind("<<ComboboxSelected>>", self._on_table_selected)

        ttk.Button(top, text="刷新当前表", command=self._refresh_current_table).pack(side=tk.LEFT)
        ttk.Label(top, text=f"数据库：{DB_PATH}").pack(side=tk.RIGHT)

        middle = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        middle.pack(fill=tk.BOTH, expand=True)

        self.tree = ttk.Treeview(middle, show="headings")
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.tree.bind("<<TreeviewSelect>>", self._on_row_selected)

        yscroll = ttk.Scrollbar(middle, orient="vertical", command=self.tree.yview)
        xscroll = ttk.Scrollbar(self.root, orient="horizontal", command=self.tree.xview)
        self.tree.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        yscroll.pack(side=tk.RIGHT, fill=tk.Y)
        xscroll.pack(fill=tk.X, padx=10, pady=(0, 8))

        form_wrap = ttk.LabelFrame(self.root, text="编辑区（中文字段映射）", padding=10)
        form_wrap.pack(fill=tk.BOTH, padx=10, pady=(0, 10))

        self.form_canvas = tk.Canvas(form_wrap, height=250)
        self.form_scrollbar = ttk.Scrollbar(form_wrap, orient="vertical", command=self.form_canvas.yview)
        self.form_container = ttk.Frame(self.form_canvas)
        self.form_container.bind(
            "<Configure>",
            lambda e: self.form_canvas.configure(scrollregion=self.form_canvas.bbox("all")),
        )
        self.form_canvas.create_window((0, 0), window=self.form_container, anchor="nw")
        self.form_canvas.configure(yscrollcommand=self.form_scrollbar.set)

        self.form_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self.form_scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

        btns = ttk.Frame(self.root, padding=(10, 0, 10, 10))
        btns.pack(fill=tk.X)
        ttk.Button(btns, text="新增记录", command=self._insert_record).pack(side=tk.LEFT)
        ttk.Button(btns, text="保存修改", command=self._update_record).pack(side=tk.LEFT, padx=8)
        ttk.Button(btns, text="删除选中", command=self._delete_record).pack(side=tk.LEFT)
        ttk.Button(btns, text="清空表单", command=self._clear_form).pack(side=tk.LEFT, padx=8)

    def _init_table_list(self):
        with self._db() as conn:
            rows = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name"
            ).fetchall()

        display_items = []
        self.display_to_table = {}
        for r in rows:
            table_name = r["name"]
            zh = TABLE_LABELS.get(table_name, table_name)
            display = f"{zh} ({table_name})"
            display_items.append(display)
            self.display_to_table[display] = table_name

        self.table_combo["values"] = display_items
        if display_items:
            self.table_combo.current(0)
            self._on_table_selected()

    def _on_table_selected(self, _event=None):
        display = self.table_var.get()
        table = self.display_to_table.get(display)
        if not table:
            return
        self.current_table = table
        self.original_pk_values = None
        self._load_schema_and_rows()

    def _refresh_current_table(self):
        if not self.current_table:
            return
        self.original_pk_values = None
        self._load_schema_and_rows()

    def _load_schema_and_rows(self):
        with self._db() as conn:
            pragma = conn.execute(f"PRAGMA table_info('{self.current_table}')").fetchall()
            self.columns = []
            for c in pragma:
                self.columns.append(
                    {
                        "name": c["name"],
                        "type": (c["type"] or "TEXT").upper(),
                        "notnull": int(c["notnull"]),
                        "default": c["dflt_value"],
                        "pk": int(c["pk"]),
                    }
                )

            self.pk_columns = [c["name"] for c in sorted(self.columns, key=lambda x: x["pk"]) if c["pk"] > 0]
            if not self.pk_columns and self.columns:
                self.pk_columns = [self.columns[0]["name"]]

            rows = conn.execute(f"SELECT rowid as _rowid_, * FROM {self.current_table}").fetchall()

        self.rows = [dict(r) for r in rows]
        self._render_tree()
        self._render_form()

    def _render_tree(self):
        for item in self.tree.get_children():
            self.tree.delete(item)

        col_names = [c["name"] for c in self.columns]
        self.tree["columns"] = col_names

        for name in col_names:
            zh = COLUMN_LABELS.get(name, name)
            self.tree.heading(name, text=f"{zh}\n({name})")
            self.tree.column(name, width=140, anchor=tk.W)

        for i, row in enumerate(self.rows):
            values = ["" if row.get(name) is None else str(row.get(name)) for name in col_names]
            self.tree.insert("", tk.END, iid=str(i), values=values)

    def _render_form(self):
        for child in self.form_container.winfo_children():
            child.destroy()

        self.form_widgets = {}
        for i, c in enumerate(self.columns):
            name = c["name"]
            zh = COLUMN_LABELS.get(name, name)
            suffix = []
            if c["pk"]:
                suffix.append("主键")
            if c["notnull"]:
                suffix.append("必填")
            meta = f"（{'/'.join(suffix)}）" if suffix else ""

            row = i // 2
            col_base = (i % 2) * 2

            ttk.Label(
                self.form_container,
                text=f"{zh} ({name}) {meta}",
            ).grid(row=row, column=col_base, sticky="w", padx=(0, 8), pady=4)

            if name in BOOLEAN_LIKE_COLUMNS:
                widget = ttk.Combobox(self.form_container, state="readonly", width=30, values=["0", "1"])
            elif name == "item_type":
                widget = ttk.Combobox(self.form_container, state="readonly", width=30, values=["item", "points_child"])
            else:
                widget = ttk.Entry(self.form_container, width=35)

            widget.grid(row=row, column=col_base + 1, sticky="ew", padx=(0, 20), pady=4)
            self.form_widgets[name] = widget

        for i in range(4):
            self.form_container.grid_columnconfigure(i, weight=1)

    def _on_row_selected(self, _event=None):
        selected = self.tree.selection()
        if not selected:
            return

        row_idx = int(selected[0])
        row = self.rows[row_idx]
        self.original_pk_values = {k: row.get(k) for k in self.pk_columns}

        for c in self.columns:
            name = c["name"]
            val = row.get(name)
            widget = self.form_widgets[name]

            if isinstance(widget, ttk.Combobox):
                widget.set("" if val is None else str(val))
            else:
                widget.delete(0, tk.END)
                widget.insert(0, "" if val is None else str(val))

    def _clear_form(self):
        self.tree.selection_remove(self.tree.selection())
        self.original_pk_values = None
        for name, widget in self.form_widgets.items():
            if isinstance(widget, ttk.Combobox):
                widget.set("")
            else:
                widget.delete(0, tk.END)

    def _read_form_values(self):
        data = {}
        for c in self.columns:
            name = c["name"]
            t = c["type"]
            widget = self.form_widgets[name]
            raw = widget.get().strip()

            if raw == "":
                if c["notnull"] and c["default"] is None:
                    raise ValueError(f"字段 {name} 不能为空")
                data[name] = None
                continue

            try:
                if "INT" in t:
                    data[name] = int(raw)
                elif "REAL" in t or "FLOA" in t or "DOUB" in t:
                    data[name] = float(raw)
                else:
                    data[name] = raw
            except ValueError as e:
                raise ValueError(f"字段 {name} 类型错误，期望 {t}") from e

        return data

    def _insert_record(self):
        if not self.current_table:
            return
        try:
            data = self._read_form_values()
        except ValueError as e:
            messagebox.showerror("校验失败", str(e))
            return

        columns = [c["name"] for c in self.columns if data.get(c["name"]) is not None]
        values = [data[c] for c in columns]
        if not columns:
            messagebox.showerror("新增失败", "没有可写入字段")
            return

        sql = f"INSERT INTO {self.current_table}({', '.join(columns)}) VALUES({', '.join(['?' for _ in columns])})"
        try:
            with self._db() as conn:
                conn.execute(sql, values)
                conn.commit()
        except Exception as e:
            messagebox.showerror("新增失败", str(e))
            return

        self._load_schema_and_rows()
        messagebox.showinfo("成功", "新增记录成功")

    def _update_record(self):
        if not self.current_table:
            return
        if not self.original_pk_values:
            messagebox.showwarning("提示", "请先在上方选择一条记录后再保存")
            return

        try:
            data = self._read_form_values()
        except ValueError as e:
            messagebox.showerror("校验失败", str(e))
            return

        set_columns = [c["name"] for c in self.columns if c["name"] not in self.pk_columns]
        if not set_columns:
            messagebox.showwarning("提示", "当前表没有可更新字段")
            return

        set_clause = ", ".join([f"{c}=?" for c in set_columns])
        where_clause = " AND ".join([f"{k}=?" for k in self.pk_columns])

        params = [data.get(c) for c in set_columns] + [self.original_pk_values[k] for k in self.pk_columns]
        sql = f"UPDATE {self.current_table} SET {set_clause} WHERE {where_clause}"

        try:
            with self._db() as conn:
                cur = conn.execute(sql, params)
                conn.commit()
                if cur.rowcount == 0:
                    messagebox.showwarning("提示", "没有匹配到待更新记录，可能已被删除")
                    self._load_schema_and_rows()
                    return
        except Exception as e:
            messagebox.showerror("更新失败", str(e))
            return

        self._load_schema_and_rows()
        messagebox.showinfo("成功", "保存修改成功")

    def _delete_record(self):
        if not self.current_table:
            return
        if not self.original_pk_values:
            messagebox.showwarning("提示", "请先选择一条记录")
            return

        pk_text = ", ".join([f"{k}={self.original_pk_values[k]}" for k in self.pk_columns])
        ok = messagebox.askyesno("确认删除", f"确定删除当前记录吗？\n{pk_text}")
        if not ok:
            return

        where_clause = " AND ".join([f"{k}=?" for k in self.pk_columns])
        params = [self.original_pk_values[k] for k in self.pk_columns]
        sql = f"DELETE FROM {self.current_table} WHERE {where_clause}"

        try:
            with self._db() as conn:
                cur = conn.execute(sql, params)
                conn.commit()
                if cur.rowcount == 0:
                    messagebox.showwarning("提示", "记录不存在或已被删除")
        except Exception as e:
            messagebox.showerror("删除失败", str(e))
            return

        self._clear_form()
        self._load_schema_and_rows()
        messagebox.showinfo("成功", "删除成功")


def main():
    if not DB_PATH.exists():
        raise SystemExit(f"数据库不存在: {DB_PATH}")

    root = tk.Tk()
    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    app = DbAdminApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
