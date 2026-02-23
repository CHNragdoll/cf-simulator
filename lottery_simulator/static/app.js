const state = {
  config: null,
  user: null,
  analysis: null,
  simulation: null,
  skipPopup: localStorage.getItem("skipPopup") === "1",
  decomposeView: localStorage.getItem("decomposeView") || "keys",
  stashPage: 1,
  stashPageSize: 8,
  giftTab: "draw",
  giftPage: 1,
  giftPageSize: 8,
  rarePopupQueue: [],
  pendingClassicResults: null,
  reopenGiftAfterRare: false,
};

const topStats = document.getElementById("topStats");
const prizeGrid = document.getElementById("prizeGrid");
const drawSummary = document.getElementById("drawSummary");
const stashModalTable = document.getElementById("stashModalTable");
const stashDecomposeTable = document.getElementById("stashDecomposeTable");
const stashPrevPage = document.getElementById("stashPrevPage");
const stashNextPage = document.getElementById("stashNextPage");
const stashPageInfo = document.getElementById("stashPageInfo");
const warehouseList = document.getElementById("warehouseList");
const redeemList = document.getElementById("redeemList");
const modal = document.getElementById("resultModal");
const resultTitle = document.getElementById("resultTitle");
const resultBody = document.getElementById("resultBody");
const resultTotalPoints = document.getElementById("resultTotalPoints");
const resultTotal = document.querySelector(".result-total");
const resultNotes = document.querySelector(".result-notes");
const centerPoints = document.getElementById("centerPoints");
const centerKeys = document.getElementById("centerKeys");
const drawCenterPanel = document.getElementById("drawCenterPanel");
const skipPopup = document.getElementById("skipPopup");
const analysisSummary = document.getElementById("analysisSummary");
const analysisDistribution = document.getElementById("analysisDistribution");
const analysisExpected = document.getElementById("analysisExpected");
const analysisConfidence = document.getElementById("analysisConfidence");
const analysisRecent = document.getElementById("analysisRecent");
const analysisTrend = document.getElementById("analysisTrend");
const analysisLinearFormula = document.getElementById("analysisLinearFormula");
const analysisDaily = document.getElementById("analysisDaily");
const analysisAlerts = document.getElementById("analysisAlerts");
const analysisPointsValueDist = document.getElementById("analysisPointsValueDist");
const analysisProbCompare = document.getElementById("analysisProbCompare");
const simRuns = document.getElementById("simRuns");
const simStrategy = document.getElementById("simStrategy");
const runSimulationBtn = document.getElementById("runSimulation");
const simSummary = document.getElementById("simSummary");
const simModel = document.getElementById("simModel");
const simTable = document.getElementById("simTable");
const simCostChart = document.getElementById("simCostChart");
const simCdfChart = document.getElementById("simCdfChart");
const simCiChart = document.getElementById("simCiChart");
const simProgressWrap = document.getElementById("simProgressWrap");
const simProgressBar = document.getElementById("simProgressBar");
const simProgressText = document.getElementById("simProgressText");
const probabilityModal = document.getElementById("probabilityModal");
const probabilityTable = document.getElementById("probabilityTable");
const stashModal = document.getElementById("stashModal");
const giftRecordModal = document.getElementById("giftRecordModal");
const giftRecordTable = document.getElementById("giftRecordTable");
const giftTimeHeader = document.getElementById("giftTimeHeader");
const giftAreaHeader = document.getElementById("giftAreaHeader");
const giftNameHeader = document.getElementById("giftNameHeader");
const giftExtraHeader = document.getElementById("giftExtraHeader");
const giftPrevPage = document.getElementById("giftPrevPage");
const giftNextPage = document.getElementById("giftNextPage");
const giftPageInfo = document.getElementById("giftPageInfo");
const giftTabDraw = document.getElementById("giftTabDraw");
const giftTabRedeem = document.getElementById("giftTabRedeem");
const toast = document.getElementById("toast");

async function api(path, method = "GET", data = null) {
  const res = await fetch(path, {
    method,
    cache: "no-store",
    headers: { "Content-Type": "application/json" },
    body: data ? JSON.stringify(data) : undefined,
  });

  if (!res.ok) {
    let msg = `请求失败(${res.status})`;
    try {
      const err = await res.json();
      if (err.error) msg = err.error;
    } catch {
      // keep default message
    }
    throw new Error(msg);
  }
  return res.json();
}

function showToast(msg) {
  toast.textContent = msg;
  toast.classList.add("show");
  setTimeout(() => toast.classList.remove("show"), 1800);
}

function pct(v) {
  return `${(v * 100).toFixed(2)}%`;
}

function renderStats() {
  const u = state.user;
  topStats.innerHTML = "";
  const rows = [
    ["累计消费", `${u.money_spent} 元`],
    ["剩余钥匙", `${u.keys}`],
    ["总积分", `${u.points}`],
    ["总抽数", `${u.total_draws}`],
  ];
  for (const [label, value] of rows) {
    const div = document.createElement("div");
    div.className = "stat";
    div.innerHTML = `<div class="label">${label}</div><div class="value">${value}</div>`;
    topStats.appendChild(div);
  }
  centerPoints.textContent = u.points;
  centerKeys.textContent = u.keys;
}

function paletteClass(row) {
  const key = (row.palette_key || "").toLowerCase();
  if (key === "orange") return "palette-orange";
  if (key === "purple") return "palette-purple";
  if (key === "blue") return "palette-blue";
  if (key === "gray") return "palette-gray";
  if (row.type === "points_group" || row.id === "king_stone") return "palette-gray";
  return "palette-orange";
}

function renderPrizeGrid() {
  prizeGrid.innerHTML = "";
  const cards = [];
  const orderedPool = [...(state.config.pool || [])].sort((a, b) => {
    const pa = Number(a.palette_priority ?? 999);
    const pb = Number(b.palette_priority ?? 999);
    if (pa !== pb) return pa - pb;
    const sa = Number(a.sort_order ?? 9999);
    const sb = Number(b.sort_order ?? 9999);
    return sa - sb;
  });

  for (const row of orderedPool) {
    const card = document.createElement("div");
    card.className = `prize-card ${paletteClass(row)}`.trim();
    const imageNode = row.image_url
      ? `<div class="prize-image"><img src="${row.image_url}" alt="${row.name}"></div>`
      : `<div class="prize-image"></div>`;

    if (row.type === "points_group") {
      const lines = row.children
        .map(
          (c) =>
            `<div>${c.name}: 全局${pct(c.probability_global)} | 组内${pct(c.probability_in_group)}</div>`
        )
        .join("");

      card.innerHTML = `
        <div class="hover-wrap">
          <div class="prize-top">
            <div class="prize-meta">
              <span class="prize-tag">概率 ${pct(row.probability)}</span>
              <span class="prize-tag">嵌套项</span>
            </div>
            ${imageNode}
          </div>
          <div class="prize-bottom">
            <div class="prize-name bottom">${row.name}</div>
          </div>
          <div class="hover-pop">${lines}</div>
        </div>
      `;
    } else {
      card.innerHTML = `
        <div class="prize-top">
          <div class="prize-meta">
            <span class="prize-tag">${pct(row.probability)}</span>
            <span class="prize-tag">${row.direct_to_warehouse === 1 ? "直发仓库" : "暂存箱"}</span>
          </div>
          ${imageNode}
        </div>
        <div class="prize-bottom">
          <div class="prize-name bottom">${row.name}</div>
        </div>
      `;
    }
    cards.push(card);
  }
  layoutRing(cards);
}

