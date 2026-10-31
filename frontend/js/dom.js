// Builds DOM with createElement/textContent; server data is never parsed as HTML.
export function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (key.startsWith("on")) el.addEventListener(key.slice(2), value);
    else if (value === true) el.setAttribute(key, "");
    else if (value !== false && value != null) el.setAttribute(key, value);
  }
  el.append(...children.flat(Infinity).filter((c) => c != null && c !== false));
  return el;
}

// SVG variant of h(): createElementNS so icons are built as DOM, never parsed from strings.
export function svg(tag, props = {}, ...children) {
  const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
  for (const [key, value] of Object.entries(props)) if (value != null && value !== false) el.setAttribute(key, value);
  el.append(...children.flat(Infinity).filter(Boolean));
  return el;
}
