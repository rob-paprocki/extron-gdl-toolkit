# examples/

Specs, edits and scripts to start from. `python -m gdl.spec check <spec>`
needs nothing installed, `render` needs Pillow, and building any of them needs
Windows and GUI Designer (`powershell/New-GdlPanel.ps1`).

## Panel specs

| file | what it is |
|---|---|
| `panel.json` | the worked example: a boardroom page with a volume popup for a TLP Pro 1035. `docs/panel-preview.png` is its preview |
| `huddle.json` | one huddle-room page, written from a verbal brief |
| `huddle-functions.json` | the same brief with what each control does, for `gdl.idmap` |
| `multipage.json` | three pages: the smallest spec that shows IDs allocated page by page |
| `icons.json` | icon-font glyphs by name and by codepoint, and a mute with two glyph states |
| `clean-room.json` | an 835M panel on the Afterburn 835 seed, with Afterburn's tokens and Off/On states |
| `boardroom-full.json` | a full-size system: many pages, volume popups on some of them, and modals |
| `panel-plan.json` | the kind of file `gdl.spec plan` writes and `Apply-GdlPlan.ps1` reads |

## Edits

`edits.json` renames by map and by regex and restyles, and checks against
`tests/data/synthetic/synthetic.gdl`. `retarget.json` moves a panel such as that
one from a TLP Pro 1035T to a 1535M.

## Scripts

| file | what it is |
|---|---|
| `add-page-and-popup.ps1` | adds a page, a button, a popup in a new group and a popup reference to an extracted project, removes a popup, and checks its own work. Needs Windows, GUI Designer and 32-bit PowerShell 5.1 |
| `probes-128/` | format probes run once on GUI Designer 1.28.0.7. Its README says what each asked and what it proved |
