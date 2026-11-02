// Motion helpers. Every effect here is feedback or arrival (a number changing, a change applied, a section
// coming into view), never decoration, and every one of them does nothing when the visitor prefers reduced motion.

export const reduced = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false;

/** Animate a number in `el` from `from` to `to`. The final value is always exact. */
export function tweenNumber(el, from, to, format, ms = 450) {
  cancelAnimationFrame(el._raf);
  if (reduced() || from === to || !Number.isFinite(from)) {
    el.textContent = format(to);
    return;
  }
  const start = performance.now();
  const ease = (t) => 1 - (1 - t) ** 3;
  const frame = (now) => {
    if (!el.isConnected) return; // the caller re-rendered and replaced this element; stop tweening it
    const t = Math.min(1, (now - start) / ms);
    if (t < 1) {
      el.textContent = format(Math.round(from + (to - from) * ease(t)));
      el._raf = requestAnimationFrame(frame);
    } else {
      el.textContent = format(to);
    }
  };
  el._raf = requestAnimationFrame(frame);
}

/**
 * A money amount that animates for sighted users while screen readers get only the final value once:
 * the tweening text is aria-hidden and a visually hidden copy holds the real number.
 */
export function animatedAmount(value, previous, format, cls = "num") {
  const live = document.createElement("span");
  live.setAttribute("aria-hidden", "true");
  live.textContent = format(previous ?? value);
  const real = document.createElement("span");
  real.className = "visually-hidden";
  real.textContent = format(value);
  const wrap = document.createElement("strong");
  wrap.className = cls;
  wrap.append(live, real);
  tweenNumber(live, previous ?? value, value, format);
  return wrap;
}

const COLORS = ["#F0442D", "#FFD65A", "#82B441", "#3F702B", "#8AD8FF"];

/** A short burst of confetti from the centre of `anchor`. Skipped for reduced motion. */
export function confetti(anchor) {
  if (reduced() || !anchor?.isConnected) return;
  const parent = anchor.offsetParent ?? document.body;
  const a = anchor.getBoundingClientRect();
  const p = parent.getBoundingClientRect();
  const box = document.createElement("span");
  box.className = "confetti";
  box.setAttribute("aria-hidden", "true");
  box.style.left = `${a.left - p.left + a.width / 2}px`;
  box.style.top = `${a.top - p.top + a.height / 2}px`;
  for (let i = 0; i < 18; i++) {
    const piece = document.createElement("i");
    const angle = (Math.PI * 2 * i) / 18 + Math.random() * 0.4;
    const dist = 50 + Math.random() * 50;
    piece.style.setProperty("--dx", `${Math.cos(angle) * dist}px`);
    piece.style.setProperty("--dy", `${Math.sin(angle) * dist - 18}px`);
    piece.style.setProperty("--rot", `${Math.random() * 540 - 270}deg`);
    piece.style.setProperty("--c", COLORS[i % COLORS.length]);
    box.append(piece);
  }
  parent.append(box);
  setTimeout(() => box.remove(), 1200);
}

/**
 * One-shot class animation: restarts `cls` on `el` and removes it once every CSS animation it started, on `el`
 * or on its descendants (the step "enter" animates the children), has finished.
 */
export function play(el, cls) {
  if (reduced()) return;
  el.classList.remove(cls);
  void el.offsetWidth; // restart the animation
  el.classList.add(cls);
  const token = (el._playToken = {});
  const running = el.getAnimations({ subtree: true }).filter((a) => a instanceof CSSAnimation && a.effect?.getComputedTiming().iterations !== Infinity);
  Promise.allSettled(running.map((a) => a.finished)).then(() => {
    if (el._playToken === token) el.classList.remove(cls); // a newer play() on the same element owns the class now
  });
}

/** Reveal elements as they scroll into view (adds `.in`). Visible immediately when motion is reduced. */
export function reveal(elements) {
  const els = [...elements];
  if (reduced() || !("IntersectionObserver" in window)) {
    els.forEach((e) => e.classList.add("in"));
    return;
  }
  const io = new IntersectionObserver((entries) => {
    for (const entry of entries) {
      if (entry.isIntersecting) {
        entry.target.classList.add("in");
        io.unobserve(entry.target);
      }
    }
  }, { rootMargin: "0px 0px -8% 0px", threshold: 0.12 });
  els.forEach((e) => io.observe(e));
}
