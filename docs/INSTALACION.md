# Instalación paso a paso (sin conocimientos de terminal)

## A. Solo instalar el add-on (lo mínimo)

1. Abre en el navegador: `https://github.com/Serio13/Blender-IA/blob/claude/gifted-lamport-jkmw6u/releases/pirate_prop_forge-0.2.1.zip`
   y pulsa **Download raw file** (icono ⬇). Se guarda en *Descargas*. **No lo descomprimas.**
2. En Blender 5.2: *Edit → Preferences → Get Extensions*. Si pregunta por acceso a Internet, puedes decir
   que no: no hace falta.
3. Arriba a la derecha pulsa la flecha **▾** → **Install from Disk…** → elige el `.zip` → *Install from Disk*.
4. Comprueba que "Pirate Prop Forge" está activado (casilla marcada) en la lista de extensiones.
5. En la vista 3D pasa el ratón por encima y pulsa **N**. Aparece la pestaña **Prop Forge** a la derecha.

## B. Tener el código completo en tu PC (para actualizar y usar la línea de comandos)

Con **GitHub Desktop** (programa con botones, sin terminal):

1. Instala GitHub Desktop (desktop.github.com) e inicia sesión con tu cuenta de GitHub.
2. *File → Clone repository…* → pestaña *GitHub.com* → elige **Serio13/Blender-IA** → elige una carpeta
   (p. ej. `D:\Proyectos\Blender-IA`) → *Clone*.
3. Arriba, en **Current Branch**, selecciona **claude/gifted-lamport-jkmw6u**.
4. Para traer cambios nuevos que yo suba: botón **Fetch origin** y luego **Pull origin**.

Alternativa: pídele a Claude Code (VS Code): *"Clona https://github.com/Serio13/Blender-IA en D:\Proyectos
y cambia a la rama claude/gifted-lamport-jkmw6u"*. Él ejecuta los comandos de git por ti.

## C. Primer uso

1. **Guarda una copia de tu escena** (*File → Save As*, p. ej. `escena_prueba.blend`). El add-on no modifica
   tus objetos originales, pero crea una colección `PF_LODS`.
2. Selecciona las piezas de un asset (clic en una, **Ctrl+clic** en las demás; p. ej. base y tapa del cofre).
3. En **Prop Forge → LODs** pulsa **Generar LODs**. El resultado aparece en el recuadro del panel.
   Activa *Separar LODs en X* si quieres verlos uno al lado del otro.
4. En **Exportar a Unity** elige la carpeta de salida (puede ser `Assets/Props` de tu proyecto de Unity) y pulsa
   **Exportar paquete**. Si dejas `//Export/`, se crea junto al `.blend` (por eso hay que guardarlo antes).
5. Resultado: una carpeta por asset con `.fbx`, `Textures/`, informe `_report.json` y `Source~/` (el `.blend`).

## D. Llevarlo a Unity

1. **Copia la carpeta completa del asset** (no solo el `.fbx`) a `Assets/` de tu proyecto. Sin `Textures/` al
   lado, el modelo sale sin color.
2. Opcional pero recomendado: copia `unity/PropForge/Editor/PropForgePostprocessor.cs` a `Assets/Editor/`
   (crea la carpeta `Editor` si no existe). Crea y asigna el material automáticamente.
3. Más detalles y qué revisar: `docs/UNITY_NOTES.md`.

## Si algo falla

- **No veo la pestaña Prop Forge:** comprueba que la extensión esté activada y que el ratón esté sobre la
  vista 3D al pulsar **N**.
- **Mensaje de error:** aparece en rojo dentro del panel (recuadro de resultado). Cópialo y pásamelo.
- **Más detalle:** *Window → Toggle System Console* (solo Windows) muestra los mensajes internos.


## E. Actualizar el plugin (importante)

`Pull` en GitHub Desktop **solo actualiza la carpeta del repositorio en tu PC; no cambia el plugin que ya
tienes instalado en Blender**. Hay que reinstalarlo:

1. En GitHub Desktop comprueba arriba que **Current Branch** es `claude/gifted-lamport-jkmw6u` (si pone `main`,
   estás en la rama equivocada y no verás nada nuevo). Pulsa **Fetch origin** y luego **Pull origin**.
