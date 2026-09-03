export function demoCompareImage(group: number, index: number): string {
  const palettes = [
    ['#365f8c', '#d48a56', '#f0d7b5'],
    ['#3f775d', '#c56f53', '#e9cfa7'],
    ['#6c4c7d', '#d5a54e', '#d9d3c4'],
    ['#49646f', '#b85f68', '#e6c8a7'],
  ];
  const palette = palettes[(group + index) % palettes.length];
  const shift = (index % 5) * 11;
  const sunX = 72 + shift;
  const sunY = 52 + (index % 3) * 9;
  const treeX = 255 - shift * 1.3;
  const cloudOffset = (index % 4) * 16;
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600">
    <defs><linearGradient id="sky" x1="0" y1="0" x2="0" y2="1"><stop stop-color="${palette[0]}"/><stop offset="1" stop-color="${palette[2]}"/></linearGradient></defs>
    <rect width="800" height="600" fill="url(#sky)"/>
    <circle cx="${sunX}" cy="${sunY}" r="${42 + (index % 2) * 6}" fill="${palette[1]}" opacity=".92"/>
    <path d="M0 390 L145 ${270 + shift / 2} L270 365 L430 ${230 - shift / 3} L590 355 L720 ${245 + shift / 3} L800 315 V600 H0Z" fill="#283c45"/>
    <path d="M0 445 L180 ${355 + shift / 3} L320 430 L505 ${325 - shift / 4} L680 415 L800 360 V600 H0Z" fill="#1d2d31"/>
    <rect y="475" width="800" height="125" fill="#304a43"/>
    <rect x="${treeX}" y="350" width="18" height="145" rx="5" fill="#3a2b22"/>
    <circle cx="${treeX + 9}" cy="335" r="${78 + (index % 3) * 8}" fill="#31563d"/>
    <circle cx="${treeX - 35}" cy="350" r="54" fill="#31563d"/>
    <circle cx="${treeX + 48}" cy="350" r="48" fill="#31563d"/>
    <ellipse cx="${520 + cloudOffset}" cy="${110 + (index % 2) * 13}" rx="88" ry="24" fill="#fff" opacity=".5"/>
    <ellipse cx="${610 - cloudOffset / 2}" cy="${150 + (index % 3) * 9}" rx="58" ry="17" fill="#fff" opacity=".34"/>
    <rect x="${575 + shift / 2}" y="${400 - (index % 2) * 10}" width="88" height="62" rx="4" fill="${palette[1]}" opacity=".88"/>
    <polygon points="${565 + shift / 2},400 ${620 + shift / 2},352 ${674 + shift / 2},400" fill="#4f3a34"/>
    <rect x="${610 + shift / 2}" y="424" width="20" height="38" fill="#3a2b22"/>
  </svg>`;
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

function hslToRgb(h: number, s: number, l: number): [number, number, number] {
  h = ((h % 360) + 360) % 360;
  s /= 100;
  l /= 100;
  const c = (1 - Math.abs(2 * l - 1)) * s;
  const x = c * (1 - Math.abs((h / 60) % 2 - 1));
  const m = l - c / 2;
  let r = 0;
  let g = 0;
  let b = 0;
  if (h < 60) [r, g] = [c, x];
  else if (h < 120) [r, g] = [x, c];
  else if (h < 180) [g, b] = [c, x];
  else if (h < 240) [g, b] = [x, c];
  else if (h < 300) [r, b] = [x, c];
  else [r, b] = [c, x];
  return [r + m, g + m, b + m];
}

export function demoDifferenceMask(
  group: number,
  selectedIndex: number,
  referenceIndex: number,
  hue = 190,
  contrast = 180,
  binary = true,
): string {
  const reference = demoCompareImage(group, referenceIndex);
  const selected = demoCompareImage(group, selectedIndex);
  const [r, g, b] = hslToRgb(hue, 90, 58);

  const filter = binary
    ? `<feImage href="${reference}" result="ref"/><feImage href="${selected}" result="sel"/><feBlend in="ref" in2="sel" mode="difference" result="d"/><feColorMatrix in="d" type="matrix" values="1.9 0 0 0 0 0 1.9 0 0 0 0 0 1.9 0 0 0 0 0 1 0" result="boost"/><feComponentTransfer in="boost" result="threshold"><feFuncR type="gamma" amplitude="3.4" exponent=".6" offset="0"/><feFuncG type="gamma" amplitude="3.4" exponent=".6" offset="0"/><feFuncB type="gamma" amplitude="3.4" exponent=".6" offset="0"/></feComponentTransfer><feColorMatrix in="threshold" type="matrix" values="0 0 0 0 ${r} 0 0 0 0 ${g} 0 0 0 0 ${b} .333 .333 .333 0 0" result="selectedColor"/><feComposite in="selectedColor" in2="threshold" operator="in"/>`
    : `<feImage href="${reference}" result="ref"/><feImage href="${selected}" result="sel"/><feBlend in="ref" in2="sel" mode="difference" result="raw"/><feColorMatrix in="raw" type="matrix" values=".2126 .7152 .0722 0 0 .2126 .7152 .0722 0 0 .2126 .7152 .0722 0 0 0 0 0 1 0" result="lum"/><feComponentTransfer in="lum" result="mapped"><feFuncR type="gamma" amplitude="${Math.max(0.5, Math.min(3, contrast / 100))}" exponent=".75" offset="0"/><feFuncG type="gamma" amplitude="${Math.max(0.5, Math.min(3, contrast / 100))}" exponent=".75" offset="0"/><feFuncB type="gamma" amplitude="${Math.max(0.5, Math.min(3, contrast / 100))}" exponent=".75" offset="0"/></feComponentTransfer><feColorMatrix in="mapped" type="matrix" values="${r} 0 0 0 0 0 ${g} 0 0 0 0 0 ${b} 0 0 0 0 0 1 0"/>`;

  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="800" height="600" viewBox="0 0 800 600"><defs><filter id="diff" x="0" y="0" width="100%" height="100%" color-interpolation-filters="sRGB">${filter}</filter></defs><rect width="800" height="600" fill="#000"/><rect width="800" height="600" filter="url(#diff)"/></svg>`;
  return `data:image/svg+xml;charset=UTF-8,${encodeURIComponent(svg)}`;
}

