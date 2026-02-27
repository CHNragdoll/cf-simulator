const state = {
  tables: [],
  schema: [],
  rows: [],
  currentTable: "",
  selectedPk: null,
  columnLabelsZh: {},
  booleanColumns: new Set(),
};

const el = {
  tableSelect: document.getElementById("tableSelect"),
  refreshBtn: document.getElementById("refreshBtn"),
  status: document.getElementById("status"),
  thead: document.querySelector("#dataTable thead"),
  tbody: document.querySelector("#dataTable tbody"),
  formGrid: document.getElementById("formGrid"),
  insertBtn: document.getElementById("insertBtn"),
  updateBtn: document.getElementById("updateBtn"),
  deleteBtn: document.getElementById("deleteBtn"),
  clearBtn: document.getElementById("clearBtn"),
};

function setStatus(msg) {
  el.status.textContent = msg || "";
}

async function api(path, method = "GET", data = null) {
  const res = await fetch(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: data ? JSON.stringify(data) : undefined,
  });
  const payload = await res.json().catch(() => ({}));
  if (!res.ok || payload.ok === false) {
    throw new Error(payload.error || `请求失败(${res.status})`);
  }
  return payload;
}

function pkColumns() {
  const pks = state.schema.filter((c) => Number(c.pk) > 0).sort((a, b) => a.pk - b.pk).map((c) => c.name);
  if (pks.length) return pks;
  return state.schema.length ? [state.schema[0].name] : [];
}

function getWidgetValue(name) {
  const node = document.getElementById(`f_${name}`);
  if (!node) return null;
  const val = node.value.trim();
  return val === "" ? null : val;
}

function castByType(raw, type) {
  if (raw === null) return null;
  const t = (type || "TEXT").toUpperCase();
  if (t.includes("INT")) return Number.parseInt(raw, 10);
  if (t.includes("REAL") || t.includes("FLOA") || t.includes("DOUB")) return Number.parseFloat(raw);
  return raw;
}

function buildForm() {
  el.formGrid.innerHTML = "";
  for (const c of state.schema) {
    const wrap = document.createElement("div");
    wrap.className = "field";
    const label = document.createElement("label");
    const meta = [];
    if (Number(c.pk) > 0) meta.push("主键");
    if (Number(c.notnull) === 1) meta.push("必填");
    label.textContent = `${c.label_zh || c.name} (${c.name})${meta.length ? ` [${meta.join("/")}]` : ""}`;
    wrap.appendChild(label);

    let input;
    if (state.booleanColumns.has(c.name)) {
      input = document.createElement("select");
      input.innerHTML = `<option value=""></option><option value="0">0</option><option value="1">1</option>`;
    } else if (c.name === "item_type") {
      input = document.createElement("select");
      input.innerHTML = `<option value=""></option><option value="item">item</option><option value="points_child">points_child</option>`;
    } else {
      input = document.createElement("input");
      input.type = "text";
    }
    input.id = `f_${c.name}`;
    wrap.appendChild(input);
    el.formGrid.appendChild(wrap);
  }
}

function rowDisplayValue(row, c) {
  const v = row[c.name];
  return v === null || v === undefined ? "" : String(v);
}

function clearSelection() {
  state.selectedPk = null;
  for (const c of state.schema) {
    const input = document.getElementById(`f_${c.name}`);
    if (input) input.value = "";
  }
  for (const tr of el.tbody.querySelectorAll("tr")) tr.classList.remove("selected");
}

function selectRow(row, tr) {
  for (const all of el.tbody.querySelectorAll("tr")) all.classList.remove("selected");
  tr.classList.add("selected");
  const pks = pkColumns();
  state.selectedPk = {};
  for (const pk of pks) state.selectedPk[pk] = row[pk];
  for (const c of state.schema) {
    const input = document.getElementById(`f_${c.name}`);
    if (input) {
      const v = row[c.name];
      input.value = v === null || v === undefined ? "" : String(v);
    }
  }
}

function renderTable() {
  el.thead.innerHTML = "";
  el.tbody.innerHTML = "";

  const trHead = document.createElement("tr");
  for (const c of state.schema) {
    const th = document.createElement("th");
    th.textContent = `${c.label_zh || c.name} (${c.name})`;
    trHead.appendChild(th);
  }
  el.thead.appendChild(trHead);

  for (const row of state.rows) {
    const tr = document.createElement("tr");
    for (const c of state.schema) {
      const td = document.createElement("td");
      td.textContent = rowDisplayValue(row, c);
      tr.appendChild(td);
    }
    tr.addEventListener("click", () => selectRow(row, tr));
    el.tbody.appendChild(tr);
  }
}

async function loadMeta() {
  const meta = await api("/api/db/meta");
  state.tables = meta.tables || [];
  state.columnLabelsZh = meta.column_labels_zh || {};
  state.booleanColumns = new Set(meta.boolean_columns || []);

  el.tableSelect.innerHTML = "";
  for (const t of state.tables) {
    const opt = document.createElement("option");
    opt.value = t.name;
    opt.textContent = `${t.label_zh} (${t.name})`;
    el.tableSelect.appendChild(opt);
  }
}

async function loadTable(table) {
  if (!table) return;
  setStatus("加载中...");
  const data = await api(`/api/db/rows?table=${encodeURIComponent(table)}`);
  state.currentTable = table;
  state.schema = data.schema || [];
  state.rows = data.rows || [];
  buildForm();
  renderTable();
  clearSelection();
  setStatus(`已加载 ${table}，共 ${state.rows.length} 行`);
}

function collectDataFromForm() {
  const data = {};
  for (const c of state.schema) {
    const raw = getWidgetValue(c.name);
    data[c.name] = castByType(raw, c.type);
  }
  return data;
}

async function onInsert() {
  try {
    const data = collectDataFromForm();
    await api("/api/db/insert", "POST", { table: state.currentTable, data });
    await loadTable(state.currentTable);
    setStatus("新增成功");
  } catch (e) {
    alert(e.message);
  }
}

async function onUpdate() {
  if (!state.selectedPk) {
    alert("请先选中一行");
    return;
  }
  try {
    const data = collectDataFromForm();
    await api("/api/db/update", "POST", { table: state.currentTable, data, pk: state.selectedPk });
    await loadTable(state.currentTable);
    setStatus("保存成功");
  } catch (e) {
    alert(e.message);
  }
}

async function onDelete() {
  if (!state.selectedPk) {
    alert("请先选中一行");
    return;
  }
  if (!confirm("确定删除当前记录？")) return;
  try {
    await api("/api/db/delete", "POST", { table: state.currentTable, pk: state.selectedPk });
    await loadTable(state.currentTable);
    setStatus("删除成功");
  } catch (e) {
    alert(e.message);
  }
}

function bindEvents() {
  el.tableSelect.addEventListener("change", () => loadTable(el.tableSelect.value));
  el.refreshBtn.addEventListener("click", () => loadTable(el.tableSelect.value));
  el.insertBtn.addEventListener("click", onInsert);
  el.updateBtn.addEventListener("click", onUpdate);
  el.deleteBtn.addEventListener("click", onDelete);
  el.clearBtn.addEventListener("click", clearSelection);
}

async function bootstrap() {
  try {
    bindEvents();
    await loadMeta();
    if (el.tableSelect.value) {
      await loadTable(el.tableSelect.value);
    }
  } catch (e) {
    setStatus("加载失败");
    alert(e.message);
  }
}

bootstrap();
