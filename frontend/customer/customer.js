// Customer ordering UI. All DOM is built with h() (createElement/textContent); server data is never
// parsed as HTML. Totals shown are always the server's OrderOut values, never computed here.
import { api } from "/js/api.js";
import { h } from "/js/dom.js";
import { S, DIR, LANGS } from "./i18n.js";

const STORE = "catering_order";
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;
const LOCALES = { he: "he-IL", ar: "ar-IL-u-nu-latn", en: "en-IL" };
const $ = (id) => document.getElementById(id);
const app = $("app");

const st = {
  lang: "he", order: null, cred: null, step: "event", busy: false,
  types: [], settings: { lead_time_days: 7, min_food_total: "500.00", max_km: "40.00" }, quote: null, slots: [], blocked: [], cats: [], dishes: [], cat: "all",
  recs: {}, details: {}, open: new Set(), imgBase: null, errs: {}, form: null,
};
const t = () => S[st.lang];
const fmt = (text, vars) => text.replace(/\{(\w+)\}/g, (_, k) => vars[k]);

// ---- storage (may throw in private windows)
const store = {
  get() { try { return JSON.parse(localStorage.getItem(STORE)); } catch { return null; } },
  set(v) { try { localStorage.setItem(STORE, JSON.stringify(v)); } catch { /* ignore */ } },
  clear() { try { localStorage.removeItem(STORE); } catch { /* ignore */ } },
};
const prefLang = {
  get() { try { return localStorage.getItem("lang"); } catch { return null; } },
  set(v) { try { localStorage.setItem("lang", v); } catch { /* ignore */ } },
};

// ---- api helpers
const withLang = (path) => `${path}${path.includes("?") ? "&" : "?"}lang=${st.lang}`;
const pub = (path) => api(withLang(path));
const orderApi = (path = "", options = {}) =>
  api(withLang(`/api/orders/${st.cred.id}${path}`), {
    ...options, headers: { ...options.headers, "X-Order-Token": st.cred.token },
  });

function say(text, kind = "ok") {
  const m = $("message");
  m.textContent = text;
  m.className = kind;
}

// ---- formatting (display only)
const money = (v, cur = "ILS") => new Intl.NumberFormat(LOCALES[st.lang], { style: "currency", currency: cur }).format(Number(v));
const num = (v) => new Intl.NumberFormat(LOCALES[st.lang], { maximumFractionDigits: 3 }).format(Number(v));
function unitText(pricingUnit, label) {
  const k = { per_guest: "perGuest", per_tray: "perTray", per_weight: "perKg", per_item: "perItem" }[pricingUnit];
  if (pricingUnit === "per_weight") return t().perKg; // always per kg, whatever the stored label
  return label ? `${t()[k]} (${label})` : t()[k];
}
const dateStr = (d) => `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
// Earliest bookable date: local today + lead time (the server re-checks in the business timezone).
const minDate = () => { const d = new Date(); d.setDate(d.getDate() + st.settings.lead_time_days); return dateStr(d); };
const leadMsg = () => fmt(t().leadHint, { n: st.settings.lead_time_days });
const meetsMin = (o) => Number(o.subtotal) >= Number(st.settings.min_food_total);
// Python weekday: Monday=0..Sunday=6; JS getDay() is Sunday=0.
function pyWeekday(dateStr) {
  const [y, m, d] = dateStr.split("-").map(Number);
  return (new Date(y, m - 1, d).getDay() + 6) % 7;
}

// ---- errors
async function handle(e) {
  if (e.status === 404 && st.cred) return resetOrder(t().notFound);
  if (e.code === "order_version_conflict") {
    await reloadOrder().catch(() => {});
    say(t().conflict, "error");
  } else if (e.code === "invalid_transition") {
    await reloadOrder().catch(() => {});
    say(t().locked, "error");
  } else say(e.status ? e.message : t().error, "error");
  render();
}
async function guard(fn) {
  if (st.busy) return;
  st.busy = true;
  say("");
  try { await fn(); } catch (e) { await handle(e); } finally { st.busy = false; render(); }
}

// ---- order lifecycle
function setCred(cred) {
  st.cred = cred;
  store.set(cred);
  history.replaceState(null, "", `#order=${encodeURIComponent(cred.id)}&token=${encodeURIComponent(cred.token)}`);
}
function resetOrder(msg = "") {
  store.clear();
  history.replaceState(null, "", location.pathname + location.search);
  Object.assign(st, { order: null, cred: null, step: "event", form: null, recs: {}, errs: {} });
  say(msg, msg ? "error" : "ok");
  render();
}
async function reloadOrder() {
  st.order = await orderApi();
  await loadRecs();
}
async function loadRecs() {
  st.recs = {};
  if (st.order?.status !== "draft") return;
  try {
    for (const r of await orderApi("/recommendations")) st.recs[r.dish_id] = r;
  } catch { /* recommendations are optional */ }
}
function privateLink() {
  return `${location.origin}/customer/#order=${encodeURIComponent(st.cred.id)}&token=${encodeURIComponent(st.cred.token)}`;
}

