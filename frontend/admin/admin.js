// All DOM is built with createElement/textContent; server data is never parsed as HTML.
import { api, auth } from "/js/api.js";

const app = document.getElementById("app");
const message = document.getElementById("message");
const state = { config: null, categories: [], allergens: [] };

function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (value === true) el.setAttribute(key, "");
    else if (value !== false && value != null) el.setAttribute(key, value);
  }
  el.append(...children.flat().filter((c) => c != null));
  return el;
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
    if (e.status === 401) return logout("Session expired. Please log in again.");
    say(e.status === 403 ? "This account is not an admin." : e.message, "error");
  }
}

function logout(text = "") {
  auth.clear();
  showLogin();
  say(text, "error");
}

// ---- login (Supabase Auth REST, email + password)
function showLogin() {
  const email = h("input", { type: "email", required: true, autocomplete: "username" });
  const password = h("input", { type: "password", required: true, autocomplete: "current-password" });
  const form = h("form", { class: "card", onsubmit: (ev) => { ev.preventDefault(); run(() => login(email.value, password.value)); } },
    h("label", {}, "Email", email),
    h("label", {}, "Password", password),
    h("button", { class: "primary", type: "submit" }, "Log in"));
  app.replaceChildren(form);
}

async function login(email, password) {
  state.config ??= await api("/api/public-config");
  const { supabase_url: url, supabase_anon_key: key } = state.config;
  if (!url || !key) throw new Error("Supabase is not configured on the server.");
  const response = await fetch(`${url}/auth/v1/token?grant_type=password`, {
    method: "POST",
    headers: { "Content-Type": "application/json", apikey: key },
    body: JSON.stringify({ email, password }),
  });
  const body = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error("Login failed. Check your email and password.");
  auth.set(body.access_token);
  await showDashboard();
}

// ---- generic CRUD tab
const LANG_FIELDS = (base, label, required) => [
  { name: `${base}_he`, label: `${label} (Hebrew${required ? ", required" : ""})`, dir: "rtl", required },
  { name: `${base}_ar`, label: `${label} (Arabic)`, dir: "rtl" },
  { name: `${base}_en`, label: `${label} (English)`, dir: "ltr" },
];
const UNITS = ["per_guest", "per_tray", "per_weight", "per_item"];

const RESOURCES = {
  categories: {
    title: "Categories", path: "/api/admin/categories",
    fields: [...LANG_FIELDS("name", "Name", true),
      { name: "sort_order", label: "Sort order", type: "number", step: "1", def: 0 },
      { name: "is_active", label: "Active", type: "checkbox", def: true }],
    columns: ["name_he", "name_en", "sort_order", "is_active"],
  },
  dishes: {
    title: "Dishes", path: "/api/admin/dishes",
    fields: [{ name: "category_id", label: "Category", type: "select", options: () => state.categories.map((c) => [c.id, c.name_he]), required: true },
      ...LANG_FIELDS("name", "Name", true),
      ...LANG_FIELDS("description", "Description", false).map((f) => ({ ...f, type: "textarea" })),
      { name: "pricing_unit", label: "Pricing unit", type: "select", options: () => UNITS.map((u) => [u, u]), required: true },
      { name: "unit_price", label: "Unit price (ILS)", type: "number", step: "0.01", min: "0", required: true },
      { name: "unit_label", label: "Unit label (e.g. tray size)" },
      { name: "min_quantity", label: "Minimum quantity", type: "number", step: "0.01", min: "0" },
      { name: "is_available", label: "Available", type: "checkbox", def: true }],
    columns: ["name_he", "name_en", "unit_price", "pricing_unit", "is_available"],
    extras: dishExtras,
  },
  "delivery-zones": {
    title: "Delivery zones", path: "/api/admin/delivery-zones",
    fields: [{ name: "name", label: "Name", required: true },
      { name: "fee", label: "Fee (ILS)", type: "number", step: "0.01", min: "0", required: true },
      { name: "definition", label: "Definition (JSON object, e.g. {\"cities\":[\"Haifa\"]})", type: "json", def: {} },
      { name: "is_active", label: "Active", type: "checkbox", def: true }],
    columns: ["name", "fee", "is_active"],
  },
  "time-slots": {
    title: "Time slots", path: "/api/admin/time-slots",
    fields: [{ name: "fulfillment_type", label: "Type", type: "select", options: () => [["pickup", "pickup"], ["delivery", "delivery"]], required: true },
      { name: "weekday", label: "Weekday (0-6, blank = every day)", type: "number", step: "1", min: "0", max: "6" },
      { name: "start_time", label: "Start", type: "time", required: true },
      { name: "end_time", label: "End", type: "time", required: true },
      { name: "capacity", label: "Capacity (blank = unlimited)", type: "number", step: "1", min: "0" },
      { name: "is_active", label: "Active", type: "checkbox", def: true }],
    columns: ["fulfillment_type", "weekday", "start_time", "end_time", "capacity", "is_active"],
  },
  "blocked-dates": {
    title: "Blocked dates", path: "/api/admin/blocked-dates", noEdit: true,
    fields: [{ name: "date", label: "Date", type: "date", required: true }, { name: "reason", label: "Reason" }],
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
    h("thead", {}, h("tr", {}, ...cfg.columns.map((c) => h("th", {}, c)), h("th", {}, "Actions"))),
    h("tbody", {}, ...rows.map((row) => h("tr", {},
      ...cfg.columns.map((c) => h("td", {}, cell(row[c]))),
      h("td", { class: "actions" },
        cfg.noEdit ? null : h("button", { type: "button", onclick: () => edit(row.id) }, "Edit"),
        h("button", { type: "button", class: "danger", onclick: () => remove(row) }, "Delete")))))));

  function remove(row) {
    if (!confirm("Delete this item?")) return;
    run(async () => { await api(`${cfg.path}/${row.id}`, { method: "DELETE" }); await showResource(key, tabs); say("Deleted."); });
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
        say("Saved.");
      });
    } },
      h("h2", {}, row ? `Edit ${cfg.title.toLowerCase()}` : `New ${cfg.title.toLowerCase()}`),
      h("div", { class: "grid" }, ...cfg.fields.map((f) => f.type === "checkbox"
        ? h("label", { class: "check" }, input(f, row ? row[f.name] : f.def), " ", f.label)
        : h("label", {}, f.label, input(f, row ? row[f.name] : f.def)))),
      h("button", { class: "primary", type: "submit" }, "Save"));
    const box = h("div", {}, form);
    if (row && cfg.extras) box.append(await cfg.extras(row, () => edit(row.id)));
    return box;
  }

  holder.append(h("button", { type: "button", class: "primary", onclick: () => edit(null) }, `New ${cfg.title.toLowerCase()}`));
  const view = h("section", {}, h("h2", {}, cfg.title), h("div", { class: "card" }, table), holder);
  app.replaceChildren(tabs, view);
  if (openId) await edit(openId);
}

