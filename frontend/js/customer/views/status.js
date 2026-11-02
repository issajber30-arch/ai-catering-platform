// C5: quotation status. A pending quotation is never presented as a confirmed booking.
import { fill, h, icon } from "../../lib/dom.js";
import { fmtDate, fmtMoney } from "../../lib/format.js";
import { illustration } from "../../lib/illustrations.js";
import { confetti } from "../../lib/motion.js";
import { getState, startOver } from "../store.js";

const VIEW = {
  pending_approval: {
    badge: ["badge-warning", "ממתין לאישור העסק"],
    icon: "clock-countdown",
    title: "הבקשה נשלחה לעסק",
    text: "זו בקשה להצעת מחיר ולא הזמנה מאושרת. נעדכן אתכם כשהעסק יחליט.",
  },
  approved: {
    badge: ["badge-green", "אושרה על ידי העסק"],
    icon: "seal-check",
    title: "ההזמנה אושרה",
    text: "העסק אישר את ההזמנה במחיר שמופיע למטה.",
  },
  rejected: {
    badge: ["badge-danger", "נדחתה על ידי העסק"],
    icon: "seal-warning",
    title: "הבקשה לא אושרה",
    text: "העסק לא יכול לספק את ההזמנה כפי שהוגשה.",
  },
};

const TRACK = [
  ["נשלחה", () => true],
  ["בבדיקת העסק", (s) => s === "pending_approval"],
  ["החלטת העסק", (s) => s === "approved" || s === "rejected"],
];

export function mountStatus(root) {
  const { order } = getState();
  const view = VIEW[order.status] ?? VIEW.pending_approval;
  const snap = order.snapshot;
  const e = order.event;

  const activeIndex = order.status === "pending_approval" ? 1 : 2;

  fill(root, 
    h("section", { class: `status-hero is-${order.status}`, "aria-labelledby": "status-title" },
      // The celebrating mascot acknowledges that the request was SENT. The status text and badge beside it
      // always say it is still awaiting the business's decision; it is never shown for approved or rejected.
      order.status === "pending_approval"
        ? illustration("mascot-celebrating", { alt: "", cls: "status-mascot" })
        : h("span", { class: "status-icon" }, icon(view.icon)),
      h("div", { class: "stack" },
        h("p", { class: `badge ${view.badge[0]}`, role: "status" },
          order.status === "pending_approval" ? icon("clock-countdown") : null, view.badge[1]),
        h("h1", { id: "status-title", class: "page-title", text: view.title }),
        h("p", { class: "page-lead", text: view.text }),
      ),
    ),

    h("ol", { class: "track", "aria-label": "התקדמות הבקשה" },
      TRACK.map(([label], i) => h("li", { class: `track-item${i < activeIndex ? " done" : ""}${i === activeIndex ? " now" : ""}`, "aria-current": i === activeIndex ? "step" : null },
        h("span", { class: "track-dot" }, i < activeIndex ? icon("check") : String(i + 1)),
        h("span", { text: label })))),

    order.ownerNote
      ? h("section", { class: "callout", "aria-label": "הודעה מהעסק" }, icon("info"),
        h("div", {}, h("strong", { text: "הודעה מהעסק" }), h("p", { text: order.ownerNote })))
      : null,

    h("section", { class: "panel stack", "aria-labelledby": "snap-title" },
      h("h2", { id: "snap-title", text: "פירוט הבקשה" }),
      h("p", { class: "muted", text: `${e.type}, ${fmtDate(e.date)}, ${e.slot}` }),
      h("ul", { class: "lines" }, snap.lines.map((l) => h("li", { class: "line line-static" },
        h("div", { class: "line-info" }, h("strong", { text: l.name }), h("span", { class: "muted small", text: l.qty })),
        h("strong", { class: "num", text: fmtMoney(l.lineTotal) })))),
      h("div", { class: "totals" },
        h("div", { class: "total-row" }, h("span", { text: "סכום ביניים" }), h("span", { class: "num", text: fmtMoney(snap.subtotal) })),
        h("div", { class: "total-row" }, h("span", { text: e.fulfillment === "delivery" ? "דמי משלוח" : "איסוף עצמי" }), h("span", { class: "num", text: fmtMoney(snap.deliveryFee ?? 0) })),
        h("div", { class: "total-row grand" }, h("span", { text: "סה״כ" }), h("strong", { class: "num", text: fmtMoney(snap.total) }))),
      h("p", { class: "muted small", text: "המחיר נקבע ברגע השליחה ולא ישתנה אם מחירי התפריט יעודכנו." }),
    ),

    order.status !== "pending_approval"
      ? h("div", { class: "form-actions" }, h("button", { class: "btn btn-primary", type: "button", onclick: startOver }, "התחלת הזמנה חדשה"))
      : null,
  );
  // Once, as the "request sent" mascot arrives right after submitting (not on later visits to this screen).
  // Keyed on the submission's snapshot, so a new order submitted after "start over" celebrates again.
  if (order.status === "pending_approval" && celebratedFor !== snap) {
    celebratedFor = snap;
    setTimeout(() => confetti(root.querySelector(".status-mascot")), 600);
  }
  return () => {};
}

let celebratedFor = null;