// ---- catalog loading
async function loadDishes() {
  st.dishes = await pub(st.cat === "all" ? "/api/catalog/dishes" : `/api/catalog/dishes?category_id=${st.cat}`);
}
async function loadCatalog() {
  st.cats = await pub("/api/catalog/categories");
  await loadDishes();
}

// ---- shared widgets
function field(id, label, control, { hint, err } = {}) {
  if (err) control.setAttribute("aria-invalid", "true");
  const desc = [hint && `${id}-h`, err && `${id}-e`].filter(Boolean).join(" ");
  if (desc) control.setAttribute("aria-describedby", desc);
  return h("div", { class: "field" }, h("label", { for: id }, label), control,
    hint && h("p", { class: "hint", id: `${id}-h` }, hint),
    err && h("p", { class: "err", id: `${id}-e` }, err));
}
function stepper(id, label, value, min, max, onchange, step = 1) {
  const set = (v) => onchange(Math.min(max, Math.max(min, v)));
  const input = h("input", { id, type: "number", inputmode: step < 1 ? "decimal" : "numeric", min, max, step, value, "aria-label": label,
    onchange: (ev) => { const v = Number(ev.target.value); set(Number.isFinite(v) ? v : min); } });
  return h("div", { class: "stepper" },
    h("button", { type: "button", "aria-label": `${t().dec}: ${label}`, disabled: Number(value) <= min, onclick: () => set(Number(value) - step) }, "−"),
    input,
    h("button", { type: "button", "aria-label": `${t().inc}: ${label}`, disabled: Number(value) >= max, onclick: () => set(Number(value) + step) }, "+"));
}

// ---- C1 event
function defaultForm() {
  const o = st.order;
  if (o) {
    const slot = st.slots.find((s) => s.id === o.time_slot_id);
    return { type: o.event.event_type, date: o.event.event_date, slot: o.time_slot_id ?? "", adults: o.event.adults, children: o.event.children,
      veg: o.event.vegetarian_guests, vegan: o.event.vegan_guests, restricted: o.event.restricted_guests, notes: o.event.dietary_notes ?? "",
      fulfillment: slot?.fulfillment_type ?? o.fulfillment_type, address: o.delivery_address ?? "",
      name: o.customer.full_name, email: o.customer.email ?? "", phone: o.customer.phone ?? "" };
  }
  return { type: st.types[0] ?? "other", date: "", slot: "", adults: 10, children: 0, veg: 0, vegan: 0, restricted: 0, notes: "",
    fulfillment: "pickup", address: "", name: "", email: "", phone: "" };
}
const availableSlots = (f) => st.slots.filter((s) => s.is_active && s.fulfillment_type === f.fulfillment &&
  (!f.date || s.weekday == null || s.weekday === pyWeekday(f.date)));

