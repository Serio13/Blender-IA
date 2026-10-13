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
5. `bpy.data.libraries.write` con una **Scene** cierra Blender; con una **Collection** funciona.
6. Cambiar el espacio de color de una imagen *después* de rellenar sus píxeles los pone a cero (solo
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
| 1b | Rehorneado de normales desde LOD0 (plan B si Decimate deforma UV) | pendiente |
| 2 | Automatizar horneado V2 → BAKED; generadores paramétricos (cofre, barril, llave) y spec JSON | pendiente |
| 3 | Resolutor de intención (texto/imagen/ejemplo) con proveedores intercambiables (locales y APIs) | pendiente |
| 4 | Worker de IA local con cooldown térmico (GPU), SF3D opcional, modo comercial seguro de licencias | pendiente |
