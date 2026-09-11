# vendor/

Extron's own content, copied from the GUI Designer 1.27.0.9 install so the tests
and scripts that read it need nothing outside this directory.

| Here | From |
|---|---|
| `extron/TouchLink Templates/` | `C:\Users\Public\Documents\Extron\GUI Designer Templates\TouchLink Templates` - the 44 `.glt` theme templates |
| `extron/Resources/Afterburn/Icons/` | the Afterburn icon kit, 1,316 PNGs - `powershell/New-ImageProbe.ps1`'s default icon source |

**Only this README and `MANIFEST.md` are in git.** The files themselves (about
470 MB) are Extron's installed, reinstallable content rather than work product,
and pushing them through Git LFS would nearly triple the repo's LFS footprint
for no information gain. `MANIFEST.md` records every file with its size and
SHA-256, so what belongs here is exact even though the bytes are not pushed.

To repopulate on a fresh clone, on a machine with GUI Designer installed:

```powershell
$src = 'C:\Users\Public\Documents\Extron\GUI Designer Templates'
Copy-Item "$src\TouchLink Templates" 'vendor\extron\' -Recurse
New-Item -ItemType Directory -Force 'vendor\extron\Resources\Afterburn' | Out-Null
Copy-Item "$src\Resources\Afterburn\Icons" 'vendor\extron\Resources\Afterburn\' -Recurse
```

Without it, `tests/_corpus.py` falls back to the install path, and the tests that
need a template skip rather than fail.

The rest of the install's `Resources/` (about 2.5 GB of icons and images for
every theme) was not copied; nothing in this repo reads it.
