const dataBase = location.pathname.includes("/public/") ? "../data" : "data";
const dataUrl = `${dataBase}/current/crawlers.json`;
const robotsUrl = `${dataBase}/current/robots-ai.txt`;
let data = null;
let filtered = [];
let sortState = { key: "prefixes", direction: "desc" };
const number = new Intl.NumberFormat("en-US");
const filterIds = ["category-filter", "operator-filter", "source-filter", "service-filter"];
const filterFields = {
  "category-filter": "category",
  "operator-filter": "operator",
  "source-filter": "sourceType",
  "service-filter": "id",
};
const filterLabels = {
  "category-filter": "All categories",
  "operator-filter": "All operators",
  "source-filter": "All source types",
  "service-filter": "All services",
};
const categoryNames = {
  ai: "AI crawlers",
  archive: "Archive",
  fetcher: "Fetchers",
  monitoring: "Monitoring",
  search: "Search",
  "security-scanner": "Security scanners",
  seo: "SEO crawlers",
  social: "Social previews",
};
const sourceTypeNames = {
  documented_user_agent: "Documented UA",
  known_static: "Known static",
  official_json: "Official JSON",
  official_text: "Official text",
};
const countryNames = {
  US: "United States",
  GB: "United Kingdom",
  CN: "China",
  RU: "Russia",
  DE: "Germany",
  FR: "France",
  JP: "Japan",
  SG: "Singapore",
  CZ: "Czechia",
};

function fmt(value) {
  return number.format(value || 0);
}

async function load() {
  updateExportLinks();
  const [dataResponse, robotsResponse] = await Promise.all([
    fetch(dataUrl, { cache: "no-store" }),
    fetch(robotsUrl, { cache: "no-store" }).catch(() => null),
  ]);
  data = await dataResponse.json();
  document.getElementById("robots-preview").textContent =
    robotsResponse && robotsResponse.ok ? await robotsResponse.text() : "";
  updateFilterOptions();
  render();
}

function updateExportLinks() {
  document.getElementById("robots-link").href = `${dataBase}/current/robots-ai.txt`;
  document.getElementById("nginx-link").href = `${dataBase}/current/nginx-ai-map.conf`;
  document.getElementById("json-link").href = `${dataBase}/current/crawlers.json`;
}

function updateFilterOptions() {
  for (const id of filterIds) {
    const select = document.getElementById(id);
    const selected = select.value || "all";
    const scoped = applyFilters({ ignore: id, includeQuery: true });
    const field = filterFields[id];
    const values = [...new Set(scoped.map((s) => s[field]))].filter(Boolean).sort((a, b) => labelFor(field, a).localeCompare(labelFor(field, b)));
    fill(id, values);
    select.value = selected === "all" || values.includes(selected) ? selected : "all";
  }
}

function fill(id, values) {
  const select = document.getElementById(id);
  select.innerHTML =
    `<option value="all">${escapeHtml(filterLabels[id])}</option>` +
    values.map((value) => `<option value="${escapeHtml(value)}">${escapeHtml(labelFor(filterFields[id], value))}</option>`).join("");
}

function filters() {
  return {
    category: document.getElementById("category-filter").value,
    operator: document.getElementById("operator-filter").value,
    source: document.getElementById("source-filter").value,
    service: document.getElementById("service-filter").value,
    query: document.getElementById("search").value.trim().toLowerCase(),
  };
}

function applyFilters(options = {}) {
  const f = filters();
  const ignore = options.ignore;
  const includeQuery = options.includeQuery !== false;
  return data.services
    .filter((s) => ignore === "category-filter" || f.category === "all" || s.category === f.category)
    .filter((s) => ignore === "operator-filter" || f.operator === "all" || s.operator === f.operator)
    .filter((s) => ignore === "source-filter" || f.source === "all" || s.sourceType === f.source)
    .filter((s) => ignore === "service-filter" || f.service === "all" || s.id === f.service)
    .filter((s) => {
      if (!includeQuery || !f.query) return true;
      return [s.service, s.operator, s.sourceUrl, s.userAgentPatterns.join(" "), s.category]
        .join(" ")
        .toLowerCase()
        .includes(f.query);
    });
}

