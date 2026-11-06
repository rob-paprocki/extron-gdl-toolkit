"""The synthetic fixture's spec and art: a many-page panel with no client in it.

    python tests/data/synthetic/make_synthetic.py          # writes synthetic.json
    python tests/data/synthetic/make_synthetic.py --art    # and art/*.png (Pillow)

The render baseline used to be measurable only against a client's project and
GUI Designer's snapshot exports of it, since deleted from the repo
(docs/history.md). This is its replacement: the same reach - pages and popups of every size the client's
has, every control type the renderer scores, text drawn live at many sizes,
weights, alignments and widths - built on the Afterburn 1035 seed by
powershell/New-GdlPanel.ps1, so it is the toolkit's own work end to end, in
generic words and in pictures drawn here. tests/data/synthetic/README.md says
what is in it and how its snapshots were exported.

The JSON is what is built and committed; this is how it was written, and
tests/test_synthetic.py holds the two together. Its art is drawn once and
pinned (tools/public_sync.py BINARY_OK): re-drawing it with another Pillow can
change the bytes, which would need a rebuild and new snapshots.
"""
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))

# The Afterburn template's own colors (gdl/designsys/afterburn.json): the
# template's chrome, so the 6-color cap (GUI Design Standards p.49) counts
# only the five added below.
TEMPLATE = {
    'page': '#242634', 'raised': '#37394E', 'text': '#FFFFFF', 'muted': '#BABCCE',
    'subtle': '#767789', 'ground': '#414459', 'shape': '#6A6E89', 'accent': '#D69B61',
    'accent2': '#626ACF', 'alert': '#D32929', 'black': '#000000',
}
OWN = {'blue': '#3D8BFD', 'green': '#2E9E5B', 'yellow': '#F2C94C', 'deep': '#12131C',
       'paper': '#DCDCDC'}
# Translucent fills, over the stripes: a snapshot blends them in light, GDI+'s
# gamma 2.2 (docs/render-fidelity.md finding 2).
ALPHA = {'accent25': '#40D69B61', 'accent50': '#80D69B61', 'accent75': '#C0D69B61',
         'white20': '#33FFFFFF', 'black50': '#80000000', 'blue60': '#993D8BFD'}

W, H = 1280, 800


def label(name, rect, text, **kw):
    return dict(kind='label', name=name, rect=list(rect), text=text, **kw)


def button(name, rect, text=None, **kw):
    c = dict(kind='button', name=name, rect=list(rect), **kw)
    if text is not None:
        c['text'] = text
    return c


def title(text, w=W, x=40, y=20, h=60, size=28):
    return label('Title', (x, y, w - 2 * x, h), text, size=size, bold=True, align='left')


# -- pages -----------------------------------------------------------------
def start():
    return {'name': 'Start', 'number': 1000, 'background_image': 'backdrop.png',
            'controls': [
                label('Heading', (80, 60, 1120, 110), 'Synthetic Panel', size=48, bold=True),
                label('Subheading', (80, 170, 1120, 50), 'A test project in generic words',
                      size=20, color='muted'),
                {'kind': 'popup_ref', 'name': 'NoteRef', 'rect': [340, 250, 600, 150],
                 'group': 'Note'},
                button('Begin', (540, 440, 200, 80), 'Begin', size=24, fill='accent',
                       border='capsule', color='deep', on='raised'),
                {'kind': 'datetime', 'name': 'Clock', 'rect': [415, 590, 450, 70],
                 'format': 'time', 'size': 32},
                {'kind': 'datetime', 'name': 'Date', 'rect': [340, 670, 600, 50],
                 'format': 'dddd, MMMM d, yyyy', 'size': 18, 'color': 'muted'},
            ]}


NAV = ['Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon', 'Zeta', 'Eta', 'Theta']


def main_page():
    return {'name': 'Main', 'number': 2000, 'controls': [
        {'kind': 'panel', 'name': 'Rail', 'rect': [0, 0, 365, 800], 'fill': 'raised',
         'border': 'rect-thin'},
        label('RailTitle', (24, 20, 317, 60), 'Main', size=28, bold=True, align='left'),
        {'stack': {'rect': [24, 100, 317, 580], 'count': 8, 'gap': 12, 'kind': 'button',
                   'fill': 'page', 'border': 'afterburn', 'stroke': 'muted', 'size': 20,
                   'align': 'left', 'items': [{'name': f'Nav{n}', 'text': n} for n in NAV]}},
        {'kind': 'datetime', 'name': 'Clock', 'rect': [24, 700, 317, 70], 'format': 'h:mm tt',
         'size': 24, 'align': 'left'},
        {'kind': 'popup_ref', 'name': 'ContentRef', 'rect': [365, 0, 915, 800],
         'group': 'Content'},
        {'kind': 'popup_ref', 'name': 'LevelRef', 'rect': [1120, 24, 136, 496], 'group': 'Level'},
        {'kind': 'popup_ref', 'name': 'SingleRef', 'rect': [600, 600, 400, 160],
         'popup': 'Single'},
    ]}


