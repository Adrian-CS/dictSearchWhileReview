# Jisho Lookup — Anki add-on

**Language:** [English](./README.md) · [Español](./README.es.md) · [日本語](./README.ja.md)

Select a word while reviewing a card, press a shortcut, and the add-on
fetches its definition and writes it into a configurable field. Supports
**four language pairs** (ja↔en, es↔en) with
[Jisho](https://jisho.org/) for Japanese and
[Wiktionary](https://wiktionary.org/) for Spanish, with *fallback* to
**local Yomichan / Yomitan dictionaries** you provide yourself.

The add-on's UI is available in **English, Spanish and Japanese**; it
picks the language automatically based on Anki's own UI language.

Compatible with **Anki 2.1.60+** (Qt6).

## Features

- **Two configurable shortcuts** over the word selected in the reviewer:
  - `Ctrl+S` (default) — quick insert: all senses at once.
  - `Ctrl+Shift+S` (default) — **picker popup**: choose field, mode
    (replace / append), language, whether to show grammar tags, and
    which sense(s) to insert.
- **Language pairs**: `ja→en`, `en→ja`, `es→en`, `en→es`. Pick a
  default in the configuration, override per-use from the popup.
- **Auto-detection** for the quick shortcut: if the default pair
  returns nothing, the add-on retries with the pair auto-detected
  from the selected text (CJK → ja, Spanish markers → es, Latin → en).
- Three strategies: `Online → Local`, `Online only`, `Local only`.
- **Field mapping per note type**: define which field to use per
  note type and an ordered fallback list of alternative names
  (`Significado`, `Meaning`, `Back`…). The first one that exists on
  the current card is used; you can also override the target field
  per-use from the popup.
- **Offline support** via Yomichan/Yomitan ZIPs (JMdict, Jitendex,
  Daijirin, Shinmeikai, etc.). They are indexed on Anki startup.
- *Replace* / *Append* modes, configurable globally and per-use.
- Asynchronous: HTTP requests don't freeze the UI.
- Menu actions **Search selection now** (`Ctrl+Shift+J`) and
  **Pick definition (popup)…** (`Ctrl+Shift+K`) as manual fallbacks.
- **Fully localized UI** — menus, dialogs and tooltips follow Anki's
  UI language (English / Spanish / Japanese; other locales fall back
  to English).

## Installation

### Option A — From release (.ankiaddon)

1. Download the latest `.ankiaddon` from the [releases page](../../releases).
2. In Anki: `Tools → Add-ons → Install from file…` and pick the
   `.ankiaddon`.
3. Restart Anki.

### Option B — From source

```bash
git clone <REPO-URL> anki-jisho-lookup
cd anki-jisho-lookup
python3 build.py
# Produces dist/jisho_lookup-<version>.ankiaddon
```

Then install it in Anki as in option A.

### Option C — Symlink for development

Copy or symlink `src/jisho_lookup/` into Anki's `addons21` folder:

| OS       | Path                                                        |
|----------|-------------------------------------------------------------|
| Windows  | `%APPDATA%\Anki2\addons21\jisho_lookup`                     |
| macOS    | `~/Library/Application Support/Anki2/addons21/jisho_lookup` |
| Linux    | `~/.local/share/Anki2/addons21/jisho_lookup`                |

## Usage

1. Open any deck and start reviewing.
2. Drag with the mouse over a word to select it.
3. Press one of the two shortcuts:
   - **`Ctrl+S`** — insert every sense directly.
   - **`Ctrl+Shift+S`** — opens the popup: pick which sense(s) to
     insert (Ctrl/Shift+click for multi-select, Enter to accept).
4. You'll see a "Searching…" tooltip and, once done, a confirmation
   with the field that got filled and the source (`Jisho` /
   `Wiktionary` / `local dictionary` / `mixed`).

If nothing happens, use `Ctrl+Shift+J` / `Ctrl+Shift+K` (menu
**Tools → Jisho Lookup**) as a manual fallback to rule out
shortcut-capture issues.

## Configuration

`Tools → Jisho Lookup → Configuration…`

- **Shortcut**: any combo like `Ctrl+S`, `Ctrl+Shift+J`, `Alt+D`.
- **Strategy**:
  - `jisho_then_local` (recommended) — try online, fall back to local.
  - `local_only` — fully offline.
  - `jisho_only` — online only, no fallback.
- **Default language pair**: `ja_en`, `en_ja`, `es_en`, `en_es`. Picked
  in the configuration and determines which online source is used
  (Jisho for Japanese pairs, Wiktionary for Spanish pairs).
- **Auto-detect language if the default pair returns nothing**: when
  enabled, the quick shortcut retries with the auto-detected pair
  whenever the default pair comes up empty.
- **Field mapping per note type**: a table of rows
  `notetype → list of field names`. The special `_default` row is
  used when the current notetype has no rule of its own.
- **Local dictionaries**: a checklist of ZIPs found in
  `src/jisho_lookup/dictionaries/` (or the equivalent folder of the
  installed add-on). If none are checked, all are considered active.
- **Overwrite** / **Append**: behaviour when the target field already
  has content.
- **Include reading** / **Include grammar tags**: formatting of the
  inserted result.

Example `note_type_field_map`:

```json
{
    "Japanese":                 ["Significado"],
    "Core 2k/6k Optimized":     ["Meaning", "Vocabulary-English"],
    "Basic":                    ["Back"],
    "_default":                 ["Significado", "Meaning", "Definición"]
}
```

## Local dictionaries (Yomichan / Yomitan)

Drop your ZIPs into `src/jisho_lookup/dictionaries/` (or
`.../addons21/jisho_lookup/dictionaries/` once installed):

```
dictionaries/
    jmdict_english.zip
    jitendex.zip
    daijirin.zip
```

You can find them through the Yomitan community. The add-on indexes
them on Anki startup, supports both the classic format (`glossary`
as a list of strings) and the modern `structured-content`, and
queries every active dictionary simultaneously.

## Interface language

The UI auto-detects Anki's own language setting
(`Tools → Preferences → Interface language`):

- English locales → English UI
- `es`, `es_ES`, `es_MX`, etc. → Spanish UI
- `ja`, `ja_JP` → Japanese UI
- Any other locale → English UI (safe default)

The brand name "Jisho Lookup" is kept across all three languages.

## Development

### Repo layout

```
├── src/
│   └── jisho_lookup/        # add-on source
│       ├── __init__.py
│       ├── manifest.json
│       ├── config.json
│       ├── config.md
│       ├── i18n.py          # UI translations (en / es / ja)
│       ├── reviewer.py      # reviewer hook + keydown JS
│       ├── lookup.py        # search → field orchestration
│       ├── lang.py          # language pairs + auto-detect
│       ├── jisho_client.py  # HTTP client for Jisho (ja↔en)
│       ├── wiktionary_client.py  # HTTP client for Wiktionary (es↔en, en→ja)
│       ├── yomitan_reader.py# Yomichan/Yomitan ZIP parser
│       ├── picker_dialog.py # Qt picker popup
│       ├── config_dialog.py # Qt config dialog
│       └── dictionaries/    # user ZIPs (gitignored)
├── build.py                 # bundles src/ → dist/*.ankiaddon
├── .github/workflows/
│   └── release.yml          # CI: attach .ankiaddon to each release tag
├── README.md                # English (primary)
├── README.es.md             # Spanish
├── README.ja.md             # Japanese
├── CHANGELOG.md
└── LICENSE
```

### Building the package

```bash
python3 build.py
# dist/jisho_lookup-<version>.ankiaddon
```

### Publishing a release

```bash
git tag v1.3.0
git push origin v1.3.0
```

The `.github/workflows/release.yml` workflow builds the `.ankiaddon`
and attaches it to the GitHub release automatically.

## Known limitations

- Jisho's API is public but unofficial: it may rate-limit or change.
  That's why local fallback exists.
- The shortcut is captured via JavaScript inside the WebView (needed
  because `QWebEngineView` eats keyboard events before `QShortcut`
  gets them), so it only works during review — not in the editor nor
  in the browser.
- Yomichan/Yomitan dictionaries are loaded into memory on first use;
  with many large dictionaries the first lookup can take 1–3 s.

## License

MIT — see [LICENSE](./LICENSE).
