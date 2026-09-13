# seeds/

Fourteen themed projects made in GUI Designer with **File > New Project**, used
as donors for clean-room authoring: a panel generated from one of these carries
nothing of any client's. They are Git LFS objects - run `git lfs pull` on a
fresh clone, or `git lfs pull --include "seeds/Afterburn 1035.gdl"` for one.

`PBProject` cannot be constructed headlessly and the Project Create Wizard
exposes nothing to UI Automation, so a seed is the one step that needs a person -
about a minute each. `docs/from-scratch.md` §5c has the recipe.

| File | Project name | Model(s) by part number | Part | Canvas | Pages | Popups | Controls | Borders | Declared fonts |
|---|---|---|---|---|---:|---:|---:|---:|---|
| `Afterburn 1035.gdl` | Afterburn All-inclusive 1220 | TLP1035M, TLP1035T | 60-1999-02 | 1280x800 | 7 | 29 | 650 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 1230W.gdl` | Afterburn All-inclusive 1230 | TLP1230WTG | 60-1668-02 | 1920x720 | 12 | 26 | 878 | 18 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 1535.gdl` | Afterburn All-inclusive 1720 | TLP1535M | 60-2000-02 | 1920x1080 | 7 | 29 | 652 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 300M Landscape.gdl` | Afterburn All-Inclusive str300 | TLP300M | 60-1667-02 | 480x320 | 13 | 6 | 180 | 17 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 300M Portrait.gdl` | Afterburn All-inclusive str300 | TLP300M | 60-1667-02 | 320x480 | 13 | 6 | 192 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 835 (Project1).gdl` | Afterburn All-inclusive 1220 | TLP835M | 60-1996-02 | 1280x800 | 7 | 29 | 650 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Mach 1035.gdl` | Mach All-inclusive 1220 | TLP1035M, TLP1035T | 60-1999-02 | 1280x800 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 1535.gdl` | Mach All-inclusive 1720 | TLP1535M | 60-2000-02 | 1920x1080 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 300M Portrait.gdl` | Mach All inclusive str300 | TLP300M | 60-1667-02 | 320x480 | 12 | 6 | 176 | 13 | Arial, Arial Black, Extron-Lift, Open Sans |
| `Shockwave 1035.gdl` | Shockwave All-inclusive 1220 | TLP1035M, TLP1035T | 60-1999-02 | 1280x800 | 7 | 24 | 537 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 1535.gdl` | Shockwave All-inclusive 1720 | TLP1535M | 60-2000-02 | 1920x1080 | 7 | 24 | 535 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron-Shockwave, Open Sans, Roboto |
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
- **Three pairs are the same project at two sizes** - Afterburn, Mach and
  Shockwave at 1035 and 1535. They are ground truth for `retarget`
  (research/2026-09-10/retarget_truth.py).

## Gaps

No seed yet for: the Teams Rooms family (Extron Control for Teams Rooms, 16x9
and 16x10), Zoom Rooms at 725 or 986x740, and several sizes with templates but no
seed - 1024x600 (1020), 1366x768 (1520), 800x480 (520/720), 1280x720 (535) and
320x240 (320). Each is one File > New Project away.

These derive from Extron's templates. Keep the repo private while they are in it.
