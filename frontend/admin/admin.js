// All DOM is built with createElement/textContent; server data is never parsed as HTML.
import { api, auth } from "/js/api.js";
import { beep, muteToggle } from "/js/radio.js";
import { h } from "/js/dom.js";

const app = document.getElementById("app");
const message = document.getElementById("message");
const topTabs = document.getElementById("tabs");
const tools = document.getElementById("tools");
const state = { config: null, categories: [], allergens: [], safety: false };
let openSection = async () => {};

// ---- time helpers (the owner's clock is Asia/Jerusalem whatever the browser says)
const TZ = "Asia/Jerusalem";
const parseTs = (s) => new Date(/(Z|[+-]\d\d:?\d\d)$/i.test(s) ? s : `${s}Z`);
const fmt = (opts, s) => (s ? new Intl.DateTimeFormat("he-IL", { timeZone: TZ, hour12: false, ...opts }).format(parseTs(s)) : "—");
const fmtTime = (s) => fmt({ hour: "2-digit", minute: "2-digit" }, s);
const fmtDT = (s) => fmt({ day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" }, s);
const fmtDate = (d) => (d ? d.split("-").reverse().join(".") : "—");
const todayStr = () => new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(new Date());
const localDay = (s) => (s ? new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(parseTs(s)) : "");

// ---- Safety Car switch (header and settings share state)
const TICKER = "SAFETY CAR DEPLOYED: Pacing the kitchen to guarantee 100% perfection on every dish";
const switches = [];
function setSafety(on) {
  state.safety = on;
  for (const sw of switches) {
    if (!sw.isConnected) continue;
    sw.setAttribute("aria-checked", String(on));
    const t = sw.querySelector(".sw-text");
    if (t) t.textContent = `SAFETY CAR (${on ? "פעיל" : "כבוי"})`;
  }
  document.body.classList.toggle("safety-on", on);
}
function safetySwitch() {
  const sw = h("button", { type: "button", class: "sw", role: "switch", "aria-checked": String(state.safety), dir: "ltr" },
    h("span", { class: "track", "aria-hidden": "true" }, h("span", { class: "knob" })),
    h("span", { class: "sw-text label" }, `SAFETY CAR (${state.safety ? "פעיל" : "כבוי"})`));
  sw.addEventListener("click", () => {
    sw.disabled = true;
    run(async () => { setSafety((await api("/api/admin/safety-car", { method: "PUT", body: JSON.stringify({ on: !state.safety }) })).safety_car); beep(); })
      .finally(() => { sw.disabled = false; });
  });
  switches.push(sw);
  return sw;
}

function say(text, kind = "ok") {
  message.textContent = text;
  message.className = kind;
}

async function run(action) {
  try {
    say("");
    await action();
  } catch (e) {
    if (e.status === 401) return logout("פג תוקף ההתחברות. התחברו שוב.");
    say(e.status === 403 ? "החשבון הזה אינו מנהל." : e.message, "error");
  }
}

function logout(text = "") {
  auth.clear();
  topTabs.replaceChildren();
  tools.replaceChildren();
  document.body.classList.remove("safety-on");
  showLogin();
  say(text, "error");
}

// ---- login (Supabase Auth REST, email + password)
function showLogin() {
  const email = h("input", { type: "email", required: true, autocomplete: "username", dir: "ltr" });
  const password = h("input", { type: "password", required: true, autocomplete: "current-password", dir: "ltr" });
  const form = h("form", { class: "panel login", onsubmit: (ev) => { ev.preventDefault(); run(() => login(email.value, password.value)); } },
    h("img", { src: "/assets/brand/favicon.svg", alt: "", width: "56", height: "44" }),
    h("div", { class: "label" }, "PIT WALL // כניסה"),
    h("h2", {}, "כניסת בעל העסק"),
    h("label", {}, "אימייל", email),
    h("label", {}, "סיסמה", password),
    h("button", { class: "primary", type: "submit" }, "כניסה"));
  app.replaceChildren(form);
}

async function login(email, password) {
  state.config ??= await api("/api/public-config");
  const { supabase_url: url, supabase_anon_key: key } = state.config;
  if (!url || !key) throw new Error("Supabase לא מוגדר בשרת.");
  const response = await fetch(`${url}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: { "Content-Type": "application/json", apikey: key },
    body: JSON.stringify({ email, password }),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error("ההתחברות נכשלה. בדקו אימייל וסיסמה.");
  auth.set(body.access_token);
  await showDashboard();
}

// ---- generic CRUD tab
const LANG_FIELDS = (base, label, required) => [
  { name: `${base}_he`, label: `${label} (עברית${required ? ", חובה" : ""})`, dir: "rtl", required },
  { name: `${base}_ar`, label: `${label} (ערבית)`, dir: "rtl" },
  { name: `${base}_en`, label: `${label} (אנגלית)`, dir: "ltr" },
];
const UNITS = ["per_guest", "per_tray", "per_weight", "per_item"];
const UNIT_TEXT = { per_guest: "לסועד", per_tray: "למגש", per_weight: "לק\"ג", per_item: "ליחידה" };
const FULFIL_TEXT = { pickup: "איסוף עצמי", delivery: "משלוח" };
const WEEKDAY_TEXT = ["ראשון", "שני", "שלישי", "רביעי", "חמישי", "שישי", "שבת"];
const COL_TEXT = { name_he: "שם (עברית)", name_en: "שם (אנגלית)", sort_order: "סדר", is_active: "פעיל", unit_price: "מחיר", pricing_unit: "יחידת תמחור",
  is_available: "זמין", name: "שם", fee: "דמי משלוח", fulfillment_type: "סוג", weekday: "יום", start_time: "התחלה", end_time: "סיום", capacity: "קיבולת",
  date: "תאריך", reason: "סיבה" };
// Show API values as Hebrew labels; the stored values stay unchanged.
function show(col, v) {
  if (typeof v === "boolean") return v ? "כן" : "לא";
  if (v === null || v === undefined) return col === "weekday" ? "כל יום" : col === "capacity" ? "ללא הגבלה" : "—";
  if (col === "pricing_unit") return UNIT_TEXT[v] ?? v;
  if (col === "fulfillment_type") return FULFIL_TEXT[v] ?? v;
  if (col === "weekday") return WEEKDAY_TEXT[v] ?? v;
  return String(v);
}

const RESOURCES = {
  categories: {
    title: "קטגוריות", one: "קטגוריה", path: "/api/admin/categories",
    fields: [...LANG_FIELDS("name", "שם", true),
      { name: "sort_order", label: "סדר מיון", type: "number", step: "1", def: 0 },
      { name: "is_active", label: "פעיל", type: "checkbox", def: true }],
    columns: ["name_he", "name_en", "sort_order", "is_active"],
  },
  dishes: {
    title: "מנות", one: "מנה", path: "/api/admin/dishes",
    fields: [{ name: "category_id", label: "קטגוריה", type: "select", options: () => state.categories.map((c) => [c.id, c.name_he]), required: true },
      ...LANG_FIELDS("name", "שם", true),
      ...LANG_FIELDS("description", "תיאור", false).map((f) => ({ ...f, type: "textarea" })),
      { name: "pricing_unit", label: "יחידת תמחור", type: "select", options: () => UNITS.map((u) => [u, UNIT_TEXT[u]]), required: true },
      { name: "unit_price", label: "מחיר ליחידה (₪)", type: "number", step: "0.01", min: "0", required: true },
      { name: "unit_label", label: "תווית יחידה (למשל גודל מגש)" },
      { name: "min_quantity", label: "כמות מינימלית", type: "number", step: "0.01", min: "0" },
      { name: "is_available", label: "זמין", type: "checkbox", def: true }],
    columns: ["name_he", "name_en", "unit_price", "pricing_unit", "is_available"],
    extras: dishExtras,
  },
  "delivery-zones": {
    title: "אזורי משלוח", one: "אזור משלוח", path: "/api/admin/delivery-zones",
    fields: [{ name: "name", label: "שם", required: true },
      { name: "fee", label: "דמי משלוח (₪)", type: "number", step: "0.01", min: "0", required: true },
      { name: "definition", label: "הגדרה (אובייקט JSON, למשל {\"cities\":[\"Haifa\"]})", type: "json", def: {} },
      { name: "is_active", label: "פעיל", type: "checkbox", def: true }],
    columns: ["name", "fee", "is_active"],
  },
  "time-slots": {
    title: "חלונות זמן", one: "חלון זמן", path: "/api/admin/time-slots",
    fields: [{ name: "fulfillment_type", label: "סוג", type: "select", options: () => [["pickup", FULFIL_TEXT.pickup], ["delivery", FULFIL_TEXT.delivery]], required: true },
      { name: "weekday", label: "יום בשבוע (0-6, ריק = כל יום)", type: "number", step: "1", min: "0", max: "6" },
      { name: "start_time", label: "התחלה", type: "time", required: true },
      { name: "end_time", label: "סיום", type: "time", required: true },
      { name: "capacity", label: "קיבולת (ריק = ללא הגבלה)", type: "number", step: "1", min: "0" },
      { name: "is_active", label: "פעיל", type: "checkbox", def: true }],
    columns: ["fulfillment_type", "weekday", "start_time", "end_time", "capacity", "is_active"],
  },
  "blocked-dates": {
    title: "תאריכים חסומים", one: "תאריך חסום", path: "/api/admin/blocked-dates", noEdit: true,
    fields: [{ name: "date", label: "תאריך", type: "date", required: true }, { name: "reason", label: "סיבה" }],
    columns: ["date", "reason"],
  },
};

function input(f, value) {
  const common = { name: f.name, required: f.required, dir: f.dir, step: f.step, min: f.min, max: f.max };
  if (f.type === "select") {
    const select = h("select", common, f.required ? null : h("option", { value: "" }, "—"),
      ...f.options().map(([v, text]) => h("option", { value: v }, text)));
    select.value = value ?? "";
    return select;
  }
  if (f.type === "textarea") {
    const area = h("textarea", { ...common, rows: 3 });
    area.value = value ?? "";
    return area;
  }
  if (f.type === "json") {
    const area = h("textarea", { ...common, rows: 3 });
    area.value = JSON.stringify(value ?? {});
    return area;
  }
  const el = h("input", { ...common, type: f.type ?? "text" });
  if (f.type === "checkbox") el.checked = Boolean(value);
  else el.value = value ?? "";
  return el;
}

function readForm(cfg, form) {
  const out = {};
  for (const f of cfg.fields) {
    const el = form.elements[f.name];
    if (f.type === "checkbox") out[f.name] = el.checked;
    else if (f.type === "json") out[f.name] = JSON.parse(el.value || "{}");
    else if (el.value === "") out[f.name] = f.required ? el.value : null;
    else out[f.name] = f.type === "number" && f.step === "1" ? Number(el.value) : el.value;
  }
  return out;
}

function cell(value) {
  return value === null || value === undefined ? "—" : String(value);
}

async function showResource(key, tabs, openId = null) {
  const cfg = RESOURCES[key];
  if (key === "dishes" || key === "categories") state.categories = await api("/api/admin/categories");
  const rows = await api(cfg.path);
  const holder = h("div");

  const table = h("div", { class: "table-wrap" }, h("table", {},
    h("thead", {}, h("tr", {}, ...cfg.columns.map((c) => h("th", {}, COL_TEXT[c] ?? c)), h("th", {}, "פעולות"))),
    h("tbody", {}, ...rows.map((row) => h("tr", {},
      ...cfg.columns.map((c) => h("td", {}, show(c, row[c]))),
      h("td", { class: "actions" },
        cfg.noEdit ? null : h("button", { type: "button", onclick: () => edit(row.id) }, "עריכה"),
        h("button", { type: "button", class: "danger", onclick: () => remove(row) }, "מחיקה")))))));

  function remove(row) {
    if (!confirm("למחוק את הפריט?")) return;
    run(async () => { await api(`${cfg.path}/${row.id}`, { method: "DELETE" }); await showResource(key, tabs); say("נמחק."); });
  }

  async function edit(id) {
    // Only dishes have a detail endpoint (dietary and allergens come with it).
    const row = !id ? null : cfg.extras ? await api(`${cfg.path}/${id}`) : rows.find((r) => r.id === id);
    holder.replaceChildren(await renderForm(row));
    holder.scrollIntoView({ behavior: "smooth", block: "nearest" });
  }

  async function renderForm(row) {
    const form = h("form", { class: "card", onsubmit: (ev) => {
      ev.preventDefault();
      run(async () => {
        const body = readForm(cfg, form);
        const saved = await api(row ? `${cfg.path}/${row.id}` : cfg.path, { method: row ? "PATCH" : "POST", body: JSON.stringify(body) });
        await showResource(key, tabs, cfg.extras ? saved.id : null);
        say("נשמר.");
      });
    } },
      h("h2", {}, row ? `עריכה: ${cfg.one}` : `הוספה: ${cfg.one}`),
      h("div", { class: "grid" }, ...cfg.fields.map((f) => f.type === "checkbox"
        ? h("label", { class: "check" }, input(f, row ? row[f.name] : f.def), " ", f.label)
        : h("label", {}, f.label, input(f, row ? row[f.name] : f.def)))),
      h("button", { class: "primary", type: "submit" }, "שמירה"));
    const box = h("div", {}, form);
    if (row && cfg.extras) box.append(await cfg.extras(row, () => edit(row.id)));
    return box;
  }

  holder.append(h("button", { type: "button", class: "primary", onclick: () => edit(null) }, `הוספה: ${cfg.one}`));
  const view = h("section", {}, h("h2", {}, cfg.title), h("div", { class: "card" }, table), holder);
  app.replaceChildren(tabs, view);
  if (openId) await edit(openId);
}

// ---- dish extras: dietary info, allergens, image
async function dishExtras(dish, reload) {
  if (!state.allergens.length) state.allergens = await api("/api/admin/allergens");
  const tri = (name, value) => {
    const s = h("select", { name }, h("option", { value: "" }, "לא ידוע"), h("option", { value: "true" }, "כן"), h("option", { value: "false" }, "לא"));
    s.value = value === null || value === undefined ? "" : String(value);
    s.dataset.tri = s.value;
    s.addEventListener("change", () => { s.dataset.tri = s.value; });
    return s;
  };
  const kashrut = h("select", { name: "kashrut_class" }, h("option", { value: "" }, "לא ידוע"),
    ...["meat", "dairy", "pareve"].map((k) => h("option", { value: k }, { meat: "בשרי", dairy: "חלבי", pareve: "פרווה" }[k])));
  kashrut.value = dish.dietary.kashrut_class ?? "";
  const current = Object.fromEntries(dish.allergens.map((a) => [a.allergen_id, a.status]));
  const allergenSelects = state.allergens.map((a) => {
    const s = h("select", { "data-allergen": a.id }, ...["unknown", "contains", "free"].map((v) => h("option", { value: v }, { unknown: "לא ידוע", contains: "מכיל", free: "ללא" }[v])));
    s.value = current[a.id] ?? "unknown";
    s.dataset.status = s.value;
    s.addEventListener("change", () => { s.dataset.status = s.value; });
    return h("label", { class: "allergen" }, a.name, s);
  });
  const veg = tri("is_vegetarian", dish.dietary.is_vegetarian);
  const vegan = tri("is_vegan", dish.dietary.is_vegan);
  const triValue = (s) => (s.value === "" ? null : s.value === "true");

  const dietaryForm = h("form", { class: "card", onsubmit: (ev) => {
    ev.preventDefault();
    run(async () => {
      const allergens = allergenSelects.map((l) => l.querySelector("select"))
        .filter((s) => s.value !== "unknown")
        .map((s) => ({ allergen_id: Number(s.dataset.allergen), status: s.value }));
      const body = { kashrut_class: kashrut.value || null, is_vegetarian: triValue(veg), is_vegan: triValue(vegan), allergens };
      await api(`/api/admin/dishes/${dish.id}/dietary`, { method: "PUT", body: JSON.stringify(body) });
      say("המידע התזונתי נשמר.");
    });
  } },
    h("h2", {}, "מידע תזונתי ואלרגנים"),
    h("p", {}, "\"לא ידוע\" אומר שלא הוזן מידע; הוא אף פעם לא מוצג כ\"לא\"."),
    h("div", { class: "grid" }, h("label", {}, "כשרות", kashrut), h("label", {}, "צמחוני", veg), h("label", {}, "טבעוני", vegan)),
    h("fieldset", {}, h("legend", {}, "אלרגנים"), h("div", { class: "grid allergens" }, ...allergenSelects)),
    h("button", { class: "primary", type: "submit" }, "שמירת מידע תזונתי"));

  const file = h("input", { type: "file", accept: "image/jpeg,image/png,image/webp", required: true });
  const preview = dish.image_path && state.config?.supabase_url
    ? h("img", { class: "thumb", alt: "", src: `${state.config.supabase_url}/storage/v1/object/public/dish-images/${encodeURIComponent(dish.image_path)}` })
    : null;
  const imageForm = h("form", { class: "card", onsubmit: (ev) => {
    ev.preventDefault();
    run(async () => {
      const data = new FormData();
      data.append("file", file.files[0]);
      await api(`/api/admin/dishes/${dish.id}/image`, { method: "POST", body: data });
      say("התמונה הועלתה.");
      reload();
    });
  } },
    h("h2", {}, "תמונה (JPEG, PNG או WebP, עד 5MB)"), preview,
    h("label", {}, "קובץ", file), h("button", { class: "primary", type: "submit" }, "העלאה"));
  return h("div", {}, dietaryForm, imageForm);
}

// ---- orders
const STATUS_TEXT = { draft: "טיוטה", pending_approval: "ממתינה לאישור", approved: "אושרה", in_kitchen: "בבישול", out_for_delivery: "במשלוח",
  ready_for_pickup: "מוכנה לאיסוף", delivered: "נמסרה", rejected: "נדחתה", cancelled: "בוטלה" };
const STAGES = {
  pending_approval: { en: "Grid", tone: "amber" }, approved: { en: "Grid", tone: "amber" },
  in_kitchen: { en: "Box Box", tone: "purple" }, out_for_delivery: { en: "Flying Lap", tone: "cyan" },
  ready_for_pickup: { en: "Pit Lane", tone: "cyan" }, delivered: { en: "Chequered Flag", tone: "green" },
};
const PROPOSAL_TEXT = { pending: "ממתינה", approved: "אושרה", rejected: "נדחתה", expired: "פגה", failed: "נכשלה" };
const RULE_TEXT = { per_adult: "למבוגר", per_child: "לילד", round_step: "צעד עיגול" };
const ACTIVE = ["pending_approval", "approved", "in_kitchen", "out_for_delivery", "ready_for_pickup"];
const nextTerm = (o) => (o.status === "approved" ? "Box Box"
  : o.status === "in_kitchen" ? (o.fulfillment_type === "delivery" ? "Flying Lap" : "Pit Lane") : "Chequered Flag");
const canAdvance = (o) => ["approved", "in_kitchen", "out_for_delivery", "ready_for_pickup"].includes(o.status);
const money = (v, cur) => `${Number(v).toFixed(2)} ${cur}`;
const shekel = (v) => `₪${Number(v).toLocaleString("en-US", { maximumFractionDigits: 2 })}`;
const statusBadge = (st) => h("span", { class: `chip chip-${STAGES[st]?.tone ?? (st === "rejected" || st === "cancelled" ? "red" : "muted")}` }, STATUS_TEXT[st] ?? st);
const stageChip = (st) => h("span", { class: "stage" },
  h("span", { class: `chip chip-${STAGES[st]?.tone ?? "muted"}` }, STAGES[st]?.en ?? st), h("small", {}, STATUS_TEXT[st] ?? st));
const firstName = (n) => String(n ?? "").trim().split(/\s+/)[0] || "—";

// Advance one stage with the version the screen was rendered from; a conflict reloads the view.
function advanceButton(o, after) {
  const btn = h("button", { type: "button", class: "primary advance", "aria-label": `קידום הזמנה ${o.id.slice(0, 8)} ל-${nextTerm(o)}` }, "Advance ◂");
  btn.addEventListener("click", () => {
    btn.disabled = true;
    run(async () => {
      try {
        const r = await api(`/api/admin/orders/${o.id}/advance`, { method: "POST", body: JSON.stringify({ version: o.version }) });
        say(`ההזמנה התקדמה ל-${STAGES[r.status]?.en ?? r.status}.`);
        beep();
      } catch (e) {
        if (e.status !== 409) throw e;
        say(e.code === "order_version_conflict" ? "ההזמנה עודכנה במקום אחר. הרשימה רועננה, נסו שוב." : "אי אפשר להתקדם מהשלב הזה. הרשימה רועננה.", "error");
      }
      await after();
    }).finally(() => { btn.disabled = false; });
  });
  return btn;
}

// ---- Pit Wall dashboard
async function showWall(tabs) {
  const list = await api("/api/admin/orders");
  const today = todayStr();
  const near = (o) => Math.abs((new Date(o.event_date) - new Date(today)) / 864e5) <= 1;
  const full = list.filter((o) => ACTIVE.includes(o.status) || (o.status === "delivered" && near(o)));
  const active = full.filter((o) => ACTIVE.includes(o.status)).sort((a, b) => parseTs(a.requested_at) - parseTs(b.requested_at));
  const doneToday = full.filter((o) => o.status === "delivered" && localDay(o.delivered_at) === today).length;
  const count = (...st) => active.filter((o) => st.includes(o.status)).length;
  const tile = (n, tone, term, he, num) => h("div", { class: `tile tile-${tone}` },
    h("div", { class: "label" }, `SECTOR ${n} // ${term}`), h("div", { class: "he" }, he), h("div", { class: "num" }, String(num)));
  const tiles = h("section", { class: "tiles", "aria-label": "שלבים" },
    tile(1, "amber", "GRID", "ממתינות לאישור ולהכנה", count("pending_approval", "approved")),
    tile(2, "purple", "BOX BOX", "בבישול והכנה", count("in_kitchen")),
    tile(3, "cyan", "FLYING LAP", "במשלוח / מוכנות לאיסוף", count("out_for_delivery", "ready_for_pickup")),
    tile(4, "green", "CHEQUERED FLAG", "נמסרו היום", doneToday));
  const goOrder = (id) => run(() => openSection("orders", id));
  const refresh = () => showWall(tabs);
  const tower = h("section", { class: "panel tower" },
    h("div", { class: "head" }, h("h2", {}, "TIMING TOWER"), h("p", { class: "hint" }, "הזמנות פעילות לפי מועד האירוע")),
    active.length ? h("ul", { class: "rows" },
      h("li", { class: "row th", "aria-hidden": "true" }, ...["POS", "לקוח / תאריך", "אורחים", "סך הזמנה", "שלב", ""].map((t) => h("span", { class: "label" }, t))),
      ...active.map((o, i) => h("li", { class: `row tone-${STAGES[o.status].tone}` },
        h("span", { class: "pos" }, `P${i + 1}`),
        h("span", { class: "who" }, h("button", { type: "button", class: "link", onclick: () => goOrder(o.id) }, firstName(o.customer_name)),
          h("small", {}, `${fmtDate(o.event_date)} · ${fmtTime(o.requested_at)}`)),
        h("span", { class: "guests" }, `${o.guests} אורחים`),
        h("span", { class: "total num" }, shekel(o.total)),
        stageChip(o.status),
        canAdvance(o) ? advanceButton(o, refresh)
          : h("button", { type: "button", class: "ghost", onclick: () => goOrder(o.id) }, o.status === "pending_approval" ? "לאישור" : "פתיחה"))))
      : h("p", { class: "hint" }, "אין הזמנות פעילות."));
  const todays = full.filter((o) => o.event_date === today)
    .sort((a, b) => parseTs(a.requested_at) - parseTs(b.requested_at));
  const race = h("section", { class: "panel race" },
    h("div", { class: "head" }, h("h2", {}, "RACE CONTROL"), h("p", { class: "hint" }, "האירועים של היום לפי שעה")),
    todays.length ? h("ol", { class: "timeline" }, ...todays.map((o) => h("li", { class: `tone-${STAGES[o.status].tone}` },
      h("time", { class: "num" }, fmtTime(o.requested_at)),
      h("div", {}, h("span", { class: `chip chip-${STAGES[o.status].tone}` }, STAGES[o.status].en),
        h("strong", {}, firstName(o.customer_name)), h("small", {}, `${o.guests} אורחים`))))) 
      : h("p", { class: "hint" }, "אין אירועים להיום."));
  app.replaceChildren(tabs, tiles, h("div", { class: "wall" }, tower, race));
}

async function showOrders(tabs, filter = "", openId = null) {
  const rows = await api(`/api/admin/orders${filter ? `?status=${encodeURIComponent(filter)}` : ""}`);
  const holder = h("div");
  const select = h("select", { onchange: () => run(() => showOrders(tabs, select.value)) },
    h("option", { value: "" }, "הכול"),
    ...Object.entries(STATUS_TEXT).map(([v, t]) => h("option", { value: v }, t)));
  select.value = filter;
  const refresh = (id) => showOrders(tabs, filter, id);
  const table = h("div", { class: "table-wrap" }, h("table", {},
    h("thead", {}, h("tr", {}, ...["תאריך", "לקוח", "סוג אירוע", "אורחים", "סכום", "סטטוס", ""].map((c) => h("th", {}, c)))),
    h("tbody", {}, ...rows.map((o) => h("tr", {},
      h("td", {}, fmtDate(o.event_date)), h("td", {}, cell(o.customer_name)), h("td", {}, cell(o.event_type)),
      h("td", {}, cell(o.guests)),
      h("td", {}, o.status === "draft" || o.total == null ? "—" : money(o.total, o.currency)),
      h("td", {}, statusBadge(o.status)),
      h("td", { class: "actions" }, h("button", { type: "button", onclick: () => run(async () => {
        holder.replaceChildren(await orderDetail(o.id, refresh));
        holder.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }) }, "פתיחה")))))));
  app.replaceChildren(tabs, h("section", {}, h("h2", {}, "הזמנות"),
    h("label", { class: "filter" }, "סטטוס", select),
    h("div", { class: "card" }, rows.length ? table : h("p", { class: "hint" }, "אין הזמנות.")), holder));
  if (openId) holder.replaceChildren(await orderDetail(openId, refresh));
}

async function orderDetail(id, refresh) {
  const o = await api(`/api/admin/orders/${id}`);
  const ev = o.event;
  const dl = (pairs) => h("dl", {}, ...pairs.flatMap(([k, v]) => [h("dt", {}, k), h("dd", {}, cell(v))]));
  const note = h("textarea", { maxlength: 1000, rows: 3 });
  const actions = h("div", { class: "decision" });
  const decide = (kind) => run(async () => {
    try {
      await api(`/api/admin/orders/${id}/${kind}`, { method: "POST", body: JSON.stringify({ note: note.value.trim() || null }) });
      await refresh(id);
      say(kind === "approve" ? "ההזמנה אושרה." : "ההזמנה נדחתה.");
      if (kind === "approve") beep();
    } catch (e) {
      if (e.code !== "invalid_transition") throw e;
      await refresh(id);
      say("ההזמנה כבר טופלה או שאינה ממתינה לאישור. התצוגה רועננה.", "error");
    }
  });
  const ask = (kind) => actions.replaceChildren(
    h("span", { role: "alert" }, kind === "approve" ? "לאשר את ההזמנה?" : "לדחות את ההזמנה?"),
    h("button", { type: "button", class: kind === "approve" ? "approve" : "danger", onclick: () => decide(kind) }, kind === "approve" ? "כן, לאשר" : "כן, לדחות"),
    h("button", { type: "button", onclick: idle }, "חזרה"));
  function idle() {
    actions.replaceChildren(h("button", { type: "button", class: "approve", onclick: () => ask("approve") }, "אשר הזמנה"),
      h("button", { type: "button", class: "danger", onclick: () => ask("reject") }, "דחה"));
  }
  idle();
  const why = h("textarea", { maxlength: 1000, rows: 3 });
  const cancelBox = h("div", { class: "decision" });
  const doCancel = () => run(async () => {
    try {
      await api(`/api/admin/orders/${id}/cancel`, { method: "POST", body: JSON.stringify({ note: why.value.trim() }) });
      await refresh(id);
      say("ההזמנה בוטלה.");
    } catch (e) {
      if (e.code !== "invalid_transition") throw e;
      await refresh(id);
      say("אי אפשר לבטל את ההזמנה יותר. התצוגה רועננה.", "error");
    }
  });
  const askCancel = () => cancelBox.replaceChildren(
    h("span", { role: "alert" }, "לבטל את ההזמנה? הלקוח יראה את ההערה."),
    h("button", { type: "button", class: "danger", onclick: doCancel }, "כן, לבטל"),
    h("button", { type: "button", onclick: idleCancel }, "השאר הזמנה"));
  function idleCancel() {
    cancelBox.replaceChildren(h("button", { type: "button", class: "danger", disabled: !why.value.trim(), onclick: askCancel }, "בטל הזמנה"));
  }
  why.addEventListener("input", idleCancel);
  idleCancel();
  const ai = await api(`/api/admin/orders/${id}/assistant`);
  const diffText = (d) => `${d.name}: ${d.current == null ? "—" : d.current} → ${d.proposed == null ? "הוסר" : d.proposed}`;
  const assistant = h("div", { class: "assistant" },
    h("p", {}, `${ai.message_count} הודעות · אחרונה ב-${fmtDT(ai.last_message_at)}`),
    ai.proposals.length ? h("ul", { class: "proposals" }, ...ai.proposals.map((p) => h("li", {},
      h("span", { class: "chip" }, PROPOSAL_TEXT[p.status] ?? p.status), ` ${fmtDT(p.created_at)} · ${money(p.price_before, o.currency)} → ${money(p.price_after, o.currency)}`,
      h("ul", {}, ...p.diff.map((d) => h("li", {}, diffText(d))))))) : h("p", { class: "hint" }, "אין הצעות."));
  const cur = { pending_approval: 0, approved: 0, in_kitchen: 1, out_for_delivery: 2, ready_for_pickup: 2, delivered: 3 }[o.status];
  const delivery = o.fulfillment_type === "delivery";
  const steps = [["Grid", "הזמנה אושרה", o.submitted_at], ["Box Box", "בישול והכנה", o.kitchen_at],
    [delivery ? "Flying Lap" : "Pit Lane", delivery ? "במשלוח" : "מוכנה לאיסוף", o.dispatched_at], ["Chequered Flag", "נמסרה", o.delivered_at]];
  const timeline = h("ol", { class: "sectors" }, ...steps.map(([en, he, at], i) => h("li", {
    class: i === cur && o.status !== "delivered" ? "active" : at || (cur != null && i <= cur) ? "done" : "", "aria-current": i === cur ? "step" : null },
    h("span", { class: "dot", "aria-hidden": "true" }), h("strong", { dir: "ltr" }, en), h("small", {}, he), h("span", { class: "label" }, at ? fmtDT(at) : "—"))));
  const stars = (n) => "★".repeat(n) + "☆".repeat(5 - n);
  const driver = h("section", { class: "panel" }, h("h3", {}, "DRIVER OF THE DAY"),
    o.rating ? h("div", { class: "rating" }, h("div", { class: "stars", role: "img", "aria-label": `${o.rating.stars} / 5` }, stars(o.rating.stars)),
      o.rating.comment ? h("p", { class: "comment" }, o.rating.comment) : null, h("span", { class: "label" }, fmtDT(o.rating.created_at)))
      : h("p", { class: "hint" }, "הדירוג יופיע אחרי Chequered Flag"));
  const decisionBlock = o.status === "pending_approval"
    ? h("div", {}, h("label", {}, "הערה (אופציונלי, עד 1000 תווים)", note), actions)
    : o.decided_at ? h("div", {}, h("h3", {}, "החלטה"), dl([["זמן ההחלטה", fmtDT(o.decided_at)], ["הערה", o.decision_note]])) : null;
  const advance = canAdvance(o) ? advanceButton(o, () => refresh(id)) : null;
  return h("div", { class: "order-detail" },
    h("header", { class: "panel od-head" }, h("div", {}, h("div", { class: "label" }, `הזמנה ${o.id.slice(0, 8)}`), h("h2", {}, o.customer.full_name), stageChip(o.status)),
      h("div", { class: "od-total" }, h("span", { class: "label" }, "סה\"כ"), h("span", { class: "num" }, shekel(o.total)))),
    o.reopened_at ? h("p", { class: "notice", role: "note" }, `שונתה על ידי הלקוח ב-${fmtDT(o.reopened_at)}`) : null,
    h("div", { class: "od-grid" },
      h("div", { class: "col" },
        h("section", { class: "panel" }, h("h3", {}, "RACE CONTROL"), decisionBlock, advance,
          o.status === "pending_approval" || o.status === "approved"
            ? h("div", {}, h("h3", {}, "ביטול הזמנה"), h("label", {}, "סיבה (חובה, מוצגת ללקוח, עד 1000 תווים)", why), cancelBox) : null,
          o.cancelled_at ? h("div", {}, h("h3", {}, "ביטול"), dl([["זמן הביטול", fmtDT(o.cancelled_at)], ["הערת ביטול", o.cancel_note]])) : null),
        h("section", { class: "panel" }, h("h3", {}, "RACE ENGINEER"), assistant),
        driver),
      h("div", { class: "col" },
        h("section", { class: "panel" }, h("h3", {}, "SECTOR TIMINGS"), timeline),
        h("section", { class: "panel" },
          h("h3", {}, "איש קשר"), dl([["שם", o.customer.full_name], ["אימייל", o.customer.email], ["טלפון", o.customer.phone]]),
          h("h3", {}, "אירוע"), dl([["סוג", ev.event_type], ["תאריך", fmtDate(ev.event_date)], ["מבוגרים", ev.adults], ["ילדים", ev.children],
            ["אורחים צמחוניים (מתוך הסך)", ev.vegetarian_guests], ["אורחים טבעוניים (מתוך הסך)", ev.vegan_guests],
            ["אורחים עם הגבלות תזונה (מתוך הסך)", ev.restricted_guests], ["הערות תזונה", ev.dietary_notes]]),
          h("h3", {}, "אספקה"), dl([["סוג", FULFIL_TEXT[o.fulfillment_type] ?? o.fulfillment_type], ["זמן מבוקש", fmtDT(o.requested_at)], ["כתובת", o.delivery_address]])),
        h("section", { class: "panel" }, h("h3", {}, "LOCKED SNAPSHOT MANIFEST"),
          h("div", { class: "table-wrap" }, h("table", {}, h("tbody", {}, ...o.items.map((i) => h("tr", {},
            h("td", {}, i.name),
            h("td", { class: "num" }, `${i.quantity} × ${money(i.unit_price, o.currency)}${i.unit ? ` (${i.unit})` : ""}`),
            h("td", { class: "num" }, money(i.line_total, o.currency))))))),
          o.warnings?.includes("mixes_meat_dairy") ? h("p", { class: "notice", role: "note" }, "ההזמנה מערבבת מנות בשריות וחלביות") : null,
          dl([...(o.delivery_km != null ? [["מרחק", `${Number(o.delivery_km)} ק\"מ`]] : []), ["סכום ביניים", money(o.subtotal, o.currency)],
            ["דמי משלוח", o.delivery_fee == null ? (o.delivery_fee_estimated ? "יאושר בהמשך (הכתובת לא נמצאה)" : "—")
              : o.delivery_fee_estimated ? `${money(o.delivery_fee, o.currency)} (הערכה)` : money(o.delivery_fee, o.currency)],
            ["סה\"כ", money(o.total, o.currency)]]),
          h("p", { class: "hint" }, "המחירים כוללים מע\"מ.")))));
}

// ---- serving rules
async function showRules(tabs) {
  const [cats, rules] = await Promise.all([api("/api/admin/categories"), api("/api/admin/quantity-rules")]);
  const byCat = new Map(rules.map((r) => [r.category_id, r]));
  const rows = cats.filter((c) => c.is_active).map((c) => {
    const rule = byCat.get(c.id);
    const num = (name, v, min) => h("input", { type: "number", name, min, step: "0.001", required: true, value: v ?? "", "aria-label": RULE_TEXT[name] });
    const pa = num("per_adult", rule?.per_adult, "0"), pc = num("per_child", rule?.per_child, "0"), rs = num("round_step", rule?.round_step, "0.001");
    const save = () => run(async () => {
      if (!(Number(rs.value) > 0) || pa.value === "" || pc.value === "") throw new Error("מלאו את שלושת הערכים; צעד העיגול חייב להיות גדול מ-0.");
      await api(`/api/admin/quantity-rules/${c.id}`, { method: "PUT",
        body: JSON.stringify({ per_adult: pa.value, per_child: pc.value, round_step: rs.value }) });
      await showRules(tabs); say("הכלל נשמר.");
    });
    const remove = () => run(async () => { await api(`/api/admin/quantity-rules/${c.id}`, { method: "DELETE" }); await showRules(tabs); say("הכלל הוסר."); });
    return h("tr", {}, h("td", {}, c.name_en || c.name_he), h("td", {}, pa), h("td", {}, pc), h("td", {}, rs),
      h("td", {}, rule ? "מוגדר" : "אין כלל"),
      h("td", { class: "actions" }, h("button", { type: "button", class: "primary", onclick: save }, "שמירה"),
        rule ? h("button", { type: "button", class: "danger", onclick: remove }, "הסרה") : null));
  });
  app.replaceChildren(tabs, h("section", {}, h("h2", {}, "כללי כמויות"),
    h("p", {}, "כמה להכין לכל מבוגר ולכל ילד, ביחידה של המנה (מגש/ק\"ג/יחידה). מנות שנבחרו באותה קטגוריה מתחלקות בכמות שווה; ההצעות מעוגלות כלפי מעלה. בלי כלל, הלקוח לא מקבל כמות מוצעת."),
    h("div", { class: "card" }, h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, ...["קטגוריה", "למבוגר", "לילד", "צעד עיגול", "כלל", ""].map((c) => h("th", {}, c)))),
      h("tbody", {}, ...rows))))));
}