export type ComparisonMemberData = {
  name: string;
  source: string;
  size: string;
  sizeNum: number;
  dims: string;
  taken: string;
  codec: string;
  library: string;
  uploaded: string;
  similarity: string;
};

export function comparisonMemberData(group: number, index: number): ComparisonMemberData {
  const sizes = [4.8, 5.4, 4.9, 6.1, 4.3, 5.0, 5.8, 4.7, 6.5, 5.2];
  const dims = ['4032 × 3024', '4032 × 3024', '4000 × 3000', '4032 × 3024'];
  const sources = ['Immich upload', 'External library', 'Immich upload', 'External library'];
  const dates = ['Aug 21, 2026 · 17:45', 'Aug 21, 2026 · 17:45', 'Aug 21, 2026 · 17:46', 'Aug 20, 2026 · 21:11'];
  const uploads = ['Aug 21 · 17:47', 'Aug 22 · 08:20', 'Aug 21 · 17:48', 'Aug 23 · 10:05'];
  return {
    name: `IMG_G${group}_${String(index + 1).padStart(2, '0')}.jpg`,
    source: sources[index % sources.length],
    size: `${sizes[index % sizes.length].toFixed(1)} MB`,
    sizeNum: sizes[index % sizes.length],
    dims: dims[index % dims.length],
    taken: dates[index % dates.length],
    codec: index % 4 === 3 ? 'JPEG · quality 92' : 'JPEG · quality 95',
    library: index % 2 === 0 ? 'Camera Uploads' : 'Family NAS',
    uploaded: uploads[index % uploads.length],
    similarity: (99.4 - (index * 0.65) % 8).toFixed(1),
  };
}