function layoutRing(cards) {
  if (!cards.length) return;

  prizeGrid.innerHTML = "";
  const topRow = document.createElement("div");
  topRow.className = "ring-row";
  const bottomRow = document.createElement("div");
  bottomRow.className = "ring-row";
  const middle = document.createElement("div");
  middle.className = "ring-middle";

  const total = cards.length;
  let idx = 0;
  const ringRows = Math.max(3, Number(state.config?.layout_rows || 3));
  const sideRows = Math.max(1, ringRows - 2);
  const sideSlots = sideRows * 2;
  const sideCount = Math.min(sideSlots, total);
  const rest = Math.max(0, total - sideCount);
  const topCount = Math.floor(rest / 2);
  const bottomCount = rest - topCount;
  const ringCols = Math.max(3, topCount || Math.min(4, total));

  middle.style.setProperty("--ring-cols", String(ringCols));
  middle.style.setProperty("--side-rows", String(sideRows));
  drawCenterPanel.classList.add("ring-center");
  drawCenterPanel.style.gridColumn = `2 / span ${Math.max(1, ringCols - 2)}`;
  drawCenterPanel.style.gridRow = `1 / span ${sideRows}`;
  middle.appendChild(drawCenterPanel);

  for (let i = 0; i < topCount; i += 1) {
    topRow.appendChild(cards[idx]);
    idx += 1;
  }

  for (let r = 0; r < sideRows && idx < total; r += 1) {
    cards[idx].style.gridRow = String(r + 1);
    cards[idx].style.gridColumn = "1";
    middle.appendChild(cards[idx]);
    idx += 1;
    if (idx < total) {
      cards[idx].style.gridRow = String(r + 1);
      cards[idx].style.gridColumn = String(ringCols);
      middle.appendChild(cards[idx]);
      idx += 1;
    }
  }

  for (let i = 0; i < bottomCount && idx < total; i += 1) {
    bottomRow.appendChild(cards[idx]);
    idx += 1;
  }

  if (topCount > 0) {
    prizeGrid.appendChild(topRow);
  }
  prizeGrid.appendChild(middle);
  if (bottomCount > 0) {
    prizeGrid.appendChild(bottomRow);
  }

  while (idx < total) {
    const extra = document.createElement("div");
    extra.className = "ring-row";
    const rowSize = Math.min(5, total - idx);
    for (let i = 0; i < rowSize; i += 1) {
      extra.appendChild(cards[idx]);
      idx += 1;
    }
    prizeGrid.appendChild(extra);
  }
}

function renderSummary() {
  drawSummary.innerHTML = "";
  const entries = Object.entries(state.user.draw_counts || {}).sort((a, b) => b[1] - a[1]);
  if (!entries.length) {
    drawSummary.innerHTML = `<div class="tip">暂无抽奖记录</div>`;
    return;
  }

  for (const [name, qty] of entries.slice(0, 14)) {
    const row = document.createElement("div");
    row.className = "summary-item";
    row.textContent = `${name} × ${qty}`;
    drawSummary.appendChild(row);
  }
}

function renderStash() {
  stashModalTable.innerHTML = "";
  const rows = [...(state.user.stash_records || [])].sort(
    (a, b) => Number(b.record_id || 0) - Number(a.record_id || 0)
  );
  const totalPages = Math.max(1, Math.ceil(rows.length / state.stashPageSize));
  if (state.stashPage > totalPages) state.stashPage = totalPages;
  if (state.stashPage < 1) state.stashPage = 1;
  stashPageInfo.textContent = `${state.stashPage} / ${totalPages}`;
  stashPrevPage.disabled = state.stashPage <= 1;
  stashNextPage.disabled = state.stashPage >= totalPages;

  if (!rows.length) {
    stashModalTable.innerHTML = `<tr><td colspan="3" class="tip">暂存箱为空</td></tr>`;
    return;
  }

  const start = (state.stashPage - 1) * state.stashPageSize;
  const pageRows = rows.slice(start, start + state.stashPageSize);
  for (const r of pageRows) {
    let leftCell = `<button class="stash-action-btn" data-action="send-record" data-record-id="${r.record_id}">发送仓库</button>`;
    let rightCell = `<button class="stash-action-btn" data-action="decompose-record" data-record-id="${r.record_id}">分解</button>`;
    if (r.status === "sent") {
      leftCell = `<span class="stash-result-text">已发送</span>`;
      rightCell = `<span class="stash-result-text">x</span>`;
    } else if (r.status === "decomposed") {
      leftCell = `<span class="stash-result-text">x</span>`;
      rightCell = `<span class="stash-result-text">已分解</span>`;
    }
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${r.name}</td>
      <td>${leftCell}</td>
      <td>${rightCell}</td>
    `;
    stashModalTable.appendChild(tr);
  }
}

function renderDecomposeMap() {
  stashDecomposeTable.innerHTML = "";
  const rows = (state.config?.pool || [])
    .filter((r) => r.type === "item")
    .map((r) => ({
      name: r.name,
      value: Number(r.decompose_keys || 0),
    }))
    .filter((r) => r.value > 0)
    .sort((a, b) => b.value - a.value);

  if (!rows.length) {
    stashDecomposeTable.innerHTML = `<tr><td colspan="2" class="tip">当前活动没有可分解钥匙配置</td></tr>`;
    return;
  }

  for (const r of rows) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td>${r.name}</td><td>${r.value}</td>`;
    stashDecomposeTable.appendChild(tr);
  }
}

function renderWarehouse() {
  warehouseList.innerHTML = "";
  const rows = state.user.warehouse_detail || [];
  if (!rows.length) {
    warehouseList.innerHTML = `<div class="tip">暂无直发仓库道具</div>`;
    return;
  }
  for (const r of rows) {
    const row = document.createElement("div");
    row.className = "row";
    const thumb = r.image_url ? `<img class="thumb" src="${r.image_url}" alt="${r.name}">` : "";
    row.innerHTML = `
      <div>
        ${thumb}
        <div class="name">${r.name} x ${r.qty}</div>
        <div class="meta">该道具为直发仓库类型，不进入暂存箱</div>
      </div>
    `;
    warehouseList.appendChild(row);
  }
}

