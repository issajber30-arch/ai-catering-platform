// C1: event configuration.
import { fill, h, icon } from "../../lib/dom.js";
import { fmtDate, fmtMoney, fmtNumber } from "../../lib/format.js";
import {
  EVENT_TYPES, ZONES, blockedDates, minEventDate, slotsFor, totalGuests, validateEvent,
} from "../mock-backend.js";
import { illustration, OCCASION_ART } from "../../lib/illustrations.js";
import { counter } from "../components/counter.js";
import { getState, goto, setEvent } from "../store.js";

export function mountEvent(root) {
  const ev = () => getState().order.event;
  let attempted = false;
  const fields = {}; // name -> { wrap, error }

  function field(name, labelText, control, { hint, hintId } = {}) {
    const errorId = `err-${name}`;
    const error = h("p", { class: "error", id: errorId, hidden: true });
    const wrap = h("div", { class: "field" },
      h("label", { for: control.id, text: labelText }),
      control,
      hint ? h("p", { class: "hint", id: hintId, text: hint }) : null,
      error,
    );
    control.setAttribute("aria-describedby", [hint ? hintId : null, errorId].filter(Boolean).join(" "));
    fields[name] = { wrap, error, control };
    return wrap;
  }

  /* ----- basics ----- */
  // Occasion picker: real radio inputs wrapped in illustrated cards. The art is decorative (alt="");
  // the visible label is the accessible name, so the choice works with images disabled.
  const typeError = h("p", { class: "error", id: "err-type", hidden: true });
  const typeGroup = h("fieldset", { class: "occasion-grid", "aria-describedby": "err-type" },
    h("legend", { class: "visually-hidden", text: "סוג האירוע" }),
    EVENT_TYPES.map((t, i) => {
      const input = h("input", { type: "radio", name: "event-type", value: t, id: `f-type-${i}`, checked: ev().type === t });
      input.addEventListener("change", () => update({ type: t }));
      return h("label", { class: "occasion" }, input,
        h("span", { class: "occasion-body" },
          illustration(OCCASION_ART[t] ?? "occasion-other", { alt: "", cls: "occasion-art" }),
          h("strong", { text: t })));
    }));
  fields.type = { wrap: typeGroup, error: typeError, control: typeGroup.querySelector("input") };

  const date = h("input", { id: "f-date", class: "input", type: "date", min: minEventDate(), value: ev().date, required: true });
  date.addEventListener("change", () => update({ date: date.value }));

  const slot = h("select", { id: "f-slot", class: "input", required: true });
  slot.addEventListener("change", () => update({ slot: slot.value }));

  const closed = blockedDates().map(fmtDate).join(", ");

  /* ----- guests ----- */
  const total = h("p", { class: "total-line", "aria-live": "polite" });
  const guestCounters = {};
  function guestField(name, labelText, hint, opts = {}) {
    const id = `f-${name}`;
    const c = counter({ id, value: ev()[name], min: opts.min ?? 0, onChange: (n) => update({ [name]: n }), describedBy: `${id}-hint` });
    guestCounters[name] = c;
    return h("div", { class: "field" },
      h("label", { for: id, text: labelText }),
      c.el,
      h("p", { class: "hint", id: `${id}-hint`, text: hint }),
    );
  }
  const dietaryError = h("p", { class: "error", id: "err-dietary", hidden: true });
  const adultsError = h("p", { class: "error", id: "err-adults", hidden: true });

  const notes = h("textarea", { id: "f-notes", class: "input", rows: "3", text: ev().notes, placeholder: "למשל: אורח עם רגישות לאגוזים, בקשה מיוחדת" });
  notes.addEventListener("input", () => update({ notes: notes.value }, { quiet: true }));

  /* ----- fulfillment ----- */
  function option(value, labelText, ic, hintText) {
    const input = h("input", { type: "radio", name: "fulfillment", value, checked: ev().fulfillment === value });
    input.addEventListener("change", () => update({ fulfillment: value, slot: "" }));
    return h("label", { class: "choice" }, input,
      h("span", { class: "choice-body" }, icon(ic), h("span", {}, h("strong", { text: labelText }), h("span", { class: "muted small", text: hintText }))));
  }

  const city = h("select", { id: "f-city", class: "input" },
    h("option", { value: "", text: "בחרו עיר" }),
    ZONES.map((z) => h("option", { value: z.city, text: z.city, selected: ev().city === z.city })));
  city.addEventListener("change", () => update({ city: city.value }));
  const address = h("input", { id: "f-address", class: "input", type: "text", autocomplete: "street-address", value: ev().address });
  address.addEventListener("input", () => update({ address: address.value }, { quiet: true }));
  const feeLine = h("p", { class: "fee-line", "aria-live": "polite" });

  const deliveryBox = h("div", { class: "grid-2 delivery-fields" },
    field("city", "עיר", city),
    field("address", "רחוב ומספר בית", address),
    feeLine,
  );

  const continueBtn = h("button", { class: "btn btn-primary", type: "submit" }, "המשך לתפריט", icon("arrow-left"));

  const form = h("form", { class: "stack-lg", novalidate: true, onsubmit: onSubmit },
    h("section", { class: "panel stack" },
      h("h2", { text: "איזה אירוע מתכננים?" }),
      typeGroup,
      typeError,
    ),
    h("section", { class: "panel stack" },
      h("h2", { text: "מתי?" }),
      h("div", { class: "grid-2" },
        field("date", "תאריך", date, { hint: `תאריכים סגורים להזמנות: ${closed}`, hintId: "hint-date" }),
        field("slot", "שעת איסוף או משלוח", slot),
      ),
    ),
    h("section", { class: "panel stack" },
      h("h2", { text: "האורחים" }),
      h("div", { class: "grid-2" },
        h("div", {}, guestField("adults", "מבוגרים", "מגיל 13 ומעלה", { min: 0 }), adultsError),
        guestField("children", "ילדים", "עד גיל 12, נחשבים כחצי מנה"),
      ),
      h("fieldset", { class: "stack" },
        h("legend", { class: "label", text: "הגבלות תזונתיות" }),
        // OPEN_DECISIONS #4: these are treated as a subset of all guests until the business decides.
        h("p", { class: "hint", text: "כמה מהאורחים הכוללים צריכים כל אחת מההגבלות?" }),
        h("div", { class: "grid-3" },
          guestField("vegetarian", "צמחונים", "לא אוכלים בשר ודגים"),
          guestField("vegan", "טבעונים", "לא אוכלים מוצרים מהחי"),
          guestField("restricted", "הגבלה אחרת", "למשל אלרגיה או צליאק"),
        ),
        dietaryError,
      ),
      total,
      field("notes", "הערות תזונה", notes, { hint: "אופציונלי. נעביר את זה לעסק כמו שהוא.", hintId: "hint-notes" }),
    ),
    h("section", { class: "panel stack" },
      h("h2", { text: "איסוף או משלוח" }),
      h("fieldset", { class: "choice-row" },
        h("legend", { class: "visually-hidden", text: "אופן קבלת ההזמנה" }),
        option("pickup", "איסוף עצמי", "storefront", "מהעסק, בשעה שתבחרו"),
        option("delivery", "משלוח", "moped", "לכתובת האירוע, בתוספת דמי משלוח"),
      ),
      deliveryBox,
    ),
    h("div", { class: "form-actions" }, continueBtn),
  );

  fill(root,
    h("div", { class: "page-head" },
      h("div", {},
        h("h1", { class: "page-title", text: "ספרו לנו על האירוע" }),
        h("p", { class: "page-lead muted", text: "הפרטים האלה קובעים את הכמויות המומלצות ואת המחיר." })),
      // The mascot greets here once and never sits over a form field; hidden on narrow screens.
      illustration("mascot-welcome", { alt: "", cls: "page-mascot", eager: true })),
    form,
  );

  /* ----- behavior ----- */
  function update(patch, { quiet = false } = {}) {
    setEvent(patch);
    if (!quiet) refresh();
    else refreshDerived();
  }

  function showError(name, message) {
    const f = fields[name];
    if (!f) return;
    f.wrap.classList.toggle("invalid", Boolean(message));
    f.control.setAttribute("aria-invalid", message ? "true" : "false");
    f.error.hidden = !message;
    fill(f.error, ...(message ? [icon("warning"), message] : []));
  }

  function showSimpleError(el, message) {
    el.hidden = !message;
    fill(el, ...(message ? [icon("warning"), message] : []));
  }

  function refreshDerived() {
    const e = ev();
    total.textContent = `סה״כ ${fmtNumber(totalGuests(e))} אורחים`;
    const delivery = e.fulfillment === "delivery";
    deliveryBox.hidden = !delivery;
    const zone = ZONES.find((z) => z.city === e.city);
    feeLine.textContent = delivery && zone ? `דמי משלוח ל${zone.city}: ${fmtMoney(zone.fee)}` : "";
    if (attempted) showErrors(validateEvent(e));
  }

  function refresh() {
    const e = ev();
    const slots = slotsFor(e.fulfillment);
    if (e.slot && !slots.includes(e.slot)) setEvent({ slot: "" });
    fill(slot, 
      h("option", { value: "", text: "בחרו חלון זמן" }),
      slots.map((s) => h("option", { value: s, text: s, selected: ev().slot === s })),
    );
    refreshDerived();
  }

  function showErrors(errors) {
    for (const name of ["type", "date", "slot", "city", "address"]) showError(name, errors[name]);
    showSimpleError(adultsError, errors.adults);
    guestCounters.adults.input.setAttribute("aria-invalid", errors.adults ? "true" : "false");
    showSimpleError(dietaryError, errors.dietary);
  }

  function onSubmit(e) {
    e.preventDefault();
    attempted = true;
    const errors = validateEvent(ev());
    showErrors(errors);
    const firstInvalid = form.querySelector('[aria-invalid="true"]');
    if (firstInvalid) {
      firstInvalid.focus();
      return;
    }
    goto("menu");
  }

  refresh();
  return () => {};
}
