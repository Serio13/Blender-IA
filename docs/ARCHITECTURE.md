# Arquitectura y hoja de ruta

## Objetivo

Props premium para un juego isométrico de piratas (Unity 6, URP) con el menor gasto posible de tokens y de
tiempo manual. Los props premium ya existen en producción como `_V2` (procedurales) → `_BAKED` (un material,
texturas de 2048/1024/512 px, 5–15 k triángulos por asset). Falta bajar LODs y empaquetar para Unity.

## Estructura

```
addon/pirate_prop_forge/
  blender_manifest.toml   extensión de Blender (4.2+; probado en 5.2.2)
  api.py                  comandos cortos: lods / export / clean / profile
  cli.py                  blender -b archivo.blend --python cli.py -- <comando>
  core/                   lógica sin UI (assets, lods, textures, colliders, export, profile)
  ui/                     panel N, propiedades, operadores (delgados: llaman a api)
tests/                    pytest con bpy real
tools/export_style_report.py   informe completo de la escena (uso puntual; pesado)
```

## Reglas del FBX (verificadas con el parser del propio exportador)

1. `bake_space_transform=True`, eje arriba Y, adelante −Z: los nodos salen con rotación 0.
2. **Sin nodo raíz explícito.** Con el espacio horneado, una malla anidada bajo un vacío que no es de
   primer nivel recibe un giro extra de 90°. Los nodos `Asset_LODn` son de primer nivel con las piezas
   dentro (jerarquía *grouped*) o cada pieza es de primer nivel (*flat*). Unity crea la raíz con el nombre
   del archivo.
3. Los nombres de nodos y mallas deben ser exactos (`Asset_LOD1`, sin `.001`): antes de crear los
   objetos temporales se **reserva** el nombre renombrando temporalmente al objeto existente y se restaura al
   terminar (`_Temp.claim`).
4. Escala aplicada en la copia, con ancla (traslación + rotación, sin escala) en el origen; el pivote de
   cada pieza (p. ej. la bisagra de la tapa) se conserva.
5. `bpy.data.libraries.write` con una **Scene** cierra Blender; con una **Collection** funciona. El `.blend`
   va en `Source~/` (Unity ignora esa carpeta) y se escribe con `path_remap="RELATIVE"`.
6. **Texturas en el FBX:** el material exportado se reconstruye con los PNG ya escritos
   (`BaseMap`→Base Color, `Normal`→Normal Map) y se exporta con `path_mode="RELATIVE"`; así el FBX contiene
   `DiffuseColor`/`NormalMap` → `Textures/<Asset>_*.png`. Blender no exporta metal/smoothness en FBX
   (lo cubre `unity/PropForge/Editor/PropForgePostprocessor.cs`).
7. **Pivote** (`base` por defecto): se desplaza solo el ancla del asset; los orígenes de las piezas
   (bisagra de la tapa) se conservan. LOD0 manda: los LODs usan el mismo ancla.
8. **Control de calidad de LODs** (`core/quality.py`): por triángulo del LOD se busca el punto más cercano del
   original **entre caras que miran al mismo lado** (no confundir las dos paredes de una tabla) y se mide la
   desviación de forma, el error de UV y, si hay BaseMap, la **diferencia de color real** (textura leída con la UV
   del LOD y con la esperada). Avisa con p95 de color > 10 % o forma > 1,2 % (sin textura, UV > 2 %). Con `strict`
   (por defecto) un LOD que falla se rehace con ×1,4 triángulos (hasta 2 veces) y, si sigue mal, se descarta.
9. **Capas UV** (`meshutil.order_uv_layers`): Unity usa la primera capa del FBX; se pone primero la capa de las
   texturas (nodo UV Map si existe, si no la de render). Antes de la 0.1.2 se exportaba el orden original y los
   assets de dos capas salian en mosaico en Unity. `--drop-uv2` conserva esa capa, no la primera por azar.
10. Los LODs generados se crean **ocultos** (`hide_viewport`, `hide_render`) salvo con `spread`: nacen en el mismo
    sitio que el original y visibles lo tapan con z-fighting. `tests/test_original_untouched.py` fija que ni
    generar LODs ni exportar tocan el original (malla, UV, materiales, imagenes).
11. Cambiar el espacio de color de una imagen *después* de rellenar sus píxeles los pone a cero (solo
   afecta a imágenes generadas, no a PNG empaquetados); se fija antes.

## Decisiones

| Tema | Decisión |
|---|---|
| Motor de IA | Fase posterior. Receta/generador paramétrico + spec JSON; SF3D (6 GB) solo como extra para orgánicos. TRELLIS descartado en 11 GB |
| PyTorch en GTX 1080 Ti | Pascal: ruedas cu126 o anteriores (≤ PyTorch 2.14), FP32, sin flash-attn |
| Texturas | Metallic+Roughness → `MetallicSmoothness` (R=metal, A=1−roughness), propiedades URP/Lit |
| Colisiones | Se hacen en Unity. Opcional: datos sugeridos (`hint`) o malla `_COL` |
| Tokens | API de comandos, respuestas mínimas, perfil de estilo compacto, `CLAUDE.md` corto |

## Fases

| Fase | Contenido | Estado |
|---|---|---|
| 1 | LODs por pieza, paquete Unity, perfil de estilo, panel, CLI, pruebas | **hecha** |
| 1b | Rehorneado de normales/UV desde LOD0 (plan B si el control de calidad avisa de que Decimate deforma) | pendiente |
| 2 | Automatizar horneado V2 → BAKED; generadores paramétricos (cofre, barril, llave) y spec JSON | pendiente |
| 3 | Resolutor de intención (texto/imagen/ejemplo) con proveedores intercambiables (locales y APIs) | pendiente |
| 4 | Worker de IA local con cooldown térmico (GPU), SF3D opcional, modo comercial seguro de licencias | pendiente |