// ---- delivery estimate (display only; the server recalculates the fee on save)
let quoteTimer;
function quoteNodes(f) {
  const q = st.quote;
  if (!q || q.addr !== f.address.trim()) return [];
  if (q.loading) return [h("p", { class: "hint" }, t().checking)];
  if (q.error) return [];
  const d = q.data;
  if (d.too_far) return [h("p", { class: "notice warn" }, fmt(t().quoteFar, { max: num(d.max_km) })),
    h("button", { type: "button", id: "to-pickup", onclick: () => { f.fulfillment = "pickup"; st.quote = null; if (!availableSlots(f).some((s) => s.id === f.slot)) f.slot = ""; render(); } }, t().toPickup)];
  if (!d.found) return [h("p", { class: "notice" }, t().quoteNone)];
  return [h("p", { class: "notice" }, fmt(t().quoteFound, { km: num(d.km), fee: money(d.fee) }))];
}
function queueQuote(f) { clearTimeout(quoteTimer); quoteTimer = setTimeout(() => checkQuote(f), 600); }
async function checkQuote(f) {
  clearTimeout(quoteTimer);
  const addr = f.address.trim();
  if (!addr || st.quote?.addr === addr) return;
  st.quote = { addr, loading: true };
  const paint = () => $("quote")?.replaceChildren(...quoteNodes(f));
  paint();
  try {
    const data = await api(`/api/delivery-quote?address=${encodeURIComponent(addr)}`);
    if (st.quote?.addr === addr) st.quote = { addr, data };
  } catch { if (st.quote?.addr === addr) st.quote = { addr, error: true }; }
  paint();
}

async function onDate(f, value) {
  f.date = value;
  st.errs.date = null;
  if (value) {
    if (value < minDate()) st.errs.date = leadMsg();
    else {
      try {
        const a = await pub(`/api/availability?from=${value}&to=${value}`);
        st.blocked = a.blocked_dates;
        if (a.blocked_dates.some((b) => b.date === value)) st.errs.date = t().dateBlocked;
      } catch { /* backend re-validates on submit */ }
    }
  }
  if (!availableSlots(f).some((s) => s.id === f.slot)) f.slot = "";
  render();
}

function viewEvent() {
  const f = (st.form ??= defaultForm());
  const e = st.errs;
  const total = f.adults + f.children;
  const clampSubsets = () => { for (const k of ["veg", "vegan", "restricted"]) f[k] = Math.min(f[k], f.adults + f.children); };
  const guest = (key, label) => stepper(`f-${key}`, label, f[key], 0, 100000, (v) => { f[key] = v; clampSubsets(); render(); });
  const sub = (key, label) => stepper(`f-${key}`, `${t().of_these}: ${label}`, f[key], 0, total, (v) => { f[key] = v; render(); });
  const slots = availableSlots(f);
  const text = (key, label, props = {}) => field(`f-${key}`, label, h("input", { id: `f-${key}`, value: f[key], oninput: (ev) => (f[key] = ev.target.value), ...props }), { err: e[key] });

  const form = h("form", { class: "ep-card ep-form", novalidate: true, onsubmit: (ev) => { ev.preventDefault(); guard(() => submitEvent(f)); } },
    h("h2", {}, t().step1),
    field("f-type", t().eventType, h("select", { id: "f-type", onchange: (ev) => (f.type = ev.target.value) },
      st.types.map((k) => h("option", { value: k, selected: k === f.type }, t().event_types[k] ?? k)))),
    field("f-date", t().date, h("input", { id: "f-date", type: "date", min: minDate(), value: f.date, required: true, onchange: (ev) => onDate(f, ev.target.value) }), { err: e.date, hint: leadMsg() }),
    field("f-fulfillment-group", t().fulfillment, h("div", { class: "pills", role: "group", id: "f-fulfillment-group", "aria-label": t().fulfillment },
      ["pickup", "delivery"].map((k) => h("button", { type: "button", id: `f-ful-${k}`, "aria-pressed": String(f.fulfillment === k),
        onclick: () => { f.fulfillment = k; if (!availableSlots(f).some((s) => s.id === f.slot)) f.slot = ""; render(); } }, t()[k])))),
    field("f-slot", t().slot, h("select", { id: "f-slot", onchange: (ev) => (f.slot = ev.target.value) },
      h("option", { value: "" }, slots.length ? "—" : t().noSlots),
      slots.map((s) => h("option", { value: s.id, selected: s.id === f.slot }, `\u2066${s.start_time.slice(0, 5)}–${s.end_time.slice(0, 5)}\u2069`))), { err: e.slot }),
    f.fulfillment === "delivery" && h("div", {},
      field("f-address", t().address, h("input", { id: "f-address", value: f.address, autocomplete: "street-address", maxlength: 500, enterkeyhint: "search",
        onkeydown: (ev) => { if (ev.key === "Enter") { ev.preventDefault(); checkQuote(f); } },
        oninput: (ev) => { f.address = ev.target.value; queueQuote(f); }, onblur: () => checkQuote(f) }), { err: e.address }),
      h("button", { type: "button", id: "check-delivery", onclick: () => checkQuote(f) }, t().checkDelivery),
      h("div", { id: "quote", class: "quote", role: "status", "aria-live": "polite" }, quoteNodes(f))),
    h("div", { class: "row" }, field("f-adults", t().adults, guest("adults", t().adults)), field("f-children", t().children, guest("children", t().children))),
    e.guests && h("p", { class: "err" }, e.guests),
    h("fieldset", { class: "subset" }, h("legend", {}, t().of_these),
      h("div", { class: "row" },
        field("f-veg", t().vegetarian, sub("veg", t().vegetarian)),
        field("f-vegan", t().vegan, sub("vegan", t().vegan)),
        field("f-restricted", t().restricted, sub("restricted", t().restricted))),
      h("p", { class: "hint" }, t().subsetHint)),
    field("f-notes", t().dietaryNotes, h("textarea", { id: "f-notes", maxlength: 2000, oninput: (ev) => (f.notes = ev.target.value) }, f.notes)),
    text("name", t().fullName, { autocomplete: "name", maxlength: 200, disabled: !!st.order }),
    !st.order && h("div", {},
      text("email", t().email, { type: "email", autocomplete: "email", autocapitalize: "none", autocorrect: "off", inputmode: "email", maxlength: 254 }),
      text("phone", t().phone, { type: "tel", inputmode: "tel", autocomplete: "tel", maxlength: 50 }),
      h("p", { class: "hint" }, t().contactHint),
      e.contact && h("p", { class: "err" }, e.contact)),
    h("div", { class: "actions" }, h("button", { class: "primary", type: "submit", disabled: st.busy }, st.busy ? t().saving : t().next),
      st.order && h("button", { type: "button", class: "link", onclick: () => { st.step = "menu"; render(); } }, t().back)));
  return form;
}