function render() {
  updateFilterOptions();
  filtered = applyFilters();
  filtered = sortServices(filtered);
  document.getElementById("generated-at").textContent = `Updated ${data.generatedAt}`;
  renderFilterSummary();
  renderMetrics();
  renderInsights();
  renderMap();
  renderCategoryChart();
  renderOperatorBars();
  renderTable();
}

function renderMetrics() {
  const prefixes = filtered.reduce((sum, s) => sum + s.counts.prefixes, 0);
  const ipv4 = filtered.reduce((sum, s) => sum + s.counts.ipv4, 0);
  const ipv6 = filtered.reduce((sum, s) => sum + s.counts.ipv6, 0);
  const ai = filtered.filter((s) => s.category === "ai").reduce((sum, s) => sum + s.counts.prefixes, 0);
  const ok = filtered.filter((s) => s.sourceOk).length;
  const official = filtered.filter((s) => s.ipListAuthoritative).length;
  const metrics = [
    ["Services", fmt(filtered.length)],
    ["Prefixes", fmt(prefixes)],
    ["AI Prefixes", fmt(ai)],
    ["IPv4", fmt(ipv4)],
    ["IPv6", fmt(ipv6)],
    ["Official", `${official}/${filtered.length || 0}`],
  ];
  document.getElementById("status-dot").style.background = ok < filtered.length ? "var(--amber)" : "var(--green)";
  document.getElementById("metrics").innerHTML = metrics
    .map(([label, value]) => `<div class="metric"><span>${label}</span><strong>${value}</strong></div>`)
    .join("");
}

function renderFilterSummary() {
  const f = filters();
  const active = [];
  if (f.category !== "all") active.push(labelFor("category", f.category));
  if (f.operator !== "all") active.push(f.operator);
  if (f.source !== "all") active.push(labelFor("sourceType", f.source));
  if (f.service !== "all") active.push(labelFor("id", f.service));
  if (f.query) active.push(`Search: ${f.query}`);
  const prefixCount = filtered.reduce((sum, s) => sum + s.counts.prefixes, 0);
  document.getElementById("filter-summary").textContent = active.length
    ? `${fmt(filtered.length)} services, ${fmt(prefixCount)} prefixes | ${active.join(" / ")}`
    : `${fmt(filtered.length)} services, ${fmt(prefixCount)} prefixes | all data`;
}

function renderInsights() {
  document.getElementById("insights").innerHTML = data.insights.slice(0, 4)
    .map((item) => `
      <div class="insight">
        <span>${escapeHtml(item.title)}</span>
        <strong>${escapeHtml(item.value)}</strong>
        <p>${escapeHtml(item.detail)}</p>
      </div>
    `)
    .join("");
}

function renderMap() {
  const rows = aggregate(filtered, "operatorCountry");
  document.getElementById("map-note").textContent = `${fmt(filtered.length)} services in current filter`;
  if (!window.Plotly) {
    document.getElementById("map").textContent = "Map library unavailable";
    return;
  }
  Plotly.react("map", [{
    type: "choropleth",
    locationmode: "ISO-3",
    locations: rows.map((row) => iso2ToIso3(row.key)),
    z: rows.map((row) => row.count),
    text: rows.map((row) => `${countryLabel(row.key)}<br>${fmt(row.count)} prefixes`),
    hovertemplate: "%{text}<extra></extra>",
    colorscale: [[0, "#edf3fb"], [0.5, "#7db7ff"], [1, "#2f6fdd"]],
    marker: { line: { color: "#fff", width: 0.5 } },
    colorbar: { thickness: 12, outlinewidth: 0 },
  }], {
    margin: { l: 0, r: 0, t: 0, b: 0 },
    paper_bgcolor: "rgba(0,0,0,0)",
    geo: {
      projection: { type: "natural earth" },
      showframe: false,
      showcoastlines: true,
      coastlinecolor: "#b8c7da",
      showcountries: true,
      countrycolor: "#ffffff",
      showland: true,
      landcolor: "#eef3fb",
      showocean: true,
      oceancolor: "#f8fbff",
      bgcolor: "rgba(0,0,0,0)",
    },
  }, { displayModeBar: false, responsive: true });
}