// ---- settings
async function showSettings(tabs) {
  const st = await api("/api/admin/settings");
  const connected = (await api("/api/admin/notify-status").catch(() => ({ enabled: false }))).enabled;
  const f = (name, label, unit, attrs) => [name, h("label", {}, `${label} (${unit})`, h("input", { name, required: true, value: st[name] ?? "", ...attrs }))];
  const num = (name, label, unit, max) => f(name, label, unit, { type: "number", min: "0", step: name === "lead_time_days" || name === "edit_cutoff_hours" ? "1" : "0.01", ...(max ? { max } : {}) });
  const fields = Object.fromEntries([num("lead_time_days", "התראה מראש", "ימים", "365"), num("edit_cutoff_hours", "סגירת עריכה (שעות לפני האירוע)", "שעות", "168"), num("min_food_total", "מינימום אוכל", "₪"),
    num("delivery_base_fee", "דמי משלוח בסיסיים", "₪"), num("delivery_per_km", "לכל ק\"מ", "₪"), num("delivery_max_km", "מרחק מקסימלי", "ק\"מ", "500"),
    f("kitchen_address", "כתובת המטבח", "טקסט", { type: "text", maxlength: 300 })]);
  const form = h("form", { class: "card", onsubmit: (ev) => {
    ev.preventDefault();
    run(async () => {
      const body = {};
      for (const [k, label] of Object.entries(fields)) body[k] = label.querySelector("input").value.trim();
      body.lead_time_days = Number(body.lead_time_days);
      body.edit_cutoff_hours = Number(body.edit_cutoff_hours);
      await api("/api/admin/settings", { method: "PUT", body: JSON.stringify(body) });
      await showSettings(tabs); say("ההגדרות נשמרו.");
    });
  } }, ...Object.values(fields),
    h("p", { class: "hint" }, `מיקום: ${st.kitchen_lat}, ${st.kitchen_lon}`),
    h("button", { class: "primary", type: "submit" }, "שמירה"));
  const sms = (label, text, dir) => h("label", {}, label, h("textarea", { readonly: true, rows: 3, dir }, text));
  const safety = h("section", { class: "panel safety" }, h("h2", {}, "SAFETY CAR"),
    h("p", { class: "hint" }, "הפעלת Safety Car מציגה ללקוחות באנר ענבר ומאטה את קצב ההזמנות."), safetySwitch(),
    h("div", { class: "label" }, "תצוגה מקדימה של הטיקר ללקוחות"), h("p", { class: "ticker", dir: "ltr" }, TICKER));
  const smsBox = h("section", { class: "panel" }, h("h2", {}, "SMS / WHATSAPP"),
    h("p", { class: "notice", role: "note" }, `ספק SMS/WhatsApp: ${connected ? "מחובר" : "לא מחובר"}`),
    h("div", { class: "grid" },
      sms("עברית (Flying Lap)", "ההזמנה שלך יצאה למסלול! Flying Lap - הצוות בדרך אליך", "rtl"),
      sms("العربية (Flying Lap)", "طلبك انطلق! Flying Lap - الفريق في الطريق إليك", "rtl")),
    h("p", { class: "hint", dir: "ltr" }, "{customer_name} {driver_name} {eta} {order_id}"));
  app.replaceChildren(tabs, h("section", {}, h("h2", {}, "הגדרות"), form, safety, smsBox));
}

