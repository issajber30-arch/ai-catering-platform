// Illustration manifest: key -> file base path (no extension) and intrinsic size.
// Every illustration ships as WebP with a PNG fallback. Width and height are always set on the <img>
// so the layout never shifts while images load. Decorative art uses alt="" (the nearby label is the
// accessible name); only pass a real alt when the picture carries information on its own.

const A = "/assets";
export const ART = {
  "mascot-welcome": [`${A}/mascot/welcome/mascot-welcome`, 692, 900],
  "mascot-thinking": [`${A}/mascot/thinking/mascot-thinking`, 541, 900],
  "mascot-suggesting": [`${A}/mascot/suggesting/mascot-suggesting`, 453, 900],
  "mascot-explaining": [`${A}/mascot/explaining/mascot-explaining`, 560, 900],
  "mascot-celebrating": [`${A}/mascot/celebrating/mascot-celebrating`, 654, 900],

  "occasion-birthday": [`${A}/occasions/occasion-birthday`, 900, 670],
  "occasion-family-dinner": [`${A}/occasions/occasion-family-dinner`, 900, 591],
  "occasion-bar-bat-mitzvah": [`${A}/occasions/occasion-bar-bat-mitzvah`, 900, 708],
  "occasion-shabbat": [`${A}/occasions/occasion-shabbat`, 900, 621],
  "occasion-anniversary": [`${A}/occasions/occasion-anniversary`, 900, 626],
  "occasion-celebration": [`${A}/occasions/occasion-celebration`, 900, 677],
  "occasion-garden-party": [`${A}/occasions/occasion-garden-party`, 900, 594],
  "occasion-other": [`${A}/occasions/occasion-other`, 900, 657],

  "food-main": [`${A}/menu-categories/food-main`, 723, 800],
  "food-bread": [`${A}/menu-categories/food-bread`, 663, 800],
  "food-canapes": [`${A}/menu-categories/food-canapes`, 736, 692],
  "food-dessert": [`${A}/menu-categories/food-dessert`, 625, 800],
  "food-fish": [`${A}/menu-categories/food-fish`, 717, 800],
  "food-lemonade": [`${A}/menu-categories/food-lemonade`, 476, 800],
  "food-salad": [`${A}/menu-categories/food-salad`, 763, 800],
  "food-sides": [`${A}/menu-categories/food-sides`, 689, 740],

  "decor-awning": [`${A}/decorations/decor-awning`, 480, 475],
  "decor-confetti": [`${A}/decorations/decor-confetti`, 432, 480],
  "decor-lemon": [`${A}/decorations/decor-lemon`, 480, 430],
  "decor-olives": [`${A}/decorations/decor-olives`, 309, 480],
  "decor-parsley": [`${A}/decorations/decor-parsley`, 376, 480],
  "decor-rosemary": [`${A}/decorations/decor-rosemary`, 251, 480],
  "decor-tomatoes": [`${A}/decorations/decor-tomatoes`, 432, 480],
};

// Event type (label shown to the customer) -> occasion illustration.
export const OCCASION_ART = {
  "יום הולדת": "occasion-birthday",
  "אירוע משפחתי": "occasion-family-dinner",
  "בר או בת מצווה": "occasion-bar-bat-mitzvah",
  "ארוחת שבת": "occasion-shabbat",
  "יום נישואין": "occasion-anniversary",
  "חגיגה פרטית": "occasion-celebration",
  "אחר": "occasion-other",
};

// Menu category id -> category illustration. Category headers and chips only: these are drawings of a kind
// of food, never a picture of a dish being sold (dish cards show no image unless the data supplies one).
export const CATEGORY_ART = {
  salads: "food-salad",
  mains: "food-main",
  fish: "food-fish",
  sides: "food-sides",
  desserts: "food-dessert",
  drinks: "food-lemonade",
};

/** <picture> with WebP + PNG fallback and reserved dimensions. */
export function illustration(key, { alt = "", cls = "", eager = false, height } = {}) {
  const entry = ART[key];
  if (!entry) throw new Error(`Unknown illustration: ${key}`);
  const [base, w, h] = entry;
  const source = document.createElement("source");
  source.type = "image/webp";
  source.srcset = `${base}.webp`;
  const img = document.createElement("img");
  img.src = `${base}.png`;
  img.alt = alt;
  img.width = w;
  img.height = h;
  img.decoding = "async";
  img.loading = eager ? "eager" : "lazy";
  if (!alt) img.setAttribute("aria-hidden", "true");
  if (height) img.style.height = `${height}px`;
  const picture = document.createElement("picture");
  if (cls) picture.className = cls;
  picture.append(source, img);
  return picture;
}
