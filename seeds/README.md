# seeds/

Twenty themed projects made in GUI Designer with **File > New Project**, used
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

`docs/from-scratch.md` §5c has the recipe and §7 the automation detail.

| File | Project name | Model(s) by part number | Part | Canvas | Pages | Popups | Controls | Borders | Declared fonts |
|---|---|---|---|---|---:|---:|---:|---:|---|
| `Afterburn 1035.gdl` | Afterburn All-inclusive 1220 | TLP1035M, TLP1035T | 60-1999-02 | 1280x800 | 7 | 29 | 650 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 1230W.gdl` | Afterburn All-inclusive 1230 | TLP1230WTG | 60-1668-02 | 1920x720 | 12 | 26 | 878 | 18 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 1535.gdl` | Afterburn All-inclusive 1720 | TLP1535M | 60-2000-02 | 1920x1080 | 7 | 29 | 652 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 300M Landscape.gdl` | Afterburn All-Inclusive str300 | TLP300M | 60-1667-02 | 480x320 | 13 | 6 | 180 | 17 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 300M Portrait.gdl` | Afterburn All-inclusive str300 | TLP300M | 60-1667-02 | 320x480 | 13 | 6 | 192 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 835 (Project1).gdl` | Afterburn All-inclusive 1220 | TLP835M | 60-1996-02 | 1280x800 | 7 | 29 | 650 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn ECP 16-9.gdl` | Afterburn All-inclusive 1720 | VTLPEcp | 60-sVTLPEcp | 1920x1080 | 7 | 29 | 649 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn ECP 16-10.gdl` | Afterburn All-inclusive Extron Control Pro | VTLPEcp | 60-sVTLPEcp | 1280x800 | 7 | 29 | 648 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Mach 1035.gdl` | Mach All-inclusive 1220 | TLP1035M, TLP1035T | 60-1999-02 | 1280x800 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 1535.gdl` | Mach All-inclusive 1720 | TLP1535M | 60-2000-02 | 1920x1080 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 300M Portrait.gdl` | Mach All inclusive str300 | TLP300M | 60-1667-02 | 320x480 | 12 | 6 | 176 | 13 | Arial, Arial Black, Extron-Lift, Open Sans |
| `Mach ECP 16-9.gdl` | Mach All-inclusive 1720 | VTLPEcp | 60-sVTLPEcp | 1920x1080 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach ECP 16-10.gdl` | Mach All-inclusive 1220 | VTLPEcp | 60-sVTLPEcp | 1280x800 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Shockwave 1035.gdl` | Shockwave All-inclusive 1220 | TLP1035M, TLP1035T | 60-1999-02 | 1280x800 | 7 | 24 | 537 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 1535.gdl` | Shockwave All-inclusive 1720 | TLP1535M | 60-2000-02 | 1920x1080 | 7 | 24 | 535 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave ECP 16-9.gdl` | Shockwave All-inclusive 1720 | VTLPEcp | 60-sVTLPEcp | 1920x1080 | 7 | 24 | 535 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave ECP 16-10.gdl` | Shockwave All-inclusive 1220 | VTLPEcp | 60-sVTLPEcp | 1280x800 | 7 | 24 | 537 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Turbulence 1035.gdl` | Turbulence All-inclusive 1220 | TLP1035M, TLP1035T | 60-1999-02 | 1280x800 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Zoom Rooms Dark ZRTP 1035.gdl` | Zoom Rooms Dark ZRTP 1220 | TLP1035M, TLP1035T | 60-1999-02 | 1280x800 | 3 | 4 | 186 | 16 | Arial, Arial Black |
| `Zoom Rooms Light ZRTP 1035.gdl` | Zoom Rooms Light ZRTP 1220 | TLP1035M, TLP1035T | 60-1999-02 | 1280x800 | 3 | 4 | 186 | 16 | Arial, Arial Black |

Borders and page/popup/control counts come from `tests/audit_corpus.py`; model,
part and fonts from each seed's own built `layout.json`.

## What to know before using one

- **They are full All-inclusive templates, not blank projects** - 3 to 13 pages
  and up to 878 controls each. A generated page *joins* the seed, so a spec's page
  and popup names must not collide with the seed's; `python -m gdl.spec donors`
  checks that, and five other things, before any Windows work.
- **The built panel is the seed's model**, whatever the spec's `model` says. Use
  a seed at the size you are delivering on; `retarget` is the fallback, and it
  matches Extron's own hand layout at another size for only 22% of controls.
- **Border resources are per theme family, not universal.** Afterburn seeds
  define 17-31, Mach/Shockwave/Turbulence 13-14, the Zoom Rooms seeds 16. A spec
  that names `2D Capsule` or an Afterburn radius resolves in one family and not
  another; `donors` says which are missing.
- **Fonts differ too.** The Zoom Rooms seeds declare only Arial and Arial Black;
  Afterburn adds Open Sans; Mach and Shockwave add their icon fonts. A declared
  face is not always an embedded one — see `gdl/fonts/README.md`.
- **A declared face is not always one a spec can use.** The column above is what
  the built `layout.json` declares. What a spec can ask for is narrower: the
  families the seed has a `PBFontResource` for, which is what `gdl.spec donors`
  checks. **No seed has one for Arial Black**, and no Mach or Turbulence seed has
  one for Open Sans Light — so on every seed, a spec naming either warns in
  `donors` and builds in the donor's face. The warning lists the families the
  seed does define.
- **The ECP seeds are a soft client, and their canvas is a choice.** Every other
  seed is locked to its panel's resolution. Extron Control Pro offers seven
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
and 16x10), Zoom Rooms at 725 or 986x740, and several sizes with templates but no
seed - 1024x600 (1020), 1366x768 (1520), 800x480 (520/720), 1280x720 (535) and
320x240 (320). Each is one File > New Project away.

ECP is complete: all three themes at both presets that can be themed. Its other
five presets (iPhone, Android Phone, iPad, Android Tablet, Custom) are Blank-only
and so cannot produce a useful donor — a blank ECP project is 1 page, 1 popup and
3 controls.

These derive from Extron's templates. Keep the repo private while they are in it.