def matrix_page():
    return {'name': 'Matrix', 'number': 2100, 'controls': [
        title('Matrix'),
        label('Hint', (40, 84, 1200, 40), 'Each row routes one input to the outputs above it',
              size=16, color='muted', align='left'),
        {'kind': 'popup_ref', 'name': 'WideRef', 'rect': [190, 140, 900, 530], 'group': 'Wide'},
        {'grid': {'rect': [190, 690, 900, 80], 'cols': 3, 'gap': 24, 'kind': 'button',
                  'fill': 'raised', 'border': 'afterburn', 'stroke': 'shape', 'size': 20,
                  'items': [{'name': 'Clear', 'text': 'Clear'},
                            {'name': 'Undo', 'text': 'Undo'},
                            {'name': 'Apply', 'text': 'Apply', 'fill': 'accent', 'color': 'deep',
                             'on': 'raised'}]}},
    ]}


SIZES = (14, 16, 18, 20, 24, 28, 32, 40)


def type_sizes():
    """Open Sans regular, bold and italic at each size, one line each."""
    rows, top = [], 100
    for pt in SIZES:
        h = round(pt * 1.375 * 1.45) + 8
        x = 40
        for style, w, kw in (('Regular', 460, {}), ('Bold', 380, {'bold': True}),
                             ('Italic', 340, {'italic': True})):
            rows.append(label(f'{style}{pt}', (x, top, w, h), f'Type {pt} {style}', size=pt,
                              align='left', **kw))
            x += w + 10
        top += h + 4
    return {'name': 'Type Sizes', 'number': 3000, 'controls': [title('Type Sizes')] + rows}


def type_faces():
    """Arial, Arial Black and Open Sans Light beside Open Sans, on fills and off."""
    c = [title('Type Faces')]
    faces = (('Arial', 'Arial'), ('Black', 'Arial Black'), ('Light', 'Open Sans Light'),
             ('Sans', 'Open Sans'))
    for i, (tag, face) in enumerate(faces):
        x = 40 + i * 300
        c.append(label(f'{tag}Name', (x, 90, 280, 40), face, size=16, color='muted',
                       align='left'))
        top = 136
        for pt in (14, 18, 24, 28):
            h = round(pt * 1.375 * 1.45) + 6
            c.append(label(f'{tag}{pt}', (x, top, 280, h), f'Hamburg {pt}', size=pt,
                           font=face, align='left'))
            top += h + 2
        # The same words on an opaque fill: text over art, antialiased.
        c.append(label(f'{tag}OnFill', (x, top + 8, 280, 60), 'On a fill 18', size=18,
                       font=face, fill='raised', border='rounded'))
        c.append(label(f'{tag}Colored', (x, top + 76, 280, 60), 'Colored 20', size=20,
                       font=face, color=('accent', 'blue', 'yellow', 'green')[i]))
        c.append(label(f'{tag}Digits', (x, top + 144, 280, 50), '0123456789', size=22,
                       font=face, color='muted'))
        c.append(label(f'{tag}Word', (x, top + 200, 280, 50), 'Hamburgefons', size=18,
                       font=face, align='left'))
    c.append(label('Mixed', (40, 690, 1200, 80),
                   'Labels set in four faces, each at four sizes, on and off a fill',
                   size=20, color='muted'))
    return {'name': 'Type Faces', 'number': 3100, 'controls': c}


ALIGNS = ('top-left', 'top', 'top-right', 'left', 'center', 'right',
          'bottom-left', 'bottom', 'bottom-right')
WORDS = {'top-left': 'Top Left', 'top': 'Top', 'top-right': 'Top Right', 'left': 'Left',
         'center': 'Center', 'right': 'Right', 'bottom-left': 'Bottom Left',
         'bottom': 'Bottom', 'bottom-right': 'Bottom Right'}


def alignment():
    one = {'grid': {'rect': [40, 96, 1200, 330], 'cols': 3, 'rows': 3, 'gap': 12,
                    'kind': 'label', 'fill': 'raised', 'border': 'rounded', 'size': 20,
                    'items': [{'name': f'Fill{a}', 'text': WORDS[a], 'align': a} for a in ALIGNS]}}
    two = {'grid': {'rect': [40, 440, 1200, 330], 'cols': 3, 'rows': 3, 'gap': 12,
                    'kind': 'label', 'size': 18, 'color': 'muted',
                    'items': [{'name': f'Two{a}', 'text': f'{WORDS[a]}\nsecond line', 'align': a}
                              for a in ALIGNS]}}
    return {'name': 'Alignment', 'number': 3200, 'controls': [title('Alignment'), one, two]}


SENTENCE = 'The quick brown fox jumps over the lazy dog'


