import { play } from "../lib/motion.js";
import { renderStepper } from "./components/stepper.js";
import { mountChat } from "./components/chat.js";
import { EVENT_TYPES, validateEvent } from "./mock-backend.js";
import { STEPS, canEnter, getState, goto, seedDemo, setEvent, subscribe } from "./store.js";
import { mountEvent } from "./views/event.js";
import { mountMenu } from "./views/menu.js";
import { mountStatus } from "./views/status.js";
import { mountSummary } from "./views/summary.js";

const VIEWS = { event: mountEvent, menu: mountMenu, summary: mountSummary, status: mountStatus };
const TITLES = {
  event: "פרטי האירוע",
  menu: "בחירת תפריט",
  summary: "סיכום ההזמנה",
  status: "מצב הבקשה",
};

const app = document.getElementById("app");
const stepperRoot = document.getElementById("stepper");

// Design review shortcut: ?demo=pending|approved|rejected, or #demo-pending etc. when the
// page is embedded and has no query string. Never used with real data.
const demo = new URLSearchParams(location.search).get("demo") ?? location.hash.replace(/^#demo-/, "");
if (["pending", "approved", "rejected"].includes(demo)) seedDemo(demo);

// Landing-page occasion cards link here with ?occasion=<event type> to preselect it.
const occasion = new URLSearchParams(location.search).get("occasion");
if (occasion && EVENT_TYPES.includes(occasion) && getState().order.status === "draft") setEvent({ type: occasion });

let currentStep = null;
let cleanup = null;
let stepperSig = null;
let firstRender = true;

function render(state) {
  // Never show a screen the order cannot be in (e.g. a stale saved step).
  if (!canEnter(state.step, state)) {
    const fallback = state.order.status !== "draft" ? "status" : "event";
    if (state.step !== fallback) {
      goto(fallback);
      return;
    }
  }

  const sig = `${state.step}|${state.order.status}|${Object.keys(validateEvent(state.order.event)).length === 0}`;
  if (sig !== stepperSig) {
    stepperSig = sig;
    renderStepper(stepperRoot);
  }

  if (state.step === currentStep) return;
  cleanup?.();
  currentStep = state.step;
  cleanup = VIEWS[currentStep](app);
  play(app, "enter"); // each step arrives with a short rise; skipped for reduced motion
  document.title = `${TITLES[currentStep]} | yumm.ai`;

  // Assigning the hash adds a history entry and works in sandboxed frames, where pushState can throw.
  if (location.hash !== `#${currentStep}`) location.hash = currentStep;
  if (!firstRender) {
    window.scrollTo({ top: 0 });
    const heading = app.querySelector("h1");
    heading?.setAttribute("tabindex", "-1");
    heading?.focus({ preventScroll: true });
  }
  firstRender = false;
}

window.addEventListener("hashchange", () => {
  const wanted = location.hash.slice(1);
  if (STEPS.includes(wanted) && wanted !== getState().step) {
    if (!goto(wanted)) location.hash = getState().step;
  }
});

mountChat(document.getElementById("chat-root"));
subscribe(render);
render(getState());
