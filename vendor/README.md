# vendor/

Extron's own content, copied from the GUI Designer 1.28.0.7 install so the tests
and scripts that read it need nothing outside this directory.

| Here | From |
|---|---|
| `extron/TouchLink Templates/` | `C:\Users\Public\Documents\Extron\GUI Designer Templates\TouchLink Templates` - the 50 `.glt` theme templates |
| `extron/Resources/Afterburn/Icons/` | the Afterburn icon kit, 1,316 PNGs - `powershell/New-ImageProbe.ps1`'s default icon source |

**Only this README and `MANIFEST.md` are in git.** The files themselves (about
470 MB) are Extron's installed, reinstallable content rather than work product,
and pushing them through Git LFS would nearly triple the repo's LFS footprint
for no information gain. `MANIFEST.md` records every file with its size and
SHA-256, so what belongs here is exact even though the bytes are not pushed.

To repopulate on a fresh clone, on a machine with GUI Designer installed:

```powershell
$src = 'C:\Users\Public\Documents\Extron\GUI Designer Templates'
# Create each destination BEFORE copying into it. Copy-Item -Recurse copies a
# folder's *contents* when the destination does not exist, and copies the folder
# itself when it does - so without this line the 52 template files land directly
# in vendor\extron\ with no "TouchLink Templates" level, which is exactly the
# state a fresh clone is in.
New-Item -ItemType Directory -Force 'vendor\extron' | Out-Null
Copy-Item "$src\TouchLink Templates" 'vendor\extron\' -Recurse
New-Item -ItemType Directory -Force 'vendor\extron\Resources\Afterburn' | Out-Null
Copy-Item "$src\Resources\Afterburn\Icons" 'vendor\extron\Resources\Afterburn\' -Recurse
```

Verify afterwards — `vendor\extron\TouchLink Templates` should hold 52 files (50
`.glt` plus two `.config`), and `vendor\extron\Resources\Afterburn\Icons` 1,316
files. `MANIFEST.md` has the SHA-256 of every one. Note that GUI Designer
rewrites `TemplateInfoTable.config` and `TemplateInstallerInfoTable.config` as
it runs, so those two will not match the manifest on a machine that has opened
the application; nothing in this repo reads them.

Without it, `tests/_corpus.py` falls back to the install path, and the tests that
need a template skip rather than fail.

**Images that exist only inside Extron's files** go here too, extracted rather
than copied: Turbulence has no `Resources` folder in 1.28 - its kit lives inside
its TouchLink templates - and Mach's slider art lives only inside its seed.

```bash
python -m gdl.designsys extract turbulence   # -> vendor/extron/Resources/Turbulence/Extracted
```

A profile's `kit.extract` names the files to read (`seeds/...`, or a template
name pattern) and where the images go. Like everything else here, they are
Extron's, reproducible, and not in git.

The rest of the install's `Resources/` (about 2.5 GB of icons and images for
every theme) was not copied; nothing in this repo reads it.
