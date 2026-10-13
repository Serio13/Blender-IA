# Instalación paso a paso (sin conocimientos de terminal)

## A. Solo instalar el add-on (lo mínimo)

1. Abre en el navegador: `https://github.com/Serio13/Blender-IA/blob/claude/gifted-lamport-jkmw6u/releases/pirate_prop_forge-0.1.0.zip`
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
