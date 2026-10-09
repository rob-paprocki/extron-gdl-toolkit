/* @ds-bundle: __HEADER__ */
/*
 * Extron touch-panel components for Claude Design - one template's look.
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
  function truthy(v) { return v === true || v === 'true' || v === 'yes' || v === '1'; }

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
    if (keep) {
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
  // its rail; a line of text at least one line tall.
  function needs(it, L) {
    var T = L.panel, p = it.props || {};
    if (it.kind === 'button') {
      var V = P.buttons[p.variant] || P.buttons[P.defaults.button.variant];
      var f = font(p, P.defaults.button.type, L);
      var words_ = [textOf(p.children, p.text)];
      (list(p.states) || []).forEach(function (s) { if (s && s.text) words_.push(s.text); });
      var img = imageOf(V, p, words_[0]);
      // As drawn: an indented caption carries the spaces that clear its icon.
      var wide = Math.max.apply(null, words_.map(function (t) {
        return textWidth(img && img.caption === 'indent' ? placed(img, t) : t, f.css);
      }));
      var lines = img && img.caption === 'below' && words_[0] ? (img.breaks || 2) + 1 : 1;
      var tall = words_[0] ? lines * lineHeight(f.size) + 4 : 0;
      return [Math.max(T.touch, Math.ceil(wide + (img ? 8 : 24))), Math.max(T.touch, tall)];
    }
    if (it.kind === 'slider') return [T.touch, T.touch];
    if (it.kind === 'group' && truthy(p.joined)) {
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
  function asLevel(it, r, axis, T, key) {
    var p = it.props || {};
    var name = p.name || 'Slider';
    var t = T.touch, g = T.gap;
    var along = axis === 'row' ? r[2] : r[3];
    if (along < 2 * t + 2 * g + 8) return { els: [], problems: [name + ' cannot fit a level with Up and Down on a ' + T.model] };
    var up = axis === 'row' ? [r[0] + r[2] - t, r[1] + (r[3] - t) / 2, t, t] : [r[0] + (r[2] - t) / 2, r[1], t, t];
    var down = axis === 'row' ? [r[0], r[1] + (r[3] - t) / 2, t, t] : [r[0] + (r[2] - t) / 2, r[1] + r[3] - t, t, t];
    var lv = axis === 'row' ? [r[0] + t + g, r[1], r[2] - 2 * (t + g), r[3]] : [r[0], r[1] + t + g, r[2], r[3] - 2 * (t + g)];
    function btn(suffix, caption, verb, rect) {
      return h('div', { key: key + suffix, style: cell(rect) },
               h(Button, { name: name + ' ' + suffix, derived: true, text: caption,
                           does: verb + ' ' + name + ' one step.' }));
    }
    var level = Object.assign({}, p, { orientation: axis === 'row' ? 'right' : 'up', fromSlider: true });
    return { els: [btn('Down', '-', 'Lowers', down), h('div', { key: key + 'level', style: cell(lv) }, h(Level, level)),
                   btn('Up', '+', 'Raises', up)], problems: [] };
  }
  // Tiers A and B, and the panel the canvas was drawn for: every child at its
  // own design rect, mapped by the frame's scale, then grown about its centre
  // to what it needs on this panel.
  function scaleLayout(items, D, T, L, frame) {
    var f = fit(D, frame);
    var els = [], probs = [];
    items.forEach(function (it, i) {
      if (!it.rect || it.kind === 'mainarea' || it.kind === 'rail') {
        els.push(it.kind === 'mainarea' || it.kind === 'rail'
          ? React.cloneElement(it.host, { key: 'f' + i, style: { display: 'contents' } }) : it.host);
        return;
      }
      var r = [f.x - frame[0] + it.rect[0] * f.s, f.y - frame[1] + it.rect[1] * f.s, it.rect[2] * f.s, it.rect[3] * f.s];
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
        var lv = asLevel(it, r, it.rect[2] > it.rect[3] ? 'row' : 'column', T, 's' + i);
        els = els.concat(lv.els);
        probs = probs.concat(lv.problems);
        return;
      }
      if (it.kind === 'group') {
        els.push(React.cloneElement(it.host, { key: 'g' + i, style: cell(r) },
                   React.cloneElement(it.comp, { __box: [Math.round(r[2]), Math.round(r[3])], __k: f.s })));
        return;
      }
      els.push(placeHost(it.host, grow(r, needs(it, L), hasArt(it)), 'c' + i));
    });
    return { els: els, problems: probs, k: f.s };
  }
  // Tier C: positions scaled by a quarter cannot keep 14 pt lines apart, so
  // the frame's children reflow - rows in design order, each control at what
  // it needs, rows centred - and a panel card behind a set of them is drawn
  // behind where they land. What does not fit is a problem, never dropped.
  function flowLayout(items, D, T, L, frame, where) {
    var f = fit(D, frame), k = f.s;
    var pad = T.gap, gap = T.gap, tight = 2;
    var W = frame[2] - 2 * pad, els = [], probs = [];
    var cards = [], flow = [];
    items.forEach(function (it, i) {
      it.i = i;
      if (!it.rect || it.kind === 'mainarea' || it.kind === 'rail') {
        els.push(it.kind === 'mainarea' || it.kind === 'rail'
          ? React.cloneElement(it.host, { key: 'f' + i, style: { display: 'contents' } }) : it.host);
      } else if (it.kind === 'box') {
        probs.push('a plain container in ' + where + ' cannot reflow on a ' + T.model + ' - use a Group');
      } else if (it.kind === 'panel') {
        cards.push(it);
      } else {
        flow.push(it);
      }
    });
    flow.sort(function (a, b) { return (a.rect[1] - b.rect[1]) || (a.rect[0] - b.rect[0]); });
    // Rows: a control joins the row above while its middle is inside it.
    var rows = [];
    flow.forEach(function (it) {
      var mid = it.rect[1] + it.rect[3] / 2;
      var row = rows[rows.length - 1];
      if (row && mid >= row.top && mid <= row.bottom) { row.items.push(it); row.bottom = Math.max(row.bottom, it.rect[1] + it.rect[3]); }
      else rows.push({ top: it.rect[1], bottom: it.rect[1] + it.rect[3], items: [it] });
    });
    // Sizes on this panel, then rows that are too wide wrap.
    var laid = [];
    rows.forEach(function (row) {
      row.items.sort(function (a, b) { return a.rect[0] - b.rect[0]; });
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
        } else if (it.kind === 'slider') {
          w = Math.min(W, Math.max(it.rect[2] * k, 3 * T.touch)); ht = T.touch;
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
        w = Math.ceil(w); ht = Math.ceil(ht);
        line.push({ it: it, w: w, h: ht });
      });
      if (line.length) laid.push(line);
    });
    function touchy(line) { return line.some(function (c) { return c.it.kind === 'button' || c.it.kind === 'slider'; }); }
    var total = 0;
    laid.forEach(function (line, n) {
      line.h = Math.max.apply(null, line.map(function (c) { return c.h; }));
      line.gap = n ? (touchy(line) || touchy(laid[n - 1]) ? gap : tight) : 0;
      total += line.h + line.gap;
    });
    if (total > frame[3] - 2 * tight) {
      probs.push(where + ' needs ' + Math.round(total) + ' px of a ' + T.model + "'s " + frame[3] + ' - it does not fit');
    }
    var y = Math.round(Math.max(tight, (frame[3] - total) / 2));
    var placed = {};
    laid.forEach(function (line) {
      y += line.gap;
      var wsum = line.reduce(function (s, c) { return s + c.w; }, 0) + gap * (line.length - 1);
      var x = Math.round((frame[2] - wsum) / 2);
      line.forEach(function (c) {
        var r = [x, y + Math.round((line.h - c.h) / 2), c.w, c.h];
        placed[c.it.i] = r;
        if (c.it.kind === 'slider' && T.kinds && T.kinds.slider === false) {
          var lv = asLevel(c.it, r, 'row', T, 's' + c.it.i);
          els = els.concat(lv.els);
          probs = probs.concat(lv.problems);
        } else if (c.it.kind === 'group') {
          els.push(React.cloneElement(c.it.host, { key: 'g' + c.it.i, style: cell(r) },
                     React.cloneElement(c.it.comp, { __box: [c.w, c.h], __k: k })));
        } else {
          els.push(placeHost(c.it.host, r, 'c' + c.it.i));
        }
        x += c.w + gap;
      });
      y += line.h;
    });
    // A card goes behind the controls it was drawn behind, wherever they land.
    var back = [];
    cards.forEach(function (card) {
      var c = card.rect, box = null;
      flow.forEach(function (it) {
        var r = it.rect;
        if (r[0] >= c[0] && r[1] >= c[1] && r[0] + r[2] <= c[0] + c[2] && r[1] + r[3] <= c[1] + c[3] && placed[it.i]) {
          var q = placed[it.i];
          box = box ? [Math.min(box[0], q[0]), Math.min(box[1], q[1]), Math.max(box[2], q[0] + q[2]), Math.max(box[3], q[1] + q[3])]
                    : [q[0], q[1], q[0] + q[2], q[1] + q[3]];
        }
      });
      var r = box ? [Math.max(0, box[0] - pad), Math.max(0, box[1] - pad),
                     Math.min(frame[2], box[2] + pad) - Math.max(0, box[0] - pad),
                     Math.min(frame[3], box[3] + pad) - Math.max(0, box[1] - pad)]
                  : [(frame[2] - c[2] * k) / 2, (frame[3] - c[3] * k) / 2, c[2] * k, c[3] * k];
      back.push(placeHost(card.host, r, 'card' + card.i));
    });
    return { els: back.concat(els), problems: probs, k: k };
  }
  function layout(items, D, frame, L, where) {
    var flow = L.panel.tier === 'C' && L.model !== L.designModel;
    return flow ? flowLayout(items, D, L.panel, L, frame, where) : scaleLayout(items, D, L.panel, L, frame);
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
    var asked = listed.length || props.preview || forcedPanel();
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
    return h(Ctx.Provider, { value: { scheme: scheme, colors: colors } },
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
    if (!full) {
      // A popup shows in a region of the main area, so it scales as that does.
      var sm = fit(D.main, T.main).s;
      tw = Math.round(dw * sm); th = Math.round(dh * sm);
    }
    // At the page's own scale from the start: needs() measures the page's own
    // children - a modal's title and steps - at this type before layout ends.
    var L = { scheme: scheme, colors: colors, aware: true, panel: T, design: D, model: model,
              designModel: designModel, tier: T.tier, k: fit([0, 0, dw, dh], [0, 0, tw, th]).s };
    var out = layout(itemsOf(props.children, [dw, dh]), [0, 0, dw, dh], [0, 0, tw, th], L, props.name || 'the page');
    L.k = out.k;
    problems = problems.concat(out.problems);
    var bgArt = kind === 'page' ? (T.backgrounds || {})[theme.id] || null : null;
    var image = bgArt && P.backdrops ? P.backdrops[T.series + '|' + theme.id] : null;
    var bg = kind === 'modal' ? null : props.background || P.defaults.page.background;
    var style = {
      position: 'relative', boxSizing: 'border-box', overflow: 'hidden',
      width: tw + 'px', height: th + 'px',
      background: kind === 'modal'
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
      kind: kind === 'page' ? 'page' : 'popup', modal: kind === 'modal' || null,
      name: props.name, group: props.group, start: truthy(props.start) || null,
      reached_by: props.reachedBy, background: bg, scheme: scheme, theme: theme.id,
      background_image: bgArt ? bgArt.image : null, background_file: bgArt ? bgArt.file : null,
      template: P.template, size: [tw, th], does: props.does,
      panel: model, panels: listed.length ? listed : [designModel], tier: T.tier, seed: T.seed,
      borders: T.borders && Object.keys(T.borders).length ? T.borders : null,
      derived: true
    });
    return h(Ctx.Provider, { value: L },
      h('div', { 'data-gdl': data, 'data-theme': theme.id, 'data-panel': model, className: 'xgdl-page',
                 style: outlined(style, problems) },
        out.els, problems.map(problem)));
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
      var out = layout(itemsOf(props.children, [D[2], D[3]]), [0, 0, D[2], D[3]], [0, 0, T[2], T[3]], L,
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
        var n = needs(it, Lk);
        if (p.variant === 'icon' || P.buttons[p.variant] && P.buttons[p.variant].kit && !textOf(p.children, p.text)) {
          var sq = Math.max(t, Math.round(64 * k));
          slots.push({ it: it, i: i, role: 'host', along: sq, cross: sq });
        } else {
          var designed = it.rect ? (col ? it.rect[3] : it.rect[2]) * k : 64 * k;
          slots.push({ it: it, i: i, role: 'host', along: Math.max(col ? n[1] : n[0], designed),
                       cross: Math.max(size, col ? n[0] : n[1]) });
        }
      } else if (it.kind === 'label' || it.kind === 'clock') {
        var g = font(p, it.kind === 'clock' ? P.defaults.clock.type : P.defaults.label.type, Lk);
        var line = lineHeight(g.size) + 2;
        slots.push({ it: it, i: i, role: 'host',
                     along: col ? line : textWidth(textOf(p.children, p.text), g.css) + 8,
                     cross: col ? size : line });
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

  // -- Group: a set of like controls, laid out and paged for each panel ------
  // A wrapping grid of equal cells, `cap` to a row, in the Group's own box.
  // On each panel every cell is as big as its largest member needs (touch
  // minimum, caption at the panel's type), and then, by tier: A - in place,
  // or, if they do not fit, its pages as popups in its box with Previous and
  // Next; B - a popup group in its box always (the region the program shows
  // it in); C - one button that opens its pages, each a page of its own with
  // Back. Every control keeps its name; what cannot fit even so is named.
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
  function Group(props) {
    var L = useLook();
    var items = itemsOf(props.children);
    var title = props.title || props.name || 'Group';
    var cap = Number(props.cap) || 4;
    var cellD = cellsOf(props, items);
    var gapD = props.gap != null ? Number(props.gap) : 49;
    var joined = truthy(props.joined);
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
    var problems = loose.slice();
    // A segmented control is one row of touching segments on every panel:
    // paged, or split into pages, it would no longer be one control.
    if (joined) {
      var JW = Math.max(props.__box[0], n * cw), JH = Math.max(props.__box[1], ch);
      var jr = gridPlace(n, n, cw, ch, 0, JW, JH);
      return h('div', { className: 'xgdl-group',
                        style: { position: 'absolute', left: Math.round((props.__box[0] - JW) / 2) + 'px',
                                 top: Math.round((props.__box[1] - JH) / 2) + 'px', width: JW + 'px', height: JH + 'px' } },
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
    var perRow = Math.max(1, Math.min(cap, Math.floor((W + g + 2) / (cw + g))));
    var rows = Math.max(1, Math.floor((H + g + 2) / (ch + g)));
    W = Math.max(W, perRow * cw + (perRow - 1) * g);
    var popup = L.tier === 'B' && L.model !== L.designModel;
    var root = { position: 'absolute', left: Math.round((bx[0] - W) / 2) + 'px', top: Math.round((bx[1] - H) / 2) + 'px',
                 width: W + 'px', height: H + 'px' };
    if (n <= perRow * rows && !popup) {
      var at = gridPlace(n, perRow, cw, ch, g, W, H);
      return h('div', { className: 'xgdl-group', style: outlined(root, problems) },
               items.map(function (it, i) { return member(it, at[i], 'c' + i); }).concat(problems.map(problem)));
    }
    var fits = n <= perRow * rows;
    var avail = fits ? rows : Math.floor((H - nav) / (ch + g));
    var perPage = perRow * avail;
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
      var spots2 = gridPlace(mine2.length, perRow, cw, ch, g, W, count > 1 ? H - nav - g : H, top);
      var kids2 = mine2.map(function (it, j) { return member(it, spots2[j], 'p' + pi + 'c' + j); });
      (function (p0) {
        var y = H - nav, right = W;
        if (p0 < count - 1) {
          var wn = navW('Next');
          kids2.push(navButton('Next', 'Next', partName(p0 + 1), function () { shown[1](p0 + 1); },
                               [right - wn, y, wn, nav], 'next' + p0));
          right -= wn + g;
        }
        if (p0 > 0) {
          var wp = navW('Previous');
          kids2.push(navButton('Previous', 'Previous', partName(p0 - 1), function () { shown[1](p0 - 1); },
                               [0, y, wp, nav], 'prev' + p0));
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
  function imageOf(V, props, caption) {
    if (V.kit) return { kit: V.kit, caption: V.caption, indent: V.indent, breaks: V.breaks,
                        icon: props.icon || V.icon };
    if (props.icon && V.with_icon) {
      var W = V.with_icon;
      return caption ? { kit: W.kit, caption: W.caption, indent: W.indent, breaks: W.breaks, icon: props.icon }
                     : { kit: W.bare, caption: 'none', icon: props.icon };
    }
    return null;
  }
  // The caption as the panel draws it: the kit leaves the label room below or
  // beside the icon, and the template's own buttons reach it with line breaks
  // or leading spaces in the caption itself - two breaks unless the variant
  // says (Mach's 150 px source tiles take three, as its seed's Camera 1 does).
  function placed(img, text) {
    if (!img || text == null) return text;
    if (img.caption === 'none') return '';
    if (img.caption === 'below') return text ? new Array((img.breaks || 2) + 1).join('\r\n') + text : text;
    if (img.caption === 'indent') return text ? new Array((img.indent || 0) + 1).join(' ') + text : text;
    return text;
  }

  // -- Button ---------------------------------------------------------------
  function Button(props) {
    var L = useLook();
    var variant = P.buttons[props.variant] ? props.variant : P.defaults.button.variant;
    var V = P.buttons[variant];
    var caption = textOf(props.children, props.text);
    var img = imageOf(V, props, caption);
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
        if (s.text != null) s.text = placed(img, s.text);
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
    var b = P.borders[now.border];
    // An indented caption reads from the left unless the variant says
    // otherwise: Shockwave's centers it, pushed right past the icon.
    var align = props.align || V.align || (img && img.caption === 'indent' ? 'left' : null) || 'center';
    var art = now.image && KIT && KIT.art ? KIT.art[now.image] : null;
    var style = {
      boxSizing: 'border-box', width: '100%', height: '100%',
      // The touch minimum; on a panel, the cell the frame gave it already is,
      // unless a plain container scales it (css).
      minWidth: (L.aware ? L.panel.touch / (L.css || 1) : P.touch) + 'px',
      minHeight: (L.aware ? L.panel.touch / (L.css || 1) : P.touch) + 'px',
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
        kind: 'button', name: props.name, id: props.id != null ? Number(props.id) : null,
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
    var color = props.color || P.defaults.label.color;
    var align = props.align || 'left';
    return h('div', {
      className: 'xgdl xgdl-label',
      style: {
        boxSizing: 'border-box', width: '100%', height: '100%', display: 'flex',
        alignItems: 'center', justifyContent: ALIGN[align] || 'flex-start',
        textAlign: align, whiteSpace: 'pre-line', color: paint(L.colors, color), font: f.css,
        // At least a line on this panel, as a Button is at least its touch
        // size - from inside, where a scaled container laid it out.
        minHeight: L.aware ? (lineHeight(f.size) + 2) / (L.css || 1) + 'px' : undefined
      },
      'data-gdl': gdl({ kind: 'label', name: props.name, id: props.id != null ? Number(props.id) : null,
                        text: textOf(props.children, props.text), color: color, size: f.size,
                        bold: f.bold, align: align, does: props.does })
    }, textOf(props.children, props.text));
  }

  // -- Panel: a filled shape behind other controls --------------------------
  function Panel(props) {
    var L = useLook();
    var fill = props.fill || P.defaults.panel.fill;
    var border = props.border || P.defaults.panel.border;
    var stroke = props.stroke || P.defaults.panel.stroke;
    var b = P.borders[border];
    return h('div', {
      className: 'xgdl xgdl-panel',
      style: { boxSizing: 'border-box', width: '100%', height: '100%',
               background: paint(L.colors, fill), border: edge(b, L.colors, stroke),
               borderRadius: radius(b) },
      'data-gdl': gdl({ kind: 'panel', name: props.name, fill: fill, stroke: stroke,
                        border: border })
    });
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
    var from = along ? (o === 'up' ? 'bottom' : 'top') : (o === 'right' ? 'left' : 'right');
    var rail = { position: 'absolute', borderRadius: t / 2 + 'px',
                 background: rails.track ? 'url("' + rails.track + '") center / 100% 100% no-repeat'
                                         : paint(L.colors, fill) };
    var bar = { position: 'absolute', borderRadius: t / 2 + 'px', background: paint(L.colors, d.value) };
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
    return h('div', {
      className: 'xgdl xgdl-' + kind,
      style: { position: 'relative', boxSizing: 'border-box', width: '100%', height: '100%' },
      'data-gdl': gdl({ kind: kind, name: props.name, id: props.id != null ? Number(props.id) : null,
                        fill: fill, border: props.border || d.border, orientation: o,
                        track: t, thumb: s || null,
                        // A level's filled part, which Build takes from the
                        // control - a clone's is its donor's scheme. A slider's
                        // is the template's one color in every scheme.
                        bar: kind === 'level' ? d.value : null,
                        thumb_height: s && Number(d.thumb_height) ? Number(d.thumb_height) : null,
                        does: props.does })
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
    return h('div', {
      className: 'xgdl xgdl-clock',
      style: { boxSizing: 'border-box', width: '100%', height: '100%', display: 'flex',
               alignItems: 'center', justifyContent: ALIGN[align] || 'flex-start',
               color: paint(L.colors, color), font: f.css },
      'data-gdl': gdl({ kind: 'datetime', name: props.name, color: color, size: f.size,
                        // Always: the spec's own default is center, so a
                        // left clock that said nothing built centered.
                        bold: f.bold, align: align, format: fmt })
    }, sample);
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
      'data-gdl': gdl({ kind: 'popup_ref', name: props.name, group: props.group })
    }, 'Popups in ' + (props.group || '(no group)'));
  }

  KINDS = new Map([[Button, 'button'], [Label, 'label'], [Panel, 'panel'], [Line, 'line'],
                   [Slider, 'slider'], [Level, 'level'], [Clock, 'clock'], [PopupRegion, 'popupregion'],
                   [MainArea, 'mainarea'], [Rail, 'rail'], [Group, 'group']]);
  var api = { Page: Page, MainArea: MainArea, Rail: Rail, Group: Group, Button: Button, Label: Label, Panel: Panel,
              Line: Line, Slider: Slider, Level: Level, Clock: Clock, PopupRegion: PopupRegion,
              profile: P };
  window[P.namespace] = Object.assign(window[P.namespace] || {}, api);
})();
