# seeds/

Themed projects made in GUI Designer with **File > New Project**, used
as donors for clean-room authoring: a panel generated from one of these carries
nothing of any client's. They are Git LFS objects - run `git lfs pull` on a
fresh clone, or `git lfs pull --include "seeds/Afterburn 1035.gdl"` for one.

`PBProject` cannot be constructed headlessly, so a seed has to come from the
Project Create Wizard. In 1.28 that wizard **can** be driven through the
accessibility tree - expand each combo and click the list item you want - which
is how all six `ECP` seeds were made. Two things to avoid, both of which produce
a plausible-looking wizard that builds the wrong project:

- **Never set a combo's value as text.** That updates the edit field without
  raising the selection, so the wizard reads correct and stays internally
  unselected, with Create disabled and no way back but Cancel.
- **Click the Blank/Theme radio yourself and check it took.** The Theme combo
  populates on its own once a themed resolution is picked, so it can read
  `Mach` while `Blank` is still the selected radio — and Create is enabled
  either way. Two seeds were built blank that way before it was noticed. The
  radio exposes no toggle state to read back, so the only check is a screenshot,
  or counting pages afterwards: a blank ECP project has 1 page and 3 controls.

`powershell/New-GdlSeed.ps1` does it with no hands on the mouse, avoiding both,
builds the result, and keeps a seed only if `tests/verify_seed.py` passes it:
the part number and theme asked for, a themed project and not a Blank one, and
pages that are those of the series template GUI Designer takes for the model (a
built seed does not name its series). It needs a connected desktop.
`docs/from-scratch.md` §5c has the recipe and §7 the automation detail.

A panel turned where its theme draws no template that way up - the 835M and
1035M portrait, the 520M, 521M and 535M turned, and in Mach, which draws its 300
portrait alone, the 300M landscape - the wizard offers Blank alone,
so its seed is the model's own turned: `powershell/New-GdlTurnedSeed.ps1`
retargets it (`docs/editing.md`), builds it, and keeps it only if
`tests/verify_seed.py` finds its pages are the series template's turned the same
way - every canvas and control scaled per axis.

A seed is named `<Theme> <size>.gdl` - the panel's number, and a `W` if it is
wide (`Mach 725.gdl`, `Afterburn 1230W.gdl`) - not its model, so a second model
of one size takes its whole model: a TLP725M's is `Afterburn TLP725M.gdl`, beside
the TLP725T's `Afterburn 725.gdl`. The 300M's add the way up they were made
(`Mach 300M Portrait.gdl`, `Afterburn 300M Landscape.gdl`), as does a seed of
any panel made the other way up from its default (`Afterburn 1035
Portrait.gdl`); `New-GdlSeed.ps1 -Resolution` makes one that way up where a
template is drawn so, `New-GdlTurnedSeed.ps1` where none is. `Afterburn 835 (Project1).gdl` keeps the wizard's own
default project name, and the ECP and Zoom Rooms seeds are named for their
preset or theme.

