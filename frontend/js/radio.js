// Team-radio sound: opt-in (muted by default), Web Audio only, no assets.
import { h, svg } from "/js/dom.js";

const KEY = "ck-radio";
let ctx = null;
const toggles = new Set(); // { btn, sync } for each rendered toggle

export function isOn() {
  try { return localStorage.getItem(KEY) === "on"; } catch { return false; }
}
export function setOn(on) {
  try { localStorage.setItem(KEY, on ? "on" : "off"); } catch { /* sound stays per-session off */ }
  // Re-renders replace toggles; forget the ones no longer on the page.
  for (const t of toggles) if (t.btn.isConnected) t.sync(); else toggles.delete(t);
}

// One tone: sine with a 10ms attack / 30ms release so it never clicks. Callers are user-gesture handlers.
function tone(freq, start, dur) {
  const o = ctx.createOscillator(), g = ctx.createGain(), t = ctx.currentTime + start;
  o.frequency.value = freq;
  g.gain.setValueAtTime(0.0001, t);
  g.gain.linearRampToValueAtTime(0.08, t + 0.01);
  g.gain.setValueAtTime(0.08, t + dur - 0.03);
  g.gain.linearRampToValueAtTime(0.0001, t + dur);
  o.connect(g).connect(ctx.destination);
  o.start(t); o.stop(t + dur + 0.01);
}
function play(notes) {
  if (!isOn()) return;
  try {
    // Created lazily on the first beep, which only ever follows a click/key (or a poll after the user already opted in by clicking).
    ctx ??= new (window.AudioContext || window.webkitAudioContext)();
    if (ctx.state === "suspended") ctx.resume().catch(() => {});
    notes.forEach(([f, s, d]) => tone(f, s, d));
  } catch { /* no audio support */ }
}
export const beep = () => play([[1000, 0, 0.2]]);
export const chirp = () => play([[1000, 0, 0.08], [1500, 0.11, 0.1]]);

export function muteToggle(labels = {}) {
  const { on: onText = "RADIO ON", off: offText = "MUTE RADIO", aria = "Mute Radio" } = labels;
  const text = h("span", { class: "radio-text label", dir: "ltr" });
  const wave = svg("path", { d: "M16 9a4 4 0 0 1 0 6M19 6a8 8 0 0 1 0 12", class: "radio-wave" });
  const icon = svg("svg", { viewBox: "0 0 24 24", width: 18, height: 18, fill: "none", stroke: "currentColor", "stroke-width": 2, "stroke-linecap": "round", "stroke-linejoin": "round", "aria-hidden": "true" },
    svg("path", { d: "M4 9v6h4l5 4V5L8 9z" }), wave);
  const btn = h("button", { type: "button", class: "radio-toggle", role: "switch", "aria-label": aria });
  const sync = () => {
    const on = isOn();
    btn.setAttribute("aria-checked", String(on));
    btn.classList.toggle("on", on);
    text.textContent = on ? onText : offText;
  };
  btn.append(icon, text);
  btn.addEventListener("click", () => { setOn(!isOn()); if (isOn()) beep(); });
  toggles.add({ btn, sync }); // keeps several toggles in step
  sync();
  return btn;
}