function renderRedeem() {
  redeemList.innerHTML = "";
  redeemList.className = "redeem-grid";
  const items = [...(state.config.shop_items || [])].sort((a, b) => {
    const pa = Number(a.exchange_points || 0);
    const pb = Number(b.exchange_points || 0);
    if (pa !== pb) return pb - pa;
    return String(a.id || "").localeCompare(String(b.id || ""));
  });
  const poolPaletteMap = new Map(
    (state.config.pool || [])
      .filter((x) => x.type === "item")
      .map((x) => [x.id, x.palette_key || "orange"])
  );
  for (const r of items) {
    const palette_key = poolPaletteMap.has(r.id) ? poolPaletteMap.get(r.id) : "gray";
    const redeemed = Number(state.user?.redeem_item_counts?.[r.id] || 0);
    const limited = Number(r.redeem_limit_enabled || 0) === 1 && Number(r.redeem_limit_count || 0) > 0;
    const limitCount = Number(r.redeem_limit_count || 0);
    const reachedLimit = limited && redeemed >= limitCount;
    const topTag = (r.redeem_tag_left || "").trim();
    const rightTag = (r.redeem_tag_right || "").trim();
    const card = document.createElement("div");
    card.className = "redeem-unit";
    const thumb = r.image_url ? `<img class="redeem-thumb" src="${r.image_url}" alt="${r.name}">` : "";
    card.innerHTML = `
      <div class="redeem-card ${paletteClass({ ...r, palette_key })}">
        <div class="redeem-top">
          <div class="redeem-ribbons">
            ${topTag ? `<span class="redeem-ribbon-left">${topTag}</span>` : ""}
            ${rightTag ? `<span class="redeem-ribbon-right">${rightTag}</span>` : ""}
          </div>
          <div class="redeem-image">${thumb}</div>
        </div>
        <div class="redeem-bottom">
          <div class="redeem-name">${r.name}</div>
        </div>
      </div>
      <button class="redeem-btn ${reachedLimit ? "disabled" : ""}" data-action="redeem" data-id="${r.id}" ${reachedLimit ? "disabled" : ""}>
        ${reachedLimit ? "已兑换" : `${r.exchange_points}积分兑换`}
      </button>
    `;
    redeemList.appendChild(card);
  }
}

function renderAll() {
  renderStats();
  renderPrizeGrid();
  renderSummary();
  renderDecomposeMap();
  renderStash();
  renderWarehouse();
  renderRedeem();
  renderSimulation();
  renderAnalysis();
  skipPopup.checked = state.skipPopup;
}