A name is where a seed is kept, not what it is. `python -m gdl.seeds pick
<spec.json>` is the seed here for a spec that names its `"family"`: the one
whose own built `layout.json` is that theme, part number and canvas - looked for
under the theme's profile first, then its name, then every seed here - so
`Afterburn ECP 16-9.gdl` serves a VTLPEcp, and `Afterburn 725.gdl` serves no
TLP725M. With none, it prints the line that makes one - `New-GdlSeed.ps1`'s, or
for a panel turned where no template is drawn that way up,
`New-GdlTurnedSeed.ps1`'s, after its own seed's line where that is missing too
- or why there is no such line: seeds Git LFS left as pointers, to pull; a soft
panel, whose seed is made in the wizard by hand, as the ECP ones were; or a
theme that draws no template for the panel either way up, so a seed retargeted
to it is the way (`docs/editing.md`). **Translate
uses a made seed only once its theme's profile lists it**: it reads
`gdl/designsys/<theme>.json`, not this folder. Add the seed under its series'
`seeds` in the profile's `panels`, with the `kinds` and `borders` that `python
tests/measure_series.py <Theme>` measures for it - and, for a series that had no
seed, the `frame` its `--frame` measures - and a row to the table below.

| File | Project name | Model(s) by part number | Part | Canvas | Pages | Popups | Controls | Borders | Declared fonts |
|---|---|---|---|---|---:|---:|---:|---:|---|
| `Afterburn 1035 Portrait.gdl` | Afterburn All-inclusive 1220 | TLP1035M | 60-1999-02 | 800x1280 | 7 | 29 | 650 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 1035.gdl` | Afterburn All-inclusive 1220 | TLP1035M, TLP1035T | 60-1999-02 | 1280x800 | 7 | 29 | 650 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 1230W.gdl` | Afterburn All-inclusive 1230 | TLP1230WTG | 60-1668-02 | 1920x720 | 12 | 26 | 878 | 18 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 1535.gdl` | Afterburn All-inclusive 1720 | TLP1535M | 60-2000-02 | 1920x1080 | 7 | 29 | 652 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 300M Landscape.gdl` | Afterburn All-Inclusive str300 | TLP300M | 60-1667-02 | 480x320 | 13 | 6 | 180 | 17 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 300M Portrait.gdl` | Afterburn All-inclusive str300 | TLP300M | 60-1667-02 | 320x480 | 13 | 6 | 192 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 320.gdl` | Afterburn All-inclusive 320 | TLP320M | 60-1451-02 | 320x240 | 12 | 2 | 86 | 30 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 525.gdl` | Afterburn All-inclusive 525 | TLP525T | 60-1559-02 | 800x480 | 3 | 21 | 243 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 725.gdl` | Afterburn All-inclusive 725 | TLP725T | 60-1562-02 | 1024x600 | 7 | 26 | 582 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 835 (Project1).gdl` | Afterburn All-inclusive 1220 | TLP835M | 60-1996-02 | 1280x800 | 7 | 29 | 650 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn ECP 16-9.gdl` | Afterburn All-inclusive 1720 | VTLPEcp | 60-sVTLPEcp | 1920x1080 | 7 | 29 | 649 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn ECP 16-10.gdl` | Afterburn All-inclusive Extron Control Pro | VTLPEcp | 60-sVTLPEcp | 1280x800 | 7 | 29 | 648 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Mach 1035.gdl` | Mach All-inclusive 1220 | TLP1035M, TLP1035T | 60-1999-02 | 1280x800 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 1525.gdl` | Mach All-inclusive 1525 | TLP1525TG | 60-1790-02 | 1366x768 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 1535.gdl` | Mach All-inclusive 1720 | TLP1535M | 60-2000-02 | 1920x1080 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 300M Portrait.gdl` | Mach All inclusive str300 | TLP300M | 60-1667-02 | 320x480 | 12 | 6 | 176 | 13 | Arial, Arial Black, Extron-Lift, Open Sans |
| `Mach 320.gdl` | Mach All-inclusive 320 | TLP320M | 60-1451-02 | 320x240 | 12 | 2 | 82 | 13 | Arial, Arial Black, Extron-Lift, Open Sans |
| `Mach 525.gdl` | Mach All-inclusive 525 | TLP525T | 60-1559-02 | 800x480 | 3 | 20 | 234 | 14 | Arial, Arial Black, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 535.gdl` | Mach All-inclusive 535 | TLP535T | 60-1994-02 | 1280x720 | 3 | 20 | 232 | 14 | Arial, Arial Black, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 720.gdl` | Mach All-inclusive 720 | TLP720T | 60-1395-02 | 800x480 | 7 | 24 | 524 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 725.gdl` | Mach All-inclusive 725 | TLP725T | 60-1562-02 | 1024x600 | 8 | 26 | 618 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach ECP 16-9.gdl` | Mach All-inclusive 1720 | VTLPEcp | 60-sVTLPEcp | 1920x1080 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach ECP 16-10.gdl` | Mach All-inclusive 1220 | VTLPEcp | 60-sVTLPEcp | 1280x800 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Shockwave 1035.gdl` | Shockwave All-inclusive 1220 | TLP1035M, TLP1035T | 60-1999-02 | 1280x800 | 7 | 24 | 537 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 1525.gdl` | Shockwave All-inclusive 1525 | TLP1525TG | 60-1790-02 | 1366x768 | 7 | 24 | 514 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 1535.gdl` | Shockwave All-inclusive 1720 | TLP1535M | 60-2000-02 | 1920x1080 | 7 | 24 | 535 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 320.gdl` | Shockwave All-inclusive 320 | TLP320M | 60-1451-02 | 320x240 | 12 | 2 | 94 | 14 | Arial, Arial Black, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 525.gdl` | Shockwave All-inclusive 525 | TLP525T | 60-1559-02 | 800x480 | 2 | 18 | 223 | 13 | Arial, Arial Black, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 535.gdl` | Shockwave All-inclusive 535 | TLP535T | 60-1994-02 | 1280x720 | 2 | 18 | 221 | 13 | Arial, Arial Black, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 720.gdl` | Shockwave All-inclusive 720 | TLP720T | 60-1395-02 | 800x480 | 7 | 24 | 511 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 725.gdl` | Shockwave All-inclusive 725 | TLP725T | 60-1562-02 | 1024x600 | 7 | 24 | 511 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave ECP 16-9.gdl` | Shockwave All-inclusive 1720 | VTLPEcp | 60-sVTLPEcp | 1920x1080 | 7 | 24 | 535 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave ECP 16-10.gdl` | Shockwave All-inclusive 1220 | VTLPEcp | 60-sVTLPEcp | 1280x800 | 7 | 24 | 537 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Turbulence 1035.gdl` | Turbulence All-inclusive 1220 | TLP1035M, TLP1035T | 60-1999-02 | 1280x800 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence 1525.gdl` | Turbulence All-inclusive 1525 | TLP1525TG | 60-1790-02 | 1366x768 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence 320.gdl` | Turbulence All-inclusive 320 | TLP320M | 60-1451-02 | 320x240 | 12 | 2 | 94 | 13 | Arial, Arial Black, Open Sans |
| `Turbulence 525.gdl` | Turbulence All-inclusive 525 | TLP525T | 60-1559-02 | 800x480 | 2 | 18 | 236 | 13 | Arial, Arial Black, Extron GUI Configurator, Open Sans |
| `Turbulence 720.gdl` | Turbulence All-inclusive 720 | TLP720T | 60-1395-02 | 800x480 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence 725.gdl` | Turbulence All-inclusive 725 | TLP725T | 60-1562-02 | 1024x600 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Zoom Rooms Dark ZRTP 1035.gdl` | Zoom Rooms Dark ZRTP 1220 | TLP1035M, TLP1035T | 60-1999-02 | 1280x800 | 3 | 4 | 186 | 16 | Arial, Arial Black |
| `Zoom Rooms Light ZRTP 1035.gdl` | Zoom Rooms Light ZRTP 1220 | TLP1035M, TLP1035T | 60-1999-02 | 1280x800 | 3 | 4 | 186 | 16 | Arial, Arial Black |