def wrapping():
    c = [title('Wrapping')]
    x = 40
    for w in (120, 200, 300, 480):
        c.append(label(f'Wrap{w}', (x, 96, w, 260), SENTENCE, size=18, fill='raised',
                       border='rect-thin', align='top-left'))
        x += w + 20
    c += [
        label('Breaks', (40, 370, 360, 150), 'First line\nSecond line\nThird line', size=20,
              align='left', fill='ground', border='rounded'),
        label('LongWord', (420, 370, 160, 150), 'Abcdefghijklmnopqrstuvwxyz', size=18,
              fill='ground', border='rounded'),
        label('Centered', (600, 370, 640, 150),
              'A centered paragraph of several lines that wraps inside its box', size=22,
              fill='ground', border='rounded'),
    ]
    # Bold captions on one line and on two, near their box's edge and far from it
    # (docs/render-fidelity.md section 8 asks for these).
    # Near is the regular's width at 20 pt (27.5 px), plus GDI+'s 1/6 em a side,
    # plus the 1/60 em a glyph emboldening adds: 185 + 9 + 6 for Program Level,
    # 231 + 9 + 7 for Conference Room, 66 + 9 + 2 for Level. Far is twice that.
    bold = [('Program Level', 204), ('Program Level', 408), ('Level\nOne', 84),
            ('Level\nOne', 168), ('Conference Room', 248), ('Conference Room', 496)]
    x, y = 40, 540
    for i, (text, w) in enumerate(bold):
        if x + w > W - 40:
            x, y = 40, y + 120
        c.append(label(f'Bold{i}', (x, y, w, 100), text, size=20, bold=True,
                       fill='raised', border='rounded'))
        x += w + 20
    return {'name': 'Wrapping', 'number': 3300, 'controls': c}


# Not 3D Gradient, which the seed defines: Build draws its fill as a gradient,
# so tests/verify_built.py finds the planned fill in none of its art and the
# build would not verify (docs/ROADMAP.md, the backlog).
BORDERS1 = ('rect', 'rect-thin', 'rounded', 'capsule', 'ellipse', 'rect-3d', 'rounded-3d',
            'capsule-3d')
BORDERS2 = ('afterburn', 'afterburn-flat', 'afterburn-14', 'afterburn-ellipse', 'capsule')


def buttons():
    c = [title('Buttons'),
         {'grid': {'rect': [40, 90, 1200, 90], 'cols': 8, 'gap': 12, 'kind': 'button',
                   'fill': 'raised', 'stroke': 'muted', 'size': 14,
                   'items': [{'name': f'B{b}', 'text': b.replace('-', ' '), 'border': b}
                             for b in BORDERS1]}},
         {'grid': {'rect': [40, 194, 1200, 90], 'cols': 5, 'gap': 16, 'kind': 'button',
                   'fill': 'accent', 'color': 'deep', 'size': 18, 'on': 'raised',
                   'items': [{'name': f'A{b}', 'text': b.replace('-', ' '), 'border': b}
                             for b in BORDERS2]}},
         # Translucent fills over a picture.
         {'kind': 'image', 'name': 'Stripes', 'rect': [40, 298, 1200, 110],
          'image': 'stripes.png', 'layout': 'stretch'},
         {'grid': {'rect': [60, 313, 1160, 80], 'cols': 6, 'gap': 16, 'kind': 'button',
                   'border': 'rounded', 'size': 18,
                   'items': [{'name': f'T{a}', 'text': a, 'fill': a} for a in ALPHA]}},
         # States: the panel draws state 0; the rest are Build's to rasterize.
         {'grid': {'rect': [40, 422, 1200, 90], 'cols': 5, 'gap': 16, 'kind': 'button',
                   'fill': 'raised', 'border': 'afterburn', 'stroke': 'shape', 'size': 18,
                   'items': [
                       {'name': 'OneState', 'text': 'One state', 'on': None},
                       {'name': 'TwoStates', 'text': 'Two states'},
                       {'name': 'ThreeStates', 'text': 'Three',
                        'states': ['Off', {'name': 'Ready', 'fill': 'green'},
                                   {'name': 'On', 'fill': 'accent'}]},
                       {'name': 'FourStates', 'text': 'Muted',
                        'states': [{'name': 'Muted', 'fill': 'alert'},
                                   {'name': 'Low', 'fill': 'ground', 'text': 'Low'},
                                   {'name': 'Mid', 'fill': 'shape', 'text': 'Mid'},
                                   {'name': 'High', 'fill': 'accent', 'text': 'High'}]},
                       {'name': 'PressFirst', 'text': 'Pressed', 'fill': 'accent2',
                        'on': 'blue'}]}},
         # Icons in the theme's icon font, and pictures of our own.
         {'grid': {'rect': [40, 526, 760, 100], 'cols': 6, 'gap': 16, 'kind': 'button',
                   'fill': 'raised', 'border': 'afterburn', 'size': 40,
                   'items': [{'name': n, 'icon': n} for n in
                             ('home', 'display', 'camera', 'pc', 'hdmi', 'doc_cam')]}},
         {'grid': {'rect': [816, 526, 424, 100], 'cols': 3, 'gap': 16, 'kind': 'button',
                   'fill': 'raised', 'border': 'afterburn',
                   'items': [{'name': 'PicA', 'image': 'glyph.png'},
                             {'name': 'PicB', 'image': 'glyph.png', 'fill': 'ground'},
                             {'name': 'PicC', 'states': [{'name': 'Off', 'image': 'glyph.png'},
                                                         {'name': 'On', 'image': 'glyph-on.png',
                                                          'fill': 'accent'}]}]}},
         # Captions Build bakes into the art (FlattenText).
         {'grid': {'rect': [40, 640, 1200, 130], 'cols': 4, 'gap': 16, 'kind': 'button',
                   'fill': 'ground', 'border': 'afterburn', 'stroke': 'muted', 'flatten': True,
                   'items': [{'name': 'Flat1', 'text': 'Flattened 16', 'size': 16},
                             {'name': 'Flat2', 'text': 'Flattened 24', 'size': 24, 'bold': True},
                             {'name': 'Flat3', 'text': 'Two lines\nflattened', 'size': 20},
                             {'name': 'Flat4', 'text': 'Arial flat', 'size': 22,
                              'font': 'Arial'}]}},
         ]
    return {'name': 'Buttons', 'number': 4000, 'controls': c}


