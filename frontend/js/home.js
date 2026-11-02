import { STRINGS, LANGS } from "/js/home-i18n.js";

function pick() {
  let l = new URLSearchParams(location.search).get("lang");
  if (!Object.hasOwn(LANGS, l ?? "")) { try { l = localStorage.getItem("ck-lang"); } catch {} }
  return Object.hasOwn(LANGS, l ?? "") ? l : "he";
}

function apply(lang, remember) {
  const s = STRINGS[lang];
  const root = document.documentElement;
  root.lang = lang; root.dir = LANGS[lang];
  document.title = s.title;
  document.querySelector('meta[name="description"]').setAttribute("content", s.desc);
  for (const el of document.querySelectorAll("[data-t]")) el.textContent = s[el.dataset.t];
  for (const b of document.querySelectorAll("[data-lang]")) {
    if (b.dataset.lang === lang) b.setAttribute("aria-current", "true"); else b.removeAttribute("aria-current");
  }
  if (remember) { try { localStorage.setItem("ck-lang", lang); } catch {} }
}

for (const b of document.querySelectorAll("[data-lang]")) b.addEventListener("click", () => apply(b.dataset.lang, true));
apply(pick(), false);
