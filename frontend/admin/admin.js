// All DOM is built with createElement/textContent; server data is never parsed as HTML.
import { api, auth } from "/js/api.js";
import { h } from "/js/dom.js";

const app = document.getElementById("app");
const message = document.getElementById("message");
const state = { config: null, categories: [], allergens: [] };

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

// ---- orders
const STATUS_TEXT = { draft: "Draft", pending_approval: "Awaiting approval", approved: "Approved", rejected: "Rejected", cancelled: "Cancelled" };
const money = (v, cur) => `${Number(v).toFixed(2)} ${cur}`;
const statusBadge = (st) => h("span", { class: `badge badge-${st}` }, STATUS_TEXT[st] ?? st);

async function showOrders(tabs, filter = "", openId = null) {
  const rows = await api(`/api/admin/orders${filter ? `?status=${encodeURIComponent(filter)}` : ""}`);
  const holder = h("div");
  const select = h("select", { onchange: () => run(() => showOrders(tabs, select.value)) },
    h("option", { value: "" }, "All"),
    ...Object.entries(STATUS_TEXT).map(([v, t]) => h("option", { value: v }, t)));
  select.value = filter;
  const refresh = (id) => showOrders(tabs, filter, id);
  const table = h("div", { class: "table-wrap" }, h("table", {},
    h("thead", {}, h("tr", {}, ...["Event date", "Customer", "Event type", "Guests", "Total", "Status", ""].map((c) => h("th", {}, c)))),
    h("tbody", {}, ...rows.map((o) => h("tr", {},
      h("td", {}, cell(o.event_date)), h("td", {}, cell(o.customer_name)), h("td", {}, cell(o.event_type)),
      h("td", {}, cell(o.guests)),
      h("td", {}, o.status === "draft" || o.total == null ? "—" : money(o.total, o.currency)),
      h("td", {}, statusBadge(o.status)),
      h("td", { class: "actions" }, h("button", { type: "button", onclick: () => run(async () => {
        holder.replaceChildren(await orderDetail(o.id, refresh));
        holder.scrollIntoView({ behavior: "smooth", block: "nearest" });
      }) }, "Open")))))));
  app.replaceChildren(tabs, h("section", {}, h("h2", {}, "Orders"),
    h("label", { class: "filter" }, "Status", select),
    h("div", { class: "card" }, rows.length ? table : h("p", {}, "No orders.")), holder));
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
      say(kind === "approve" ? "Order approved." : "Order rejected.");
    } catch (e) {
      if (e.code !== "invalid_transition") throw e;
      await refresh(id);
      say("This order was already decided or is not awaiting approval. The view was refreshed.", "error");
    }
  });
  const ask = (kind) => actions.replaceChildren(
    h("span", { role: "alert" }, kind === "approve" ? "Approve this order?" : "Reject this order?"),
    h("button", { type: "button", class: kind === "approve" ? "primary" : "danger", onclick: () => decide(kind) }, `Yes, ${kind}`),
    h("button", { type: "button", onclick: idle }, "Cancel"));
  function idle() {
    actions.replaceChildren(h("button", { type: "button", class: "primary", onclick: () => ask("approve") }, "Approve"),
      h("button", { type: "button", class: "danger", onclick: () => ask("reject") }, "Reject"));
  }
  idle();
  const why = h("textarea", { maxlength: 1000, rows: 3 });
  const cancelBox = h("div", { class: "decision" });
  const doCancel = () => run(async () => {
    try {
      await api(`/api/admin/orders/${id}/cancel`, { method: "POST", body: JSON.stringify({ note: why.value.trim() }) });
      await refresh(id);
      say("Order cancelled.");
    } catch (e) {
      if (e.code !== "invalid_transition") throw e;
      await refresh(id);
      say("This order can no longer be cancelled. The view was refreshed.", "error");
    }
  });
  const askCancel = () => cancelBox.replaceChildren(
    h("span", { role: "alert" }, "Cancel this order? The customer will see your note."),
    h("button", { type: "button", class: "danger", onclick: doCancel }, "Yes, cancel"),
    h("button", { type: "button", onclick: idleCancel }, "Keep order"));
  function idleCancel() {
    cancelBox.replaceChildren(h("button", { type: "button", class: "danger", disabled: !why.value.trim(), onclick: askCancel }, "Cancel order"));
  }
  why.addEventListener("input", idleCancel);
  idleCancel();
  const ai = await api(`/api/admin/orders/${id}/assistant`);
  const diffText = (d) => `${d.name}: ${d.current == null ? "—" : d.current} → ${d.proposed == null ? "removed" : d.proposed}`;
  const assistant = h("div", { class: "assistant" },
    h("p", {}, `${ai.message_count} messages · last at ${cell(ai.last_message_at)}`),
    ai.proposals.length ? h("ul", { class: "proposals" }, ...ai.proposals.map((p) => h("li", {},
      h("span", { class: `badge badge-${p.status}` }, p.status), ` ${p.created_at} · ${money(p.price_before, o.currency)} → ${money(p.price_after, o.currency)}`,
      h("ul", {}, ...p.diff.map((d) => h("li", {}, diffText(d))))))) : h("p", { class: "hint" }, "No proposals."));
  return h("div", { class: "card order-detail" },
    h("h2", {}, "Order ", statusBadge(o.status)),
    h("h3", {}, "Contact"), dl([["Name", o.customer.full_name], ["Email", o.customer.email], ["Phone", o.customer.phone]]),
    h("h3", {}, "Event"), dl([["Type", ev.event_type], ["Date", ev.event_date], ["Adults", ev.adults], ["Children", ev.children],
      ["Vegetarian guests (within total)", ev.vegetarian_guests], ["Vegan guests (within total)", ev.vegan_guests],
      ["Restricted-diet guests (within total)", ev.restricted_guests], ["Dietary notes", ev.dietary_notes]]),
    h("h3", {}, "Fulfillment"), dl([["Type", o.fulfillment_type], ["Requested time", o.requested_at], ["Address", o.delivery_address]]),
    h("h3", {}, "Items"),
    h("div", { class: "table-wrap" }, h("table", {}, h("tbody", {}, ...o.items.map((i) => h("tr", {},
      h("td", {}, i.name),
      h("td", {}, `${i.quantity} × ${money(i.unit_price, o.currency)}${i.unit ? ` (${i.unit})` : ""}`),
      h("td", {}, money(i.line_total, o.currency))))))),
    o.warnings?.includes("mixes_meat_dairy") ? h("p", { class: "notice", role: "note" }, "Order mixes meat and dairy dishes") : null,
    dl([...(o.delivery_km != null ? [["Distance", `${Number(o.delivery_km)} km`]] : []), ["Subtotal", money(o.subtotal, o.currency)],
      ["Delivery fee", o.delivery_fee == null ? (o.delivery_fee_estimated ? "To be confirmed (address not found)" : "—")
        : o.delivery_fee_estimated ? `${money(o.delivery_fee, o.currency)} (estimate)` : money(o.delivery_fee, o.currency)],
      ["Total", money(o.total, o.currency)]]),
    h("p", { class: "hint" }, "Prices include VAT."),
    h("h3", {}, "Assistant"), assistant,
    o.status === "pending_approval"
      ? h("div", {}, h("label", {}, "Note (optional, up to 1000 characters)", note), actions)
      : o.decided_at ? h("div", {}, h("h3", {}, "Decision"), dl([["Decided at", o.decided_at], ["Note", o.decision_note]])) : null,
    o.status === "pending_approval" || o.status === "approved"
      ? h("div", {}, h("h3", {}, "Cancel order"), h("label", {}, "Reason (required, shown to the customer, up to 1000 characters)", why), cancelBox) : null,
    o.cancelled_at ? h("div", {}, h("h3", {}, "Cancellation"), dl([["Cancelled at", o.cancelled_at], ["Cancellation note", o.cancel_note]])) : null);
}

