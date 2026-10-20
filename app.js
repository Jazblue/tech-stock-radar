const DATA_URL = "data/latest.json";
const $ = (id) => document.getElementById(id);
let allStocks = [];

function formatPrice(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return new Intl.NumberFormat("en-GB", { style: "currency", currency: "GBP", minimumFractionDigits: 2, maximumFractionDigits: 4 }).format(value);
}
function formatChange(value) {
  if (typeof value !== "number" || !Number.isFinite(value)) return "—";
  return (value > 0 ? "+" : "") + value.toFixed(2) + "%";
}
function safeText(value) {
  return String(value == null ? "" : value);
}
function renderMovers(id, stocks, positive) {
  const items = stocks.filter(s => typeof s.change_pct === "number").sort((a,b) => positive ? b.change_pct-a.change_pct : a.change_pct-b.change_pct).slice(0,5);
  const target = $(id);
  if (!items.length) {
    target.innerHTML = '<li class="empty">Price data will appear after the first update.</li>';
    return;
  }
  target.innerHTML = items.map(s => '<li><span><span class="mover-name">' + safeText(s.name) + '</span><span class="mover-symbol">' + safeText(s.ticker) + '</span></span><strong class="' + (s.change_pct >= 0 ? "positive" : "negative") + '">' + formatChange(s.change_pct) + '</strong></li>').join("");
}
function renderTable() {
  const query = $("search").value.trim().toLowerCase();
  const stocks = allStocks.filter(s => (safeText(s.name) + " " + safeText(s.ticker)).toLowerCase().includes(query));
  const body = $("stocks-body");
  if (!stocks.length) {
    body.innerHTML = '<tr><td colspan="5" class="empty">No matching shares.</td></tr>';
    return;
  }
  body.innerHTML = stocks.map(s => {
    const hasPrice = typeof s.price_gbp === "number";
    const changeClass = typeof s.change_pct === "number" ? (s.change_pct >= 0 ? "positive" : "negative") : "";
    const status = hasPrice ? '<span class="status ok">Updated</span>' : '<span class="status missing">No quote</span>';
    return '<tr><td><span class="company">' + safeText(s.name) + '</span></td><td>' + safeText(s.ticker.replace(/\.L$/,"")) + '</td><td class="numeric">' + formatPrice(s.price_gbp) + '</td><td class="numeric ' + changeClass + '">' + formatChange(s.change_pct) + '</td><td>' + status + '</td></tr>';
  }).join("");
}
async function loadData() {
  try {
    const response = await fetch(DATA_URL + "?v=" + Date.now(), { cache: "no-store" });
    if (!response.ok) throw new Error("No price file available yet");
    const data = await response.json();
    allStocks = Array.isArray(data.stocks) ? data.stocks : [];
    $("ai-summary").textContent = data.ai_summary || "No Granite summary is available yet.";
    $("summary-meta").textContent = data.summary_source ? "Summary source: " + data.summary_source : "Summary not generated";
    $("tracked-count").textContent = allStocks.length || 30;
    const changes = allStocks.map(s => s.change_pct).filter(v => typeof v === "number");
    $("riser-count").textContent = changes.filter(v => v > 0).length;
    $("faller-count").textContent = changes.filter(v => v < 0).length;
    $("updated-at").textContent = data.updated_at ? new Date(data.updated_at).toLocaleString("en-GB", { dateStyle: "medium", timeStyle: "short" }) : "Waiting";
    $("data-note").textContent = data.note || "Daily market data; values can be delayed.";
    renderMovers("risers-list", allStocks, true);
    renderMovers("fallers-list", allStocks, false);
    renderTable();
  } catch (error) {
    $("data-note").textContent = "Price data has not been collected yet. Run scripts/update_prices.py on your Windows PC, then publish data/latest.json.";
  }
}
$("search").addEventListener("input", renderTable);
loadData();