async function submitEvent(f) {
  const e = (st.errs = {});
  if (!f.date) e.date = t().datePast;
  else if (f.date < minDate()) e.date = leadMsg();
  else if (st.errs.date) e.date = st.errs.date;
  if (f.adults + f.children < 1) e.guests = t().needGuests;
  if (!f.slot) e.slot = t().needSlot;
  if (f.fulfillment === "delivery") {
    if (!f.address.trim()) e.address = t().needAddress;
  }
  if (!f.name.trim()) e.name = t().fullName;
  if (!st.order && !f.email.trim() && !f.phone.trim()) e.contact = t().needContact;
  if (Object.keys(e).length) { render(); return; }
  const delivery = f.fulfillment === "delivery";
  const event = { event_type: f.type, event_date: f.date, adults: f.adults, children: f.children, vegetarian_guests: f.veg,
    vegan_guests: f.vegan, restricted_guests: f.restricted, dietary_notes: f.notes.trim() || null };
  const common = { fulfillment_type: f.fulfillment, time_slot_id: f.slot,
    delivery_address: delivery ? f.address.trim() : null };
  if (st.order) {
    st.order = await orderApi("", { method: "PATCH", body: JSON.stringify({ version: st.order.version, event, ...common }) });
  } else {
    const body = { customer: { full_name: f.name.trim(), email: f.email.trim() || null, phone: f.phone.trim() || null }, event, ...common };
    const created = await api(withLang("/api/orders"), { method: "POST", body: JSON.stringify(body) });
    setCred({ id: created.id, token: created.access_token });
    st.order = created;
  }
  await loadRecs();
  await loadCatalog();
  st.step = "menu";
  render();
}

// ---- C2 menu
async function setQty(dishId, qty) {
  await guard(async () => {
    const o = st.order;
    st.order = Number(qty) > 0
      ? await orderApi(`/items/${dishId}`, { method: "PUT", body: JSON.stringify({ quantity: qty, version: o.version }) })
      : await orderApi(`/items/${dishId}?version=${o.version}`, { method: "DELETE" });
    await loadRecs();
    render();
  });
}

