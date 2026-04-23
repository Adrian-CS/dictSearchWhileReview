# Jisho Lookup — Anki アドオン

**言語:** [English](./README.md) · [Español](./README.es.md) · [日本語](./README.ja.md)

カードの復習中に語を選択してショートカットを押すと、アドオンが
定義を取得して設定可能なフィールドへ自動で書き込みます。日本語は
[Jisho](https://jisho.org/)、スペイン語は
[Wiktionary](https://wiktionary.org/) を使い、**4つの言語ペア**
(ja↔en, es↔en) に対応。オンラインが使えない場合は自分で用意した
**Yomichan / Yomitan のローカル辞書 (ZIP)** にフォールバックします。

アドオンの UI は **英語・スペイン語・日本語** に対応しており、
Anki 本体の UI 言語に合わせて自動で切り替わります。

対応: **Anki 2.1.60+** (Qt6)。

## 機能

- 復習中に選択した語に対して **2つのショートカット** を設定可能:
  - `Ctrl+S` (既定) — クイック挿入: すべての意味を一度に入力。
  - `Ctrl+Shift+S` (既定) — **選択ポップアップ**: フィールド、
    モード (置き換え / 追記)、言語、品詞タグの表示、および挿入する
    意味を選択できます。
- **言語ペア**: `ja→en`, `en→ja`, `es→en`, `en→es`。設定で既定ペア
  を選び、ポップアップからはその場で切り替え可能。
- **クイックショートカットの自動検出**: 既定のペアで結果が無い場合、
  選択テキストから判定したペアで再試行します (CJK → ja、
  スペイン語特有の記号 → es、ラテン文字 → en)。
- 3つの方式: `オンライン → ローカル`、`オンラインのみ`、
  `ローカルのみ`。
- **ノートタイプごとのフィールドマッピング**: ノートタイプごとに
  使うフィールドと代替名の順序リスト (`Significado`, `Meaning`,
  `Back` など) を定義できます。カードに存在する最初のものが使われ、
  ポップアップから個別に上書きもできます。
- **オフライン対応**: Yomichan/Yomitan の ZIP (JMdict, Jitendex,
  大辞林、新明解など) を読み込みます。Anki 起動時にインデックス化。
- *置き換え* / *追記* モードはグローバルにもポップアップからも
  設定可能。
- 非同期: HTTP リクエストで UI は固まりません。
- メニュー操作 **選択した語をいま検索 (クイック)**
  (`Ctrl+Shift+J`) と **定義を選択 (ポップアップ)…**
  (`Ctrl+Shift+K`) が手動フォールバックとして使えます。
- **UI の完全ローカライズ** — メニュー、ダイアログ、ツールチップ
  はすべて Anki の UI 言語に従います (英語 / スペイン語 / 日本語。
  その他の言語は英語にフォールバック)。

## インストール

### A — リリース (.ankiaddon) から

1. [リリースページ](../../releases) から最新の `.ankiaddon` を
   ダウンロードします。
2. Anki で `ツール → アドオン → ファイルからインストール…` を選び、
   `.ankiaddon` を指定します。
3. Anki を再起動します。

### B — ソースから

```bash
git clone <REPO-URL> anki-jisho-lookup
cd anki-jisho-lookup
python3 build.py
# dist/jisho_lookup-<version>.ankiaddon が生成されます
```

その後、A と同じように Anki からインストールします。

### C — 開発用にシンボリックリンク

`src/jisho_lookup/` を Anki の `addons21` フォルダへコピーまたは
シンボリックリンクします:

| OS       | パス                                                        |
|----------|-------------------------------------------------------------|
| Windows  | `%APPDATA%\Anki2\addons21\jisho_lookup`                     |
| macOS    | `~/Library/Application Support/Anki2/addons21/jisho_lookup` |
| Linux    | `~/.local/share/Anki2/addons21/jisho_lookup`                |

## 使い方

1. 任意のデッキを開いて復習を始めます。
2. マウスで語を選択します。
3. 2つのショートカットのいずれかを押します:
   - **`Ctrl+S`** — すべての意味を直接挿入。
   - **`Ctrl+Shift+S`** — ポップアップを開き、挿入する意味を選択
     (Ctrl/Shift+クリックで複数選択、Enter で決定)。
4. 「検索中…」のツールチップが出て、完了するとフィールド名と
   情報源 (`Jisho` / `Wiktionary` / `ローカル辞書` / `複数のソース`)
   が表示されます。

何も起きない場合は `Ctrl+Shift+J` / `Ctrl+Shift+K` (メニュー
**ツール → Jisho Lookup**) を手動フォールバックとして使い、
ショートカット取得の問題を切り分けてください。

## 設定

`ツール → Jisho Lookup → 設定…`

- **ショートカット**: `Ctrl+S`、`Ctrl+Shift+J`、`Alt+D` などの
  任意の組み合わせ。
- **方式**:
  - `jisho_then_local` (推奨) — オンラインを試して、失敗したら
    ローカル。
  - `local_only` — 完全オフライン。
  - `jisho_only` — オンラインのみ、フォールバック無し。
- **既定の言語ペア**: `ja_en`、`en_ja`、`es_en`、`en_es`。設定画面
  で選択し、どのオンラインソースを使うかを決めます
  (日本語ペアは Jisho、スペイン語ペアは Wiktionary)。
- **既定のペアで見つからない場合は言語を自動検出**: 有効にすると、
  既定のペアで結果が無かった時に自動検出したペアで再試行します。
- **ノートタイプごとのフィールドマッピング**:
  `ノートタイプ → フィールド名のリスト` の表。特別な `_default`
  行はノートタイプ固有のルールが無い場合に使われます。
- **ローカル辞書**: `src/jisho_lookup/dictionaries/` (インストール後
  は同等のフォルダ) にある ZIP のチェックリスト。何も選択しない場合
  はすべて有効として扱われます。
- **上書き** / **追記**: 挿入先フィールドに既に内容がある場合の
  動作。
- **読み仮名を含める** / **品詞タグを含める**: 挿入結果の書式。

`note_type_field_map` の例:

```json
{
    "Japanese":                 ["Significado"],
    "Core 2k/6k Optimized":     ["Meaning", "Vocabulary-English"],
    "Basic":                    ["Back"],
    "_default":                 ["Significado", "Meaning", "Definición"]
}
```

## ローカル辞書 (Yomichan / Yomitan)

ZIP を `src/jisho_lookup/dictionaries/` (インストール後は
`.../addons21/jisho_lookup/dictionaries/`) に置きます:

```
dictionaries/
    jmdict_english.zip
    jitendex.zip
    daijirin.zip
```

ZIP は Yomitan コミュニティから入手できます。アドオンは Anki 起動時
にインデックスを作り、従来形式 (`glossary` が文字列リスト) と新しい
`structured-content` 形式の両方に対応し、有効な辞書を同時に検索
します。

## UI 言語

UI は Anki 本体の言語設定
(`ツール → 環境設定 → インターフェース言語`) を自動検出します:

- `en`, `en_US` など → 英語 UI
- `es`, `es_ES`, `es_MX` など → スペイン語 UI
- `ja`, `ja_JP` → 日本語 UI
- その他の言語 → 英語 UI (安全なフォールバック)

固有名詞 "Jisho Lookup" は 3言語ともそのまま使用します。

## 開発

### リポジトリ構成

```
├── src/
│   └── jisho_lookup/        # アドオンのソース
│       ├── __init__.py
│       ├── manifest.json
│       ├── config.json
│       ├── config.md
│       ├── i18n.py          # UI 翻訳 (en / es / ja)
│       ├── reviewer.py      # reviewer フック + keydown JS
│       ├── lookup.py        # 検索 → フィールド書き込みの統括
│       ├── lang.py          # 言語ペアと自動検出
│       ├── jisho_client.py  # Jisho HTTP クライアント (ja↔en)
│       ├── wiktionary_client.py  # Wiktionary クライアント (es↔en, en→ja)
│       ├── yomitan_reader.py# Yomichan/Yomitan ZIP パーサ
│       ├── picker_dialog.py # Qt 選択ポップアップ
│       ├── config_dialog.py # Qt 設定ダイアログ
│       └── dictionaries/    # ユーザの ZIP (gitignore)
├── build.py                 # src/ を dist/*.ankiaddon に固める
├── .github/workflows/
│   └── release.yml          # CI: 各リリースタグに .ankiaddon を添付
├── README.md                # 英語 (主)
├── README.es.md             # スペイン語
├── README.ja.md             # 日本語
├── CHANGELOG.md
└── LICENSE
```

### パッケージのビルド

```bash
python3 build.py
# dist/jisho_lookup-<version>.ankiaddon
```

### リリースの公開

```bash
git tag v1.3.0
git push origin v1.3.0
```

`.github/workflows/release.yml` のワークフローが `.ankiaddon` を
ビルドして、GitHub のリリースに自動で添付します。

## 既知の制限

- Jisho API は公開されていますが非公式のため、レート制限や仕様変更の
  可能性があります。そのためローカルフォールバックがあります。
- ショートカットは WebView 内の JavaScript でキャプチャしています
  (`QWebEngineView` がキーイベントを `QShortcut` より先に消費する
  ため)。したがって、復習中のみ動作し、エディタやブラウザーでは
  動作しません。
- Yomichan/Yomitan 辞書は初回使用時にメモリへ読み込まれます。
  辞書が多く大きい場合、最初の検索に 1〜3 秒かかることがあります。

## ライセンス

MIT — [LICENSE](./LICENSE) を参照。