2. En la carpeta del repositorio (por ejemplo `D:\Proyectos\Blender-IA`) abre `releases\` y localiza el `.zip`
   con la versión más alta (ahora `pirate_prop_forge-0.2.1.zip`).
3. Blender → *Edit → Preferences → Get Extensions* → busca **Pirate Prop Forge** → menú **▾** → **Remove**.
4. Menú **▾** de arriba a la derecha → **Install from Disk…** → elige ese `.zip`.
5. **Comprueba la versión:** en la vista 3D, **N → Prop Forge**: la primera línea dice `Version 0.2.1`.
   Si pone otra, sigue instalada la antigua: repite el paso 3.
6. Con objetos seleccionados, pulsa **Revisar seleccion**: te dice qué texturas reconoce el plugin de cada asset
   (por ejemplo `BaseMap 2048, Normal 2048, Metallic 2048, Roughness 2048`). Si dice `SIN TEXTURAS` o `FALTA`,
   el problema está en Blender, no en Unity: copia esa línea y envíamela.
7. **Vuelve a exportar** los assets (los paquetes anteriores tienen el FBX antiguo).

## F. Si en Unity no salen las texturas

1. Comprueba que usaste la versión nueva (paso E) y que **volviste a exportar**.
2. Copia a `Assets/` **la carpeta completa** del asset: debe contener `Textures/` junto al `.fbx`.
3. En Unity selecciona el `.fbx` → *Inspector → pestaña Materials*. Deben verse `Material Creation Mode:
   Import via MaterialDescription` y `Location: Use Embedded Materials`. Pulsa **Apply** si cambias algo.
4. Si el material existe pero sale blanco: pulsa **Extract Materials…**, elige una carpeta, abre el material
   creado y arrastra `…_BaseMap.png` a *Base Map* y `…_Normal.png` a *Normal Map* (Unity te ofrecerá
   *Fix Now*; acepta).
5. Para que se haga solo (incluido metal y brillo): instala `unity/PropForge/Editor/PropForgePostprocessor.cs`
   en `Assets/Editor/` y haz clic derecho en la carpeta del asset → **Reimport**.

## G. Si la textura sale como un mosaico desordenado en Unity

Es el síntoma de que Unity está usando una capa UV distinta de la que usan las texturas. Pasa en assets con
**dos capas UV** (p. ej. `Barril_simple_V2`): Blender usa la capa marcada con la cámara 📷 (*Object Data →
UV Maps*), pero Unity usa siempre la primera del FBX.

- Desde la versión 0.1.4 el plugin pone **primera** la capa que usan las texturas al exportar.
- **Revisar seleccion** lo muestra: `UV: UVMap, Bake*` (el asterisco marca la capa de las texturas) y avisa
  `(la de texturas se pondra primera)`.
- Si aun así sale mal: en Unity selecciona el `.fbx` → *Inspector → Model → Geometry* y comprueba que
  **Swap UVs** está **desactivado**.
- Y pásame la línea de **Revisar seleccion** de ese asset.

## H. Si en Unity se ve distinto del original

Sigue este orden; cada paso descarta una causa:

1. **¿Estás viendo un LOD?** Selecciona el objeto en la escena → componente **LOD Group** → pulsa el cuadro
   **LOD 0** para forzarlo. Si LOD 0 se ve igual que el original, el problema está solo en un LOD inferior.
   Con la cámara lejos Unity enseña LOD 1 o 2 aunque el original parezca "el mismo".
2. **Normal map.** En Unity selecciona `…_Normal.png` → *Inspector → Texture Type* → **Normal map** → *Apply*.
   Sin esto el relieve se interpreta como color y salen tablas grises y ruido (la banda roja "sucia").
3. **Metal y brillo.** Sin el script `PropForgePostprocessor.cs` (sección F) no se asigna `…_MetallicSmoothness.png`
   y el material queda mate frente al original.
4. **Avisos de LOD.** Desde la 0.1.4 el plugin mide si un LOD **cambia el color visible** y, si deforma, lo sube
   de tamaño o lo descarta (`AVISO: LOD2 omitido: …`). Si no quieres ese descarte: *LODs → desmarca "Descartar LODs
   que deformen"* o `--no-strict`.

## I. "Al exportar se rompe mi modelo en Blender" (líneas, manchas, triángulos sobre la madera)

No es el original: son los **LODs superpuestos**. Los LODs nacen exactamente en el mismo sitio que el original;
si están visibles, sus superficies simplificadas asoman a través del modelo (z-fighting). Desde la 0.1.4 los LODs
**se crean ocultos**. Si quieres verlos para compararlos, marca **Mostrar LODs (separados en X)**: salen al lado.

Si ya los tenías creados con una versión anterior: botón de la papelera junto a *Generar LODs* (Quitar LODs), o
borra la colección `PF_LODS`. Las pruebas comprueban además que generar LODs o exportar **no modifica** el
original (malla, UV, materiales ni texturas).

## IA local (desde la 0.2.0)

Después de instalar el plugin, haz doble clic en `instalar_ia.bat` (raíz del repositorio) para instalar el motor de
IA. Guía completa: `docs/IA_LOCAL.md`.