def controls():
    c = [title('Controls'),
         # Sliders, each way up; the panel's value is parked at half travel.
         {'kind': 'slider', 'name': 'Up', 'rect': [40, 100, 60, 360], 'orientation': 'up',
          'fill': 'raised', 'track': 14},
         {'kind': 'slider', 'name': 'Down', 'rect': [120, 100, 60, 360], 'orientation': 'down',
          'fill': 'shape', 'track': 10},
         # A thumb of its own art. Not a rail of art too: on the Afterburn
         # seed's slider Build drew the rail's fill as the clone's #BABCCE bar,
         # not the fill picture (docs/ROADMAP.md, the backlog).
         {'kind': 'slider', 'name': 'Pictured', 'rect': [200, 100, 70, 360], 'orientation': 'up',
          'fill': 'ground', 'track': 24, 'thumb': 64, 'thumb_image': 'thumb.png'},
         {'kind': 'slider', 'name': 'Right', 'rect': [300, 100, 560, 60],
          'orientation': 'right', 'fill': 'raised', 'track': 12},
         {'kind': 'slider', 'name': 'Left', 'rect': [300, 180, 560, 60], 'orientation': 'left',
          'fill': 'ground', 'track': 20, 'thumb': 56},
         # Lines, of several weights and ways.
         # Two pixels, not one: a 1 px line across the middle of an even box
         # built half on each of two rows, at alpha 128 at most, which the
         # verifier reads as see-through.
         {'kind': 'line', 'name': 'Hair', 'rect': [300, 260, 560, 10], 'thickness': 2,
          'fill': 'muted', 'border': 'none'},
         {'kind': 'line', 'name': 'Rule', 'rect': [300, 280, 560, 10], 'thickness': 3,
          'fill': 'accent', 'border': 'none'},
         {'kind': 'line', 'name': 'Heavy', 'rect': [300, 300, 560, 16], 'thickness': 6,
          'fill': 'blue', 'border': 'none'},
         {'kind': 'line', 'name': 'Upright', 'rect': [300, 330, 20, 130], 'thickness': 2,
          'fill': 'muted', 'border': 'none', 'from': 'TopCenter', 'to': 'BottomCenter'},
         {'kind': 'line', 'name': 'Slant', 'rect': [340, 330, 240, 130], 'thickness': 3,
          'fill': 'yellow', 'border': 'none', 'from': 'TopLeft', 'to': 'BottomRight'},
         {'kind': 'line', 'name': 'Rise', 'rect': [600, 330, 260, 130], 'thickness': 2,
          'fill': 'green', 'border': 'none', 'from': 'BottomLeft', 'to': 'TopRight'},
         # Pictures fitted and stretched into a box of another shape.
         {'kind': 'image', 'name': 'Fitted', 'rect': [900, 100, 340, 160], 'image': 'pattern.png'},
         {'kind': 'image', 'name': 'Stretched', 'rect': [900, 280, 340, 180],
          'image': 'pattern.png', 'layout': 'stretch'},
         # Panels: a fill in each border, one translucent, one outlined only.
         {'grid': {'rect': [40, 490, 820, 120], 'cols': 5, 'gap': 16, 'kind': 'panel',
                   'items': [{'name': 'PanelRect', 'fill': 'ground', 'border': 'rect-thin'},
                             {'name': 'PanelRound', 'fill': 'raised', 'border': 'afterburn',
                              'stroke': 'shape'},
                             {'name': 'PanelPill', 'fill': 'accent2', 'border': 'capsule'},
                             {'name': 'PanelClear', 'fill': 'white20', 'border': 'rounded'},
                             {'name': 'PanelLine', 'fill': 'page', 'stroke': 'accent',
                              'border': 'afterburn'}]}},
         # Clocks in three patterns and three alignments.
         {'kind': 'datetime', 'name': 'TimeLeft', 'rect': [900, 490, 340, 50], 'format': 'time',
          'size': 20, 'align': 'left'},
         {'kind': 'datetime', 'name': 'DateRight', 'rect': [900, 550, 340, 50],
          'format': 'date', 'size': 20, 'align': 'right', 'color': 'muted'},
         {'kind': 'datetime', 'name': 'Stamp', 'rect': [900, 610, 340, 50],
          'format': 'datetime', 'size': 18, 'color': 'accent'},
         label('SliderNote', (40, 630, 820, 140),
               'Sliders up, down, with a thumb of their own, right and left; lines of two, '
               'three and six pixels; pictures fitted and stretched; five panels; three clocks',
               size=18, color='muted', align='top-left'),
         ]
    return {'name': 'Controls', 'number': 4100, 'controls': c}


