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
8. **Control de calidad de LODs** (`core/quality.py`): por triángulo del LOD se mide la distancia a la
   superficie original y el error de UV frente a la UV interpolada del original. p95 > 2 % de UV o > 1,2 % de
   forma genera un AVISO. Sirve de verificación sin capturas.
9. Cambiar el espacio de color de una imagen *después* de rellenar sus píxeles los pone a cero (solo
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
