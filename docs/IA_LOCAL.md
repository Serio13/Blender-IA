# IA local: de una imagen a un prop listo para Unity

Todo corre **en tu PC** (GTX 1080 Ti), sin API de pago y sin gastar tokens. El plugin no importa PyTorch: lanza un
proceso aparte (*worker*) con su propio Python, así Blender no se bloquea ni se rompe por dependencias.

```
Blender (panel N) ──JSON por stdin/stdout──► worker (Python propio, PyTorch + SF3D)
        ▲ temporizador cada 0,25 s (no bloquea)          │ pausa de enfriamiento + temperatura (nvidia-smi)
        └── malla cruda ─► limpieza, escala real, origen, triángulos, material PBR ─► Asset_malla_BAKED
```

## Instalar (una sola vez, ~20-30 min, ~6 GB)

1. Actualiza el plugin (zip de `releases/`, ver `INSTALACION.md`).
2. Doble clic en **`instalar_ia.bat`** (carpeta raíz del repositorio; también viene dentro del plugin en
   `worker/`). Hace solo: Python 3.11 aislado, PyTorch 2.6 + CUDA 12.4 (las versiones nuevas ya no soportan
   tu tarjeta), Stable Fast 3D y sus dependencias, y te guía para el permiso del modelo.
   - Si pide **Build Tools de Visual Studio** (compilador de C++, ~5 GB): responde `s`; SF3D lo necesita para dos
     piezas pequeñas.
   - **Permiso del modelo (gratis):** crea cuenta en huggingface.co, abre
     <https://huggingface.co/stabilityai/stable-fast-3d>, pulsa *Agree*, crea un token de lectura y pégalo cuando
     el instalador lo pida.
3. Al final imprime un diagnóstico (`VEREDICTO: LISTO para generar`). Si no, copia esas líneas: cada una dice
   qué falla y cómo arreglarlo. También está en el panel: **N → Prop Forge → IA local → Diagnosticar**.

## Usar

**N → Prop Forge → IA local:** `Iniciar motor de IA` (carga el modelo en la primera generación) → elige la
imagen (mejor con el objeto centrado y fondo liso) → nombre (`Familia_variante_V2`) → categoría → `Generar malla`.
Blender sigue usable mientras tanto; hay barra de progreso y botón *Cancelar*.

Al terminar aparece `<Nombre>_malla_BAKED` seleccionado: limpio, a tamaño real, con el origen en la base y con
material. Después usa **Generar LODs** y **Exportar paquete** como siempre.

| Opción | Qué hace |
|---|---|
| Categoría / Alto real | Escala a metros reales (barril 0,85 · cofre 0,55 · llave 0,14 · cantimplora 0,20…). Con *Alto real* propio manda ese; referencia: el pirata mide 1,62 m |
| Origen | `Base` (centro de la base en 0,0,0), `Centro` o `Mantener` |
| Triángulos | `Automático` (tope por categoría), `Manual` (mínimo y máximo) o `Sin límite`. Si queda por debajo del mínimo avisa |
| Material | `Texturas de la IA` (SF3D trae color, normal, rugosidad y metal; TripoSR solo color por vértice, que se hornea) o `Madera` / `Cuero` / `Metal`: PBR procedural horneado (BaseColor, Roughness, Normal). Color propio opcional |

Limpieza automática: une vértices duplicados, borra sueltos y **fragmentos flotantes** (<1 % de las caras del
cuerpo principal), recalcula normales hacia fuera. Con material procedural y sin UV, desenvuelve solo.

**Sin IA:** *Normalizar una malla existente* aplica lo mismo a un `.obj/.glb` que ya tengas.

**Python / Claude Code (sin tokens extra):**
```python
pf.ai_generate("D:/ref/barril.png", "Barril_ia_V2", category="barril", material="madera")   # bloquea hasta acabar
pf.ai_generate(["a.png", "b.png"], ["Barril_ia_V2", "Cofre_ia_V2"], category="barril")       # lote con pausas
pf.ai_import("D:/ia/barril.glb", "Barril_ia_V2", category="barril")                           # sin IA
```
CLI: `-- ai-generate --image a.png b.png --name A B --category barril` · `-- ai-import --mesh x.glb --name A`.