// ---- dish extras: dietary info, allergens, image
async function dishExtras(dish, reload) {
  if (!state.allergens.length) state.allergens = await api("/api/admin/allergens");
  const tri = (name, value) => {
    const s = h("select", { name }, h("option", { value: "" }, "Unknown"), h("option", { value: "true" }, "Yes"), h("option", { value: "false" }, "No"));
    s.value = value === null || value === undefined ? "" : String(value);
    return s;
  };
  const kashrut = h("select", { name: "kashrut_class" }, h("option", { value: "" }, "Unknown"),
    ...["meat", "dairy", "pareve"].map((k) => h("option", { value: k }, k)));
  kashrut.value = dish.dietary.kashrut_class ?? "";
  const current = Object.fromEntries(dish.allergens.map((a) => [a.allergen_id, a.status]));
  const allergenSelects = state.allergens.map((a) => {
    const s = h("select", { "data-allergen": a.id }, ...["unknown", "contains", "free"].map((v) => h("option", { value: v }, v)));
    s.value = current[a.id] ?? "unknown";
    return h("label", {}, a.name, s);
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
      say("Dietary info saved.");
    });
  } },
    h("h2", {}, "Dietary info and allergens"),
    h("p", {}, "Unknown means not provided; it is never shown as No."),
    h("div", { class: "grid" }, h("label", {}, "Kashrut", kashrut), h("label", {}, "Vegetarian", veg), h("label", {}, "Vegan", vegan)),
    h("fieldset", {}, h("legend", {}, "Allergens"), h("div", { class: "grid" }, ...allergenSelects)),
    h("button", { class: "primary", type: "submit" }, "Save dietary info"));

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
      say("Image uploaded.");
      reload();
    });
  } },
    h("h2", {}, "Image (JPEG, PNG or WebP, up to 5 MB)"), preview,
    h("label", {}, "File", file), h("button", { class: "primary", type: "submit" }, "Upload"));
  return h("div", {}, dietaryForm, imageForm);
}

// ---- shell
async function showDashboard() {
  state.config ??= await api("/api/public-config");
  const tabs = h("nav", { "aria-label": "Sections" });
  const open = (key) => run(async () => {
    for (const b of tabs.children) b.setAttribute("aria-pressed", String(b.dataset.key === key));
    await showResource(key, tabs);
  });
  for (const [key, cfg] of Object.entries(RESOURCES)) {
    tabs.append(h("button", { type: "button", "data-key": key, "aria-pressed": "false", onclick: () => open(key) }, cfg.title));
  }
  tabs.append(h("button", { type: "button", onclick: () => logout() }, "Log out"));
  app.replaceChildren(tabs);
  await open("categories");
}

if (auth.get()) run(showDashboard); else showLogin();
