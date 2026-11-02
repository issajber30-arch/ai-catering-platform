import { h } from "../../lib/dom.js";
import { illustration } from "../../lib/illustrations.js";

/**
 * Round mascot avatar: a cropped view of the character's hat and face, used as the assistant's identity.
 * Purely decorative (aria-hidden, alt=""): every message and control carries its meaning in text, and the
 * mascot never sits on, or changes, the approve and reject controls.
 * States: welcome, thinking, suggesting, explaining, celebrating.
 */
export function mascotAvatar(state, { size = 40, cls = "" } = {}) {
  return h("span", { class: `mascot-avatar ${cls}`.trim(), style: `--avatar:${size}px`, "aria-hidden": "true" },
    illustration(`mascot-${state}`, { alt: "" }));
}