def keys_page():
    return {'name': 'Keys', 'number': 5000, 'controls': [
        {'kind': 'panel', 'name': 'Side', 'rect': [0, 0, 285, 800], 'fill': 'raised',
         'border': 'rect-thin'},
        label('SideTitle', (24, 20, 237, 60), 'Keys', size=28, bold=True, align='left'),
        {'stack': {'rect': [24, 100, 237, 280], 'count': 3, 'gap': 16, 'kind': 'button',
                   'fill': 'page', 'border': 'afterburn', 'stroke': 'muted', 'size': 20,
                   'items': [{'name': 'Upper', 'text': 'Upper case'},
                             {'name': 'Lower', 'text': 'Lower case'},
                             {'name': 'ClearAll', 'text': 'Clear'}]}},
        {'kind': 'popup_ref', 'name': 'KeysRef', 'rect': [285, 0, 995, 800], 'group': 'Keys'},
    ]}


# -- popups ----------------------------------------------------------------
def content(name, number, controls):
    return {'name': name, 'number': number, 'group': 'Content', 'size': [915, 800],
            'controls': [title(name.split(' ', 1)[1], w=915, x=32, y=24, h=56)] + controls}


GREEK = ['Alpha', 'Beta', 'Gamma', 'Delta', 'Epsilon', 'Zeta', 'Eta', 'Theta']


def content_alpha():
    rows = 8
    return content('Content Alpha', 6000, [
        {'grid': {'rect': [32, 100, 300, 620], 'cols': 1, 'rows': rows, 'gap': 12,
                  'kind': 'label', 'size': 20, 'align': 'left',
                  'items': [{'name': f'Name{i}', 'text': f'Channel {i + 1:02d}'}
                            for i in range(rows)]}},
        {'grid': {'rect': [340, 100, 250, 620], 'cols': 1, 'rows': rows, 'gap': 12,
                  'kind': 'label', 'size': 16, 'color': 'muted', 'align': 'left',
                  'items': [{'name': f'State{i}', 'text': ('Ready', 'Idle', 'Busy', 'Offline')[i % 4]}
                            for i in range(rows)]}},
        {'grid': {'rect': [610, 100, 130, 620], 'cols': 1, 'rows': rows, 'gap': 12,
                  'kind': 'button', 'fill': 'raised', 'border': 'afterburn', 'stroke': 'shape',
                  'size': 16, 'items': [{'name': f'Set{i}', 'text': 'Set'} for i in range(rows)]}},
        {'grid': {'rect': [756, 100, 130, 620], 'cols': 1, 'rows': rows, 'gap': 12,
                  'kind': 'button', 'fill': 'ground', 'border': 'afterburn-flat', 'size': 16,
                  'items': [{'name': f'Reset{i}', 'text': 'Reset'} for i in range(rows)]}},
    ])


def content_beta():
    words = ['Input\nOne', 'Input\nTwo', 'Input\nThree', 'Input\nFour', 'Input\nFive',
             'Input\nSix', 'Input\nSeven', 'Input\nEight', 'Input\nNine']
    return content('Content Beta', 6010, [
        {'grid': {'rect': [32, 100, 851, 600], 'cols': 3, 'rows': 3, 'gap': 24, 'kind': 'button',
                  'fill': 'raised', 'border': 'afterburn', 'stroke': 'muted', 'size': 24,
                  'bold': True, 'items': [{'name': f'In{i}', 'text': t}
                                          for i, t in enumerate(words)]}},
        label('Footer', (32, 716, 851, 60), 'Two-line bold captions on raised keys', size=16,
              color='muted'),
    ])


def content_gamma():
    params = ['Address', 'Gateway', 'Subnet', 'Port', 'Protocol', 'Firmware', 'Serial', 'Uptime',
              'Model', 'Location', 'Contact', 'Status']
    values = ['10.0.0.20', '10.0.0.1', '255.255.255.0', '23', 'Telnet', '3.04.0001', 'A1B2C3D4',
              '12 days', 'Unit 100', 'Room 3', 'Desk', 'Online']
    out = []
    for col, (x0, tag) in enumerate(((32, 'L'), (480, 'R'))):
        out.append({'grid': {'rect': [x0, 100, 200, 660], 'cols': 1, 'rows': 12, 'gap': 6,
                             'kind': 'label', 'size': 16, 'color': 'muted', 'align': 'left',
                             'items': [{'name': f'{tag}Key{i}', 'text': p}
                                       for i, p in enumerate(params)]}})
        out.append({'grid': {'rect': [x0 + 200, 100, 220, 660], 'cols': 1, 'rows': 12, 'gap': 6,
                             'kind': 'label', 'size': 16, 'align': 'left',
                             'items': [{'name': f'{tag}Val{i}',
                                        'text': values[i] if col == 0 else values[i].upper()}
                                       for i in range(12)]}})
    return content('Content Gamma', 6020, out)