function renderProbabilityTable() {
  probabilityTable.innerHTML = "";
  for (const row of state.config.pool || []) {
    if (row.type === "item") {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${row.name}</td><td>${pct(row.probability)}</td>`;
      probabilityTable.appendChild(tr);
      continue;
    }
    if (row.type === "points_group") {
      for (const c of row.children || []) {
        const tr = document.createElement("tr");
        tr.innerHTML = `<td>${c.name}</td><td>${pct(c.probability_global)}</td>`;
        probabilityTable.appendChild(tr);
      }
    }
  }
}

function renderSimulation() {
  const s = state.simulation;
  simSummary.innerHTML = "";
  simModel.innerHTML = "";
  simTable.innerHTML = "";
  if (!s || !s.summary) {
    simSummary.innerHTML = `<div class="tip">输入模拟次数后点击“开始模拟”</div>`;
    simCostChart.innerHTML = `<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#8a7b66">暂无模拟数据</text>`;
    simCdfChart.innerHTML = `<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#8a7b66">暂无模拟数据</text>`;
    simCiChart.innerHTML = `<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#8a7b66">暂无模拟数据</text>`;
    return;
  }

  const summaryCards = [
    ["模拟次数", `${s.summary.runs}`],
    ["道具数量", `${s.summary.item_count}`],
    ["购钥匙方案", `${s.summary.buy_option?.label || "-"} (${(s.summary.buy_option?.unit_cost_per_key || 0).toFixed(2)}/钥匙)`],
    ["模拟策略", `${s.summary.strategy_label || "-"}`],
    ["全分解均价(全道具均值)", `${(s.summary.avg_full_cost_all_items || 0).toFixed(2)} 元`],
    ["纯保底均价(全道具均值)", `${(s.summary.avg_pure_cost_all_items || 0).toFixed(2)} 元`],
    ["不分解时单抽期望积分", `${Number(s.summary.expected_points_per_draw_no_decompose || 0).toFixed(4)}`],
    ["全分解时单抽期望钥匙", `${Number(s.summary.expected_keys_per_draw_full_decompose || 0).toFixed(6)}`],
  ];
  for (const [label, value] of summaryCards) {
    const div = document.createElement("div");
    div.className = "stat";
    div.innerHTML = `<div class="label">${label}</div><div class="value">${value}</div>`;
    simSummary.appendChild(div);
  }

  if (s.model) {
    const modelRows = [
      `回归方程：${s.model.equation || "-"}`,
      `R²：${Number(s.model.r2 || 0).toFixed(4)}`,
      `相关系数：${Number(s.model.correlation || 0).toFixed(4)}`,
    ];
    const ev = s.model_eval || {};
    modelRows.push(`可建模样本数(概率>0): ${Number(ev.sample_size || 0)}`);
    modelRows.push(`训练集/测试集: ${Number(ev.train_size || 0)} / ${Number(ev.test_size || 0)}`);
    modelRows.push(`MAE(训练/测试): ${Number(ev.train_mae || 0).toFixed(2)} / ${Number(ev.test_mae || 0).toFixed(2)}`);
    modelRows.push(`RMSE(训练/测试): ${Number(ev.train_rmse || 0).toFixed(2)} / ${Number(ev.test_rmse || 0).toFixed(2)}`);
    modelRows.push(`R²(训练/测试): ${Number(ev.train_r2 || 0).toFixed(4)} / ${Number(ev.test_r2 || 0).toFixed(4)}`);
    for (const t of modelRows) {
      const div = document.createElement("div");
      div.className = "chart-row";
      div.textContent = t;
      simModel.appendChild(div);
    }
  }

  const rows = s.rows || [];
  if (!rows.length) {
    simTable.innerHTML = `<tr><td colspan="5" class="tip">暂无模拟数据</td></tr>`;
    simCostChart.innerHTML = `<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#8a7b66">暂无模拟数据</text>`;
    simCdfChart.innerHTML = `<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#8a7b66">暂无模拟数据</text>`;
    simCiChart.innerHTML = `<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#8a7b66">暂无模拟数据</text>`;
    return;
  }

  for (const r of rows) {
    const tr = document.createElement("tr");
    const full = r.full_decompose || {};
    const pure = r.pure_guarantee || {};
    const hitDraw = Number(full.hit_by_draw_rate || 0) * 100;
    const hitRedeem = Number(full.hit_by_redeem_rate || 0) * 100;
    tr.innerHTML = `
      <td>${r.name}</td>
      <td>${Number(full.avg_cost || 0).toFixed(2)} 元</td>
      <td>${Number(full.p50_cost || 0).toFixed(2)} / ${Number(full.p90_cost || 0).toFixed(2)} 元</td>
      <td>${pure.enabled ? `${Number(pure.avg_cost || 0).toFixed(2)} 元` : "-"}</td>
      <td>${hitDraw.toFixed(1)}% / ${hitRedeem.toFixed(1)}%</td>
    `;
    simTable.appendChild(tr);
  }

  const colorMap = new Map(rows.map((r, i) => [r.id, getSeriesColor(i)]));
  renderSimCostChart(rows);
  renderSimCdfChart(rows, colorMap);
  renderSimCiChart(rows, colorMap);
}

function getSeriesColor(index) {
  const palette = [
    "#ff7a00", "#2f77f1", "#7a44c8", "#00a58e", "#d94841", "#8c6d1f",
    "#e83e8c", "#17a2b8", "#6f42c1", "#20c997", "#fd7e14", "#3b5bdb",
    "#a61e4d", "#2b8a3e", "#5f3dc4", "#c2255c", "#1c7ed6", "#f08c00",
  ];
  return palette[index % palette.length];
}

function renderSimCostChart(rows) {
  const width = 600;
  const height = 240;
  const pad = 32;
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  if (!rows.length) {
    simCostChart.innerHTML = `<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#8a7b66">暂无模拟数据</text>`;
    return;
  }
  const maxVal = Math.max(
    ...rows.map((r) => Math.max(Number(r.full_decompose?.avg_cost || 0), Number(r.pure_guarantee?.avg_cost || 0))),
    1
  );
  const step = innerW / rows.length;
  const bars = rows
    .map((r, i) => {
      const x = pad + i * step + step * 0.12;
      const w = step * 0.34;
      const full = Number(r.full_decompose?.avg_cost || 0);
      const pure = Number(r.pure_guarantee?.avg_cost || 0);
      const h1 = (full / maxVal) * innerH;
      const h2 = pure > 0 ? (pure / maxVal) * innerH : 0;
      const y1 = pad + innerH - h1;
      const y2 = pad + innerH - h2;
      return `
        <rect x="${x}" y="${y1}" width="${w}" height="${h1}" fill="#ff9d00"></rect>
        ${pure > 0 ? `<rect x="${x + w + 2}" y="${y2}" width="${w}" height="${h2}" fill="#2f77f1"></rect>` : ""}
      `;
    })
    .join("");
  simCostChart.innerHTML = `
    <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" stroke="#d3c6b0" />
    <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" stroke="#d3c6b0" />
    ${bars}
    <rect x="${pad + 8}" y="${pad + 8}" width="10" height="10" fill="#ff9d00"></rect>
    <text x="${pad + 22}" y="${pad + 18}" fill="#6f5b48" font-size="12">全分解均价</text>
    <rect x="${pad + 98}" y="${pad + 8}" width="10" height="10" fill="#2f77f1"></rect>
    <text x="${pad + 112}" y="${pad + 18}" fill="#6f5b48" font-size="12">纯保底均价</text>
  `;
}

function renderSimCdfChart(rows, colorMap) {
  const width = 600;
  const height = 240;
  const pad = 32;
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  const withCdf = rows.filter((r) => (r.full_decompose?.cdf_points || []).length > 1);
  if (!withCdf.length) {
    simCdfChart.innerHTML = `<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#8a7b66">暂无CDF数据</text>`;
    return;
  }
  const maxX = Math.max(
    ...withCdf.flatMap((r) => (r.full_decompose?.cdf_points || []).map((p) => Number(p.cost || 0))),
    1
  );
  const lines = withCdf
    .map((r) => {
      const points = (r.full_decompose?.cdf_points || [])
        .map((p) => {
          const x = pad + (Number(p.cost || 0) / maxX) * innerW;
          const y = pad + innerH - Number(p.cdf || 0) * innerH;
          return `${x},${y}`;
        })
        .join(" ");
      return `<polyline fill="none" stroke="${colorMap.get(r.id) || "#2f77f1"}" stroke-width="2" points="${points}" />`;
    })
    .join("");
  const legendBgH = Math.min(withCdf.length, 8) * 14 + 10;
  const legends = withCdf
    .slice(0, 8)
    .map(
      (r, i) =>
        `<text x="${pad + 12}" y="${pad + 18 + i * 14}" fill="${colorMap.get(r.id) || "#2f77f1"}" font-size="11">${r.name}</text>`
    )
    .join("");
  simCdfChart.innerHTML = `
    <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" stroke="#d3c6b0" />
    <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" stroke="#d3c6b0" />
    <rect x="${pad + 4}" y="${pad + 4}" width="200" height="${legendBgH}" fill="rgba(255,255,255,0.9)" stroke="#d9ccb6" />
    ${lines}
    ${legends}
    <text x="${width - pad}" y="${height - 10}" fill="#6f5b48" font-size="12" text-anchor="end">成本(元)</text>
    <text x="${pad + 4}" y="${pad - 8}" fill="#6f5b48" font-size="12">CDF</text>
  `;
}

function renderSimCiChart(rows, colorMap) {
  const width = 600;
  const height = 240;
  const pad = 32;
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  if (!rows.length) {
    simCiChart.innerHTML = `<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#8a7b66">暂无区间数据</text>`;
    return;
  }
  const maxX = Math.max(...rows.map((r) => Number(r.full_decompose?.ci95_high || 0)), 1);
  const stepY = innerH / rows.length;
  const lines = rows
    .map((r, i) => {
      const y = pad + stepY * i + stepY * 0.5;
      const lo = Number(r.full_decompose?.ci95_low || 0);
      const hi = Number(r.full_decompose?.ci95_high || 0);
      const mean = Number(r.full_decompose?.avg_cost || 0);
      const x1 = pad + (lo / maxX) * innerW;
      const x2 = pad + (hi / maxX) * innerW;
      const xm = pad + (mean / maxX) * innerW;
      const c = colorMap.get(r.id) || "#2f77f1";
      return `
        <line x1="${x1}" y1="${y}" x2="${x2}" y2="${y}" stroke="${c}" stroke-width="2.5"></line>
        <circle cx="${xm}" cy="${y}" r="3.2" fill="${c}"></circle>
      `;
    })
    .join("");
  simCiChart.innerHTML = `
    <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" stroke="#d3c6b0" />
    <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" stroke="#d3c6b0" />
    ${lines}
    <text x="${width - pad}" y="${height - 10}" fill="#6f5b48" font-size="12" text-anchor="end">全分解成本区间(元)</text>
  `;
}

function setSimProgress(visible, progress = 0, text = "") {
  simProgressWrap.style.display = visible ? "" : "none";
  const p = Math.max(0, Math.min(1, Number(progress || 0)));
  simProgressBar.style.width = `${(p * 100).toFixed(1)}%`;
  simProgressText.textContent = text || `训练进度 ${(p * 100).toFixed(1)}%`;
}

async function runSimulation() {
  const runs = Math.max(10, Number(simRuns.value || 500));
  simRuns.value = String(runs);
  const strategy = simStrategy?.value || "min_unit";
  runSimulationBtn.disabled = true;
  try {
    setSimProgress(true, 0, "提交任务中...");
    const start = await api("/api/simulate/start", "POST", { runs, strategy });
    const jobId = start.job_id;
    while (true) {
      await new Promise((resolve) => setTimeout(resolve, 300));
      const st = await api(`/api/simulate/status?job_id=${encodeURIComponent(jobId)}`);
      setSimProgress(true, st.progress || 0, st.message || "训练中");
      if (st.status === "done") {
        state.simulation = st.result;
        renderSimulation();
        setSimProgress(false);
        showToast(`模拟完成：${runs} 次`);
        return;
      }
      if (st.status === "failed") {
        setSimProgress(false);
        throw new Error(st.error || "模拟失败");
      }
    }
  } finally {
    runSimulationBtn.disabled = false;
  }
}

function fmtTime(ts) {
  if (!ts) return "-";
  const d = new Date(Number(ts) * 1000);
  const p = (n) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${p(d.getMonth() + 1)}-${p(d.getDate())} ${p(d.getHours())}:${p(d.getMinutes())}:${p(d.getSeconds())}`;
}

function isRareItemResult(r) {
  if (!r || r.type !== "item") return false;
  const highlightPalettes = new Set(state.config?.popup_highlight_palettes || ["orange", "purple", "blue"]);
  const poolItem = (state.config?.pool || []).find((x) => x.type === "item" && x.id === r.id);
  const palette = (poolItem?.palette_key || "").toLowerCase();
  return highlightPalettes.has(palette);
}

function renderGiftRecords() {
  giftRecordTable.innerHTML = "";
  const isDraw = state.giftTab === "draw";
  const source = isDraw ? [...(state.user.history || [])] : [...(state.user.redeem_logs || [])];
  source.sort((a, b) => Number((b.ts || b.action_ts || 0)) - Number((a.ts || a.action_ts || 0)));
  const totalPages = Math.max(1, Math.ceil(source.length / state.giftPageSize));
  if (state.giftPage > totalPages) state.giftPage = totalPages;
  if (state.giftPage < 1) state.giftPage = 1;
  giftPageInfo.textContent = `${state.giftPage} / ${totalPages}`;
  giftPrevPage.disabled = state.giftPage <= 1;
  giftNextPage.disabled = state.giftPage >= totalPages;
  giftTimeHeader.textContent = isDraw ? "获奖时间" : "兑换时间";
  giftAreaHeader.textContent = isDraw ? "获奖大区" : "兑换大区";
  giftNameHeader.textContent = isDraw ? "获奖礼包" : "兑换奖励";
  giftExtraHeader.style.display = isDraw ? "" : "none";

  const start = (state.giftPage - 1) * state.giftPageSize;
  const rows = source.slice(start, start + state.giftPageSize);
  if (!rows.length) {
    giftRecordTable.innerHTML = `<tr><td colspan="${isDraw ? 4 : 3}" class="tip">暂无记录</td></tr>`;
    return;
  }
  for (const r of rows) {
    const giftName = isDraw
      ? r.name
      : (r.source === "stash_send" ? `${r.name}（暂存箱发送）` : `${r.name}（-${r.cost || 0}积分）`);
    const tr = document.createElement("tr");
    const euhuangCell = isRareItemResult(r)
      ? `<button class="ghost" data-action="view-rare" data-draw-index="${r.draw_index}">点击查看</button>`
      : "";
    tr.innerHTML = isDraw
      ? `
      <td>${fmtTime(r.ts || r.action_ts)}</td>
      <td>河北一区</td>
      <td>${giftName}</td>
      <td>${euhuangCell}</td>
    `
      : `
      <td>${fmtTime(r.ts || r.action_ts)}</td>
      <td>河北一区</td>
      <td>${giftName}</td>
    `;
    giftRecordTable.appendChild(tr);
  }
}

function renderAnalysis() {
  const a = state.analysis;
  // Avoid stale values after reset / empty analysis response.
  analysisLinearFormula.textContent = "线性近似: y = 0.0000x + 0.00，R² = 0.0000";
  if (!a || !a.summary) {
    analysisSummary.innerHTML = "";
    analysisDistribution.innerHTML = `<div class="tip">暂无数据</div>`;
    analysisExpected.innerHTML = `<tr><td colspan="4" class="tip">暂无数据</td></tr>`;
    analysisConfidence.innerHTML = `<tr><td colspan="4" class="tip">暂无数据</td></tr>`;
    analysisRecent.innerHTML = `<div class="tip">暂无数据</div>`;
    analysisDaily.innerHTML = `<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#8a7b66">暂无日级数据</text>`;
    analysisTrend.innerHTML = `<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#8a7b66">暂无趋势数据</text>`;
    analysisPointsValueDist.innerHTML = `<div class="tip">暂无数据</div>`;
    analysisProbCompare.innerHTML = `<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#8a7b66">暂无数据</text>`;
    analysisAlerts.innerHTML = `<div class="tip">暂无异常提醒</div>`;
    return;
  }

  analysisSummary.innerHTML = "";
  const cards = [
    ["抽奖总次数", `${a.summary.total_draws}`],
    ["道具命中次数", `${a.summary.item_hits}`],
    ["积分命中次数", `${a.summary.points_hits}`],
    ["抽奖获得积分总量", `${a.summary.points_total_from_draw}`],
    ["单抽平均积分", `${a.summary.avg_points_per_draw.toFixed(2)}`],
    ["直发仓库次数", `${a.summary.warehouse_hits}`],
    ["进入暂存箱次数", `${a.summary.stash_hits}`],
    ["当前积分/钥匙", `${a.summary.current_points} / ${a.summary.current_keys}`],
  ];
  for (const [label, value] of cards) {
    const div = document.createElement("div");
    div.className = "stat";
    div.innerHTML = `<div class="label">${label}</div><div class="value">${value}</div>`;
    analysisSummary.appendChild(div);
  }

  analysisDistribution.innerHTML = "";
  const allDist = a.distribution_all || [];
  if (!allDist.length) {
    analysisDistribution.innerHTML = `<div class="tip">暂无数据</div>`;
  } else {
    const maxCount = Math.max(...allDist.map((x) => x.count), 1);
    for (const row of allDist) {
      const item = document.createElement("div");
      item.className = "chart-row";
      const width = (row.count / maxCount) * 100;
      item.innerHTML = `
        <div class="chart-label">
          <span>${row.name}</span>
          <span>${row.count} 次 / ${(row.rate * 100).toFixed(2)}%</span>
        </div>
        <div class="chart-bar-bg"><div class="chart-bar" style="width:${width}%"></div></div>
      `;
      analysisDistribution.appendChild(item);
    }
  }

  analysisExpected.innerHTML = "";
  const compare = a.expected_compare_all || [];
  if (!compare.length) {
    analysisExpected.innerHTML = `<tr><td colspan="4" class="tip">暂无数据</td></tr>`;
  } else {
    for (const row of compare) {
      const tr = document.createElement("tr");
      const dev = row.deviation;
      const color = dev >= 0 ? "#0b8a3d" : "#b32424";
      tr.innerHTML = `
        <td>${row.name}</td>
        <td>${row.expected.toFixed(2)}</td>
        <td>${row.actual}</td>
        <td style="color:${color};font-weight:700;">${dev >= 0 ? "+" : ""}${dev.toFixed(2)}</td>
      `;
      analysisExpected.appendChild(tr);
    }
  }

  renderTrend(a.timeline || [], a.linear_fit || {});
  renderConfidence(a.confidence_rows || []);
  renderRecent(a.recent_vs_global || {});
  renderDailyTrend(a.daily_trend || []);
  renderAlerts(a.alerts || [], a.global_fit || {});
  renderPointsValueDist(a.points_value_distribution || []);
  renderProbCompare(a.expected_compare_all || []);
}

