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
  function font(props, fallbackType) {
    var t = typeStyle(props.type) || typeStyle(fallbackType) || P.type[P.type.length - 1];
    var size = props.size != null ? Number(props.size) : t.pt;
    var bold = props.bold != null ? truthy(props.bold) : t.weight >= 600;
    return { size: size, bold: bold,
             css: (bold ? 700 : 400) + ' ' + px(size) + '/1.2 ' + P.font.stack };
  }
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
    // The background image is a page's: a popup is a card over one, and a
    // modal shows the page beneath.
    var image = kind === 'page' && P.backdrops ? P.backdrops[theme.id] : null;
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
      template: P.template, size: [w, ht], does: props.does
    });
    return h(Ctx.Provider, { value: { scheme: scheme, colors: colors } },
      h('div', { 'data-gdl': data, 'data-theme': theme.id, className: 'xgdl-page', style: style },
        props.children));
  }

  // -- MainArea: the template's own main region, for layout -----------------
  // Afterburn's is the squircle its background image draws. It paints
  // nothing and is not a control: its children are placed inside it, with
  // absolute positions relative to it or with flex and grid.
  function MainArea(props) {
    var m = (P.layout && P.layout.main) || [0, 0, P.size[0], P.size[1]];
    var style = Object.assign({ position: 'absolute', left: m[0] + 'px', top: m[1] + 'px',
                                width: m[2] + 'px', height: m[3] + 'px', boxSizing: 'border-box' },
                              props.style || {});
    return h('div', { className: 'xgdl-main', style: style }, props.children);
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
    function on() {
      return (primary ? fam[KIT.primary[scheme]] : fam[KIT.secondary[scheme]])
        || fam.sel || fam.red || fam.plain || fam.off || null;
    }
    if (look === 'on') return on();
    if (look === 'off') return fam.off || fam.gray || fam.plain || on();
    return fam[look] || null;
  }
  // How the variant draws its image, if it has one: the kit size, and where
  // the caption goes - `below` the icon, `indent`ed past it, or `none`.
  function imageOf(V, props, caption) {
    if (V.kit) return { kit: V.kit, caption: V.caption, indent: V.indent, icon: props.icon || V.icon };
    if (props.icon && V.with_icon) {
      var W = V.with_icon;
      return caption ? { kit: W.kit, caption: W.caption, indent: W.indent, icon: props.icon }
                     : { kit: W.bare, caption: 'none', icon: props.icon };
    }
    return null;
  }
  // The caption as the panel draws it: the kit leaves the label room below or
  // beside the icon, and the template's own buttons reach it with line breaks
  // or leading spaces in the caption itself.
  function placed(img, text) {
    if (!img || text == null) return text;
    if (img.caption === 'none') return '';
    if (img.caption === 'below') return text ? '\r\n\r\n' + text : text;
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
    var f = font(props, P.defaults.button.type);
    var b = P.borders[now.border];
    var align = props.align || (img && img.caption === 'indent' ? 'left' : V.align) || 'center';
    var art = now.image && KIT && KIT.art ? KIT.art[now.image] : null;
    var style = {
      boxSizing: 'border-box', width: '100%', height: '100%',
      minWidth: P.touch + 'px', minHeight: P.touch + 'px',
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
        states: states, press: props.press, nav: props.nav, does: props.does,
        missing_icon: missing.length ? missing : null
      })
    };
    if (props.nav) attrs.href = navHref(props.nav); else attrs.type = 'button';
    attrs.onPointerDown = function () { held[1](true); };
    attrs.onPointerUp = attrs.onPointerLeave = attrs.onPointerCancel = function () { held[1](false); };
    var label = shown.text != null ? shown.text : text;
    if (missing.length && !label) label = '[' + missing[0] + ']';
    return h(props.nav ? 'a' : 'button', attrs, label);
  }

  // -- Label ----------------------------------------------------------------
  function Label(props) {
    var L = useLook();
    var f = font(props, P.defaults.label.type);
    var color = props.color || P.defaults.label.color;
    var align = props.align || 'left';
    return h('div', {
      className: 'xgdl xgdl-label',
      style: {
        boxSizing: 'border-box', width: '100%', height: '100%', display: 'flex',
        alignItems: 'center', justifyContent: ALIGN[align] || 'flex-start',
        textAlign: align, whiteSpace: 'pre-line', color: paint(L.colors, color), font: f.css
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
                        track: t, thumb: s || null, does: props.does })
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
    var f = font(props, P.defaults.clock.type);
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
    return h('div', {
      className: 'xgdl xgdl-popupregion',
      style: { boxSizing: 'border-box', width: '100%', height: '100%', display: 'flex',
               alignItems: 'center', justifyContent: 'center',
               border: '2px dashed ' + paint(L.colors, 'text-secondary'),
               color: paint(L.colors, 'text-secondary'), font: font({}, 'body').css },
      'data-gdl': gdl({ kind: 'popup_ref', name: props.name, group: props.group })
    }, 'Popups in ' + (props.group || '(no group)'));
  }

  var api = { Page: Page, MainArea: MainArea, Button: Button, Label: Label, Panel: Panel, Line: Line,
              Slider: Slider, Level: Level, Clock: Clock, PopupRegion: PopupRegion,
              profile: P };
  window[P.namespace] = Object.assign(window[P.namespace] || {}, api);
})();
