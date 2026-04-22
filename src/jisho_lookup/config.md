# Jisho Lookup — Configuración

Selecciona una palabra japonesa mientras revisas una tarjeta y pulsa el atajo (por defecto **Ctrl+S**) para buscar su definición automáticamente y rellenar un campo configurable.

## Opciones

- **shortcut**: atajo para inserción automática (inserta todas las acepciones).
- **picker_shortcut**: atajo para abrir el *popup* y elegir manualmente qué acepciones insertar (por defecto `Ctrl+Shift+S`).
- **picker_multi_select**: si `true` permite seleccionar varias acepciones a la vez en el popup.
- **strategy**: orden de búsqueda.
  - `jisho_then_local` — intenta Jisho online, si falla usa diccionarios locales (recomendado).
  - `local_only` — solo diccionarios locales (offline).
  - `jisho_only` — solo Jisho.
- **jisho_timeout_seconds**: timeout de la petición HTTP a Jisho.
- **max_senses**: máximo de acepciones a incluir en el resultado.
- **include_reading**: añadir lectura en kana (ej: `食べる【たべる】`).
- **include_parts_of_speech**: añadir marca tipo `[Ichidan verb, transitive]`.
- **overwrite_existing**: si `true`, sobrescribe aunque el campo ya tenga contenido.
- **append_mode**: si `true`, añade al final del campo en vez de reemplazar.
- **note_type_field_map**: qué campo usar por cada tipo de nota. La clave es el nombre del notetype y el valor es una lista de posibles nombres de campo (se usa el primero que exista). La clave especial `_default` es el fallback.
- **enabled_local_dicts**: lista de nombres (sin `.zip`) de diccionarios Yomichan/Yomitan a cargar. Deja vacío para cargar **todos** los ZIPs de la carpeta `dictionaries/`.
- **show_tooltip_on_success** / **show_tooltip_on_error**: avisos tipo globo.

## Diccionarios locales (fallback offline)

Copia tus ZIPs de Yomichan/Yomitan dentro de la carpeta `dictionaries/` del add-on:

```
Anki/addons21/jisho_lookup/dictionaries/
    jmdict_english.zip
    jitendex.zip
    ...
```

Pueden descargarse desde la comunidad de Yomitan (JMdict, Jitendex, etc.). El add-on los indexa al arrancar y los consulta si Jisho no responde.

## Ejemplo `note_type_field_map`

```json
"note_type_field_map": {
    "Japanese": ["Significado"],
    "Core 2k/6k Optimized Japanese Vocabulary": ["Meaning", "Vocabulary-English"],
    "Mi plantilla personal": ["Definición", "Significado"],
    "_default": ["Significado", "Meaning"]
}
```

Abre **Herramientas → Jisho Lookup → Configurar mapeo de campos** para editarlo con un diálogo.
