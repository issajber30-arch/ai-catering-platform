// Tiny hyperscript helper. Builds DOM with textContent only, never innerHTML,
// so user-supplied or API-supplied strings cannot inject markup.
const PROPERTY_ATTRS = new Set(["value", "checked", "disabled", "selected", "hidden", "required"]);

export function h(tag, props = {}, ...children) {
  const el = document.createElement(tag);
  for (const [key, val] of Object.entries(props ?? {})) {
    if (val === false || val == null) continue;
    if (key === "class") el.className = val;
    else if (key === "text") el.textContent = val;
    else if (key.startsWith("on") && typeof val === "function") el.addEventListener(key.slice(2).toLowerCase(), val);
    else if (PROPERTY_ATTRS.has(key)) el[key] = val;
    else el.setAttribute(key, val === true ? "" : val);
  }
  append(el, children);
  return el;
}

function append(el, children) {
  for (const child of children.flat(Infinity)) {
    if (child == null || child === false) continue;
    el.append(child instanceof Node ? child : document.createTextNode(String(child)));
  }
}

export function icon(name, label) {
  const el = h("span", { class: `icon icon-${name}` });
  if (label) {
    el.setAttribute("role", "img");
    el.setAttribute("aria-label", label);
  } else {
    el.setAttribute("aria-hidden", "true");
  }
  return el;
}

export function clear(el) {
  el.replaceChildren();
  return el;
}

export function debounce(fn, ms) {
  let t;
  return (...args) => {
    clearTimeout(t);
    t = setTimeout(() => fn(...args), ms);
  };
}

/** Replace an element's children. Unlike Element.replaceChildren it flattens arrays and skips null/false. */
export function fill(el, ...children) {
  el.replaceChildren();
  append(el, children);
  return el;
}
