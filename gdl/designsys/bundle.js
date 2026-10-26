/* @ds-bundle: __HEADER__ */
/*
 * Extron touch-panel components for a Design canvas - one template's look.
 *
 * Written by gdl/designsys, which puts a template's profile in P below.
 * Every component draws the template's own look and carries its
 * spec fields on one element as data-gdl JSON, which is what
 * gdl/design.py reads to turn a canvas into a spec. The drawing is for the
 * designer; the data-gdl is the contract. Keep the two in step.
 *
 * A classic script: no import, no eval, no network, and no closing script tag
 * or HTML comment opener anywhere in it (consumers inline it).
 */
(function () {
  'use strict';
  var P = __PROFILE__;
  var React = window.React;
  var h = React.createElement;
  var Ctx = React.createContext(null);

  // -- the template's colors, per accent scheme ---------------------------
  function schemeColors(id) {
    var first = P.schemes[0].id;
    var out = {};
    P.colors.forEach(function (c) {
      var v = c.value;
      if (v && typeof v === 'object') v = v[id] || v[first];
      out[c.name] = v;
    });
    Object.keys(out).forEach(function (k) {
      var v = out[k];
      if (typeof v === 'string' && v.charAt(0) === '{') out[k] = out[v.slice(1, -1)];
    });
    return out;
  }
  function schemeId(s) {
    for (var i = 0; i < P.schemes.length; i++) if (P.schemes[i].id === s) return s;
    return P.schemes[0].id;
  }
  function useLook() {
    return React.useContext(Ctx) || { scheme: P.schemes[0].id, colors: schemeColors(P.schemes[0].id) };
  }
  // A token name or a literal hex -> a CSS color. A name the template does
  // not have paints magenta, so it is seen in the design, not only in the
  // translator's report.
  function paint(colors, v) {
    if (v == null || v === '' || v === 'none') return 'transparent';
    v = String(v);
    if (v.charAt(0) === '#') return v;
    return colors[v] || '#FF00FF';
  }

  // -- units: sizes are POINTS, as in the spec and GUI Designer -------------
  function px(pt) { return Math.round(Number(pt) * P.pt * 100) / 100 + 'px'; }
  function typeStyle(name) {
    for (var i = 0; i < P.type.length; i++) if (P.type[i].name === name) return P.type[i];
    return null;
  }
  // A point size on the panel being drawn: scaled with the frame the text is
  // laid out in, as Extron's own smaller series step their type down, and
  // never under that panel's floor - 14 pt as it reads on a 1025/1035
  // (gdl.spec.type_floor). Unchanged on the panel the canvas was drawn for.
  function ptOn(pt, L) {
    if (!L || !L.aware) return pt;
    var k = L.k == null ? 1 : L.k;
    var scaled = k === 1 ? pt : Math.round(pt * k * 2) / 2;
    return Math.max(L.panel.floor || 0, scaled);
  }
  function font(props, fallbackType, L) {
    var t = typeStyle(props.type) || typeStyle(fallbackType) || P.type[P.type.length - 1];
    var size = ptOn(props.size != null ? Number(props.size) : t.pt, L);
    var bold = props.bold != null ? truthy(props.bold) : t.weight >= 600;
    // In a plain container scaled as a whole (L.css), drawn at size / scale so
    // it shows at `size` - the size the translator reads and the panel builds.
    var at = L && L.aware && L.css ? size / L.css : size;
    return { size: size, bold: bold,
             css: (bold ? 700 : 400) + ' ' + px(at) + '/1.2 ' + P.font.stack };
  }
  // A caption's width at a font, from the font's own metrics. Not layout:
  // nothing on the page is measured.
  var metrics = null;
  function textWidth(text, css) {
    try {
      if (!metrics) metrics = document.createElement('canvas').getContext('2d');
      metrics.font = css;
      return String(text).split(/\r?\n/).reduce(function (m, line) {
        return Math.max(m, metrics.measureText(line).width);
      }, 0);
    } catch (e) {
      return String(text).length * 10;
    }
  }
  function lineHeight(size) { return Math.ceil(size * P.pt * 1.2); }
  // Words in lines no wider than `width` at `css`, at the spaces between
  // them; a line break already in them stays one.
  function wrapWords(text, css, width) {
    var out = [];
    String(text).split(/\r?\n/).forEach(function (para) {
      var line = '';
      para.split(/\s+/).forEach(function (w) {
        if (!w) return;
        var t = line ? line + ' ' + w : w;
        if (line && textWidth(t, css) > width) { out.push(line); line = w; } else line = t;
      });
      out.push(line);
    });
    return out;
  }
  function truthy(v) { return v === true || v === 'true' || v === 'yes' || v === '1'; }
  // A control's `id` as the designer wrote it: a whole number is the ID, and
  // anything else goes through as written, for gdl.spec check to name.
  // Number() made 'abc' NaN, which JSON writes as null, so the control quietly
  // took an allocated ID; and an empty one 0, GUI Designer's 'no ID'.
  function idOf(v) {
    if (v == null || String(v).trim() === '') return null;
    return /^\s*\d+\s*$/.test(String(v)) ? Number(v) : v;
  }

  // -- props that arrive as text from markup --------------------------------
  // `states` may be "Off, On" or a JSON list '[{"name":"Off"}, ...]', or an
  // array from a {{hole}}.
  function list(v) {
    if (v == null || v === '') return null;
    if (Array.isArray(v)) return v;
    var s = String(v).trim();
    if (s.charAt(0) === '[') {
      try { return JSON.parse(s); } catch (e) { return [{ name: 'states is not valid JSON' }]; }
    }
    return s.split(',').map(function (n) { return n.trim(); }).filter(Boolean);
  }
  function find(xs, name) {
    for (var i = 0; xs && i < xs.length; i++) if (xs[i] && xs[i].name === name) return xs[i];
    return null;
  }
  function textOf(children, fallback) {
    var parts = [];
    React.Children.forEach(children, function (c) {
      if (typeof c === 'string' || typeof c === 'number') parts.push(String(c));
    });
    var s = parts.join('').trim();
    return s || (fallback != null ? String(fallback) : '');
  }
  function gdl(fields) {
    var o = {};
    Object.keys(fields).forEach(function (k) {
      var v = fields[k];
      if (v != null && v !== '' && !(Array.isArray(v) && !v.length)) o[k] = v;
    });
    return JSON.stringify(o);
  }
  // A border as this panel's own seed defines it: every project carries
  // its own copy of the built-ins, and Build draws the panel's - Shockwave's
  // 520s, 535s and 320 round 2D Rounded Rectangle at 10 px where its 1035
  // does at 2 (the model row's `radii`, tests/measure_series.py seed_radii).
  function borderOn(L, name) {
    var b = P.borders[name], r = L && L.panel && L.panel.radii;
    return b && r && r[name] != null ? Object.assign({}, b, { radius: r[name] }) : b;
  }
  function radius(b, w, hgt) {
    if (!b) return '0';
    if (b.radius < 0) return '50%';
    if (b.radius >= 9999) return '9999px';
    return b.radius + 'px';
  }
  function edge(b, colors, stroke) {
    if (!b || !b.thickness || !stroke) return 'none';
    return b.thickness + 'px solid ' + paint(colors, stroke);
  }
  function navHref(nav) {
    nav = String(nav);
    return /\.dc\.html$/.test(nav) ? nav : nav + '.dc.html';
  }
  var ALIGN = { left: 'flex-start', center: 'center', right: 'flex-end' };

  // -- panels: one canvas, every panel a room has ----------------------------
  // P.models (gdl.designsys.models) holds every panel the template's series
  // serve: its size, minimums, type floor, main region, rail band and art. A
  // Page that lists `panels` derives its layout for one of them - the one the
  // translator names (window.__GDL_PANEL), else `preview`, else the first,
  // the panel the canvas is drawn on. A canvas that lists none draws exactly
  // as it always has.
  var MODELS = P.models || {};
  function words(v) { return String(v || '').split(/[\s,]+/).filter(Boolean); }
  function forcedPanel() {
    return typeof window !== 'undefined' && window.__GDL_PANEL ? String(window.__GDL_PANEL) : null;
  }
  // What a frame's child is, read off its element: the runtime wraps each
  // x-import in a host div whose `style` is the designer's rect, around the
  // component's own element. A plain div is a 'box'.
  var KINDS = null;
  function compOf(host) {
    var kids = React.Children.toArray(host && host.props ? host.props.children : null);
    return kids.length === 1 && React.isValidElement(kids[0]) && typeof kids[0].type === 'function'
      ? kids[0] : null;
  }
  // A length in a frame `base` px across: px, or a percentage of the frame.
  function len(v, base) {
    if (v == null || v === '' || v === 'auto') return null;
    var s = String(v).trim(), n = parseFloat(s);
    if (isNaN(n)) return null;
    if (/%$/.test(s)) return base != null ? n * base / 100 : null;
    return n;
  }
  // The rect a child was drawn at in its frame (`box` its [width, height]):
  // `width: 100%` read as 100 px, and a box held by left and right with no
  // width had no rect and stayed at its design place, unscaled.
  function itemsOf(children, box) {
    var out = [];
    var BW = box ? box[0] : null, BH = box ? box[1] : null;
    React.Children.toArray(children).forEach(function (host) {
      if (!React.isValidElement(host)) return;
      var comp = compOf(host);
      // A region (or a Section) written with no x-import host round it - a
      // design system's preview card, in React - is its own element.
      var own = typeof host.type === 'function' && KINDS.get(host.type);
      if (!comp && own && (REGION_NAMES[own] || own === 'section')) comp = host;
      var kind = comp ? KINDS.get(comp.type) || null : (typeof host.type === 'string' ? 'box' : null);
      var st = host.props && host.props.style;
      var rect = null;
      if (st && typeof st === 'object') {
        var w = len(st.width, BW), ht = len(st.height, BH);
        var l = len(st.left, BW), t = len(st.top, BH), rt = len(st.right, BW), b = len(st.bottom, BH);
        if (w == null && l != null && rt != null && BW != null) w = BW - l - rt;
        if (ht == null && t != null && b != null && BH != null) ht = BH - t - b;
        if (w != null && ht != null) {
          if (l == null) l = rt != null && BW != null ? BW - rt - w : 0;
          if (t == null) t = b != null && BH != null ? BH - b - ht : 0;
          rect = [l, t, w, ht];
        }
      }
      out.push({ host: host, comp: comp, kind: kind, rect: rect, props: comp ? comp.props : host.props });
    });
    return out;
  }
  // A design rect onto a panel rect at one uniform scale, centred, so squares
  // stay square.
  function fit(D, T) {
    var s = Math.min(T[2] / D[2], T[3] / D[3]);
    return { s: s, x: T[0] + (T[2] - D[2] * s) / 2, y: T[1] + (T[3] - D[3] * s) / 2 };
  }
  // Whole pixels, as GUI Designer places controls: a layout that summed
  // fractions would round two neighbours a pixel closer than the gap.
  function cell(r) {
    return { position: 'absolute', left: Math.round(r[0]) + 'px', top: Math.round(r[1]) + 'px',
             width: Math.round(r[2]) + 'px', height: Math.round(r[3]) + 'px' };
  }
  function grow(r, m, keep) {
    var w = Math.max(r[2], m[0]), ht = Math.max(r[3], m[1]);
    // A box of no size has no shape to keep.
    if (keep && r[2] > 0 && r[3] > 0) {
      // Kit art is drawn to fit its box: grown on one side only it would sit
      // in a new shape and move off the caption laid out round it.
      var f = Math.max(w / r[2], ht / r[3]);
      w = r[2] * f; ht = r[3] * f;
    }
    return [r[0] - (w - r[2]) / 2, r[1] - (ht - r[3]) / 2, w, ht];
  }
  // A variant whose kit image is the whole button (a source tile, a toggle);
  // an icon beside a caption is not - its caption is laid out past it.
  function hasArt(it) {
    if (it.kind !== 'button') return false;
    var p = it.props || {};
    var V = P.buttons[p.variant] || P.buttons[P.defaults.button.variant];
    return !!V.kit;
  }
  // The least a control can be on this panel: a button at the touch minimum
  // and as big as its caption at the panel's type; a slider that wide across
  // its rail; a line of text at least one line tall. `filled`: a button that
  // fills its box across, as a Rail's do, needs only its own padding round
  // its caption (10 px a side) and its border where a look strokes one, not
  // the 4 px more a loose one keeps - the round-three Mach room's Mute came
  // to 100 px with them, and was refused in the 525's 98 px rail.
  function needs(it, L, filled) {
    var T = L.panel, p = it.props || {};
    if (it.kind === 'button') {
      var V = P.buttons[p.variant] || P.buttons[P.defaults.button.variant];
      var f = font(p, P.defaults.button.type, L);
      var words_ = [captionOf(V, p)];
      (list(p.states) || []).forEach(function (s) { if (s && s.text) words_.push(twoWords(V, s.text)); });
      var img = imageOf(V, p, words_[0]);
      // As drawn: an indented caption carries the spaces that clear its icon.
      var wide = Math.max.apply(null, words_.map(function (t) {
        return textWidth(img && img.caption === 'indent' ? placed(img, t) : t, f.css);
      }));
      var lines = img && img.caption === 'below' && words_[0]
        ? (belowBreaks(img) ? belowBreaks(img) + 1 : words_[0].split(/\r?\n/).length)
        : V.lines && words_[0] ? words_[0].split(/\r?\n/).length : 1;
      var tall = words_[0] ? lines * lineHeight(f.size) + 4 : 0;
      // The widest border a look of it strokes (edge(): a stroke on a border
      // with thickness), which its box holds inside it.
      var base = Object.assign({}, V.look || {}), edgeW = 0;
      if (p.border != null) base.border = p.border;
      if (p.stroke != null) base.stroke = p.stroke;
      [{}].concat((list(p.states) || []).filter(function (s) { return s && typeof s === 'object'; }))
        .forEach(function (s) {
          var lk = Object.assign({}, base, s), bd = P.borders[lk.border];
          if (lk.stroke && bd && bd.thickness) edgeW = Math.max(edgeW, bd.thickness);
        });
      return [Math.max(T.touch, Math.ceil(wide + (img ? 8 : filled ? 20 + 2 * edgeW : 24))),
              Math.max(T.touch, tall)];
    }
    if (it.kind === 'slider') return [T.touch, T.touch];
    if (it.kind === 'group' && joinedHere(p, L)) {
      var seg = segments(p, L);
      return [seg.n * seg.cw, seg.ch];
    }
    if (it.kind === 'group' && L.tier === 'C' && L.model !== L.designModel) {
      var o = font({}, P.defaults.button.type, L);
      return [Math.max(T.touch, Math.ceil(textWidth(p.title || 'Group', o.css) + 24)), T.touch];
    }
    if (it.kind === 'label' || it.kind === 'clock') {
      var g = font(p, it.kind === 'clock' ? P.defaults.clock.type : P.defaults.label.type, L);
      return [0, lineHeight(g.size) + 2];
    }
    return [0, 0];
  }
  function problem(msg, key) {
    return h('i', { key: 'problem-' + key, 'data-gdl-problem': msg, style: { display: 'none' } });
  }
  function placeHost(host, r, key) {
    return React.cloneElement(host, { key: key, style: cell(r) });
  }
  // A slider on a panel whose seed has no slider to clone (the 525's, the
  // 320's) is a level with Up and Down buttons, as Extron's own 520 and 320
  // templates draw volume. The level keeps the slider's name and ID; Up and
  // Down are navigation the program handles (derived, in the ID map).
  // Up and Down stand beside the level, one at each of its ends, where there
  // is room across for the level's track, a gap and a button: Extron's own
  // 520 and 535 stand Up, Down and Mute beside their volume level, the level
  // the length of the column - Mach 525's is 14 x 309 beside 66 px buttons,
  // and none of its templates draws one shorter than 175 px - where between
  // Up and Down the hubs' levels came out 15 to 42 px long. One at each end
  // is this layout's: the column's other buttons are the canvas's to place.
  // The three keep to `band`, the
  // cross-axis span of the band the slider is in (a hub's menu bar), centred
  // where the slider was, with the panel's spacing minimum between the level
  // and its buttons and at least that from the band's sides - or, in a band
  // too narrow for that (a hub's 98 to 104 px menu bar), an equal share of
  // what it leaves: a level is not touched, and Extron's own Shockwave 525
  // leaves 8 px. Failing that, they keep to `page`, the spacing minimum
  // between them. Without the room, the level is between them, and at least
  // 24 px long, as a rail's is.
  // Up and Down look like the button the canvas draws nearest the slider, in
  // its band where it has one, as Extron draws its volume Up, Down and Mute
  // alike - Mach 525's three on one transparent ground, Turbulence's three
  // rings; in the default look Mach's showed as two faint tiles on its photo
  // beside a solid Mute. `items` and `band` are in the design's own
  // coordinates.
  function stepVariant(it, items, band, a) {
    var cx = it.rect[0] + it.rect[2] / 2, cy = it.rect[1] + it.rect[3] / 2, best = null, d0 = Infinity;
    items.forEach(function (o) {
      if (o === it || o.kind !== 'button' || !o.rect) return;
      var ox = o.rect[0] + o.rect[2] / 2, oy = o.rect[1] + o.rect[3] / 2;
      if (band && ((a ? oy : ox) < band[0] || (a ? oy : ox) > band[1])) return;
      var d = Math.sqrt((ox - cx) * (ox - cx) + (oy - cy) * (oy - cy));
      if (d < d0) { d0 = d; best = o; }
    });
    var v = best && best.props && best.props.variant, V = v && P.buttons[v];
    if (!V) return null;
    // Only a look Up and Down can be drawn in: one drawn without the kit, or
    // one whose kit size has the theme's own volume icons. Another kit look
    // draws the icon its button names - an End Call, a laptop - or, with
    // none named, nothing: Afterburn's icon look, which the translator
    // refused. The theme's default button is used there.
    var steps = P.defaults.level.steps || {};
    var at = V.kit && KIT && KIT.files && KIT.files[V.kit];
    return !V.kit || at && steps.up && steps.down && at[steps.up] && at[steps.down] ? v : null;
  }
  function asLevel(it, r, axis, T, key, band, page, variant) {
    var p = it.props || {};
    var name = p.name || 'Slider';
    var t = T.touch, g = T.gap, row = axis === 'row';
    var along = row ? r[2] : r[3];
    var tw = Number(p.track) || P.defaults.level.track;
    var sp = band ? Math.min(g, Math.floor((band[1] - band[0] - tw - t) / 3)) : -1;
    var gi = sp >= 2 ? sp : g;
    var lo = sp >= 2 ? band[0] + sp : page && page[1] - page[0] >= tw + g + t ? page[0] : null;
    var hi = sp >= 2 ? band[1] - sp : lo != null ? page[1] : null;
    var up, down, lv;
    if (along >= 2 * t + g && lo != null) {
      var across = tw + gi + t;
      var c0 = Math.round(Math.max(lo, Math.min((row ? r[1] + r[3] / 2 : r[0] + r[2] / 2) - across / 2, hi - across)));
      var b0 = c0 + tw + gi;
      lv = row ? [r[0], c0, r[2], tw] : [c0, r[1], tw, r[3]];
      up = row ? [r[0] + r[2] - t, b0, t, t] : [b0, r[1], t, t];
      down = row ? [r[0], b0, t, t] : [b0, r[1] + r[3] - t, t, t];
    } else {
      if (along < 2 * t + 2 * g + 24) return { els: [], problems: [name + ' cannot fit a level with Up and Down on a ' + T.model] };
      up = row ? [r[0] + r[2] - t, r[1] + (r[3] - t) / 2, t, t] : [r[0] + (r[2] - t) / 2, r[1], t, t];
      down = row ? [r[0], r[1] + (r[3] - t) / 2, t, t] : [r[0] + (r[2] - t) / 2, r[1] + r[3] - t, t, t];
      lv = row ? [r[0] + t + g, r[1], r[2] - 2 * (t + g), r[3]] : [r[0], r[1] + t + g, r[2], r[3] - 2 * (t + g)];
    }
    // The theme's own volume icons (its level's `steps`) where that look draws
    // from the kit and the kit has them at its size, else '+' and '-'.
    var V = P.buttons[variant] || P.buttons[P.defaults.button.variant];
    var size = V.kit || (V.with_icon && V.with_icon.bare);
    var steps = P.defaults.level.steps || {};
    function btn(suffix, caption, verb, rect) {
      var icon = steps[suffix.toLowerCase()];
      icon = icon && size && KIT && KIT.files && KIT.files[size] && KIT.files[size][icon] ? icon : null;
      return h('div', { key: key + suffix, style: cell(rect) },
               h(Button, { name: name + ' ' + suffix, derived: true, variant: variant || undefined,
                           icon: icon || undefined, text: icon ? '' : caption,
                           does: verb + ' ' + name + ' one step.' }));
    }
    var level = Object.assign({}, p, { orientation: axis === 'row' ? 'right' : 'up', fromSlider: true });
    return { els: [btn('Down', '-', 'Lowers', down), h('div', { key: key + 'level', style: cell(lv) }, h(Level, level)),
                   btn('Up', '+', 'Raises', up)], problems: [] };
  }
  // A page's own children, on a panel other than the one drawn, go through
  // both panels' main regions rather than at one scale for the page, where
  // the template draws its bars as controls. Main's edges cut each page into
  // the same bands - the header and footer, the bands beside main, main - and
  // a child moves with its band. An edge on a cut, or within 4 px of one,
  // stays on it, so a bar across the page stretches with it and an end cap
  // stays at the end of its band; a child with no edge on one keeps its
  // shape, at the scale of the band its centre is in - or, where it stretches
  // the other way, at this way's own. Mach, Shockwave and Turbulence draw
  // their bars as controls, and their series' bands are not one scale of
  // each other's: scaled whole, the 1035's header stopped 32 px short of
  // each side of the 725 and came out 48 deep where its template's is 60.
  // The 4 px: Turbulence's header ends 4 px above its main region, as its
  // template's does, and is still the header.
  function onCut(v, s) {
    for (var i = 0; i < s.length; i++) if (Math.abs(v - s[i]) <= 4) return i;
    return -1;
  }
  function bandOf(v, s) {
    for (var i = 1; i < s.length - 1; i++) if (v <= s[i]) return i;
    return s.length - 1;
  }
  function through(v, s, t) {
    var i = bandOf(v, s), span = s[i] - s[i - 1];
    return span > 0 ? t[i - 1] + (v - s[i - 1]) * (t[i] - t[i - 1]) / span : t[i - 1];
  }
  function bandScale(v, s, t) {
    var i = bandOf(v, s), span = s[i] - s[i - 1];
    return span > 0 ? (t[i] - t[i - 1]) / span : 1;
  }
  function cutRect(r, cut) {
    var ax = [0, 1].map(function (a) {
      var s = cut.from[a], lo = r[a], hi = r[a] + r[a + 2];
      var at = onCut(lo, s), to = onCut(hi, s);
      return { s: s, t: cut.to[a], lo: lo, hi: hi, at: at, to: to, both: at >= 0 && to >= 0 && at !== to,
               k: bandScale((lo + hi) / 2, s, cut.to[a]) };
    });
    var out = [0, 0, 0, 0];
    ax.forEach(function (x, a) {
      var k = ax[1 - a].both ? x.k : Math.min(ax[0].k, ax[1].k);
      var size = (x.hi - x.lo) * k, lo, hi;
      if (x.both) { lo = x.t[x.at]; hi = x.t[x.to]; }
      else if (x.at >= 0) { lo = x.t[x.at]; hi = lo + size; }
      else if (x.to >= 0) { hi = x.t[x.to]; lo = hi - size; }
      else { var m = through((x.lo + x.hi) / 2, x.s, x.t); lo = m - size / 2; hi = m + size / 2; }
      out[a] = lo; out[a + 2] = hi - lo;
    });
    out.both = [ax[0].both, ax[1].both];
    return out;
  }
  // A target's cuts on one axis - [0, main's start, main's end, size] - where
  // a band the design panel has and the target has not is carved from the
  // target's main at the page's scale `k`, at most a quarter of main a side.
  // A hub's main runs from its top to its bottom and from its left edge to
  // its menu bar (the 520's, the 535's): a header, a footer or a column drawn
  // beside main had nowhere to go and collapsed to nothing. Extron's own hub
  // templates keep a title strip at the top of main, so a header there is
  // the hub's way too.
  // Whole pixels: cell() rounds a rect's top and height apart, so a footer
  // under a cut at 670.5 ended at 721 on the 535's 720 and left the canvas.
  // A carved band that holds a button or a slider is at least the panel's
  // touch minimum deep, and one that holds a Group as deep as its cells
  // (`minLo`, `minHi`): the 535's 49 px footer grew its end cap to 104 px, up
  // into the menu bar's mute. What a band holds wins over the quarter, which
  // bounds only its scaled depth: capped, the round-two Turbulence room's
  // 128 px source tabs kept a 120 px header on the 525 and stood 8 px into
  // main. panelPage names a main the bands leave smaller than a control.
  function hubBands(dLo, dHi, dSize, tLo, tHi, tSize, k, minLo, minHi) {
    var lo = tLo, hi = tHi, quarter = (tHi - tLo) / 4;
    if (dLo >= 1 && tLo < 1) lo = Math.round(Math.max(Math.min(dLo * k, quarter), minLo || 0));
    if (dSize - dHi >= 1 && tSize - tHi < 1) {
      hi = Math.round(tSize - Math.max(Math.min((dSize - dHi) * k, tSize - tHi + quarter), minHi || 0));
    }
    return [0, lo, hi, tSize];
  }
  // Where a Group in box `r` comes out on its own (Group, tiers A and B): at
  // least one cell, centred on its box, kept to the page as it keeps itself
  // (`room`). A joined Group is its one row.
  function groupOut(it, r, room, k, L) {
    var p = it.comp.props, seg = segments(p, Object.assign({}, L, { k: k }));
    var w = Math.max(r[2], truthy(p.joined) ? seg.n * seg.cw : seg.cw), ht = Math.max(r[3], seg.ch);
    var x = r[0] + (r[2] - w) / 2, y = r[1] + (r[3] - ht) / 2;
    if (room) { x = Math.min(Math.max(x, 0), room[2] - w); y = Math.min(Math.max(y, 0), room[3] - ht); }
    return [x, y, w, ht];
  }
  // Tiers A and B, and the panel the canvas was drawn for: every child at its
  // own design rect, mapped by the frame's scale - or a page's own, through
  // its bands (`cut`, above) - then grown about its centre to what it needs on
  // this panel.
  function scaleLayout(items, D, T, L, frame, cut) {
    var f = fit(D, frame);
    var els = [], probs = [];
    // Where each control came out, and each Panel's slot, for holds() below.
    var out = [], cards = [];
    items.forEach(function (it, i) {
      var own = it.kind === 'mainarea' || it.kind === 'rail' || REGION_NAMES[it.kind];
      if (!it.rect || own) {
        els.push(own ? React.cloneElement(it.host, { key: 'f' + i, style: { display: 'contents' } }) : it.host);
        return;
      }
      var c = cut;
      var r = c ? cutRect(it.rect, c)
        : [f.x - frame[0] + it.rect[0] * f.s, f.y - frame[1] + it.rect[1] * f.s, it.rect[2] * f.s, it.rect[3] * f.s];
      if (it.kind === 'box' && c) {
        // A plain container keeps its own layout, scaled whole to its place
        // among the bands (as below): by the way it spans, edge to edge, where
        // it spans one way - a row the depth of its bar stays in the bar
        // (Turbulence's source tabs, scaled by their width's band, stood 3 px
        // out of the 725's header), and a column across main fills main's
        // width (its Help's steps, scaled by main's height, no longer held
        // their words) - else by the smaller of its two sides. Centred in its
        // place where it comes out smaller than it.
        var rx = it.rect[2] ? r[2] / it.rect[2] : Infinity, ry = it.rect[3] ? r[3] / it.rect[3] : Infinity;
        var bk = r.both[0] && !r.both[1] ? rx : r.both[1] && !r.both[0] ? ry : Math.min(rx, ry);
        if (!isFinite(bk)) bk = f.s;
        var ox = r[0] + Math.max(0, r[2] - it.rect[2] * bk) / 2, oy = r[1] + Math.max(0, r[3] - it.rect[3] * bk) / 2;
        var placed = { position: 'absolute', left: Math.round(ox - it.rect[0] * bk) + 'px',
                       top: Math.round(oy - it.rect[1] * bk) + 'px', width: 0, height: 0,
                       transform: 'scale(' + bk + ')', transformOrigin: '0 0' };
        els.push(h(Ctx.Provider, { key: 'b' + i, value: Object.assign({}, L, { k: bk, css: bk }) },
                   h('div', { style: placed }, it.host)));
        return;
      }
      if (it.kind === 'box') {
        // A plain container keeps its own layout, scaled as a whole; what is
        // in it grows to its minimum from inside (Button's own min size). The
        // runtime draws a plain div from its markup and ignores a style cloned
        // onto it - the container stayed at design size beside its scaled
        // siblings - so the scale is on a zero-size layer of ours at the
        // frame's mapped origin, the container at its own design place in it.
        var layer = { position: 'absolute', left: Math.round(f.x - frame[0]) + 'px',
                      top: Math.round(f.y - frame[1]) + 'px', width: 0, height: 0,
                      transform: 'scale(' + f.s + ')', transformOrigin: '0 0' };
        els.push(h(Ctx.Provider, { key: 'b' + i, value: Object.assign({}, L, { k: f.s, css: f.s }) },
                   h('div', { style: layer }, it.host)));
        return;
      }
      if (it.kind === 'slider' && T.kinds && T.kinds.slider === false) {
        var a = it.rect[2] > it.rect[3] ? 1 : 0, page = [0, frame[2 + a]], band = page, drawn = null;
        if (c) {
          var bi = bandOf(it.rect[a] + it.rect[a + 2] / 2, c.from[a]);
          band = [c.to[a][bi - 1], c.to[a][bi]];
          drawn = [c.from[a][bi - 1], c.from[a][bi]];
        }
        var lv = asLevel(it, r, a ? 'row' : 'column', T, 's' + i, band, page, stepVariant(it, items, drawn, a));
        els = els.concat(lv.els);
        probs = probs.concat(lv.problems);
        return;
      }
      if (it.kind === 'group') {
        // Its box's place and the frame's size (`__room`), so a Group grown
        // past its box keeps to the page as a control does (below).
        var room = c || L.keepIn ? [Math.round(r[0]), Math.round(r[1]), frame[2], frame[3]] : null;
        els.push(React.cloneElement(it.host, { key: 'g' + i, style: cell(r) },
                   React.cloneElement(it.comp, { __box: [Math.round(r[2]), Math.round(r[3])], __k: f.s,
                                                 __room: room })));
        out.push({ it: it, r: groupOut(it, r, room, f.s, L) });
        return;
      }
      var g = grow(r, needs(it, L), hasArt(it));
      // Grown past a bar shallower than the touch minimum (the 725's 57 px
      // footer), a page's own child stays on the page: Build moves a control
      // that crosses its page's edge.
      if (c || L.keepIn) g = [Math.min(Math.max(g[0], 0), frame[2] - g[2]), Math.min(Math.max(g[1], 0), frame[3] - g[3]), g[2], g[3]];
      if (it.kind === 'panel' && c && c.hub) cards.push({ at: els.length, it: it, g: g, i: i });
      else out.push({ it: it, r: g });
      els.push(placeHost(it.host, g, 'c' + i));
    });
    // On a hub a bar or a card among a page's own controls holds what was
    // drawn in it, grown to the panel's touch minimum, as the band carved for
    // it does: on the 525 the round-three
    // Shockwave room's header came out 71 px deep under 94 px source tabs,
    // and its footer capsule 39 under a 66 px Mic Mute. Elsewhere a bar keeps
    // its series' own depth, as Extron's templates draw it, and a control grown
    // past it stays on the page (above): the 725's footer is 57.
    cards.forEach(function (cd) {
      var d = cd.it.rect, g = cd.g.slice();
      out.forEach(function (o) {
        var q = o.it.rect;
        if (!q) return;
        var cx = q[0] + q[2] / 2, cy = q[1] + q[3] / 2;
        if (cx < d[0] || cx > d[0] + d[2] || cy < d[1] || cy > d[1] + d[3]) return;
        var x0 = Math.min(g[0], o.r[0]), y0 = Math.min(g[1], o.r[1]);
        var x1 = Math.max(g[0] + g[2], o.r[0] + o.r[2]), y1 = Math.max(g[1] + g[3], o.r[1] + o.r[3]);
        g = [x0, y0, x1 - x0, y1 - y0];
      });
      g = [Math.max(0, g[0]), Math.max(0, g[1]), Math.min(frame[2], g[0] + g[2]) - Math.max(0, g[0]),
           Math.min(frame[3], g[1] + g[3]) - Math.max(0, g[1])];
      els[cd.at] = placeHost(cd.it.host, g, 'c' + cd.i);
    });
    return { els: els, problems: probs, k: f.s };
  }
  // Tier C: positions scaled by a quarter cannot keep 14 pt lines apart, so
  // the frame's children reflow - rows in design order, each control at what
  // it needs, rows centred - and a panel card behind a set of them is drawn
  // behind where they land. What does not fit is a problem, never dropped.
  function flowLayout(items, D, T, L, frame, where) {
    var R = flowRows(items, D, T, L, frame, where);
    var total = R.laid.reduce(function (s, line) { return s + line.h + line.gap; }, 0);
    if (total > frame[3] - 2 * R.tight) {
      R.probs.push(where + ' needs ' + Math.round(total) + ' px of a ' + T.model + "'s " + frame[3] + ' - it does not fit');
    }
    var put = placeRows(R, R.laid, [0, 0, frame[2], frame[3]], Math.round(Math.max(R.tight, (frame[3] - total) / 2)));
    var back = cardsBehind(R, put.placed, [0, 0, frame[2], frame[3]], true, function (card, r) {
      return placeHost(card.host, r, 'card' + card.i);
    });
    return { els: back.concat(R.els, put.els), problems: R.probs, k: R.k };
  }
  // The rows a frame's children reflow into on a tier C panel: each line of
  // controls at what each needs on it, wrapped to the frame's width, and the
  // gap above it - none above the first. `band(it)`, where given, orders the
  // controls by region first, and a row is never two regions'. `page`: a
  // page's rows where its template's chrome is art (rowsPage) - a heading in
  // the row of the Group it heads, a Line between the rows it was drawn
  // between, and, where the rows need more than `room`, a row beside an
  // earlier one of another region that has room across for it.
  function flowRows(items, D, T, L, frame, where, band, page, room) {
    var bandOf = band || function () { return 0; };
    var f = fit(D, frame), k = f.s;
    var pad = T.gap, gap = T.gap, tight = 2;
    var W = frame[2] - 2 * pad, els = [], probs = [];
    var cards = [], flow = [], rules = [];
    items.forEach(function (it, i) {
      it.i = i;
      var own = it.kind === 'mainarea' || it.kind === 'rail' || REGION_NAMES[it.kind];
      if (!it.rect || own) {
        els.push(own ? React.cloneElement(it.host, { key: 'f' + i, style: { display: 'contents' } }) : it.host);
      } else if (it.kind === 'box') {
        probs.push('a plain container in ' + where + ' cannot reflow on a ' + T.model + ' - use a Group');
      } else if (it.kind === 'panel') {
        cards.push(it);
      } else if (page && it.kind === 'line' && (it.props || {}).orientation !== 'vertical') {
        rules.push(it);
      } else {
        flow.push(it);
      }
    });
    // A Line with no row of its own region to stand by is a row, as before.
    rules = rules.filter(function (ru) {
      var lone = !flow.some(function (it) { return bandOf(it) === bandOf(ru); });
      if (lone) flow.push(ru);
      return !lone;
    });
    flow.sort(function (a, b) { return (bandOf(a) - bandOf(b)) || (a.rect[1] - b.rect[1]) || (a.rect[0] - b.rect[0]); });
    // Rows: a control joins the row above while its middle is inside it.
    var rows = [];
    flow.forEach(function (it) {
      var mid = it.rect[1] + it.rect[3] / 2;
      var row = rows[rows.length - 1];
      if (row && row.band === bandOf(it) && mid >= row.top && mid <= row.bottom) {
        row.items.push(it); row.bottom = Math.max(row.bottom, it.rect[1] + it.rect[3]);
      } else rows.push({ top: it.rect[1], bottom: it.rect[1] + it.rect[3], items: [it], band: bandOf(it) });
    });
    // A heading: a Label alone in its row whose foot meets the row under it
    // in its own region, within the canvas's gap. It goes on with that row
    // (overPages). On a `page`, over a Group - the one button that opens its
    // pages here, captioned with its title - it is that button's, so it
    // stands at its left in its row: ordered by its own place, Afterburn's
    // left-rail heading came out as the page's first row and its Group the
    // last, a main-area control between them - Start, round four's, on
    // Lights. Over loose controls it keeps its row, and the two stay together.
    for (var r = rows.length - 2; r >= 0; r--) {
      var a = rows[r], b = rows[r + 1], lab = a.items.length === 1 && a.items[0].kind === 'label' ? a.items[0] : null;
      if (!lab || b.band !== a.band || b.top - (lab.rect[1] + lab.rect[3]) > P.spacing) continue;
      var lr = lab.rect;
      var grp = page && b.items.filter(function (it) {
        return it.kind === 'group' && it.rect[0] < lr[0] + lr[2] && lr[0] < it.rect[0] + it.rect[2];
      })[0];
      if (grp) {
        lab.heads = grp; b.items.push(lab); rows.splice(r, 1);
      } else {
        a.heading = a.fixed = b.fixed = true;
      }
    }
    if (page) {
      // A Line goes under the last row of its region that starts above its
      // middle, else over the first: Main SD's Divider, its middle level with
      // the sources' foot, joined their row and took 193 of its 302 px.
      rules.forEach(function (ru) {
        var mid = ru.rect[1] + ru.rect[3] / 2;
        var mine = rows.filter(function (row) { return row.band === bandOf(ru); });
        var over = mine.filter(function (row) { return row.top <= mid; }).pop();
        if (over) (over.below = over.below || []).push(ru);
        else (mine[0].above = mine[0].above || []).push(ru);
      });
    }
    // Sizes on this panel, then rows that are too wide wrap.
    var laid = [];
    rows.forEach(function (row) {
      row.items.sort(function (a, b) { return a.rect[0] - b.rect[0]; });
      row.items.filter(function (it) { return it.heads; }).forEach(function (lab) {
        row.items.splice(row.items.indexOf(lab), 1);
        row.items.splice(row.items.indexOf(lab.heads), 0, lab);
      });
      var first = laid.length;
      var line = [], width = 0;
      row.items.forEach(function (it) {
        var n = needs(it, L);
        var w, ht;
        if (it.kind === 'label' || it.kind === 'clock') {
          var g = font(it.props || {}, it.kind === 'clock' ? P.defaults.clock.type : P.defaults.label.type, L);
          var text = it.kind === 'clock' ? clockSample(CLOCK_FORMATS[(it.props || {}).format || 'time'] || (it.props || {}).format)
                                         : textOf((it.props || {}).children, (it.props || {}).text);
          w = Math.min(W, Math.max(it.rect[2] * k, textWidth(text, g.css) + 8));
          ht = n[1];
          // Words wider than the screen break into lines, each as GUI Designer
          // lays one out (1.362 em of Open Sans, where the canvas's is 1.2):
          // the round-three Help modals' sentences, one 26 px line in a 302 px
          // box on the 320, ran past it into the next.
          it.lines = null;
          if (it.kind === 'label' && textWidth(text, g.css) + 8 > W) {
            it.lines = wrapWords(text, g.css, W - 8);
            ht = it.lines.length * Math.ceil(g.size * P.pt * 1.37) + 2;
          }
        } else if (it.kind === 'slider') {
          // As a level (asLevel), Down and Up at the touch minimum with 24 px
          // of level between them: three touch minimums were 2 px short of it
          // on the 320.
          var least = T.kinds && T.kinds.slider === false ? 2 * T.touch + 2 * T.gap + 24 : 0;
          w = Math.min(W, Math.max(it.rect[2] * k, 3 * T.touch, least)); ht = T.touch;
        } else if (it.kind === 'group') {
          // On a small panel a Group is the button that opens its pages, or a
          // segmented control's one row: what it needs, not its drawn box.
          w = Math.min(W, n[0]); ht = n[1];
        } else {
          var g2 = grow([0, 0, it.rect[2] * k, it.rect[3] * k], n, hasArt(it));
          w = Math.min(W, g2[2]); ht = g2[3];
        }
        if (line.length && width + gap + w > W) { laid.push(line); line = []; width = 0; }
        width += (line.length ? gap : 0) + w;
        // A popup region is rounded as its popups are scaled (panelPage), a
        // popup being its reference's size (Standards p.70): rounded up, the
        // 320's 880x525 region came out 223x133 over 222x133 popups.
        if (it.kind === 'popupregion') {
          // A row holds the frame's width less its padding, and the popups
          // scale as the region would: past it they are wider than their
          // region, which a popup being its reference's size cannot be. The
          // 300 Portrait (a 294 px row, 307 px popups) names what to draw.
          if (it.rect[2] * k > W + 0.5) {
            probs.push(nameOf(it) + ' is ' + Math.round(it.rect[2]) + ' px wide, which a row on the ' + T.model
                       + ' (' + Math.floor(W) + ' px) cannot hold - draw it and its popups at most '
                       + Math.floor(W / k) + ' px wide');
          }
          w = Math.round(w); ht = Math.round(ht);
        }
        w = Math.ceil(w); ht = Math.ceil(ht);
        line.push({ it: it, w: w, h: ht });
      });
      if (line.length) laid.push(line);
      // The lines a row came out as: its Lines over the first and under the
      // last, and its region; a row that wrapped is not moved (below).
      var mine = laid.slice(first);
      mine.forEach(function (ln) { ln.bands = [row.band]; ln.fixed = row.fixed || mine.length > 1; });
      if (row.heading && mine.length) mine[mine.length - 1].heading = true;
      if (mine.length) {
        mine[0].above = row.above || null;
        mine[mine.length - 1].below = row.below || null;
      }
    });
    function touchy(line) { return line.some(function (c) { return c.it.kind === 'button' || c.it.kind === 'slider'; }); }
    // A Group here is a button too (or a joined row of them): two rows of
    // them keep the panel's gap apart, which the gap rule above, counting
    // only buttons and sliders, left at 2 px - Call's Camera Presets over
    // its VTC. A Group's row and a popup region under it keep 2 px: the
    // region is no touch target.
    function touches(line) { return line.some(function (c) { return c.it.kind === 'group'; }) || touchy(line); }
    var trail = 0;
    function thick(ru) { return Number((ru.props || {}).thickness) || P.defaults.line.thickness; }
    function stack(rs) {
      return rs.reduce(function (s, ru) { return s + thick(ru); }, 0) + tight * Math.max(0, rs.length - 1);
    }
    function heights() {
      laid.forEach(function (line, n) {
        var prev = laid[n - 1];
        line.h = Math.max.apply(null, line.map(function (c) { return c.h; }));
        line.gap = n ? (touchy(line) || touchy(prev) || touches(line) && touches(prev) ? gap : tight) : 0;
        // A Line between two rows stands in the gap between them, 2 px clear
        // of each: held to its own thickness, Main SD's Divider on the 300
        // touched the sources' foot and its popup region's top.
        var between = n && page ? (prev.below || []).concat(line.above || []) : [];
        if (between.length) line.gap = Math.max(line.gap, stack(between) + 2 * tight);
      });
      if (laid.length && page) {
        laid[0].pre = laid[0].above ? stack(laid[0].above) + tight : 0;
        trail = laid[laid.length - 1].below ? stack(laid[laid.length - 1].below) + tight : 0;
      }
    }
    function join(a, b) { var c = (a || []).concat(b || []); return c.length ? c : null; }
    function across(line) { return line.reduce(function (s, c) { return s + c.w; }, 0) + gap * (line.length - 1); }
    function total() {
      return laid.reduce(function (s, line, n) { return s + line.h + (n ? line.gap : 0) + (line.pre || 0); }, 0) + trail;
    }
    heights();
    // Where the rows need more than the screen holds, a row of one region
    // stands beside the first earlier row of others it fits beside, after
    // what that row holds - a left rail's Group in the sources' row, where
    // the two fit across. A heading's own row and the row it heads, and a row
    // that wrapped, stay where they are. `before`: what they needed one under
    // another, which rowsPage says too where they still do not fit.
    var before = null;
    if (page && room != null && total() > room - 2 * tight) {
      before = total();
      var out = [];
      laid.forEach(function (line) {
        var to = line.fixed ? null : out.filter(function (o) {
          return !o.fixed && o.bands.indexOf(line.bands[0]) < 0 && across(o) + gap + across(line) <= W;
        })[0];
        if (!to) { out.push(line); return; }
        line.forEach(function (c) { to.push(c); });
        to.bands = to.bands.concat(line.bands);
        to.above = join(to.above, line.above);
        to.below = join(to.below, line.below);
      });
      laid = out;
      heights();
    }
    return { laid: laid, cards: cards, flow: flow, items: items, els: els, probs: probs,
             k: k, T: T, pad: pad, gap: gap, tight: tight, trail: trail, total: total(), before: before, thick: thick,
             stack: stack };
  }
  // flowRows' `lines` in `box` from `top` down, each centred across it - the
  // first with no gap above it, wherever it fell in the flow.
  function placeRows(R, lines, box, top) {
    var T = R.T, els = [], placed = {}, y = box[1] + top;
    lines.forEach(function (line, n) {
      if (n) y += line.gap;
      y += line.pre || 0;
      line.y = y;
      var wsum = line.reduce(function (s, c) { return s + c.w; }, 0) + R.gap * (line.length - 1);
      var x = box[0] + Math.round((box[2] - wsum) / 2);
      line.forEach(function (c) {
        var r = [x, y + Math.round((line.h - c.h) / 2), c.w, c.h];
        placed[c.it.i] = r;
        if (c.it.kind === 'slider' && T.kinds && T.kinds.slider === false) {
          // Its line is one touch minimum deep, which cannot hold Up and Down
          // beside it: they are along it.
          var lv = asLevel(c.it, r, 'row', T, 's' + c.it.i, null, null,
                           c.it.rect ? stepVariant(c.it, R.items, null, 0) : null);
          els = els.concat(lv.els);
          R.probs = R.probs.concat(lv.problems);
        } else if (c.it.kind === 'group') {
          els.push(React.cloneElement(c.it.host, { key: 'g' + c.it.i, style: cell(r) },
                     React.cloneElement(c.it.comp, { __box: [c.w, c.h], __k: R.k })));
        } else if (c.it.lines) {
          els.push(React.cloneElement(c.it.host, { key: 'c' + c.it.i, style: cell(r) },
                     React.cloneElement(c.it.comp, { __text: c.it.lines.join('\r\n') })));
        } else {
          els.push(placeHost(c.it.host, r, 'c' + c.it.i));
        }
        x += c.w + R.gap;
      });
      y += line.h;
    });
    return { els: els, placed: placed };
  }
  // A card goes behind the controls it was drawn behind, wherever they land
  // in `box`. One drawn behind none (`lone`) goes in the middle of `box` at
  // the frame's scale; one whose controls all landed elsewhere, nowhere.
  // `draw(card, rect)` makes its element.
  function cardsBehind(R, placed, box, lone, draw) {
    var back = [], pad = R.pad, k = R.k;
    R.cards.forEach(function (card) {
      var c = card.rect, b = null, any = false;
      R.flow.forEach(function (it) {
        var r = it.rect;
        if (!(r[0] >= c[0] && r[1] >= c[1] && r[0] + r[2] <= c[0] + c[2] && r[1] + r[3] <= c[1] + c[3])) return;
        any = true;
        var q = placed[it.i];
        if (!q) return;
        b = b ? [Math.min(b[0], q[0]), Math.min(b[1], q[1]), Math.max(b[2], q[0] + q[2]), Math.max(b[3], q[1] + q[3])]
              : [q[0], q[1], q[0] + q[2], q[1] + q[3]];
      });
      if (!b && (any || !lone)) return;
      var x0 = box[0], y0 = box[1], x1 = box[0] + box[2], y1 = box[1] + box[3];
      var r = b ? [Math.max(x0, b[0] - pad), Math.max(y0, b[1] - pad),
                   Math.min(x1, b[2] + pad) - Math.max(x0, b[0] - pad),
                   Math.min(y1, b[3] + pad) - Math.max(y0, b[1] - pad)]
                : [x0 + (box[2] - c[2] * k) / 2, y0 + (box[3] - c[3] * k) / 2, c[2] * k, c[3] * k];
      back.push(draw(card, r));
    });
    return back;
  }
  // A page on a tier C panel where the template's chrome is its art
  // (Afterburn's 320 and 300s): the Page's own controls - the left rail's
  // headings and Groups - and its MainArea's are laid out in one set of
  // rows (flowRows' `page`), in main over the Rail's band where the page has
  // a Rail, else on the whole screen. They were two, the Page's over the
  // whole screen and MainArea's in main, each centred: Start's Lights
  // Heading landed on Start and Call's VTC Heading on Camera Presets
  // whatever the designer moved, and Main SD's Settings stood on its popup
  // region. By region, as the page reads: the main area's first, then the
  // side columns' left to right, each in the order it was placed. Main is at
  // the main area's own scale, which its popup region keeps (its popups').
  // What does not fit is refused: the page does not go on, as a Group does.
  // Where the seed has no standard popup (the 320's), a popup region has
  // nothing to show - each source is a page of its own there (popupPage) -
  // and is left off, named, as the region page's 320 leaves its Center.
  // `footed`: the page stands a Back in the foot's row (popupPage), so its
  // rows keep to main as a page with a Rail's do.
  function rowsPage(items, D, T, L, name, footed) {
    var dm = D.main, M = T.main, flat = [], railed = false, left = [], warns = [];
    var bare = (T.kinds || {}).popup === false;
    function take(c) {
      if (bare && c.kind === 'popupregion') {
        left.push(nameOf(c));
        warns.push(name + "'s " + nameOf(c) + ' is left off the ' + T.model + ' - its seed has no standard popup, '
                   + 'and each source is a page of its own');
        return;
      }
      flat.push(c);
    }
    items.forEach(function (it) {
      if (it.kind === 'mainarea') {
        itemsOf(it.comp.props.children, [dm[2], dm[3]]).forEach(function (c) {
          if (c.rect) c.rect = [c.rect[0] + dm[0], c.rect[1] + dm[1], c.rect[2], c.rect[3]];
          take(c);
        });
      } else {
        if (it.kind === 'rail') railed = true;
        take(it);
      }
    });
    function region(it) {
      var cx = it.rect[0] + it.rect[2] / 2;
      return cx < dm[0] ? 1 : cx > dm[0] + dm[2] ? 2 : 0;
    }
    var box = (railed || footed) && T.rail ? M : [0, 0, T.size[0], T.size[1]];
    var R = flowRows(flat, [0, 0, dm[2], dm[3]], T, L, [0, 0, M[2], M[3]], name, region, true, box[3]);
    // Said as the README says it (Every panel the room has, Kind): 'needs 188
    // px of a TLP320M's 190' did not fit, its 2 px clear of main's top and
    // foot not counted. Where a side column's rows stood beside others' and
    // it still does not fit, both: a designer counting rows one under another
    // from the README, and trimming to the smaller number, was still refused.
    var room = box[3] - 2 * R.tight, where = box === M ? 'main' : 'screen';
    if (R.total > room) {
      R.probs.push(name + "'s rows need " + (R.before > R.total
        ? Math.round(R.before) + ' px of the ' + room + ' a ' + T.model + "'s " + where + ' holds, one under '
          + 'another, and ' + Math.round(R.total) + " with a side column's beside another's"
        : Math.round(R.total) + ' px of the ' + room + ' a ' + T.model + "'s " + where + ' holds') + ' - it does not fit');
    }
    var put = placeRows(R, R.laid, box, Math.round(Math.max(R.tight, (box[3] - R.total) / 2)));
    // Each Line across the gap it stands in, centred there, as wide as it
    // scales to: over the first row in the room it keeps above it, under the
    // last in the room below.
    var ruled = [], W = M[2] - 2 * R.pad;
    function draw(rs, y) {
      rs.forEach(function (ru) {
        var t = R.thick(ru), w = Math.min(W, Math.ceil(ru.rect[2] * R.k));
        ruled.push(placeHost(ru.host, [box[0] + Math.round((box[2] - w) / 2), Math.round(y), w, t], 'r' + ru.i));
        y += t + R.tight;
      });
    }
    R.laid.forEach(function (line, n) {
      var prev = R.laid[n - 1];
      if (!n && line.above) draw(line.above, line.y - line.pre);
      var between = prev ? (prev.below || []).concat(line.above || []) : [];
      if (between.length) draw(between, prev.y + prev.h + (line.gap - R.stack(between)) / 2);
      if (n === R.laid.length - 1 && line.below) draw(line.below, line.y + line.h + R.tight);
    });
    var back = cardsBehind(R, put.placed, box, true, function (card, r) {
      return placeHost(card.host, r, 'card' + card.i);
    });
    // What it leaves is the template's grammar, not the designer's to change:
    // named, but it does not outline the page (`quiet`).
    return { els: back.concat(R.els, put.els, ruled), problems: R.probs, warnings: warns, quiet: warns, left: left,
             k: R.k };
  }
  // A standard popup on a tier C panel whose seed has none to clone (its
  // series' `kinds`: Afterburn's 320), where the template's chrome is its
  // art: a page of its own, named as it is, as that template gives each
  // source one (its frame's note) and the bar themes' 320 draws a source
  // popup (pagePart). What is put in it stands in rows in main, laid out from
  // the popup's own box as a page's are (rowsPage), and a Back stands at the
  // foot's left, where a Group's pages stand theirs and in their words, going
  // back to the page whose button shows it - which only the translator knows
  // (`back`). Kept a popup, round four's revised Afterburn room showed its
  // sources from the Sources Group's own pages, which hold no reference to
  // their group - and the 320's seed had nothing to clone them from: the ID
  // map refused all four.
  function popupPage(items, D, T, L, name, size) {
    var out = rowsPage(items, Object.assign({}, D, { main: [0, 0, size[0], size[1]] }), T, L, name, true);
    var M = T.main, foot = T.rail || [0, M[1] + M[3], T.size[0], T.size[1] - M[1] - M[3]];
    var f = font({}, P.defaults.button.type, Object.assign({}, L, { k: out.k }));
    var w = Math.max(T.touch, Math.ceil(textWidth('Back', f.css) + 24));
    var r = [foot[0] + T.gap, foot[1] + Math.round((foot[3] - T.touch) / 2), w, T.touch];
    out.els = out.els.concat([drawnAt(Button, { name: name + ' Back', derived: true, text: 'Back', back: true,
                                                does: 'Goes back to the page that shows ' + name + '.' }, r, 'back')]);
    return out;
  }
  // A bar theme's page on a tier C panel (the 320), as Extron's own 320
  // templates draw one: the page's header bar is the title strip above the
  // series' main region - 36 px on Mach's, Shockwave's and Turbulence's -
  // with the labels drawn on it where they fit there, and everything else -
  // the page's own controls, its MainArea's and its Rail's, since the 320 has
  // no rail - reflows in rows in design order in main. Rows one screen cannot
  // hold go on over pages of their own (Home 2, Home 3), each under the
  // strip, with Previous and Next at main's foot, as a Group's pages do. A
  // row never splits, and a heading goes on with the row it heads (flowRows).
  // Extron's own Mach 320 spreads a room over twelve pages
  // this way; the round-three rooms needed 201 to 359 px of its 240.
  function overPages(items, D, T, L, name) {
    var dw = D.size[0], M = T.main, sw = T.size[0];
    var strip = [0, 0, sw, M[1]];
    // The scale the page's rows are laid out at, as flowRows lays them.
    var R0k = fit([0, 0, dw, D.size[1]], [0, 0, M[2], M[3]]).s;
    // Play: Next and Previous show a page by setting the one shown.
    var shown = { set: null };
    function shower(p) { return function () { if (shown.set) shown.set(p); }; }
    // The MainArea's and the Rail's children, where the page drew them: a
    // Rail's need no place of their own, so they stack in its band in order.
    var flat = [];
    items.forEach(function (it) {
      if (it.kind === 'mainarea' && D.main) {
        itemsOf(it.comp.props.children, [D.main[2], D.main[3]]).forEach(function (c) {
          if (c.rect) c.rect = [c.rect[0] + D.main[0], c.rect[1] + D.main[1], c.rect[2], c.rect[3]];
          flat.push(c);
        });
      } else if (it.kind === 'rail') {
        var band = D.rail || it.rect || [0, 0, dw, D.size[1]];
        var row = (D.rail_axis || 'column') === 'row', at = row ? band[0] : band[1];
        React.Children.toArray(it.comp.props.children).forEach(function (host) {
          if (!React.isValidElement(host)) return;
          var c = itemsOf([host])[0], st = host.props.style || {};
          var w = len(st.width, band[2]), ht = len(st.height, band[3]);
          w = w == null ? (row ? T.touch / R0k : band[2]) : w;
          ht = ht == null ? (row ? band[3] : T.touch / R0k) : ht;
          c.rect = row ? [at, band[1] + (band[3] - ht) / 2, w, ht] : [band[0] + (band[2] - w) / 2, at, w, ht];
          at += (row ? w : ht) + 1;
          flat.push(c);
        });
      } else {
        flat.push(it);
      }
    });
    // The header: a Panel across the page's top, ending above main.
    var head = null;
    flat.forEach(function (it) {
      var r = it.rect;
      if (!head && it.kind === 'panel' && r && r[1] <= 1 && r[2] >= 0.9 * dw && D.main && r[1] + r[3] <= D.main[1] + 2) head = it;
    });
    // Its labels, in the strip where they fit across it at the panel's type.
    var Lk = Object.assign({}, L, { k: R0k });
    var titles = [], widths = [];
    if (head) {
      var hb = head.rect[1] + head.rect[3];
      titles = flat.filter(function (it) {
        return (it.kind === 'label' || it.kind === 'clock') && it.rect && it.rect[1] + it.rect[3] / 2 < hb;
      }).sort(function (a, b) { return a.rect[0] - b.rect[0]; });
      var widths = titles.map(function (it) {
        var g = font(it.props || {}, it.kind === 'clock' ? P.defaults.clock.type : P.defaults.label.type, Lk);
        var text = it.kind === 'clock' ? clockSample(CLOCK_FORMATS[(it.props || {}).format || 'time'] || (it.props || {}).format)
                                       : textOf((it.props || {}).children, (it.props || {}).text);
        return Math.ceil(textWidth(text, g.css) + 8);
      });
      var across = widths.reduce(function (s, w) { return s + w; }, 0) + T.gap * Math.max(0, titles.length - 1);
      var deep = titles.every(function (it) { return needs(it, Lk)[1] <= strip[3]; });
      if (!titles.length || across > sw - 2 * T.gap || !deep) { titles = []; widths = []; }
    }
    var rest = flat.filter(function (it) { return it !== head && titles.indexOf(it) < 0; });
    // By region, as the page reads on a screen that holds a few rows: the
    // header's, main's, the side columns' left to right, then the footer's.
    // In design order alone a rail's 520 px slider beside main took main's
    // controls into its row, and they came out in the order they ran across.
    var dm = D.main;
    function region(it) {
      var cx = it.rect[0] + it.rect[2] / 2, cy = it.rect[1] + it.rect[3] / 2;
      if (cy < dm[1]) return 0;
      if (cy > dm[1] + dm[3]) return 4;
      return cx < dm[0] ? 2 : cx > dm[0] + dm[2] ? 3 : 1;
    }
    var R = flowRows(rest, [0, 0, dw, D.size[1]], T, L, [0, 0, M[2], M[3]], name, dm ? region : null);
    var nav = T.touch, room = M[3] - 2 * R.tight;
    // Into pages: all on one when they fit, else each holds what fits above a
    // row of Previous and Next.
    var total = R.laid.reduce(function (s, line, n) { return s + line.h + (n ? line.gap : 0); }, 0);
    var parts = [[]];
    if (total <= room) {
      parts[0] = R.laid;
    } else {
      var avail = room - nav - R.gap, used = 0;
      R.laid.forEach(function (line) {
        var cur = parts[parts.length - 1];
        var add = line.h + (cur.length ? line.gap : 0);
        if (cur.length && used + add > avail) {
          // A heading goes on with the row it heads, never alone at a foot.
          var head = cur.length > 1 && cur[cur.length - 1].heading ? cur.pop() : null;
          parts.push(head ? [head, line] : [line]);
          used = head ? head.h + line.gap + line.h : line.h;
          return;
        }
        cur.push(line); used += add;
      });
      parts.forEach(function (lines, p) {
        var deepest = lines.reduce(function (s, line, n) { return s + line.h + (n ? line.gap : 0); }, 0);
        if (deepest > avail) {
          R.probs.push(name + (p ? ' ' + (p + 1) : '') + ' has a row ' + Math.round(deepest) + ' px deep, more than the '
                       + Math.round(avail) + " a page of a " + T.model + ' holds above Previous and Next - it does not fit');
        }
      });
    }
    function partName(p) { return p ? name + ' ' + (p + 1) : name; }
    var navFont = font({}, P.defaults.button.type, Lk);
    function navW(word) { return Math.max(T.touch, Math.ceil(textWidth(word, navFont.css) + 24)); }
    // The strip on each page: the header and its labels, on a later page a
    // copy the layout derived.
    function stripOf(p) {
      var els = [];
      function put(it, r, key) {
        els.push(p ? React.cloneElement(it.host, { key: key, style: cell(r) }, React.cloneElement(it.comp, { derived: true }))
                   : placeHost(it.host, r, key));
      }
      if (head) put(head, strip, 'head' + p);
      var x = Math.round((sw - (widths.reduce(function (s, w) { return s + w; }, 0) + T.gap * (titles.length - 1))) / 2);
      titles.forEach(function (it, j) { put(it, [x, 0, widths[j], strip[3]], 'title' + p + '-' + j); x += widths[j] + T.gap; });
      return els;
    }
    var drawn = {};
    var pages = parts.map(function (lines, p) {
      var deep = lines.reduce(function (s, line, n) { return s + line.h + (n ? line.gap : 0); }, 0);
      var hold = parts.length > 1 ? room - nav - R.gap : room;
      var put = placeRows(R, lines, [M[0], M[1], M[2], M[3]], Math.round(Math.max(R.tight, (hold - deep) / 2)));
      // The first page a card is drawn on has the card; a later one, a copy.
      var back = cardsBehind(R, put.placed, M, p === 0, function (card, r) {
        if (!drawn[card.i]) { drawn[card.i] = true; return placeHost(card.host, r, 'card' + card.i); }
        return React.cloneElement(card.host, { key: 'card' + p + '-' + card.i, style: cell(r) },
                                  React.cloneElement(card.comp, { derived: true }));
      });
      var els = stripOf(p).concat(back, put.els);
      if (parts.length > 1) {
        var ny = M[1] + M[3] - R.tight - nav;
        if (p > 0) {
          els.push(h('div', { key: 'prev' + p, style: cell([M[0] + T.gap, ny, navW('Previous'), nav]) },
                     h(Button, { name: partName(p) + ' Previous', derived: true, text: 'Previous', goes: partName(p - 1),
                                 onPress: shower(p - 1) })));
        }
        if (p < parts.length - 1) {
          var wn = navW('Next');
          els.push(h('div', { key: 'next' + p, style: cell([M[0] + M[2] - T.gap - wn, ny, wn, nav]) },
                     h(Button, { name: partName(p) + ' Next', derived: true, text: 'Next', goes: partName(p + 1),
                                 onPress: shower(p + 1) })));
        }
      }
      return els;
    });
    var els = R.els.concat(pages[0]);
    if (pages.length > 1) {
      els.push(h(Parts, { key: 'parts', names: pages.map(function (_, p) { return partName(p); }), pages: pages, shown: shown }));
    }
    return { els: els, problems: R.probs, k: R.k };
  }
  // The pages a page goes on over, each laid over it as a page of its own
  // that wears the page's look; its Groups' pages come Back to it.
  function Parts(props) {
    var L = React.useContext(Ctx);
    var st = React.useState(0);
    props.shown.set = st[1];
    var forced = typeof window !== 'undefined' && window.__GDL_SHOW ? String(window.__GDL_SHOW) : null;
    var cur = st[0];
    props.names.forEach(function (n, p) { if (forced === n) cur = p; });
    return props.pages.slice(1).map(function (els, j) {
      var p = j + 1, name = props.names[p];
      var look = Object.assign({ kind: 'page', name: name, host: L.pageName || 'Page', size: L.panel.size },
                               L.pageLook || {});
      return h(Ctx.Provider, { key: 'part' + p, value: Object.assign({}, L, { pageName: name }) },
        h('div', { 'data-gdl-part': JSON.stringify(look),
                   style: Object.assign({ position: 'fixed', left: 0, top: 0, width: L.panel.size[0] + 'px',
                                          height: L.panel.size[1] + 'px', zIndex: 5,
                                          visibility: cur === p ? 'visible' : 'hidden' }, L.pageStyle || {}) }, els));
    });
  }
  function layout(items, D, frame, L, where, cut) {
    var flow = L.panel.tier === 'C' && L.model !== L.designModel;
    return flow ? flowLayout(items, D, L.panel, L, frame, where) : scaleLayout(items, D, L.panel, L, frame, cut);
  }
  function outlined(style, probs) {
    return probs.length ? Object.assign({}, style, { outline: '2px dashed #FF00FF', outlineOffset: '-2px' }) : style;
  }

  // -- Page: the artboard's one root ----------------------------------------
  function themeOf(id) {
    for (var i = 0; i < P.themes.length; i++) if (P.themes[i].id === id) return P.themes[i];
    return P.themes[0];
  }
  function Page(props) {
    var kind = props.kind === 'popup' || props.kind === 'modal' ? props.kind : 'page';
    // A theme is the template's pairing of background image and accent scheme
    // (Afterburn's four); `scheme` alone swaps the accent, as Extron allows.
    var theme = themeOf(props.theme);
    var scheme = schemeId(props.scheme || theme.scheme);
    var colors = schemeColors(scheme);
    var listed = words(props.panels);
    // A region page draws from a panel's frame: listing none, the system's own.
    // So does a source popup and a window, and a `role` is checked there - with
    // none listed, a source popup came out at the system's popup size with no
    // title, and a window with no band, title or Close.
    var asked = listed.length || props.preview || forcedPanel() || regionsIn(props.children).length
      || barFrames() && (props.role != null && String(props.role) !== '' || framedRole(props, kind));
    if (asked) {
      var designModel = listed[0] || P.model;
      var model = forcedPanel() || props.preview || designModel;
      var unknown = [];
      listed.concat(props.preview ? [props.preview] : [], [model]).forEach(function (m) {
        if (!MODELS[m] && unknown.indexOf(m) < 0) unknown.push(m);
      });
      var problems = unknown.map(function (m) {
        return m + ' is not a panel the ' + P.template + ' design system can draw'
          + (Object.keys(MODELS).length ? ' - no ' + P.template + ' series serves it' : ' yet - it draws one panel');
      });
      if (MODELS[designModel] && MODELS[model]) {
        return panelPage(props, kind, theme, scheme, colors, listed, designModel, model, problems);
      }
    }
    // The background image is a page's: a popup is a card over one, and a
    // modal shows the page beneath.
    var own = P.models && P.models[P.model];
    var image = kind === 'page' && P.backdrops
      ? (own && P.backdrops[own.series + '|' + theme.id]) || P.backdrops[theme.id] : null;
    var full = kind !== 'popup';
    var w = Number(props.width) || (full ? P.size[0] : P.popup[0]);
    var ht = Number(props.height) || (full ? P.size[1] : P.popup[1]);
    // Build draws every modal popup as the page beneath under a black scrim,
    // whatever background it is given, so a modal shows that and carries none.
    var bg = kind === 'modal' ? null : props.background || P.defaults.page.background;
    var style = {
      position: 'relative', boxSizing: 'border-box', overflow: 'hidden',
      width: w + 'px', height: ht + 'px',
      background: kind === 'modal'
        ? 'linear-gradient(' + paint(colors, 'scrim') + ', ' + paint(colors, 'scrim') + '), '
          + paint(colors, P.defaults.page.background)
        : (image ? 'url("' + image + '") 0 0 / 100% 100% no-repeat, ' : '') + paint(colors, bg),
      color: colors.text, font: font({}, 'body').css
    };
    Object.keys(colors).forEach(function (k) { style['--' + k] = colors[k]; });
    var data = gdl({
      kind: kind === 'page' ? 'page' : 'popup', modal: kind === 'modal' || null,
      name: props.name, group: props.group, start: truthy(props.start) || null,
      reached_by: props.reachedBy, background: bg, scheme: scheme, theme: theme.id,
      background_image: kind === 'page' ? theme.image || null : null,
      template: P.template, size: [w, ht], does: props.does,
      panels: asked && listed.length ? listed : null
    });
    // `page`: drawn on a Page, which builds - not a component's own card.
    return h(Ctx.Provider, { value: { scheme: scheme, colors: colors, page: true } },
      h('div', { 'data-gdl': data, 'data-theme': theme.id, className: 'xgdl-page',
                 style: asked && problems.length ? outlined(style, problems) : style },
        props.children, asked ? problems.map(problem) : null));
  }

  // A Page derived for one of its panels: its own size, its series'
  // background, and every child laid out for it by the frame it is in.
  function panelPage(props, kind, theme, scheme, colors, listed, designModel, model, problems) {
    var D = Object.assign({ model: designModel }, MODELS[designModel]);
    var T = Object.assign({ model: model }, MODELS[model]);
    var full = kind !== 'popup';
    var dw = Number(props.width) || (full ? D.size[0] : P.popup[0]);
    var dh = Number(props.height) || (full ? D.size[1] : P.popup[1]);
    var tw = T.size[0], th = T.size[1];
    // A source popup or a window, where the template draws its bars as
    // controls (framedPart): drawn in the template's own well or window. A
    // role it does not take is named: designers leave out the Close, the
    // title and the well a role draws, and a typo drew a window with no way
    // out.
    var role = String(props.role || '').toLowerCase(), part = null;
    var framed = barFrames() && framedRole(props, kind);
    // A working page's own roles: the call mode (Main VC) and the page its
    // sources are chosen on (Main Select Source).
    var paged = kind === 'page' && PAGE_ROLES[role];
    if (barFrames() && role && !framed && !paged) {
      problems.push((props.name || 'Page') + "'s role=\"" + props.role + '" is not one a kind="' + kind + '" takes - '
                    + 'say role="source" on a kind="popup" (or "dialer", the call\'s dialer), role="call" or '
                    + '"select" on a page with regions, or role="settings", "help", "confirm" or "wait" on a '
                    + 'kind="modal"');
    }
    if (framed) {
      part = framedPart(props, role, kind, D, T, props.name || 'Page');
      if (part.problem) {
        problems.push(part.problem);
        part = null;
      } else if (part.dsize) {
        // A source popup is its own panel's popup region, the 725's from the
        // 725's template - drawn at the drawn panel's.
        dw = part.dsize[0]; dh = part.dsize[1];
      }
    }
    // A standard popup where the panel's seed has none to clone (its series'
    // `kinds`: Afterburn's 320) and the template's chrome is its art: a page
    // of its own (popupPage), as that template gives each source one.
    var alone = kind === 'popup' && !part && P.layout.bars !== 'controls' && T.tier === 'C' && model !== designModel
      && T.main && D.main && (T.kinds || {}).popup === false;
    // One left over - a bar theme's roleless popup on the same panel - has
    // nothing to be built from: refused here by name, where the build would
    // stop at "donor project has no standard popup to clone" on Windows.
    if (kind === 'popup' && !part && !alone && (T.kinds || {}).popup === false) {
      problems.push((props.name || 'Page') + ' is a standard popup, which the ' + T.model + "'s seed cannot build - "
                    + (barFrames() ? 'say role="source" and the ' + T.model + ' draws it as a page, as it draws every source'
                                   : 'make it a kind="modal" or a kind="page"'));
    }
    if (part && part.size) {
      tw = part.size[0]; th = part.size[1];
    } else if (!full && !alone) {
      // A popup shows in a region of the main area, so it scales as that does.
      var sm = fit(D.main, T.main).s;
      tw = Math.round(dw * sm); th = Math.round(dh * sm);
    }
    // At the page's own scale from the start: needs() measures the page's own
    // children - a modal's title and steps - at this type before layout ends.
    // `within`: what the page is - page, modal or popup. A Group in a modal
    // or popup cannot page as popups: a popup is shown only from a page.
    var L = { scheme: scheme, colors: colors, aware: true, panel: T, design: D, model: model,
              designModel: designModel, tier: T.tier, k: fit([0, 0, dw, dh], [0, 0, tw, th]).s, within: kind };
    // A region page: its regions draw from this panel's own series' frame.
    // One missing a region the template always draws is named, never
    // refused (the owner's call, 2026-10-22); a splash page needs none.
    var regs = regionsIn(props.children), warnings = [], pname = props.name || 'Page';
    // A popup in the Center's group (Sources, its default) with no role
    // scales with main (above), where the Center is each panel's own region:
    // on another panel it can come out larger than the region it shows in -
    // Mach's 720 drew a 564x311 Doc Cam in its 554x324 region.
    var CF = barFrames() && kind === 'popup' && !role ? frameFor(T) : null;
    if (CF && String(props.group || '').toLowerCase() === 'sources'
        && (tw > CF.center.region[2] || th > CF.center.region[3])) {
      warnings.push(pname + ' comes out ' + tw + 'x' + th + ' on a ' + model + ', larger than the '
                    + CF.center.region[2] + 'x' + CF.center.region[3] + ' popup region its group shows in - say '
                    + 'role="source" and it is that region on every panel');
    }
    if (barFrames() && paged && !regs.length) {
      problems.push(pname + "'s role=\"" + role + '" is a working page\'s - draw it in its regions (Header, LeftRail, '
                    + 'RightRail, Footer, Center)');
    }
    if (regs.length) {
      var F = kind === 'page' ? frameFor(T, paged ? role : null) : null;
      // A hub draws the same regions in its own grammar (planHub), and the
      // 320 in its own (planPages).
      var HF = kind === 'page' && !F ? hubFor(T) : null;
      var PF = kind === 'page' && !F && !HF ? pagesFor(T) : null;
      if (kind !== 'page') {
        L.regionRefused = true;
        problems.push(pname + ' is a ' + kind + ' and holds a ' + REGION_NAMES[regs[0].kind]
                      + " - the regions are a working page's");
      } else if (!F && !HF && !PF) {
        L.regionRefused = true;
        problems.push(pname + ' uses the region frame, which the ' + model + ' does not draw yet');
      } else {
        L.region = F ? { F: F } : HF ? { F: HF, hub: true } : { F: PF, pages: true };
        L.region.role = paged ? role : null;
        // The page a bar series chooses its sources on is Mach's and
        // Turbulence's Main Select Source; Shockwave's bar templates draw
        // none (a hub's and the 320's own grammar starts from one).
        if (F && role === 'select' && !F.choose) {
          problems.push(pname + "'s role=\"select\" is a page the " + model + "'s template does not draw - "
                        + P.template + " chooses sources by its Header's tabs alone there");
        }
        if (!truthy(props.splash)) {
          REGION_ORDER.forEach(function (k) {
            if (!regs.some(function (it) { return it.kind === k; })) {
              warnings.push(pname + ' has no ' + REGION_NAMES[k] + ' - the ' + P.template
                            + ' working page always draws one');
            }
          });
        }
      }
    }
    // A page's own children go through both panels' bands where the template
    // draws its bars as controls (`layout.bars`: Mach, Shockwave, Turbulence),
    // on a panel other than the one drawn - there they stay as drawn.
    // Afterburn's chrome is its background art, and its pages' own children
    // - a modal's card - scale whole about the screen's centre, as Extron's
    // own 525 centres its modals. A popup's, shown in a region of main, at
    // main's scale.
    var bands = full && model !== designModel && P.layout.bars === 'controls' && D.main && T.main;
    var own = bands ? itemsOf(props.children, [dw, dh]) : [];
    // The depth a band beside main on axis `a` needs for what it holds: the
    // touch minimum where a finger presses a control there, and a Group's own
    // cells on this panel - Shockwave's source tabs in its header grew to
    // 94 px in a band cut 55 deep, and centred on it stood 19 px above the
    // screen.
    function touchIn(a, lo, hi) {
      return own.reduce(function (most, it) {
        var c = it.rect ? it.rect[a] + it.rect[a + 2] / 2 : -1;
        if (c < lo || c > hi) return most;
        if (it.kind === 'button' || it.kind === 'slider') return Math.max(most, T.touch);
        if (it.kind === 'group' && it.comp) {
          var sg = segments(it.comp.props, L);
          return Math.max(most, T.touch, a ? sg.ch : sg.cw);
        }
        return most;
      }, 0);
    }
    var cut = bands ? {
      from: [[0, D.main[0], D.main[0] + D.main[2], dw], [0, D.main[1], D.main[1] + D.main[3], dh]],
      to: [hubBands(D.main[0], D.main[0] + D.main[2], dw, T.main[0], T.main[0] + T.main[2], tw, L.k,
                    touchIn(0, 0, D.main[0]), touchIn(0, D.main[0] + D.main[2], dw)),
           hubBands(D.main[1], D.main[1] + D.main[3], dh, T.main[1], T.main[1] + T.main[3], th, L.k,
                    touchIn(1, 0, D.main[1]), touchIn(1, D.main[1] + D.main[3], dh))],
      // A hub: its main reaches an edge the drawn panel's does not, so its
      // bars are bands carved from main for what they hold (hubBands).
      hub: (T.main[1] < 1 && D.main[1] >= 1) || (T.main[1] + T.main[3] > th - 1 && D.main[1] + D.main[3] <= dh - 1)
           || (T.main[0] < 1 && D.main[0] >= 1) } : null;
    // What a MainArea and a column Rail lay out keeps to what those bands
    // leave - on a hub, the main region less the bands carved from it, and
    // the menu bar between the header and the footer - not under the bars.
    // Elsewhere the bands are the panel's own, and this changes nothing.
    if (cut && T.tier !== 'C') {
      var bx = cut.to[0], by = cut.to[1], col = T.rail && (T.rail_axis || 'column') !== 'row';
      // What the bars hold wins over main (hubBands): two deep ones can leave
      // it less than a control, or nothing.
      if (bx[2] - bx[1] < T.touch || by[2] - by[1] < T.touch) {
        problems.push('the bars a ' + model + ' carves from its main leave it ' + (bx[2] - bx[1]) + 'x'
                      + (by[2] - by[1]) + ', less than a control - give the bars less to hold there');
      }
      var r0 = col ? Math.max(T.rail[1], by[1]) : 0, r1 = col ? Math.min(T.rail[1] + T.rail[3], by[2]) : 0;
      L.panel = Object.assign({}, T, {
        main: [bx[1], by[1], bx[2] - bx[1], by[2] - by[1]],
        rail: col ? [T.rail[0], r0, T.rail[2], r1 - r0] : T.rail });
    }
    // A bar theme's page on the 320: under a title strip, over as many pages
    // as its rows need (overPages).
    var over = kind === 'page' && T.tier === 'C' && model !== designModel && P.layout.bars === 'controls' && T.main
      && !L.region;
    // One whose chrome is its art (Afterburn's): in one set of rows (rowsPage).
    var rowed = kind === 'page' && T.tier === 'C' && model !== designModel && P.layout.bars !== 'controls'
      && T.main && D.main && !L.region && !part;
    var kids = itemsOf(props.children, [dw, dh]);
    // A dialer's controls are the template's keys (dialerPart): what the
    // designer puts in it is named, not drawn over them.
    if (part && part.items) {
      kids.forEach(function (it) {
        problems.push(nameOf(it) + ' in ' + pname + ': a dialer (role="dialer") draws the template\'s keys - put '
                      + 'nothing in it');
      });
      kids = itemsOf(part.items, [dw, dh]);
    }
    // A page the 320 draws a window or a source as: the strip and its
    // columns (pagePart), its Groups paging as a page's do.
    if (part && part.lay || alone) L.within = 'page';
    var out = part && part.lay ? part.lay(kids, L)
      : part ? framedLayout(kids, part, L)
      : over ? overPages(kids, D, T, L, props.name || 'Page')
      : alone ? popupPage(kids, D, T, L, props.name || 'Page', [dw, dh])
      : rowed ? rowsPage(kids, D, T, L, props.name || 'Page')
      // A page's own child grown at the screen's edge keeps to the page, as
      // one in a bar theme's MainArea does (keepIn): Build moves a control
      // that crosses its page's edge, and Afterburn's left rail, flush at x
      // 0, grew about its centre to x -2 on the 725 - its Start's Lights to
      // -10 on the 1035 it was drawn on.
      : layout(kids, [0, 0, dw, dh], [0, 0, tw, th], Object.assign({}, L, { keepIn: true }), props.name || 'the page',
               cut);
    L.k = out.k;
    problems = problems.concat(out.problems);
    if (out.warnings) warnings = warnings.concat(out.warnings);
    var left = (out.left || []).slice(), chromeNotes = [];
    if (part && !part.lay) {
      // The template's chrome over the page and under what was put in it.
      var drawn = part.chrome(L, kids.length > 0);
      // What was put in it clear of the title the template draws at its top:
      // laid out in Turbulence's whole region, a Doc Cam's headings ran into
      // the title of an empty source, 40 px lower than one with controls.
      var tr = drawn.title ? [drawn.title[0] + 1, drawn.title[1] + 1, drawn.title[2] - 2, drawn.title[3] - 2] : null;
      (tr && out.placed || []).forEach(function (q) {
        if (overlaps(q.r, tr)) {
          warnings.push(nameOf(q.it) + ' stands under ' + pname + "'s title on a " + model + ' - keep what is put in '
                        + (role === 'source' ? 'a source popup' : 'a window') + ' clear of the title its template '
                        + 'draws at its top');
        }
      });
      out = { els: drawn.els.concat(out.els), problems: [], k: out.k };
      problems = problems.concat(drawn.problems);
      // What the chrome could not draw for want of a word - a source naming
      // no device its template pictures - is said, and does not outline the
      // page: the place stays empty, as it always has.
      chromeNotes = drawn.notes || [];
      warnings = warnings.concat(chromeNotes);
    }
    // What a hub's or a 320's template has no place for (its clock, the
    // Center's popup region, the Header's ends) is named - a warning, and
    // the page's `left` - but is the template's grammar, not the designer's
    // to change: it does not outline the page as a problem (`quiet`), or
    // every correct region page there looked broken.
    var quiet = chromeNotes.concat(out.quiet || []);
    if (L.region && (L.region.hub || L.region.pages)) {
      var hub = (L.region.hub ? planHub : planPages)(regs, L, pname);
      out = { els: out.els.concat(hub.els), problems: [], k: out.k };
      problems = problems.concat(hub.probs);
      warnings = warnings.concat(hub.warns);
      quiet = quiet.concat(hub.warns);
      left = left.concat(hub.left);
    } else if (L.region) {
      var planned = planRegions(regs, L, pname);
      L.region.plans = planned.plans;
      L.region.count = planned.count;
      problems = problems.concat(planned.probs);
    }
    // A hub draws a settings window as a popup of main's group (`part.popup`):
    // its own fill where the template gives it one (Mach's #303030). The
    // 320 draws a source or a window as a page (`part.page`), on the photo
    // or, where its template's is on the page's own ground (Mach's
    // question, on #303030), on that.
    var asPage = part && part.page || alone;
    var asPopup = part && part.popup, shownKind = asPage ? 'page' : asPopup ? 'popup' : kind;
    // A hub's popup stands on the page's photo where its template's do
    // (regions.hub.popup.photo: Shockwave's and Turbulence's), stretched to
    // the popup as the page's is to the page.
    var onPhoto = shownKind === 'popup' && part && part.hub && (HD.popup || {}).photo;
    var bgArt = shownKind === 'page' && !(part && part.page && !part.art) || onPhoto
      ? (T.backgrounds || {})[theme.id] || null : null;
    var image = bgArt && P.backdrops ? P.backdrops[T.series + '|' + theme.id] : null;
    // A source popup has no fill of its own: the page shows through, as through the template's own.
    var bg = shownKind === 'modal' ? null : asPopup ? props.background || asPopup.background || 'none'
      : props.background || (part && (role === 'source' || role === 'dialer') && !asPage ? 'none' : P.defaults.page.background);
    var style = {
      position: 'relative', boxSizing: 'border-box', overflow: 'hidden',
      width: tw + 'px', height: th + 'px',
      background: shownKind === 'modal'
        ? 'linear-gradient(' + paint(colors, 'scrim') + ', ' + paint(colors, 'scrim') + '), '
          + paint(colors, P.defaults.page.background)
        : (image ? 'url("' + image + '") 0 0 / 100% 100% no-repeat, ' : '') + paint(colors, bg),
      color: colors.text, font: font({}, 'body', L).css
    };
    Object.keys(colors).forEach(function (k) { style['--' + k] = colors[k]; });
    // What a Group's pages on a small panel wear: this page's own look.
    L.pageName = props.name || 'Page';
    L.pageStyle = { background: style.background, color: style.color, font: style.font };
    L.pageLook = { background: bg, theme: theme.id, scheme: scheme,
                   background_image: bgArt ? bgArt.image : null, background_file: bgArt ? bgArt.file : null };
    var data = gdl({
      kind: shownKind === 'page' ? 'page' : 'popup', modal: shownKind === 'modal' || null,
      name: props.name, group: asPage ? null : asPopup ? asPopup.group : props.group || (part && (role === 'source' || role === 'dialer') ? 'Sources' : null),
      start: truthy(props.start) || null, left: left.length ? left : null,
      // A hub's source popup or settings popup (hubPart): shown from the
      // Select a Source a region page derives, and in its group.
      hub: part && part.hub || null, main_group: asPopup && asPopup.main || null,
      reached_by: props.reachedBy, background: bg, scheme: scheme, theme: theme.id,
      background_image: bgArt ? bgArt.image : null, background_file: bgArt ? bgArt.file : null,
      template: P.template, size: [tw, th], does: props.does,
      panel: model, panels: listed.length ? listed
        : (regs.length || barFrames() && (role || framed)) && !props.preview && !forcedPanel() ? null : [designModel],
      tier: T.tier, seed: T.seed,
      borders: T.borders && Object.keys(T.borders).length ? T.borders : null,
      derived: true
    });
    return h(Ctx.Provider, { value: L },
      h('div', { 'data-gdl': data, 'data-theme': theme.id, 'data-panel': model, className: 'xgdl-page',
                 style: outlined(style, problems.concat(warnings.filter(function (w) { return quiet.indexOf(w) < 0; }))) },
        out.els, problems.map(problem), warnings.map(warning)));
  }

  // -- MainArea: the template's own main region, for layout -----------------
  // Afterburn's is the squircle its background image draws. It paints
  // nothing and is not a control: its children are placed inside it, with
  // absolute positions relative to it or with flex and grid. On a Page that
  // lists panels it is that panel's own main region - the series' squircle,
  // measured off its art - and its children are laid out for it.
  function MainArea(props) {
    var L = React.useContext(Ctx);
    if (L && L.aware) {
      var D = L.design.main, T = L.panel.main;
      // A control grown to the panel's touch minimum stays in main rather
      // than reach under a bar (a 60 px button flush with main's bottom, 104
      // px on the 535, ended 25 px into its footer) - or off the screen,
      // where main reaches its edge: Afterburn's sources Group, grown to the
      // 525's tiles about its centre, stood 17 px above the screen.
      var Lm = Object.assign({}, L, { keepIn: true });
      var out = layout(itemsOf(props.children, [D[2], D[3]]), [0, 0, D[2], D[3]], [0, 0, T[2], T[3]], Lm,
                       'the main area');
      var st = { position: 'absolute', left: T[0] + 'px', top: T[1] + 'px', width: T[2] + 'px',
                 height: T[3] + 'px', boxSizing: 'border-box' };
      return h(Ctx.Provider, { value: Object.assign({}, L, { k: out.k }) },
        h('div', { className: 'xgdl-main', style: outlined(st, out.problems) },
          out.els, out.problems.map(problem)));
    }
    var m = (P.layout && P.layout.main) || [0, 0, P.size[0], P.size[1]];
    var style = Object.assign({ position: 'absolute', left: m[0] + 'px', top: m[1] + 'px',
                                width: m[2] + 'px', height: m[3] + 'px', boxSizing: 'border-box' },
                              props.style || {});
    return h('div', { className: 'xgdl-main', style: style }, props.children);
  }

  // -- Rail: the side column of the template's system controls ---------------
  // Volume, mute, help and power, stacked in the band the series leaves
  // beside its main region (Afterburn's right rail) - or, where there is no
  // room beside it, below it, running across (the 320's footer). Its children
  // need no positions: each takes what it needs on the panel, a slider or
  // level the rest. Without panels, a column filling the Rail's own box.
  function Rail(props) {
    var L = React.useContext(Ctx);
    var items = itemsOf(props.children);
    if (!(L && L.aware)) {
      return h('div', { className: 'xgdl-rail',
                        style: { position: 'absolute', inset: 0, display: 'flex', flexDirection: 'column',
                                 alignItems: 'center', gap: P.spacing + 'px', padding: P.spacing + 'px',
                                 boxSizing: 'border-box' } }, props.children);
    }
    var T = L.panel, band = T.rail;
    if (!band) {
      return h('div', { className: 'xgdl-rail' }, problem('the ' + T.model + ' has no rail band', 'rail'));
    }
    var out = railLayout(items, L);
    var st = { position: 'absolute', left: band[0] + 'px', top: band[1] + 'px', width: band[2] + 'px',
               height: band[3] + 'px', boxSizing: 'border-box' };
    return h(Ctx.Provider, { value: Object.assign({}, L, { k: out.k }) },
      h('div', { className: 'xgdl-rail', style: outlined(st, out.problems) },
        out.els, out.problems.map(problem)));
  }
  function railLayout(items, L) {
    var T = L.panel, band = T.rail, col = (T.rail_axis || 'column') !== 'row';
    var along = col ? band[3] : band[2], cross = col ? band[2] : band[3];
    var Dr = L.design.rail, dcol = (L.design.rail_axis || 'column') !== 'row';
    var k = Dr ? Math.min(along / (dcol ? Dr[3] : Dr[2]), cross / (dcol ? Dr[2] : Dr[3])) : 1;
    if (L.model === L.designModel) k = 1;
    var Lk = Object.assign({}, L, { k: k });
    var t = T.touch, gap = T.gap;
    var padC = Math.floor(Math.max(0, Math.min(gap, (cross - t) / 2))), size = cross - 2 * padC;
    var probs = [], slots = [];
    items.forEach(function (it, i) {
      var p = it.props || {};
      if (it.kind === 'slider' && T.kinds && T.kinds.slider === false) {
        slots.push({ it: it, i: i, role: 'Down', along: t, cross: t });
        slots.push({ it: it, i: i, role: 'level', flex: true, cross: Math.min(size, t) });
        slots.push({ it: it, i: i, role: 'Up', along: t, cross: t });
      } else if (it.kind === 'slider' || it.kind === 'level') {
        slots.push({ it: it, i: i, role: 'host', flex: true, cross: Math.min(size, Math.max(t, 54 * k)) });
      } else if (it.kind === 'button') {
        var n = needs(it, Lk, true);
        if (p.variant === 'icon' || P.buttons[p.variant] && P.buttons[p.variant].kit && !textOf(p.children, p.text)) {
          // At the size its seed draws its variant at, where the variant has
          // one (Turbulence's ring, 100 x 100), else an icon button's 64. At a
          // generic 64 a ring looked nothing like the template's, and a
          // designer placed the rail's controls by hand instead.
          var vs = (P.buttons[p.variant] && P.buttons[p.variant].size) || [64, 64];
          var vw = Math.max(t, Math.round(vs[0] * k)), vh = Math.max(t, Math.round(vs[1] * k));
          slots.push({ it: it, i: i, role: 'host', along: col ? vh : vw, cross: col ? vw : vh });
        } else {
          var designed = it.rect ? (col ? it.rect[3] : it.rect[2]) * k : 64 * k;
          slots.push({ it: it, i: i, role: 'host', along: Math.max(col ? n[1] : n[0], designed),
                       cross: Math.max(size, col ? n[0] : n[1]) });
        }
      } else if (it.kind === 'label' || it.kind === 'clock') {
        // Read, not touched: it spans the band, where the touch padding is for
        // its neighbours. Held to it, a Volume heading overflowed every hub's
        // rail at the hub's type floor.
        var g = font(p, it.kind === 'clock' ? P.defaults.clock.type : P.defaults.label.type, Lk);
        var line = lineHeight(g.size) + 2;
        slots.push({ it: it, i: i, role: 'host',
                     along: col ? line : textWidth(textOf(p.children, p.text), g.css) + 8,
                     cross: col ? cross : line });
      } else if (it.host) {
        slots.push({ it: it, i: i, role: 'host', along: it.rect ? (col ? it.rect[3] : it.rect[2]) * k : t,
                     cross: size });
      }
    });
    slots.forEach(function (s) {
      if (s.cross > cross) probs.push((s.it.props.name || s.it.kind) + ' is ' + Math.round(s.cross)
                                       + ' px across a ' + T.model + "'s " + cross + ' px rail');
    });
    var fixed = slots.reduce(function (a, s) { return a + (s.flex ? 0 : s.along); }, 0)
      + gap * Math.max(0, slots.length - 1) + 2 * padC;
    var flexN = slots.filter(function (s) { return s.flex; }).length;
    // A slider is touched, so it is at least a touch target long; a level
    // only shows a value, and 24 px of one still reads.
    var least = slots.reduce(function (a, s) {
      return a + (!s.flex ? 0 : s.role === 'level' || s.it.kind === 'level' ? 24 : t);
    }, 0);
    var rest = along - fixed, each = flexN ? Math.floor(rest / flexN) : 0;
    if (rest < least) {
      probs.push('the rail needs ' + Math.round(fixed + least) + ' px of a ' + T.model + "'s " + along);
      each = Math.max(each, flexN ? least / flexN : 0);
    }
    var els = [], at = padC;
    slots.forEach(function (s, n) {
      var a = Math.ceil(s.flex ? each : s.along);
      var c = Math.round(Math.min(s.cross, cross));
      var r = col ? [Math.round((cross - c) / 2), at, c, a] : [at, Math.round((cross - c) / 2), a, c];
      var p = s.it.props || {}, name = p.name || 'Slider', key = 'r' + s.i + s.role;
      if (s.role === 'Up' || s.role === 'Down') {
        els.push(h('div', { key: key, style: cell(r) },
                   h(Button, { name: name + ' ' + s.role, derived: true, text: s.role === 'Up' ? '+' : '-',
                               does: (s.role === 'Up' ? 'Raises ' : 'Lowers ') + name + ' one step.' })));
      } else if (s.role === 'level') {
        els.push(h('div', { key: key, style: cell(r) },
                   h(Level, Object.assign({}, p, { orientation: col ? 'up' : 'right', fromSlider: true }))));
      } else if (s.it.comp && (s.it.kind === 'slider' || s.it.kind === 'level')) {
        els.push(React.cloneElement(s.it.host, { key: key, style: cell(r) },
                   React.cloneElement(s.it.comp, { orientation: col ? p.orientation || 'up' : 'right' })));
      } else {
        els.push(placeHost(s.it.host, r, key));
      }
      at += a + gap;
    });
    return { els: els, problems: probs, k: k };
  }

  // -- Regions: a working page in the template's own grammar ----------------
  // (docs/superpowers/specs/2026-10-22-region-frame-design.md.) Header,
  // LeftRail (holding Sections), RightRail, Footer and Center paint nothing
  // and carry no data-gdl, as MainArea and Rail do. A Page holding any of
  // them is a region page, and on each panel each region takes its band from
  // that panel's own series' measured frame (P.frames, once per series) - the
  // 725's from the 725's template, not the 1035's scaled - and places what it
  // holds by meaning: a source at the template's tab, a Section at its rail
  // group, Volume, Help and Power where its own are. What the template draws
  // and the designer does not override - its bars' surfaces, the Volume
  // heading, slider and Mute, the clock, Help and Power - the region draws
  // itself as components, so the translator sees every one (a painting
  // wrapper is refused as stray), and what it holds takes the template's
  // look where the designer gives none (the profile's `regions`). A slot
  // under the panel's touch minimum or type floor grows as needs() says and
  // keeps to its band.
  // The page plans its regions together (planRegions), once its own layout
  // has set the scale its type is drawn at: a seam between two regions'
  // controls is the page's to keep, not either region's (openSeams).
  // Hubs (the 520s and 535s) and the 320s draw their working page in another
  // grammar - a right menu bar and popups in main (planHub); a page per
  // source (planPages) - and a turned panel's frame turns the header into a
  // left band: a region page is refused there by name until it is drawn.
  var FRAMES = P.frames || {};
  var RD = P.regions || {};
  var REGION_NAMES = { header: 'Header', leftrail: 'LeftRail', rightrail: 'RightRail', footer: 'Footer',
                       center: 'Center' };
  var REGION_ORDER = ['header', 'leftrail', 'rightrail', 'footer', 'center'];
  function regionsIn(children) {
    return itemsOf(children).filter(function (it) { return REGION_NAMES[it.kind]; });
  }
  // Whether this system draws a working page from its series' frames: a
  // theme whose bars are controls (Afterburn's are its art).
  function barFrames() {
    return P.layout.bars === 'controls' && Object.keys(FRAMES).length > 0;
  }
  function frameFor(T, role) {
    var F = FRAMES[T.series];
    if (!F || T.turned || T.tier === 'C') return null;
    if (!(F.top && F.left && F.right && F.bottom && F.center)) return null;
    // A call page (role="call") is the series' call mode, Main VC: its
    // header's Share Content at the end, its left rail's VTC group and the
    // launchers under it, which hold one more than Main SD's on Mach. Its
    // tabs, right rail, footer and centre are the working page's.
    if (role === 'call' && F.call) {
      return Object.assign({}, F, { top: Object.assign({}, F.top, F.call.top), left: F.call.left, role: 'call' });
    }
    return F;
  }
  function warning(msg, key) {
    return h('i', { key: 'warning-' + key, 'data-gdl-warning': msg, style: { display: 'none' } });
  }
  // A measured #RRGGBBAA as the template's token of that color, if it has one.
  function hex8(v) {
    v = String(v || '').toUpperCase();
    return /^#[0-9A-F]{6}$/.test(v) ? v + 'FF' : v;
  }
  function tokenOf(colors, v) {
    if (!v) return null;
    var want = hex8(v), names = Object.keys(colors);
    for (var i = 0; i < names.length; i++) if (hex8(colors[names[i]]) === want) return names[i];
    return null;
  }
  function borderOf(resource) {
    var names = Object.keys(P.borders);
    for (var i = 0; i < names.length; i++) if (resource && P.borders[names[i]].resource === resource) return names[i];
    return 'none';
  }
  function sameRect(a, b) { return a && b && a[0] === b[0] && a[1] === b[1] && a[2] === b[2] && a[3] === b[3]; }
  // A region's sets are named apart from anything a designer titles:
  // gdl.spec passes over two touch targets with one `joined`, so a Section
  // called Header must not join the tabs.
  function setName(region, n) { return 'region:' + region + (n != null ? ':' + n : ''); }
  // `r` grown to `need`, the extra on the side that is free: an edge on a
  // seam (`seams`: low and high on x, then on y) stays where it is - Help
  // grows away from Power, keeping the template's 1 px between them - and an
  // edge on neither grows about the middle, as models()' legal rect does.
  // Inside `band` where it holds the size, else on the screen: Build moves a
  // control that crosses its page's edge.
  function settle(r, need, band, size, seams) {
    var out = r.slice();
    [0, 1].forEach(function (a) {
      var n = Math.ceil(Math.max(r[a + 2], need[a])), extra = n - r[a + 2];
      if (extra <= 0) return;
      var lo = seams[2 * a], hi = seams[2 * a + 1];
      var at = hi && !lo ? r[a] - extra : lo && !hi ? r[a] : r[a] - Math.floor(extra / 2);
      at = n <= band[a + 2] ? Math.min(Math.max(at, band[a]), band[a] + band[a + 2] - n)
                            : Math.min(Math.max(at, 0), size[a] - n);
      out[a] = at; out[a + 2] = n;
    });
    return out;
  }
  // Which of `r`'s edges meet another of its set (within 2 px) or its band's.
  function seamsOf(r, band, mates) {
    var s = [false, false, false, false];
    [0, 1].forEach(function (a) {
      var b = 1 - a;
      if (Math.abs(r[a] - band[a]) <= 1) s[2 * a] = true;
      if (Math.abs(r[a] + r[a + 2] - band[a] - band[a + 2]) <= 1) s[2 * a + 1] = true;
      mates.forEach(function (m) {
        if (m === r || m[b] >= r[b] + r[b + 2] || r[b] >= m[b] + m[b + 2]) return;
        if (Math.abs(m[a] + m[a + 2] - r[a]) <= 2) s[2 * a] = true;
        if (Math.abs(r[a] + r[a + 2] - m[a]) <= 2) s[2 * a + 1] = true;
      });
    });
    return s;
  }
  function overlaps(a, b) {
    return a[0] < b[0] + b[2] && b[0] < a[0] + a[2] && a[1] < b[1] + b[3] && b[1] < a[1] + a[3];
  }
  function nameOf(it) {
    var p = it.props || {};
    return p.name || textOf(p.children, p.text) || it.kind || 'a child';
  }
  function slotName(s) { return s.props.name || s.role || s.kind; }
  // A designer's states that name their states ("Off, On") under a region
  // look that draws its own of those names: each takes the look's state of
  // its name, and keeps what it says itself. Given states, unset() kept the
  // variant's alone - Mach's Share Content lit shade-on where the template's
  // lights #A82925DC, Shockwave's Make Call and Turbulence's Privacy lost
  // their lit captions. Null where the look draws no states.
  function statesOver(given, look) {
    var mine = list(given), own = look && look.states;
    if (!mine || !own) return null;
    return mine.map(function (s) {
      s = typeof s === 'string' ? { name: s } : Object.assign({}, s);
      var o = find(own, s.name);
      return o ? Object.assign({}, o, s) : s;
    });
  }
  // Props the region gives a control unless the designer set them.
  function unset(props, dflt) {
    var o = {};
    Object.keys(dflt || {}).forEach(function (k) {
      if (dflt[k] != null && (props || {})[k] == null) o[k] = dflt[k];
    });
    return o;
  }
  // A designer's control at `r`, with what the region adds.
  function hostAt(it, r, key, extra) {
    var comp = it.comp ? React.cloneElement(it.comp, extra || {}) : null;
    // One with no x-import host round it (a preview card's) takes a box.
    if (it.comp && it.host === it.comp) return h('div', { key: key, style: cell(r) }, comp);
    return comp ? React.cloneElement(it.host, { key: key, style: cell(r) }, comp)
                : React.cloneElement(it.host, { key: key, style: cell(r) });
  }
  // One the region draws itself, in a box that paints nothing.
  function drawnAt(type, props, r, key) {
    return h('div', { key: key, style: cell(r) }, h(type, props));
  }
  // What a control needs on this panel; a region's buttons fill their cell,
  // so need only their own padding round the caption.
  function needOf(kind, props, L) {
    return needs({ kind: kind, props: props }, L, true);
  }
  function isTouch(kind) { return kind === 'button' || kind === 'slider'; }
  // An indented caption centred on kit art whose icon stands at its left
  // (Mach's 1376x440 tab art): the leading spaces that start the caption 4
  // px clear of the icon in a `w` x `ht` cell, and the least width from `w`
  // up at which they and the caption fit, 4 px in from its right. The 4 px
  // also covers the caption measured before the canvas's Open Sans loads
  // (in Arial, 5% narrower).
  // `kit.icon_right` is how far across its art a kit size's icons reach
  // (Mach's: 319 of 1376, the pc glyph). At the 725's 16 pt type floor four
  // spaces in a 152 px tab ran Streaming into its glyph; the template's own
  // tabs take five at their smaller type. Null for any other caption.
  function indentFit(p, w, ht, L) {
    var V = P.buttons[p.variant] || P.buttons[P.defaults.button.variant];
    var caption = textOf(p.children, p.text);
    var img = imageOf(V, Object.assign({}, p, { __indent: null }), caption);
    var reach = img && img.caption === 'indent' && KIT && KIT.icon_right ? KIT.icon_right[img.kit] : null;
    if (!reach || !caption || (p.align || V.align || 'left') !== 'center') return null;
    var dims = String(img.kit).split('x').map(Number), f = font(p, P.defaults.button.type, L);
    var tc = textWidth(caption, f.css), sp = textWidth('          ', f.css) / 10, base = img.indent || 0;
    function spaces(W) {
      var s = Math.min(W / dims[0], ht / dims[1]), aw = dims[0] * s;
      var icon = (W - aw) / 2 + reach * aw;
      // Centred, the caption starts at (W - tc + n sp) / 2.
      return Math.max(base, Math.ceil((2 * (icon + 4) - W + tc) / sp));
    }
    for (var W = Math.ceil(w); W < w + 400; W++) {
      if (tc + spaces(W) * sp + 8 <= W) return { n: spaces(W), w: W };
    }
    return { n: spaces(w), w: Math.ceil(w) };
  }
  // A region's set of slots, each grown to what it holds needs, the set's
  // seams kept. `slots`: [{ r, kind, props, need }]. A set stays one size:
  // every touchable member grows to the most any of them (and `least`)
  // needs, so the template's uniform row or column does not come out
  // ragged - Mach 720's Lighting alone came out 92 wide among 80s. A stack
  // along `axis` (0 a row of tabs, 1 a rail group) keeps its first slot's
  // start and stands each after the one before it by the template's seam,
  // so one grown along the stack moves the rest on rather than into them:
  // the 835's 67 px touch minimum takes Mach's 60 px rail buttons, 61 apart,
  // to 68 apart. Shockwave's own Settings launchers overlap by 6 px,
  // transparent art over each other; at no seam they come out touching. Two
  // grown into each other across the stack, or a set with no axis, is
  // named: the template's places do not hold them on this panel.
  function settleSet(slots, band, L, where, axis, least) {
    var mates = slots.map(function (s) { return s.r; }), probs = [];
    var size = L.panel.size, most = (least || [0, 0]).slice();
    slots.forEach(function (s) {
      if (!s.need) s.need = needOf(s.kind, s.props, L);
      if (s.touch) most = [Math.max(most[0], s.need[0]), Math.max(most[1], s.need[1])];
    });
    slots.forEach(function (s) {
      if (s.touch) s.need = [Math.max(s.need[0], most[0]), Math.max(s.need[1], most[1])];
      s.at = settle(s.r, s.need, band, size, seamsOf(s.r, band, mates));
    });
    if (axis === 0 || axis === 1) {
      var a = axis;
      slots.slice().sort(function (p, q) { return p.r[a] - q.r[a]; }).forEach(function (s, i, order) {
        var start = s.r[a];
        if (i) {
          var prev = order[i - 1], seam = Math.max(0, s.r[a] - (prev.r[a] + prev.r[a + 2]));
          start = Math.max(start, prev.at[a] + prev.at[a + 2] + seam);
        }
        s.at[a] = start;
      });
    }
    for (var i = 0; i < slots.length; i++) {
      for (var j = i + 1; j < slots.length; j++) {
        if (overlaps(slots[i].at, slots[j].at)) {
          probs.push(where + "'s " + slotName(slots[i]) + ' and ' + slotName(slots[j]) + ' need more room than the '
                     + L.model + "'s template gives them - shorten their captions");
        }
      }
    }
    return probs;
  }
  // The template's surfaces in a band, as Panels named for the region.
  // `fit(s, i)` gives each its rect and name on this panel. A surface that
  // is art (Turbulence's header and footer, `art` in the frame) is that art,
  // stretched over the band as every Turbulence seed lays its bars out, where
  // the kit has the file and the panel's seed can clone an image; else it
  // stands as its one measured colour, the profile's `regions.bar`.
  function surfacesOf(L, list, region, fit) {
    var els = [], seen = {};
    (list || []).forEach(function (s, i) {
      var r = fit ? fit(s, i) : { rect: s.rect.slice(), name: null };
      if (!r || r.rect[2] <= 0 || r.rect[3] <= 0) return;
      var name = r.name || region + ' Bar';
      seen[name] = (seen[name] || 0) + 1;
      if (seen[name] > 1) name += ' ' + seen[name];
      if (s.art && kitHas(s.art) && imagesOn(L)) {
        els.push(drawnAt(ImageArt, { name: name, image: s.art, layout: 'stretch', derived: true }, r.rect,
                         region + 's' + i));
        return;
      }
      var fill = tokenOf(L.colors, s.fill) || (s.art && RD.bar) || P.defaults.panel.fill;
      els.push(drawnAt(Panel, { name: name, fill: fill, border: borderOf(s.border), stroke: 'none', derived: true },
                       r.rect, region + 's' + i));
    });
    return els;
  }
  // A surface kept to what the controls by it became. One that holds a
  // control (Shockwave's capsule round Room Mode and Help, a rail's art
  // round its buttons) grows to hold it as it grew. One a control stands
  // beside across the band, 2 px or less off its edge (Mach's footer strip
  // between Room Mode and Help, 1 px each side), keeps that seam to it as it
  // grew or gave way, and is as deep as it: the 725's Room Mode and Help grew
  // to 60 px and over a 57 px strip, a darker block of doubled shade standing
  // proud of it, where the template draws one flat band.
  function fitTo(slots) {
    return function (s) {
      var t = s.rect, r = t.slice();
      slots.forEach(function (c) {
        if (!c.touch || !c.at) return;
        var a = c.r, at = c.at;
        if (a[0] >= t[0] - 2 && a[1] >= t[1] - 2 && a[0] + a[2] <= t[0] + t[2] + 2 && a[1] + a[3] <= t[1] + t[3] + 2) {
          var x0 = Math.min(r[0], at[0]), y0 = Math.min(r[1], at[1]);
          r = [x0, y0, Math.max(r[0] + r[2], at[0] + at[2]) - x0, Math.max(r[1] + r[3], at[1] + at[3]) - y0];
          return;
        }
        if (Math.min(a[1] + a[3], t[1] + t[3]) - Math.max(a[1], t[1]) <= 0) return;
        var before = t[0] - (a[0] + a[2]), after = a[0] - (t[0] + t[2]);
        if (before >= 0 && before <= 2) {
          var right = r[0] + r[2];
          r[0] = at[0] + at[2] + before; r[2] = right - r[0];
        } else if (after >= 0 && after <= 2) {
          r[2] = at[0] - after - r[0];
        } else {
          return;
        }
        var top = Math.min(r[1], at[1]), bottom = Math.max(r[1] + r[3], at[1] + at[3]);
        r[1] = top; r[3] = bottom - top;
      });
      return { rect: r, name: null };
    };
  }
  function regionBox(name, els, probs) {
    return h('div', { className: 'xgdl-region xgdl-' + name.toLowerCase(), style: { display: 'contents' } },
             els, (probs || []).map(problem));
  }
  // A region with no frame to draw from: on a page refused for its panel it
  // draws nothing (the page names why); anywhere else it is named.
  function noFrame(name, L) {
    if (L && L.regionRefused) return null;
    return regionBox(name, [], [name + ' is a region of a working page - put it directly on a Page']);
  }
  function slotOf(it) { return String((it.props || {}).slot || ''); }
  function propsOf(it) { return (it.comp ? it.comp.props : it.props) || {}; }

  // Each region's plan: its touchable `slots` - each with `r` the template's
  // rect, `at` where it stands on this panel, `need` the least it can be
  // there, `set` its joined set or null - and `render`, which draws it from
  // where they came out once the page has opened its seams.
  function planHeader(props, L) {
    var R = L.region, F = R.F.top, band = F.rect, TB = F.tabs, look = (TB && TB.look) || {};
    var call = R.role === 'call', select = R.role === 'select' ? R.F.choose : null;
    var items = itemsOf(props.children), probs = [];
    var tabs = [], starts = [], ends = [], share = null;
    // Share Content, at the header's end where the call mode's template
    // stands it (the frame's `end`, role share): Main VC's, which only a
    // call page draws.
    var place = call ? ((F.end || []).filter(function (x) { return x.role === 'share'; })[0] || null) : null;
    items.forEach(function (it) {
      var s = slotOf(it);
      if (s === 'source') tabs.push(it);
      else if (s === 'start') starts.push(it);
      else if (s === 'end') ends.push(it);
      else if (s === 'share' && place && !share) share = it;
      else if (s === 'share') {
        probs.push(nameOf(it) + (place ? ' is a second Share Content - the Header has one share place'
          : " takes the Header's share place, which only a call page's template draws - give the Page "
            + 'role="call", or say slot="end"'));
      } else {
        probs.push(nameOf(it) + ' in the Header has no slot - say slot="source" for a tab, "start" or "end"'
                   + (place ? ', or "share" for Share Content' : ''));
      }
    });
    if (tabs.length && !(TB && TB.items && TB.items.length)) {
      probs.push('the ' + L.model + "'s template draws no tabs in its header");
      tabs = [];
    }
    // The page the sources are chosen on (role="select"): the header holds
    // the template's title, and the tabs are the Center's tiles (planCenter).
    if (select) {
      R.tiles = tabs;
      tabs = [];
    }
    // The template's tabs in order: its own places for as many as it draws,
    // then on at its step.
    var first = TB && TB.items ? TB.items : [];
    function tabRect(i) {
      if (i < first.length) return first[i].rect.slice();
      var last = first[first.length - 1].rect;
      return [last[0] + (i - first.length + 1) * TB.pitch, last[1], last[2], last[3]];
    }
    var offT = tokenOf(L.colors, look.off && look.off.fill), onT = tokenOf(L.colors, look.on && look.on.fill);
    var set = setName('header');
    var twins = TB && TB.twin && TB.twin.items && TB.twin.items.length ? TB.twin : null;
    var slots = tabs.map(function (it, i) {
      var p = it.props || {}, d = Object.assign({}, RD.tab || {}), s0 = null;
      var V = P.buttons[p.variant || d.variant] || P.buttons[P.defaults.button.variant];
      // The template's look where the button draws one of its own (not a
      // kit image, which has its own), unless the designer gave it one.
      if (!V.kit) {
        if (offT) d.fill = offT;
        if (look.off && !look.off.border) d.border = 'none';
        // Named as its variant names them (Off, On): on a hub the same
        // control is a Select a Source tile in the hub's own look, and the ID
        // map numbers a control's states once for every panel.
        if (onT && onT !== offT) d.states = [{ name: 'Off' }, { name: 'On', fill: onT }];
      }
      var extra = Object.assign(unset(p, d), { joined: set });
      // Where the template names its tabs by a twin (Shockwave's 1035 and
      // 1535), the tab draws no caption: its twin, drawn under its glyph
      // with its ID, says it (render).
      if (twins) {
        s0 = { caption: textOf(p.children, p.text), states: list(p.states) || V.states };
        extra.children = ''; extra.text = '';
      }
      var s = { r: tabRect(i), kind: it.kind, props: Object.assign({}, p, extra), it: it, extra: extra, set: set,
                touch: isTouch(it.kind), role: 'tab', twin: twins ? s0 : null };
      s.need = needOf(s.kind, s.props, L);
      var fit = indentFit(s.props, Math.max(s.r[2], s.need[0]), Math.max(s.r[3], s.need[1]), L);
      if (fit) s.need[0] = Math.max(s.need[0], fit.w);
      return s;
    });
    probs = probs.concat(settleSet(slots, band, L, 'the Header', 0));
    // Each caption clears its icon at the width its tab came out.
    slots.forEach(function (s) {
      var fit = indentFit(s.props, s.at[2], s.at[3], L);
      if (fit) s.extra.__indent = s.props.__indent = fit.n;
    });
    // The tabs end where the header's end chrome starts: Share Content on a
    // call page, else the bar's end. Past it the Header holds more sources
    // than this panel's does, and the template's answer is named - Mach's
    // and Turbulence's choose among more on their Main Select Source
    // (role="select"); Shockwave's bar templates draw no such page.
    var limit = share && place ? place.rect[0] : band[0] + band[2];
    var lastAt = slots.length ? slots[slots.length - 1].at : null;
    if (lastAt && lastAt[0] + lastAt[2] > limit) {
      var fit = slots.filter(function (s) { return s.at[0] + s.at[2] <= limit; }).length;
      probs.push('the Header holds ' + slots.length + ' tabs, more than the ' + L.model + "'s holds across ("
                 + fit + (share && place ? ' before its Share Content' : '') + ')' + (R.F.choose
        ? ' - choose among more on the page ' + P.template + "'s template chooses sources on: draw a Page with "
          + 'role="select" whose Header holds every source, and keep ' + fit + ' or fewer tabs here'
        : ' - ' + P.template + "'s template draws no page to choose among more there: keep " + fit
          + ' or fewer tabs here, and put the rest in a source popup of their own as keys'));
    }
    // At the bar's ends, each at its own size (or what it needs), in order
    // from that end, the panel's gap between them.
    var others = [];
    function along(list, fromRight) {
      var x = fromRight ? band[0] + band[2] : band[0];
      (fromRight ? list.slice().reverse() : list).forEach(function (it, j) {
        var need = needOf(it.kind, it.props || {}, L);
        var w = Math.max(it.rect ? it.rect[2] * L.k : 0, need[0], it.kind === 'button' ? L.panel.touch : 0);
        var ht = Math.min(Math.max(it.rect ? it.rect[3] * L.k : band[3], need[1]), Math.max(band[3], need[1]));
        if (fromRight) x -= w;
        var r = [x, Math.max(0, band[1] + (band[3] - ht) / 2), w, ht];
        if (slots.some(function (s) { return overlaps(r, s.at); })) {
          probs.push(nameOf(it) + ' at the Header\'s ' + (fromRight ? 'end' : 'start') + ' runs into its tabs on a '
                     + L.model);
        }
        others.push({ r: r, at: r.slice(), kind: it.kind, props: it.props || {}, it: it, set: null, need: need,
                      touch: isTouch(it.kind), key: (fromRight ? 'end' : 'start') + j });
        x = fromRight ? x - L.panel.gap : x + w + L.panel.gap;
      });
    }
    along(starts, false);
    // Share Content at the template's place, grown to what it holds there,
    // in the template's look unless the designer gives one.
    if (share) {
      var sx = Object.assign(unset(share.props, RD.share), (share.props || {}).id == null ? seedIn([place], 'share') : {});
      var sst = statesOver((share.props || {}).states, RD.share);
      if (sst) sx.states = sst;
      var sp = Object.assign({}, share.props || {}, sx), sneed = needOf(share.kind, sp, L);
      var sat = settle(place.rect, sneed, band, L.panel.size, [false, false, false, false]);
      if (lastAt && overlaps(sat, lastAt)) {
        probs.push(nameOf(share) + " at the Header's share place runs into its tabs on a " + L.model);
      }
      others.push({ r: place.rect.slice(), at: sat, kind: share.kind, props: sp, it: share, set: null, need: sneed,
                    touch: isTouch(share.kind), key: 'share', extra: sx, role: 'share' });
      band = [band[0], band[1], Math.max(0, sat[0] - band[0]), band[3]];
    }
    along(ends, true);
    // A tab's twin, as the template draws it: a caption-only button across
    // the tab's foot at the twin's depth, as far from the foot as the
    // template's, saying the tab's name in the twin's colour in every state
    // - one control to the program, so the tab's ID (the translator's
    // `mirror`), its states' names, its nav and its does. It lies inside the
    // tab, whose press and states it is (gdl.spec mirrors), and is drawn on
    // the panels whose template draws one: the layout's, so derived.
    function twinOf(s, i) {
      var tw = twins.items[Math.min(i, twins.items.length - 1)].rect, tr = first[Math.min(i, first.length - 1)].rect;
      var depth = Math.min(tw[3], s.at[3]), off = Math.max(0, (tr[1] + tr[3]) - (tw[1] + tw[3]));
      var r = [s.at[0], s.at[1] + s.at[3] - off - depth, s.at[2], depth];
      var tl = twins.look || {}, color = tokenOf(L.colors, tl.off && tl.off.text) || 'text';
      var p = s.it.props || {}, name = nameOf(s.it);
      var states = (s.twin.states || []).map(function (x) {
        return { name: typeof x === 'string' ? x : x.name, fill: 'none', color: color };
      });
      return drawnAt(Button, { name: name + ' Caption', derived: true, __mirror: name,
                               variant: P.buttons.clear ? 'clear' : undefined, fill: 'none', border: 'none',
                               color: color, text: s.twin.caption, states: states, size: p.size, bold: p.bold,
                               nav: p.nav, does: p.does, press: p.press }, r, 'twin' + i);
    }
    return { slots: slots.concat(others), render: function () {
      var lastAt = slots.length ? slots[slots.length - 1].at : null;
      var tlast = first.length ? first[first.length - 1].rect : null;
      // The bar is one band: as deep as its tabs came out. At the 725's
      // type floor Shockwave's caption two breaks under its glyph needs 85
      // px of its 75 px tab, and the tabs hung below the bar.
      var top = Math.min.apply(null, slots.map(function (s) { return s.at[1]; }));
      var foot = Math.max.apply(null, slots.map(function (s) { return s.at[1] + s.at[3]; }));
      // The bar's own surfaces; the one after the template's last tab starts
      // after this page's, so fewer tabs close the bar up and more take from it.
      // The page sources are chosen on draws its own across the top (Mach's
      // one strip under its title) where it has any.
      var surf = select && select.surfaces && select.surfaces.length ? select.surfaces : F.surfaces;
      var els = surfacesOf(L, surf, 'Header', function (s) {
        var r = s.rect.slice();
        var name = (F.start || []).some(function (x) { return sameRect(x.rect, s.rect); }) ? 'Header Left'
          : (F.end || []).some(function (x) { return sameRect(x.rect, s.rect); }) ? 'Header Right' : null;
        if (lastAt && tlast && r[0] >= tlast[0] + tlast[2]) {
          var right = r[0] + r[2];
          r[0] = lastAt[0] + lastAt[2] + 1; r[2] = right - r[0];
        }
        if (slots.length && r[1] < foot && top < r[1] + r[3]) {
          var y0 = Math.min(r[1], top);
          r[3] = Math.max(r[1] + r[3], foot) - y0; r[1] = y0;
        }
        return { rect: r, name: name };
      });
      slots.forEach(function (s, i) { els.push(hostAt(s.it, s.at, 'tab' + i, s.extra)); });
      slots.forEach(function (s, i) { if (s.twin) els.push(twinOf(s, i)); });
      others.forEach(function (s) { els.push(hostAt(s.it, s.at, s.key, s.extra)); });
      // Its title, in the template's words unless the Page gives one, at the
      // size that panel's template sets it.
      if (select && select.title) {
        var tl = Object.assign({}, RD.heading || {}, (RD.select || {}).title || {});
        els.push(chromeLabel(L, tl, 'Select Source Title', props.title || select.text || 'Select a Source',
                             select.title, 'select-title', (select.pt || {}).title));
      }
      return regionBox('Header', els, probs);
    } };
  }

  function planLeftRail(props, L) {
    var F = L.region.F.left, band = F.rect, probs = [], secs = [];
    itemsOf(props.children).forEach(function (it) {
      if (it.kind === 'section') secs.push(it);
      else probs.push(nameOf(it) + ' in the LeftRail is not in a Section - put the rail\'s controls in titled Sections');
    });
    var groups = F.groups || [], heads = [], sets = [];
    secs.forEach(function (sec, gi) {
      var G = groups[gi], sp = propsOf(sec);
      if (!G || !G.buttons || !G.buttons.length) {
        probs.push('the LeftRail holds ' + secs.length + ' Sections; the ' + L.model + "'s template draws "
                   + groups.length);
        return;
      }
      var title = sp.title || null, set = setName('left', gi), shown = title || 'Left Rail ' + (gi + 1);
      // The heading where the template draws one over this group: Shockwave's
      // and Turbulence's second group has none, and its title only names it.
      if (title && G.heading) {
        var hp = Object.assign({ name: title + ' Heading', text: title }, RD.heading || {});
        heads.push({ props: hp, at: settle(G.heading.rect, needOf('label', hp, L), band, L.panel.size,
                                           [false, false, false, false]), key: 'lh' + gi });
      }
      // The template's look for the group: its first is the display's
      // (`rail`), the rest launch settings (`launcher`). On a call page the
      // first is the VTC group, each key in its own look by what it is
      // (`regions.call`: Make Call green, End Call red, Privacy Mach's dim
      // yellow) and keeping its seed ID (Initiate Call 5014, End Call 5215,
      // VC Privacy 5217) where the designer gives none.
      var d = gi ? RD.launcher || RD.rail : RD.rail;
      var keys = L.region.role === 'call' && gi === 0;
      var members = itemsOf(sp.children);
      var mv = L.moved && L.moved.there && L.moved.group === gi ? L.moved : null;
      var pitch = G.pitch || G.buttons[0].rect[3] + 1;
      // Each member at the template's place for its turn in the group.
      function slotsOf(list) {
        return list.map(function (it, j) {
          var r = j < G.buttons.length ? G.buttons[j].rect.slice()
            : (function (last) { return [last[0], last[1] + (j - G.buttons.length + 1) * pitch, last[2], last[3]]; })(
              G.buttons[G.buttons.length - 1].rect);
          var touch = it.kind === 'button';
          var cr = keys && touch ? callRoleOf(it) : null;
          var lk = cr ? Object.assign({}, d || {}, (RD.call || {})[cr] || {}) : d;
          var extra = touch ? Object.assign(unset(it.props, lk), { joined: set },
                                            cr && (it.props || {}).id == null ? seedIn(G.buttons, cr) : {}) : {};
          var cst = cr ? statesOver((it.props || {}).states, lk) : null;
          if (cst) extra.states = cst;
          var s = { r: r, kind: it.kind, props: Object.assign({}, it.props || {}, extra), it: it, extra: extra,
                    set: touch ? set : null, touch: touch, key: 'l' + gi + '-' + j };
          s.need = needOf(s.kind, s.props, L);
          return s;
        });
      }
      var drawn = slotsOf(members);
      if (mv) members.splice(Math.min(mv.index, members.length), 0, mv.it);
      sets.push({ G: G, slots: mv ? slotsOf(members) : drawn, drawn: drawn, shown: shown, moved: mv });
    });
    // A column is one width: groups the template draws as wide (Mach's,
    // Shockwave's) take the widest any of them needs. Turbulence's rings
    // and docks are two widths, and keep their own.
    sets.forEach(function (a) {
      var w = 0;
      sets.forEach(function (b) {
        if (Math.abs(b.G.buttons[0].rect[2] - a.G.buttons[0].rect[2]) > 1) return;
        b.slots.forEach(function (s) { if (s.touch) w = Math.max(w, s.need[0]); });
      });
      var held = settleSet(a.slots, band, L, 'the ' + a.shown + ' Section', 1, [w, 0]);
      var past = a.slots.filter(function (s) { return s.at[1] + s.at[3] > band[1] + band[3]; });
      if (past.length && a.moved) {
        // Said once, as the RightRail's - the designer put none of it there -
        // and the Section stands as drawn: the page is refused for it, and a
        // launcher pushed off the screen was a second problem of one cause.
        probs.push(a.moved.said + ', where with it the ' + a.shown + ' Section holds ' + a.slots.length
                   + ', more than the ' + L.model + "'s rail has room for - take a launcher out of that Section "
                   + '(a page flip such as a call page is the Footer\'s mode launcher)');
        a.slots = a.drawn;
        held = settleSet(a.slots, band, L, 'the ' + a.shown + ' Section', 1, [w, 0]);
        past = [];
      }
      probs = probs.concat(held);
      past.forEach(function (s) {
        probs.push(slotName(s) + ' runs past the foot of the ' + L.model + "'s left rail - the " + a.shown
                   + ' Section holds ' + a.slots.length + ', more than the template has room for');
      });
    });
    // Down the rail in order: a set whose keys grew past the next one's top
    // - the 725's VTC keys, 50 px deep in its template, grown to its 60 px
    // touch minimum - moves that set and its heading down by as much, the
    // panel's gap clear, as the template stands its groups apart; one that
    // then runs past the rail's foot is named.
    sets.forEach(function (a, i) {
      var b = sets[i + 1];
      if (!b || !a.slots.length || !b.slots.length) return;
      var foot = Math.max.apply(null, a.slots.map(function (s) { return s.at[1] + s.at[3]; }));
      var head = heads.filter(function (x) { return x.key === 'lh' + (i + 1); })[0];
      var top = Math.min.apply(null, b.slots.map(function (s) { return s.at[1]; }).concat(head ? [head.at[1]] : []));
      // Only where they meet: seams the template leaves under the gap are
      // openSeams' to open.
      if (foot <= top) return;
      var by_ = foot + L.panel.gap - top;
      b.slots.forEach(function (s) { s.at[1] += by_; });
      if (head) head.at = [head.at[0], head.at[1] + by_, head.at[2], head.at[3]];
      b.slots.forEach(function (s) {
        if (s.at[1] + s.at[3] > band[1] + band[3]) {
          probs.push(slotName(s) + ' runs past the foot of the ' + L.model + "'s left rail - the " + b.shown
                     + ' Section stands lower there, under the ' + a.shown + ' Section grown to the touch minimum');
        }
      });
    });
    var all = [].concat.apply([], sets.map(function (a) { return a.slots; }));
    return { slots: all, render: function () {
      var els = surfacesOf(L, F.surfaces, 'Left Rail', fitTo(all));
      heads.forEach(function (x) { els.push(drawnAt(Label, x.props, x.at, x.key)); });
      all.forEach(function (s) {
        els.push(s.it.comp ? hostAt(s.it, s.at, s.key, s.extra)
                           : React.cloneElement(s.it.host, { key: s.key, style: cell(s.at) }));
      });
      return regionBox('LeftRail', els, probs);
    } };
  }
  // Drawn by its LeftRail; on its own, named.
  function Section(props) {
    var L = useLook();
    return regionBox('Section', [], [(props.title || 'A Section') + ' is a Section, which goes in a LeftRail']
      .filter(function () { return !(L && L.regionRefused); }));
  }

  // The fixed chrome whose seed ID (the frame's `ids`, each slot's `id`) a
  // region page keeps by default: the translator pins it where the designer
  // gave none and no canvas control has it (gdl.design pin_ids), so a
  // program written against Extron's template finds Help at 8117 on every
  // panel. A heading's label keeps none: it is not chrome a program drives.
  var SEED_ROLES = { help: true, power: true, volume: true, mute: true, mode: true };
  function seedOf(role, item) {
    return SEED_ROLES[role] && item && item.id != null ? { __seed: item.id } : {};
  }
  // The call mode's keys (the frame's call `ids`): one in the VTC group or
  // the Header's share place keeps the template's seed ID - the frame item
  // of its role among `items` - where the designer gives none.
  function seedIn(items, role) {
    var x = (items || []).filter(function (b) { return b.role === role; })[0];
    return x && x.id != null ? { __seed: x.id } : {};
  }
  // A call key's meaning off its own words, as the template names its own
  // (Initiate Call captioned Make Call, End Call, VC Privacy): the VTC
  // group's look and seed ID go by it, not by its place, so a launcher a
  // designer stands third is not dressed as Privacy.
  function callRoleOf(it) {
    var p = propsOf(it), w = (String(p.name || '') + ' ' + String(textOf(p.children, p.text) || '')).toLowerCase();
    if (/\bend\b/.test(w) && /\bcall\b/.test(w)) return 'end-call';
    if (/\bprivacy\b/.test(w)) return 'privacy';
    if (/\bcall\b/.test(w)) return 'call';
    return null;
  }
  // The roles a right rail or a footer draws by default, and how.
  function chrome(role, item, L, nav) {
    var ids = seedOf(role, item);
    if (role === 'heading') return [Label, Object.assign({ name: (item.text || 'Volume') + ' Heading', text: item.text || 'Volume' }, RD.heading || {}, ids)];
    if (role === 'volume') return [Slider, Object.assign({ name: 'Volume' }, RD.volume || {}, ids)];
    if (role === 'mute') return [Button, Object.assign({ name: 'Volume Mute', text: 'Mute' }, RD.mute || {}, ids)];
    if (role === 'help') return [Button, Object.assign({ name: 'Help', text: 'Help' }, RD.help || {}, ids, nav ? { nav: nav } : {})];
    if (role === 'power') return [Button, Object.assign({ name: 'Power' }, RD.power || {}, ids, nav ? { nav: nav } : {})];
    if (role === 'clock') return [Clock, Object.assign({ name: 'Date Time' }, RD.clock || {})];
    return null;
  }
  var KIND_OF = { heading: 'label', volume: 'slider', mute: 'button', help: 'button', power: 'button', clock: 'clock' };
  // The template's look for a designer's own control in a role's slot,
  // where the designer gives none: Audio Control is a launcher.
  function roleLook(role) {
    return role === 'audio' ? RD.launcher || RD.rail : RD[role];
  }
  // Lay out a band's roles: the designer's child in a slot wins; else the
  // template's own where it is drawn by default. `cells`: [{ item, band }];
  // `setOf(cell)`: the joined set a touchable cell is one of, or null.
  function roles(cells, over, L, navs, setOf, where) {
    var probs = [], slots = [];
    cells.forEach(function (c, i) {
      var role = c.item.role, it = over[role], def = it ? null : chrome(role, c.item, L, navs[role]);
      if (!it && !def) return;
      var kind = it ? it.kind : KIND_OF[role], touch = isTouch(kind), set = touch ? setOf(c) : null;
      var extra = Object.assign(it ? unset(it.props, roleLook(role)) : {}, set ? { joined: set } : {},
                                it && (it.props || {}).id == null ? seedOf(role, c.item) : {});
      var props = Object.assign({}, it ? it.props || {} : def[1], extra);
      slots.push({ r: c.item.rect.slice(), band: c.band, kind: kind, props: props, it: it, def: def, extra: extra,
                   role: role, i: i, touch: touch, set: set, need: needOf(kind, props, L) });
    });
    // A set's members grow away from each other's seams: Help from Power.
    slots.forEach(function (s) {
      var mates = slots.filter(function (m) { return s.set && m.set === s.set; }).map(function (m) { return m.r; });
      s.at = settle(s.r, s.need, s.band, L.panel.size, seamsOf(s.r, s.band, mates));
    });
    for (var i = 0; i < slots.length; i++) {
      for (var j = i + 1; j < slots.length; j++) {
        if (slots[i].touch && slots[j].touch && overlaps(slots[i].at, slots[j].at)) {
          probs.push(where + "'s " + slotName(slots[i]) + ' and ' + slotName(slots[j])
                     + ' need more room than the ' + L.model + "'s template gives them");
        }
      }
    }
    // The clock gives way on its side to a control grown into it, so its
    // words do not run into it.
    slots.forEach(function (s) {
      if (s.kind !== 'clock') return;
      slots.forEach(function (t) {
        if (!t.touch || !overlaps(s.at, t.at)) return;
        if (t.at[0] + t.at[2] / 2 < s.at[0] + s.at[2] / 2) {
          var right = s.at[0] + s.at[2];
          s.at = [Math.min(right, t.at[0] + t.at[2] + L.panel.gap), s.at[1], 0, s.at[3]];
          s.at[2] = right - s.at[0];
        } else {
          s.at = [s.at[0], s.at[1], Math.max(0, t.at[0] - L.panel.gap - s.at[0]), s.at[3]];
        }
      });
    });
    return { slots: slots, probs: probs, els: function () {
      var els = [];
      slots.forEach(function (s) {
        var key = where + s.role + s.i;
        if (s.it) {
          els.push(hostAt(s.it, s.at, key, s.extra));
        } else if (s.role === 'volume' && L.panel.kinds && L.panel.kinds.slider === false) {
          // A seed with no slider: a level with Up and Down, as Extron's own
          // hubs and 320s draw volume (asLevel).
          var lv = asLevel({ props: s.def[1], rect: s.r }, s.at, 'column', L.panel, key,
                           [s.band[0], s.band[0] + s.band[2]], null, null);
          els = els.concat(lv.els, lv.problems.map(function (q, n) { return problem(q, key + n); }));
        } else {
          els.push(drawnAt(s.def[0], s.props, s.at, key));
        }
      });
      return els;
    } };
  }
  // A region's children by slot. One whose slot the region draws on
  // another panel but not this one (Shockwave's Audio Control: in the 1035's
  // right rail, in the 725's left) is named as that.
  function slotted(children, allowed, where, band, L) {
    var over = {}, probs = [], known = {};
    // The slots a designer can fill: a bar series' own. A hub's menu bar
    // adds the openers its layout derives (settings, Display Control, Up and
    // Down), which no designer's control fills - read as places a template
    // draws, slot="settings" was told to list the panels that draw one.
    Object.keys(FRAMES).forEach(function (series) {
      if (FRAMES[series].hub) return;
      ((FRAMES[series][band] || {}).items || []).forEach(function (x) { known[x.role] = true; });
    });
    var mv = where === 'RightRail' && L.moved;
    itemsOf(children).forEach(function (it) {
      var s = slotOf(it);
      if (allowed.indexOf(s) >= 0) over[s] = it;
      else if (mv && s === mv.slot) {
        // Where this panel's template keeps it (movedPlace): the LeftRail
        // draws it, or with no Section there it is named.
        if (!mv.there) probs.push(mv.said + ' - draw a ' + (ORDINAL[mv.group] || 'next') + ' Section, and it goes there');
      } else if (s && known[s] && KIND_OF[s] == null) {
        probs.push(nameOf(it) + ' takes the ' + where + "'s " + s + ' place, which the ' + L.model
                   + "'s template does not draw - list the panels whose template draws one");
      } else {
        probs.push(nameOf(it) + ' in the ' + where + ' has no slot it draws - say slot="' + allowed.join('", "') + '"');
      }
    });
    return { over: over, probs: probs };
  }

  function planRightRail(props, L) {
    var F = L.region.F.right;
    // Power and Help are the Footer's, wherever the template stands them.
    var cells = (F.items || []).filter(function (x) { return x.role !== 'power' && x.role !== 'help'; })
      .map(function (x) { return { item: x, band: F.rect }; });
    var allowed = cells.map(function (c) { return c.item.role; });
    var sl = slotted(props.children, allowed, 'RightRail', 'right', L);
    // Audio Control and the like are drawn only when given.
    cells = cells.filter(function (c) { return KIND_OF[c.item.role] || sl.over[c.item.role]; });
    // The volume - heading, slider and Mute - is the right rail's group: one
    // set, as a left rail group is (owner's call 2), its controls as near as
    // the template stands them (Shockwave 725's Mute flush under the slider).
    var out = roles(cells, sl.over, L, {}, function (c) {
      return ['heading', 'volume', 'mute'].indexOf(c.item.role) >= 0 ? setName('right') : null;
    }, 'the RightRail');
    return { slots: out.slots, render: function () {
      return regionBox('RightRail', surfacesOf(L, F.surfaces, 'Right Rail', fitTo(out.slots)).concat(out.els()),
                       sl.probs.concat(out.probs));
    } };
  }

  // The footer's sets: the touchable cells the template stands together,
  // 2 px or less apart and side by side - Mach's Help and Power (1 px),
  // Turbulence's Help and Room Mode (2 px). Each other cell, Shockwave's
  // among them, is in none and keeps the panel's gap.
  function meetingSets(cells, touchy, region) {
    var parent = cells.map(function (_, i) { return i; });
    function root(i) { while (parent[i] !== i) i = parent[i]; return i; }
    cells.forEach(function (a, i) {
      cells.forEach(function (b, j) {
        if (j <= i || !touchy(a) || !touchy(b)) return;
        var p = a.item.rect, q = b.item.rect;
        var gx = Math.max(q[0] - (p[0] + p[2]), p[0] - (q[0] + q[2]));
        var gy = Math.max(q[1] - (p[1] + p[3]), p[1] - (q[1] + q[3]));
        if ((gx >= 0 && gx <= 2 && gy < 0) || (gy >= 0 && gy <= 2 && gx < 0)) parent[root(j)] = root(i);
      });
    });
    var size = {};
    cells.forEach(function (_, i) { size[root(i)] = (size[root(i)] || 0) + 1; });
    return function (c) {
      var r = root(cells.indexOf(c));
      return size[r] > 1 ? setName(region, r) : null;
    };
  }

  function planFooter(props, L) {
    var R = L.region, F = R.F.bottom;
    var cells = (F.items || []).map(function (x) { return { item: x, band: F.rect }; });
    (R.F.right.items || []).forEach(function (x) {
      if (x.role === 'power' || x.role === 'help') cells.push({ item: x, band: R.F.right.rect });
    });
    var sl = slotted(props.children, cells.map(function (c) { return c.item.role; }), 'Footer', 'bottom', L);
    // The mode launcher is the room's own: drawn only when given.
    cells = cells.filter(function (c) { return c.item.role !== 'mode' || sl.over.mode; });
    var sets = meetingSets(cells, function (c) {
      var it = sl.over[c.item.role];
      return isTouch(it ? it.kind : c.item.role === 'mode' ? 'button' : KIND_OF[c.item.role]);
    }, 'footer');
    var out = roles(cells, sl.over, L, { help: props.help, power: props.power }, sets, 'the Footer');
    return { slots: out.slots, render: function () {
      return regionBox('Footer', surfacesOf(L, F.surfaces, 'Footer', fitTo(out.slots)).concat(out.els()),
                       sl.probs.concat(out.probs));
    } };
  }

  function planCenter(props, L) {
    var R = L.region;
    var probs = itemsOf(props.children).map(function (it) {
      return nameOf(it) + ' in the Center: it is the popup region its sources fill - put a source\'s controls in '
        + 'its popup';
    });
    // On every panel the template's own region, which a source popup
    // (role="source") is sized to there - a popup is its reference's size
    // (Standards p.70). What the template draws on the page round it - not
    // in a source's popup - is its surfaces: Shockwave's translucent well.
    var C = R.F.center, r = C.region.slice();
    // The page the sources are chosen on: no popup region - the Header's
    // tabs are the template's tiles in the centre, each with its name in a
    // label under it, more than the template draws on in rows.
    if (R.role === 'select' && R.F.choose) return planTiles(R.F.choose, R.tiles || [], L, probs);
    return { slots: [], render: function () {
      var wells = (C.surfaces || []).filter(function (s) { return !s.popup && s.kind === 'shape'; });
      var els = chromePanels(L, wells, 'Center Well', 'cw');
      els.push(drawnAt(PopupRegion, { name: props.name || 'Controls', group: props.group || 'Sources' }, r, 'center'));
      return regionBox('Center', els, probs);
    } };
  }
  // A Select Source page's tiles: the template's grid (gridSpots) in the
  // centre band between the rails and bars, each tile the designer's tab in
  // the template's tile look (`regions.select.tile`) unless it gives one,
  // its caption the label under it where the tile draws its icon alone, as
  // the template's tiles are captioned. One joined set: the template stands
  // Turbulence's 10 px apart.
  function planTiles(S, tabs, L, probs) {
    var T = L.panel, band = L.region.F.center.rect || L.region.F.center.region;
    var top = S.title ? Math.max(band[1], S.title[1] + S.title[3]) : band[1];
    var spots = gridSpots(S, tabs.length, T, band[1] + band[3], top + T.gap, [band[0], band[0] + band[2]]);
    var look = (RD.select || {}).tile || {}, labelLook = Object.assign({}, RD.heading || {}, (RD.select || {}).label || {});
    var set = setName('select'), slots = [];
    tabs.forEach(function (it, i) {
      var sp = spots[i];
      if (!sp) return;
      var p = propsOf(it), caption = textOf(p.children, p.text);
      var extra = Object.assign(unset(p, look), { joined: set });
      // A tab's own look is the header's: as a tile it takes the template's.
      ['size', 'align', '__indent'].forEach(function (k) { if (p[k] != null) extra[k] = undefined; });
      var icon = iconHere(Object.assign({}, p, extra), p.icon || extra.icon);
      var alone = !!icon && !!sp.label;
      if (alone) extra.text = '';
      if (p.icon && !icon) extra.icon = undefined;
      var all = Object.assign({}, p, extra, alone ? { children: null } : {});
      slots.push({ r: sp.tile.slice(), kind: 'button', props: all, it: it, extra: extra, set: set, touch: true,
                   label: alone && caption ? sp.label : null, caption: caption, key: 'tile' + i,
                   need: needOf('button', all, L) });
    });
    probs = probs.concat(settleSet(slots, band, L, 'the Select Source tiles', null));
    slots.forEach(function (s) {
      if (s.at[1] + s.at[3] > band[1] + band[3] || (s.label && s.label[1] + s.label[3] > band[1] + band[3])) {
        probs.push('the Select Source tiles hold ' + tabs.length + ', more than the ' + L.model + "'s centre has room for");
      }
    });
    return { slots: slots, render: function () {
      var els = [];
      slots.forEach(function (s) {
        els.push(hubHost(s.it, s.at, s.key, s.extra, s.label ? null : undefined));
        if (s.label) {
          var lr = [s.label[0], Math.max(s.label[1], s.at[1] + s.at[3]), s.label[2], s.label[3]];
          els.push(chromeLabel(L, labelLook, (propsOf(s.it).name || s.caption) + ' Label', s.caption, lr, s.key + 'l',
                               (S.pt || {}).label));
        }
      });
      return regionBox('Center', els, probs.filter(function (q, i, a) { return a.indexOf(q) === i; }));
    } };
  }

  var PLANS = { header: planHeader, leftrail: planLeftRail, rightrail: planRightRail, footer: planFooter,
                center: planCenter };
  // Two touch targets of different sets nearer than the panel's 2 mm gap
  // (gdl.spec's spacing rule; owner's call 2: unrelated controls keep it).
  // The template's own seams between its regions are under it on Shockwave
  // and Turbulence - Turbulence's last rail launcher 1 px from its footer's
  // Help, Shockwave 725's Mute 10 px over Power and its last launcher 8 px
  // from Room Mode - so each opens to the gap. Each side gives what it can
  // spare above its own need, the side whose giving way moves fewer
  // controls first - a set's edge moves for every member on it, so a column
  // stays one width: Turbulence's Help gives way, not its two launchers,
  // and comes out 12 px in, as the profile's own Layout says - else the two
  // alike. What the two cannot spare between them is named, as is a
  // control grown into another region's.
  function openSeams(plans, L) {
    var all = [], gap = L.panel.gap, probs = [];
    REGION_ORDER.forEach(function (k) {
      ((plans[k] || {}).slots || []).forEach(function (s) {
        if (s.touch && s.at) { s.region = k; all.push(s); }
      });
    });
    function apart(a, b, ax) {
      return Math.max(b.at[ax] - (a.at[ax] + a.at[ax + 2]), a.at[ax] - (b.at[ax] + b.at[ax + 2]));
    }
    // The pair's axis and gap where they are neighbours under the gap: side
    // by side on one axis, apart by less on the other.
    function near(a, b) {
      if (a.set && a.set === b.set) return null;
      var gx = apart(a, b, 0), gy = apart(a, b, 1);
      var ax = gx < 0 && gy >= 0 ? 1 : gy < 0 && gx >= 0 ? 0 : -1;
      if (ax < 0) return null;
      var g = ax ? gy : gx;
      return g < gap ? { ax: ax, g: g } : null;
    }
    // `s` and the members of its set whose edge on that side is where its is.
    function side(s, ax, hi) {
      function edge(m) { return hi ? m.at[ax] + m.at[ax + 2] : m.at[ax]; }
      return all.filter(function (m) {
        return m === s || s.set && m.set === s.set && Math.abs(edge(m) - edge(s)) <= 1;
      });
    }
    function spare(ms, ax) {
      return Math.max(0, ms.reduce(function (least, m) {
        return Math.min(least, Math.floor(m.at[ax + 2] - m.need[ax]));
      }, Infinity));
    }
    function give(ms, ax, hi, d) {
      ms.forEach(function (m) { m.at[ax + 2] -= d; if (!hi) m.at[ax] += d; });
    }
    for (var i = 0; i < all.length; i++) {
      for (var j = i + 1; j < all.length; j++) {
        var n = near(all[i], all[j]);
        if (!n) continue;
        var ax = n.ax, lo = all[i].at[ax] < all[j].at[ax] ? all[i] : all[j], hi = lo === all[i] ? all[j] : all[i];
        var lm = side(lo, ax, true), hm = side(hi, ax, false);
        var ls = spare(lm, ax), hs = spare(hm, ax), want = gap - n.g, dl, dh;
        if (ls + hs < want) continue;
        if (lm.length < hm.length) { dl = Math.min(ls, want); dh = want - dl; }
        else if (hm.length < lm.length) { dh = Math.min(hs, want); dl = want - dh; }
        else { dl = Math.min(ls, Math.ceil(want / 2)); dh = Math.min(hs, want - dl); dl = want - dh; }
        give(lm, ax, true, dl);
        give(hm, ax, false, dh);
      }
    }
    for (i = 0; i < all.length; i++) {
      for (j = i + 1; j < all.length; j++) {
        var a = all[i], b = all[j], m = near(a, b);
        if (m) {
          probs.push(slotName(a) + ' and ' + slotName(b) + ' stand ' + m.g + ' px apart on a ' + L.model
                     + ", under its 2 mm (" + gap + ' px), and neither can give way - the template\'s places do not '
                     + 'hold them there');
        } else if (a.region !== b.region && !(a.set && a.set === b.set) && overlaps(a.at, b.at)) {
          probs.push(slotName(a) + ' and ' + slotName(b) + ' run into each other on a ' + L.model
                     + ' - the template\'s places do not hold them there');
        }
      }
    }
    return probs;
  }
  // A RightRail slot this panel's template keeps elsewhere: Shockwave's
  // Audio Control, in the 1035's right rail and in the 725's left - its
  // second group, where the frame's `audio` role stands (the 725's Main VC:
  // Display Control, Audio Control, Lighting Control). The designer's control
  // in that slot goes where this panel's template keeps it: into the
  // LeftRail's Section for that group, at that role's place among its
  // launchers (`there`), or - with no such Section drawn - is named, with
  // where to draw one. Null where this panel's right rail draws the slot.
  var ORDINAL = ['first', 'second', 'third', 'fourth'];
  function movedPlace(regs, L) {
    var F = L.region.F, rr = null, lr = null;
    regs.forEach(function (it) {
      if (it.kind === 'rightrail' && !rr) rr = it;
      if (it.kind === 'leftrail' && !lr) lr = it;
    });
    if (!rr || ((F.right || {}).items || []).some(function (x) { return x.role === 'audio'; })) return null;
    var child = itemsOf(propsOf(rr).children).filter(function (it) { return slotOf(it) === 'audio'; })[0];
    var at = null;
    ((F.left || {}).groups || []).forEach(function (G, gi) {
      (G.buttons || []).forEach(function (b, j) {
        if (!at && b.role === 'audio') at = { group: gi, index: j, name: b.name };
      });
    });
    if (!child || !at) return null;
    var secs = lr ? itemsOf(propsOf(lr).children).filter(function (it) { return it.kind === 'section'; }) : [];
    return Object.assign(at, { it: child, slot: 'audio', there: secs.length > at.group,
                               said: nameOf(child) + " takes the RightRail's audio place, which the " + L.model
                                 + "'s template does not draw - it keeps it in its LeftRail's "
                                 + (ORDINAL[at.group] || 'next') + ' Section, at ' + at.name + "'s place" });
  }
  // The page's regions planned together: each its own, then the seams
  // between them opened. A second of one region is named, and draws nothing.
  function planRegions(regs, L, pname) {
    var plans = {}, count = {}, probs = [];
    var mv = movedPlace(regs, L);
    if (mv) L = Object.assign({}, L, { moved: mv });
    // In the regions' own order, whatever the canvas's: a Select Source
    // page's Center draws the Header's tabs as its tiles.
    regs = regs.slice().sort(function (a, b) { return REGION_ORDER.indexOf(a.kind) - REGION_ORDER.indexOf(b.kind); });
    regs.forEach(function (it) {
      count[it.kind] = (count[it.kind] || 0) + 1;
      if (count[it.kind] === 2) {
        probs.push(pname + ' holds more than one ' + REGION_NAMES[it.kind] + ' - a working page has one of each');
      }
      if (plans[it.kind]) return;
      var props = propsOf(it);
      plans[it.kind] = PLANS[it.kind](props, L);
      plans[it.kind].props = props;
    });
    return { plans: plans, count: count, probs: probs.concat(openSeams(plans, L)) };
  }
  function drawRegion(kind, props) {
    var L = React.useContext(Ctx), R = L && L.region;
    if (!R) return noFrame(REGION_NAMES[kind], L);
    // A hub's page draws its regions together, in its own grammar (planHub),
    // and the 320's (planPages).
    if (R.hub || R.pages) return null;
    var plan = R.plans && R.plans[kind];
    if (plan && plan.props !== props && R.count[kind] > 1) return null;
    return (plan || PLANS[kind](props, L)).render();
  }
  function Header(props) { return drawRegion('header', props); }
  function LeftRail(props) { return drawRegion('leftrail', props); }
  function RightRail(props) { return drawRegion('rightrail', props); }
  function Footer(props) { return drawRegion('footer', props); }
  function Center(props) { return drawRegion('center', props); }

  // -- The center and the windows -------------------------------------------
  // (docs/superpowers/specs/2026-10-22-region-frame-design.md.) A popup with
  // role="source" is a source's controls, shown in the working page's Center:
  // on each panel it is that panel's own popup region - the 725's from the
  // 725's template - and draws the template's chrome for it from the frame
  // (P.frames' center) and the profile: Mach's framed shade well, titled at
  // its left; Shockwave's 40 pt title (its well is the page's, a Center
  // surface); Turbulence's large centred title over the device picture it
  // pins at the top left (devicePicture, below). With nothing in it, it says the template's empty state in the
  // template's own words (P.writing). A modal with a role - settings, help,
  // confirm, wait - or with a title and no role is a window, drawn as the
  // template draws its windows (P.frames' windows): Mach's #303030 band
  // between the bars, Shockwave's #999999 card, Turbulence's navy one, each
  // with its title and Close, or its question and buttons, or its wait. What
  // they draw is derived - in the ID map, with IDs of its own - and Close and
  // Cancel go back to the page that opened the window, which is the
  // program's to know: they carry what they do, not a `nav`. What they say is
  // set at the size that panel's own template sets it (the frame's `pt`), not
  // the drawn panel's scaled: the 725 titles its sources 20 pt to the 1035's
  // 24, and scaled they came out 18, no larger than the 16 pt Close.
  var WD = P.writing || {};
  var CLOSE_DOES = 'Closes the window - back to the page that opened it.';
  var WINDOW_ROLES = { settings: true, help: true, confirm: true, wait: true };
  // A working page's roles (a Page with regions): the call mode and the
  // page its sources are chosen on.
  var PAGE_ROLES = { call: true, select: true };
  // Whether a Page is a source popup or a window: role="source" on a popup,
  // or the call mode's dialer (role="dialer"), drawn in the Center as a
  // source's popup is; a window's role, or a title and no role, on a modal.
  function framedRole(props, kind) {
    var role = String(props.role || '').toLowerCase();
    return !!(kind === 'popup' && (role === 'source' || role === 'dialer')
              || kind === 'modal' && (WINDOW_ROLES[role] || !role && props.title != null && String(props.title) !== ''));
  }
  // A measured fill as the template's token: exactly, else the token of its
  // colour - Turbulence draws its Lighting window opaque and its others at
  // alpha 212 (`raised`).
  function tokenNear(colors, v) {
    var t = tokenOf(colors, v);
    if (t || !v) return t;
    var want = hex8(v).slice(0, 7), names = Object.keys(colors);
    for (var i = 0; i < names.length; i++) if (hex8(colors[names[i]]).slice(0, 7) === want) return names[i];
    return null;
  }
  // The template's words with the source's name in them: `{name}` as it is
  // titled, `{noun}` in a sentence's case - Shockwave's 'Please connect your
  // laptop.', 'your PC.'
  function said(tpl, name) {
    var noun = String(name).split(' ').map(function (w) {
      return w.length > 1 && w.slice(1) === w.slice(1).toLowerCase() ? w.toLowerCase() : w;
    }).join(' ');
    return String(tpl).replace(/\{name\}/g, name).replace(/\{noun\}/g, noun);
  }
  function inRegion(F, r) {
    var g = F.center.region;
    return r ? [r[0] - g[0], r[1] - g[1], r[2], r[3]] : null;
  }
  // A source popup's parts on a panel, in the popup's own coordinates: its
  // title - where the template titles a source with controls (Turbulence's
  // Doc Cam at the popup's top, its empty Laptop 40 px lower) and one with
  // none - the shapes its popup draws (Mach's title bar and well body), the
  // box its controls are laid out in - the well's body where the template
  // draws one, else the whole region (Shockwave's and Turbulence's keys and
  // headings reach up beside their titles) - its empty state and status,
  // and the sizes it sets them in.
  function sourceParts(F) {
    var c = F.center, g = c.region;
    var title = inRegion(F, c.title);
    var shapes = (c.surfaces || []).filter(function (s) { return s.popup && s.kind === 'shape'; })
      .map(function (s) { return { s: s, r: inRegion(F, s.rect) }; });
    var bar = title ? shapes.filter(function (x) { return overlaps(x.r, title); })[0] || null : null;
    var wells = shapes.filter(function (x) { return x !== bar; });
    return { size: [g[2], g[3]], title: title, titleControls: inRegion(F, c.title_controls) || title,
             shapes: shapes, bar: bar, body: wells.length ? wells[0].r.slice() : [0, 0, g[2], g[3]],
             empty: c.empty ? inRegion(F, c.empty) : [0, 0, g[2], g[3]], status: inRegion(F, c.status),
             pt: c.pt || {} };
  }
  // The device picture a source's popup draws where its template pins one -
  // Turbulence's 1152x1152_<device>.png, fitted, at the popup's top left on
  // its bar series and under the title on its hub, behind the words - with
  // the device by the Page's `device`, else by its name or title where the
  // kit pictures one (Laptop, PC, Doc Cam), else by the profile's
  // `regions.source.devices` for a name the seed pairs with another
  // picture (its Aux is the iPod's). It stands where the panel's own seed
  // draws that device (the frame's `pictures`): each is sized its own way,
  // the 1035's Doc Cam 326x288 to its Laptop's 293x257 and the 525's PC
  // 264x260 to its 310x241; drawn at the Laptop's, that Doc Cam came out a
  // tenth small and that PC 241 px square, not 260. A device the seed
  // pictures for no source (Streaming named a monitor) takes the Laptop's -
  // the frame's image surface of the measured source's popup. `at` is the
  // popup's origin on the page. {el}, {problem} - a `device` the kit has no
  // picture of - or {warning} where nothing names one; null where the
  // template pins none, the kit is not here or the panel's seed cannot
  // clone an image.
  function squash(v) { return String(v == null ? '' : v).toLowerCase().replace(/[^a-z0-9]/g, ''); }
  function devicePicture(L, F, props, name, title, at) {
    var S = (F.center.surfaces || []).filter(function (s) { return s.popup && s.kind === 'image' && s.art; })[0];
    var size = S && (/^(\d+x\d+)_/.exec(S.art) || [])[1];
    var fams = size && KIT && KIT.files ? KIT.files[size] : null;
    if (!fams || !Object.keys(fams).length || !imagesOn(L)) return null;
    var aliases = (RD.source || {}).devices || {};
    function famOf(word) {
      var w = squash(word);
      if (!w) return null;
      if (aliases[w] && fams[aliases[w]]) return aliases[w];
      return Object.keys(fams).filter(function (f) { return squash(f) === w; })[0] || null;
    }
    var kinds = Object.keys(fams).sort().join(', ');
    var fam = null;
    if (props.device != null && String(props.device) !== '') {
      fam = famOf(props.device);
      if (!fam) {
        return { problem: name + "'s device \"" + props.device + '" is not one the ' + P.template
                          + ' kit pictures - one of ' + kinds };
      }
    } else {
      var words = [name, title].concat(String(name).split(/\s+/), String(title || '').split(/\s+/));
      for (var i = 0; i < words.length && !fam; i++) fam = famOf(words[i]);
      if (!fam) {
        return { warning: name + ' names no device the ' + P.template + ' kit pictures, so the place its template '
                          + 'pins a device picture stays empty - say device="..." (' + kinds + ')' };
      }
    }
    var looks = fams[fam], file = looks.plain || looks.off || looks[Object.keys(looks)[0]];
    var r = (F.center.pictures || {})[fam] || S.rect;
    return { el: drawnAt(ImageArt, { name: name + ' Image', image: file, derived: true },
                         [r[0] - at[0], r[1] - at[1], r[2], r[3]], 'picture') };
  }
  // The window a modal draws on a panel: its role's record, or for a
  // settings window the one drawn for a window of its name (Shockwave's
  // Audio Control is wider than its Lighting Control). One named for none
  // is drawn alike on every panel: the one here that draws most of the
  // windows the drawn panel's (`from`) draws, else the template's commonest
  // settings window - titled, with a Close, drawn as shapes, drawing the
  // most windows. The first measured on Mach's 725 is its Share Content, a
  // translucent shade over a photo with no title, where its 1035's is the
  // titled #303030 band.
  function windowOf(F, role, label, from, topic) {
    var W = F.windows || {};
    // The question the program shows when a call comes in is its own window
    // where the template draws one (Incoming Call); elsewhere it stands where
    // the power-down question does.
    if (role === 'confirm' && topic === 'call' && W.incoming) return W.incoming;
    if (role === 'confirm' || role === 'wait') return W[role] || null;
    var help = W.help ? Object.assign({}, W.help, { popups: ['Help'], help: true }) : null;
    if (role === 'help') return help;
    var first = String(label || '').split(/\s+/)[0].toLowerCase();
    var named = (W.settings || []).concat(help ? [help] : []).filter(function (r) {
      return (r.popups || []).some(function (q) { return String(q).split(/\s+/)[0].toLowerCase() === first; });
    })[0];
    if (named) return named;
    var plain = (W.settings || []).filter(function (r) {
      return r.title && r.close && (r.surfaces || []).length
        && r.surfaces.every(function (s) { return s.kind === 'shape'; });
    });
    function shared(r) {
      return from ? (r.popups || []).filter(function (q) { return (from.popups || []).indexOf(q) >= 0; }).length : 0;
    }
    var best = null;
    (plain.length ? plain : W.settings || []).forEach(function (r) {
      var a = shared(r), b = best ? shared(best) : -1;
      if (a > b || a === b && (r.popups || []).length > (best.popups || []).length) best = r;
    });
    return best || help;
  }
  // A question's answer by its place: the one that does it (Power Down,
  // Accept) and the one that does not (Cancel, Decline) - a call's in its
  // template's words (Mach's Accept and Decline, Shockwave's Accept Call and
  // Ignore Call; Turbulence's are in their art) and looks, where the panel
  // draws the call's question at the power-down question's place.
  function answerOf(b, topic, B, RW) {
    var yes = b.role === 'power' || b.role === 'accept';
    if (topic === 'call') {
      return { yes: yes, word: b.text || (yes ? B.accept || 'Accept' : B.decline || 'Decline'),
               look: RW[yes ? 'accept' : 'decline'] || RW[yes ? 'power' : 'cancel'], does: 'Declines the call.' };
    }
    return { yes: yes, word: yes ? B.power || 'Power Down' : B.cancel || 'Cancel', look: RW[yes ? 'power' : 'cancel'],
             does: CLOSE_DOES };
  }
  // A derived button at the template's rect `r`, grown in `band` to what it
  // needs on this panel. A look that draws no caption (Shockwave's and
  // Turbulence's kit Close) is given none: sized for the word it never
  // draws, Shockwave's 1035 Close came out 57 wide and no longer square for
  // its X.
  function chromeButton(L, name, look, caption, does, r, band, key) {
    var p = Object.assign({ name: name, derived: true }, look || {});
    // Its words beside its glyph, where its look sets them so (Shockwave's
    // incoming call's answers), at the template's size for it.
    if (p.__caption === 'indent' && p.__fit == null) p.__fit = [r[2], r[3]];
    var V = P.buttons[p.variant] || P.buttons[P.defaults.button.variant];
    var img = imageOf(V, p, caption);
    if (p.text == null && caption != null && !(img && img.caption === 'none')) p.text = caption;
    if (does) p.does = does;
    var at = settle(r, needOf('button', p, L), band, L.panel.size, [false, false, false, false]);
    return drawnAt(Button, p, at, key);
  }
  // A derived label at `r`, at `pt` - this panel's own template's size,
  // never under its floor - where one is measured, else its look's scaled
  // with the layout (ptOn).
  function chromeLabel(L, look, name, text, r, key, pt) {
    var p = Object.assign({}, look || {}, { name: name, text: text, derived: true });
    if (pt == null) return drawnAt(Label, p, r, key);
    p.size = pt;
    return h(Ctx.Provider, { key: key, value: Object.assign({}, L, { k: 1 }) },
             h('div', { style: cell(r) }, h(Label, p)));
  }
  function chromePanels(L, list, name, key) {
    var n = 0;
    return (list || []).filter(function (s) { return s.kind === 'shape'; }).map(function (s, i) {
      n += 1;
      return drawnAt(Panel, { name: name + (n > 1 ? ' ' + n : ''), fill: tokenNear(L.colors, s.fill) || P.defaults.panel.fill,
                              border: borderOf(s.border), stroke: 'none', derived: true }, s.r || s.rect, key + i);
    });
  }
  // A message's box: the template's, unless the words take more lines in it
  // than the template sets them in (`lines`, measured in the template's own
  // face). The system draws Open Sans, a little wider than the Light most
  // templates set their messages in, and in Turbulence's 505 px the 1035's
  // power-down question broke on its last word, where the template's is one
  // line. Then it widens about its middle, inside the window less the
  // panel's gap each side. The words are measured 6% wide, for a canvas
  // measuring them before its Open Sans loads (Arial is 5% narrower).
  function messageBox(L, look, text, r, win, lines, pt) {
    if (!lines || !win) return r;
    var f = font(Object.assign({}, look || {}, { size: pt != null ? pt : (look || {}).size }), P.defaults.label.type,
                 Object.assign({}, L, { k: pt != null ? 1 : L.k }));
    if (wrapWords(text, f.css, r[2] / 1.06).length <= lines) return r;
    var gap = L.panel.gap || 0, w = Math.max(r[2], win[2] - 2 * gap);
    // Where even that cannot hold them so - the 725 sets Turbulence's Help
    // at 14 pt, under its 16 pt floor - the template's box.
    if (wrapWords(text, f.css, w / 1.06).length > lines) return r;
    var x = Math.min(Math.max(r[0] + (r[2] - w) / 2, win[0] + gap), win[0] + win[2] - gap - w);
    return [Math.round(x), r[1], Math.round(w), r[3]];
  }
  // A source popup or a window on this panel: what it is drawn in (`T`, in
  // the page's coordinates) and from (`D`, the drawn panel's), its size, and
  // its chrome - or why the panel does not draw it.
  function framedPart(props, role, kind, D, T, name) {
    if (role === 'dialer') return dialerPart(props, D, T, name);
    var FD = frameFor(D), FT = frameFor(T), HT = FT ? null : hubFor(T), what = role === 'source' ? 'a source popup'
      : 'a ' + (role || 'settings') + ' window';
    // The 320 draws each as a page of its own (pagePart).
    var PT = !FT && !HT ? pagesFor(T) : null;
    if (PT) {
      var named = props.title != null && String(props.title) !== '';
      return pagePart(props, role, name, named ? String(props.title) : role === 'help' && WD.help_title || name,
                      PT, D, T);
    }
    if (!FT && !HT || !FD) {
      return { problem: name + ' is ' + what + ', which the ' + (FT || HT ? D.model : T.model) + ' does not draw yet' };
    }
    var given = props.title != null && String(props.title) !== '';
    // Help with no title says the template's own: Shockwave's and
    // Turbulence's HELP.
    var title = given ? String(props.title) : role === 'help' && WD.help_title || name;
    if (HT && (role === 'source' || !WINDOW_ROLES[role] || role === 'settings')) {
      return hubPart(role, FD, HT, name, title, D.model, props.group, props);
    }
    if (HT) FT = HT;
    if (role === 'source') {
      var SD = sourceParts(FD), ST = sourceParts(FT);
      return { D: SD.body, T: ST.body, dsize: SD.size, size: ST.size, looks: RD.source || {},
               chrome: function (L, content) {
                 var RS = RD.source || {}, els = [], pt = ST.pt;
                 // Turbulence's device picture, behind everything else.
                 var pic = devicePicture(L, FT, props, name, title, FT.center.region) || {};
                 if (pic.el) els.push(pic.el);
                 // Mach's title bar, then its well's body 1 px under it.
                 els = els.concat(chromePanels(L, ST.bar ? [{ kind: 'shape', fill: ST.bar.s.fill, border: ST.bar.s.border,
                                                              r: ST.bar.r }] : [], name + ' Title Bar', 'bar'));
                 els = els.concat(chromePanels(L, ST.shapes.filter(function (x) { return x !== ST.bar; }).map(function (x) {
                   return { kind: 'shape', fill: x.s.fill, border: x.s.border, r: x.r };
                 }), name + ' Well', 'well'));
                 var at = content ? ST.titleControls : ST.title;
                 if (at) els.push(chromeLabel(L, RS.title, name + ' Title', title, at, 'title', pt.title));
                 if (!content && WD.empty) {
                   var e = ST.empty, s = ST.status;
                   if (WD.status) {
                     // Shockwave's: the request in the box's upper half, as
                     // its 1035 and 725 draw it, over the status the program
                     // sets where the template stands it - else centred at
                     // the box's foot, 30% of it each way.
                     var sw = Math.round(e[2] * 0.3), sh = Math.round(e[3] * 0.3);
                     s = s || [e[0] + Math.round((e[2] - sw) / 2), e[1] + e[3] - sh, sw, sh];
                     els.push(chromeLabel(L, RS.empty, name + ' Empty', said(WD.empty, title),
                                          [e[0], e[1], e[2], Math.round(e[3] / 2)], 'empty', pt.empty));
                     els.push(chromeLabel(L, RS.status || RS.empty, name + ' Status', WD.status, s, 'status',
                                          pt.status != null ? pt.status : pt.empty));
                   } else {
                     els.push(chromeLabel(L, RS.empty, name + ' Empty', said(WD.empty, title), e, 'empty', pt.empty));
                   }
                 }
                 return { els: els, problems: pic.problem ? [pic.problem] : [], title: at || null,
                          notes: pic.warning ? [pic.warning] : [] };
               } };
    }
    var asked = String(props.topic || '');
    var rd = windowOf(FD, role, title, null, asked), rt = windowOf(FT, role, title, rd, asked);
    // Mach's hubs draw no window: Help, the question and the wait stand on
    // the scrim, over the whole screen.
    if (HT && rt && !rt.rect) rt = Object.assign({}, rt, { rect: [0, 0, T.size[0], T.size[1]] });
    if (!rd || !rt || !rd.rect || !rt.rect) {
      return { problem: name + ' is ' + what + ', which the ' + (rt && rt.rect ? D.model : T.model)
                        + "'s template does not draw" };
    }
    // A hub's windows in its own look where it has one (`regions.hub.window`):
    // Mach's Help on the scrim centres its title and closes with the back
    // glyph, where the 1035's titles its window from the left and writes
    // Close; Shockwave's closes with the hub's white X, not the card's dark one.
    var RW = Object.assign({}, RD.window || {});
    if (HT && HD.window) {
      Object.keys(HD.window).forEach(function (k) { RW[k] = Object.assign({}, RW[k] || {}, HD.window[k]); });
    }
    // What is put in it is laid out from the body under its title on the
    // panel drawn into the body under its title on this one: the 725's and
    // the 525's titles stand lower in their windows than the 1035's, and a
    // Label 7 px under Shockwave 1035's HELP, mapped from window to window,
    // came out under the 725's title and into its words on the 525.
    function body(rec) {
      var r = rec.rect, t = rec.title;
      if (!t) return r;
      var top = Math.min(Math.max(r[1], t[1] + t[3]), r[1] + r[3] - 1);
      return [r[0], top, r[2], r[1] + r[3] - top];
    }
    return { D: body(rd), T: body(rt), dsize: null, size: null, looks: RW,
             chrome: function (L, content) {
               var B = WD.buttons || {}, els = [], probs = [], pt = rt.pt || {};
               var plain = role !== 'confirm' && role !== 'wait';
               els = els.concat(chromePanels(L, rt.surfaces, name + ' Window', 'win'));
               if (plain && rt.title) els.push(chromeLabel(L, RW.title, name + ' Title', title, rt.title, 'title', pt.title));
               if (plain && rt.close) {
                 // Where the template stands it: in the window, or - a hub's
                 // Help - outside it, at the screen's corner (Shockwave's at
                 // 728,10 over its card at 162,99), so it settles in the page.
                 var cr = rt.close.rect, inWin = cr[0] >= rt.rect[0] && cr[1] >= rt.rect[1]
                   && cr[0] + cr[2] <= rt.rect[0] + rt.rect[2] && cr[1] + cr[3] <= rt.rect[1] + rt.rect[3];
                 els.push(chromeButton(L, name + ' Close', RW.close, B.close, CLOSE_DOES, cr,
                                       inWin ? rt.rect : [0, 0, T.size[0], T.size[1]], 'close'));
               }
               var topic = String(props.topic || ''), words_ = null;
               if (!plain) {
                 var said_ = WD[role] || {};
                 words_ = said_[topic];
                 // This panel's own template's words for a call's question.
                 if (words_ != null && topic === 'call' && rt.text) words_ = rt.text;
                 if (words_ == null) {
                   probs.push(name + "'s topic '" + topic + "' is not one the " + P.template + ' template has words for - '
                              + 'say topic="' + Object.keys(said_).join('" or "') + '"');
                 }
               } else if (rt.help && !content) {
                 words_ = WD.help;
               }
               if (words_ != null && rt.message) {
                 els.push(chromeLabel(L, RW.message, name + ' Message', words_,
                                      messageBox(L, RW.message, words_, rt.message, rt.rect, rt.lines, pt.message),
                                      'message', pt.message));
               }
               if (role === 'confirm' && words_ != null) {
                 (rt.buttons || []).forEach(function (b, i) {
                   var a = answerOf(b, topic, B, RW);
                   els.push(chromeButton(L, name + ' ' + a.word, a.look, a.word, a.yes ? props.does : a.does,
                                         b.rect, rt.rect, 'answer' + i));
                 });
               }
               return { els: els, problems: probs, title: plain && rt.title || null };
             } };
  }
  // The call mode's dialer (role="dialer", a popup in the Center's group):
  // the template's VTC Dialer drawn whole - its title, the entry the program
  // writes the number into, and its keys, each with its seed ID (Dialer
  // Keypad 1 5203, VC Call 5214) and saying what it does - so a designer
  // draws an empty popup and gets the template's. On a bar panel from that
  // panel's own series' frame (`call.center.dialer`), every key at its
  // template's place; a hub's and the 320's templates have no call mode, so
  // there the drawn panel's keys are the popup's controls, laid out as a
  // source popup's are. The keys are the popup's own controls, not derived,
  // each with its seed ID as its `id`: a derived control is keyed by the
  // page it is on, and the 320 pages the dialer over four, where a key on a
  // later page took an ID of its own. They are one joined set, as the
  // template packs them 1 to 10 px apart.
  var DIAL_WORDS = { star: '*', hash: '#', period: '.', call: 'Call', flash: 'Flash', contacts: 'Contacts',
                     keyboard: 'Keyboard', 'delete': 'Delete' };
  var DIAL_LETTERS = { 2: 'abc', 3: 'def', 4: 'ghi', 5: 'jkl', 6: 'mno', 7: 'pqrs', 8: 'tuv', 9: 'wxyz' };
  var DIAL_DOES = { call: 'Places the call to the number entered; lit while the call is up.',
                    flash: 'Sends a hook flash on the call.', contacts: 'Opens the contacts.',
                    keyboard: 'Opens the keyboard.', 'delete': 'Deletes the last character entered.' };
  // The field the program writes the number on, as the template paints it:
  // the smallest filled surface the entry stands in - the entry Label's own
  // paint on Shockwave and Turbulence (white, #DCDCDC), Mach's Input Field
  // Rectangle under it. `drawn`: the dialer's chrome draws its shapes (a bar
  // panel's own, dialerPart), so Mach's field is drawn there and the label
  // takes none; a hub and the 320 draw no chrome of the dialer's, so there
  // the label is the field. Without it the number was black on the well.
  function dialField(d, drawn) {
    var e = d.entry.rect, cx = e[0] + e[2] / 2, cy = e[1] + e[3] / 2;
    var s = (d.surfaces || []).filter(function (x) {
      var r = x.rect;
      return x.fill && (x.kind === 'shape' || x.kind === 'label') && r[0] <= cx && cx <= r[0] + r[2]
        && r[1] <= cy && cy <= r[1] + r[3];
    }).sort(function (a, b) { return a.rect[2] * a.rect[3] - b.rect[2] * b.rect[3]; })[0];
    if (!s || drawn && s.kind === 'shape') return {};
    return { fill: asMeasured(schemeColors(P.schemes[0].id), s.fill) || 'none', border: borderOf(s.border) };
  }
  function dialHosts(d, at, drawn) {
    var DL = RD.dialer || {}, hosts = [];
    function host(type, p, r, key) {
      hosts.push(h('div', { key: key, style: { position: 'absolute', left: (r[0] - at[0]) + 'px', top: (r[1] - at[1]) + 'px',
                                                width: r[2] + 'px', height: r[3] + 'px' } }, h(type, p)));
    }
    if (d.entry) {
      host(Label, Object.assign({ name: d.entry.name || 'Dialer Entry', text: ' ', id: d.entry.id,
                                  does: 'Shows the number entered; the program writes it.' }, DL.entry || {},
                                dialField(d, drawn)),
           d.entry.rect, 'entry');
    }
    var pad = setName('dialer');
    (d.keys || []).forEach(function (k, i) {
      var digit = /^digit-(\d)$/.exec(k.role), dial = digit || k.role === 'star' || k.role === 'hash' || k.role === 'period';
      var word = digit ? digit[1] : DIAL_WORDS[k.role] || k.text || k.role;
      // A key's own look first - Turbulence's Period, its vc_dot - then the
      // keypad's: Period counts as a dialled key, and took `key`'s
      // dialpad_{key}, a file the kit lacks, and was drawn blank.
      var lk = Object.assign({}, DL[k.role] || DL.key || {});
      // Where the template draws no dialer (a hub, the 320) its keys are a
      // source's controls, at no size of the template's: words set past a
      // glyph have no key to be fitted to - the 320's 87 px Contacts ran
      // out of its box - and are drawn on the key, Mach's 880x440 art left
      // off and Shockwave's pills keeping theirs.
      if (!drawn && lk.__caption === 'indent') {
        if (lk.__kit) { delete lk.icon; delete lk.__kit; }
        delete lk.__caption;
      }
      // A kit family per key where the template draws its digits as art
      // (Shockwave's and Turbulence's dialpad_01): `{key}` is 01-09, 00, star
      // or hash. `{letters}` the letters a phone's key carries, where the
      // template draws them under its digit (Mach's 440x440_abc to _wxyz);
      // none on 1, 0, *, # and the period.
      if (lk.icon) {
        lk.icon = String(lk.icon).replace('{key}', digit ? '0' + digit[1] : k.role)
          .replace('{letters}', digit ? DIAL_LETTERS[digit[1]] || '' : '');
        if (!lk.icon) delete lk.icon;
      }
      if (lk.icon && !iconHere(lk, lk.icon)) delete lk.icon;
      var p = Object.assign({ name: k.name || 'Dialer ' + word, text: word, id: k.id,
                              does: dial ? 'Dials ' + word + '.' : DIAL_DOES[k.role] || 'Sends ' + word + '.' }, lk);
      // Its words beside its glyph, fitted to the template's key (Button).
      if (drawn && p.__caption === 'indent') p.__fit = [k.rect[2], k.rect[3]];
      // One block, as the template packs its keypad and the keys round it
      // 1 to 10 px apart: Delete over the keypad's last column, Call, Flash,
      // Contacts and Keyboard beside it.
      p.joined = pad;
      host(Button, p, k.rect, 'key' + i);
    });
    return hosts;
  }
  function dialerPart(props, D, T, name) {
    var FD = frameFor(D), FT = frameFor(T), HT = FT ? null : hubFor(T), PT = !FT && !HT ? pagesFor(T) : null;
    var DD = FD && FD.call && FD.call.center.dialer, DT = FT && FT.call && FT.call.center.dialer;
    if (!DD) return { problem: name + " is the call mode's dialer, which the " + D.model + "'s template does not draw" };
    var given = props.title != null && String(props.title) !== '';
    var title = given ? String(props.title) : DD.text || name;
    if (!DT) {
      // The drawn panel's keys, as a source's controls there.
      var hosts = dialHosts(DD, FD.center.region.slice(0, 2));
      var part = PT ? pagePart(props, 'source', name, title, PT, D, T)
        : HT ? hubPart('source', FD, HT, name, title, D.model, props.group, props)
        : { problem: name + " is the call mode's dialer, which the " + T.model + ' does not draw yet' };
      if (!part.problem) part.items = hosts;
      return part;
    }
    // This panel's own: its keys at its template's places, the popup at its
    // popup region's size, its chrome - the well and title bar Mach draws,
    // the field behind the entry - under them.
    var g = FT.center.region, sg = FD.center.region, box = [0, 0, g[2], g[3]];
    return { D: box, T: box, dsize: [sg[2], sg[3]], size: [g[2], g[3]], looks: {}, items: dialHosts(DT, g.slice(0, 2), true),
             asDrawn: true,
             chrome: function (L) {
               var els = chromePanels(L, (DT.surfaces || []).map(function (s) {
                 return { kind: s.kind, fill: s.fill, border: s.border, r: [s.rect[0] - g[0], s.rect[1] - g[1], s.rect[2], s.rect[3]] };
               }), name + ' Panel', 'dial');
               if (DT.title) {
                 els.push(chromeLabel(L, Object.assign({}, (RD.source || {}).title || {}, (RD.dialer || {}).title || {}),
                                      name + ' Title', title, [DT.title[0] - g[0], DT.title[1] - g[1], DT.title[2], DT.title[3]],
                                      'title', (DT.pt || {}).title));
               }
               return { els: els, problems: [], title: null };
             } };
  }
  // A source popup or a settings window on a hub: a popup of main's group,
  // filling main, under the hub's own header - its strip where it draws one,
  // the title centred across it and a Close back to Select a Source, which
  // a source's grid tile showed it from - and what it holds laid out under
  // that, clear of the Volume Level strip. A source with nothing in it says
  // the hub's empty state; a settings window takes the opaque ground its
  // template gives it (Mach's #303030).
  function hubPart(role, FD, F, name, title, drawn, group, props) {
    var g = F.center.region, at = [g[0], g[1]], names = hubNames(F), c = F.center;
    var sel = (F.select || {}).text || 'Select a Source';
    var titleLook = Object.assign({}, (RD.source || {}).title || {}, HD.title || {});
    var label = Object.assign({}, (RD.source || {}).label || {}, { color: (HD.label || {}).color || 'text' });
    var does = 'Closes ' + title + ' - back to ' + sel + '.';
    if (role === 'source') {
      var SD = sourceParts(FD);
      var bars = (c.surfaces || []).filter(function (x) { return x.popup && x.kind === 'shape'; });
      return { D: SD.body, T: hubHead(F, c.title, c.close && c.close.rect, bars), dsize: SD.size, size: [g[2], g[3]], snug: true,
               hub: 'source',
               looks: { label: label, button: HD.button || (RD.source || {}).button },
               chrome: function (L, content) {
                 var RS = RD.source || {}, els = [], pt = c.pt || {};
                 // Turbulence's device picture, under its title and behind it.
                 var pic = devicePicture(L, F, props || {}, name, title, at) || {};
                 if (pic.el) els.push(pic.el);
                 els = els.concat(hubPanels(L, bars, name + ' Title Bar', 'bar', at));
                 var tr = content ? c.title_controls || c.title : c.title;
                 var tat = tr ? [tr[0] - at[0], tr[1] - at[1], tr[2], tr[3]] : null;
                 if (tat) els.push(chromeLabel(L, titleLook, name + ' Title', title, tat, 'title', pt.title));
                 if (c.close) els.push(hubClose(L, F, name, at, c.close.rect, names.select, does));
                 var words_ = WD.hub_empty || WD.empty;
                 if (!content && words_ && c.empty) {
                   els.push(chromeLabel(L, Object.assign({}, RS.empty || {}, { color: label.color }), name + ' Empty',
                                        said(words_, title), [c.empty[0] - at[0], c.empty[1] - at[1], c.empty[2], c.empty[3]],
                                        'empty', pt.empty));
                 }
                 return { els: els, problems: pic.problem ? [pic.problem] : [], title: tat,
                          notes: pic.warning ? [pic.warning] : [] };
               } };
    }
    var rec = windowOf(F, 'settings', title) || {}, rd = windowOf(FD, 'settings', title);
    if (!rd || !rd.rect) return { problem: name + ' is a settings window, which the ' + drawn + "'s template does not draw" };
    var O = HD.options || {};
    return { D: rd.rect, T: hubHead(F, rec.title, rec.close && rec.close.rect, rec.surfaces), dsize: null, size: [g[2], g[3]], snug: true,
             looks: { label: Object.assign({}, label, O.label || {}), button: O.button || (RD.window || {}).button },
             hub: 'settings',
             // Main's group: the designer's, else the region page's Center's,
             // which the translator binds it to (`main_group`) - a settings
             // window is a modal on the 1035, and names none.
             popup: { group: group || 'Sources', main: !group, background: O.background || null },
             chrome: function (L) {
               var els = hubPanels(L, rec.surfaces, name + ' Header', 'head', at), pt = rec.pt || {};
               var tat = rec.title ? [rec.title[0] - at[0], rec.title[1] - at[1], rec.title[2], rec.title[3]] : null;
               if (tat) els.push(chromeLabel(L, Object.assign({}, titleLook, O.title || {}), name + ' Title', title, tat, 'title', pt.title));
               if (rec.close) els.push(hubClose(L, F, name, at, rec.close.rect, names.select, does, O.close));
               return { els: els, problems: [], title: tat };
             } };
  }
  // What the designer put in a source popup or a window, laid out in its
  // box: as drawn on the panel drawn, and on another from the drawn panel's
  // box into this one's at one scale, centred - the 725's well from the
  // 1035's - each in the look the template gives what stands there (white
  // labels on Mach's well, its ghost keys) unless it sets its own. A plain
  // container, and a child with no rect, is drawn at its own place in a
  // layer moved by the box's origin, since the layout draws it at its CSS
  // place in the box and that place is the page's: a flex row drawn at
  // 420,520 in Mach's Lighting came out 64 px lower, under the band's top.
  // `placed`: where each child with a rect comes out, in the page's
  // coordinates, before it grows to its minimum.
  function framedLayout(items, part, L) {
    var Dc = part.D, Tc = part.T, looks = part.looks || {};
    // A hub's main is about half the 1035's band (`snug`): what was put in
    // the window or the well is mapped from the box round it, a gap clear,
    // centred in the hub's, and scaled up no more than the hub's touch
    // minimum is the drawn panel's. Mapped from the whole window, Mach's
    // Audio came out at half size and its Mic heading, grown back to the
    // 525's type floor, ran into its Mute; at the 1035's size on the 535,
    // whose touch minimum is twice the 1035's, its Doc Cam keys grew from 60
    // to 104 px into each other 100 px apart.
    if (part.snug) {
      var bb = null;
      items.forEach(function (it) {
        if (!it.rect || it.kind === 'mainarea' || it.kind === 'rail' || REGION_NAMES[it.kind]) return;
        var r = it.rect;
        bb = bb ? [Math.min(bb[0], r[0]), Math.min(bb[1], r[1]), Math.max(bb[2], r[0] + r[2]), Math.max(bb[3], r[1] + r[3])]
                : [r[0], r[1], r[0] + r[2], r[1] + r[3]];
      });
      if (bb) {
        var pad = L.panel.gap;
        Dc = [bb[0] - pad, bb[1] - pad, bb[2] - bb[0] + 2 * pad, bb[3] - bb[1] + 2 * pad];
        var up = Math.max(1, L.panel.touch / ((L.design && L.design.touch) || L.panel.touch));
        var sn = Math.min(up, Tc[2] / Dc[2], Tc[3] / Dc[3]);
        var sw = Math.round(Dc[2] * sn), sh = Math.round(Dc[3] * sn);
        Tc = [Tc[0] + Math.round((Tc[2] - sw) / 2), Tc[1] + Math.round((Tc[3] - sh) / 2), sw, sh];
      }
    }
    var f = fit([0, 0, Dc[2], Dc[3]], [0, 0, Tc[2], Tc[3]]), placed = [];
    var moved = items.map(function (it, i) {
      var look = it.kind === 'label' ? looks.label : it.kind === 'button' ? looks.button : null;
      var extra = look && it.comp ? unset(it.props, look) : {};
      var comp = it.comp && Object.keys(extra).length ? React.cloneElement(it.comp, extra) : it.comp;
      var host = comp === it.comp ? it.host : it.host === it.comp ? comp : React.cloneElement(it.host, {}, comp);
      var own = it.kind === 'mainarea' || it.kind === 'rail' || REGION_NAMES[it.kind];
      if ((it.kind === 'box' || !it.rect) && !own) {
        host = h('div', { key: 'at' + i, style: { position: 'absolute', left: -Dc[0] + 'px', top: -Dc[1] + 'px',
                                                  width: 0, height: 0 } }, host);
      }
      if (it.rect) {
        placed.push({ it: it, r: [Tc[0] + f.x + (it.rect[0] - Dc[0]) * f.s, Tc[1] + f.y + (it.rect[1] - Dc[1]) * f.s,
                                  it.rect[2] * f.s, it.rect[3] * f.s] });
      }
      return Object.assign({}, it, { host: host, comp: comp, props: comp ? comp.props : it.props,
                                     rect: it.rect ? [it.rect[0] - Dc[0], it.rect[1] - Dc[1], it.rect[2], it.rect[3]] : null });
    });
    var out = scaleLayout(moved, [0, 0, Dc[2], Dc[3]], L.panel, L, [0, 0, Tc[2], Tc[3]], null);
    return { els: [h('div', { key: 'framed', style: { position: 'absolute', left: Tc[0] + 'px', top: Tc[1] + 'px',
                                                       width: Tc[2] + 'px', height: Tc[3] + 'px' } }, out.els)],
             problems: out.problems, k: out.k, placed: placed };
  }

  // -- Hubs: the 520s' and 535s' working page --------------------------------
  // (docs/superpowers/specs/2026-10-22-region-frame-design.md, PR6.) A hub
  // draws no header bar, footer or left rail: a right menu bar - Volume, Up,
  // Down, Mute, a settings opener and Power, as its own frame measured them
  // (P.frames, `hub`) - and one popup region filling main, in which every
  // popup appears: a Select a Source grid first, each source's popup with
  // its own header and a Close back to the grid, and its settings. So the
  // same region page derives to that grammar there, from the hub's own frame,
  // and nothing on it is dropped: the Header's source tabs are the grid's
  // tiles, each the same control (its name, so its ID); the RightRail and
  // the Footer's Power are the menu bar, Help the grid's header; the
  // LeftRail's first Section is the popup the hub's Display Control opens
  // (Shockwave's and Turbulence's from the bar, Mach's from a tile in its
  // Settings), its later Sections' launchers, an Audio Control and the
  // footer's mode launcher the options its settings opener shows. What the
  // hub has no place for - the footer's clock, a Header's start and end -
  // is named on the canvas and in the page's `left`, which the translator
  // lets be absent there. What the layout adds - the grid's title and
  // labels, the openers, Up and Down, every Close - is derived; Up, Down and
  // the openers keep the hub's own seed IDs (gdl.design.pin_ids).
  var HD = RD.hub || {};
  function hubFor(T) {
    var F = FRAMES[T.series];
    return F && F.hub && !T.turned && T.tier !== 'C' ? F : null;
  }
  function byRole(items) {
    var o = {};
    (items || []).forEach(function (x) { if (!o[x.role]) o[x.role] = x; });
    return o;
  }
  // The popups a hub's page derives, by the template's own names.
  function hubNames(F) {
    var R = byRole(F.right.items);
    return { select: (F.select || {}).popup || 'Select Source', options: (F.options || {}).popup || 'More Options',
             display: R.display ? R.display.name : 'Display Settings', level: 'Volume Level' };
  }
  // The template's token for a measured colour, else the nearest it has,
  // alpha weighed most: Shockwave's side bar, #2B2424 at alpha 110, and
  // Turbulence's, black at 110, draw as their `header`, black at 115 - not
  // Turbulence's `rail`, black at 38, which tokenNear's colour-only match
  // gave.
  function tokenClose(colors, v) {
    var t = tokenOf(colors, v);
    if (t || !v) return t;
    var want = hex8(v), best = null, d0 = Infinity;
    function ch(s, i) { return parseInt(s.slice(1 + 2 * i, 3 + 2 * i), 16); }
    Object.keys(colors).forEach(function (n) {
      var c = hex8(colors[n]);
      if (!/^#[0-9A-F]{8}$/.test(c)) return;
      var d = 0;
      for (var i = 0; i < 4; i++) d += Math.pow(ch(c, i) - ch(want, i), 2) * (i === 3 ? 4 : 1);
      if (d < d0) { d0 = d; best = n; }
    });
    return best;
  }
  // A measured colour as the template draws it: its token where one is
  // exactly it, else - opaque - itself, as #RRGGBB (the spec reads eight
  // digits alpha first, CSS alpha last; six read alike), else the nearest
  // token. Template chrome, which the six-colour cap exempts.
  function asMeasured(colors, v) {
    var t = tokenOf(colors, v);
    if (t || !v) return t;
    var c = hex8(v);
    return /^#[0-9A-F]{6}FF$/.test(c) ? c.slice(0, 7) : tokenClose(colors, v);
  }
  function hubPanels(L, list, name, key, at) {
    var n = 0;
    return (list || []).filter(function (s) { return s.kind === 'shape'; }).map(function (s, i) {
      n += 1;
      var r = at ? [s.rect[0] - at[0], s.rect[1] - at[1], s.rect[2], s.rect[3]] : s.rect;
      return drawnAt(Panel, { name: name + (n > 1 ? ' ' + n : ''), fill: tokenClose(L.colors, s.fill) || P.defaults.panel.fill,
                              border: borderOf(s.border), stroke: 'none', derived: true }, r, key + i);
    });
  }
  // A look's icon, where its kit draws one at its size, and whether the
  // button then carries no caption: an icon look on a hub draws its glyph
  // alone, its name in a label under it or in its `does`.
  // The region's own default in the hub's look for its role, where the hub
  // draws one its kit has: Mach's menu bar draws Mute and Power as glyphs.
  function hubLook(props, look) {
    if (!look) return props;
    var out = Object.assign({}, props, look);
    if (look.icon && !iconHere(out, look.icon)) return props;
    return out;
  }
  function iconHere(look, icon) {
    var V = P.buttons[look.variant] || P.buttons[P.defaults.button.variant];
    var size = V.kit || look.__kit || (V.with_icon && V.with_icon.bare);
    return icon && size && KIT && KIT.files && KIT.files[size] && KIT.files[size][icon] ? icon : null;
  }
  // A hub's popup's header: its strip, title and Close, in the popup's own
  // coordinates, and the box under it that what it holds is laid out in -
  // centred on the whole popup, as the template centres its sources' keys,
  // and clear of the Volume Level strip it stands at main's right: as wide
  // each side of the middle as the strip leaves on its side. Clear of the
  // strip alone, the box was the 651 px left of it, and Mach 525's Doc Cam
  // came out 15 px from the screen's edge where the template's is 55.
  function hubHead(F, title, close, bars) {
    var g = F.center.region, foot = 0;
    [title, close].concat((bars || []).map(function (s) { return s.rect; })).forEach(function (r) {
      if (r) foot = Math.max(foot, r[1] - g[1] + r[3]);
    });
    var strip = F.center.strip, right = strip ? Math.min(g[2], strip[0] - g[0]) : g[2];
    var half = Math.max(0, right - g[2] / 2);
    return [Math.round(g[2] / 2 - half), foot, Math.round(2 * half), g[3] - foot];
  }
  // A popup's Close on a hub: back to the grid its group starts from.
  function hubClose(L, F, name, at, rect, to, does, own) {
    var look = Object.assign({}, own || HD.close || RD.window && RD.window.close || {});
    var icon = iconHere(look, look.icon);
    var r = [rect[0] - at[0], rect[1] - at[1], rect[2], rect[3]];
    var p = Object.assign({ name: name + ' Close', derived: true, nav: to, does: does }, look);
    if (look.icon && !icon) delete p.icon;
    var V = P.buttons[p.variant] || P.buttons[P.defaults.button.variant];
    var img = imageOf(V, p, null);
    if (icon || look.icon) p.text = '';
    else if (!(img && img.caption === 'none')) p.text = (WD.buttons || {}).close || 'Close';
    var g = F.center.region;
    var at2 = settle(r, needOf('button', p, L), [0, 0, g[2], g[3]], [g[2], g[3]], [false, false, false, false]);
    return drawnAt(Button, p, at2, 'close');
  }
  // A designer's control drawn anew at `r` with `extra` props, and with
  // `children` in place of its own where given (a tile's caption moves to
  // its label).
  function hubHost(it, r, key, extra, children) {
    if (!it.comp) return React.cloneElement(it.host, { key: key, style: cell(r) });
    var comp = children !== undefined ? React.cloneElement(it.comp, extra || {}, children)
                                      : React.cloneElement(it.comp, extra || {});
    if (it.host === it.comp) return h('div', { key: key, style: cell(r) }, comp);
    return React.cloneElement(it.host, { key: key, style: cell(r) }, comp);
  }
  // A grid's places for `n` tiles: the template's tile, its rows and its
  // pitch, each row centred where its first row is, the label under each
  // where the template sets one - wider than its tile where the template's
  // is (Mach's Streaming). Grown to the panel's touch minimum. Where the
  // template draws one row (an options grid), more tiles than it draws stay
  // in that row while they fit between `room`'s ends a gap clear, closer
  // than its pitch but a gap apart, and else wrap into rows centred on it -
  // Shockwave's More Options draws two in one centred row, and three wrapped
  // 2+1 from under its header.
  function gridSpots(G, n, T, H, top, room) {
    var t = (G && G.tiles) || [];
    if (!t.length || !n) return [];
    var first = t[0].rect, rows = [], cols = 0;
    t.forEach(function (x) {
      if (Math.abs(x.rect[1] - first[1]) <= 20) cols += 1;
      if (!rows.some(function (y) { return Math.abs(y - x.rect[1]) <= 20; })) rows.push(x.rect[1]);
    });
    var w = Math.max(first[2], T.touch), ht = Math.max(first[3], T.touch);
    var lab = t[0].label, off = lab ? [lab[1] - first[1], lab[3]] : null;
    var lw = 0;
    t.forEach(function (x) { if (x.label) lw = Math.max(lw, x.label[2]); });
    var px = cols > 1 ? t[1].rect[0] - first[0] : w + T.gap;
    var py = rows.length > 1 ? rows[1] - rows[0] : (off ? off[0] + off[1] : ht) + T.gap;
    var row0 = t.slice(0, cols), cx = row0.reduce(function (s, x) { return s + x.rect[0] + x.rect[2] / 2; }, 0) / cols;
    var R = Math.ceil(n / cols), cellH = off ? Math.max(off[0], ht) + off[1] : ht;
    var y0 = rows[0], lwide = Math.max(lw, w);
    if (rows.length === 1 && n > cols && room) {
      var span = room[1] - room[0] - 2 * T.gap - w, fits = n > 1 ? span / (n - 1) : px;
      if (fits >= w + T.gap) {
        cols = n; px = Math.min(px, Math.floor(fits)); R = 1;
      } else {
        // Rows a gap apart, centred where the template's one row is.
        py = Math.min(py, cellH + T.gap);
        var block = (R - 1) * py + cellH;
        y0 = Math.round(rows[0] + cellH / 2 - block / 2);
        y0 = Math.max(top || 0, Math.min(y0, (H || y0 + block + T.gap) - T.gap - block));
        rows = [];
      }
      // The whole row clear of the room's ends, a gap in.
      var half = ((Math.min(cols, n) - 1) * px + w) / 2;
      cx = Math.min(Math.max(cx, room[0] + T.gap + half), room[1] - T.gap - half);
      if (cols > 1 && px < lwide + 2) lwide = Math.max(w, px - 2);
    }
    // More rows than the template draws, run past main's foot: they close up
    // to a gap apart and the grid rises toward its header - Shockwave's More
    // Options draws two in one row, and a third came out under the screen.
    if (H && rows.length && R > rows.length && y0 + (R - 1) * py + cellH > H - T.gap) {
      py = Math.min(py, cellH + T.gap);
      y0 = Math.max(top || 0, Math.min(y0, H - T.gap - ((R - 1) * py + cellH)));
      rows = [];
    }
    var out = [];
    for (var i = 0; i < n; i++) {
      var r = Math.floor(i / cols), c = i % cols, cnt = Math.min(cols, n - r * cols);
      var x = Math.round(cx - ((cnt - 1) * px) / 2 + c * px - w / 2);
      var y = r < rows.length ? rows[r] : (rows.length ? rows[0] : y0) + r * py;
      var tile = [x, y, w, ht];
      out.push({ tile: tile, label: off ? [Math.round(x + (w - lwide) / 2), y + Math.max(off[0], ht),
                                           lwide, off[1]] : null });
    }
    return out;
  }
  // A grid's tiles: each designer control at its place in `look`, its
  // caption in a label under it where it draws an icon alone - or always,
  // where the template's tiles are captioned under (`under`: the options).
  function gridTiles(L, G, list, at, set, labelLook, pt, where, probs) {
    // The room a row has: centred on main, as wide each side of its middle
    // as the Volume Level strip leaves on its side (hubHead's box) - kept
    // clear of the strip alone, Mach 535's four options stood 40 px left of
    // the middle.
    var g = L.region.F.center.region, S = L.region.F.center.strip, right = S ? S[0] : g[0] + g[2];
    var spots = gridSpots(G, list.length, L.panel, g[1] + g[3],
                          G && G.title ? G.title[1] + G.title[3] + L.panel.gap : 0,
                          [g[0] + Math.max(0, g[0] + g[2] - right), right]), els = [], placed = [];
    list.forEach(function (x, i) {
      var sp = spots[i];
      if (!sp) return;
      var tile = [sp.tile[0] - at[0], sp.tile[1] - at[1], sp.tile[2], sp.tile[3]];
      var p = x.it ? propsOf(x.it) : x.props, caption = x.caption != null ? x.caption : textOf(p.children, p.text);
      var extra = Object.assign({}, x.look || {});
      // A header tab's own look is the header's (its type, its fill): as a
      // tile it takes the hub's. A launcher's is the designer's, and stays.
      if (x.strip) {
        ['size', 'align', 'fill', 'border', 'stroke', '__indent'].forEach(function (k) { if (p[k] != null) extra[k] = undefined; });
      }
      if (set) extra.joined = set;
      // A tab's tile that draws another family of the tab's glyph names the
      // suffix its glyph drops (`glyph`): Shockwave's tab draws the 744x456
      // laptop_white, its hub's tile the whole device, white_laptop. Not an
      // option's tile, whose look the hub's tile look underlies.
      var want = p.icon || extra.icon, glyph = extra.glyph;
      delete extra.glyph;
      if (x.strip && want && glyph && String(want).slice(-glyph.length) === glyph) {
        var dev = String(want).slice(0, -glyph.length);
        // A device the family lacks (blu-ray-2) keeps its tab's own art.
        if (iconHere(Object.assign({}, p, extra), dev)) want = extra.icon = dev;
        else extra.variant = undefined;
      }
      var icon = iconHere(Object.assign({}, p, extra), want);
      var alone = (!!icon || !!x.under) && !!sp.label;
      if (alone) extra.text = '';
      if (p.icon && !icon) extra.icon = undefined;
      var need = needOf('button', Object.assign({}, p, extra, alone ? { children: null } : {}), L);
      tile = settle(tile, need, [0, 0, g[2], g[3]], [g[2], g[3]], [false, false, false, false]);
      els.push(x.it ? hubHost(x.it, tile, where + 't' + i, extra, alone ? null : undefined)
                    : drawnAt(Button, Object.assign({}, x.props, extra, { text: alone ? '' : caption }), tile, where + 't' + i));
      placed.push(tile);
      if (alone && caption) {
        var lr = [sp.label[0] - at[0], Math.max(sp.label[1] - at[1], tile[1] + tile[3]), sp.label[2], sp.label[3]];
        els.push(chromeLabel(L, labelLook, (p.name || caption) + ' Label', caption, lr, where + 'l' + i, pt));
      }
      if (tile[1] + tile[3] > g[3] || (sp.label && sp.label[1] + sp.label[3] - at[1] > g[3])) {
        probs.push(where + ' holds ' + list.length + ', more than the ' + L.model + "'s template has room for");
      }
    });
    return els;
  }
  // The menu bar's buttons down its band: the template's places, each grown
  // to what it needs, one stack kept in order - its seams closed up where
  // they no longer fit (Shockwave 535's buttons grow from 81 to its 104 px
  // minimum), and then a cell taller than it needs (its 136 px Power) gives
  // way. One joined set, as the template stands its menu 0 to 25 px apart.
  function stackMenu(slots, band, L, probs) {
    if (!slots.length) return;
    var size = slots.map(function (s) { return Math.max(s.r[3], Math.ceil(s.need[1])); });
    var seams = slots.map(function (s, i) {
      return i ? Math.max(0, s.r[1] - (slots[i - 1].r[1] + slots[i - 1].r[3])) : 0;
    });
    var start = slots[0].r[1], room = band[1] + band[3] - start;
    function sum(a) { return a.reduce(function (x, y) { return x + y; }, 0); }
    var n = slots.length;
    if (sum(size) + sum(seams) > room) {
      // Each seam the template opens keeps a share of what is left, at least
      // 1 px; where nothing is left they close, as Turbulence's rings touch.
      var free = room - sum(size), have = sum(seams);
      var nz = seams.filter(function (g) { return g > 0; }).length;
      seams = seams.map(function (g) {
        if (!g || free < nz) return 0;
        return have > nz ? 1 + Math.floor((g - 1) * (free - nz) / (have - nz)) : 1;
      });
    }
    var over = sum(size) + sum(seams) - room;
    var spare = slots.map(function (s, i) { return Math.max(0, size[i] - Math.ceil(s.need[1])); });
    // A pixel at a time from the cell with the most to spare.
    while (over > 0) {
      var most = spare.indexOf(Math.max.apply(null, spare));
      if (spare[most] <= 0) break;
      size[most] -= 1; spare[most] -= 1; over -= 1;
    }
    if (over > 0) probs.push("the menu bar holds more than the " + L.model + "'s has room for");
    var y = start;
    slots.forEach(function (s, i) {
      y += seams[i];
      var w = Math.max(s.r[2], Math.ceil(s.need[0]));
      var x = s.r[0] - Math.floor((w - s.r[2]) / 2);
      if (w <= band[2]) x = Math.min(Math.max(x, band[0]), band[0] + band[2] - w);
      s.at = [x, y, w, size[i]];
      y += size[i];
    });
  }
  // The popups a hub's page derives, over its main region: the program's
  // first is the grid - shown on the canvas until an opener shows another,
  // or `window.__GDL_SHOW` names one.
  function HubParts(props) {
    var st = React.useState(props.parts.length ? props.parts[0].name : null);
    props.shown.set = st[1];
    var forced = typeof window !== 'undefined' && window.__GDL_SHOW ? String(window.__GDL_SHOW) : null;
    var names = props.parts.map(function (q) { return q.name; });
    var cur = forced && names.indexOf(forced) >= 0 ? forced : st[0];
    // The Volume Level strip is a popup of its own the program shows over
    // main as the volume moves: on the canvas, only when asked for.
    return props.parts.map(function (q) {
      var look = { kind: 'popup', name: q.name, group: q.group, size: q.size };
      if (q.background) look.background = q.background;
      // The grid main's popup region shows first: the group a hub's settings
      // popups go in, wherever their boards stand on the canvas.
      if (q.main) look.main = true;
      var L = props.L;
      // The options and Display Control on the page's photo, as Shockwave's
      // and Turbulence's own are (regions.hub.popup.photo); Select a Source is the
      // page's own grid there, and the Volume Level strip its own ground.
      var pl = q.photo && L.pageLook && L.pageLook.background_image ? L.pageLook : null;
      if (pl) {
        look.background_image = pl.background_image;
        look.background_file = pl.background_file;
      }
      var photo = pl && P.backdrops ? P.backdrops[L.panel.series + '|' + pl.theme] : null;
      return h(Ctx.Provider, { key: 'hub-' + q.name, value: Object.assign({}, L, { within: 'popup', pageName: q.name }) },
        h('div', { 'data-gdl-part': JSON.stringify(look),
                   style: { position: 'absolute', left: q.at[0] + 'px', top: q.at[1] + 'px', width: q.size[0] + 'px',
                            height: q.size[1] + 'px', zIndex: 5,
                            background: (photo ? 'url("' + photo + '") 0 0 / 100% 100% no-repeat, ' : '')
                              + (q.background ? paint(L.colors, q.background) : 'transparent'),
                            visibility: (q.alone ? forced === q.name : cur === q.name) ? 'visible' : 'hidden' } },
          q.els));
    });
  }
  // A Section's controls in a popup's box: its heading over a row of them,
  // centred, each as wide as the widest needs and at least the panel's touch
  // minimum, wrapping where the row does not fit; in the template's look for
  // a rail's display group unless the designer set their own.
  // `own`: the look a member takes where the designer gives none - one look,
  // or a function of the member (a call page's keys, each its own). `opts`:
  // `cell`, the least a cell is ([w, h]), and `title`, the popup's own, which
  // a heading saying it again is not drawn under.
  function sectionIn(L, sec, box, where, labelLook, probs, own, opts) {
    var sp = propsOf(sec), members = itemsOf(sp.children), els = [], o = opts || {};
    var T = L.panel, g = T.gap, cw = Math.max(T.touch, o.cell ? o.cell[0] : 0), ch = Math.max(T.touch, o.cell ? o.cell[1] : 0);
    var looks = members.map(function (it) {
      if (it.kind !== 'button') return {};
      var lk = (typeof own === 'function' ? own(it) : own) || RD.rail, x = unset(it.props, lk);
      // A call key's lit look, as the call page draws it (statesOver).
      var st = typeof own === 'function' ? statesOver((it.props || {}).states, lk) : null;
      if (st) x.states = st;
      return x;
    });
    members.forEach(function (it, i) {
      var nd = needOf(it.kind, Object.assign({}, it.props || {}, looks[i]), L);
      if (it.kind === 'button') { cw = Math.max(cw, Math.ceil(nd[0])); ch = Math.max(ch, Math.ceil(nd[1])); }
    });
    // A cell grown wider for its words keeps the shape it was given: Mach's
    // call keys came out 120x66 on the 525, too shallow at its 18 pt for
    // their words a line under the 755x440 icon, which the translator then
    // set over it.
    if (o.cell) ch = Math.max(ch, Math.round(cw * o.cell[1] / o.cell[0]));
    // The hub's VTC popup is titled with its Section's heading, and drew
    // VTC under VTC.
    var head = sp.title && String(sp.title).toLowerCase() !== String(o.title || '').toLowerCase() ? sp.title : null;
    var headH = head ? Math.ceil(needOf('label', Object.assign({ text: head }, labelLook), L)[1]) : 0;
    var per = Math.max(1, Math.floor((box[2] - 2 * g + g) / (cw + g)));
    var rows = Math.ceil(members.length / per), block = headH + (headH ? g : 0) + rows * ch + (rows - 1) * g;
    var top = box[1] + Math.max(g, Math.round((box[3] - block) / 2));
    // Its heading is the canvas's, as the LeftRail draws it: one control,
    // one ID, on every panel.
    if (head) {
      els.push(drawnAt(Label, Object.assign({ name: head + ' Heading', text: head }, labelLook),
                       [box[0] + g, top, box[2] - 2 * g, headH], where + 'h'));
    }
    var spots = gridPlace(members.length, per, cw, ch, g, box[2], 0, 0);
    members.forEach(function (it, i) {
      var r = [box[0] + spots[i][0], top + headH + (headH ? g : 0) + spots[i][1], cw, ch];
      els.push(hubHost(it, r, where + i, looks[i]));
      if (r[1] + r[3] > box[1] + box[3]) {
        probs.push((sp.title || 'A Section') + ' holds more than the ' + L.model + "'s popup has room for");
      }
    });
    return els;
  }

  // The hub's working page from the page's regions: the menu bar on the
  // page, its popup regions, and the popups it derives - `els` - with what
  // it named (`probs`, `warns`) and the canvas controls it has no place for
  // (`left`).
  function planHub(regs, L, pname) {
    var F = L.region.F, T = L.panel, R = byRole(F.right.items), C = F.center, g = C.region;
    var names = hubNames(F), at = [g[0], g[1]];
    var probs = [], warns = [], left = [], els = [], parts = [];
    var by = {};
    regs.forEach(function (it) { if (!by[it.kind]) by[it.kind] = propsOf(it); });
    var group = (by.center && by.center.group) || 'Sources';
    var shown = {};
    function opener(name) { return function () { if (shown.set) shown.set(name); }; }
    var labelLook = Object.assign({}, RD.heading || {}, HD.label || {});
    var titleLook = Object.assign({}, (RD.source || {}).title || {}, HD.title || {});
    var O = HD.options || {};
    var optTitle = Object.assign({}, titleLook, O.title || {}), optLabel = Object.assign({}, labelLook, O.label || {});
    // What each region holds. A call page's Share Content goes with its call
    // keys (below): the hub's template has no call mode, and it is the call's.
    var tabs = [], callPage = L.region.role === 'call', share = null;
    if (by.header) {
      itemsOf(by.header.children).forEach(function (it) {
        if (slotOf(it) === 'source') tabs.push(it);
        else if (callPage && slotOf(it) === 'share' && !share) share = it;
        else {
          left.push(nameOf(it));
          warns.push(pname + "'s " + nameOf(it) + ' is left off the ' + L.model + ' - its template has no header bar '
                     + 'for the Header\'s ' + (slotOf(it) || 'unslotted') + ' controls');
        }
      });
    }
    var rr = by.rightrail ? slotted(by.rightrail.children, ['heading', 'volume', 'mute', 'audio'], 'RightRail', 'right', L)
      : { over: {}, probs: [] };
    var ft = by.footer ? slotted(by.footer.children, ['mode', 'clock', 'help', 'power'], 'Footer', 'bottom', L)
      : { over: {}, probs: [] };
    probs = probs.concat(rr.probs, ft.probs);
    var secs = [];
    if (by.leftrail) {
      itemsOf(by.leftrail.children).forEach(function (it) {
        if (it.kind === 'section') secs.push(it);
        else probs.push(nameOf(it) + ' in the LeftRail is not in a Section - put the rail\'s controls in titled Sections');
      });
    }
    if (by.center) {
      itemsOf(by.center.children).forEach(function (it) {
        probs.push(nameOf(it) + ' in the Center: it is the popup region its sources fill - put a source\'s controls in '
                   + 'its popup');
      });
    }
    // The footer's clock: no hub template draws one.
    if (by.footer) {
      var clockName = ft.over.clock ? nameOf(ft.over.clock) : 'Date Time';
      left.push(clockName);
      warns.push(pname + "'s " + clockName + ' is left off the ' + L.model + ' - its template draws no clock');
    }
    // The options its settings opener shows: the display group's popup
    // (Mach's, from a tile there), the later Sections' launchers, Audio
    // Control and the mode launcher - each the template's tile, its glyph
    // the kit's where one names what it opens (`glyphs`: Lighting's bulb,
    // Audio's speaker) and its caption the label under it, as every tile of
    // the template's own is; one the kit has no glyph for is its blank tile
    // (`blank`) - a source tile's look alone drew a laptop on Lighting. On
    // an opaque popup the tiles take its own look (Mach's Settings: raised
    // keys on #303030, where the photo's shade read as black holes).
    var tileLook = Object.assign({}, HD.tile || {}, O.tile || {});
    var blankLook = Object.assign({}, O.blank || RD.launcher || RD.rail || {});
    function launcher(it) {
      var p = propsOf(it), cap = String(textOf(p.children, p.text) || p.name || '').toLowerCase();
      var mine = p.icon && iconHere(Object.assign({}, p, tileLook), p.icon);
      var key = Object.keys(O.glyphs || {}).filter(function (k) { return cap.indexOf(k) >= 0; })[0];
      var glyph = mine || (key && iconHere(tileLook, O.glyphs[key]));
      return { it: it, under: true, look: glyph ? Object.assign({}, tileLook, { icon: glyph }) : Object.assign({}, blankLook) };
    }
    // A call page's first Section is its call keys, not the display's: a
    // popup of its own (below), titled with its heading.
    var callSec = callPage ? secs[0] || null : null;
    var display = callPage ? null : secs[0] || null, displayTitle = display ? (R.display ? R.display.name : names.display) : null;
    var callName = callSec ? propsOf(callSec).title || 'Call' : null;
    var options = [];
    if (callSec) {
      options.push({ it: null, caption: callName, under: true,
                     props: { name: callName, derived: true, nav: callName, does: 'Opens ' + callName + '.',
                              onPress: opener(callName) },
                     look: Object.assign({}, tileLook) });
    }
    if (display && !R.display) {
      options.push({ it: null, caption: propsOf(display).title || 'Display', under: true,
                     props: { name: names.display, derived: true, nav: names.display,
                              does: 'Opens ' + names.display + '.', icon: (HD.display || {}).icon,
                              onPress: opener(names.display) },
                     look: Object.assign({}, tileLook) });
    }
    // A later Section's heading, which the drawn panel's rail draws over its
    // group (Mach's Settings), has no place among the options: named.
    var FDL = (frameFor(L.design) || {}).left;
    secs.slice(1).forEach(function (sec, i) {
      var title = propsOf(sec).title, G = FDL && FDL.groups && FDL.groups[i + 1];
      if (title && G && G.heading) {
        left.push(title + ' Heading');
        warns.push(pname + "'s " + title + ' Heading is left off the ' + L.model + " - its template's options "
                   + 'draw no heading');
      }
      itemsOf(propsOf(sec).children).forEach(function (it) { options.push(launcher(it)); });
    });
    if (rr.over.audio) options.push(launcher(rr.over.audio));
    if (ft.over.mode) options.push(launcher(ft.over.mode));
    options.forEach(function (o) {
      // A designer's own look stays theirs.
      if (o.it) Object.keys(o.look).forEach(function (k) { if ((o.it.props || {})[k] != null) delete o.look[k]; });
    });

    // The menu bar.
    if (F.right) {
      els = els.concat(hubPanels(L, F.right.surfaces, 'Menu Bar', 'menu'));
      var band = F.right.rect, menu = [], level = null, set = setName('menu');
      var vol = null;
      if (by.rightrail) {
        var hd = rr.over.heading, hdef = R.heading ? chrome('heading', R.heading, L) : null;
        if (hd || hdef) {
          // In the hub's own look where it has one: Mach's is white on its
          // bar, where the 1035's rail heading is black on the photo.
          var hlook = Object.assign({}, RD.heading || {}, HD.heading || {});
          var hp = hd ? hd.props || {} : Object.assign({}, hdef[1], HD.heading || {});
          var hr = R.heading ? R.heading.rect : [band[0], band[1], band[2], 40];
          var hat = settle(hr, needOf('label', hp, L), band, T.size, [false, false, false, false]);
          els.push(hd ? hubHost(hd, hat, 'menu-heading', unset(hd.props, hlook)) : drawnAt(Label, hp, hat, 'menu-heading'));
        }
        vol = rr.over.volume ? Object.assign({}, rr.over.volume.props || {}) : chrome('volume', {}, L)[1];
      }
      var steps = P.defaults.level.steps || {}, vname = vol ? vol.name || 'Volume' : 'Volume';
      // An opener on the bar: the template's glyph alone where its look
      // draws one, else its name - and both where the look keeps its caption
      // under its glyph (`caption`: Turbulence's More, its ••• over 'More').
      // `caption: "over"` sets them over it instead (Turbulence's Display
      // Control, its words on the template's blank tile).
      function openerProps(x, ol, to, does) {
        var keep = ol.caption, oi = iconHere(ol, ol.icon);
        delete ol.caption;
        if (keep === 'over') ol.__breaks = 0;
        var words_ = x.name.split(' ').join('\n');
        var p = Object.assign({ name: x.name, derived: true, id: x.id, nav: to, does: does }, ol,
                              oi ? { icon: oi, text: keep ? words_ : '' } : { icon: undefined, text: words_ });
        p.onPress = opener(to);
        return p;
      }
      F.right.items.forEach(function (x) {
        var role = x.role, look = Object.assign({}, HD.menu || {}), it = null, props = null;
        if ((role === 'volume-up' || role === 'volume-down') && vol) {
          // The hub's own glyph (`up`, `down`): Mach's chevrons, where the
          // level's steps are its speaker+ and speaker-; Shockwave's a
          // chevron its Open Sans draws, as its kit has none.
          var up = role === 'volume-up', ul = Object.assign({}, look, HD[up ? 'up' : 'down'] || {});
          var icon = iconHere(ul, ul.icon !== undefined ? ul.icon : steps[up ? 'up' : 'down']);
          var said = ul.text != null ? ul.text : up ? '+' : '-';
          delete ul.icon; delete ul.text;
          props = Object.assign({ name: vname + (up ? ' Up' : ' Down'), derived: true, id: x.id,
                                  does: (up ? 'Raises ' : 'Lowers ') + vname + ' one step.' }, ul,
                                icon ? { icon: icon, text: '' } : { text: said });
        } else if (role === 'mute' && by.rightrail) {
          it = rr.over.mute || null;
          props = it ? null : hubLook(chrome('mute', x, L)[1], HD.mute);
        } else if (role === 'display' && display) {
          props = openerProps(x, Object.assign({}, look, HD.display || {}), names.display, 'Opens ' + names.display + '.');
        } else if (role === 'settings' && options.length) {
          props = openerProps(x, Object.assign({}, look, HD.settings || {}), names.options,
                              'Opens ' + ((F.options || {}).text || names.options) + '.');
        } else if (role === 'power' && by.footer) {
          it = ft.over.power || null;
          props = it ? null : hubLook(chrome('power', x, L, by.footer.power)[1], HD.power);
        } else {
          return;
        }
        var kind = it ? it.kind : 'button';
        var rl = HD[role] || roleLook(role);
        var all = it ? Object.assign({}, it.props || {}, unset(it.props, rl)) : props;
        var s = { r: (x.legal || x.rect).slice(), it: it, props: all, kind: kind, role: role, touch: isTouch(kind),
                  extra: it ? Object.assign(unset(it.props, rl), { joined: set }) : null };
        if (!it) s.props = Object.assign({}, props, { joined: set });
        s.need = needOf(kind, s.props, L);
        menu.push(s);
      });
      stackMenu(menu, band, L, probs);
      menu.forEach(function (s, i) {
        els.push(s.it ? hubHost(s.it, s.at, 'menu' + i, s.extra) : drawnAt(Button, s.props, s.at, 'menu' + i));
      });
      // The level, in the Volume Level strip beside the bar: a popup of its
      // own, as the template shows it over main - its own ground (Mach's
      // opaque #4B4B4C, Shockwave's #595757, Turbulence's black at 184) and
      // its level where and as the template draws it (`level`, measured):
      // Mach's 16 px white bar on its shade track, Shockwave's and
      // Turbulence's from the kit's art, which the panel's level - a clone
      // of the seed's own - keeps. The glyphs over and under it are in icon
      // faces the system does not carry, and are not drawn.
      if (vol && C.strip) {
        var S = C.strip, SL = C.level || null, tw = Number(vol.track) || P.defaults.level.track;
        var inset = Math.round(S[3] * 0.1);
        var lv = Object.assign({}, vol, { orientation: 'up', fromSlider: true });
        delete lv.joined;
        var lr = [Math.round((S[2] - tw) / 2), inset, tw, S[3] - 2 * inset];
        if (SL && SL.rect) {
          lr = SL.rect.slice();
          lv.track = lr[2];
          lv.border = SL.border ? borderOf(SL.border) : 'none';
          if (SL.track) lv.fill = tokenClose(L.colors, SL.track) || lv.fill;
          if (SL.bar) lv.bar = tokenClose(L.colors, SL.bar) || null;
          if (SL.art) lv.art = SL.art;
        }
        parts.push({ name: names.level, group: names.level, size: [S[2], S[3]], at: [S[0], S[1]], alone: true,
                     background: SL && SL.fill ? tokenClose(L.colors, SL.fill) : null,
                     els: [drawnAt(Level, lv, lr, 'level')] });
        els.push(h('div', { key: 'level-ref', style: cell(S),
                            'data-gdl': gdl({ kind: 'popup_ref', name: 'Volume', group: names.level, derived: true }) }));
      }
    }
    // The popup region every popup of the page appears in.
    if (by.center) {
      // A Select Source page draws no popup region on the bar panels - its
      // tiles are the page's own - so here, where its grid is a popup, the
      // region is the layout's.
      els.push(drawnAt(PopupRegion, { name: by.center.name || 'Controls', group: group, __quiet: true,
                                      derived: L.region.role === 'select' || undefined }, g, 'center'));
    }
    // Select a Source: the header's tabs as the template's tiles, its title,
    // and Help where it stands it - drawn wherever main's popup region is, as
    // every source popup's and settings popup's Close goes back to it.
    var S2 = F.select || {};
    if (by.header || by.footer || by.center) {
      var sel = [];
      sel = sel.concat(hubPanels(L, S2.surfaces, names.select + ' Header', 'sh', at));
      if (S2.title) {
        sel.push(chromeLabel(L, titleLook, names.select + ' Title', S2.text || 'Select a Source',
                             [S2.title[0] - at[0], S2.title[1] - at[1], S2.title[2], S2.title[3]], 'st',
                             (S2.pt || {}).title));
      }
      sel = sel.concat(gridTiles(L, S2, tabs.map(function (it) { return { it: it, strip: true, look: Object.assign({}, HD.tile || {}) }; }),
                                 at, setName('select'), labelLook, (S2.pt || {}).label, names.select, probs));
      var help = ft.over.help || null, hdef2 = by.footer && !help ? chrome('help', S2.help || {}, L, by.footer.help) : null;
      if ((help || hdef2) && S2.help) {
        var hl = Object.assign({}, HD.help || {});
        var hr2 = [S2.help.rect[0] - at[0], S2.help.rect[1] - at[1], S2.help.rect[2], S2.help.rect[3]];
        var hprops = help ? null : Object.assign({}, hdef2[1], hl, iconHere(hl, hl.icon) ? { text: '' } : { icon: undefined });
        var hneed = needOf('button', help ? help.props || {} : hprops, L);
        var hat2 = settle(hr2, hneed, [0, 0, g[2], g[3]], [g[2], g[3]], [false, false, false, false]);
        sel.push(help ? hubHost(help, hat2, 'help', unset(help.props, hl)) : drawnAt(Button, hprops, hat2, 'help'));
      } else if (help || hdef2) {
        left.push(help ? nameOf(help) : 'Help');
        warns.push(pname + "'s Help is left off the " + L.model + ' - its template stands no Help on its grid');
      }
      parts.push({ name: names.select, group: group, size: [g[2], g[3]], at: at, els: sel, main: true });
    }
    // The options its settings opener shows.
    var O2 = F.options || {};
    if (options.length) {
      var opt = hubPanels(L, O2.surfaces, names.options + ' Header', 'oh', at);
      if (O2.title) {
        opt.push(chromeLabel(L, optTitle, names.options + ' Title', O2.text || names.options,
                             [O2.title[0] - at[0], O2.title[1] - at[1], O2.title[2], O2.title[3]], 'ot',
                             (O2.pt || {}).title));
      }
      if (O2.close) {
        opt.push(hubClose(L, F, names.options, at, O2.close.rect, names.select,
                          'Closes ' + (O2.text || names.options) + ' - back to ' + (S2.text || 'Select a Source') + '.',
                          O.close));
      }
      opt = opt.concat(gridTiles(L, O2, options, at, null, optLabel, (O2.pt || {}).label, names.options, probs));
      parts.push({ name: names.options, group: group, size: [g[2], g[3]], at: at, els: opt, background: O.background,
                   photo: !!(HD.popup || {}).photo });
    }
    // The display group's popup, as the hub's Display Control or Mach's
    // Display Settings draws it: the options popup's header and Close.
    if (display) {
      var rec = ((F.windows || {}).settings || [])[0] || {};
      var dsp = hubPanels(L, rec.surfaces, names.display + ' Header', 'dh', at);
      var dt = rec.title || O2.title;
      if (dt) {
        dsp.push(chromeLabel(L, optTitle, names.display + ' Title', displayTitle,
                             [dt[0] - at[0], dt[1] - at[1], dt[2], dt[3]], 'dt', (O2.pt || {}).title || (rec.pt || {}).title));
      }
      var back = R.display ? names.select : names.options;
      var dc = (rec.close || O2.close || {}).rect;
      if (dc) {
        dsp.push(hubClose(L, F, names.display, at, dc, back,
                          'Closes ' + displayTitle + ' - back to ' + (R.display ? S2.text || 'Select a Source' : O2.text || names.options) + '.',
                          O.close));
      }
      var box = hubHead(F, dt, dc, rec.surfaces);
      dsp = dsp.concat(sectionIn(L, display, box, names.display, optLabel, probs, O.button));
      parts.push({ name: names.display, group: group, size: [g[2], g[3]], at: at, els: dsp, background: O.background,
                   photo: !!(HD.popup || {}).photo });
    }
    // A call page's keys: the options popup's header, its Close back to the
    // grid and the Section's controls - with Share Content after them -
    // laid out as the display group's are. The program shows them first on
    // the call page, as the call mode's own page does.
    if (callSec) {
      var crec = ((F.windows || {}).settings || [])[0] || {};
      var cp = hubPanels(L, crec.surfaces, callName + ' Header', 'ch', at);
      var ct = crec.title || O2.title;
      if (ct) {
        cp.push(chromeLabel(L, optTitle, callName + ' Title', callName,
                            [ct[0] - at[0], ct[1] - at[1], ct[2], ct[3]], 'ct', (O2.pt || {}).title || (crec.pt || {}).title));
      }
      var cc = (crec.close || O2.close || {}).rect;
      if (cc) {
        cp.push(hubClose(L, F, callName, at, cc, names.select,
                         'Closes ' + callName + ' - back to ' + (S2.text || 'Select a Source') + '.', O.close));
      }
      var csp = propsOf(callSec), withShare = share ? { props: Object.assign({}, csp, {
        children: React.Children.toArray(csp.children).concat([share.host]) }) } : callSec;
      // Each key in its call look, as the call page draws it - not the
      // options grid's key, Turbulence's round rings its captions overran and
      // Shockwave's grey art, with the call's green, red and yellow lost -
      // Share Content in the header's. A cell is the options tile's width in
      // the shape the drawn panel's template gives its call keys (Shockwave's
      // 120x60 pills), so the art is not letterboxed.
      var kb = (((((frameFor(L.design) || {}).call || {}).left || {}).groups || [])[0] || {}).buttons;
      var tw = ((O2.tiles || [])[0] || {}).rect;
      var ccell = tw && kb && kb[0] ? [tw[2], Math.round(tw[2] * kb[0].rect[3] / kb[0].rect[2])] : null;
      var callLook = function (it) {
        var cr = callRoleOf(it);
        return cr ? Object.assign({}, RD.rail || {}, (RD.call || {})[cr] || {}) : slotOf(it) === 'share' ? RD.share : O.button;
      };
      cp = cp.concat(sectionIn(L, withShare, hubHead(F, ct, cc, crec.surfaces), callName, optLabel, probs, callLook,
                               { cell: ccell, title: callName }));
      // Its heading is the popup's title here (sectionIn): named, as a
      // stand-in window's is, so the ID map says where it went.
      if (csp.title) {
        left.push(csp.title + ' Heading');
        warns.push(pname + "'s " + csp.title + ' Heading is left off the ' + L.model + ' - the ' + callName
                   + " popup's title says it");
      }
      parts.push({ name: callName, group: group, size: [g[2], g[3]], at: at, els: cp, background: O.background,
                   photo: !!(HD.popup || {}).photo, first: true });
    }
    // The program shows the grid first - a call page its keys - then its
    // group's others.
    function order(q) { return q.first ? -1 : q.name === names.select ? 0 : q.group === group ? 1 : 2; }
    parts.sort(function (a, b) { return order(a) - order(b); });
    els.push(h(HubParts, { key: 'hub-parts', parts: parts, shown: shown, L: L }));
    return { els: els, probs: probs, warns: warns, left: left };
  }

  // -- The 320: a page per source --------------------------------------------
  // (docs/superpowers/specs/2026-10-22-region-frame-design.md, PR7.) The 320
  // draws no bar, rail or footer: every page under a 36 px title strip, each
  // source a page of its own - its controls in the template's columns, under
  // their headings, or its three-line empty state - going on over a second
  // page joined by More (the foot's right) and Back (the strip's end on
  // Mach's, the foot's right on Shockwave's and Turbulence's); the question
  // and the waits pages on the template's rounded box; the volume a modal the
  // program shows, a level at the screen's right edge. So the same region
  // page derives to it there, from the 320's own frame (P.frames, `pages`),
  // and nothing on it is dropped: Main is the template's Select a Source,
  // its strip titled as the template's, holding the Header's tabs under it as
  // the 320's keys - the same controls, so the same IDs - and going on by More
  // to pages of Main's own with what the template keeps off its pages (the
  // LeftRail's Sections, the volume's heading and Mute, Room Mode, Help and
  // Power), each Section a column under its heading; the slider is the
  // level in the Volume modal; what has no place at all - the clock, the
  // Center's popup region - is named and listed in the page's `left`. A
  // source popup, a settings window and Help are pages under the strip; a
  // window's Close is Back. The template has no way back from a source on
  // screen - it chooses sources off it - so a page's first Back stands where
  // its second page's stands, and goes back to the page that shows it, which
  // the translator finds (`back`): only the canvas as a whole knows it. What
  // the layout adds is derived, and keeps the template's seed ID where the
  // frame has one (More 8010, Back 8011, the title strips', the question's).
  var PD = RD.page || {};
  function pagesFor(T) {
    var F = FRAMES[T.series];
    return F && F.pages && !T.turned ? F : null;
  }
  function roleIn(rec, role) {
    var out = null;
    ['top', 'bottom', 'left', 'right', 'center'].forEach(function (b) {
      ((rec && rec[b] || {}).items || []).forEach(function (x) { if (!out && x.role === role) out = x; });
    });
    return out;
  }
  // Where a page's More and Back stand: More where the template's first
  // page stands it; Back where its second page does - and where More stands
  // there too (Shockwave's and Turbulence's foot's right), at the strip's
  // end, as Mach's template stands it, a square the strip's depth: at the
  // foot's left, as far in, it took the third key of the first column, and
  // a column of three went on over two.
  function navPlaces(L, F, more, back) {
    var M = roleIn(F, 'more'), B = roleIn(F.second, 'back'), W = L.panel.size[0];
    var out = { more: more && M ? M : null, back: null, strip: false };
    if (back && B) {
      var r = B.rect.slice(), sh = F.top.rect[3];
      out.strip = r[1] + r[3] <= F.center.rect[1] + 1;
      if (!out.strip && out.more && overlaps(r, out.more.rect)) {
        r = [W - sh, 0, sh, sh];
        out.strip = true;
      }
      out.back = { rect: r, id: B.id };
    }
    return out;
  }
  // The strip across a page's top: the record's surfaces as derived Panels
  // (the 320's black label ground; on a page with Back at the strip's end,
  // Mach's shape short of it), its title over them at the template's size.
  // Where Back ends it (`back`, its rect there), the strip and its title are
  // as deep as Back: the touch minimum took Mach's 57x36 Back to 40, and it
  // hung 4 px under the 36 px strip. Its title stays clear of Back: centred
  // on the strip where it fits the span Back leaves either side of the
  // middle, else centred on what Back leaves of the strip; `title` is the
  // words, or the words to try in turn (Main's later pages: their Sections'
  // titles joined, then the first's), and words that fit neither way are
  // named in `probs` - the label drawn the full 320 across ran 'Display and
  // Room Settings' under Back unremarked.
  function stripEls(L, F, rec, name, title, id, back, probs) {
    var els = [], gap = L.panel.gap;
    var deep = back && back[1] === 0 ? back[3] : 0;
    function taller(r) { return deep > r[3] && r[1] === 0 ? [r[0], r[1], r[2], deep] : r; }
    (rec.top.surfaces || []).forEach(function (s, i) {
      els.push(drawnAt(Panel, { name: name + ' Strip' + (i ? ' ' + (i + 1) : ''),
                                fill: tokenClose(L.colors, s.fill) || 'none', border: borderOf(s.border),
                                stroke: 'none', derived: true }, taller(s.rect), 'strip' + i));
    });
    var t = roleIn(rec, 'title') || roleIn(rec, 'heading');
    var p = Object.assign({}, PD.strip || {}, id != null ? { id: id } : {});
    var pt = (F.center.pt || {}).title, r = taller(t ? t.rect : rec.top.rect), tries = [].concat(title);
    var words_ = tries[0], at = r;
    if (deep && overlaps(back, r)) {
      var f = font(Object.assign({}, p, pt != null ? { size: pt } : {}), P.defaults.label.type,
                   Object.assign({}, L, { k: pt != null ? 1 : L.k }));
      // Measured 6% wide, as messageBox does: before the canvas's Open Sans
      // loads it measures Arial, 5% narrower.
      var wide = function (s) { return textWidth(s, f.css) * 1.06; };
      var right = back[0] + back[2] / 2 >= r[0] + r[2] / 2, mid = r[0] + r[2] / 2;
      var span = right ? 2 * (back[0] - mid) : 2 * (mid - back[0] - back[2]);
      var lean = right ? [r[0], r[1], back[0] - r[0], r[3]] : [back[0] + back[2], r[1], r[0] + r[2] - back[0] - back[2], r[3]];
      var got = null;
      tries.forEach(function (s) {
        if (got) return;
        if (wide(s) <= span) got = { s: s, r: r };
        else if (wide(s) <= lean[2] - 2 * gap) got = { s: s, r: lean };
      });
      if (got) { words_ = got.s; at = got.r; }
      else {
        at = lean;
        if (probs) {
          probs.push(name + "'s title '" + words_ + "' runs under its Back on the " + L.model + ' - its strip holds '
                     + Math.floor(lean[2] - 2 * gap) + ' px beside Back: shorten it');
        }
      }
    }
    els.push(chromeLabel(L, p, name + ' Title', words_, at, 'title', pt));
    return els;
  }
  function navButton(L, look, name, r, id, extra, key) {
    var p = Object.assign({ name: name, derived: true }, look || {}, id != null ? { id: id } : {}, extra || {});
    var at = settle(r, needOf('button', p, L), [0, 0, L.panel.size[0], L.panel.size[1]], L.panel.size,
                    [false, false, false, false]);
    return drawnAt(Button, p, at, key);
  }
  // A control the 320's page draws in its own look: a designer's in the
  // page's key look unless they set their own - the icon a header tab draws
  // its header's own, not a key's - and a region default (Mute, Help, Power)
  // in the key look with its own words, keeping its icon where the key's kit
  // draws it, its states by name.
  function pageMember(it, props, kind, tab) {
    var look = Object.assign({}, PD.button || {});
    if (it) {
      var p = it.props || {}, extra = kind === 'button' ? unset(p, look) : {};
      if (tab) {
        ['size', 'align', 'fill', 'border', 'stroke', '__indent', 'icon', 'variant'].forEach(function (k) {
          if (p[k] != null && look[k] == null) extra[k] = undefined;
        });
        if (look.variant) extra.variant = look.variant;
      }
      if (kind === 'label') extra = unset(p, PD.heading);
      // `auto`: in the page's key look, which a wider caption widens (paginate).
      return { it: it, kind: kind, props: Object.assign({}, p, extra), extra: extra,
               auto: kind === 'button' && (tab || p.variant == null) };
    }
    var q = Object.assign({}, props);
    if (kind === 'button') {
      var keep = q.icon && iconHere(Object.assign({}, q, look), q.icon);
      q = Object.assign(q, look, { icon: keep || undefined });
      if (!keep && !q.text) q.text = q.name === 'Volume Mute' ? 'Mute' : q.name;
      if (q.states) q.states = list(q.states).map(function (s) { return { name: s.name }; });
    }
    return { it: null, kind: kind, props: q, extra: null, auto: kind === 'button' };
  }
  // A slider where the panel's seed has none to clone (the 320's: its
  // profile's `kinds`): a level there, with the derived Up and Down every
  // level a slider becomes has (asLevel), a column of its own (`level`).
  // Drawn as the designer's slider in one key's cell, it was a 50 px slider
  // the 320's seed could not build, refused only at the donor check.
  function asLevelHere(it, L) {
    return it.kind === 'slider' && (L.panel.kinds || {}).slider === false;
  }
  // A Group on a 320's page: its members the page's own, in its columns -
  // a tier C Group's opener has no place among a page's keys, and laid out
  // in one key's cell its six buttons ran off the screen unremarked. A
  // Group in a Group, or what is not a component, cannot page so, and is
  // named.
  function groupMembers(it, where, probs) {
    var out = [];
    itemsOf(propsOf(it).children).forEach(function (c) {
      if (c.kind === 'group' || !c.comp) {
        probs.push(nameOf(c) + ' in ' + nameOf(it) + ' in ' + where + ' cannot page on a 320 - put its controls in '
                   + nameOf(it) + ' directly');
        return;
      }
      out.push(c);
    });
    return out;
  }
  // A designer's controls in a source popup or a window as the 320's
  // columns: what stands one over another, by where it was drawn, a label
  // at a column's top its heading; a Group a column of its own under its
  // title, and a slider the panel cannot build one of its own, a level.
  // Unplaced children are drawn as they are; a plain container cannot
  // reflow, and a card has no place on a page.
  function columnsOf(kids, where, probs, warns, left, L) {
    var cols = [], loose = [];
    kids.forEach(function (it) {
      if (!it.rect || REGION_NAMES[it.kind] || it.kind === 'mainarea' || it.kind === 'rail') { loose.push(it); return; }
      if (it.kind === 'box') {
        probs.push('a plain container in ' + where + ' cannot reflow on a 320 - put its controls in ' + where
                   + ' directly, or in a Group');
        return;
      }
      if (it.kind === 'panel' || it.kind === 'line') {
        var n = nameOf(it);
        if ((it.props || {}).name) left.push(n);
        warns.push(where + "'s " + n + ' is left off the 320 - its pages draw no cards or lines');
        return;
      }
      var r = it.rect, c = null;
      // A Group and a level stand in columns of their own.
      if (it.kind === 'group' || asLevelHere(it, L)) {
        cols.push({ lo: r[0], hi: r[0] + r[2], items: [it], own: true });
        return;
      }
      cols.forEach(function (x) { if (!c && !x.own && r[0] < x.hi && x.lo < r[0] + r[2]) c = x; });
      if (c) { c.items.push(it); c.lo = Math.min(c.lo, r[0]); c.hi = Math.max(c.hi, r[0] + r[2]); }
      else cols.push({ lo: r[0], hi: r[0] + r[2], items: [it] });
    });
    // Columns that came to overlap as they grew are one.
    for (var i = 0; i < cols.length; i++) {
      for (var j = i + 1; j < cols.length; j++) {
        if (cols[i].own || cols[j].own) continue;
        if (cols[j].lo < cols[i].hi && cols[i].lo < cols[j].hi) {
          cols[i].items = cols[i].items.concat(cols[j].items);
          cols[i].lo = Math.min(cols[i].lo, cols[j].lo); cols[i].hi = Math.max(cols[i].hi, cols[j].hi);
          cols.splice(j, 1); j = i;
        }
      }
    }
    cols.sort(function (a, b) { return a.lo - b.lo; });
    var blocks = cols.map(function (c) {
      var g = c.items[0];
      if (c.own && g.kind === 'group') {
        // Its title a heading the 320 adds (no other panel draws one), in
        // capitals where the template sets its 320's column labels so (ZOOM,
        // INPUTS: the profile's writing.column_labels_320). The control keeps
        // the designer's name; its caption is what the panel shows.
        var gt = propsOf(g).title || propsOf(g).name || null;
        var shown = gt && WD.column_labels_320 === 'caps' ? gt.toUpperCase() : gt;
        return { head: gt ? pageMember(null, Object.assign({ name: gt + ' Heading', text: shown, derived: true }, RD.heading || {},
                                                           PD.heading || {}), 'label') : null,
                 title: gt, members: groupMembers(g, where, probs).map(function (it) {
                   return pageMember(it, null, it.kind);
                 }) };
      }
      if (c.own) return { head: null, title: null, level: true, members: [pageMember(g, null, 'slider')] };
      var items = c.items.sort(function (a, b) { return a.rect[1] - b.rect[1] || a.rect[0] - b.rect[0]; });
      var head = items.length > 1 && items[0].kind === 'label' ? items.shift() : null;
      return { head: head ? pageMember(head, null, 'label') : null,
               title: head ? textOf((head.props || {}).children, (head.props || {}).text) : null,
               members: items.map(function (it) { return pageMember(it, null, it.kind); }) };
    });
    return { blocks: blocks, loose: loose };
  }
  // The template's grid on a page: its slots across - its first row's, on at
  // its step - and its rows down from the first, under the headings where
  // the page draws them, as many as its column holds, each as deep as the
  // template's and no less than what is in it needs.
  function pageGrid(L, F, heads, needH, headNeed) {
    var C = F.center, row = C.row, T = L.panel, H = T.size[1];
    var rowH = row[0][3], py = (C.pitch || [])[1] || rowH + T.gap, seam = Math.max(1, py - rowH);
    var n = 0;
    while (row[0][1] + n * py + rowH <= H) n += 1;
    n = Math.max(1, n);
    // A heading starts under the strip (Turbulence's boxes reach 7 px up
    // into it) and ends where the template's does, or as deep as its words,
    // its keys under it. The template's own 12 pt heading reaches 14 px into
    // Turbulence's keys' clear tops, but at the 320's 14 pt floor its words
    // fill its box, and reaching as far ran them into the keys' touch areas
    // (the translator's words check): Turbulence's rows stay 57 deep to the
    // template's 65 (docs/ROADMAP.md).
    var hd = (C.headings || [])[0] || null, top = row[0][1], ht = hd ? Math.max(hd[1], C.rect[1]) : 0;
    var head = hd ? [hd[0], ht, hd[2], Math.max(hd[1] + hd[3] - ht, Math.ceil(headNeed))] : null;
    if (heads && head) top = Math.max(top, head[1] + head[3] + 1);
    var hgt = Math.max(Math.ceil(needH), T.touch, Math.min(rowH, Math.floor((H - 1 - top - (n - 1) * seam) / n)));
    return { xs: row.map(function (r) { return r[0] + r[2] / 2; }), w: row[0][2], top: top, h: hgt, seam: seam,
             rows: n, head: head, H: H, W: T.size[0] };
  }
  // `blocks` over as many pages as they need: each a column of its own
  // (`grid`: one block row by row across the slots), a heading over its
  // first, the rest of a long one on in the next slot; More on every page
  // but the last (`tail`: the last's too, on to pages after these), Back on
  // every page but the first (`back`: the first's too).
  // Each page: its slots' places and members, and its More and Back.
  function paginate(L, F, blocks, grid, back, tail) {
    var T = L.panel, gap = T.gap, needH = 0, headNeed = 0, heads = false;
    blocks.forEach(function (b) {
      b.w = 0;
      b.members.forEach(function (m) {
        m.need = needOf(m.kind, m.props, L);
        if (m.kind !== 'label') needH = Math.max(needH, m.need[1]);
        b.w = Math.max(b.w, m.need[0]);
      });
      if (b.head) { heads = true; b.head.need = needOf('label', b.head.props, L); headNeed = Math.max(headNeed, b.head.need[1]); }
    });
    var G = pageGrid(L, F, heads, needH, headNeed);
    // A column of keys whose art is narrower at the row's depth than a
    // caption needs takes the theme's next wider art (`regions.page.wider`),
    // the whole column one art, as wide as that art is at the row's depth
    // while two columns still stand a gap apart: Shockwave's 504x440 tile is
    // 65 px wide at its 57, and 'Lighting' and 'Streaming' ran off it. Only
    // an art that, that wide, is still the touch minimum deep and holds the
    // caption: Turbulence's 720x180 bar came out 94x23, its caption over its
    // edges. With none (Turbulence's: it has no wider key), the key keeps
    // its own art at the row's depth, and a caption of two words or more
    // goes on two lines where that holds it on the art ('Doc' over 'Cam'),
    // as the theme's own two-word keys do (captionOf); one that still does
    // not fit runs past the art's sides, its cell as wide as it is - grown
    // in the art's own shape, 'Streaming' took Turbulence's keys to 100 px
    // and Main's four sources over two pages.
    function aspect(v) {
      var k = (P.buttons[v] || {}).kit, d = k ? String(k).split('x').map(Number) : null;
      return d && d[1] ? d[0] / d[1] : 0;
    }
    var pitchX = G.xs.length > 1 ? G.xs[1] - G.xs[0] : G.W;
    blocks.forEach(function (b) {
      var auto = b.members.filter(function (m) { return m.auto; });
      var a0 = auto.length ? aspect(auto[0].props.variant || P.defaults.button.variant) : 0;
      if (!a0) return;
      var want = Math.max.apply(null, auto.map(function (m) { return m.need[0]; }));
      if (G.h * a0 >= want) return;
      function across(v) { return Math.min(Math.floor(G.h * aspect(v)), pitchX - gap); }
      // The art as drawn - to fit its cell, as wide as the caption or the
      // art at the row's depth, to the column's step: [width, depth].
      function drawn(v) {
        var w = Math.max(want, across(v));
        return [Math.min(w, G.h * aspect(v)), Math.min(G.h, w / aspect(v))];
      }
      var pick = null;
      (PD.wider || []).forEach(function (v) {
        if (!pick && drawn(v)[0] >= want && drawn(v)[1] >= T.touch) pick = v;
      });
      if (!pick) {
        var artW = Math.floor(G.h * a0);
        auto.forEach(function (m) {
          var c = textOf(m.props.children, m.props.text);
          if (m.need[0] <= artW || !c || c.indexOf(' ') < 0 || /\n/.test(c)) return;
          var at = -1;
          for (var i = 0; i < c.length; i++) {
            if (c.charAt(i) === ' ' && (at < 0 || Math.abs(i - c.length / 2) < Math.abs(at - c.length / 2))) at = i;
          }
          var two = c.slice(0, at) + '\n' + c.slice(at + 1);
          var q = Object.assign({}, m.props, { children: two, text: two });
          var n2 = needOf(m.kind, q, L), f = font(q, P.defaults.button.type, L);
          if (n2[0] <= artW && 2 * lineHeight(f.size) + 4 <= G.h) { m.caption = two; m.need = n2; }
        });
        b.w = Math.max.apply(null, b.members.map(function (m) { return m.need[0]; }));
        return;
      }
      auto.forEach(function (m) {
        var q = Object.assign({}, m.props, { variant: pick });
        if (q.icon && !iconHere(q, q.icon)) return;
        m.props = q;
        if (m.extra) m.extra.variant = pick;
        m.need = needOf(m.kind, m.props, L);
      });
      b.w = Math.max.apply(null, b.members.map(function (m) { return m.need[0]; }).concat([across(pick)]));
    });
    var queue = [];
    blocks.forEach(function (b, bi) { b.members.forEach(function (m, mi) { queue.push({ b: bi, m: mi }); }); });
    // More and Back, which a key keeps the panel's 2 mm from where the two
    // stand side by side (gdl.spec's rule; diagonal neighbours are clear).
    function keepOut(nav) {
      return [nav.more && nav.more.rect, nav.back && !nav.strip && nav.back.rect].filter(Boolean);
    }
    function near(r, o) {
      var gx = Math.max(o[0] - (r[0] + r[2]), r[0] - (o[0] + o[2])), gy = Math.max(o[1] - (r[1] + r[3]), r[1] - (o[1] + o[3]));
      return gx < 0 && gy < gap || gy < 0 && gx < gap;
    }
    function clear(r, outs) { return r[1] + r[3] <= G.H - 1 && !outs.some(function (o) { return near(r, o); }); }
    // One page from the head of `q`: its slots and what each holds.
    function pack(q, nav) {
      var outs = keepOut(nav), slots = [], k = 0;
      function wOf(bi) { return Math.max(G.w, Math.ceil(blocks[bi].w)); }
      if (grid) {
        for (var j = 0; j < G.rows && k < q.length; j++) {
          for (var i = 0; i < G.xs.length && k < q.length; i++) {
            var w = wOf(q[k].b), y = G.top + j * (G.h + G.seam);
            var r = [Math.round(G.xs[i] - w / 2), y, w, G.h];
            if (!clear(r, outs)) continue;
            slots[i] = slots[i] || { i: i, w: w, cells: [] };
            slots[i].cells.push({ c: q[k], r: r });
            k += 1;
          }
        }
      } else {
        var minX = gap;
        for (var si = 0; si < G.xs.length && k < q.length; si++) {
          var bi = q[k].b, w2 = wOf(bi), s = { i: si, w: w2, b: bi, cells: [], head: q[k].m === 0 && blocks[bi].head };
          // At its slot - or, where More or Back stands in the way, moved
          // left clear of it, while that holds more of the column.
          var rows = function (x) {
            var n = 0;
            for (var j = 0; j < G.rows; j++) if (clear([x, G.top + j * (G.h + G.seam), w2, G.h], outs)) n += 1;
            return n;
          };
          // A level stands the column's depth, the touch minimum across,
          // clear of More and Back (asLevel's Up and Down at its ends).
          if (blocks[bi].level) {
            w2 = T.touch;
            var lx = Math.max(minX, Math.round(G.xs[si] - w2 / 2)), bot = G.H - 1;
            outs.forEach(function (o) { if (o[0] - gap < lx + w2 && lx < o[0] + o[2] + gap) bot = Math.min(bot, o[1] - gap); });
            if (bot - G.top >= 2 * T.touch + 2 * gap + 24) {
              s.w = w2;
              s.cells.push({ c: q[k], r: [lx, G.top, w2, bot - G.top] });
              k += 1;
              slots.push(s);
              minX = lx + w2 + gap;
            }
            continue;
          }
          var x0 = Math.max(minX, Math.round(G.xs[si] - w2 / 2)), x1 = x0;
          outs.forEach(function (o) { if (o[0] - gap < x0 + w2 && x0 < o[0] + o[2]) x1 = Math.min(x1, o[0] - gap - w2); });
          // As far as the columns before it can give way, to the screen's gap.
          var lead = slots.length ? Math.min.apply(null, slots.map(function (t) {
            return Math.min.apply(null, t.cells.map(function (c) { return c.r[0]; }));
          })) - gap : 0;
          var give = Math.max(0, minX - x1);
          var x = x0;
          if (x1 < x0 && give <= lead && rows(x1) > rows(x0)) {
            slots.forEach(function (t) { t.cells.forEach(function (c) { c.r[0] -= give; }); });
            x = x1;
          }
          for (var j2 = 0; j2 < G.rows && k < q.length && q[k].b === bi; j2++) {
            var r2 = [x, G.top + j2 * (G.h + G.seam), w2, G.h];
            if (!clear(r2, outs)) continue;
            s.cells.push({ c: q[k], r: r2 });
            k += 1;
          }
          if (s.cells.length) { slots.push(s); minX = x + w2 + gap; }
        }
      }
      return { slots: slots.filter(Boolean), used: k, outs: outs };
    }
    var pages = [], probs = [];
    while (queue.length || !pages.length) {
      var p = pages.length, hasBack = p > 0 || !!back;
      var navA = navPlaces(L, F, !!tail, hasBack), got = pack(queue, navA);
      if (got.used < queue.length && !tail) {
        navA = navPlaces(L, F, true, hasBack);
        got = pack(queue, navA);
      }
      if (!got.used && queue.length) {
        probs.push('what ' + (pages.length ? 'is left' : 'it holds') + ' needs more room than a page of the '
                   + L.model + ' has');
        break;
      }
      got.nav = navA;
      got.cells = queue.slice(0, got.used);
      queue = queue.slice(got.used);
      pages.push(got);
    }
    // Across: fewer columns than the template's centre as a group, where that
    // keeps them clear of More and Back; columns grown wide stand a gap apart
    // and inside the screen.
    pages.forEach(function (pg) {
      var S = pg.slots.slice().sort(function (a, b) { return a.i - b.i; });
      if (S.length && S.length < G.xs.length) {
        var lo = Math.min.apply(null, S.map(function (s) { return G.xs[s.i] - s.w / 2; }));
        var hi = Math.max.apply(null, S.map(function (s) { return G.xs[s.i] + s.w / 2; }));
        var dx = Math.round(G.W / 2 - (lo + hi) / 2);
        var ok = S.every(function (s) {
          return s.cells.every(function (c) { return clear([c.r[0] + dx, c.r[1], c.r[2], c.r[3]], pg.outs); });
        });
        if (ok) S.forEach(function (s) { s.cells.forEach(function (c) { c.r[0] += dx; }); s.dx = dx; });
      }
      var right = -Infinity;
      S.forEach(function (s) {
        var x0 = Math.min.apply(null, s.cells.map(function (c) { return c.r[0]; }));
        var shift = Math.max(0, right + gap - x0);
        if (shift) s.cells.forEach(function (c) { c.r[0] += shift; });
        s.dx = (s.dx || 0) + shift;
        right = Math.max.apply(null, s.cells.map(function (c) { return c.r[0] + c.r[2]; }));
      });
      if (right > G.W) probs.push('its columns need more than the ' + G.W + ' px across a ' + L.model + ' has');
    });
    return { pages: pages, G: G, probs: probs };
  }
  // A page's Back where it stands: at the strip's end, as deep as the strip
  // and in the look the strip's end takes (`strip_back`: Turbulence's kit
  // return key - its Back key has the word in its art, 5 px tall at 40).
  function backAt(L, nav) {
    var look = nav.strip ? PD.strip_back || PD.back : PD.back;
    return { look: look, rect: settle(nav.back.rect, needOf('button', Object.assign({}, look || {}), L),
                                      [0, 0, L.panel.size[0], L.panel.size[1]], L.panel.size,
                                      [false, false, false, false]) };
  }
  // A 320 page of words alone (pagePart's `prose`): set as the template sets
  // Help's message - across the page under the strip, clear of More and
  // Back - each Label as deep as its words wrap to at this panel's type, one
  // under another, a half gap apart; going on over a second page by More and
  // Back, as the template's own pages go on, where they do not all fit. A
  // Label too long for a page of its own is named: a Label is one control,
  // and does not break across pages.
  function prosePages(L, F, prose, name, title, back0, probs) {
    var gap = L.panel.gap, W = L.panel.size[0], w = W - 2 * gap, top = F.center.rect[1] + gap, step = Math.round(gap / 2);
    var items = prose.slice().sort(function (a, b) { return a.rect[1] - b.rect[1] || a.rect[0] - b.rect[0]; })
      .map(function (it) {
        var p = propsOf(it), f = font(p, P.defaults.label.type, L);
        return { it: it, h: wrapWords(textOf(p.children, p.text), f.css, w / 1.06).length * lineHeight(f.size) + 2 };
      });
    function footOf(nav) {
      var f = L.panel.size[1];
      if (nav.more) f = Math.min(f, nav.more.rect[1]);
      if (nav.back && !nav.strip) f = Math.min(f, nav.back.rect[1]);
      return f - gap;
    }
    function fill(i, nav) {
      var y = top, n = 0;
      while (i + n < items.length && y + items[i + n].h <= footOf(nav)) { y += items[i + n].h + step; n += 1; }
      return n;
    }
    var pages = [], i = 0;
    while (i < items.length) {
      var nav = navPlaces(L, F, false, true), n = fill(i, nav);
      if (i + n < items.length) {
        nav = navPlaces(L, F, true, true);
        n = Math.max(1, fill(i, nav));
      }
      var room = footOf(nav) - top;
      items.slice(i, i + n).forEach(function (x) {
        if (x.h > room) {
          probs.push(name + "'s " + nameOf(x.it) + ' needs ' + x.h + ' px of the ' + room + ' the ' + L.model
                     + ' has under its strip, set at its ' + L.panel.floor + ' pt floor - say less');
        }
      });
      pages.push({ nav: nav, items: items.slice(i, i + n) });
      i += n;
    }
    var shown = { set: null };
    function partName(p) { return p ? name + ' ' + (p + 1) : name; }
    function shower(p) { return function () { if (shown.set) shown.set(p); }; }
    var homeT = roleIn(F, 'heading') || roleIn(F, 'title'), secondT = roleIn(F.second, 'title');
    var drawn = pages.map(function (pg, p) {
      var nav = pg.nav, bk = backAt(L, nav);
      var rec = nav.strip ? F.second : F;
      var els = stripEls(L, F, rec, partName(p), title, p === 0 ? (homeT || {}).id : (secondT || {}).id,
                         nav.strip ? bk.rect : null, probs);
      var y = top;
      pg.items.forEach(function (x, j) {
        els.push(hostAt(x.it, [gap, y, w, x.h], 'prose' + p + '-' + j));
        y += x.h + step;
      });
      if (nav.more) {
        els.push(navButton(L, PD.more, partName(p) + ' More', nav.more.rect, nav.more.id,
                           { nav: partName(p + 1), does: 'Shows ' + partName(p + 1) + '.', onPress: shower(p + 1) },
                           'more' + p));
      }
      var bx = p ? { nav: partName(p - 1), does: 'Goes back to ' + partName(p - 1) + '.', onPress: shower(p - 1) }
                 : back0;
      els.push(navButton(L, bk.look, partName(p) + ' Back', bk.rect, nav.back.id, bx, 'back' + p));
      return { name: partName(p), els: els };
    });
    var els = drawn[0].els;
    if (drawn.length > 1) els = els.concat([h(PageParts, { key: 'pages', parts: drawn.slice(1), shown: shown })]);
    return els;
  }
  // What `paginate` placed, drawn: each page's strip, headings, members,
  // More and Back. `title(p)` the strip's words on page p (or the words to
  // try in turn, stripEls), `back0` the first page's Back (null for none),
  // `ids` the strip's seed IDs; what does not fit is named in `probs`. Its
  // later pages go over it as pages of their own (PageParts).
  function drawPages(L, F, blocks, laid, name, title, back0, firstRec, probs) {
    var G = laid.G, shown = { set: null }, gap = L.panel.gap;
    function partName(p) { return p ? name + ' ' + (p + 1) : name; }
    function shower(p) { return function () { if (shown.set) shown.set(p); }; }
    var homeT = roleIn(firstRec, 'heading') || roleIn(firstRec, 'title'), secondT = roleIn(F.second, 'title');
    var pages = laid.pages.map(function (pg, p) {
      var els = [], nav = pg.nav;
      var rec = nav.back && nav.strip ? F.second : p === 0 ? firstRec : F;
      var tid = p === 0 ? (homeT || {}).id : (secondT || {}).id;
      var bk = nav.back && (p || back0) ? backAt(L, nav) : null;
      els = els.concat(stripEls(L, F, rec, partName(p), title(p, pg), tid, bk && nav.strip ? bk.rect : null, probs));
      pg.slots.forEach(function (s, si) {
        var b = blocks[s.b != null ? s.b : s.cells[0].c.b];
        if (s.head && b.head && G.head) {
          var cx = s.cells.length ? s.cells[0].r[0] + s.cells[0].r[2] / 2 : G.xs[s.i] + (s.dx || 0);
          var hw = Math.max(G.head[2], s.w), hr = [Math.round(cx - hw / 2), G.head[1], hw, G.head[3]];
          var hp = b.head.props;
          els.push(b.head.it ? hubHost(b.head.it, hr, 'h' + p + '-' + si, b.head.extra)
                             : drawnAt(Label, hp, hr, 'h' + p + '-' + si));
        }
        s.cells.forEach(function (c, ci) {
          var m = blocks[c.c.b].members[c.c.m], key = 'm' + p + '-' + si + '-' + ci;
          var set = m.kind === 'button' ? setName('page', c.c.b) : null;
          if (blocks[c.c.b].level) {
            var lvl = asLevel(m.it, c.r, 'column', L.panel, key, null, null, (PD.button || {}).variant);
            els = els.concat(lvl.els);
            if (probs) lvl.problems.forEach(function (q) { probs.push(q); });
          } else if (m.it) {
            // `caption`: its words on two lines (paginate).
            var extra = Object.assign({}, m.extra || {}, set ? { joined: set } : {});
            els.push(m.caption != null ? hubHost(m.it, c.r, key, extra, m.caption) : hubHost(m.it, c.r, key, extra));
          } else {
            els.push(drawnAt(m.kind === 'label' ? Label : Button,
                             Object.assign({}, m.props, set ? { joined: set } : {}, m.caption != null ? { text: m.caption } : {}),
                             c.r, key));
          }
        });
      });
      if (nav.more) {
        els.push(navButton(L, PD.more, partName(p) + ' More', nav.more.rect, nav.more.id,
                           { nav: partName(p + 1), does: 'Shows ' + partName(p + 1) + '.', onPress: shower(p + 1) },
                           'more' + p));
      }
      if (bk) {
        var bx = p ? { nav: partName(p - 1), does: 'Goes back to ' + partName(p - 1) + '.', onPress: shower(p - 1) }
                   : back0;
        els.push(navButton(L, bk.look, partName(p) + ' Back', bk.rect, nav.back.id, bx, 'back' + p));
      }
      return { name: partName(p), els: els };
    });
    var els = pages[0].els;
    if (pages.length > 1) els = els.concat([h(PageParts, { key: 'pages', parts: pages.slice(1), shown: shown })]);
    return els;
  }
  // The pages a 320's page goes on over, and the Volume modal, each over it
  // as a page or a modal of its own: a later page in the page's own look, the
  // program's modal only when asked for (`window.__GDL_SHOW`).
  function PageParts(props) {
    var L = React.useContext(Ctx);
    var st = React.useState(0);
    props.shown.set = st[1];
    var forced = typeof window !== 'undefined' && window.__GDL_SHOW ? String(window.__GDL_SHOW) : null;
    return props.parts.map(function (q, j) {
      var look = q.modal ? { kind: 'popup', name: q.name, modal: true, reached_by: 'program', size: L.panel.size }
        : Object.assign({ kind: 'page', name: q.name, host: L.pageName || 'Page', size: L.panel.size }, L.pageLook || {});
      var on = q.modal ? forced === q.name : forced ? forced === q.name : st[0] === j + 1;
      return h(Ctx.Provider, { key: 'pp' + j, value: Object.assign({}, L, { pageName: q.name,
                                                                          within: q.modal ? 'modal' : 'page' }) },
        h('div', { 'data-gdl-part': JSON.stringify(look),
                   style: Object.assign({ position: 'fixed', left: 0, top: 0, width: L.panel.size[0] + 'px',
                                          height: L.panel.size[1] + 'px', zIndex: 5, visibility: on ? 'visible' : 'hidden' },
                                        q.modal ? { background: paint(L.colors, 'scrim') } : L.pageStyle || {}) }, q.els));
    });
  }
  // The region page on the 320 (see above): Main, the pages it goes on over
  // and the Volume modal - `els` - with what it named (`probs`, `warns`) and
  // what it has no place for (`left`).
  function planPages(regs, L, pname) {
    var F = L.region.F, probs = [], warns = [], left = [], by = {};
    regs.forEach(function (it) { if (!by[it.kind]) by[it.kind] = propsOf(it); });
    // What the drawn panel's own regions draw by default, by role.
    var FD = frameFor(L.design), RR = byRole(FD ? FD.right.items : []), RB = byRole(FD ? FD.bottom.items : []);
    function drawn(role, band) { return !FD || !!band[role]; }
    var tabs = [], ends = [];
    if (by.header) {
      itemsOf(by.header.children).forEach(function (it) { (slotOf(it) === 'source' ? tabs : ends).push(it); });
    }
    var rr = by.rightrail ? slotted(by.rightrail.children, ['heading', 'volume', 'mute', 'audio'], 'RightRail', 'right', L)
      : { over: {}, probs: [] };
    var ft = by.footer ? slotted(by.footer.children, ['mode', 'clock', 'help', 'power'], 'Footer', 'bottom', L)
      : { over: {}, probs: [] };
    probs = probs.concat(rr.probs, ft.probs);
    var blocks = [];
    // The LeftRail's Sections: a column each, under its heading where the
    // drawn panel's rail draws one (Shockwave's and Turbulence's second
    // group has none).
    if (by.leftrail) {
      var FDL = FD ? FD.left : null, secs = [];
      itemsOf(by.leftrail.children).forEach(function (sec) {
        if (sec.kind !== 'section') {
          probs.push(nameOf(sec) + ' in the LeftRail is not in a Section - put the rail\'s controls in titled Sections');
          return;
        }
        // The Section's place among the rail's (a level a Section holds is a
        // block of its own, so not blocks.length).
        var sp = propsOf(sec), gi = secs.length, G = FDL && FDL.groups ? FDL.groups[gi] : null;
        secs.push(sec);
        var head = sp.title && (!FDL || G && G.heading)
          ? pageMember(null, Object.assign({ name: sp.title + ' Heading', text: sp.title }, RD.heading || {}, PD.heading || {}), 'label')
          : null;
        var mem = [], lv = [];
        itemsOf(sp.children).forEach(function (it) {
          (it.kind === 'group' ? groupMembers(it, sp.title || 'the LeftRail', probs) : [it]).forEach(function (x) {
            if (asLevelHere(x, L)) lv.push({ head: null, title: null, level: true, members: [pageMember(x, null, 'slider')] });
            else mem.push(pageMember(x, null, x.kind));
          });
        });
        blocks.push({ head: head, title: sp.title || null, members: mem });
        blocks = blocks.concat(lv);
      });
    }
    // The volume: its heading over Mute (and an Audio Control), its level
    // the Volume modal's.
    var vol = null;
    if (by.rightrail) {
      var hd = rr.over.heading, hdef = !hd && RR.heading ? chrome('heading', RR.heading, L) : null;
      var vm = [];
      if (rr.over.mute) vm.push(pageMember(rr.over.mute, null, rr.over.mute.kind));
      else if (drawn('mute', RR)) vm.push(pageMember(null, chrome('mute', RR.mute || {}, L)[1], 'button'));
      if (rr.over.audio) vm.push(pageMember(rr.over.audio, null, rr.over.audio.kind));
      var head2 = hd ? pageMember(hd, null, 'label')
        : hdef ? pageMember(null, Object.assign({}, hdef[1], PD.heading || {}), 'label') : null;
      if (vm.length) blocks.push({ head: head2, title: head2 ? head2.props.text || textOf(head2.props.children) : null, members: vm });
      else if (head2) blocks.push({ head: null, title: null, members: [head2] });
      if (rr.over.volume) vol = Object.assign({}, rr.over.volume.props || {});
      else if (drawn('volume', RR)) vol = chrome('volume', RR.volume || {}, L)[1];
    }
    // The footer: Room Mode, Help and Power in a column; its clock has no
    // place on a 320.
    if (by.footer) {
      var fm = [];
      if (ft.over.mode) fm.push(pageMember(ft.over.mode, null, ft.over.mode.kind));
      ['help', 'power'].forEach(function (role) {
        var it = ft.over[role], x = RB[role] || RR[role];
        if (it) fm.push(pageMember(it, null, it.kind));
        else if (!FD || x) fm.push(pageMember(null, chrome(role, x || {}, L, by.footer[role])[1], 'button'));
      });
      if (fm.length) blocks.push({ head: null, title: null, members: fm });
      if (ft.over.clock || drawn('clock', RB)) {
        var cn = ft.over.clock ? nameOf(ft.over.clock) : 'Date Time';
        left.push(cn);
        warns.push(pname + "'s " + cn + ' is left off the ' + L.model + ' - its template draws no clock');
      }
    }
    // A Header's start and end controls: on with the rest.
    if (ends.length) blocks.push({ head: null, title: null, members: ends.map(function (it) { return pageMember(it, null, it.kind); }) });
    if (by.center) {
      itemsOf(by.center.children).forEach(function (it) {
        probs.push(nameOf(it) + ' in the Center: it is the popup region its sources fill - put a source\'s controls in '
                   + 'its popup');
      });
      var cname = by.center.name || 'Controls';
      left.push(cname);
      warns.push(pname + "'s " + cname + ' is left off the ' + L.model + ' - its template shows each source as a page '
                 + 'of its own');
    }
    // Main: the template's Select a Source, the tabs its keys; the rest on
    // pages of Main's own from its More.
    var homeT = roleIn(F.home, 'heading') || roleIn(F.home, 'title');
    var sel = { head: null, title: null, members: tabs.map(function (it) { return pageMember(it, null, it.kind, true); }) };
    var rest = blocks.filter(function (b) { return b.members.length; });
    var first = paginate(L, F, [sel], true, false, rest.length > 0);
    var later = rest.length ? paginate(L, F, rest, false, true, false) : { pages: [], probs: [] };
    probs = probs.concat(first.probs, later.probs);
    // One run of pages: the sources', then the rest's, each More on to the next.
    var all = { G: first.G, pages: [] };
    var nb = [sel].concat(rest);
    first.pages.forEach(function (pg) { all.pages.push(pg); });
    later.pages.forEach(function (pg) {
      pg.slots.forEach(function (s) {
        if (s.b != null) s.b += 1;
        s.cells.forEach(function (c) { c.c = { b: c.c.b + 1, m: c.c.m }; });
      });
      all.pages.push(pg);
    });
    // Each later page titled with the Sections it holds - or, where they
    // would run under its Back, with the first's, else the page's own name
    // (each Section's heading still names it on the page).
    function title(p, pg) {
      if (!p) return (homeT || {}).text || 'Select a Source';
      var words_ = [];
      pg.slots.forEach(function (s) {
        var t = nb[s.b != null ? s.b : s.cells[0].c.b].title;
        if (t && words_.indexOf(t) < 0) words_.push(t);
      });
      return (words_.length > 1 ? [words_.join(' and ')] : []).concat(words_.slice(0, 1), [pname]);
    }
    var els = drawPages(L, F, nb, all, pname, title, null, F.home, probs);
    // The Volume modal: the template's, the slider its level.
    var V = F.volume;
    if (vol && V) {
      // Its colours as the template draws them (Mach's #4B4B4C strip and
      // #E4EDF5 level): template chrome, which the six-colour cap exempts
      // (the translator's `_template_colors`) - the nearest token drew the
      // strip #303030 and the level white.
      var vels = (V.surfaces || []).map(function (s, i) {
        return drawnAt(Panel, { name: V.popup + ' Strip' + (i ? ' ' + (i + 1) : ''), fill: asMeasured(L.colors, s.fill) || 'none',
                                border: borderOf(s.border), stroke: 'none', derived: true }, s.rect, 'vs' + i);
      });
      var lv = Object.assign({}, vol, { orientation: 'up', fromSlider: true }), SL = V.level;
      delete lv.joined;
      lv.track = SL.rect[2];
      lv.border = SL.border ? borderOf(SL.border) : 'none';
      if (SL.track) lv.fill = asMeasured(L.colors, SL.track) || lv.fill;
      if (SL.bar) lv.bar = asMeasured(L.colors, SL.bar) || null;
      if (SL.art) lv.art = SL.art;
      vels.push(drawnAt(Level, lv, SL.rect, 'vlevel'));
      // Its glyphs over and under the level - Volume Up Label and Volume
      // Down Label, labels with the template's seed IDs, white at its size.
      // The template sets them in an icon face the system does not carry
      // (Extron-Lift, Extron GUI Configurator), so they say + and - (an en
      // dash: Windows-1252 has it, so every theme's face draws it).
      // Grown about its middle to a line at that size, on the screen: Mach's
      // 29 px Down glyph at 18 pt ran 3 px off its foot.
      (V.labels || []).forEach(function (x, i) {
        if (!x || !x.rect) return;
        var up = i === 0, lk = Object.assign({}, PD.glyph || PD.message || {});
        var line = x.pt != null ? lineHeight(ptOn(x.pt, Object.assign({}, L, { k: 1 }))) + 2 : 0;
        var gr = settle(x.rect, [0, line], [0, 0, L.panel.size[0], L.panel.size[1]], L.panel.size,
                        [false, false, false, false]);
        vels.push(chromeLabel(L, Object.assign(lk, { id: x.id }), 'Volume ' + (up ? 'Up' : 'Down') + ' Label',
                              up ? '+' : '\u2013', gr, 'vglyph' + i, x.pt));
      });
      if (V.cancel) {
        vels.push(drawnAt(Button, Object.assign({ name: V.popup + ' Cancel', derived: true, id: V.cancel.id,
                                                  does: 'Puts ' + V.popup + ' away.' }, PD.cancel || {}),
                          V.cancel.rect, 'vcancel'));
      }
      els.push(h(PageParts, { key: 'volume', parts: [{ name: V.popup, modal: true, els: vels }], shown: {} }));
    } else if (vol) {
      left.push(vol.name || 'Volume');
      warns.push(pname + "'s " + (vol.name || 'Volume') + ' is left off the ' + L.model + ' - its template draws no volume');
    }
    return { els: els, probs: probs, warns: warns, left: left };
  }
  // A line of chrome's words in `look` at `pt` (this panel's own, never under
  // its floor) in `width`: as it is where it fits, else broken at the space
  // that leaves its longer line least wide - 'Document Camera is' over
  // 'currently selected.', not an orphaned last word - else wrapped as often
  // as it takes; `more`, the height its extra lines add. Measured 6% wide,
  // as messageBox measures, for a canvas measuring before Open Sans loads.
  function brokenLine(L, look, line, width, pt) {
    var f = font(Object.assign({}, look || {}, { size: pt != null ? pt : (look || {}).size }), P.defaults.label.type,
                 Object.assign({}, L, { k: pt != null ? 1 : L.k }));
    var w = function (s) { return textWidth(s, f.css) * 1.06; };
    if (w(line) <= width) return { text: line, more: 0 };
    var best = null, words_ = String(line).split(' ');
    for (var i = 1; i < words_.length; i++) {
      var a = words_.slice(0, i).join(' '), b = words_.slice(i).join(' '), m = Math.max(w(a), w(b));
      if (m <= width && (!best || m < best.m)) best = { m: m, text: a + '\r\n' + b };
    }
    var lines = best ? 2 : wrapWords(line, f.css, width / 1.06).length;
    var text = best ? best.text : wrapWords(line, f.css, width / 1.06).join('\r\n');
    return { text: text, more: (lines - 1) * lineHeight(f.size) };
  }
  // `word` as a button in `look` at `r` says it: on one line where that fits
  // r across, else broken at the space nearest its middle where two lines fit
  // r both ways, else as it is (the button then grows to it).
  function twoLines(L, look, word, r) {
    var p = Object.assign({}, look || {}, { text: word });
    if (needOf('button', p, L)[0] <= r[2] || String(word).indexOf(' ') < 0) return word;
    var at = -1, mid = word.length / 2;
    for (var i = 0; i < word.length; i++) if (word[i] === ' ' && (at < 0 || Math.abs(i - mid) < Math.abs(at - mid))) at = i;
    var two = word.slice(0, at) + '\n' + word.slice(at + 1);
    var f = font(p, P.defaults.button.type, L);
    var fits = needOf('button', Object.assign({}, p, { text: two }), L)[0] <= r[2] && 2 * lineHeight(f.size) + 4 <= r[3];
    return fits ? two : word;
  }
  // A source popup, a settings window, Help, the question or a wait on the
  // 320: a page of its own (see above). `lay(kids, L)` draws it whole.
  function pagePart(props, role, name, title, F, D, T) {
    var FD = frameFor(D);
    var dsize = role === 'source' && FD ? sourceParts(FD).size : null;
    if (role === 'confirm' || role === 'wait') {
      var W = role === 'confirm' && String(props.topic || '') === 'call' && (F.windows || {}).incoming
        || (F.windows || {})[role];
      if (!W || !W.rect) return { problem: name + ' is a ' + role + ' window, which the ' + T.model + "'s template does not draw" };
      return { page: true, art: !!W.art, size: T.size.slice(), dsize: null, lay: function (kids, L) {
        var B = WD.buttons || {}, els = [], probs = [], RW = RD.window || {};
        (W.surfaces || []).forEach(function (s, i) {
          els.push(drawnAt(Panel, { name: name + ' Window' + (i ? ' ' + (i + 1) : ''),
                                    fill: s.fill ? tokenNear(L.colors, s.fill) || 'none' : 'none',
                                    border: borderOf(s.border), derived: true }, s.rect, 'win' + i));
        });
        var topic = String(props.topic || ''), said_ = WD[role] || {}, words_ = said_[topic];
        // The 320's own words for its question, where it has them: the 1035's
        // breaks Shockwave's after 'to', where its 320 runs them on.
        if (words_ != null && W.text && topic === 'power') words_ = W.text;
        if (words_ == null) {
          probs.push(name + "'s topic '" + topic + "' is not one the " + P.template + ' template has words for - '
                     + 'say topic="' + Object.keys(said_).join('" or "') + '"');
        } else if (W.message) {
          var look = Object.assign({}, RW.message || {}, PD.message || {});
          els.push(chromeLabel(L, look, name + ' Message', words_,
                               messageBox(L, look, words_, W.message, W.rect, W.lines, (W.pt || {}).message),
                               'message', (W.pt || {}).message));
        }
        if (role === 'confirm' && words_ != null) {
          (W.buttons || []).forEach(function (b, i) {
            var a = answerOf(b, topic, B, RW), word = a.word;
            var lk = a.look || {}, V = P.buttons[lk.variant] || P.buttons[P.defaults.button.variant];
            var img = imageOf(V, lk, word);
            var extra = a.yes ? { does: props.does } : topic === 'call' ? { does: a.does }
              : { does: 'Goes back to the page that asked.', back: true };
            // Its word where its look draws one (not Turbulence's, whose art
            // carries it) - on two lines where one does not fit the template's
            // button, as Turbulence's own Power Down: at the 14 pt floor
            // Mach's grew from the template's 103 to 135, unlike its Cancel.
            if (lk.text == null && !(img && img.caption === 'none')) extra.text = twoLines(L, lk, word, b.rect);
            // The seed IDs are the power-down question's (9028, 9029): a
            // call's answers standing in its places keep IDs of their own.
            els.push(navButton(L, lk, name + ' ' + word, b.rect, topic === 'call' && W !== (F.windows || {}).incoming
                               ? null : b.id, extra, 'answer' + i));
          });
        }
        if (kids.length) probs.push(name + ' is a ' + role + ' window: the template draws its words and its buttons');
        return { els: els, problems: probs, k: L.k };
      } };
    }
    return { page: true, art: true, size: T.size.slice(), dsize: dsize, lay: function (kids, L) {
      var probs = [], warns = [], left = [];
      // A page of words alone - Help in the designer's own words, in one
      // Label or a few - is set as the template sets Help's message (below):
      // in the template's columns each Label was a key's cell, Mach's 74x50,
      // and a sentence ran out of it.
      var put = kids.filter(function (it) {
        return it.rect && !REGION_NAMES[it.kind] && it.kind !== 'mainarea' && it.kind !== 'rail';
      });
      var prose = put.length && put.every(function (it) { return it.kind === 'label'; }) ? put : null;
      var cols = columnsOf(prose ? kids.filter(function (it) { return prose.indexOf(it) < 0; }) : kids,
                           name, probs, warns, left, L), els = [];
      var back0 = { does: 'Goes back to the page that shows ' + title + '.', back: true };
      var C = F.center;
      if (prose) {
        els = prosePages(L, F, prose, name, title, back0, probs);
      } else if (cols.blocks.length) {
        var laid = paginate(L, F, cols.blocks, false, true, false);
        probs = probs.concat(laid.probs);
        // A title too long beside Back is named once, not on every page.
        var said_t = [], titled = false;
        els = drawPages(L, F, cols.blocks, laid, name, function () { return title; }, back0, F, said_t);
        said_t.forEach(function (q) {
          var t = q.indexOf("'s title '") >= 0;
          if (!(t && titled)) probs.push(q);
          titled = titled || t;
        });
      } else {
        var nav = navPlaces(L, F, false, true), bk = nav.back ? backAt(L, nav) : null;
        els = stripEls(L, F, nav.strip ? F.second : F, name, title, (roleIn(F, 'title') || {}).id,
                       bk && nav.strip ? bk.rect : null, probs);
        var said_ = role === 'source' ? WD.page_empty || WD.hub_empty || WD.empty : role === 'help' ? WD.help : null;
        var lines_ = said_ != null ? said(said_, title).split('\n') : [], EL = C.empty_lines || [];
        // Help's message under the strip, clear of Back.
        var gap = L.panel.gap, top = C.rect[1] + gap;
        var foot = nav.back && !nav.strip ? nav.back.rect[1] - gap : L.panel.size[1] - gap;
        if (role === 'source' && EL.length > 1 && lines_.length === EL.length) {
          // A label a line, where the template sets its empty state so (the
          // 320's Laptop Label 1-3): its first sentence a paragraph apart
          // from the other two, which one box drawing three lines evenly lost.
          // A line its words outrun - 'Document Camera is currently selected.'
          // at the 320's 14 pt floor, already the least it may be set in -
          // breaks as the template breaks one: in that label, on a line more
          // (Mach's Aux Label 2, 'There are no controls\r\nfor this device.'
          // grown from 35 to 51 px), the first growing up into the room under
          // the strip, a later one down with what follows it.
          var down = 0;
          lines_.forEach(function (line, i) {
            var r = EL[i].rect.slice(), look = Object.assign({}, PD.empty || {}, EL[i].id != null ? { id: EL[i].id } : {});
            var br = brokenLine(L, look, line, r[2], (C.pt || {}).empty);
            r[1] += down;
            if (br.more) {
              if (i === 0) r[1] -= br.more;
              else down += br.more;
              r[3] += br.more;
            }
            els.push(chromeLabel(L, look, name + ' Empty' + (i ? ' ' + (i + 1) : ''), br.text, r, 'empty' + i,
                                 (C.pt || {}).empty));
          });
        } else if (said_ != null) {
          var e = C.empty;
          if (role === 'help') e = [gap, top, L.panel.size[0] - 2 * gap, foot - top];
          els.push(chromeLabel(L, PD.empty, name + (role === 'help' ? ' Message' : ' Empty'), said(said_, title), e,
                               'empty', (C.pt || {}).empty));
        }
        if (bk) els.push(navButton(L, bk.look, name + ' Back', bk.rect, nav.back.id, back0, 'back0'));
      }
      return { els: cols.loose.map(function (it, i) { return React.cloneElement(it.host, { key: 'loose' + i }); }).concat(els),
               problems: probs, warnings: warns, left: left, k: L.k };
    } };
  }

  // -- Group: a set of like controls, laid out and paged for each panel ------
  // A wrapping grid of equal cells, `cap` to a row, in the Group's own box.
  // On each panel every cell is as big as its largest member needs (touch
  // minimum, caption at the panel's type), and then, by tier: A - in place,
  // or, if they do not fit, its pages as popups in its box with Previous and
  // Next; B - on a page a popup group in its box always (the region the
  // program shows it in); A or B in a modal or a popup - in place, since a
  // popup shows no popups; C - one button that opens its pages, each a page
  // of its own with Back. Every control keeps its name; what cannot fit even
  // so is named.
  function cellsOf(props, items) {
    var cd = String(props.cell || '').split(/[x, ]+/).map(Number);
    if (cd.length === 2 && cd[0] > 0 && cd[1] > 0) return cd;
    var r = items.length && items[0].rect;
    return r ? [r[2], r[3]] : [110, 110];
  }
  function gridPlace(n, perRow, cw, ch, g, W, H, top) {
    var rows = Math.ceil(n / perRow), out = [];
    var block = rows * ch + (rows - 1) * g;
    var y = top != null ? top : Math.round((H - block) / 2);
    for (var r = 0; r < rows; r++) {
      var cnt = Math.min(perRow, n - r * perRow);
      var x = Math.round((W - (cnt * cw + (cnt - 1) * g)) / 2);
      for (var c = 0; c < cnt; c++) out.push([x + c * (cw + g), y + r * (ch + g), cw, ch]);
    }
    return out;
  }
  // The cell a Group's members share on this panel: the designed cell at the
  // frame's scale, grown to what its largest member needs.
  function segments(props, L) {
    var items = itemsOf(props.children);
    var cellD = cellsOf(props, items), k = L.k == null ? 1 : L.k;
    var cw = cellD[0] * k, ch = cellD[1] * k;
    items.forEach(function (it) {
      var gr = grow([0, 0, cellD[0] * k, cellD[1] * k], needs(it, L), hasArt(it));
      cw = Math.max(cw, gr[2]); ch = Math.max(ch, gr[3]);
    });
    return { n: items.length, cw: Math.ceil(cw), ch: Math.ceil(ch), cell: cellD };
  }
  // A segmented control (a joined Group) is one row of touching segments -
  // but not across more than a tier C panel's screen: Shockwave's four
  // 152 px source tabs needed 336 px of the 320's 320. There it pages as any
  // Group does, a button that opens its segments' pages.
  function joinedHere(p, L) {
    if (!truthy(p.joined)) return false;
    if (!(L && L.aware && L.tier === 'C' && L.model !== L.designModel)) return true;
    var seg = segments(p, L);
    return seg.n * seg.cw <= L.panel.size[0] - 2 * L.panel.gap;
  }
  function Group(props) {
    var L = useLook();
    var items = itemsOf(props.children);
    var title = props.title || props.name || 'Group';
    var cap = Number(props.cap) || 4;
    var cellD = cellsOf(props, items);
    var gapD = props.gap != null ? Number(props.gap) : 49;
    var joined = joinedHere(props, L);
    var shown = React.useState(null);
    // A member is a component in a cell. Anything else - a wrapper div, an
    // sc-for - keeps what it holds and is named: cloned with no children, it
    // had them replaced with nothing, and its buttons vanished unremarked.
    function member(it, r, key) {
      return it.comp
        ? React.cloneElement(it.host, { key: key, style: cell(r) },
                             React.cloneElement(it.comp, joined ? { joined: title } : {}))
        : React.cloneElement(it.host, { key: key, style: cell(r) });
    }
    var loose = items.filter(function (it) { return !it.comp; }).map(function (it) {
      return title + ' holds a ' + (typeof it.host.type === 'string' ? it.host.type : 'repeat')
        + ' - a Group lays out components, each in a cell; put the components in it directly';
    });
    if (!(L && L.aware && props.__box)) {
      var gg = joined ? 0 : gapD;
      return h('div', { className: 'xgdl-group',
                        style: { position: 'relative', width: '100%', height: '100%', display: 'flex',
                                 flexWrap: 'wrap', alignContent: 'center', justifyContent: 'center',
                                 gap: gg + 'px' } },
        items.map(function (it, i) {
          var st = { key: 'g' + i, style: { width: cellD[0] + 'px', height: cellD[1] + 'px', flex: '0 0 auto' } };
          return it.comp ? React.cloneElement(it.host, st, React.cloneElement(it.comp, joined ? { joined: title } : {}))
                         : React.cloneElement(it.host, st);
        }));
    }
    var T = L.panel, k = props.__k || L.k || 1;
    var Lk = Object.assign({}, L, { k: k });
    var seg = segments(props, Lk), cw = seg.cw, ch = seg.ch;
    var g = joined ? 0 : Math.ceil(Math.max(gapD * k, T.gap));
    var nav = T.touch, n = items.length;
    var groupName = (L.pageName || 'Page') + ' ' + title;
    function partName(i) { return i ? groupName + ' ' + (i + 1) : groupName; }
    var forced = typeof window !== 'undefined' && window.__GDL_SHOW ? String(window.__GDL_SHOW) : null;
    var navFont = font({}, P.defaults.button.type, Lk);
    function navW(word) { return Math.max(T.touch, Math.ceil(textWidth(word, navFont.css) + 24)); }
    function navButton(suffix, word, to, onPress, r, key) {
      return h('div', { key: key, style: cell(r) },
               h(Button, { name: title + ' ' + suffix, derived: true, text: word, goes: to, onPress: onPress }));
    }
    // Grown past its box, it keeps to the page as any control does
    // (scaleLayout's `__room`: its box's place and the frame's size) - Build
    // moves a control that crosses its page's edge.
    function keep(left, top, w, ht) {
      var rm = props.__room;
      if (!rm) return [left, top];
      return [Math.min(Math.max(left, -rm[0]), rm[2] - rm[0] - w),
              Math.min(Math.max(top, -rm[1]), rm[3] - rm[1] - ht)];
    }
    var problems = loose.slice();
    // A segmented control is one row of touching segments on every panel:
    // paged, or split into pages, it would no longer be one control.
    if (joined) {
      var JW = Math.max(props.__box[0], n * cw), JH = Math.max(props.__box[1], ch);
      var jr = gridPlace(n, n, cw, ch, 0, JW, JH);
      var jp = keep(Math.round((props.__box[0] - JW) / 2), Math.round((props.__box[1] - JH) / 2), JW, JH);
      return h('div', { className: 'xgdl-group',
                        style: { position: 'absolute', left: jp[0] + 'px', top: jp[1] + 'px',
                                 width: JW + 'px', height: JH + 'px' } },
               items.map(function (it, i) { return member(it, jr[i], 'c' + i); }).concat(problems.map(problem)));
    }
    // Tier C: the box holds one button; the items are pages of their own.
    if (L.tier === 'C' && L.model !== L.designModel) {
      var M = T.main, foot = T.rail_axis === 'row' && T.rail ? T.rail : null;
      var pad = T.gap;
      var area = [M[0] + pad, M[1] + pad, M[2] - 2 * pad, M[3] - 2 * pad - (foot ? 0 : nav + g)];
      var pr = Math.max(0, Math.min(cap, Math.floor((area[2] + g) / (cw + g))));
      var rr = Math.max(0, Math.floor((area[3] + g) / (ch + g)));
      var per = pr * rr;
      if (per < 1) {
        problems.push(title + ' cannot fit one ' + cw + 'x' + ch + ' cell on a page of a ' + T.model);
        per = 1; pr = 1;
      }
      var pages = Math.ceil(n / per);
      var cur = shown[0];
      for (var q = 0; q < pages; q++) if (forced === partName(q)) cur = q;
      var opener = h('div', { key: 'open', style: cell([0, 0, props.__box[0], props.__box[1]]) },
                     h(Button, { name: title, derived: true, text: title, goes: partName(0),
                                 onPress: function () { shown[1](0); } }));
      var layers = [];
      for (var pg = 0; pg < pages; pg++) {
        var mine = items.slice(pg * per, (pg + 1) * per);
        var spots = gridPlace(mine.length, pr, cw, ch, g, area[2], area[3], 0);
        var row = foot ? [foot[0], foot[1], foot[2], foot[3]] : [M[0], M[1] + M[3] - nav - pad, M[2], nav];
        var ny = row[1] + Math.round((row[3] - nav) / 2);
        var kids = mine.map(function (it, j) {
          var sp = spots[j];
          return member(it, [area[0] + sp[0], area[1] + sp[1], sp[2], sp[3]], 'p' + pg + 'c' + j);
        });
        (function (p0) {
          kids.push(navButton('Back', 'Back', L.pageName || 'Page', function () { shown[1](null); },
                              [row[0] + pad, ny, navW('Back'), nav], 'back' + p0));
          var right = row[0] + row[2] - pad;
          if (p0 < pages - 1) {
            var wn = navW('Next');
            kids.push(navButton('Next', 'Next', partName(p0 + 1), function () { shown[1](p0 + 1); },
                                [right - wn, ny, wn, nav], 'next' + p0));
            right -= wn + g;
          }
          if (p0 > 0) {
            var wp = navW('Previous');
            kids.push(navButton('Previous', 'Previous', partName(p0 - 1), function () { shown[1](p0 - 1); },
                                [right - wp, ny, wp, nav], 'prev' + p0));
          }
        })(pg);
        var look = Object.assign({ kind: 'page', name: partName(pg), host: L.pageName || 'Page',
                                   size: T.size }, L.pageLook || {});
        layers.push(h('div', { key: 'layer' + pg, 'data-gdl-part': JSON.stringify(look),
                               style: Object.assign({ position: 'fixed', left: 0, top: 0, width: T.size[0] + 'px',
                                                      height: T.size[1] + 'px', zIndex: 10,
                                                      visibility: cur === pg ? 'visible' : 'hidden' },
                                                    L.pageStyle || {}) }, kids));
      }
      return h('div', { className: 'xgdl-group', style: outlined({ position: 'absolute', inset: 0 }, problems) },
               [opener].concat(layers, problems.map(problem)));
    }
    // Tiers A and B: the box grows to hold one cell, then holds what it can.
    var bx = props.__box, W = Math.max(bx[0], cw), H = Math.max(bx[1], ch);
    // Two pixels of slack: cells and box are each rounded to whole pixels, and
    // three cells drawn to fill a box exactly must not come out one too wide.
    function holds(gg) {
      return Math.max(1, Math.min(cap, Math.floor((W + gg + 2) / (cw + gg))))
             * Math.max(1, Math.floor((H + gg + 2) / (ch + gg)));
    }
    // The gap scales with the page, the cells grow to their minimum: before
    // the Group pages, its gap gives way to them, down to the panel's own
    // 2 mm. The round-three Turbulence room's Lighting presets did not fit
    // the 525 at their scaled 24 px until its designer narrowed them by hand.
    if (!joined && n > holds(g)) {
      for (var gg = g - 1; gg >= T.gap; gg--) if (n <= holds(gg)) { g = gg; break; }
    }
    var perRow = Math.max(1, Math.min(cap, Math.floor((W + g + 2) / (cw + g))));
    var rows = Math.max(1, Math.floor((H + g + 2) / (ch + g)));
    W = Math.max(W, perRow * cw + (perRow - 1) * g);
    // A modal or a popup can show no popup group - a popup is shown only from
    // a page - so there a Group lays out in place, on a hub as well: the
    // round-two conference rooms' Lighting Presets, a popup group in their
    // Lighting modal, could never be shown.
    var inPopup = L.within === 'modal' || L.within === 'popup';
    var popup = L.tier === 'B' && L.model !== L.designModel && !inPopup;
    var rp = keep(Math.round((bx[0] - W) / 2), Math.round((bx[1] - H) / 2), W, H);
    var root = { position: 'absolute', left: rp[0] + 'px', top: rp[1] + 'px', width: W + 'px', height: H + 'px' };
    if (n <= perRow * rows && !popup) {
      var at = gridPlace(n, perRow, cw, ch, g, W, H);
      return h('div', { className: 'xgdl-group', style: outlined(root, problems) },
               items.map(function (it, i) { return member(it, at[i], 'c' + i); }).concat(problems.map(problem)));
    }
    if (inPopup) {
      // Nor can it page there: its pages would be popups. What does not fit
      // is named, and drawn in rows past its box.
      problems.push(title + ' cannot page in a ' + L.within + ' - its pages would be popups, which only a page '
                    + 'can show - and its ' + n + ' cells of ' + cw + 'x' + ch + ' do not fit its ' + W + 'x' + H
                    + ' box on a ' + T.model + ': give it a box that holds them all there, or put it on a page');
      var over = gridPlace(n, perRow, cw, ch, g, W, Math.ceil(n / perRow) * (ch + g) - g, 0);
      return h('div', { className: 'xgdl-group', style: outlined(root, problems) },
               items.map(function (it, i) { return member(it, over[i], 'c' + i); }).concat(problems.map(problem)));
    }
    var fits = n <= perRow * rows;
    // A box too narrow for Previous and Next side by side under its cells -
    // a one-cell column, Afterburn's left rail as a Group on a 525 - says
    // them as arrows where their words do not fit it, and stands them one
    // over the other where even the arrows do not fit side by side: across,
    // they came out 2 px apart and 'Previous' wider than the box.
    var words2 = navW('Previous') <= W && navW('Next') <= W ? ['Previous', 'Next'] : ['\u2039', '\u203a'];
    var stack = navW(words2[0]) + navW(words2[1]) + g > W;
    var navH = stack ? 2 * nav + g : nav;
    var avail = fits ? rows : Math.floor((H - navH) / (ch + g));
    // No room under a row for Previous and Next - a row of presets drawn one
    // cell deep, its cells grown on a 525 - and they go at its ends: under it
    // they overlapped the row, and the Group was refused (the round-two rooms'
    // Sources, Lighting and Camera Presets).
    // Where their words leave no cell between them, they are arrows at the
    // touch minimum - Mach's Sources, 113 px cells in a 320 px box - with the
    // names the ID map gives them still Previous and Next. Single guillemets:
    // Windows-1252 has them, so every theme's face draws them.
    var side = null;
    if (!fits && avail < 1 && H >= nav) {
      [['Previous', 'Next'], ['\u2039', '\u203a']].forEach(function (said) {
        if (side) return;
        var sp = navW(said[0]), sn = navW(said[1]), inner = W - sp - sn - 2 * g;
        var across = Math.max(0, Math.min(cap, Math.floor((inner + g + 2) / (cw + g))));
        if (across >= 1) side = { p: sp, n: sn, inner: inner, across: across, said: said };
      });
    }
    var perPage = side ? side.across * rows : perRow * avail;
    if (perPage < 1) {
      problems.push(title + ' cannot fit a row of ' + cw + 'x' + ch + ' cells and its Previous and Next in its '
                    + W + 'x' + H + ' box on a ' + T.model);
      perPage = Math.max(1, perRow);
    }
    var count = Math.ceil(n / perPage);
    var now = shown[0] == null ? 0 : shown[0];
    for (var f = 0; f < count; f++) if (forced === partName(f)) now = f;
    var parts = [];
    for (var pi = 0; pi < count; pi++) {
      var mine2 = items.slice(pi * perPage, (pi + 1) * perPage);
      var top = count > 1 ? 0 : null;
      var spots2 = side
        ? gridPlace(mine2.length, side.across, cw, ch, g, side.inner, H).map(function (s) {
            return [s[0] + side.p + g, s[1], s[2], s[3]];
          })
        : gridPlace(mine2.length, perRow, cw, ch, g, W, count > 1 ? H - navH - g : H, top);
      var kids2 = mine2.map(function (it, j) { return member(it, spots2[j], 'p' + pi + 'c' + j); });
      (function (p0) {
        if (side) {
          var ys = Math.round((H - nav) / 2);
          if (p0 > 0) {
            kids2.push(navButton('Previous', side.said[0], partName(p0 - 1), function () { shown[1](p0 - 1); },
                                 [0, ys, side.p, nav], 'prev' + p0));
          }
          if (p0 < count - 1) {
            kids2.push(navButton('Next', side.said[1], partName(p0 + 1), function () { shown[1](p0 + 1); },
                                 [W - side.n, ys, side.n, nav], 'next' + p0));
          }
          return;
        }
        var y = H - nav, right = W;
        if (p0 < count - 1) {
          var wn = navW(words2[1]);
          kids2.push(navButton('Next', words2[1], partName(p0 + 1), function () { shown[1](p0 + 1); },
                               [right - wn, y, wn, nav], 'next' + p0));
          right -= wn + g;
        }
        if (p0 > 0) {
          var wp = navW(words2[0]);
          kids2.push(navButton('Previous', words2[0], partName(p0 - 1), function () { shown[1](p0 - 1); },
                               stack ? [0, y - nav - g, wp, nav] : [0, y, wp, nav], 'prev' + p0));
        }
      })(pi);
      parts.push(h('div', { key: 'part' + pi,
                            'data-gdl-part': JSON.stringify({ kind: 'popup', name: partName(pi), group: groupName,
                                                              size: [W, H] }),
                            style: { position: 'absolute', left: 0, top: 0, width: W + 'px', height: H + 'px',
                                     visibility: now === pi ? 'visible' : 'hidden' } }, kids2));
    }
    // The region the program shows the group's popups in: a control of the page.
    var region = h('div', { key: 'region', style: { position: 'absolute', left: 0, top: 0, width: W + 'px', height: H + 'px' },
                            'data-gdl': gdl({ kind: 'popup_ref', name: title + ' Region', group: groupName,
                                              derived: true }) });
    return h('div', { className: 'xgdl-group', style: outlined(root, problems) },
             [region].concat(parts, problems.map(problem)));
  }

  // -- the resource kit ------------------------------------------------------
  // P.kit.files: {size: {icon: {look: file}}}, a look being `off`, a color,
  // `sel` or `plain`; P.kit.art: {file: data URI}. A state asks for `off` or
  // `on`, and `on` is the scheme's primary accent for an icon family drawn in
  // the primary accents, its secondary for one drawn in the secondary ones
  // (toggles, volume levels), else whatever the family has.
  var KIT = P.kit || null;
  var PRIMARY_ONLY = ['orange', 'light-blue', 'med-blue'];
  function kitFile(size, icon, look, scheme) {
    var fam = KIT && KIT.files && KIT.files[size] && KIT.files[size][icon];
    if (!fam) return null;
    var primary = PRIMARY_ONLY.some(function (c) { return fam[c]; });
    // A kit with no accent schemes (Mach's one image per icon) has neither map.
    function on() {
      return (primary ? fam[(KIT.primary || {})[scheme]] : fam[(KIT.secondary || {})[scheme]])
        || fam.sel || fam.red || fam.plain || fam.off || null;
    }
    if (look === 'on') return on();
    if (look === 'off') return fam.off || fam.gray || fam.plain || on();
    return fam[look] || null;
  }
  // How the variant draws its image, if it has one: the kit size, and where
  // the caption goes - `below` the icon, `indent`ed past it, or `none`.
  // `__indent`: the leading spaces a region gave an indented caption to
  // clear its icon in the cell it came out (indentFit).
  // `__breaks`: the breaks a caption below its icon takes where a region
  // sets it over the art instead (0: Turbulence's hub Display Control, its
  // words over the template's blank tile).
  // `__caption` and `__kit`: where a key the template draws its own way is
  // given that way by the region that draws it - the dialer's Call, Flash
  // and Contacts, their words beside the glyph of Mach's 880x440 art and of
  // Shockwave's pills, as the template sets them.
  function imageOf(V, props, caption) {
    function indent(d) { return props.__indent != null ? Number(props.__indent) : d; }
    function breaks(d) { return props.__breaks != null ? Number(props.__breaks) : d; }
    if (V.kit) return { kit: V.kit, caption: props.__caption || V.caption, indent: indent(V.indent),
                        breaks: breaks(V.breaks), icon: props.icon || V.icon };
    if (props.icon && V.with_icon) {
      var W = V.with_icon;
      return caption ? { kit: props.__kit || W.kit, caption: props.__caption || W.caption, indent: indent(W.indent),
                         breaks: breaks(W.breaks), icon: props.icon }
                     : { kit: props.__kit || W.bare, caption: 'none', icon: props.icon };
    }
    return null;
  }
  function belowBreaks(img) { return img.breaks === 0 ? 0 : img.breaks || 2; }
  // The caption as the panel draws it: the kit leaves the label room below or
  // beside the icon, and the template's own buttons reach it with line breaks
  // or leading spaces in the caption itself - two breaks unless the variant
  // says (Mach's 150 px source tiles take three, as its seed's Camera 1 does).
  function placed(img, text) {
    if (!img || text == null) return text;
    if (img.caption === 'none') return '';
    if (img.caption === 'below') return text ? new Array(belowBreaks(img) + 1).join('\r\n') + text : text;
    if (img.caption === 'indent') return text ? new Array((img.indent || 0) + 1).join(' ') + text : text;
    return text;
  }

  // A caption as its variant draws it: Turbulence's dock puts two words on
  // two lines (`lines`: 2), broken at the space nearest the middle, as the
  // seed's Screen Control, Lighting Control and Room Mode are - on one line
  // the 720's Room Mode grew 23 px into the date beside it.
  function captionOf(V, p) {
    return twoWords(V, textOf(p.children, p.text));
  }
  // And a state's own caption, which is the caption in that state: Mic
  // Mute's 'Mics Muted' drawn on one line in its dock ran past its 112 px
  // on Turbulence's 725, and measured so grew the rail's column into Help.
  function twoWords(V, c) {
    var at = -1;
    if (V.lines !== 2 || !c || /\n/.test(c)) return c;
    for (var i = 0; i < c.length; i++) {
      if (c.charAt(i) === ' ' && (at < 0 || Math.abs(i - c.length / 2) < Math.abs(at - c.length / 2))) at = i;
    }
    return at < 0 ? c : c.slice(0, at) + '\r\n' + c.slice(at + 1);
  }

  // -- Button ---------------------------------------------------------------
  function Button(props) {
    var L = useLook();
    var variant = P.buttons[props.variant] ? props.variant : P.defaults.button.variant;
    var V = P.buttons[variant];
    var caption = captionOf(V, props);
    var img = imageOf(V, props, caption);
    // A caption beside its icon in a key a region sizes (`__fit`, its [w, h]
    // there) and gives no indent: the leading spaces that start it clear of
    // the icon, centred (indentFit), as the template sets the dialer's Call
    // and Flash ('         Call' on Shockwave's 1035) and an incoming call's
    // answers - centred over the glyph, the words ran into it.
    var fitted = img && img.caption === 'indent' && props.__indent == null && props.__fit
      ? indentFit(Object.assign({}, props, { align: 'center' }), props.__fit[0], props.__fit[1], L) : null;
    if (fitted) {
      // Where the words and that room are wider than the key (Mach's
      // Contacts at 14 pt), as far past the glyph as the key holds them.
      var f0 = font(props, P.defaults.button.type, L), tc0 = textWidth(caption, f0.css);
      var room = Math.floor((props.__fit[0] - 8 - tc0) / (textWidth('          ', f0.css) / 10));
      img.indent = Math.max(0, fitted.w <= props.__fit[0] + 1 ? fitted.n : Math.min(fitted.n, room));
    }
    var own = {};
    ['fill', 'stroke', 'color', 'border'].forEach(function (k) { if (props[k] != null) own[k] = props[k]; });
    var look = Object.assign({}, V.look, own);
    // Icons the kit does not have, by size: the translator refuses them.
    var missing = [];
    var states = (list(props.states) || V.states).map(function (s, i) {
      s = typeof s === 'string' ? { name: s } : Object.assign({}, s);
      // A state named like one of the variant's (Off, On) starts from its look.
      s = Object.assign({}, find(V.states, s.name) || {}, s);
      if (img) {
        var icon = s.icon || img.icon;
        var want = s.look || (i === 0 ? 'off' : 'on');
        s.image = kitFile(img.kit, icon, want, L.scheme);
        if (!s.image) missing.push(img.kit + ' ' + icon);
        if (s.text != null) s.text = placed(img, twoWords(V, s.text));
      } else if (s.text != null) {
        s.text = twoWords(V, s.text);
      }
      delete s.look; delete s.icon;
      return s;
    });
    // Held, the panel shows the press state (TLPPressFeedbackStateID): `press`,
    // else the second state - the spec's own default - so Play shows it too.
    var held = React.useState(false);
    var pressState = find(states, props.press) || states[1] || states[0] || {};
    var shown = held[0] ? pressState : (find(states, props.show) || states[0] || {});
    var now = Object.assign({}, look, shown);
    var f = font(props, P.defaults.button.type, L);
    var b = borderOn(L, now.border);
    // An indented caption reads from the left unless the variant says
    // otherwise: Shockwave's centers it, pushed right past the icon.
    var align = props.align || (fitted ? 'center' : null) || V.align || (img && img.caption === 'indent' ? 'left' : null)
      || 'center';
    var art = now.image && KIT && KIT.art ? KIT.art[now.image] : null;
    var style = {
      boxSizing: 'border-box', width: '100%', height: '100%',
      // The touch minimum; on a panel, the cell the frame gave it already is,
      // unless a plain container scales it (css). A mirror inside its
      // control (planHeader's twin) is pressed as that control: its own.
      minWidth: props.__mirror ? 0 : (L.aware ? L.panel.touch / (L.css || 1) : P.touch) + 'px',
      minHeight: props.__mirror ? 0 : (L.aware ? L.panel.touch / (L.css || 1) : P.touch) + 'px',
      display: 'flex', alignItems: 'center', justifyContent: ALIGN[align] || 'center',
      padding: img ? 0 : '0 10px', margin: 0, textAlign: align,
      whiteSpace: img ? 'pre' : 'pre-line',
      background: (art ? 'url("' + art + '") center / contain no-repeat, ' : '') + paint(L.colors, now.fill),
      border: edge(b, L.colors, now.stroke),
      borderRadius: radius(b), color: paint(L.colors, now.color || 'text'),
      font: f.css, textDecoration: 'none', cursor: 'pointer'
    };
    if (missing.length) style.outline = '2px dashed #FF00FF';
    var text = img ? placed(img, caption) : caption;
    var attrs = {
      className: 'xgdl xgdl-button', style: style,
      'aria-label': props['aria-label'] || props.ariaLabel || (img && !caption ? img.icon : null),
      'data-gdl': gdl({
        kind: 'button', name: props.name, id: idOf(props.id),
        variant: variant, text: text, fill: look.fill, stroke: look.stroke,
        color: look.color, border: look.border, size: f.size, bold: f.bold,
        align: align === 'center' ? null : align,
        states: states, press: props.press, nav: props.nav || props.goes, does: props.does,
        // Navigation a panel's layout added (Up and Down beside a level, a
        // Group's Previous and Next): the program still handles it by ID.
        derived: truthy(props.derived) || null,
        // A segment of one segmented control (a joined Group): it may touch
        // its neighbours in that control, and no others.
        joined: props.joined || null,
        // A derived Back that goes back to the page that shows its page,
        // which the translator finds (the 320's: pagePart).
        back: truthy(props.back) || null,
        // The template's seed ID a region's chrome keeps where it is free,
        // and the control a copy mirrors under its ID (planHeader's twin):
        // the translator's, which pins them (gdl.design pin_ids).
        seed_id: props.__seed != null ? Number(props.__seed) : null,
        mirror: props.__mirror || null,
        missing_icon: missing.length ? missing : null
      })
    };
    if (props.nav) attrs.href = navHref(props.nav); else attrs.type = 'button';
    // A derived control's target is a derived page or popup, not an
    // artboard: it switches its Group's page in Play instead of linking.
    if (typeof props.onPress === 'function') attrs.onClick = props.onPress;
    attrs.onPointerDown = function () { held[1](true); };
    attrs.onPointerUp = attrs.onPointerLeave = attrs.onPointerCancel = function () { held[1](false); };
    var label = shown.text != null ? shown.text : text;
    if (missing.length && !label) label = '[' + missing[0] + ']';
    return h(props.nav ? 'a' : 'button', attrs, label);
  }

  // -- Label ----------------------------------------------------------------
  function Label(props) {
    var L = useLook();
    var f = font(props, P.defaults.label.type, L);
    // `__text`: its words as a tier C layout broke them into lines (flowRows).
    var words_ = props.__text != null ? props.__text : textOf(props.children, props.text);
    var color = props.color || P.defaults.label.color;
    var align = props.align || 'left';
    // A field: the ground a template's label paints itself - Shockwave's and
    // Turbulence's Dialer Feedback Label is the dialer's number field, white
    // and #DCDCDC, with no shape under it. None by default.
    var fill = props.fill && props.fill !== 'none' ? props.fill : null;
    var border = fill ? props.border || 'none' : null, b = fill ? borderOn(L, border) : null;
    return h('div', {
      className: 'xgdl xgdl-label',
      style: {
        boxSizing: 'border-box', width: '100%', height: '100%', display: 'flex',
        alignItems: 'center', justifyContent: ALIGN[align] || 'flex-start',
        textAlign: align, whiteSpace: 'pre-line', color: paint(L.colors, color), font: f.css,
        background: fill ? paint(L.colors, fill) : undefined, borderRadius: b ? radius(b) : undefined,
        // At least a line on this panel, as a Button is at least its touch
        // size - from inside, where a scaled container laid it out.
        minHeight: L.aware ? (lineHeight(f.size) + 2) / (L.css || 1) + 'px' : undefined
      },
      'data-gdl': gdl({ kind: 'label', name: props.name, id: idOf(props.id),
                        text: words_, color: color, size: f.size,
                        bold: f.bold, align: align, does: props.does, fill: fill, border: border,
                        // A copy a panel's layout repeats (overPages' title strip).
                        derived: truthy(props.derived) || null })
    }, words_);
  }

  // -- Panel: a filled shape behind other controls --------------------------
  function Panel(props) {
    var L = useLook();
    var fill = props.fill || P.defaults.panel.fill;
    var border = props.border || P.defaults.panel.border;
    var stroke = props.stroke || P.defaults.panel.stroke;
    var b = borderOn(L, border);
    return h('div', {
      className: 'xgdl xgdl-panel',
      style: { boxSizing: 'border-box', width: '100%', height: '100%',
               background: paint(L.colors, fill), border: edge(b, L.colors, stroke),
               borderRadius: radius(b) },
      'data-gdl': gdl({ kind: 'panel', name: props.name, fill: fill, stroke: stroke,
                        border: border, derived: truthy(props.derived) || null })
    });
  }

  // -- Image: the template's own art ----------------------------------------
  // A PBImage drawing a kit file from its backgroundImageField, as every one
  // in the Turbulence seeds does: its header and footer bars stretched over
  // their box (`layout` stretch), a source's device picture fitted in its
  // own (fill, the default). `fill` draws a ground under it - the seeds'
  // side bars are images with no art, a fill. A file the kit lacks draws
  // dashed and the translator refuses it; on a panel whose seed has no
  // PBImage to clone (its series' `kinds`: every Shockwave seed, Mach's hubs
  // and 320, Turbulence's 320) it is named, as a Level is.
  var KIT_FILES = null;
  function kitHas(file) {
    if (!KIT_FILES) {
      KIT_FILES = {};
      var files = (KIT && KIT.files) || {};
      Object.keys(files).forEach(function (size) {
        Object.keys(files[size]).forEach(function (icon) {
          var looks = files[size][icon];
          Object.keys(looks).forEach(function (l) { KIT_FILES[looks[l]] = true; });
        });
      });
    }
    return !!(file && KIT_FILES[file]);
  }
  // Whether this panel's seed can clone a PBImage: on a Page that lists no
  // panels, the system's own.
  function imagesOn(L) {
    var panel = L && (L.panel || (L.page && P.models && P.models[P.model]));
    return !(panel && panel.kinds && panel.kinds.image === false);
  }
  function ImageArt(props) {
    var L = useLook();
    var stretch = props.layout === 'stretch';
    var file = props.image || null;
    var art = file && KIT && KIT.art ? KIT.art[file] : null;
    var missing = file && !kitHas(file) ? file : null;
    var panel = L.panel || (L.page && P.models && P.models[P.model]);
    var lacks = !imagesOn(L)
      ? (props.name || 'Image') + " is an image, which the " + ((panel && panel.model) || P.model)
        + "'s seed cannot build"
      : null;
    var box = { boxSizing: 'border-box', width: '100%', height: '100%',
                background: (art ? 'url("' + art + '") center / ' + (stretch ? '100% 100%' : 'contain')
                             + ' no-repeat, ' : '') + paint(L.colors, props.fill) };
    if (missing) box.outline = '2px dashed #FF00FF';
    return h('div', {
      className: 'xgdl xgdl-image',
      style: lacks ? outlined(box, [lacks]) : box,
      'data-gdl': gdl({ kind: 'image', name: props.name, image: file,
                        layout: stretch ? 'stretch' : null, fill: props.fill,
                        derived: truthy(props.derived) || null })
    }, lacks ? problem(lacks, 'image') : null);
  }

  // -- Line: a divider ------------------------------------------------------
  function Line(props) {
    var L = useLook();
    var color = props.color || P.defaults.line.color;
    var t = Number(props.thickness) || P.defaults.line.thickness;
    var vertical = props.orientation === 'vertical';
    return h('div', {
      className: 'xgdl xgdl-line',
      style: { boxSizing: 'border-box', width: vertical ? t + 'px' : '100%',
               height: vertical ? '100%' : t + 'px', background: paint(L.colors, color) },
      'data-gdl': gdl({ kind: 'line', name: props.name, fill: color, thickness: t,
                        from: vertical ? 'TopCenter' : 'MiddleLeft',
                        to: vertical ? 'BottomCenter' : 'MiddleRight' })
    });
  }

  // -- Slider and Level ------------------------------------------------------
  // As the template builds them: a thin rounded rail `track` px wide, centred
  // in the control's box, which is the touch area. The rail's empty part is
  // `fill`; the part up to the value is the template's fill color; a slider
  // adds a round thumb `thumb` px across. Afterburn's own: a 10 px rail in a
  // 50 px wide control, #BABCCE fill, a 50 px periwinkle thumb.
  function track(kind, props) {
    var L = useLook();
    var d = P.defaults[kind];
    var fill = props.fill || d.fill;
    var o = props.orientation || d.orientation || 'up';
    var along = o === 'up' || o === 'down';            // the value runs vertically
    var t = Number(props.track) || d.track;
    var s = kind === 'slider' ? Number(props.thumb) || d.thumb : 0;
    var pct = props.value != null ? Math.max(0, Math.min(100, Number(props.value))) : 60;
    // The rail stops where the thumb's centre can reach: half its length
    // along the rail.
    var end = (s ? Number(d.thumb_height) || s : 0) / 2;
    // Where the template draws its rail from its own art (Shockwave,
    // Turbulence, Mach), the canvas does too: the empty rail's image, and the
    // filled one showing only as far as the value, anchored at its start.
    var rails = kind === 'slider' && P.kit && P.kit.rail_art ? P.kit.rail_art : {};
    // A hub's level from the kit's own art (its Volume Level strip's
    // `level.art`: Shockwave's vol-empty and vol-full, Turbulence's bars).
    if (kind === 'level' && props.art && KIT && KIT.art) {
      rails = { track: KIT.art[props.art.track], fill: KIT.art[props.art.fill] };
    }
    var from = along ? (o === 'up' ? 'bottom' : 'top') : (o === 'right' ? 'left' : 'right');
    // Square where its border is none (a hub's level, as its template's).
    var round = (props.border || d.border) === 'none' ? 0 : t / 2;
    var rail = { position: 'absolute', borderRadius: round + 'px',
                 background: rails.track ? 'url("' + rails.track + '") center / 100% 100% no-repeat'
                                         : paint(L.colors, fill) };
    var barColor = kind === 'level' && props.bar ? props.bar : d.value;
    var bar = { position: 'absolute', borderRadius: round + 'px', background: paint(L.colors, barColor) };
    var span = 'calc(100% - ' + 2 * end + 'px)';
    var reach = 'calc((100% - ' + 2 * end + 'px) * ' + pct / 100 + ')';
    if (rails.fill) {
      bar.background = 'url("' + rails.fill + '") ' + from + ' / '
        + (along ? '100% ' + span : span + ' 100%') + ' no-repeat';
    }
    if (along) {
      rail.left = bar.left = 'calc(50% - ' + t / 2 + 'px)'; rail.width = bar.width = t + 'px';
      rail.top = end + 'px'; rail.height = span;
      bar.height = reach; bar[o === 'up' ? 'bottom' : 'top'] = end + 'px';
    } else {
      rail.top = bar.top = 'calc(50% - ' + t / 2 + 'px)'; rail.height = bar.height = t + 'px';
      rail.left = end + 'px'; rail.width = span;
      bar.width = reach; bar[o === 'right' ? 'left' : 'right'] = end + 'px';
    }
    var kids = [h('div', { key: 'r', style: rail }), h('div', { key: 'v', style: bar })];
    if (s) {
      // The kit's own thumb for the scheme, where the system carries it: its
      // circle is 65% of the thumb's box, with a shadow round it, as the
      // panel draws it. Without it, a circle of that size in the color.
      var art = kind === 'slider' && P.kit && P.kit.thumb_art ? P.kit.thumb_art[L.scheme] : null;
      var dot = Math.round(s * (d.thumb_circle || 1));
      // A thumb need not be square: Shockwave's is 52 wide by 34 along.
      var sa = Number(d.thumb_height) || s;
      var tw = along ? s : sa, th = along ? sa : s;
      var thumb = art
        ? { position: 'absolute', width: tw + 'px', height: th + 'px',
            background: 'url("' + art + '") center / contain no-repeat' }
        : { position: 'absolute', width: tw + 'px', height: th + 'px',
            background: 'radial-gradient(circle, ' + paint(L.colors, d.thumb_color) + ' '
              + (dot / 2 - 0.5) + 'px, transparent ' + dot / 2 + 'px)' };
      var at = 'calc((100% - ' + sa + 'px) * ' + pct / 100 + ')';
      if (along) { thumb.left = 'calc(50% - ' + s / 2 + 'px)'; thumb[o === 'up' ? 'bottom' : 'top'] = at; }
      else { thumb.top = 'calc(50% - ' + s / 2 + 'px)'; thumb[o === 'right' ? 'left' : 'right'] = at; }
      kids.push(h('div', { key: 't', style: thumb }));
    }
    // A seed with a slider and no level (its series' `kinds` in the profile:
    // the design panel's among them) has no level to clone, and the build
    // refuses one there (gdl.spec
    // donors). So a Level is named where it is drawn, on the panel it is
    // drawn for - or, on a Page that lists no panels, on the system's own -
    // as a Slider is turned into a level where the seed has no slider.
    var panel = L.panel || (L.page && P.models && P.models[P.model]);
    var lacks = kind === 'level' && panel && panel.kinds && panel.kinds.level === false
      ? (props.name || 'Level') + ' is a Level, which the ' + (panel.model || P.model) + "'s seed cannot build"
        + (panel.kinds.slider ? ' - a Slider can' : '')
      : null;
    if (lacks) kids.push(problem(lacks, 'level'));
    var box = { position: 'relative', boxSizing: 'border-box', width: '100%', height: '100%' };
    return h('div', {
      className: 'xgdl xgdl-' + kind,
      style: lacks ? outlined(box, [lacks]) : box,
      'data-gdl': gdl({ kind: kind, name: props.name, id: idOf(props.id),
                        seed_id: props.__seed != null ? Number(props.__seed) : null,
                        fill: fill, border: props.border || d.border, orientation: o,
                        track: t, thumb: s || null,
                        // A level's filled part, which Build takes from the
                        // control - a clone's is its donor's scheme. A slider's
                        // is the template's one color in every scheme.
                        bar: kind === 'level' ? barColor : null,
                        thumb_height: s && Number(d.thumb_height) ? Number(d.thumb_height) : null,
                        does: props.does,
                        // One of a set the gap rule passes over: the right
                        // rail's volume group (a region's).
                        joined: kind === 'slider' ? props.joined || null : null })
    }, kids);
  }
  function Slider(props) { return track('slider', props); }
  function Level(props) { return track('level', props); }

  // -- Clock ----------------------------------------------------------------
  // format is date, time, datetime or a .NET date pattern. The sample is the
  // pattern drawn for 28 September 1960 at midnight, as GUI Designer draws it.
  var CLOCK_FORMATS = { date: 'MMMM d', time: 'h:mm tt', datetime: 'MMMM d, h:mm tt' };
  var CLOCK_WORDS = { MMMM: 'September', MMM: 'Sep', MM: '09', M: '9', dddd: 'Wednesday',
    ddd: 'Wed', dd: '28', d: '28', yyyy: '1960', yy: '60', HH: '00', H: '0', hh: '12',
    h: '12', mm: '00', m: '0', ss: '00', s: '0', tt: 'AM', t: 'A' };
  function clockSample(pattern) {
    return (pattern.match(/MMMM|MMM|MM|M|dddd|ddd|dd|d|yyyy|yy|HH|H|hh|h|mm|m|ss|s|tt|t|'[^']*'|./g) || [])
      .map(function (t) { return CLOCK_WORDS[t] || (t[0] === "'" ? t.slice(1, -1) : t); }).join('');
  }
  function Clock(props) {
    var L = useLook();
    var f = font(props, P.defaults.clock.type, L);
    var color = props.color || P.defaults.clock.color;
    var fmt = props.format || 'time';
    var sample = clockSample(CLOCK_FORMATS[fmt] || fmt);
    var align = props.align || 'left';
    // A seed with no date and time control (its series' `kinds`: Shockwave's
    // and Turbulence's 320s) has none to clone, and the build refuses one
    // there (gdl.spec donors), so a Clock is named on the panel it cannot be
    // built for.
    var panel = L.panel || (L.page && P.models && P.models[P.model]);
    var lacks = panel && panel.kinds && panel.kinds.datetime === false
      ? (props.name || 'Clock') + " is a date and time, which the " + (panel.model || P.model)
        + "'s seed cannot build"
      : null;
    return h('div', {
      className: 'xgdl xgdl-clock',
      style: { boxSizing: 'border-box', width: '100%', height: '100%', display: 'flex',
               alignItems: 'center', justifyContent: ALIGN[align] || 'flex-start',
               color: paint(L.colors, color), font: f.css },
      'data-gdl': gdl({ kind: 'datetime', name: props.name, color: color, size: f.size,
                        // Always: the spec's own default is center, so a
                        // left clock that said nothing built centered.
                        bold: f.bold, align: align, format: fmt })
    }, sample, lacks ? problem(lacks, 'clock') : null);
  }

  // -- PopupRegion: where a group's popups appear ---------------------------
  function PopupRegion(props) {
    var L = useLook();
    // Muted where the template has a secondary text color; Turbulence draws
    // all its text white and has none, which painted the region magenta.
    var muted = L.colors['text-secondary'] ? 'text-secondary' : 'text';
    return h('div', {
      className: 'xgdl xgdl-popupregion',
      style: { boxSizing: 'border-box', width: '100%', height: '100%', display: 'flex',
               alignItems: 'center', justifyContent: 'center',
               border: '2px dashed ' + paint(L.colors, muted),
               color: paint(L.colors, muted), font: font({}, 'body', L).css },
      'data-gdl': gdl({ kind: 'popup_ref', name: props.name, group: props.group, derived: props.derived || null })
    // A hub's region is always filled by a popup of its own the page derives
    // (Select a Source): its words would only show through it.
    }, props.__quiet ? null : 'Popups in ' + (props.group || '(no group)'));
  }

  KINDS = new Map([[Button, 'button'], [Label, 'label'], [Panel, 'panel'], [Line, 'line'], [ImageArt, 'image'],
                   [Slider, 'slider'], [Level, 'level'], [Clock, 'clock'], [PopupRegion, 'popupregion'],
                   [MainArea, 'mainarea'], [Rail, 'rail'], [Group, 'group'],
                   [Header, 'header'], [LeftRail, 'leftrail'], [Section, 'section'], [RightRail, 'rightrail'],
                   [Footer, 'footer'], [Center, 'center']]);
  var api = { Page: Page, MainArea: MainArea, Rail: Rail, Group: Group, Button: Button, Label: Label, Panel: Panel,
              Line: Line, Slider: Slider, Level: Level, Clock: Clock, PopupRegion: PopupRegion,
              profile: P };
  // Where the design panel's seed can clone a PBImage (gdl.designsys
  // components): no Shockwave seed has one.
  if (P.image_kind) api.Image = ImageArt;
  // The region frame's, where the template draws its bars (gdl.designsys
  // components): Afterburn's system has none.
  if (P.layout && P.layout.bars === 'controls') {
    Object.assign(api, { Header: Header, LeftRail: LeftRail, Section: Section, RightRail: RightRail, Footer: Footer,
                         Center: Center });
  }
  window[P.namespace] = Object.assign(window[P.namespace] || {}, api);
})();