function dishBadges(d) {
  const x = d.dietary ?? {};
  const k = x.kashrut_class;
  const veg = (val, yes, no, unk, cls) => h("span", { class: `badge ${val === true ? cls : val === false ? "no" : "unknown"}` }, val === true ? yes : val === false ? no : unk);
  return h("div", { class: "badges" },
    h("span", { class: `badge ${k ? k : "unknown"}` }, k ? (t().kashrut[k] ?? k) : t().kashrutUnknown),
    veg(x.is_vegetarian, t().vegBadge, t().notVeg, t().vegUnknown, "veg"),
    veg(x.is_vegan, t().veganBadge, t().notVegan, t().veganUnknown, "vegan"));
}

async function toggleAllergens(d) {
  if (st.open.has(d.id)) st.open.delete(d.id);
  else {
    st.open.add(d.id);
    try { st.details[d.id] = await pub(`/api/catalog/dishes/${d.id}`); } catch { st.details[d.id] = { allergens: [] }; }
  }
  render();
}
function allergenPanel(d) {
  const list = st.details[d.id]?.allergens ?? [];
  const statusText = { contains: t().contains, free: t().free };
  return h("div", { id: `al-${d.id}` },
    list.length
      ? h("ul", { class: "allergens" }, list.map((a) => h("li", {}, h("span", {}, a.name), h("strong", {}, statusText[a.status] ?? t().unknown))))
      : h("p", { class: "hint" }, t().unknown),
    h("p", { class: "hint" }, t().allergenNote),
    h("p", { class: "hint" }, t().disclaimer));
}

function dishCard(d) {
  const item = st.order.items.find((i) => i.dish_id === d.id);
  const qty = item ? Number(item.quantity) : 0;
  const step = d.pricing_unit === "per_weight" ? 0.5 : 1;
  const first = Math.max(Number(d.min_quantity ?? 0), step);
  const rec = st.recs[d.id];
  const open = st.open.has(d.id);
  return h("li", { class: "dish" },
    d.image_path && st.imgBase && h("img", { alt: "", loading: "lazy", src: `${st.imgBase}/${encodeURIComponent(d.image_path)}` }),
    h("div", { class: "dish-body" },
      h("h3", {}, d.name || d.name_he),
      d.description && h("p", {}, d.description),
      h("div", { class: "price" }, `${money(d.unit_price, d.currency)} / ${unitText(d.pricing_unit, d.unit_label)}`),
      d.min_quantity && h("p", { class: "hint" }, `${t().minQty}: ${num(d.min_quantity)}`),
      dishBadges(d),
      h("button", { type: "button", class: "link", id: `alb-${d.id}`, "aria-expanded": String(open), "aria-controls": `al-${d.id}`, onclick: () => toggleAllergens(d) },
        open ? t().hideAllergens : t().allergens),
      open && allergenPanel(d),
      rec && rec.reason !== "no_rule" && rec.recommended != null && h("div", { class: "rec" },
        h("span", {}, `${t().recommended}: ${num(rec.recommended)}`),
        h("button", { type: "button", id: `use-${d.id}`, disabled: st.busy, onclick: () => setQty(d.id, rec.recommended) }, t().useSuggested)),
      h("div", { class: "stepper" },
        h("button", { type: "button", id: `dec-${d.id}`, "aria-label": `${t().dec}: ${d.name}`, disabled: qty <= 0 || st.busy,
          onclick: () => setQty(d.id, qty - step < Number(d.min_quantity ?? 0) ? 0 : qty - step) }, "−"),
        h("input", { id: `qty-${d.id}`, type: "number", min: 0, step, value: qty, inputmode: step < 1 ? "decimal" : "numeric", "aria-label": `${t().qty}: ${d.name}`,
          onchange: (ev) => { const v = Number(ev.target.value); setQty(d.id, Number.isFinite(v) && v > 0 ? v : 0); } }),
        h("button", { type: "button", id: `inc-${d.id}`, "aria-label": `${t().inc}: ${d.name}`, disabled: st.busy,
          onclick: () => setQty(d.id, qty > 0 ? qty + step : first) }, "+"))));
}