function renderConfidence(rows) {
  analysisConfidence.innerHTML = "";
  if (!rows.length) {
    analysisConfidence.innerHTML = `<tr><td colspan="4" class="tip">暂无数据</td></tr>`;
    return;
  }
  for (const r of rows) {
    const zColor = Math.abs(r.z_score) >= 2 ? "#b32424" : "#0b8a3d";
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${r.name}</td>
      <td>${(r.observed_rate * 100).toFixed(2)}%</td>
      <td>[${(r.ci_low * 100).toFixed(2)}%, ${(r.ci_high * 100).toFixed(2)}%]</td>
      <td style="color:${zColor};font-weight:700;">${r.z_score.toFixed(2)}</td>
    `;
    analysisConfidence.appendChild(tr);
  }
}

function renderRecent(obj) {
  analysisRecent.innerHTML = "";
  const rows = obj.rows || [];
  const window = obj.window || 50;
  if (!rows.length) {
    analysisRecent.innerHTML = `<div class="tip">暂无数据</div>`;
    return;
  }
  const header = document.createElement("div");
  header.className = "tip";
  header.textContent = `窗口大小：最近${window}抽`;
  analysisRecent.appendChild(header);
  for (const r of rows) {
    const diff = (r.recent_rate - r.global_rate) * 100;
    const color = diff >= 0 ? "#0b8a3d" : "#b32424";
    const div = document.createElement("div");
    div.className = "chart-row";
    div.innerHTML = `
      <div class="chart-label">
        <span>${r.name}</span>
        <span>最近${(r.recent_rate * 100).toFixed(2)}% / 全局${(r.global_rate * 100).toFixed(2)}%</span>
      </div>
      <div style="color:${color};font-weight:700;">差值 ${diff >= 0 ? "+" : ""}${diff.toFixed(2)}%</div>
    `;
    analysisRecent.appendChild(div);
  }
}

function renderTrend(timeline, fit) {
  const width = 600;
  const height = 240;
  const pad = 30;
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;

  if (!timeline.length) {
    analysisTrend.innerHTML = `<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#8a7b66">暂无趋势数据</text>`;
    analysisLinearFormula.textContent = "线性近似: y = 0.0000x + 0.00，R² = 0.0000";
    return;
  }

  const maxX = timeline[timeline.length - 1].x || 1;
  const maxY = Math.max(...timeline.map((p) => p.total_points), 1);
  const points = timeline
    .map((p) => {
      const x = pad + (p.x / maxX) * innerW;
      const y = pad + innerH - (p.total_points / maxY) * innerH;
      return `${x},${y}`;
    })
    .join(" ");
  const fitPoints = timeline
    .map((p) => {
      const x = pad + (p.x / maxX) * innerW;
      const yVal = fit.slope * p.x + fit.intercept;
      const y = pad + innerH - (Math.max(0, yVal) / maxY) * innerH;
      return `${x},${y}`;
    })
    .join(" ");

  analysisTrend.innerHTML = `
    <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" stroke="#d3c6b0" />
    <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" stroke="#d3c6b0" />
    <polyline fill="none" stroke="#ff7a00" stroke-width="3" points="${points}" />
    <polyline fill="none" stroke="#2b6ce8" stroke-width="2" stroke-dasharray="6 4" points="${fitPoints}" />
    <text x="${pad}" y="${pad - 8}" fill="#7f6c55" font-size="12">累计积分</text>
    <text x="${width - pad}" y="${height - 10}" fill="#7f6c55" font-size="12" text-anchor="end">抽奖次数</text>
    <text x="${pad + 4}" y="${height - pad - 4}" fill="#7f6c55" font-size="12">${maxY}</text>
  `;
  const slope = Number(fit.slope || 0);
  const intercept = Number(fit.intercept || 0);
  const sign = intercept >= 0 ? "+" : "-";
  analysisLinearFormula.textContent = `线性近似: y = ${slope.toFixed(4)}x ${sign} ${Math.abs(intercept).toFixed(2)}，R² = ${Number(fit.r2 || 0).toFixed(4)}`;
}

