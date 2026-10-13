# Pendiente de verificar en Unity 6 (no se pudo probar sin Unity)

El FBX generado se ha comprobado con el parser del exportador de Blender y reimportándolo en Blender
(nombres, jerarquía, tamaños, pivotes, sin rotaciones espurias). Lo siguiente depende del importador de
Unity y debe revisarse con un asset real:

1. **LOD Group automático.** Unity crea el LOD Group a partir de nodos `Nombre_LOD0`, `Nombre_LOD1`…
   Aquí cada nodo `_LODn` de primer nivel contiene las piezas del nivel. Si en tu versión no se crea,
   prueba `--layout flat`.
2. **Umbrales de LOD.** El informe sugiere `unity_lod_screen_heights` (0.5, 0.2, 0.08…). Ajústalos a tu
   zoom máximo y al catalejo.
3. **Materiales.** El FBX no enlaza las texturas empaquetadas. Usa `unity_material` del informe:

   | Propiedad URP/Lit | Archivo |
   |---|---|
   | `_BaseMap` | `Textures/<Asset>_BaseMap.png` |
   | `_BumpMap` | `Textures/<Asset>_Normal.png` (marcar como *Normal map*) |
   | `_MetallicGlossMap` | `Textures/<Asset>_MetallicSmoothness.png` (*sRGB* desactivado; *Smoothness Source: Metallic Alpha*) |
   | `_EmissionMap` | `Textures/<Asset>_Emission.png` |

4. **Colisión sugerida.** `center_blender` va en ejes de Blender; `center_unity` y `size_unity` asumen
   (x, z, y) = (ancho, alto, fondo). Si el pivote no está centrado, comprueba el signo de Z.
5. **Malla `_COL`.** Unity no la trata como colisión por sí sola: hace falta un script de importación que
   quite el renderer y añada `MeshCollider`.
6. **Segunda capa UV.** Se conserva por defecto; `--drop-uv2` la elimina si Unity no la usa.
7. **Animaciones de partes móviles (tapa).** Cada LOD tiene su propia tapa (`_LOD0`, `_LOD1`…): la
   animación debe aplicarse a todas, o animar solo la del nivel visible.
