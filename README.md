# Jisho Lookup — Add-on para Anki

Selecciona una palabra durante la revisión de una tarjeta, pulsa un atajo y
el add-on busca su definición y la inserta automáticamente en un campo
configurable. Soporta **cuatro pares de idioma** (ja↔en, es↔en) con
[Jisho](https://jisho.org/) para japonés y [Wiktionary](https://wiktionary.org/)
para español, con *fallback* a **diccionarios locales Yomichan / Yomitan**
que tú mismo proporciones.

Compatible con **Anki 2.1.60+** (Qt6).

## Características

- **Dos atajos configurables** sobre la palabra seleccionada en el reviewer:
  - `Ctrl+S` (por defecto) — inserción rápida: mete todas las acepciones.
  - `Ctrl+Shift+S` (por defecto) — **popup de selección**: elige campo,
    modo (sustituir / añadir), idioma y qué acepciones insertar.
- **Pares de idioma**: `ja→en`, `en→ja`, `es→en`, `en→es`. Se elige uno por
  defecto en la configuración y puede cambiarse por-uso en el popup.
- **Auto-detección** de idioma en el atajo rápido: si el par por defecto
  no devuelve nada, re-intenta con el par auto-detectado (CJK → ja,
  marcas españolas → es, Latin → en).
- Tres estrategias: `Online → Local`, `Solo online`, `Solo local`.
- **Mapeo de campos por tipo de nota**: define qué campo usar en cada
  notetype y una lista ordenada de nombres alternativos (`Significado`,
  `Meaning`, `Definición`…). Se usa el primero que exista en la tarjeta.
  Desde el popup puedes elegir cualquier otro campo por-uso.
- **Soporte offline** cargando ZIPs Yomichan/Yomitan (JMdict, Jitendex,
  Daijirin, Shinmeikai, etc.). Se indexan al arrancar Anki.
- Modos *sustituir* / *append* configurables globalmente y por-uso en el popup.
- Asíncrono: las peticiones HTTP no congelan la UI.
- Acciones de menú **Buscar selección ahora** (`Ctrl+Shift+J`) y
  **Elegir definición (popup)…** (`Ctrl+Shift+K`) como alternativas manuales.

## Instalación

### Opción A — Desde release (.ankiaddon)

1. Descarga el último `.ankiaddon` de la [página de releases](../../releases).
2. En Anki: `Herramientas → Add-ons → Instalar desde archivo…` y selecciona
   el `.ankiaddon`.
3. Reinicia Anki.

### Opción B — Desde código

```bash
git clone <URL-DEL-REPO> anki-jisho-lookup
cd anki-jisho-lookup
python3 build.py
# Genera dist/jisho_lookup-<version>.ankiaddon
```

Luego instálalo desde Anki como en la opción A.

### Opción C — Enlace simbólico para desarrollo

Copia o enlaza `src/jisho_lookup/` dentro de la carpeta `addons21` de Anki:

| Sistema  | Ruta                                                  |
|----------|-------------------------------------------------------|
| Windows  | `%APPDATA%\Anki2\addons21\jisho_lookup`               |
| macOS    | `~/Library/Application Support/Anki2/addons21/jisho_lookup` |
| Linux    | `~/.local/share/Anki2/addons21/jisho_lookup`          |

## Uso

1. Abre cualquier mazo y empieza a revisar.
2. Arrastra con el ratón sobre una palabra japonesa para seleccionarla.
3. Pulsa uno de los dos atajos:
   - **`Ctrl+S`** — inserción directa de todas las acepciones.
   - **`Ctrl+Shift+S`** — abre un popup con la lista y eliges cuál(es)
     insertar (Ctrl/Shift+clic para multi-selección, Enter para aceptar).
4. Verás un aviso "Buscando…" y, al terminar, un globo confirmando el campo
   rellenado y la fuente (`Jisho` / `diccionario local` / `mezcla`).

Si nada ocurre, usa `Ctrl+Shift+J` / `Ctrl+Shift+K` (menú **Herramientas →
Jisho Lookup**) como alternativa manual y para descartar problemas de atajo.

## Configuración

`Herramientas → Jisho Lookup → Configuración…`

- **Atajo**: cualquier combinación tipo `Ctrl+S`, `Ctrl+Shift+J`, `Alt+D`.
- **Estrategia**:
  - `jisho_then_local` (recomendada) — prueba online, fallback local.
  - `local_only` — todo offline.
  - `jisho_only` — solo online, sin fallback.
- **Par de idioma (por defecto)**: `ja_en`, `en_ja`, `es_en`, `en_es`. Se
  elige en la configuración y determina qué fuente online se usa
  (Jisho para pares japoneses, Wiktionary para pares españoles).
- **Auto-detectar idioma si el par por defecto no da resultados**: si
  está activo, el atajo rápido re-intenta con el par auto-detectado
  cuando el par por defecto no encuentra nada.
- **Mapeo de campos por tipo de nota**: tabla con filas
  `notetype → lista de nombres de campo`. La fila especial `_default` se
  usa cuando el notetype actual no tiene regla propia.
- **Diccionarios locales**: lista con checkboxes de los ZIPs encontrados
  en `src/jisho_lookup/dictionaries/` (o en la carpeta equivalente del
  add-on instalado). Si ninguno está marcado se interpreta como "todos".
- **Sobrescribir** / **Añadir al final**: comportamiento cuando el campo
  destino ya tiene contenido.
- **Incluir lectura** / **Incluir categorías gramaticales**: formato del
  resultado insertado.

Ejemplo de `note_type_field_map`:

```json
{
    "Japanese":                 ["Significado"],
    "Core 2k/6k Optimized":     ["Meaning", "Vocabulary-English"],
    "Basic":                    ["Back"],
    "_default":                 ["Significado", "Meaning", "Definición"]
}
```

## Diccionarios locales (Yomichan / Yomitan)

Coloca tus ZIPs dentro de `src/jisho_lookup/dictionaries/` (o
`.../addons21/jisho_lookup/dictionaries/` una vez instalado):

```
dictionaries/
    jmdict_english.zip
    jitendex.zip
    daijirin.zip
```

Puedes obtenerlos desde la comunidad de Yomitan. El add-on indexa al
arrancar Anki, soporta tanto el formato clásico (`glossary` como lista
de strings) como el moderno `structured-content`, y consulta todos los
activos simultáneamente.

## Desarrollo

### Estructura del repo

```
├── src/
│   └── jisho_lookup/        # código fuente del add-on
│       ├── __init__.py
│       ├── manifest.json
│       ├── config.json
│       ├── config.md
│       ├── reviewer.py      # hook del reviewer + keydown JS
│       ├── lookup.py        # orquestador búsqueda → campo
│       ├── lang.py          # pares de idioma + auto-detección
│       ├── jisho_client.py  # cliente HTTP a Jisho (ja↔en)
│       ├── wiktionary_client.py  # cliente HTTP a Wiktionary (es↔en)
│       ├── yomitan_reader.py# parser de ZIPs Yomichan/Yomitan
│       ├── picker_dialog.py # popup Qt de selección
│       ├── config_dialog.py # diálogo Qt de configuración
│       └── dictionaries/    # ZIPs de usuario (gitignored)
├── build.py                 # empaqueta src/ → dist/*.ankiaddon
├── .github/workflows/
│   └── release.yml          # CI: adjunta .ankiaddon a cada release tag
├── README.md
├── CHANGELOG.md
└── LICENSE
```

### Construir el paquete

```bash
python3 build.py
# dist/jisho_lookup-1.0.1.ankiaddon
```

### Publicar en GitHub por primera vez

Desde la raíz del proyecto:

```bash
git init -b main
git add -A
git commit -m "Initial commit: Jisho Lookup v1.0.1"

# Sustituye por la URL de tu repo vacío creado en GitHub
git remote add origin https://github.com/<usuario>/<repo>.git
git push -u origin main
```

### Publicar una release

```bash
git tag v1.0.1
git push origin v1.0.1
```

El workflow `.github/workflows/release.yml` construye el `.ankiaddon` y lo
adjunta automáticamente al release de GitHub.

## Limitaciones conocidas

- La API de Jisho es pública pero no oficial: puede rate-limitar o cambiar.
  Por eso existe el fallback local.
- El atajo se captura vía JavaScript dentro del WebView (necesario porque
  `QWebEngineView` absorbe los eventos de teclado antes que `QShortcut`),
  así que sólo funciona durante la revisión, no en el editor ni en el browser.
- Los diccionarios Yomichan/Yomitan se cargan en memoria al primer uso;
  con muchos diccionarios grandes puede costar 1-3 s la primera búsqueda.

## Licencia

MIT — ver [LICENSE](./LICENSE).
