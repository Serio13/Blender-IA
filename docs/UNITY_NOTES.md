# Unity 6: importación y puntos por verificar

El FBX generado se ha comprobado con el parser del exportador de Blender y reimportándolo en Blender
(nombres, jerarquía, tamaños, pivotes, sin rotaciones espurias, referencias a texturas). Lo que depende del
importador de Unity no se ha podido probar aquí.

## Si el modelo sale sin color

Casi siempre es que se copió solo el `.fbx`. Copia **la carpeta completa del asset** a `Assets/`:

```
Barril_simple_V2/
  Barril_simple_V2.fbx
  Barril_simple_V2_report.json
  Textures/            <- imprescindible: el FBX apunta a Textures/<Asset>_BaseMap.png y _Normal.png
  Source~/             <- el .blend; Unity ignora las carpetas que acaban en ~
```

El FBX lleva el material `M_<Asset>` con `DiffuseColor` → `_BaseMap` y `NormalMap` → `_Normal`. Blender no
exporta metal/smoothness en FBX; para eso está el script de Unity.

## Script de importación (recomendado)

Copia `unity/PropForge/Editor/PropForgePostprocessor.cs` a `Assets/Editor/` (crea la carpeta si no existe).
Al importar un asset: marca `_Normal` como Normal map, `_MetallicSmoothness` sin sRGB, y crea
`Materials/M_<Asset>.mat` (URP/Lit) con BaseMap, Normal, Metallic+Smoothness y Emission, asignado al modelo.
**Escrito sin poder compilarlo en Unity**: si da un error de compilación, bórralo y avísame. Si ya
importaste texturas antes de instalarlo, haz clic derecho en la carpeta → *Reimport*.

## Material a mano (si no usas el script)

| Propiedad URP/Lit | Archivo |
|---|---|
| `_BaseMap` | `Textures/<Asset>_BaseMap.png` |
| `_BumpMap` | `Textures/<Asset>_Normal.png` (tipo *Normal map*) |
| `_MetallicGlossMap` | `Textures/<Asset>_MetallicSmoothness.png` (*sRGB* desactivado; *Smoothness Source: Metallic Alpha*; Smoothness = 1) |
| `_EmissionMap` | `Textures/<Asset>_Emission.png` |

## Por verificar con un asset real

1. **LOD Group automático.** Unity lo crea a partir de nodos `Nombre_LOD0`, `Nombre_LOD1`… Cada nodo
   `_LODn` es de primer nivel y contiene las piezas del nivel. Si no se crea, prueba `--layout flat`.
2. **Umbrales de LOD.** El informe sugiere `unity_lod_screen_heights` (0.5, 0.2, 0.08…). Ajústalos a tu zoom
   máximo y al catalejo.
3. **Colisión sugerida.** `center_blender` va en ejes de Blender; `center_unity` y `size_unity` asumen
   (x, z, y) = (ancho, alto, fondo). Si el pivote no está centrado, comprueba el signo de Z.
4. **Malla `_COL`.** Unity no la trata como colisión por sí sola: hace falta quitar el renderer y añadir
   `MeshCollider`.
5. **Segunda capa UV.** Se conserva por defecto; `--drop-uv2` la elimina si Unity no la usa.
6. **Animación de partes móviles (tapa).** Cada LOD tiene su propia tapa: la animación debe aplicarse a todas,
   o animar solo la del nivel visible.