Borders and page/popup/control counts come from `tests/audit_corpus.py`; model,
part and fonts from each seed's own built `layout.json`.

## What to know before using one

- **They are full themed projects, not blank ones** - 2 to 13 pages
  and up to 878 controls each. The applier drops the seed's own pages and
  popups but its Offline Page, so a spec may reuse their names, not that one
  (`docs/from-scratch.md` §5c); `python -m gdl.spec donors` checks it, and five
  other things, before any Windows work.
- **The built panel is the seed's model**, whatever the spec's `model` says. Use
  a seed at the size you are delivering on; `retarget` is the fallback, and it
  matches Extron's own hand layout at another size for only 22% of controls.
- **Every Mach, Shockwave and Turbulence seed but their 1035, 1535, 300M
  Portrait and ECP seeds, and the Afterburn 1035 Portrait, carry a checksum**
  no other seed has: GUI Designer's feature-flag Gd Generate Checksum was on
  when they were built (`docs/from-scratch.md` §7, *Feature-flag mode*).
  `tests/verify_seed.py` notes it and passes them, and `Apply-GdlPlan.ps1`
  clears it in every panel built on one.
- **Border resources are per theme family, not universal.** Afterburn seeds
  define 17-31, Mach/Shockwave/Turbulence 13-14, the Zoom Rooms seeds 16: every
  one GUI Designer's 13 built-ins (2D and 3D rectangle, rounded rectangle,
  capsule, ellipse). Afterburn, Mach and Zoom Rooms add their own; Shockwave
  and Turbulence none, bar one rounded rectangle of Shockwave's in most of its
  seeds - `2D Rounded Rectangle 1px` in the 725, 1525, 1535 and ECP 16-9, `2D
  Rounded Rectangle Border 1px` in the 720, `2D Rounded Rectangle 0 Border` in
  the 320, none in the 1035, 525, 535 and ECP 16-10 -
  and not every seed of a family has all of its own: the 320 has no 10-radius
  pair, the Mach 300M Portrait, 320 and 720 no Mach border. A border a seed lacks is built as
  its own of the nearest shape - of the same kind, its own family first, then
  the nearest thickness, then the nearest radius - and `donors` says which; one
  with no shape near enough is refused (`gdl.spec.nearest_border`).
  Built on GUI Designer 1.28.0.7, a spec naming Afterburn's 10-radius pair on
  the 320 came back with every control and state drawn in the 320's 7-radius
  outline and 14-radius flat fill the plan named (`archive/job-2419a20b/borders/`).
