# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y versionado con [SemVer](https://semver.org/lang/es/).

## [1.2.0] - 2026-04-23

### Añadido
- **Pares de idioma**: `ja→en`, `en→ja`, `es→en`, `en→es`. Configurable desde
  el diálogo de configuración y desde el propio popup.
- **Cliente Wiktionary** (`wiktionary_client.py`) para los pares que
  incluyen español (`es↔en`). Usa la REST API pública
  `*.wiktionary.org/api/rest_v1/page/definition/...`.
- **Auto-detección de idioma** en el atajo rápido: si el par global no
  devuelve nada, el add-on re-intenta con el par auto-detectado a partir
  del texto seleccionado (CJK → ja, marcas españolas `¿¡áéíóúñ` → es,
  el resto → en). Controlable con `language_pair_auto_fallback`.
- **Popup ampliado**: ahora incluye (fila superior) combo de **campo
  destino**, radios **Sustituir / Añadir** y combo de **idioma** que
  recarga la lista en vivo al cambiar.
- Módulo `lang.py` con definiciones de pares y heurísticas de detección.
- Nuevos campos en `config.json`: `language_pair`,
  `language_pair_auto_fallback`, `wiktionary_timeout_seconds`.

### Cambiado
- `lookup.do_lookup` y `lookup.collect_choices` aceptan un parámetro
  `pair` opcional. Nueva función `lookup.do_lookup_auto` para el atajo
  rápido con fallback auto-detect.
- La fuente "Jisho" en los tooltips puede ser "Wiktionary" o mezcla según
  el par elegido.

## [1.1.0] - 2026-04-23

### Añadido
- **Segundo atajo con popup de selección** (por defecto `Ctrl+Shift+S`):
  abre un diálogo Qt con todas las acepciones encontradas (Jisho + locales)
  y permite elegir cuál(es) insertar. Multi-selección activada por defecto
  (Ctrl/Shift+clic), configurable.
- Nueva acción de menú **Elegir definición (popup)…** (atajo fijo
  `Ctrl+Shift+K`) como alternativa manual al atajo configurable.
- Nuevos campos en `config.json`: `picker_shortcut`, `picker_multi_select`.
- Módulo `picker_dialog.py` con diálogo Qt reutilizable.
- Helpers `entries_to_choices()` en `jisho_client` y `yomitan_reader`, y
  `collect_choices()` / `format_picked_choices()` en `lookup.py`.

### Cambiado
- El listener JS ahora soporta múltiples atajos simultáneos con despacho
  por `kind` (`run` / `pick`).
- El diálogo de configuración expone ambos atajos y el checkbox de
  multi-selección.

## [1.0.1] - 2026-04-22

### Arreglado
- El atajo no se disparaba dentro del reviewer porque `QWebEngineView` consume
  los eventos de teclado antes que `QShortcut`. Ahora el listener se instala
  vía JavaScript directamente en el WebView y se comunica con Python mediante
  `pycmd` + `webview_did_receive_js_message`.

### Añadido
- Acción de menú **Herramientas → Jisho Lookup → Buscar selección ahora**
  (atajo fijo `Ctrl+Shift+J`) como alternativa manual al atajo configurable
  y como ayuda de diagnóstico.
- Re-inyección automática del listener al cambiar de estado al reviewer.

## [1.0.0] - 2026-04-22

### Añadido
- Búsqueda de la palabra seleccionada en Jisho (`jisho.org/api/v1/search/words`)
  al pulsar `Ctrl+S` durante la revisión.
- Fallback a diccionarios locales en formato Yomichan / Yomitan (ZIP) cuando
  Jisho no responde o se usa la estrategia `local_only`.
- Mapeo configurable de campos por tipo de nota con fallback `_default`.
- Diálogo Qt de configuración con selección de diccionarios activos.
- Empaquetado como `.ankiaddon` compatible con Anki 2.1.60+.
