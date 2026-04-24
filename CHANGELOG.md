# Changelog

Formato basado en [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/)
y versionado con [SemVer](https://semver.org/lang/es/).

## [1.4.5] - 2026-04-24

### Cambiado
- **`append_mode = true` por defecto** en instalaciones nuevas (antes
  `false`). El caso de uso habitual — rellenar una tarjeta que ya
  tiene algo en el campo de significado — se comportaba como "no
  tocar nada" con los dos flags a `false`, obligando al usuario a
  abrir el diálogo y marcarlo a mano. Ahora el atajo rápido añade
  al final por defecto; se puede cambiar a "sustituir" en Configuración
  o por-uso desde el popup. El `picker_last_mode` arranca también en
  `"append"` para que el popup abra en el mismo modo.
- `config.md` puesto al día para reflejar los 9 pares de idioma
  soportados (antes sólo listaba 4), la exclusión mutua entre
  `overwrite_existing` y `append_mode`, y la lógica script-family-aware
  de `language_pair_auto_fallback`.

### Nota sobre actualizaciones
- Anki conserva la configuración existente del usuario al actualizar
  un add-on, así que este cambio sólo afecta a **instalaciones nuevas**.
  Quien ya tenga el add-on instalado con `append_mode=false` seguirá
  con su config tal cual; puede cambiarla en el diálogo.

## [1.4.4] - 2026-04-24

### Arreglado
- **`es→ja` no encontraba traducciones para "espacio" aunque existían
  en es.wiktionary**: el regex de plantillas del bloque
  `{{trad-arriba}}…{{trad-abajo}}` aceptaba `{{t|ja|…}}`, `{{t+|ja|…}}`,
  `{{t-|ja|…}}` y `{{trad|ja|…}}`, pero **no** las variantes históricas
  `{{trad+|ja|…}}` / `{{trad-|ja|…}}` (marca de enlace al wiki target)
  ni `{{tø|ja|…}}`, que sí se usan en muchos artículos. Se amplía el
  prefijo a `(?:t[+\-]?[a-zø]?|trad[+\-]?)` para alinearlo con el
  regex equivalente de en.wiktionary. Verificado contra 10 variantes
  sintéticas y los mocks estándar de `{{trad-arriba}}`.

## [1.4.3] - 2026-04-24

### Arreglado
- **Atajo rápido con global `es→ja` sobre "silla" enrutaba por
  `en→ja`** y devolvía transliteraciones fonéticas japonesas
  (シツラ / シツラマエ / シツラート) desde Jisho. Causa: `detect_source`
  sólo marca un texto como español cuando ve marcas fuertes (¿¡áéíóúñ).
  Una palabra corta como "silla" o "casa" sin acentos se etiqueta
  como `en` por defecto, y el viejo `do_lookup_auto` interpretaba
  "source detectado ≠ source global" como señal para sobreescribir
  al global. Eso es correcto cuando el script cambia (latino → CJK,
  latino → hangul), pero es incorrecto cuando ambos son latinos,
  porque entonces la "detección" es en realidad un defecto, no
  evidencia. Ahora `do_lookup_auto` compara la *familia de script*
  (latin / cjk / hangul) en vez del código ISO: si ambas son la
  misma familia, respeta el par global del usuario; sólo sobreescribe
  cuando el script detectado pertenece claramente a otra familia
  (p. ej. seleccionar 椅子 en una tarjeta con global `en→es`).
  Verificado para las 21 combinaciones `global × texto_seleccionado`
  de los 9 pares soportados.
- **El diálogo de configuración permitía marcar a la vez "Sustituir
  existente" y "Añadir al final"**, que son acciones mutuamente
  excluyentes: la lógica de escritura usa un único modo, y con los
  dos activos ganaba `append` — contraintuitivo para quien había
  marcado "Sustituir" pensando que desactivaba lo anterior. Ahora
  marcar uno desmarca el otro automáticamente. Se admite el estado
  "ninguno marcado" = "no tocar campos que ya tengan contenido"
  (comportamiento anterior).

### Cambiado
- Configuraciones antiguas con ambos flags activos se normalizan al
  abrir el diálogo: prevalece `append_mode` (que era el que ganaba
  en la lógica de escritura) y `overwrite_existing` queda a `false`.

## [1.4.2] - 2026-04-24

### Arreglado
- **`en→es` insertaba la glosa inglesa como si fuera la definición del
  término español**: para "space" el add-on ponía
  `**espacio**` seguido de `1. physical extent in two or three dimensions`,
  que a simple vista parece una definición *de* "espacio" en inglés, lo
  cual es absurdo en una tarjeta que quieres en español. La glosa sale
  del bloque `{{trans-top|gloss}}` de en.wiktionary y siempre está en
  el idioma source (inglés aquí). Ahora la regla `hide_text` de
  `format_picked_choices` se aplica a cualquier par `en→*` y a `es→ja`:
  todos los caminos que usan el backend de *Translations* ocultan la
  glosa porque duplica la palabra del query que el usuario acaba de
  seleccionar en la propia carta.
- **`do_lookup` enruta todas las traducciones Wiktionary por el mismo
  camino** que `en→ja` con Jisho (dedupe por palabra + render vía
  `format_picked_choices`). Antes sólo `en→ja` y `es→ja` iban por ahí;
  `en→es` y `en→ko` caían en `format_entries` y mostraban la glosa.

### Cambiado
- `format_picked_choices` en modo `single_word` + `hide_text`: si todas
  las acepciones colapsan a una única palabra (caso típico tras el
  dedupe: "space" → sólo `espacio`), integra las POSes únicas en la
  cabecera (`**espacio** [Sustantivo]`) y omite el `<ol>` con un único
  "[Noun]" como pseudo-item, que no aportaba nada. Se conserva la
  lista cuando hay anotaciones de diccionario local (`— jmdict`…) que
  sí son información relevante.

## [1.4.1] - 2026-04-24

### Arreglado
- **`es→ja` insertaba `t1=椅子` como palabra japonesa**: el regex de
  captura de `{{trad|ja|…}}` sólo admitía el parámetro con nombre
  `1=`, pero es.wiktionary usa también `t1=`/`tr1=`/`tr=`. La captura
  se llevaba el prefijo pegado y acababa en la carta. Ahora el sufijo
  del regex acepta cualquier prefijo `<letras><dígitos>=` y además hay
  un segundo pase (`_strip_param_prefix`) por si algún caso raro se
  escapa.
- **`es→ja` etiquetaba los bloques como `[Etimología 1]`**: es.wiktionary
  anida los POS bajo `=== Etimología N ===` (L3) con el POS real en
  L4 (`==== Sustantivo femenino ====`). El parser anterior partía
  sólo por L3 y tomaba "Etimología 1" como POS. Ahora un nuevo
  `_walk_current_pos()` itera todas las cabeceras (L3–L6) y salta
  las estructurales (`Etimología`, `Pronunciación`, `Traducciones`,
  `Locuciones`, `Sinónimos`, `Antónimos`…), quedándose con el
  siguiente heading "real" como POS actual.
- **`es→ja` reinyectaba la glosa en español**: la glosa del bloque
  `{{trad-arriba|…}}` está en el idioma que el usuario ya lee
  (español en este par) y repetirla en la carta es redundante.
  `format_picked_choices` ahora aplica `hide_text` a cualquier par
  target→ja con source en `{en, es}`, y `do_lookup` enruta los
  resultados de Wiktionary por el mismo camino que Jisho `en→ja`
  (dedupe por palabra + render vía `format_picked_choices`) cuando
  el modo es "traducciones" y el target es japonés.

### Cambiado
- Nueva forma de `WiktEntry` con campos opcionales `gloss` y
  `translation_words`. Los backends de traducciones (en-wiki y
  es-wiki) ahora producen **una entry por palabra traducida** en
  vez de una entry con la glosa + varias palabras concatenadas.
  Mantiene retro-compat rellenando `definitions = ["(gloss) palabra"]`
  para el render clásico `format_entries` en los pares donde la
  glosa sí debe mostrarse (p. ej. `en→es`, `en→ko`).

### Añadido
- **El popup recuerda la última decisión de "Sustituir / Añadir"**:
  nueva clave de config `picker_last_mode`. Análoga a
  `picker_last_include_pos`: si en una invocación del picker elegiste
  "Añadir", la siguiente abre ya en "Añadir". Se guarda sólo al
  aceptar el picker (evita escrituras innecesarias) y no toca los
  globales `append_mode` / `overwrite_existing`, que siguen rigiendo
  el atajo rápido.

## [1.4.0] - 2026-04-24

### Añadido
- **Nuevos pares de idioma**:
  - `ja↔es` (japonés ↔ español) via **es.wiktionary**. Para `ja→es`
    usamos el parser genérico `{{lengua|ja}}` sobre el wiki español
    (ya existente). Para `es→ja` hay un backend nuevo que lee la
    sección `{{lengua|es}}` y extrae las traducciones de los bloques
    `{{trad-arriba}} … {{trad-abajo}}` mediante las plantillas
    `{{t|ja|…}}`, `{{t+|ja|…}}` y `{{trad|ja|…}}`, agrupadas por POS
    y por glosa.
  - `ko↔en` (coreano ↔ inglés) via **en.wiktionary**. Reutiliza el
    backend REST `page/definition/` (mismo que `es↔en`) para `ko→en`,
    y el parser de Translations (`{{t|ko|…}}`) para `en→ko`.
  - `ko→ja` (coreano → japonés) **sin backend online**: se enruta
    directamente a los diccionarios locales Yomitan/Yomichan (p. ej.
    `daum-extracted`, `KRDict`). Comunidades donde conseguirlos:
    `MarvNC/yomitan-dictionaries` y `themoeway/yomitan-dictionaries`
    en GitHub, más el Discord de Yomitan.
- **Detección de Hangul** en `lang.detect_source`: si el texto
  seleccionado contiene al menos una sílaba hangul
  (`AC00–D7AF`, más los rangos de Jamo), se detecta como coreano
  antes que CJK. Esto permite usar el atajo rápido sobre palabras
  coreanas aunque el par global sea ja↔en.

### Cambiado
- `lang.auto_detect_pair` ahora contempla `ko` como source válido y
  prefiere el target del par global cuando es coherente (`en`/`ja`
  para `ko`; `en`/`ja` para `es`), cayendo a `en` como default.
- `lang.sources_for_pair` enruta explícitamente:
  - `ja↔en` → Jisho
  - `es↔en`, `ko↔en` → en.wiktionary (REST + Translations)
  - `ja↔es` → es.wiktionary
  - `ko↔ja` y exóticos → sólo diccionarios locales.
- Las etiquetas de par (`pair.*` en `i18n.py`) se han traducido a
  en/es/ja para los seis nuevos pares. El label de `ko→ja` aclara
  "(sólo diccionarios locales)" / "(local dictionaries only)" /
  "(ローカル辞書のみ)" para que el usuario entienda por qué el
  resultado depende de los ZIP cargados.

## [1.3.3] - 2026-04-24

### Arreglado
- **`Ctrl+S` sobre palabra inglesa con par global `ja→en` seguía
  reinyectando el inglés** (regresión parcial: el `hide_text` de
  1.2.3 + 1.3.1 está bien, pero **no se ejecutaba** porque el
  routing nunca llegaba a `en→ja`). Causa: `do_lookup_auto` probaba
  primero el par global. Jisho cruza entre idiomas y, buscando
  "space" en modo `ja→en`, devolvía 空き con sus
  `english_definitions` ("space, room, gap…"); como había resultado,
  la función devolvía ahí y nunca reintentaba con `en→ja`. Ahora,
  cuando `language_pair_auto_fallback` está activo y el *source*
  detectado difiere del *source* del par global, el par detectado
  se usa como **primario** y el global queda de segundo intento.
  Con `auto_fallback = False` el par global sigue siendo estricto.
- **Dedupe de candidatos en `en→ja` rápido**: como el texto de
  sentido se oculta en ese par, dos sentidos de la misma palabra se
  renderizaban idénticos (`空き【あき】[Noun]` dos veces). Ahora el
  atajo rápido deduplica por `(palabra, lectura)` antes de
  recortar a `max_senses`, así el usuario ve candidatos
  distintos (ej. 空き / スペース / 場所).

## [1.3.2] - 2026-04-24

### Arreglado
- **Crash al valorar la carta después del atajo rápido** en Anki
  25.09.2 / Python 3.13: `TypeError: unsupported operand type(s)
  for -: 'float' and 'NoneType'` en
  `anki.cards.Card.time_taken`. Causa: el fix de refresh de 1.3.1
  sustituía `reviewer.card` por una copia fresca obtenida con
  `mw.col.get_card(id)`, pero esa copia no tiene `timer_started`
  (sólo se fija cuando el reviewer muestra la carta). Al pulsar
  una valoración, `sched.build_answer` llamaba a `card.time_taken()`
  y explotaba.
  Ahora mantenemos la misma instancia de `Card` (preservando
  `timer_started` y demás estado del reviewer) y sólo invalidamos
  el caché de la nota (`card.note(reload=True)`) y el caché del
  render (`card._render_output = None`) antes de diferir el
  re-draw con `QTimer.singleShot(0, ...)`. La carta se refresca y
  la valoración posterior funciona.

## [1.3.1] - 2026-04-23

### Arreglado
- **Atajo rápido en `en→ja` reinyectaba el inglés**: el fix de 1.2.3
  sólo cubría el popup (`format_picked_choices`). La ruta de
  `do_lookup` seguía llamando a `jisho_client.format_entries`, que
  serializa las `english_definitions` íntegras. Ahora, cuando el par
  es `en→ja`, el atajo rápido también enruta las entradas por
  `format_picked_choices`, así que sólo se inserta palabra+lectura
  (+ POS si está activo) en la carta.
- **La tarjeta no se refrescaba tras el atajo rápido**: `card.load()`
  sobre la instancia existente no siempre hacía que el reviewer
  re-renderizara con el campo actualizado. Ahora pedimos una copia
  fresca de la carta a la BD (`mw.col.get_card(id)`), la sustituimos
  en `reviewer.card`, invalidamos `_render_output` y diferimos el
  re-draw al siguiente tick del event loop (`QTimer.singleShot(0, …)`)
  para que Qt procese primero los eventos pendientes. Esta ruta
  bloqueaba sólo al atajo rápido porque el popup, al abrir un
  QDialog modal, drenaba el event loop de forma natural.

### Añadido
- **El popup recuerda la última decisión de "Gramática"**: nueva
  clave de config `picker_last_include_pos`. Si apagas el toggle en
  una invocación del picker, la próxima vez se abre apagado. Se
  guarda sólo cuando cambia (evita escrituras innecesarias) y no
  afecta al flag global `include_parts_of_speech`, que sigue rigiendo
  el atajo rápido.

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
