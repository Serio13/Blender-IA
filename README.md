# Pirate Prop Forge

Add-on de Blender (5.x) para llevar props estilizados a Unity: **LODs automáticos por pieza** y un
**paquete de exportación** (FBX + `.blend` + texturas PNG + informe), con comandos cortos pensados para
gastar pocos tokens al usarlo desde Claude Code.

Estado: **Fase 1** (LODs + exportación + perfil de estilo). Generación con IA, horneado automático y
protección térmica llegan en fases posteriores (ver `docs/ARCHITECTURE.md`).

## Instalar (sin terminal)

1. **Descarga el instalador ya generado:** `releases/pirate_prop_forge-0.1.3.zip` en la rama
   `claude/gifted-lamport-jkmw6u` (en GitHub: abre el archivo → botón *Download raw file* ⬇).
   No lo descomprimas.
2. Blender → *Edit → Preferences → Get Extensions* → menú **▾** (arriba a la derecha) →
   **Install from Disk…** → elige el `.zip` → deja marcado *Enable*.
3. En la vista 3D pulsa **N** → pestaña **Prop Forge**.

**Actualizar:** `git pull` NO actualiza el plugin ya instalado en Blender; hay que quitarlo y reinstalar el
`.zip` de `releases/`. La versión se ve en **N → Prop Forge** (primera línea). Guía completa con GitHub Desktop,
actualización y solución de problemas: `docs/INSTALACION.md`.
Para regenerar el instalador tras cambiar el código: `python tools/build_extension.py releases`.

## Qué hace con tus `_BAKED`

Agrupa las piezas de un asset por nombre (`Cofre_comun_V2_base_BAKED` + `Cofre_comun_V2_tapa_BAKED` →
asset `Cofre_comun_V2`; si hay padre vacío, el padre define el asset) y, por cada asset:

| Paso | Resultado |
|---|---|
| LODs | LOD1/LOD2 (preset *estándar* ≈ 35 % / 10 %), por pieza, conservando UV, pivotes y materiales. LOD0 no se toca |
| Calidad | cada LOD se compara con el original (forma y mapeo UV) y avisa si se deforma: `AVISO: LOD1: el mapeo de textura se desplaza…` |
| Exportar | `Asset/Asset.fbx`, `Textures/`, `Asset_report.json` y `Source~/Asset.blend` (Unity ignora las carpetas con `~`) |
| Origen | `--pivot base` (por defecto): centro de la base en (0,0,0); `center`: centro de la caja; `keep`: origen actual. Escala aplicada. Los pivotes de las piezas (p. ej. la bisagra) se conservan |
| Texturas | PNG extraídos del `.blend`: `_BaseMap`, `_Normal`, `_MetallicSmoothness` (R=metal, A=smoothness), `_Emission`. El FBX las referencia (`Textures/…png`) para que Unity muestre color y normal |
| Nodos FBX | `Asset_LOD0`, `Asset_LOD1`… (cada uno con sus piezas dentro) para que Unity cree el LOD Group |
| Colisión | `none`, `hint` (solo datos en el informe, por defecto) o `mesh` (casco convexo `Asset_COL`) |

Los LODs se omiten si no reducen de verdad (p. ej. un asset que ya queda en ~7 % solo con disolver planos)
y los assets con menos de 300 triángulos no los necesitan.

## Usarlo

**Panel:** selecciona las piezas → *Generar LODs* → *Exportar paquete*.

**Python (con Blender abierto, p. ej. por el puente MCP):**

```python
import bl_ext.user_default.pirate_prop_forge.api as pf
pf.lods("*_BAKED")                                   # una línea por asset
pf.export("*_BAKED", out_dir="D:/Unity/Assets/Props")
pf.profile("style_profile.json")                     # perfil de estilo de ~1 KB
```

**Línea de comandos (Blender cerrado, procesa muchos assets):**

```powershell
& "C:\Program Files\Blender Foundation\Blender 5.2\blender.exe" -b "D:\ruta\escena.blend" `
  --python "D:\ruta\Blender-IA\addon\pirate_prop_forge\cli.py" -- `
  export --target "*_BAKED" --out "D:\Unity\Assets\Props"
```

Opciones útiles: `--preset estandar|agresivo|ligero|completo`, `--ratios 0.35,0.1`, `--tris 4300,1200`
(objetivos absolutos), `--layout grouped|flat`, `--pivot base|center|keep`, `--collider none|hint|mesh`, `--drop-uv2`, `--verify`,
`--regenerate`, `--spread` (separa los LODs en X para revisarlos), `--save`.

`target` acepta un objeto, una colección o un patrón (`*`, `?`). Sin `target`, usa la selección.

## En Unity

Arrastra a `Assets/` **la carpeta completa del asset** (con el `.fbx`, `Textures/` y el `_report.json`), no solo
el `.fbx`: sin las texturas al lado, el modelo sale sin color. Para que el material URP/Lit (con metal y
smoothness) se cree y asigne solo, copia `unity/PropForge/Editor/PropForgePostprocessor.cs` a
`Assets/Editor/`. Detalles y puntos por verificar: `docs/UNITY_NOTES.md`.

## Pruebas

```powershell
pip install bpy==5.2.2 pytest
pytest
```

Las pruebas usan el módulo `bpy` real (mismo motor y exportador FBX que Blender 5.2).

## Límites conocidos

- La reducción usa el modificador Decimate de Blender. Con piezas duras y costuras UV agresivas puede
  desplazar ligeramente el mapeo: revisa los LODs con `--spread` y, si algo falla, el plan B es
  rehornear el normal desde LOD0 (no implementado todavía).
- El `.blend` del paquete contiene una **colección** (no una escena): úsalo con *Archivo → Añadir (Append)
  → colección*. Escribir una escena con `libraries.write` cierra Blender.
- Lo que depende de Unity (incluido el script de `unity/`) no se ha podido probar aquí: ver `docs/UNITY_NOTES.md`.
