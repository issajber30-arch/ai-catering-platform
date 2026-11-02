import { fill, h, icon } from "../../lib/dom.js";
import { canEnter, getState, goto } from "../store.js";

const LABELS = [
  ["event", "פרטי האירוע"],
  ["menu", "תפריט"],
  ["summary", "סיכום"],
  ["status", "שליחה"],
];

export function renderStepper(container) {
  const { step, order } = getState();
  const currentIndex = LABELS.findIndex(([id]) => id === step);
  const locked = order.status !== "draft";
  fill(container, 
    h("ol", { class: "stepper" },
      LABELS.map(([id, label], i) => {
        const done = locked ? id !== "status" : i < currentIndex;
        const current = id === step;
        const reachable = !current && canEnter(id) && (done || id !== "status");
        const content = [
          h("span", { class: "stepper-mark" }, done ? icon("check") : String(i + 1)),
          h("span", { class: "stepper-label", text: label }),
        ];
        return h("li", { class: `stepper-item${current ? " is-current" : ""}${done ? " is-done" : ""}` },
          reachable
            ? h("button", { class: "stepper-btn", type: "button", onclick: () => goto(id) }, content)
            : h("span", { class: "stepper-btn", "aria-current": current ? "step" : null }, content),
        );
      }),
    ),
  );
}
