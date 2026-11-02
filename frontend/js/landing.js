// Landing page behaviour: scroll reveal, header shadow, gentle pointer parallax on the hero art, and a
// clickable example of the assistant's approval card (it demonstrates the rule that nothing changes until
// the customer approves). No data leaves the page.
import { fmtMoney } from "./lib/format.js";
import { confetti, reduced, reveal, tweenNumber } from "./lib/motion.js";

// Scroll reveal, with a small stagger inside groups.
document.querySelectorAll(".occasions li, .steps li").forEach((el, i) => el.style.setProperty("--i", i % 6));
reveal(document.querySelectorAll(".reveal"));

// Header gets a shadow once the page has scrolled.
const header = document.querySelector(".top");
if (header && "IntersectionObserver" in window) {
  const sentinel = document.createElement("span");
  sentinel.setAttribute("aria-hidden", "true");
  sentinel.style.cssText = "position:absolute;top:0;left:0;width:1px;height:1px;pointer-events:none";
  document.body.prepend(sentinel);
  new IntersectionObserver(([entry]) => header.classList.toggle("is-stuck", !entry.isIntersecting)).observe(sentinel);
}

// Hero art drifts a few pixels toward the pointer. Fine pointers only; never when motion is reduced.
const art = document.querySelector(".hero-art");
if (art && matchMedia("(pointer: fine)").matches && !reduced()) {
  let frame = 0;
  document.querySelector(".hero")?.addEventListener("pointermove", (e) => {
    cancelAnimationFrame(frame);
    frame = requestAnimationFrame(() => {
      const r = art.getBoundingClientRect();
      art.style.setProperty("--px", ((e.clientX - r.left) / r.width - 0.5).toFixed(3));
      art.style.setProperty("--py", ((e.clientY - r.top) / r.height - 0.5).toFixed(3));
    });
  });
  document.querySelector(".hero")?.addEventListener("pointerleave", () => {
    art.style.setProperty("--px", "0");
    art.style.setProperty("--py", "0");
  });
}

// Example proposal: approve, reject, or start over.
const demo = document.getElementById("demo-proposal");
if (demo) {
  const $ = (id) => document.getElementById(id);
  const actions = $("demo-actions");
  const done = $("demo-done");
  const note = $("demo-note");
  const totalLine = $("demo-total");
  const totalNum = $("demo-total-n");
  const avatar = $("demo-avatar");
  const BEFORE = 1200;
  const AFTER = 1350;

  const settle = (applied) => {
    actions.hidden = true;
    done.hidden = false;
    totalLine.hidden = false;
    avatar.hidden = !applied;
    demo.classList.toggle("is-applied", applied);
    demo.classList.toggle("is-rejected", !applied);
    note.className = `badge ${applied ? "badge-green" : ""}`;
    note.textContent = applied ? "השינוי הוחל בהזמנה" : "השינוי נדחה. ההזמנה נשארה כמו שהייתה.";
    tweenNumber(totalNum, BEFORE, applied ? AFTER : BEFORE, fmtMoney);
    if (applied) confetti(avatar);
    $("demo-reset").focus();
  };

  $("demo-approve").addEventListener("click", () => settle(true));
  $("demo-reject").addEventListener("click", () => settle(false));
  $("demo-reset").addEventListener("click", () => {
    demo.classList.remove("is-applied", "is-rejected");
    done.hidden = true;
    totalLine.hidden = true;
    actions.hidden = false;
    $("demo-approve").focus();
  });
}