// ---- serving rules
async function showRules(tabs) {
  const [cats, rules] = await Promise.all([api("/api/admin/categories"), api("/api/admin/quantity-rules")]);
  const byCat = new Map(rules.map((r) => [r.category_id, r]));
  const rows = cats.filter((c) => c.is_active).map((c) => {
    const rule = byCat.get(c.id);
    const num = (name, v, min) => h("input", { type: "number", name, min, step: "0.001", required: true, value: v ?? "", "aria-label": name });
    const pa = num("per_adult", rule?.per_adult, "0"), pc = num("per_child", rule?.per_child, "0"), rs = num("round_step", rule?.round_step, "0.001");
    const save = () => run(async () => {
      if (!(Number(rs.value) > 0) || pa.value === "" || pc.value === "") throw new Error("Fill all three values; round step must be above 0.");
      await api(`/api/admin/quantity-rules/${c.id}`, { method: "PUT",
        body: JSON.stringify({ per_adult: pa.value, per_child: pc.value, round_step: rs.value }) });
      await showRules(tabs); say("Rule saved.");
    });
    const remove = () => run(async () => { await api(`/api/admin/quantity-rules/${c.id}`, { method: "DELETE" }); await showRules(tabs); say("Rule removed."); });
    return h("tr", {}, h("td", {}, c.name_en || c.name_he), h("td", {}, pa), h("td", {}, pc), h("td", {}, rs),
      h("td", {}, rule ? "Set" : "No rule"),
      h("td", { class: "actions" }, h("button", { type: "button", class: "primary", onclick: save }, "Save"),
        rule ? h("button", { type: "button", class: "danger", onclick: remove }, "Remove") : null));
  });
  app.replaceChildren(tabs, h("section", {}, h("h2", {}, "Serving rules"),
    h("p", {}, "How much to prepare per adult and per child, in the dish's own unit (tray/kg/item). Selected dishes in a category share it evenly; suggestions round up. Without a rule, customers get no suggested quantity."),
    h("div", { class: "card" }, h("div", { class: "table-wrap" }, h("table", {},
      h("thead", {}, h("tr", {}, ...["Category", "Per adult", "Per child", "Round step", "Rule", ""].map((c) => h("th", {}, c)))),
      h("tbody", {}, ...rows))))));
}

