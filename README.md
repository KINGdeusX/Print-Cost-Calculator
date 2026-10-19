<p align="center">
  <img src="pcc/assets/icon.png" alt="Print Cost Calculator" width="128">
</p>

<h1 align="center">Print Cost Calculator</h1>

<p align="center">Drop in a sliced <code>.3mf</code>, get a fair price for your 3D print. Desktop app, command line and HTTP API.</p>

## ✨ What it does

- **Multi-plate jobs.** Price several plates (with copies and labor per plate) in one quote.
- **`.3mf` drag & drop.** Drop a sliced Bambu Studio / OrcaSlicer file and print time, filament grams and AMS slots are filled in for you.
- **Failure allowance.** Add a percentage on top of filament and electricity to cover failed prints.
- **Hidden per-plate fee.** An internal fee added to each plate's price. It is never written to the Excel report or shown by the public API.
- **Printer and filament profiles.** Keep your machines (wattage) and spools (price per kg) in editable lists.
- **Currencies.** Pick the currency symbol and electricity rate that suit you (default PHP, ₱).
- **Light / dark / system theme.**
- **Excel reports.** Export a quote to `.xlsx`, or append it to your last report.

## 📥 Download & install

Grab the latest build from the [Releases](https://github.com/KINGdeusX/Print-Cost-Calculator/releases) page.

- **Windows (installer):** download `PrintCostCalculator-<version>-setup.exe` and run it. Windows SmartScreen may warn about an unknown publisher: click **More info → Run anyway**.
- **Windows (portable):** download `PrintCostCalculator-<version>-windows-x64.zip`, unzip it, and run `PrintCostCalculator.exe`.
- **Linux (AppImage):** download `PrintCostCalculator-<version>-x86_64.AppImage`, then:
  ```bash
  chmod +x PrintCostCalculator-*-x86_64.AppImage
  ./PrintCostCalculator-*-x86_64.AppImage
  ```
- **Linux (tarball):** extract `PrintCostCalculator-<version>-linux-x86_64.tar.gz` and run `PrintCostCalculator/PrintCostCalculator`.
- **From source** (Python 3.10+):
  ```bash
  pip install ".[gui]"
  pcc-gui
  ```
  `pcc-gui --timing` prints startup times per stage (from launch to splash and window) to stderr. The Windows `.exe` is a windowed app with no console, so run it from source to see them.

## 📁 Projects

The start screen lists your projects. Drop a sliced `.3mf` (or click **➕ New** / **📂 Import .3mf**) to start one, then **💾 Save** it. Reopen, rename or delete projects from the list; deleted projects go to the Recycle Bin.

## 🧾 Invoices

Click **🧾 Invoice** inside a project to create a numbered PDF invoice (`INV-0001`, `INV-0002`, ...). Set your company name and logo in preferences. Invoices never show cost lines, margin, the hidden fee or filament prices.

## 💰 How pricing works

For every plate, per copy:

1. **Filament** = grams / 1000 x the filament's price per kg (summed over every filament on the plate).
2. **Electricity** = printer watts / 1000 x print hours x your electricity rate.
3. **Failure allowance** = (filament + electricity) x failure %.
4. **Labor** = the labor amount you entered for that plate.
5. **Plate cost** = filament + electricity + failure allowance + labor.
6. **Plate price** = plate cost x (1 + margin %) + the hidden plate fee.

For the whole job:

- **Job cost** = sum of (plate cost x copies) + packaging (charged once per job).
- **Price** = sum of (plate price x copies) + packaging x (1 + margin %).
- The price is rounded half-up to your rounding step (for example 5). A step of 0 means 2 decimals.
- **Markup** = price - job cost.

## 🧩 Exporting a sliced `.3mf`

The app needs slice data, so export from the slicer after slicing:

- In **Bambu Studio** or **OrcaSlicer**, slice the plate and choose **Export plate sliced file**, or **Export all sliced files** for a multi-plate project.
- A plain project file saved without slicing has no time or filament data and will be rejected with a hint.

## ⌨️ Command line

```bash
pcc quote benchy.3mf --printer bambu-p1s --copies 3 --customer "Ana"
pcc quote benchy.3mf --json
pcc quote benchy.3mf --internal                      # cost breakdown, margin and fee
pcc quote benchy.3mf --export report.xlsx            # new report (refuses an existing file)
pcc quote benchy.3mf --export report.xlsx --append   # add to an existing report
pcc quote benchy.3mf --export report.xlsx --force    # replace an existing report
pcc parse benchy.3mf --json                          # plates, hours, grams, filaments
pcc printers
pcc filaments --json
```

Printer and filament ids (like `bambu-p1s`) come from `pcc printers` and `pcc filaments`.

Exit codes: `0` ok, `2` bad input, `3` file error.

## 🌐 HTTP API

```bash
pip install ".[api]"
pcc serve --host 127.0.0.1 --port 8765
```

Or with Docker (settings persist in the volume):

```bash
docker build -t pcc-api .
docker run -p 8765:8765 -v pcc-data:/data \
  -e PCC_ADMIN_TOKEN=change-me -e PCC_CORS_ORIGINS=https://shop.example.com pcc-api
```

| Environment variable | Meaning |
|---|---|
| `PCC_ADMIN_TOKEN` | Bearer token for admin routes. If unset, admin routes return 403. |
| `PCC_CORS_ORIGINS` | Comma-separated list of allowed browser origins (default: none). |
| `PCC_CONFIG_DIR` | Where settings and the printer/filament catalog are stored (`/data` in Docker). |

| Method | Path | Auth | Purpose |
|---|---|---|---|
| GET | `/api/v1/health` | none | status and version |
| GET | `/api/v1/printers` | none | printer ids and names |
| GET | `/api/v1/filaments` | none | filament id, name, type, color (no prices) |
| POST | `/api/v1/parse` | none | upload a `.3mf`, get plates and matches |
| POST | `/api/v1/quote` | none | JSON job to public quote |
| POST | `/api/v1/quote/3mf` | none | upload a `.3mf` plus options to public quote |
| POST | `/api/v1/export/xlsx` | admin | JSON job to `.xlsx` download |
| GET/PUT | `/api/v1/admin/settings` | admin | read or replace server settings |
| GET/PUT | `/api/v1/admin/catalog` | admin | read or replace printers and filaments |

```bash
curl -F file=@benchy.3mf -F copies=2 -F customer="Ana" http://localhost:8765/api/v1/quote/3mf
```

Public quotes never include cost lines, margin, the hidden fee or filament prices. A JSON quote needs at least one plate, and each public plate needs print time or filament (`400 invalid_request` otherwise). Interactive docs are at `/docs`.
Generate clients for any language from `/openapi.json`.

## 🗂️ Where your data lives

| What | Windows | macOS | Linux |
|---|---|---|---|
| Projects and invoices | `Documents\Print Cost Calculator` | `~/Documents/Print Cost Calculator` | `Print Cost Calculator` in your documents folder (`XDG_DOCUMENTS_DIR`, default `~/Documents`) |
| Settings, profiles and logo | `%APPDATA%\PrintCostCalculator` | `~/Library/Application Support/PrintCostCalculator` | `$XDG_CONFIG_HOME/print-cost-calculator` (default `~/.config/print-cost-calculator`) |
| Program (installer) | `C:\Program Files\Print Cost Calculator` | — | — |

Uninstalling removes only the program and keeps your data. Set `PCC_DATA_DIR` to store projects and invoices elsewhere, and `PCC_CONFIG_DIR` for settings, profiles and logo.

## 🔨 Building from source

```bash
bash packaging/build_linux.sh          # tarball + AppImage in packaging/out
```
```powershell
./packaging/build_windows.ps1          # zip in packaging\out
./packaging/build_windows.ps1 -Installer   # also builds the setup.exe (needs Inno Setup 6)
```

Tagged pushes (`v*`) build everything on GitHub Actions and attach it to a release.

## 📄 License

[MIT](LICENSE) © 2026 KINGdeusX
