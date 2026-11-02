// Screen-reader announcements for changes that have no focus move (totals, applied proposals).
let timer;

export function announce(message) {
  const region = document.getElementById("announce");
  if (!region) return;
  region.textContent = "";
  clearTimeout(timer);
  // Clearing first makes repeated identical messages announce again.
  timer = setTimeout(() => (region.textContent = message), 50);
}