function viewMenu() {
  const chip = (id, label) => h("button", { type: "button", id: `cat-${id}`, "aria-pressed": String(st.cat === id),
    onclick: () => guard(async () => { st.cat = id; await loadDishes(); render(); }) }, label);
  return h("div", { class: "layout" },
    h("section", { "aria-labelledby": "menu-h" },
      h("h2", { id: "menu-h" }, t().step2),
      h("div", { class: "chips", role: "group", "aria-label": t().step2 }, chip("all", t().all), st.cats.map((c) => chip(c.id, c.name || c.name_he))),
      st.dishes.length ? h("ul", { class: "dishes", style: "list-style:none;padding:0;margin:0" }, st.dishes.map(dishCard)) : h("p", {}, t().noDishes),
      h("p", { class: "notice", id: "disclaimer" }, t().disclaimer)),
    h("aside", {}, summaryCard(true)));
}

// ---- C3 summary (server values only)
function minGauge(o) {
  const min = Number(st.settings.min_food_total), sub = Number(o.subtotal);
  return h("div", { class: "gauge" },
    h("div", { class: "gauge-bar", role: "progressbar", "aria-valuemin": 0, "aria-valuemax": min, "aria-valuenow": Math.min(sub, min),
      "aria-valuetext": fmt(t().minGauge, { sub: money(o.subtotal, o.currency), min: money(min, o.currency) }) },
      h("span", { style: `inline-size:${Math.min(100, (sub / min) * 100)}%` })),
    h("p", { class: "hint" }, fmt(t().minGauge, { sub: money(o.subtotal, o.currency), min: money(min, o.currency) })),
    !meetsMin(o) && h("p", { class: "hint", id: "min-need" }, t().minNeed));
}
const warnings = (o) => o.warnings?.includes("mixes_meat_dairy") && h("p", { class: "notice", id: "warn-mix" }, t().warnMix);
function summaryCard(withActions) {
  const o = st.order;
  const feeTbc = o.delivery_fee == null && o.delivery_fee_estimated;
  const lines = o.items.length
    ? h("ul", { class: "lines" }, o.items.map((i) => h("li", {},
      h("span", {}, i.name, h("small", {}, `${num(i.quantity)} × ${money(i.unit_price, o.currency)} / ${unitText(i.pricing_unit, i.unit)}`)),
      h("strong", {}, money(i.line_total, o.currency)))))
    : h("p", { class: "hint" }, t().empty);
  const body = [lines,
    h("dl", { class: "totals" },
      h("dt", {}, t().subtotal), h("dd", {}, money(o.subtotal, o.currency)),
      h("dt", {}, t().deliveryFee), h("dd", {}, feeTbc ? t().feeTbc : o.delivery_fee == null ? "—" : money(o.delivery_fee, o.currency)),
      h("dt", { class: "grand" }, feeTbc ? t().totalExcl : t().total), h("dd", { class: "grand", id: "total" }, money(o.total, o.currency))),
    h("p", { class: "vat" }, t().vat),
    ];
  // Phone: collapsed details = compact bar (title + server total); desktop and review: open.
  const open = !withActions || matchMedia("(min-width: 900px)").matches;
  return h("div", { class: "ep-card sumbar" },
    h("details", { class: "sum", open }, h("summary", {}, h("h2", {}, t().summary), h("strong", { class: "sum-total" }, money(o.total, o.currency))), body),
    o.status === "draft" && minGauge(o), warnings(o),
    withActions && h("div", { class: "actions" },
      h("button", { type: "button", class: "primary", id: "to-review", disabled: !o.items.length || !meetsMin(o), onclick: () => { st.step = "review"; render(); } }, t().review),
      h("button", { type: "button", class: "link", onclick: () => { st.form = null; st.step = "event"; render(); } }, t().edit)));
}

