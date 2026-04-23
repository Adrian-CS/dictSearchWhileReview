# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y versionado con [SemVer](https://semver.org/lang/es/).

## [1.3.0] - 2026-04-23

### Añadido
- **UI multilingüe (en / es / ja)**: toda la interfaz del add-on —
  menú de `Herramientas`, diálogo de configuración, popup de
  selección y tooltips del reviewer — detecta el idioma de Anki
  (`anki.lang.current_lang`, con fallbacks) y se muestra en inglés,
  español o japonés. Cualquier otro idioma cae a inglés.
- Nuevo módulo `i18n.py` con un catálogo central de strings y la
  función `tr()` para acceder a ellos. `lang.pair_label` consulta
  ahora este catálogo (`pair.ja_en`, `pair.en_ja`, etc.) en lugar
  de llevar las etiquetas hardcoded.
- **README trilingüe**: `README.md` (inglés, primario) + `README.es.md`
  + `README.ja.md`, con cabecera de cambio de idioma en cada uno.

### Cambiado
- `__init__.py`, `config_dialog.py`, `picker_dialog.py` y `reviewer.py`
  pasan todos sus strings visibles por `tr()`. El nombre propio
  "Jisho Lookup" se mantiene sin traducir en los tres idiomas.
- El nombre en `manifest.json` pasa a estar en inglés
  ("Jisho Lookup (Ctrl+S during review)") porque el Add-on Manager
  de Anki no lo traduce.

## [1.2.3] - 2026-04-23

### Arreglado
- **`en→es` devolvía vacío casi siempre**: el backend parseaba
  `{{lengua|en}}` en es.wiktionary, pero esa sección rara vez existe
  (es.wiktionary no cubre la mayoría de palabras inglesas y, cuando lo
  hace, usa plantillas de traducción, no `;1: …`). Ahora se lee la
  sección `====Translations====` de en.wiktionary y se extraen las
  plantillas `{{t|es|…}}`, `{{t+|…}}`, `{{t-|…}}` agrupadas por POS y
  por *gloss* (`{{trans-top|…}}`). El parser antiguo queda como
  fallback.
- **`en→ja` reinyectaba el inglés**: al elegir 空き como traducción de
  "space", la fila del picker y el HTML insertado incluían la glosa
  inglesa de Jisho (`[Noun] space, room`), que es circular porque el
  usuario acaba de buscar "space". Ahora `format_picked_choices` omite
  esa glosa cuando el par es `en→ja`; la palabra japonesa + lectura
  (+ POS si está activo) es lo único que se guarda en la carta.

### Añadido
- **Toggle "Gramática" en el popup**: checkbox que sobreescribe
  `include_parts_of_speech` sólo para esa invocación del diálogo,
  tanto en la lista visible como en el HTML que se inserta. Útil
  cuando el global está encendido pero para esta carta concreta no
  quieres el `[Noun]` / `[Verb]`, o viceversa.

## [1.2.2] - 2026-04-23

### Arreglado
- **El popup no aplicaba el auto-detect al abrirse**: si el par global era
  `ja→en` y seleccionabas una palabra inglesa, el popup buscaba con
  `ja→en` y mostraba entradas japonesas con glosa en inglés, lo que
  parecía circular ("space" en las definiciones de "space"). Ahora, si
  `language_pair_auto_fallback` está activo, el popup abre con el par
  auto-detectado al igual que el atajo rápido.
- **Jisho en dirección inversa devuelve múltiples candidatos**: para
  `en→ja` Jisho devuelve una entrada por cada palabra japonesa
  candidata (空き, スペース, 場所…). El código anterior sólo iteraba la
  primera entrada, perdiendo el resto. Ahora `entries_to_choices`
  itera **todas** las entradas.
- Las filas del picker muestran la palabra japonesa + lectura al
  principio (ej. `空き 【あき】   [Noun] space, room`), así las listas
  de `en→ja` se leen como listas de candidatos de traducción.
- `format_picked_choices` adapta el HTML insertado: si eliges varias
  acepciones de una misma palabra, cabecera única + lista de senses;
  si eliges acepciones de palabras distintas, cada item incluye su
  propia palabra+lectura.

## [1.2.1] - 2026-04-23

### Arreglado
- **La carta no se refrescaba** tras insertar la definición: había que
  volver al deck y re-entrar para ver el cambio. Causa: Anki cachea el
  HTML renderizado en `Card._render_output`. Ahora invalidamos el caché
  y recargamos la carta desde la BD antes de re-dibujar.
- **El combo de idioma del popup** hacía la re-búsqueda en el hilo
  principal, bloqueando la UI durante la petición HTTP. Ahora se
  ejecuta en background (vía `mw.taskman.run_in_background`) con
  placeholder "Cargando definiciones…" mientras dura; también descarta
  resultados obsoletos si el usuario cambia varias veces seguidas.

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