- **Fonts differ too.** The Zoom Rooms seeds declare only Arial and Arial Black;
  Afterburn adds Open Sans; Mach and Shockwave add their icon fonts. A declared
  face is not always an embedded one — see `gdl/fonts/README.md`.
- **A declared face is not always one the seed has a resource for.** The column
  above is what the built `layout.json` declares. What a control draws in is
  narrower: the families the project has a `PBFontResource` for. Arial Black has
  one in every Mach and Shockwave seed but the 300M Portrait, 320, 525 and 535,
  and in the Afterburn 1035 Portrait, and Open Sans Light in every Mach seed but
  the 300M Portrait and 320, and in the Turbulence 720, 725, 1035 and 1525; every
  other seed declares Arial Black and defines no resource for it. What gives a
  seed the Arial Black resource is not known - each was built, and a build can
  add one (`gdl/fonts/README.md`). A spec naming a family
  its seed has no resource for is given one, a copy of the face another seed
  carries, recorded as that seed records it (`gdl.fonts.find_face`; `donors`
  names the seed, `plan --donor` writes the face beside the plan and the
  applier appends it). The family is named as the seed spells it - `open sans`
  is refused, naming `Open Sans`. Only a family no seed carries is refused
  outright, and the refusal lists the families the seed does define. Built on GUI
  Designer 1.28.0.7, labels in Open Sans Light and Arial Black on the Afterburn
  1035 seed, which has a resource for neither, came back declaring and carrying
  both, each label in its own face, and each face recorded with its carrier's
  author - Open Sans Light added from a file, Arial Black GUI Designer's own
  (`archive/job-2419a20b/fonts/`).
- **The ECP seeds are a soft client, and their canvas is a choice.** Every other
  seed is locked to its panel's resolution, either way up where the panel
  rotates (`docs/design-rules.md` §1). Extron Control Pro offers seven
  presets (`docs/design-rules.md` §1), but **only the two TouchLink ones can be
  themed** — pick a phone or tablet canvas and the wizard's Theme radio greys
  out, leaving Blank as the only option. So the themed ECP matrix is exactly six
  projects, which is exactly the six ECP templates Extron ships.
- **Three pairs are the same project at two sizes** - Afterburn, Mach and
  Shockwave at 1035 and 1535. They are ground truth for `retarget`
  (research/2026-09-10/retarget_truth.py). The ECP seeds add three more pairs at
  1920x1080 and 1280x800, on one platform rather than two.

## Gaps

No seed yet for: the Teams Rooms family (Extron Control for Teams Rooms, 16x9
and 16x10), Zoom Rooms at 725 or 986x740, and Afterburn at the two sizes it has
a template for and no seed - 1366x768 (1520) and 1280x720 (535); its only 800x480
template is the 520's.
Mach, Shockwave and Turbulence have a seed for every series they draw. Each gap
is one `New-GdlSeed.ps1` run away, made as a theme's series or a job needs it.

The wizard makes no seed for a panel turned where no template is drawn that way
up - it offers those Blank alone (`docs/design-rules.md` §1 has which) - so its
seed is its default seed turned, by `New-GdlTurnedSeed.ps1` (above). Only the
1035M has one: the 835M's is one run away, and the 520M's, 521M's and 535M's
need their own seed made first - `gdl.seeds pick` prints both lines.

ECP is complete: all three themes at both presets that can be themed. Its other
five presets (iPhone, Android Phone, iPad, Android Tablet, Custom) are Blank-only
and so cannot produce a useful donor — a blank ECP project is 1 page, 1 popup and
3 controls.

These derive from Extron's templates and are published, by the owner's
decision. Some carry, inside the project, a Windows home-folder path of the
machine that made them, so they name that machine's Windows account; the
publish check scrubs such paths from text but cannot rewrite them inside a
project without breaking it.
