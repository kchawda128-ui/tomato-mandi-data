// Run in the built-in browser on https://www.data.gov.in/resource/current-daily-price-various-commodities-various-markets-mandi
// prepare.py fills in the report date (yyyy-mm-dd) and the mandi list ([[agmarknet state, market], ...]) from mandis.json.
// Returns a JSON string: {market: "min/max/modal ..." for the 14 days ending on the report date, "-" for no report}.
const DAY = "__DAY__";
const MANDIS = __MANDIS__;
const RES = "35985678-0d79-46b4-9ed6-6f13308a1d24"; // Variety-wise Daily Market Prices (Agmarknet, DMI)
const findKey = () => ((performance.getEntriesByType("resource").map(e => e.name)
  .find(u => u.includes("api.data.gov.in") && u.includes("api-key=")) || "").match(/api-key=([0-9a-f]+)/) || [])[1];
let key = findKey();
if (!key) { const b = document.querySelector("a.btn-preview"); if (b) b.click(); await new Promise(r => setTimeout(r, 7000)); key = findKey(); }
if (!key) throw new Error("Could not find the data.gov.in preview key on this page");
const N = s => String(s).toLowerCase().replace(/[^a-z0-9]/g, "");
const d0 = new Date(DAY + "T00:00:00Z");
const days = [...Array(14)].map((_, i) => new Date(d0.getTime() - (13 - i) * 864e5));
const ddmmyyyy = d => [d.getUTCDate(), d.getUTCMonth() + 1].map(x => String(x).padStart(2, "0")).join("/") + "/" + d.getUTCFullYear();
const want = new Map(MANDIS.map(([st, mk]) => [st + "|" + N(mk), mk]));
const acc = {}; MANDIS.forEach(([, mk]) => acc[mk] = days.map(() => []));
const totals = [];
for (let i = 0; i < 14; i++) {
  const u = `https://api.data.gov.in/resource/${RES}?api-key=${key}&format=json&limit=4000&filters[Commodity]=Tomato&filters[Arrival_Date]=${ddmmyyyy(days[i])}`;
  let j = null;
  for (let t = 0; t < 3 && !j; t++) { try { const r = await fetch(u); if (r.ok) j = await r.json(); } catch (e) {} if (!j) await new Promise(r => setTimeout(r, 3000)); }
  if (!j) throw new Error("data.gov.in did not answer for " + ddmmyyyy(days[i]));
  totals.push((j.records || []).length);
  for (const r of j.records || []) { const mk = want.get(r.State + "|" + N(r.Market)); if (mk) acc[mk][i].push(r); }
}
const out = {};
for (const [, mk] of MANDIS) out[mk] = acc[mk].map(a => a.length
  ? [Math.min(...a.map(x => +x.Min_Price)), Math.round(Math.max(...a.map(x => +x.Max_Price))), Math.round(a.reduce((s, x) => s + +x.Modal_Price, 0) / a.length)].join("/")
  : "-").join(" ");
JSON.stringify({ day: DAY, records_per_day: totals, series: out });