def content_delta():
    paras = [('Overview', 'This page holds headings and paragraphs, the kind of text a help '
                          'page or a status page carries, wrapped at the width of the popup.'),
             ('Details', 'Each paragraph is one label. The words break at spaces, and a line '
                         'that would run past the edge of its box goes on to the next one.'),
             ('Notes', 'Short lines, long lines, and lines in between. Numbers like 1280 by 800 '
                       'and 14 point appear here too.')]
    out, y = [], 100
    for i, (head, body) in enumerate(paras):
        out.append(label(f'Head{i}', (32, y, 851, 44), head, size=24, bold=True, align='left'))
        out.append(label(f'Body{i}', (32, y + 48, 851, 150), body, size=18, align='top-left',
                         color='muted' if i % 2 else 'text'))
        y += 210
    return content('Content Delta', 6030, out)


ICONS = ['home', 'display', 'camera', 'pc', 'hdmi', 'doc_cam', 'bluray', 'cable_tv',
         'make_call', 'end_call', 'mic_mute_2', 'speaker_mute_2']


def content_epsilon():
    out = []
    for row in range(2):
        names = ICONS[row * 6:(row + 1) * 6]
        y = 110 + row * 300
        out.append({'grid': {'name': f'IconRow{row}', 'rect': [32, y, 851, 150], 'cols': 6,
                             'gap': 20, 'kind': 'button',
                             'fill': 'raised', 'border': 'afterburn', 'size': 48,
                             'items': [{'name': f'Icon{n}', 'icon': n} for n in names]}})
        out.append({'grid': {'rect': [32, y + 160, 851, 44], 'cols': 6, 'gap': 20,
                             'kind': 'label', 'size': 14, 'color': 'muted',
                             'items': [{'name': f'IconLabel{n}', 'text': n.replace('_', ' ')}
                                       for n in names]}})
    return content('Content Epsilon', 6040, out)


def content_zeta():
    out = []
    for i in range(4):
        x = 60 + i * 210
        out.append(label(f'ZName{i}', (x - 20, 100, 140, 40), f'Zone {i + 1}', size=18))
        out.append({'kind': 'slider', 'name': f'ZLevel{i}', 'rect': [x + 20, 150, 60, 440],
                    'orientation': 'up', 'fill': ('raised', 'ground', 'shape', 'accent2')[i],
                    'track': 10 + 4 * i})
        out.append(label(f'ZValue{i}', (x - 20, 600, 140, 40), f'{25 * (i + 1)}%', size=16,
                         color='muted'))
        out.append(button(f'ZMute{i}', (x - 10, 660, 120, 70), 'Mute', size=18, fill='raised',
                          border='afterburn', on='alert'))
    return content('Content Zeta', 6050, out)


def content_eta():
    out = [{'grid': {'rect': [180, 100, 703, 40], 'cols': 8, 'gap': 9, 'kind': 'label',
                     'size': 14, 'color': 'muted',
                     'items': [{'name': f'Out{j}', 'text': f'Out {j + 1}'} for j in range(8)]}}]
    for r in range(5):
        y = 150 + r * 120
        out.append(label(f'InName{r}', (32, y, 140, 100), f'In {r + 1}', size=20, align='left'))
        out.append({'grid': {'rect': [180, y, 703, 100], 'cols': 8, 'gap': 15, 'kind': 'button',
                             'fill': 'ground', 'border': 'rounded', 'size': 14,
                             'on': 'accent',
                             'items': [{'name': f'X{r}{j}', 'text': f'{r + 1}:{j + 1}'}
                                       for j in range(8)]}})
    return content('Content Eta', 6060, out)


def content_theta():
    out = [label('ArialHead', (32, 100, 851, 50), 'Set in Arial', size=26, font='Arial',
                 align='left'),
           label('ArialBody', (32, 156, 851, 120),
                 'Arial at 18 point, wrapped across the popup, in the face the seeds embed '
                 'for their system text.', size=18, font='Arial', align='top-left'),
           label('BlackHead', (32, 290, 851, 60), 'Arial Black Heading', size=28,
                 font='Arial Black', align='left'),
           {'grid': {'rect': [32, 370, 851, 300], 'cols': 3, 'rows': 4, 'gap': 12,
                     'kind': 'label', 'font': 'Arial', 'size': 16, 'fill': 'raised',
                     'border': 'rect-thin',
                     'items': [{'name': f'Cell{i}', 'text': f'Cell {i + 1}',
                                'align': ('left', 'center', 'right')[i % 3]}
                               for i in range(12)]}},
           label('LightFoot', (32, 690, 851, 70), 'Open Sans Light at 24 point', size=24,
                 font='Open Sans Light', color='muted')]
    return content('Content Theta', 6070, out)


def level(name, number, words, fill):
    return {'name': name, 'number': number, 'group': 'Level', 'size': [136, 496],
            'background': 'raised', 'controls': [
                label('LevelName', (0, 8, 136, 64), words, size=16, bold=True),
                {'kind': 'slider', 'name': 'LevelSlider', 'rect': [38, 80, 60, 300],
                 'orientation': 'up', 'fill': fill, 'track': 10},
                button('LevelMute', (16, 400, 104, 72), 'Mute', size=16, fill='page',
                       border='afterburn', stroke='shape', on='alert'),
            ]}


