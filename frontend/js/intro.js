// CaterKing first-open intro: once per tab session; tap, click or any key skips it.
(() => {
  const root = document.documentElement;
  let seen = false;
  try { seen = sessionStorage.getItem("ck-intro") === "1"; sessionStorage.setItem("ck-intro", "1"); } catch {}
  if (seen && !new URLSearchParams(location.search).has("intro")) { root.classList.add("ck-intro-off"); return; }
  root.classList.add("ck-intro-on");
  const off = () => root.classList.add("ck-intro-off");
  const done = () => root.classList.add("ck-intro-skip");
  addEventListener("keydown", done, { once: true });
  addEventListener("pointerdown", done, { once: true });
  const end = (e) => { if (e.target.id === "ck-intro" && e.animationName.startsWith("ck-out")) off(); };
  addEventListener("animationend", end);
  addEventListener("animationcancel", end);
  setTimeout(off, 3500); // never leave the overlay up, even if CSS or animations fail
})();