function renderCategoryChart() {
  const canvas = document.getElementById("category-chart");
  const ctx = setupCanvas(canvas);
  const { width, height } = canvas.getBoundingClientRect();
  ctx.clearRect(0, 0, width, height);
  const rows = aggregate(filtered, "category");
  const total = Math.max(rows.reduce((sum, row) => sum + row.count, 0), 1);
  const colors = ["#2f6fdd", "#c74755", "#b56b00", "#23855d"];
  let start = -Math.PI / 2;
  const cx = Math.min(width * 0.32, 150);
  const cy = height / 2;
  const radius = Math.min(height * 0.34, 82);
  rows.forEach((row, index) => {
    const angle = (row.count / total) * Math.PI * 2;
    ctx.beginPath();
    ctx.moveTo(cx, cy);
    ctx.fillStyle = colors[index % colors.length];
    ctx.arc(cx, cy, radius, start, start + angle);
    ctx.closePath();
    ctx.fill();
    start += angle;
  });
  ctx.beginPath();
  ctx.fillStyle = "#fff";
  ctx.arc(cx, cy, radius * 0.58, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = "#172033";
  ctx.font = "700 22px system-ui";
  ctx.textAlign = "center";
  ctx.fillText(fmt(total), cx, cy + 8);
  ctx.textAlign = "left";
  rows.forEach((row, index) => {
    const y = 48 + index * 38;
    ctx.fillStyle = colors[index % colors.length];
    ctx.fillRect(width * 0.55, y - 12, 14, 14);
    ctx.fillStyle = "#172033";
    ctx.font = "700 14px system-ui";
    ctx.fillText(`${labelFor("category", row.key)} ${fmt(row.count)}`, width * 0.55 + 24, y);
  });
}

function renderOperatorBars() {
  const rows = aggregate(filtered, "operator");
  const max = Math.max(...rows.map((r) => r.count), 1);
  document.getElementById("operator-bars").innerHTML = rows.map((row) => `
    <div class="bar-row" data-value="${escapeHtml(row.key)}">
      <span><code>${escapeHtml(row.key)}</code> ${fmt(row.count)}</span>
      <div class="bar-line"><div class="bar-fill" style="width:${(row.count / max) * 100}%"></div></div>
    </div>
  `).join("");
  document.querySelectorAll("#operator-bars .bar-row").forEach((row) => {
    row.addEventListener("click", () => {
      document.getElementById("operator-filter").value = row.dataset.value;
      render();
    });
  });
}

function renderTable() {
  document.getElementById("table-note").textContent = `${fmt(filtered.length)} services`;
  document.querySelectorAll("[data-sort]").forEach((button) => {
    button.classList.toggle("active", button.dataset.sort === sortState.key);
    button.classList.toggle("asc", button.dataset.sort === sortState.key && sortState.direction === "asc");
    button.classList.toggle("desc", button.dataset.sort === sortState.key && sortState.direction === "desc");
  });
  document.getElementById("service-table").innerHTML = filtered.map((s) => `
    <tr>
      <td><strong>${escapeHtml(s.service)}</strong><br><span>${escapeHtml(s.operator)}</span></td>
      <td><span class="pill ${escapeHtml(s.category)}">${escapeHtml(labelFor("category", s.category))}</span></td>
      <td><a href="${escapeHtml(s.sourceUrl)}">${escapeHtml(labelFor("sourceType", s.sourceType))}</a><br><span>${s.sourceOk ? "ok" : "cached/error"}</span></td>
      <td><strong>${fmt(s.counts.prefixes)}</strong><br><span>${fmt(s.counts.ipv4)} IPv4 / ${fmt(s.counts.ipv6)} IPv6</span></td>
      <td>${s.userAgentPatterns.map((ua) => `<code>${escapeHtml(ua)}</code>`).join("<br>")}</td>
      <td>${s.ipListAuthoritative ? "authoritative IP list" : "UA documented only"}${s.note ? `<br><span>${escapeHtml(s.note)}</span>` : ""}</td>
    </tr>
  `).join("");
}

function sortServices(rows) {
  const direction = sortState.direction === "asc" ? 1 : -1;
  return [...rows].sort((a, b) => {
    const av = sortValue(a, sortState.key);
    const bv = sortValue(b, sortState.key);
    if (typeof av === "number" && typeof bv === "number") return (av - bv) * direction;
    return String(av).localeCompare(String(bv)) * direction;
  });
}

function sortValue(service, key) {
  if (key === "prefixes") return service.counts.prefixes;
  if (key === "authority") return service.ipListAuthoritative ? 1 : 0;
  return service[key] || "";
}

function aggregate(rows, key) {
  const out = new Map();
  for (const row of rows) {
    const id = row[key] || "unknown";
    out.set(id, (out.get(id) || 0) + row.counts.prefixes);
  }
  return [...out.entries()].map(([key, count]) => ({ key, count })).sort((a, b) => b.count - a.count);
}

function labelFor(field, value) {
  if (field === "category") return categoryNames[value] || value;
  if (field === "sourceType") return sourceTypeNames[value] || value;
  if (field === "id") return data?.services.find((s) => s.id === value)?.service || value;
  return value;
}

function countryLabel(code) {
  return `${code} ${countryNames[code] || code}`;
}

function buildFilteredPayload() {
  const prefixes = filtered.flatMap((s) => [...s.prefixes.ipv4, ...s.prefixes.ipv6]);
  const summary = {
    services: filtered.length,
    prefixes: prefixes.length,
    ipv4: filtered.reduce((sum, s) => sum + s.counts.ipv4, 0),
    ipv6: filtered.reduce((sum, s) => sum + s.counts.ipv6, 0),
    authoritativeLists: filtered.filter((s) => s.ipListAuthoritative).length,
  };
  return {
    generatedAt: data.generatedAt,
    exportedAt: new Date().toISOString(),
    filters: filters(),
    summary,
    services: filtered,
  };
}

function currentCidrs() {
  return filtered.flatMap((s) => [...s.prefixes.ipv4, ...s.prefixes.ipv6]).sort();
}

function exportCurrent(type) {
  const payload = buildFilteredPayload();
  const baseName = `crawlerscope-${type}-${new Date().toISOString().slice(0, 10)}`;
  let count = 0;
  if (type === "json") {
    download(`${baseName}.json`, JSON.stringify(payload, null, 2) + "\n", "application/json");
    count = payload.services.length;
  } else if (type === "csv") {
    download(`${baseName}.csv`, buildCsv(filtered), "text/csv");
    count = payload.services.length;
  } else if (type === "cidr") {
    count = currentCidrs().length;
    download(`${baseName}.txt`, currentCidrs().join("\n") + "\n", "text/plain");
  } else if (type === "robots") {
    download(`${baseName}.txt`, buildRobots(filtered), "text/plain");
    count = filtered.filter((s) => s.category === "ai").length;
  } else if (type === "nginx") {
    download(`${baseName}.conf`, buildNginxMap(filtered), "text/plain");
    count = filtered.length;
  }
  setExportStatus(`Exported ${fmt(count)} ${type === "cidr" ? "CIDRs" : "records"}`);
}

function buildCsv(rows) {
  const header = ["id", "service", "operator", "category", "sourceType", "authoritative", "sourceOk", "prefixes", "ipv4", "ipv6", "sourceUrl"];
  const lines = rows.map((s) => [
    s.id,
    s.service,
    s.operator,
    s.category,
    s.sourceType,
    s.ipListAuthoritative,
    s.sourceOk,
    s.counts.prefixes,
    s.counts.ipv4,
    s.counts.ipv6,
    s.sourceUrl,
  ].map(csvCell).join(","));
  return `${header.join(",")}\n${lines.join("\n")}\n`;
}

function buildRobots(rows) {
  const lines = ["# Generated by CrawlerScope filtered export", ""];
  rows
    .filter((s) => s.category === "ai")
    .flatMap((s) => s.userAgentPatterns)
    .forEach((ua) => lines.push(`User-agent: ${ua}`, "Disallow: /", ""));
  return lines.join("\n").trimEnd() + "\n";
}

function buildNginxMap(rows) {
  const lines = ["# Generated by CrawlerScope filtered export", "map $http_user_agent $crawler_scope_selected_bot {", "    default 0;"];
  rows.flatMap((s) => s.userAgentPatterns).forEach((ua) => {
    lines.push(`    ~*${ua.replace("/", "\\/")} 1;`);
  });
  lines.push("}");
  return lines.join("\n") + "\n";
}

function csvCell(value) {
  const text = String(value ?? "");
  return /[",\n]/.test(text) ? `"${text.replace(/"/g, '""')}"` : text;
}

function download(filename, content, type) {
  const blob = new Blob([content], { type });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

async function copyCidrs() {
  const cidrs = currentCidrs();
  const text = cidrs.join("\n") + "\n";
  try {
    await navigator.clipboard.writeText(text);
    setExportStatus(`Copied ${fmt(cidrs.length)} CIDRs`);
  } catch (error) {
    setExportStatus("Clipboard unavailable; use CIDR export");
  }
}

function resetFilters() {
  for (const id of filterIds) document.getElementById(id).value = "all";
  document.getElementById("search").value = "";
  sortState = { key: "prefixes", direction: "desc" };
  setExportStatus("");
  render();
}

function applyPreset(preset) {
  resetFilters();
  if (preset === "ai") {
    document.getElementById("category-filter").value = "ai";
  } else if (preset === "official") {
    document.getElementById("source-filter").value = "official_json";
  } else if (preset === "monitoring") {
    document.getElementById("category-filter").value = "monitoring";
  }
  render();
}

function setExportStatus(message) {
  document.getElementById("export-status").textContent = message;
}

function setupCanvas(canvas) {
  const ratio = window.devicePixelRatio || 1;
  const width = canvas.clientWidth || canvas.parentElement.clientWidth;
  const height = Number(canvas.getAttribute("height"));
  canvas.width = width * ratio;
  canvas.height = height * ratio;
  const ctx = canvas.getContext("2d");
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  return ctx;
}

function iso2ToIso3(code) {
  return { US: "USA", GB: "GBR", CN: "CHN", RU: "RUS", DE: "DEU", FR: "FRA", JP: "JPN", SG: "SGP", CZ: "CZE" }[code] || code;
}

function escapeHtml(value) {
  return String(value || "").replace(/[&<>"']/g, (char) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#039;" })[char]);
}

filterIds.forEach((id) => {
  document.getElementById(id).addEventListener("change", render);
});
document.getElementById("search").addEventListener("input", render);
document.getElementById("reset-filters").addEventListener("click", resetFilters);
document.getElementById("copy-cidr").addEventListener("click", copyCidrs);
document.querySelectorAll("[data-preset]").forEach((button) => {
  button.addEventListener("click", () => applyPreset(button.dataset.preset));
});
document.querySelectorAll("[data-export]").forEach((button) => {
  button.addEventListener("click", () => exportCurrent(button.dataset.export));
});
document.querySelectorAll("[data-sort]").forEach((button) => {
  button.addEventListener("click", () => {
    const key = button.dataset.sort;
    sortState = {
      key,
      direction: sortState.key === key && sortState.direction === "desc" ? "asc" : "desc",
    };
    render();
  });
});
window.addEventListener("resize", render);

load().catch((error) => {
  document.getElementById("generated-at").textContent = "Failed to load data";
  document.getElementById("status-dot").style.background = "var(--red)";
  console.error(error);
});