// ---- C5 review / status
function linkBox() {
  const input = h("input", { id: "plink", readonly: true, value: privateLink(), "aria-label": t().link, onfocus: (ev) => ev.target.select() });
  return h("div", { class: "ep-card" }, h("h3", {}, t().link), h("p", { class: "hint" }, t().saveLink),
    h("div", { class: "linkbox" }, input,
      h("button", { type: "button", id: "copy", onclick: async () => {
        try { await navigator.clipboard.writeText(input.value); say(t().copied); } catch { input.select(); }
      } }, t().copy)));
}
function eventRecap() {
  const o = st.order;
  return h("p", { class: "hint" }, `${t().event_types[o.event.event_type] ?? o.event.event_type} · ${o.event.event_date} · ${t().guests}: ${o.event.adults + o.event.children}`);
}
function viewReview() {
  return h("div", { class: "ep-form" }, h("h2", {}, t().step3), eventRecap(), summaryCard(false),
    h("p", {}, t().submitNote),
    h("div", { class: "actions" },
      h("button", { type: "button", class: "primary", id: "submit", disabled: st.busy || !st.order.items.length || !meetsMin(st.order),
        onclick: () => guard(async () => { st.order = await orderApi("/submit", { method: "POST", body: JSON.stringify({ version: st.order.version }) }); render(); }) },
      st.busy ? t().submitting : t().submit),
      h("button", { type: "button", class: "link", onclick: () => { st.step = "menu"; render(); } }, t().back)),
    linkBox());
}
function viewStatus() {
  const o = st.order;
  return h("div", { class: "ep-form" },
    h("div", { class: `status ${o.status}`, id: "status" }, h("h2", {}, t().st[o.status] ?? o.status), h("p", {}, t().stDesc[o.status] ?? ""),
      o.decision_note && h("p", {}, h("strong", {}, `${t().note}: `), o.decision_note)),
    eventRecap(), summaryCard(false), linkBox(),
    h("button", { type: "button", onclick: () => resetOrder() }, t().newOrder));
}

// ---- shell
function steps(cur) {
  const names = [["event", t().step1], ["menu", t().step2], ["review", t().step3]];
  return h("ol", { class: "steps" }, names.map(([k, label]) => h("li", k === cur ? { "aria-current": "step" } : {}, label)));
}
function render() {
  const focusId = document.activeElement?.id;
  document.documentElement.lang = st.lang;
  document.documentElement.dir = DIR[st.lang];
  document.title = "CaterKing";
  $("langs").replaceChildren(h("div", { class: "pills", role: "group", "aria-label": t().lang },
    Object.entries(LANGS).map(([k, label]) => h("button", { type: "button", lang: k, "aria-pressed": String(k === st.lang), onclick: () => setLang(k) }, label))));
  const step = !st.order ? "event" : st.order.status !== "draft" ? "status" : st.step;
  const view = { event: viewEvent, menu: viewMenu, review: viewReview, status: viewStatus }[step]();
  app.replaceChildren(...(step === "status" ? [view] : [steps(step), view]));
  if (focusId) $(focusId)?.focus({ preventScroll: true });
  if (st.order) $("live").textContent = `${t().total}: ${money(st.order.total, st.order.currency)}`;
}

async function setLang(lang) {
  st.lang = lang;
  prefLang.set(lang);
  await guard(async () => {
    st.details = {};
    await loadCatalog();
    if (st.cred) await reloadOrder();
  });
  render();
}

// ---- boot
async function boot() {
  const q = new URLSearchParams(location.search).get("lang");
  st.lang = [q, prefLang.get()].find((l) => l in S) ?? "he";
  render();
  say(t().loading);
  const hash = new URLSearchParams(location.hash.slice(1));
  const saved = store.get();
  let cred = hash.get("order") && hash.get("token") ? { id: hash.get("order"), token: hash.get("token") } : saved?.id && saved?.token ? saved : null;
  // The id goes into API paths, so only accept a UUID (blocks crafted links like "../admin").
  if (cred && !UUID.test(cred.id)) cred = null;
  try {
    const [types, settings, avail, config] = await Promise.all([
      pub("/api/catalog/event-types"), api("/api/public-settings").catch(() => st.settings), pub("/api/availability"), api("/api/public-config").catch(() => ({})),
    ]);
    st.form = null;
    Object.assign(st, { types, settings, slots: avail.time_slots, blocked: avail.blocked_dates });
    if (config.supabase_url) st.imgBase = `${config.supabase_url}/storage/v1/object/public/dish-images`;
    await loadCatalog();
    if (cred) {
      st.cred = cred;
      try {
        await reloadOrder();
        setCred(cred);
        st.step = "menu";
      } catch (e) {
        if (e.status === 404 || e.status === 422) { st.cred = null; store.clear(); history.replaceState(null, "", location.pathname + location.search); say(t().notFound, "error"); render(); return; }
        throw e;
      }
    }
    if (!$("message").classList.contains("error")) say("");
  } catch (e) {
    say(e.status ? e.message : t().error, "error");
  }
  render();
}
boot();