// ---- shell
const GROUPS = {
  wall: { label: "Pit Wall", keys: [] }, orders: { label: "הזמנות", keys: [] },
  menu: { label: "תפריט", keys: ["categories", "dishes", "serving-rules"] },
  settings: { label: "הגדרות", keys: ["settings", "time-slots", "blocked-dates"] },
};
const SUB = { categories: "קטגוריות", dishes: "מנות", "serving-rules": "כללי כמויות", settings: "הגדרות", "time-slots": "חלונות זמן", "blocked-dates": "תאריכים חסומים" };
const groupOf = (key) => (GROUPS[key] ? key : Object.keys(GROUPS).find((g) => GROUPS[g].keys.includes(key)));

async function showDashboard() {
  state.config ??= await api("/api/public-config");
  try { setSafety((await api("/api/public-settings")).safety_car); } catch { /* the switch stays off */ }
  openSection = async (key, arg = null) => {
    const g = groupOf(key);
    for (const b of topTabs.children) b.setAttribute("aria-current", String(b.dataset.key === g));
    const sub = h("nav", { class: "subnav", "aria-label": "תתי-אזורים" });
    for (const k of GROUPS[g].keys) sub.append(h("button", { type: "button", "aria-pressed": String(k === key), onclick: () => run(() => openSection(k)) }, SUB[k]));
    if (key === "wall") await showWall(sub);
    else if (key === "orders") await showOrders(sub, "", arg);
    else if (key === "serving-rules") await showRules(sub);
    else if (key === "settings") await showSettings(sub);
    else await showResource(key, sub);
  };
  topTabs.replaceChildren(...Object.entries(GROUPS).map(([g, { label, keys }]) =>
    h("button", { type: "button", class: "tab", "data-key": g, "aria-current": "false", onclick: () => run(() => openSection(keys[0] ?? g)) }, label)));
  tools.replaceChildren(safetySwitch(), muteToggle({ on: "רדיו פעיל", off: "השתקת רדיו", aria: "השתקת הרדיו" }), h("button", { type: "button", class: "ghost", onclick: () => logout() }, "יציאה"));
  await openSection("wall");
}

if (auth.get()) run(showDashboard); else showLogin();