function renderDailyTrend(daily) {
  const width = 600;
  const height = 240;
  const pad = 30;
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  if (!daily.length) {
    analysisDaily.innerHTML = `<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#8a7b66">暂无日级数据</text>`;
    return;
  }
  const maxX = daily.length - 1 || 1;
  const maxY = Math.max(...daily.map((d) => d.draws), 1);
  const points = daily
    .map((d, i) => {
      const x = pad + (i / maxX) * innerW;
      const y = pad + innerH - (d.draws / maxY) * innerH;
      return `${x},${y}`;
    })
    .join(" ");
  analysisDaily.innerHTML = `
    <line x1="${pad}" y1="${height - pad}" x2="${width - pad}" y2="${height - pad}" stroke="#d3c6b0" />
    <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" stroke="#d3c6b0" />
    <polyline fill="none" stroke="#2f77f1" stroke-width="3" points="${points}" />
    <text x="${pad}" y="${pad - 8}" fill="#7f6c55" font-size="12">单日抽奖次数</text>
    <text x="${pad + 4}" y="${height - pad - 4}" fill="#7f6c55" font-size="12">${maxY}</text>
  `;
}

function renderAlerts(alerts, fit) {
  analysisAlerts.innerHTML = "";
  const fitDiv = document.createElement("div");
  fitDiv.className = "tip";
  fitDiv.textContent = `全局卡方统计量 χ²=${(fit.chi_square || 0).toFixed(2)}，自由度=${fit.dof || 0}`;
  analysisAlerts.appendChild(fitDiv);
  if (!alerts.length) {
    analysisAlerts.appendChild(Object.assign(document.createElement("div"), { className: "tip", textContent: "暂无异常提醒" }));
    return;
  }
  for (const a of alerts) {
    const div = document.createElement("div");
    div.className = "chart-row";
    div.textContent = a;
    analysisAlerts.appendChild(div);
  }
}

function renderPointsValueDist(rows) {
  analysisPointsValueDist.innerHTML = "";
  if (!rows.length) {
    analysisPointsValueDist.innerHTML = `<div class="tip">暂无数据</div>`;
    return;
  }
  const maxCount = Math.max(...rows.map((r) => r.count), 1);
  for (const r of rows) {
    const div = document.createElement("div");
    div.className = "chart-row";
    const width = (r.count / maxCount) * 100;
    div.innerHTML = `
      <div class="chart-label"><span>${r.name}</span><span>${r.count}次</span></div>
      <div class="chart-bar-bg"><div class="chart-bar" style="width:${width}%"></div></div>
    `;
    analysisPointsValueDist.appendChild(div);
  }
}

