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
TLP725M - `Afterburn TLP725M.gdl` does. With none, it prints the line that
makes one - `New-GdlSeed.ps1`'s, or for a panel turned where no template is
drawn that way up, `New-GdlTurnedSeed.ps1`'s, after its own seed's line where
that is missing too
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
| `Afterburn 1020.gdl` | Afterburn All-inclusive 1020 | TLP1020M | 60-1392-02 | 1024x600 | 7 | 26 | 582 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 1022.gdl` | Afterburn All-inclusive 1022 | TLP1022M | 60-1602-02 | 1024x600 | 7 | 26 | 582 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 1025.gdl` | Afterburn All-inclusive 1025 | TLP1025M | 60-1566-02 | 1280x800 | 7 | 29 | 648 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 1026.gdl` | Afterburn All-inclusive 1026 | TLC1026M | 60-1855-02 | 1280x800 | 7 | 29 | 648 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 1035 Portrait.gdl` | Afterburn All-inclusive 1220 | TLP1035M | 60-1999-02 | 800x1280 | 7 | 29 | 650 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 1035.gdl` | Afterburn All-inclusive 1220 | TLP1035M, TLP1035T | 60-1999-02 | 1280x800 | 7 | 29 | 650 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 1220.gdl` | Afterburn All-inclusive 1220 | TLP1220MG | 60-1340-02 | 1280x800 | 7 | 29 | 650 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 1225.gdl` | Afterburn All-inclusive 1225 | TLP1225MG | 60-1787-02 | 1280x800 | 7 | 29 | 650 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 1230W.gdl` | Afterburn All-inclusive 1230 | TLP1230WTG | 60-1668-02 | 1920x720 | 12 | 26 | 878 | 18 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 1520.gdl` | Afterburn All-inclusive 1520 | TLP1520MG | 60-1342-02 | 1366x768 | 7 | 29 | 652 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 1525.gdl` | Afterburn All-inclusive 1525 | TLP1525MG | 60-1789-02 | 1366x768 | 7 | 29 | 652 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 1535.gdl` | Afterburn All-inclusive 1720 | TLP1535M | 60-2000-02 | 1920x1080 | 7 | 29 | 652 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 1720.gdl` | Afterburn All-inclusive 1720 | TLP1720MG | 60-1344-02 | 1920x1080 | 7 | 29 | 652 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 1725.gdl` | Afterburn All-inclusive 1725 | TLP1725MG | 60-1791-02 | 1920x1080 | 7 | 29 | 652 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 300M Landscape.gdl` | Afterburn All-Inclusive str300 | TLP300M | 60-1667-02 | 480x320 | 13 | 6 | 180 | 17 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 300M Portrait.gdl` | Afterburn All-inclusive str300 | TLP300M | 60-1667-02 | 320x480 | 13 | 6 | 192 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 320.gdl` | Afterburn All-inclusive 320 | TLP320M | 60-1451-02 | 320x240 | 12 | 2 | 86 | 30 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 520.gdl` | Afterburn All-inclusive 520 | TLP520M | 60-1185-02 | 800x480 | 3 | 21 | 243 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 521.gdl` | Afterburn All-inclusive TLC521M | TLC521M | 60-1284-02 | 800x480 | 3 | 21 | 243 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 525.gdl` | Afterburn All-inclusive 525 | TLP525T | 60-1559-02 | 800x480 | 3 | 21 | 243 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 526.gdl` | Afterburn All-inclusive 526 | TLC526M | 60-1853-02 | 800x480 | 3 | 21 | 243 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 535.gdl` | Afterburn All-inclusive 535 | TLP535T | 60-1994-02 | 1280x720 | 3 | 21 | 240 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 725.gdl` | Afterburn All-inclusive 725 | TLP725T | 60-1562-02 | 1024x600 | 7 | 26 | 582 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 726.gdl` | Afterburn All-inclusive 726 | TLC726M | 60-1854-02 | 1024x600 | 7 | 26 | 582 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 835 (Project1).gdl` | Afterburn All-inclusive 1220 | TLP835M | 60-1996-02 | 1280x800 | 7 | 29 | 650 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 835 Portrait.gdl` | Afterburn All-inclusive 1220 | TLP835M | 60-1996-02 | 800x1280 | 7 | 29 | 650 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn 835.gdl` | Afterburn All-inclusive 1220 | TLP835T | 60-1997-02 | 1280x800 | 7 | 29 | 650 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn ECP 16-9.gdl` | Afterburn All-inclusive 1720 | VTLPEcp | 60-sVTLPEcp | 1920x1080 | 7 | 29 | 649 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn ECP 16-10.gdl` | Afterburn All-inclusive Extron Control Pro | VTLPEcp | 60-sVTLPEcp | 1280x800 | 7 | 29 | 648 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn TLP1020T.gdl` | Afterburn All-inclusive 1020 | TLP1020T | 60-1393-02 | 1024x600 | 7 | 26 | 582 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn TLP1022T.gdl` | Afterburn All-inclusive 1022 | TLP1022T | 60-1601-02 | 1024x600 | 7 | 26 | 582 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn TLP1025T.gdl` | Afterburn All-inclusive 1025 | TLP1025T | 60-1565-02 | 1280x800 | 7 | 29 | 648 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn TLP1220TG.gdl` | Afterburn All-inclusive 1220 | TLP1220TG | 60-1341-02 | 1280x800 | 7 | 29 | 650 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn TLP1225TG.gdl` | Afterburn All-inclusive 1225 | TLP1225TG | 60-1788-02 | 1280x800 | 7 | 29 | 650 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn TLP1520TG.gdl` | Afterburn All-inclusive 1520 | TLP1520TG | 60-1343-02 | 1366x768 | 7 | 29 | 652 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn TLP1525TG.gdl` | Afterburn All-inclusive 1525 | TLP1525TG | 60-1790-02 | 1366x768 | 7 | 29 | 652 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn TLP1535T.gdl` | Afterburn All-inclusive 1720 | TLP1535T | 60-2001-02 | 1920x1080 | 7 | 29 | 652 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn TLP1720TG.gdl` | Afterburn All-inclusive 1720 | TLP1720TG | 60-1345-02 | 1920x1080 | 7 | 29 | 652 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn TLP1725TG.gdl` | Afterburn All-inclusive 1725 | TLP1725TG | 60-1792-02 | 1920x1080 | 7 | 29 | 652 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn TLP320C.gdl` | Afterburn All-inclusive 320 | TLP320C | 60-1452-02 | 320x240 | 12 | 2 | 86 | 30 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn TLP525C.gdl` | Afterburn All-inclusive 525 | TLP525C | 60-1560-02 | 800x480 | 3 | 21 | 243 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn TLP525M.gdl` | Afterburn All-inclusive 525 | TLP525M | 60-1561-02 | 800x480 | 3 | 21 | 243 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn TLP535M.gdl` | Afterburn All-inclusive 535 | TLP535M | 60-1993-02 | 1280x720 | 3 | 21 | 240 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn TLP725C.gdl` | Afterburn All-inclusive 725 | TLP725C | 60-1564-02 | 1024x600 | 7 | 26 | 582 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn TLP725M.gdl` | Afterburn All-inclusive 725 | TLP725M | 60-1563-02 | 1024x600 | 7 | 26 | 582 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Afterburn TLP835C.gdl` | Afterburn All-inclusive 1220 | TLP835C | 60-1995-02 | 1280x800 | 7 | 29 | 650 | 31 | Arial, Arial Black, Extron-Afterburn, Open Sans |
| `Mach 1020.gdl` | Mach All-inclusive 1020 | TLP1020M | 60-1392-02 | 1024x600 | 8 | 26 | 618 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 1022.gdl` | Mach All-inclusive 1022 | TLP1022M | 60-1602-02 | 1024x600 | 8 | 26 | 618 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 1025.gdl` | Mach All-inclusive 1025 | TLP1025M | 60-1566-02 | 1280x800 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 1026.gdl` | Mach All-inclusive 1026 | TLC1026M | 60-1855-02 | 1280x800 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 1035.gdl` | Mach All-inclusive 1220 | TLP1035M, TLP1035T | 60-1999-02 | 1280x800 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 1220.gdl` | Mach All-inclusive 1220 | TLP1220MG | 60-1340-02 | 1280x800 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 1225.gdl` | Mach All-inclusive 1225 | TLP1225MG | 60-1787-02 | 1280x800 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 1520.gdl` | Mach All-inclusive 1520 | TLP1520MG | 60-1342-02 | 1366x768 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 1525.gdl` | Mach All-inclusive 1525 | TLP1525TG | 60-1790-02 | 1366x768 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 1535.gdl` | Mach All-inclusive 1720 | TLP1535M | 60-2000-02 | 1920x1080 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 1720.gdl` | Mach All-inclusive 1720 | TLP1720MG | 60-1344-02 | 1920x1080 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 1725.gdl` | Mach All-inclusive 1725 | TLP1725MG | 60-1791-02 | 1920x1080 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 300M Portrait.gdl` | Mach All inclusive str300 | TLP300M | 60-1667-02 | 320x480 | 12 | 6 | 176 | 13 | Arial, Arial Black, Extron-Lift, Open Sans |
| `Mach 320.gdl` | Mach All-inclusive 320 | TLP320M | 60-1451-02 | 320x240 | 12 | 2 | 82 | 13 | Arial, Arial Black, Extron-Lift, Open Sans |
| `Mach 520.gdl` | Mach All-inclusive 520 | TLP520M | 60-1185-02 | 800x480 | 3 | 20 | 234 | 14 | Arial, Arial Black, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 521.gdl` | Mach All-inclusive TLC521M | TLC521M | 60-1284-02 | 800x480 | 3 | 20 | 234 | 14 | Arial, Arial Black, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 525.gdl` | Mach All-inclusive 525 | TLP525T | 60-1559-02 | 800x480 | 3 | 20 | 234 | 14 | Arial, Arial Black, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 526.gdl` | Mach All-inclusive 526 | TLC526M | 60-1853-02 | 800x480 | 3 | 20 | 234 | 14 | Arial, Arial Black, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 535.gdl` | Mach All-inclusive 535 | TLP535T | 60-1994-02 | 1280x720 | 3 | 20 | 232 | 14 | Arial, Arial Black, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 720.gdl` | Mach All-inclusive 720 | TLP720T | 60-1395-02 | 800x480 | 7 | 24 | 524 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 725.gdl` | Mach All-inclusive 725 | TLP725T | 60-1562-02 | 1024x600 | 8 | 26 | 618 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 726.gdl` | Mach All-inclusive 726 | TLC726M | 60-1854-02 | 1024x600 | 8 | 26 | 618 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 835 Portrait.gdl` | Mach All-inclusive 1220 | TLP835M | 60-1996-02 | 800x1280 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach 835.gdl` | Mach All-inclusive 1220 | TLP835M | 60-1996-02 | 1280x800 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach ECP 16-9.gdl` | Mach All-inclusive 1720 | VTLPEcp | 60-sVTLPEcp | 1920x1080 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach ECP 16-10.gdl` | Mach All-inclusive 1220 | VTLPEcp | 60-sVTLPEcp | 1280x800 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach TLP1020T.gdl` | Mach All-inclusive 1020 | TLP1020T | 60-1393-02 | 1024x600 | 8 | 26 | 618 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach TLP1022T.gdl` | Mach All-inclusive 1022 | TLP1022T | 60-1601-02 | 1024x600 | 8 | 26 | 618 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach TLP1025T.gdl` | Mach All-inclusive 1025 | TLP1025T | 60-1565-02 | 1280x800 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach TLP1220TG.gdl` | Mach All-inclusive 1220 | TLP1220TG | 60-1341-02 | 1280x800 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach TLP1225TG.gdl` | Mach All-inclusive 1225 | TLP1225TG | 60-1788-02 | 1280x800 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach TLP1520TG.gdl` | Mach All-inclusive 1520 | TLP1520TG | 60-1343-02 | 1366x768 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach TLP1525MG.gdl` | Mach All-inclusive 1525 | TLP1525MG | 60-1789-02 | 1366x768 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach TLP1535T.gdl` | Mach All-inclusive 1720 | TLP1535T | 60-2001-02 | 1920x1080 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach TLP1720TG.gdl` | Mach All-inclusive 1720 | TLP1720TG | 60-1345-02 | 1920x1080 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach TLP1725TG.gdl` | Mach All-inclusive 1725 | TLP1725TG | 60-1792-02 | 1920x1080 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach TLP320C.gdl` | Mach All-inclusive 320 | TLP320C | 60-1452-02 | 320x240 | 12 | 2 | 82 | 13 | Arial, Arial Black, Extron-Lift, Open Sans |
| `Mach TLP525C.gdl` | Mach All-inclusive 525 | TLP525C | 60-1560-02 | 800x480 | 3 | 20 | 234 | 14 | Arial, Arial Black, Extron-Lift, Open Sans, Open Sans Light |
| `Mach TLP525M.gdl` | Mach All-inclusive 525 | TLP525M | 60-1561-02 | 800x480 | 3 | 20 | 234 | 14 | Arial, Arial Black, Extron-Lift, Open Sans, Open Sans Light |
| `Mach TLP535M.gdl` | Mach All-inclusive 535 | TLP535M | 60-1993-02 | 1280x720 | 3 | 20 | 232 | 14 | Arial, Arial Black, Extron-Lift, Open Sans, Open Sans Light |
| `Mach TLP720C.gdl` | Mach All-inclusive 720 | TLP720C | 60-1396-02 | 800x480 | 7 | 24 | 524 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach TLP720M.gdl` | Mach All-inclusive 720 | TLP720M | 60-1394-02 | 800x480 | 7 | 24 | 524 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach TLP725C.gdl` | Mach All-inclusive 725 | TLP725C | 60-1564-02 | 1024x600 | 8 | 26 | 618 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach TLP725M.gdl` | Mach All-inclusive 725 | TLP725M | 60-1563-02 | 1024x600 | 8 | 26 | 618 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach TLP835C.gdl` | Mach All-inclusive 1220 | TLP835C | 60-1995-02 | 1280x800 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Mach TLP835T.gdl` | Mach All-inclusive 1220 | TLP835T | 60-1997-02 | 1280x800 | 8 | 26 | 624 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron-Lift, Open Sans, Open Sans Light |
| `Shockwave 1020.gdl` | Shockwave All-inclusive 1020 | TLP1020M | 60-1392-02 | 1024x600 | 7 | 24 | 511 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 1022.gdl` | Shockwave All-inclusive 1022 | TLP1022M | 60-1602-02 | 1024x600 | 7 | 24 | 511 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 1025.gdl` | Shockwave All-inclusive 1025 | TLP1025M | 60-1566-02 | 1280x800 | 7 | 24 | 537 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 1026.gdl` | Shockwave All-inclusive 1026 | TLC1026M | 60-1855-02 | 1280x800 | 7 | 24 | 537 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 1035.gdl` | Shockwave All-inclusive 1220 | TLP1035M, TLP1035T | 60-1999-02 | 1280x800 | 7 | 24 | 537 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 1220.gdl` | Shockwave All-inclusive 1220 | TLP1220MG | 60-1340-02 | 1280x800 | 7 | 24 | 537 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 1225.gdl` | Shockwave All-inclusive 1225 | TLP1225MG | 60-1787-02 | 1280x800 | 7 | 24 | 537 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 1520.gdl` | Shockwave All-inclusive 1520 | TLP1520MG | 60-1342-02 | 1366x768 | 7 | 24 | 514 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 1525.gdl` | Shockwave All-inclusive 1525 | TLP1525TG | 60-1790-02 | 1366x768 | 7 | 24 | 514 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 1535.gdl` | Shockwave All-inclusive 1720 | TLP1535M | 60-2000-02 | 1920x1080 | 7 | 24 | 535 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 1720.gdl` | Shockwave All-inclusive 1720 | TLP1720MG | 60-1344-02 | 1920x1080 | 7 | 24 | 535 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 1725.gdl` | Shockwave All-inclusive 1725 | TLP1725MG | 60-1791-02 | 1920x1080 | 7 | 24 | 535 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 320.gdl` | Shockwave All-inclusive 320 | TLP320M | 60-1451-02 | 320x240 | 12 | 2 | 94 | 14 | Arial, Arial Black, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 520.gdl` | Shockwave All-inclusive 520 | TLP520M | 60-1185-02 | 800x480 | 2 | 18 | 223 | 13 | Arial, Arial Black, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 521.gdl` | Shockwave All-inclusive TLC521M | TLC521M | 60-1284-02 | 800x480 | 2 | 18 | 223 | 13 | Arial, Arial Black, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 525.gdl` | Shockwave All-inclusive 525 | TLP525T | 60-1559-02 | 800x480 | 2 | 18 | 223 | 13 | Arial, Arial Black, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 526.gdl` | Shockwave All-inclusive 526 | TLC526M | 60-1853-02 | 800x480 | 2 | 18 | 223 | 13 | Arial, Arial Black, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 535.gdl` | Shockwave All-inclusive 535 | TLP535T | 60-1994-02 | 1280x720 | 2 | 18 | 221 | 13 | Arial, Arial Black, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 720.gdl` | Shockwave All-inclusive 720 | TLP720T | 60-1395-02 | 800x480 | 7 | 24 | 511 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 725.gdl` | Shockwave All-inclusive 725 | TLP725T | 60-1562-02 | 1024x600 | 7 | 24 | 511 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 726.gdl` | Shockwave All-inclusive 726 | TLC726M | 60-1854-02 | 1024x600 | 7 | 24 | 511 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 835 Portrait.gdl` | Shockwave All-inclusive 1220 | TLP835M | 60-1996-02 | 800x1280 | 7 | 24 | 537 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave 835.gdl` | Shockwave All-inclusive 1220 | TLP835M | 60-1996-02 | 1280x800 | 7 | 24 | 537 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave ECP 16-9.gdl` | Shockwave All-inclusive 1720 | VTLPEcp | 60-sVTLPEcp | 1920x1080 | 7 | 24 | 535 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave ECP 16-10.gdl` | Shockwave All-inclusive 1220 | VTLPEcp | 60-sVTLPEcp | 1280x800 | 7 | 24 | 537 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave TLP1020T.gdl` | Shockwave All-inclusive 1020 | TLP1020T | 60-1393-02 | 1024x600 | 7 | 24 | 511 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave TLP1022T.gdl` | Shockwave All-inclusive 1022 | TLP1022T | 60-1601-02 | 1024x600 | 7 | 24 | 511 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave TLP1025T.gdl` | Shockwave All-inclusive 1025 | TLP1025T | 60-1565-02 | 1280x800 | 7 | 24 | 537 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave TLP1220TG.gdl` | Shockwave All-inclusive 1220 | TLP1220TG | 60-1341-02 | 1280x800 | 7 | 24 | 537 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave TLP1225TG.gdl` | Shockwave All-inclusive 1225 | TLP1225TG | 60-1788-02 | 1280x800 | 7 | 24 | 537 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave TLP1520TG.gdl` | Shockwave All-inclusive 1520 | TLP1520TG | 60-1343-02 | 1366x768 | 7 | 24 | 514 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave TLP1525MG.gdl` | Shockwave All-inclusive 1525 | TLP1525MG | 60-1789-02 | 1366x768 | 7 | 24 | 514 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave TLP1535T.gdl` | Shockwave All-inclusive 1720 | TLP1535T | 60-2001-02 | 1920x1080 | 7 | 24 | 535 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave TLP1720TG.gdl` | Shockwave All-inclusive 1720 | TLP1720TG | 60-1345-02 | 1920x1080 | 7 | 24 | 535 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave TLP1725TG.gdl` | Shockwave All-inclusive 1725 | TLP1725TG | 60-1792-02 | 1920x1080 | 7 | 24 | 535 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave TLP320C.gdl` | Shockwave All-inclusive 320 | TLP320C | 60-1452-02 | 320x240 | 12 | 2 | 94 | 14 | Arial, Arial Black, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave TLP525C.gdl` | Shockwave All-inclusive 525 | TLP525C | 60-1560-02 | 800x480 | 2 | 18 | 223 | 13 | Arial, Arial Black, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave TLP525M.gdl` | Shockwave All-inclusive 525 | TLP525M | 60-1561-02 | 800x480 | 2 | 18 | 223 | 13 | Arial, Arial Black, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave TLP535M.gdl` | Shockwave All-inclusive 535 | TLP535M | 60-1993-02 | 1280x720 | 2 | 18 | 221 | 13 | Arial, Arial Black, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave TLP720C.gdl` | Shockwave All-inclusive 720 | TLP720C | 60-1396-02 | 800x480 | 7 | 24 | 511 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave TLP720M.gdl` | Shockwave All-inclusive 720 | TLP720M | 60-1394-02 | 800x480 | 7 | 24 | 511 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave TLP725C.gdl` | Shockwave All-inclusive 725 | TLP725C | 60-1564-02 | 1024x600 | 7 | 24 | 511 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave TLP725M.gdl` | Shockwave All-inclusive 725 | TLP725M | 60-1563-02 | 1024x600 | 7 | 24 | 511 | 14 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave TLP835C.gdl` | Shockwave All-inclusive 1220 | TLP835C | 60-1995-02 | 1280x800 | 7 | 24 | 537 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Shockwave TLP835T.gdl` | Shockwave All-inclusive 1220 | TLP835T | 60-1997-02 | 1280x800 | 7 | 24 | 537 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1a, Extron Lift, Extron-Shockwave, Open Sans, Roboto |
| `Turbulence 1020.gdl` | Turbulence All-inclusive 1020 | TLP1020M | 60-1392-02 | 1024x600 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence 1022.gdl` | Turbulence All-inclusive 1022 | TLP1022M | 60-1602-02 | 1024x600 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence 1025.gdl` | Turbulence All-inclusive 1025 | TLP1025M | 60-1566-02 | 1280x800 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence 1026.gdl` | Turbulence All-inclusive 1026 | TLC1026M | 60-1855-02 | 1280x800 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence 1035.gdl` | Turbulence All-inclusive 1220 | TLP1035M, TLP1035T | 60-1999-02 | 1280x800 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence 1220.gdl` | Turbulence All-inclusive 1220 | TLP1220MG | 60-1340-02 | 1280x800 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence 1225.gdl` | Turbulence All-inclusive 1225 | TLP1225MG | 60-1787-02 | 1280x800 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence 1520.gdl` | Turbulence All-inclusive 1520 | TLP1520MG | 60-1342-02 | 1366x768 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence 1525.gdl` | Turbulence All-inclusive 1525 | TLP1525TG | 60-1790-02 | 1366x768 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence 320.gdl` | Turbulence All-inclusive 320 | TLP320M | 60-1451-02 | 320x240 | 12 | 2 | 94 | 13 | Arial, Arial Black, Open Sans |
| `Turbulence 520.gdl` | Turbulence All-inclusive 520 | TLP520M | 60-1185-02 | 800x480 | 2 | 18 | 236 | 13 | Arial, Arial Black, Extron GUI Configurator, Open Sans |
| `Turbulence 521.gdl` | Turbulence All-inclusive TLC521M | TLC521M | 60-1284-02 | 800x480 | 2 | 18 | 236 | 13 | Arial, Arial Black, Extron GUI Configurator, Open Sans |
| `Turbulence 525.gdl` | Turbulence All-inclusive 525 | TLP525T | 60-1559-02 | 800x480 | 2 | 18 | 236 | 13 | Arial, Arial Black, Extron GUI Configurator, Open Sans |
| `Turbulence 526.gdl` | Turbulence All-inclusive 526 | TLC526M | 60-1853-02 | 800x480 | 2 | 18 | 236 | 13 | Arial, Arial Black, Extron GUI Configurator, Open Sans |
| `Turbulence 720.gdl` | Turbulence All-inclusive 720 | TLP720T | 60-1395-02 | 800x480 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence 725.gdl` | Turbulence All-inclusive 725 | TLP725T | 60-1562-02 | 1024x600 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence 726.gdl` | Turbulence All-inclusive 726 | TLC726M | 60-1854-02 | 1024x600 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence 835 Portrait.gdl` | Turbulence All-inclusive 1220 | TLP835M | 60-1996-02 | 800x1280 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence 835.gdl` | Turbulence All-inclusive 1220 | TLP835M | 60-1996-02 | 1280x800 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence TLP1020T.gdl` | Turbulence All-inclusive 1020 | TLP1020T | 60-1393-02 | 1024x600 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence TLP1022T.gdl` | Turbulence All-inclusive 1022 | TLP1022T | 60-1601-02 | 1024x600 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence TLP1025T.gdl` | Turbulence All-inclusive 1025 | TLP1025T | 60-1565-02 | 1280x800 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence TLP1220TG.gdl` | Turbulence All-inclusive 1220 | TLP1220TG | 60-1341-02 | 1280x800 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence TLP1225TG.gdl` | Turbulence All-inclusive 1225 | TLP1225TG | 60-1788-02 | 1280x800 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence TLP1520TG.gdl` | Turbulence All-inclusive 1520 | TLP1520TG | 60-1343-02 | 1366x768 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence TLP1525MG.gdl` | Turbulence All-inclusive 1525 | TLP1525MG | 60-1789-02 | 1366x768 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence TLP320C.gdl` | Turbulence All-inclusive 320 | TLP320C | 60-1452-02 | 320x240 | 12 | 2 | 94 | 13 | Arial, Arial Black, Open Sans |
| `Turbulence TLP525C.gdl` | Turbulence All-inclusive 525 | TLP525C | 60-1560-02 | 800x480 | 2 | 18 | 236 | 13 | Arial, Arial Black, Extron GUI Configurator, Open Sans |
| `Turbulence TLP525M.gdl` | Turbulence All-inclusive 525 | TLP525M | 60-1561-02 | 800x480 | 2 | 18 | 236 | 13 | Arial, Arial Black, Extron GUI Configurator, Open Sans |
| `Turbulence TLP720C.gdl` | Turbulence All-inclusive 720 | TLP720C | 60-1396-02 | 800x480 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence TLP720M.gdl` | Turbulence All-inclusive 720 | TLP720M | 60-1394-02 | 800x480 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence TLP725C.gdl` | Turbulence All-inclusive 725 | TLP725C | 60-1564-02 | 1024x600 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence TLP725M.gdl` | Turbulence All-inclusive 725 | TLP725M | 60-1563-02 | 1024x600 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence TLP835C.gdl` | Turbulence All-inclusive 1220 | TLP835C | 60-1995-02 | 1280x800 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
| `Turbulence TLP835T.gdl` | Turbulence All-inclusive 1220 | TLP835T | 60-1997-02 | 1280x800 | 8 | 24 | 579 | 13 | Arial, Arial Black, Extron GUI Configurator, Extron GUIC Video Conference 1, Open Sans, Open Sans Light |
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
- **A size's forms are one project under their own part numbers.** A theme's
  TLP725M, 725C and 725T seeds hold the same pages, popups, controls and border
  and font resources - the counts in the table agree across a size's forms - and
  differ in the part number, which `gdl.seeds pick` and the built panel go by.
  So a form's seed is its own, not its size's. The counts agree across a
  series' seeds too (the 835, 1026, 1035, 1220 and 1225 are one series), bar one
  trio: Afterburn's 1025M, 1025T and 1026M hold 648 controls where its other
  1220-series seeds hold 650, as its ECP 16-10 does.
- **Most seeds carry a checksum** no others have: GUI Designer's feature-flag
  Gd Generate Checksum was on when they were built (`docs/from-scratch.md` §7,
  *Feature-flag mode*). Those without one: Afterburn's 1035, 1230W, 1535, 300M
  (both), 320, 525, 725, 835 (Project1) and ECP seeds; Mach's 1035, 1535, 300M
  Portrait and ECP seeds; Shockwave's 1035, 1535 and ECP seeds; Turbulence's
  1035; and the Zoom Rooms pair. `tests/verify_seed.py` notes a checksum and
  passes the seed, and `Apply-GdlPlan.ps1` clears it in every panel built on one.
- **Border resources are per theme family, not universal.** Afterburn seeds
  define 17-31, Mach/Shockwave/Turbulence 13-14, the Zoom Rooms seeds 16: every
  one GUI Designer's 13 built-ins (2D and 3D rectangle, rounded rectangle,
  capsule, ellipse). Afterburn, Mach and Zoom Rooms add their own; Shockwave
  and Turbulence none, bar one rounded rectangle of Shockwave's in most of its
  seeds - `2D Rounded Rectangle 1px` in the 725, 726, 1020, 1022, 1520, 1525, 1535, 1720,
  1725 and ECP 16-9 seeds, `2D Rounded Rectangle Border 1px` in the 720s, `2D Rounded Rectangle 0
  Border` in the 320s, none in the 520, 521, 525, 526, 535, 835, 1025, 1026, 1035, 1220, 1225 and ECP
  16-10 seeds -
  and not every seed of a family has all of its own: the 320s have no 10-radius
  pair, the Mach 300M Portrait, 320s and 720s no Mach border. A border a seed lacks is built as
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
  one in every Mach and Shockwave seed but the 300M Portrait, 320s, 520, 521,
  525s, 526 and 535s, and in the Afterburn 1035 Portrait, and Open Sans Light in every Mach seed
  but the 300M Portrait and 320s, and in every Turbulence seed but the 320s, 520, 521,
  525s and 526; every other seed declares Arial Black and defines no resource for it. What gives a
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

No seed yet for the Teams Rooms family (Extron Control for Teams Rooms, 16x9 and
16x10), or for Zoom Rooms at 725 or 986x740 (`python -m gdl.seeds pick` finds
none, and says why).

Every form the four bar themes draw has a seed in each theme that draws it: the
320 (M, C), 520M, 521M, 525 (M, C, T), 526M, 535 (M, T), 720 and 725 (M, C, T),
726M, 835 (M, C, T), 1020, 1022 and 1025 (M, T), 1026M, 1035 (M and T share one),
1220 and 1225 (MG, TG), 1520 and 1525 (MG, TG), 1535 (M, T), 1720 and 1725 (MG,
TG), the 1230WTG and the 300M - the TLC Pro panels (521M, 526M, 726M, 1026M) are
themed in all four. Afterburn draws no 720, and no theme but Mach and Afterburn
draws a 300; Turbulence draws no 535, 1535, 1720 or 1725.

The wizard makes no seed for a panel turned where no template is drawn that way
up - it offers those Blank alone (`docs/design-rules.md` §1 has which) - so its
seed is its default seed turned, by `New-GdlTurnedSeed.ps1` (above). Two have
one: the 835M's, in each theme (`Afterburn 835 Portrait.gdl` and its three
fellows), and the 1035M's, in Afterburn. The 520M's, 521M's and 535M's turned,
and the 1035M's in Mach, Shockwave and Turbulence, are one run away - their own
seed is here - and `gdl.seeds pick` prints the line.

ECP is complete: all three themes at both presets that can be themed, and a
spec can target either (`spec.sizes('VTLPEcp')` is 1920x1080 and 1280x800). Its other
five presets (iPhone, Android Phone, iPad, Android Tablet, Custom) are Blank-only
and so cannot produce a useful donor — a blank ECP project is 1 page, 1 popup and
3 controls.

These derive from Extron's templates and are published, by the owner's
decision. Some carry, inside the project, a Windows home-folder path of the
machine that made them, so they name that machine's Windows account; the
publish check scrubs such paths from text but cannot rewrite them inside a
project without breaking it.