## Escribir lo que quieres (texto → imagen → malla)

En **Entrada → Texto** escribes la descripción (mejor en inglés, p. ej. `old brass pirate key, ornate round bow,
worn, stylized`). El plugin dibuja primero una **imagen de referencia** con Stable Diffusion 1.5 en tu GPU (se ve
en el panel; si no te gusta, cambia la *Semilla* o el texto) y después crea la malla desde esa imagen. **Usar esta
imagen** conserva el dibujo y rehace solo la malla. Requiere volver a ejecutar `instalar_ia.bat` una vez (añade
`diffusers`; la primera generación descarga ~4 GB). Licencia OpenRAIL-M (uso comercial permitido). *No verificado en
tu PC.*

## Calidad: qué esperar de la IA de una sola imagen

Stable Fast 3D crea la forma completa a partir de **una** imagen: reconoce la silueta, pero la superficie sale
blanda y algo grumosa, y los detalles finos (grabados, remaches) se pierden. Para mejorar el resultado:
- Mira el modelo en **Material Preview** (tecla `Z` en la vista 3D): en *Solid* se ve gris y sin textura.
- Imagen de entrada: un solo objeto, centrado, fondo liso, vista 3/4 y buena luz.
- **Suavizado** (por defecto 2): alisa la grumosidad sin encoger la forma; súbelo a 3-5 si sigue áspero, 0 para ver la malla cruda.
- Triángulos: los límites automáticos por categoría son ahora más altos (llave 5000, barril 9000...).
Los props "premium" hechos con Claude + Blender MCP se construyen pieza a pieza con geometría deliberada; una IA
local de una imagen no llega a esa precisión: úsala como **base** (forma + textura) que luego se refina.

## Protección térmica (pilar 5)

Tras cada generación hay una **pausa obligatoria** (por defecto 10 s; configurable 5-15 s en Preferencias) con
cuenta atrás en el panel. La impone el *worker*, no la interfaz: aunque se salte el botón, rechaza trabajos antes
de tiempo. Además (activable) espera a que la GPU baje de 72 °C (máx. 60 s) y no acepta trabajo si está a 85 °C o
más. Mide con `nvidia-smi`; si no puede leer la temperatura, aplica solo la pausa fija.

## Licencias (para vender lo que generes)

| Modelo | Licencia | ¿Vender? |
|---|---|---|
| Stable Fast 3D | Stability AI Community License | Sí, gratis con ingresos anuales < 1 M USD (por encima, licencia de Stability) |
| TripoSR | MIT | Sí |
| Prueba (sin IA) | — | No: solo para comprobar el plugin |

Preferencias → *Solo modelos aptos para uso comercial* (activado por defecto) bloquea los modelos marcados como
solo de prueba. Cada malla guarda `pf_source`, `pf_license`, `pf_commercial_ok` (Propiedades del objeto → Custom
Properties). No es asesoría legal: lee la licencia original antes de vender, y recuerda que la salida depende
también de la imagen de entrada (usa imágenes propias o con derechos).

## Qué está verificado y qué no

Verificado en pruebas automáticas (con un modelo de prueba, sin GPU): protocolo, arranque/parada y caída del
worker, no bloqueo de Blender, cancelación, pausa de enfriamiento obligatoria (incluido saltándose la interfaz),
limpieza/escala/origen/triángulos/UV, materiales procedurales horneados, texturas PBR de un GLB, y empaquetado.

**No verificado (necesita tu PC):** la instalación en Windows, PyTorch en la 1080 Ti, la inferencia real de SF3D
y TripoSR (calidad, tiempos, VRAM) y los umbrales térmicos con tus lecturas reales. Primer paso: ejecutar
`instalar_ia.bat` y mandarme el `VEREDICTO` del diagnóstico.