function renderProbCompare(rows) {
  const width = 600;
  const height = 240;
  const pad = 32;
  const innerW = width - pad * 2;
  const innerH = height - pad * 2;
  if (!rows.length) {
    analysisProbCompare.innerHTML = `<text x="50%" y="50%" dominant-baseline="middle" text-anchor="middle" fill="#8a7b66">暂无数据</text>`;
    return;
  }

  const points = rows.map((r) => Number(r.actual || 0) - Number(r.expected || 0));
  const maxAbs = Math.max(...points.map((x) => Math.abs(x)), 1);
  const centerY = pad + innerH / 2;
  const step = rows.length > 1 ? innerW / (rows.length - 1) : 0;

  const linePoints = points
    .map((d, i) => {
      const x = pad + i * step;
      const y = centerY - (d / maxAbs) * (innerH / 2);
      return `${x},${y}`;
    })
    .join(" ");

  const dots = points
    .map((d, i) => {
      const x = pad + i * step;
      const y = centerY - (d / maxAbs) * (innerH / 2);
      const c = d >= 0 ? "#0b8a3d" : "#b32424";
      return `<circle cx="${x}" cy="${y}" r="3.2" fill="${c}" />`;
    })
    .join("");

  const nonZero = points.filter((v) => v !== 0);
  const avgDev = nonZero.length ? nonZero.reduce((a, b) => a + b, 0) / nonZero.length : 0;

  analysisProbCompare.innerHTML = `
    <line x1="${pad}" y1="${centerY}" x2="${width - pad}" y2="${centerY}" stroke="#d3c6b0" />
    <line x1="${pad}" y1="${pad}" x2="${pad}" y2="${height - pad}" stroke="#d3c6b0" />
    <polyline fill="none" stroke="#2f77f1" stroke-width="2.4" points="${linePoints}" />
    ${dots}
    <text x="${pad + 6}" y="${pad + 12}" fill="#6f5b48" font-size="12">偏差(实际-理论)</text>
    <text x="${pad + 6}" y="${centerY - (innerH / 2) + 14}" fill="#6f5b48" font-size="11">+${maxAbs.toFixed(2)}</text>
    <text x="${pad + 6}" y="${centerY + (innerH / 2) - 6}" fill="#6f5b48" font-size="11">-${maxAbs.toFixed(2)}</text>
    <text x="${width - pad}" y="${height - 10}" fill="#6f5b48" font-size="12" text-anchor="end">奖项序列(全部)</text>
    <text x="${width - pad}" y="${pad + 12}" fill="#6f5b48" font-size="11" text-anchor="end">平均偏差 ${avgDev >= 0 ? "+" : ""}${avgDev.toFixed(2)}</text>
  `;
}

function renderResultPopup(results, title = "恭喜您获得", showClassicBlocks = true) {
  resultBody.innerHTML = "";
  resultBody.classList.toggle("single", results.length === 1);
  let totalPoints = 0;
  resultTitle.textContent = title;
  resultTotal.style.display = showClassicBlocks ? "" : "none";
  resultNotes.style.display = showClassicBlocks ? "" : "none";
  for (const r of results) {
    const div = document.createElement("div");
    if (r.type === "item") {
      const poolItem = (state.config?.pool || []).find((x) => x.type === "item" && x.id === r.id);
      const tier = poolItem ? paletteClass(poolItem) : "palette-orange";
      div.className = `result-item ${tier}`.trim();
    } else {
      div.className = "result-item palette-gray";
    }

    if (r.type === "item") {
      const img = r.popup_image_url || r.image_url;
      const thumb = img ? `<img class="result-thumb" src="${img}" alt="${r.name}">` : "";
      div.innerHTML = `
        <div class="result-top">${thumb}</div>
        <div class="result-bottom"><div class="name">${r.name}</div></div>
      `;
    } else {
      const pImg = state.config?.points_image_url || "/cf_images/jifen.png";
      div.innerHTML = `
        <div class="result-top"><img class="result-thumb" src="${pImg}" alt="${r.name}"></div>
        <div class="result-bottom"><div class="name">${r.name}</div></div>
      `;
      totalPoints += Number(r.points || 0);
    }
    resultBody.appendChild(div);
  }
  resultTotalPoints.textContent = totalPoints;
}

function showResults(results) {
  // "中奖后不再单独弹出奖励弹窗": only disable standalone rare popups.
  // Draw flow should still show the classic summary popup.
  if (state.skipPopup) {
    state.rarePopupQueue = [];
    state.pendingClassicResults = null;
    renderResultPopup(results, "恭喜您获得", true);
    modal.classList.add("show");
    modal.setAttribute("aria-hidden", "false");
    return;
  }

  const rareItems = results.filter((r) => isRareItemResult(r));

  state.rarePopupQueue = [...rareItems];
  state.pendingClassicResults = results;
  if (state.rarePopupQueue.length > 0) {
    const first = state.rarePopupQueue.shift();
    renderResultPopup([first], "恭喜获得稀有道具", false);
  } else {
    renderResultPopup(results, "恭喜您获得", true);
    state.pendingClassicResults = null;
  }
  modal.classList.add("show");
  modal.setAttribute("aria-hidden", "false");
}

async function refresh() {
  const [config, user, analysis] = await Promise.all([api("/api/config"), api("/api/state"), api("/api/analysis")]);
  state.config = config;
  state.user = user;
  state.analysis = analysis;
  if (config.decompose_mode === "points") state.decomposeView = "points";
  if (config.decompose_mode === "keys") state.decomposeView = "keys";
  renderAll();
  renderProbabilityTable();
}

async function refreshAnalysis() {
  state.analysis = await api("/api/analysis");
  renderAnalysis();
}

async function buy(option) {
  const data = await api("/api/buy", "POST", { option });
  state.user = data.state;
  renderAll();
  await refreshAnalysis();
  showToast("购买成功，钥匙已到账");
}

async function draw(count) {
  const data = await api("/api/draw", "POST", { count });
  state.user = data.state;
  renderAll();
  await refreshAnalysis();
  showResults(data.results);
}

async function decompose(itemId, qty) {
  const data = await api("/api/stash/decompose", "POST", { item_id: itemId, qty });
  state.user = data.state;
  renderAll();
  await refreshAnalysis();
  showToast(`分解成功 +${data.gain_points} 积分 +${data.gain_keys} 钥匙`);
}

async function sendStash(itemId, qty) {
  const data = await api("/api/stash/send", "POST", { item_id: itemId, qty });
  state.user = data.state;
  renderAll();
  await refreshAnalysis();
  showToast("已发送到仓库");
}

async function actionStashRecord(recordId, action) {
  const data = await api("/api/stash/record-action", "POST", { record_id: recordId, action });
  state.user = data.state;
  renderAll();
  await refreshAnalysis();
  if (action === "send") {
    showToast("已发送到仓库");
  } else {
    showToast(`分解成功 +${data.gain_points} 积分 +${data.gain_keys} 钥匙`);
  }
}