// ---- settings
async function showSettings(tabs) {
  const st = await api("/api/admin/settings");
  const f = (name, label, unit, attrs) => [name, h("label", {}, `${label} (${unit})`, h("input", { name, required: true, value: st[name] ?? "", ...attrs }))];
  const num = (name, label, unit, max) => f(name, label, unit, { type: "number", min: "0", step: name === "lead_time_days" ? "1" : "0.01", ...(max ? { max } : {}) });
  const fields = Object.fromEntries([num("lead_time_days", "Notice needed", "days", "365"), num("min_food_total", "Food minimum", "₪"),
    num("delivery_base_fee", "Delivery base fee", "₪"), num("delivery_per_km", "Per km", "₪"), num("delivery_max_km", "Max distance", "km", "500"),
    f("kitchen_address", "Kitchen address", "text", { type: "text", maxlength: 300 })]);
  const form = h("form", { class: "card", onsubmit: (ev) => {
    ev.preventDefault();
    run(async () => {
      const body = {};
      for (const [k, label] of Object.entries(fields)) body[k] = label.querySelector("input").value.trim();
      body.lead_time_days = Number(body.lead_time_days);
      await api("/api/admin/settings", { method: "PUT", body: JSON.stringify(body) });
      await showSettings(tabs); say("Settings saved.");
    });
  } }, ...Object.values(fields),
    h("p", { class: "hint" }, `Located at ${st.kitchen_lat}, ${st.kitchen_lon}`),
    h("button", { class: "primary", type: "submit" }, "Save"));
  app.replaceChildren(tabs, h("section", {}, h("h2", {}, "Settings"), form));
}

// ---- shell
async function showDashboard() {
  state.config ??= await api("/api/public-config");
  const tabs = h("nav", { "aria-label": "Sections" });
  const open = (key) => run(async () => {
    for (const b of tabs.children) b.setAttribute("aria-pressed", String(b.dataset.key === key));
    if (key === "orders") await showOrders(tabs);
    else if (key === "serving-rules") await showRules(tabs);
    else if (key === "settings") await showSettings(tabs);
    else await showResource(key, tabs);
  });
  for (const [key, cfg] of Object.entries(RESOURCES)) {
    if (key === "delivery-zones") continue; // replaced by distance-based fees in Settings
    tabs.append(h("button", { type: "button", "data-key": key, "aria-pressed": "false", onclick: () => open(key) }, cfg.title));
  }
  for (const [key, title] of [["orders", "Orders"], ["serving-rules", "Serving rules"], ["settings", "Settings"]]) {
    tabs.append(h("button", { type: "button", "data-key": key, "aria-pressed": "false", onclick: () => open(key) }, title));
  }
  tabs.append(h("button", { type: "button", onclick: () => logout() }, "Log out"));
  app.replaceChildren(tabs);
  await open("orders");
}

if (auth.get()) run(showDashboard); else showLogin();