def wide():
    out = [label('WideTitle', (24, 12, 852, 50), 'Wide Grid', size=24, bold=True, align='left')]
    for r, word in enumerate(('North', 'South', 'East')):
        y = 80 + r * 150
        out.append(label(f'Row{r}', (24, y, 120, 130), word, size=18, align='left'))
        out.append({'grid': {'rect': [150, y, 726, 130], 'cols': 6, 'gap': 14, 'kind': 'button',
                             'fill': 'page', 'border': 'afterburn', 'stroke': 'shape', 'size': 16,
                             'items': [{'name': f'W{r}{j}', 'text': f'{word}\n{j + 1}'}
                                       for j in range(6)]}})
    return {'name': 'Wide Grid', 'number': 7100, 'group': 'Wide', 'size': [900, 530],
            'background': 'raised', 'controls': out}


ROWS_UPPER = ('ABCDEFGHI', 'JKLMNOPQR', 'STUVWXYZ-', '123456789')


def keys(name, number, rows):
    out = [label('Entry', (40, 40, 915, 90), 'Type here' if rows[0].islower() else 'TYPE HERE',
                 size=28, fill='paper', color='black', border='rect-thin', align='left')]
    for r, row in enumerate(rows):
        out.append({'grid': {'rect': [40, 160 + r * 110, 915, 96], 'cols': len(row), 'gap': 12,
                             'kind': 'button', 'fill': 'page', 'border': 'afterburn',
                             'stroke': 'shape', 'size': 26,
                             'items': [{'name': f'K{r}{i}', 'text': ch} for i, ch in enumerate(row)]}})
    out.append({'grid': {'rect': [40, 600, 915, 96], 'cols': 4, 'gap': 12, 'kind': 'button',
                         'fill': 'ground', 'border': 'afterburn', 'size': 22,
                         'items': [{'name': 'Zero', 'text': '0'},
                                   {'name': 'Space', 'text': 'Space'},
                                   {'name': 'Back', 'text': 'Back'},
                                   {'name': 'Enter', 'text': 'Enter', 'fill': 'accent',
                                    'color': 'deep', 'on': 'raised'}]}})
    out.append(label('KeysNote', (40, 716, 915, 50), 'Single-character captions at 26 point',
                     size=16, color='muted'))
    return {'name': name, 'number': number, 'group': 'Keys', 'size': [995, 800],
            'background': 'page', 'controls': out}


def note():
    # No background: the popup's own snapshot has nothing under its text.
    return {'name': 'Note Clear', 'number': 7200, 'group': 'Note', 'size': [600, 150],
            'background': 'none', 'controls': [
                label('NoteHead', (0, 0, 600, 60), 'Clear background', size=26, bold=True),
                label('NoteBody', (0, 60, 600, 40), 'Text drawn over nothing at all', size=18,
                      color='muted'),
                label('NoteChip', (200, 104, 200, 40), 'Chip', size=16, fill='accent2',
                      border='capsule'),
            ]}


def single():
    return {'name': 'Single', 'number': 7300, 'size': [400, 160], 'background': 'ground',
            'controls': [
                label('SingleText', (20, 10, 360, 60), 'Shown by its ID', size=20),
                button('SingleClose', (120, 84, 160, 64), 'Close', size=18, fill='raised',
                       border='afterburn', stroke='muted'),
            ]}


def modals():
    confirm = {'name': 'Confirm', 'number': 9000, 'modal': True, 'controls': [
        {'kind': 'panel', 'name': 'Card', 'rect': [340, 250, 600, 300], 'fill': 'page',
         'border': 'afterburn', 'stroke': 'shape'},
        label('Question', (370, 270, 540, 70), 'Confirm', size=28, bold=True),
        label('Detail', (370, 340, 540, 80), 'Proceed with the change to every channel?',
              size=20, color='muted'),
        {'grid': {'rect': [400, 440, 480, 80], 'cols': 2, 'gap': 40, 'kind': 'button',
                  'border': 'afterburn', 'size': 22,
                  'items': [{'name': 'Yes', 'text': 'Yes', 'fill': 'accent', 'color': 'deep',
                             'on': 'raised'},
                            {'name': 'No', 'text': 'No', 'fill': 'raised'}]}},
    ]}
    notice = {'name': 'Notice', 'number': 9010, 'modal': True, 'controls': [
        {'kind': 'panel', 'name': 'Card', 'rect': [240, 200, 800, 400], 'fill': 'raised',
         'border': 'afterburn-14'},
        label('Head', (280, 220, 720, 60), 'Notice', size=26, bold=True, align='left'),
        label('Body', (280, 290, 720, 180),
              'A longer message, set as a paragraph inside a card that covers the middle of '
              'the screen, with the page dimmed behind it.', size=20, align='top-left'),
        button('Okay', (820, 500, 180, 70), 'OK', size=22, fill='accent', color='deep',
               border='afterburn', on='raised'),
    ]}
    busy = {'name': 'Busy', 'number': 9020, 'modal': True, 'controls': [
        label('Wait', (240, 330, 800, 80), 'Please wait', size=36),
        label('WaitMore', (240, 410, 800, 50), 'Text over the dimmed page, with no card',
              size=18, color='muted'),
    ]}
    return [confirm, notice, busy]


