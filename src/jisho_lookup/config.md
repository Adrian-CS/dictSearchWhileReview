# Jisho Lookup — Configuración

Selecciona una palabra mientras revisas una tarjeta y pulsa el atajo (por defecto **Ctrl+S**) para buscar su definición automáticamente y rellenar un campo configurable. Con **Ctrl+Shift+S** se abre un popup donde eliges campo, modo de escritura, idioma y qué acepciones insertar.

## Opciones

- **shortcut**: atajo para inserción automática (inserta todas las acepciones).
- **picker_shortcut**: atajo para abrir el *popup* (por defecto `Ctrl+Shift+S`).
- **picker_multi_select**: si `true` permite seleccionar varias acepciones a la vez en el popup.
- **strategy**: orden de búsqueda.
  - `jisho_then_local` — intenta online, si falla usa diccionarios locales (recomendado).
  - `local_only` — solo diccionarios locales (offline).
  - `jisho_only` — solo online, sin fallback.
- **language_pair**: par de idioma por defecto. Valores válidos:
  - `ja_en` — Japonés → Inglés (fuente online: Jisho)
  - `en_ja` — Inglés → Japonés (fuente online: Jisho, invertido)
  - `es_en` — Español → Inglés (fuente online: Wiktionary)
  - `en_es` — Inglés → Español (fuente online: Wiktionary)
- **language_pair_auto_fallback**: si `true`, el atajo rápido re-intenta con el par auto-detectado cuando el par por defecto no devuelve resultados. La detección usa el script Unicode del texto (kana/kanji → ja, marcas españolas `¿¡áéíóúñ` → es, el resto → en).
- **jisho_timeout_seconds** / **wiktionary_timeout_seconds**: timeouts HTTP.
- **max_senses**: máximo de acepciones a incluir en el resultado.
- **include_reading**: añadir lectura en kana (ej: `食べる【たべる】`).
- **include_parts_of_speech**: añadir marca tipo `[Ichidan verb, transitive]`.
- **overwrite_existing** / **append_mode**: comportamiento por defecto al escribir en un campo que ya tiene contenido. En el popup se puede cambiar por-uso.
- **note_type_field_map**: qué campo usar por cada tipo de nota. La clave es el nombre del notetype y el valor es una lista ordenada de nombres de campo candidatos (se usa el primero que exista). La clave especial `_default` es el fallback. En el popup puedes elegir también un campo distinto al preconfigurado.
- **enabled_local_dicts**: lista de nombres (sin `.zip`) de diccionarios Yomichan/Yomitan a cargar. Deja vacío para cargar **todos** los ZIPs de la carpeta `dictionaries/`.
- **show_tooltip_on_success** / **show_tooltip_on_error**: avisos tipo globo.

## Pares de idioma y fuentes

| Par           | Fuente online   | Fallback local |
|---------------|-----------------|----------------|
| `ja_en`       | Jisho           | Yomichan/Yomitan |
| `en_ja`       | Jisho (inverso) | Yomichan/Yomitan |
| `es_en`       | Wiktionary `en` | *(tus ZIPs si aplican)* |
| `en_es`       | Wiktionary `es` | *(tus ZIPs si aplican)* |

## Diccionarios locales (fallback offline)

Copia tus ZIPs de Yomichan/Yomitan dentro de la carpeta `dictionaries/` del add-on:

```
Anki/addons21/jisho_lookup/dictionaries/
    jmdict_english.zip
    jitendex.zip
    ...
```

Pueden descargarse desde la comunidad de Yomitan (JMdict, Jitendex, etc.). El add-on los indexa al arrancar y los consulta si la fuente online no responde.

## Ejemplo `note_type_field_map`

```json
"note_type_field_map": {
    "Japanese": ["Significado"],
    "Core 2k/6k Optimized Japanese Vocabulary": ["Meaning", "Vocabulary-English"],
    "Mi plantilla personal": ["Definición", "Significado"],
    "_default": ["Significado", "Meaning"]
}
```

Abre **Herramientas → Jisho Lookup → Configuración** para editarlo con un diálogo Qt.
