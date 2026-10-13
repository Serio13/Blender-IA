# Prop Forge: reglas para gastar pocos tokens

- **Usa los comandos, no escribas bpy.** `import bl_ext.user_default.pirate_prop_forge.api as pf` y
  `pf.lods(...)`, `pf.export(...)`, `pf.profile()`. Devuelven 1–3 líneas; no pidas más detalle salvo error.
- **Sin capturas por defecto.** Verifica con cifras (triángulos, tamaños) y con `verify=True`. Renderiza
  solo si te lo piden.
- **Una sola lectura de estilo:** `pf.profile("style_profile.json")` y lee ese archivo (~1 KB). No pegues
  ni leas informes grandes de la escena.
- Si una línea trae `AVISO:` (calidad de LOD, texturas), repórtalo tal cual; no lo investigues con capturas.
- **Varios assets en una llamada:** patrones (`"*_BAKED"`), no un comando por asset.
- Convenciones del proyecto: assets `Familia_variante_V2_pieza_BAKED`; piezas `base`/`tapa`/`malla`; un
  material horneado por pieza; texturas `TX_<asset>_<BaseColor|Normal|Metallic|Roughness|MetalSmooth|Emission>`;
  escala real en metros (el pirata de referencia mide 1,62 m); colisiones se hacen en Unity.
- Código en `addon/pirate_prop_forge/` (`core/` sin UI, `api.py` comandos, `cli.py` línea de comandos).
  Pruebas: `pip install bpy==5.2.2 pytest && pytest` (usan `bpy` real). Empaquetar: `python tools/build_extension.py`.
- Antes de tocar `core/export.py`, lee `docs/ARCHITECTURE.md` (reglas del FBX que no se deben romper).
- Modelos más baratos (`/model`) bastan para tareas mecánicas; reserva el fuerte para recetas nuevas.