def spec():
    theme = dict(TEMPLATE, **OWN, **ALPHA)
    theme.update(background=TEMPLATE['page'], font='Open Sans', size=18, on='accent')
    return {
        'name': 'Synthetic Fixture',
        'model': 'TLP1035T',
        'family': 'Afterburn',
        'size': [W, H],
        '_why': ('The render baseline\'s project (tests/data/synthetic/README.md): every control '
                 'type the renderer scores, text at many sizes, faces, weights, alignments and '
                 'widths, popups of every size the old fixture had, in generic words.'),
        '_seed': 'seeds/Afterburn 1035.gdl',
        '_template_colors': sorted(set(TEMPLATE.values())),
        'theme': theme,
        'start_page': 'Start',
        # GUI Designer's own Offline Page, on, so its snapshot is scored too.
        'offline': {'enabled': True, 'replace': {'XXX.XXX.XXXX': '555.010.4567'}},
        # Two of its captions GUI Designer cuts, and the snapshots show it:
        # Type Sizes' Italic40 trimmed to 'Type 40 Itali', Wrapping's
        # LongWord split over three lines - what gdl.compose.fitted was
        # measured on. A measurement spec, so the check that refuses a cut
        # caption (gdl.spec _caption_rules) says them instead; the plan's
        # ops, and so the build, are what they were without it.
        'caption_fit': 'off',
        'images': {n: f'./art/{n}' for n in ('backdrop.png', 'stripes.png', 'pattern.png',
                                             'glyph.png', 'glyph-on.png', 'thumb.png')},
        'pages': [start(), main_page(), matrix_page(), type_sizes(), type_faces(), alignment(),
                  wrapping(), buttons(), controls(), keys_page()],
        'popups': [content_alpha(), content_beta(), content_gamma(), content_delta(),
                   content_epsilon(), content_zeta(), content_eta(), content_theta(),
                   level('Level One', 7000, 'Level\nOne', 'raised'),
                   level('Level Two', 7010, 'Level\nTwo', 'shape'),
                   wide(),
                   keys('Keys Upper', 8000, ROWS_UPPER),
                   keys('Keys Lower', 8010, tuple(r.lower() for r in ROWS_UPPER)),
                   note(), single()] + modals(),
    }


# -- art -------------------------------------------------------------------
def art(out):
    """Pictures of our own, simple enough to compress small and to read by eye."""
    from PIL import Image, ImageDraw
    os.makedirs(out, exist_ok=True)

    im = Image.new('RGB', (640, 400))
    d = ImageDraw.Draw(im)
    for y in range(400):
        t = y / 399
        d.line([(0, y), (639, y)], fill=(int(26 + 32 * t), int(28 + 33 * t), int(40 + 45 * t)))
    for i, (cx, cy, r) in enumerate(((120, 300, 90), (520, 90, 60), (330, 210, 30))):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], outline=(106, 110, 137), width=3)
    for k in range(5):
        d.line([(400 + 40 * k, 400), (640, 160 + 40 * k)], fill=(65, 68, 89), width=6)
    im.save(os.path.join(out, 'backdrop.png'), optimize=True)

    im = Image.new('RGB', (64, 32), (55, 57, 78))
    d = ImageDraw.Draw(im)
    for k in range(-32, 64, 16):
        d.polygon([(k, 32), (k + 8, 32), (k + 40, 0), (k + 32, 0)], fill=(214, 155, 97))
    im.save(os.path.join(out, 'stripes.png'), optimize=True)

    im = Image.new('RGB', (320, 200))
    d = ImageDraw.Draw(im)
    bars = [(255, 255, 255), (242, 201, 76), (106, 207, 232), (46, 158, 91), (214, 155, 97),
            (211, 41, 41), (98, 106, 207), (18, 19, 28)]
    for i, c in enumerate(bars):
        d.rectangle([i * 40, 0, i * 40 + 39, 139], fill=c)
    for x in range(320):
        v = round(255 * x / 319)
        d.line([(x, 140), (x, 169)], fill=(v, v, v))
    for i in range(16):
        d.rectangle([i * 20, 170, i * 20 + 19, 199],
                    fill=(255, 255, 255) if i % 2 else (0, 0, 0))
    im.save(os.path.join(out, 'pattern.png'), optimize=True)

    for name, ink in (('glyph.png', (255, 255, 255, 255)), ('glyph-on.png', (18, 19, 28, 255))):
        im = Image.new('RGBA', (96, 96), (0, 0, 0, 0))
        d = ImageDraw.Draw(im)
        d.ellipse([8, 8, 87, 87], outline=ink, width=6)
        d.polygon([(38, 28), (38, 68), (70, 48)], fill=ink)
        im.save(os.path.join(out, name), optimize=True)

    im = Image.new('RGBA', (64, 64), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    d.rounded_rectangle([4, 4, 59, 59], radius=14, fill=(214, 155, 97, 255),
                        outline=(255, 255, 255, 255), width=3)
    im.save(os.path.join(out, 'thumb.png'), optimize=True)


def main(argv):
    with open(os.path.join(HERE, 'synthetic.json'), 'w', encoding='utf-8', newline='\n') as fh:
        json.dump(spec(), fh, indent=1, ensure_ascii=False)
        fh.write('\n')
    if '--art' in argv:
        art(os.path.join(HERE, 'art'))
    return 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv))