async function redeem(itemId) {
  const data = await api("/api/redeem", "POST", { item_id: itemId, qty: 1 });
  state.user = data.state;
  renderAll();
  await refreshAnalysis();
  showToast(`兑换成功，已发往仓库，消耗 ${data.cost} 积分`);
}

async function resetState() {
  const data = await api("/api/state/reset", "POST", {});
  state.user = data.state;
  renderAll();
  await refreshAnalysis();
  showToast("已重置模拟数据");
}

async function reloadConfig() {
  await api("/api/config/reload", "POST", {});
  await refresh();
  showToast("配置已重载");
}

function bindEvents() {
  document.getElementById("buySingle").addEventListener("click", () => run(async () => buy("single")));
  document.getElementById("buyBundle").addEventListener("click", () => run(async () => buy("bundle")));
  runSimulationBtn.addEventListener("click", () => run(runSimulation));
  document.getElementById("draw1").addEventListener("click", () => run(async () => draw(1)));
  document.getElementById("draw10").addEventListener("click", () => run(async () => draw(10)));
  document.getElementById("resetState").addEventListener("click", () => run(resetState));
  document.getElementById("reloadConfig").addEventListener("click", () => run(reloadConfig));
  document.getElementById("showProbBtn").addEventListener("click", () => {
    probabilityModal.classList.add("show");
    probabilityModal.setAttribute("aria-hidden", "false");
  });
  document.getElementById("closeProbModal").addEventListener("click", () => {
    probabilityModal.classList.remove("show");
    probabilityModal.setAttribute("aria-hidden", "true");
  });
  document.getElementById("openGiftRecord").addEventListener("click", () => {
    state.giftTab = "draw";
    state.giftPage = 1;
    giftTabDraw.classList.add("active");
    giftTabRedeem.classList.remove("active");
    renderGiftRecords();
    giftRecordModal.classList.add("show");
    giftRecordModal.setAttribute("aria-hidden", "false");
  });
  document.getElementById("closeGiftRecordModal").addEventListener("click", () => {
    giftRecordModal.classList.remove("show");
    giftRecordModal.setAttribute("aria-hidden", "true");
  });
  document.getElementById("openStashModal").addEventListener("click", () => {
    state.stashPage = 1;
    renderStash();
    stashModal.classList.add("show");
    stashModal.setAttribute("aria-hidden", "false");
  });
  document.getElementById("closeStashModal").addEventListener("click", () => {
    stashModal.classList.remove("show");
    stashModal.setAttribute("aria-hidden", "true");
  });
  document.getElementById("closeModal").addEventListener("click", closeModal);
  skipPopup.addEventListener("change", () => {
    state.skipPopup = skipPopup.checked;
    localStorage.setItem("skipPopup", state.skipPopup ? "1" : "0");
  });

  modal.addEventListener("click", (e) => {
    if (e.target === modal) closeModal();
  });
  probabilityModal.addEventListener("click", (e) => {
    if (e.target === probabilityModal) {
      probabilityModal.classList.remove("show");
      probabilityModal.setAttribute("aria-hidden", "true");
    }
  });
  giftRecordModal.addEventListener("click", (e) => {
    if (e.target === giftRecordModal) {
      giftRecordModal.classList.remove("show");
      giftRecordModal.setAttribute("aria-hidden", "true");
    }
  });
  stashModal.addEventListener("click", (e) => {
    if (e.target === stashModal) {
      stashModal.classList.remove("show");
      stashModal.setAttribute("aria-hidden", "true");
    }
  });

  stashModalTable.addEventListener("click", (e) => {
    const target = e.target;
    if (!(target instanceof HTMLElement)) return;
    const action = target.dataset.action;
    const recordId = Number(target.dataset.recordId || 0);
    if (!action || !recordId) return;
    if (action === "send-record") {
      run(async () => actionStashRecord(recordId, "send"));
    }
    if (action === "decompose-record") {
      run(async () => actionStashRecord(recordId, "decompose"));
    }
  });

  stashPrevPage.addEventListener("click", () => {
    if (state.stashPage > 1) {
      state.stashPage -= 1;
      renderStash();
    }
  });
  stashNextPage.addEventListener("click", () => {
    const rows = state.user?.stash_records || [];
    const totalPages = Math.max(1, Math.ceil(rows.length / state.stashPageSize));
    if (state.stashPage < totalPages) {
      state.stashPage += 1;
      renderStash();
    }
  });
  giftTabDraw.addEventListener("click", () => {
    state.giftTab = "draw";
    state.giftPage = 1;
    giftTabDraw.classList.add("active");
    giftTabRedeem.classList.remove("active");
    renderGiftRecords();
  });
  giftTabRedeem.addEventListener("click", () => {
    state.giftTab = "redeem";
    state.giftPage = 1;
    giftTabRedeem.classList.add("active");
    giftTabDraw.classList.remove("active");
    renderGiftRecords();
  });
  giftPrevPage.addEventListener("click", () => {
    if (state.giftPage > 1) {
      state.giftPage -= 1;
      renderGiftRecords();
    }
  });
  giftNextPage.addEventListener("click", () => {
    state.giftPage += 1;
    renderGiftRecords();
  });
  giftRecordTable.addEventListener("click", (e) => {
    const target = e.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.dataset.action !== "view-rare") return;
    const drawIndex = Number(target.dataset.drawIndex || 0);
    if (!drawIndex) return;
    const r = (state.user.history || []).find((x) => Number(x.draw_index) === drawIndex);
    if (!r) return;
    giftRecordModal.classList.remove("show");
    giftRecordModal.setAttribute("aria-hidden", "true");
    state.reopenGiftAfterRare = true;
    state.rarePopupQueue = [];
    state.pendingClassicResults = null;
    renderResultPopup([r], "恭喜获得稀有道具", false);
    modal.classList.add("show");
    modal.setAttribute("aria-hidden", "false");
  });

  redeemList.addEventListener("click", (e) => {
    const target = e.target;
    if (!(target instanceof HTMLElement)) return;
    const action = target.dataset.action;
    const itemId = target.dataset.id;
    if (action === "redeem" && itemId) {
      run(async () => redeem(itemId));
    }
  });
}

function closeModal() {
  if (state.rarePopupQueue.length > 0) {
    const next = state.rarePopupQueue.shift();
    renderResultPopup([next], "恭喜获得稀有道具", false);
    return;
  }
  if (state.pendingClassicResults) {
    const all = state.pendingClassicResults;
    state.pendingClassicResults = null;
    renderResultPopup(all, "恭喜您获得", true);
    return;
  }
  modal.classList.remove("show");
  modal.setAttribute("aria-hidden", "true");
  if (state.reopenGiftAfterRare) {
    state.reopenGiftAfterRare = false;
    giftRecordModal.classList.add("show");
    giftRecordModal.setAttribute("aria-hidden", "false");
  }
}

async function run(fn) {
  try {
    await fn();
  } catch (err) {
    showToast(err.message || "操作失败");
  }
}

(async function boot() {
  bindEvents();
  window.addEventListener("resize", renderPrizeGrid);
  await run(refresh);
})();
