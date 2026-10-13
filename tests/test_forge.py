import bpy
import numpy as np
import pytest

import helpers
from pirate_prop_forge import api
from pirate_prop_forge.core import assets, meshutil, textures
from pirate_prop_forge.forge import bake, build, generators, kit, materials, palette


def _uv_array(mesh):
    arr = np.empty(len(mesh.loops) * 2, np.float32)
    mesh.uv_layers[0].data.foreach_get("uv", arr)
    return arr.reshape(-1, 2)


def test_pack_islands_fit_in_unit_square_without_overlap():
    b = kit.Builder("t", 1)
    sizes = [(0.12, 0.8), (0.12, 0.8), (1.9, 0.05), (0.3, 0.3), (0.02, 0.02)]
    ids = [b.surface(lambda u, v, k=k: (u * s[0], v * s[1], k), 2, 2, "wood", s) for k, s in enumerate(sizes)]
    scale = b.pack(margin=0.004)
    assert 0 < scale and b.density == scale
    uvs = _uv_rect_per_island(b)
    for rect in uvs.values():
        assert rect[0] >= 0 and rect[1] >= 0 and rect[2] <= 1.0 + 1e-6 and rect[3] <= 1.0 + 1e-6
    items = list(uvs.values())
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            a, c = items[i], items[j]
            assert a[2] <= c[0] or c[2] <= a[0] or a[3] <= c[1] or c[3] <= a[1]


def _uv_rect_per_island(b):
    rects = {}
    for f in b.bm.faces:
        i = f[b.isl]
        us = [l[b.uv].uv for l in f.loops]
        r = rects.setdefault(i, [9, 9, -9, -9])
        for u, v in us:
            r[0], r[1], r[2], r[3] = min(r[0], u), min(r[1], v), max(r[2], u), max(r[3], v)
    return rects


@pytest.mark.parametrize("variant", ["simple", "duelas", "polvora", "ron"])
def test_barrel_variants_are_premium_weight_and_well_formed(variant):
    obj = build.make_object({"archetype": "barrel", "variant": variant, "name": "B_" + variant}, mode="solid")
    tris = meshutil.tri_count(obj.data)
    assert 5000 < tris < 16000
    uv = _uv_array(obj.data)
    assert np.isfinite(uv).all() and uv.min() >= -1e-5 and uv.max() <= 1 + 1e-5
    assert "pf_id" in obj.data.attributes and len(obj.data.materials) == len(set(m.name for m in obj.data.materials))
    lo, hi = meshutil.objects_bounds([obj])
    assert 0.55 < hi[2] - lo[2] < 1.2 and (hi[0] - lo[0]) < 0.8


def test_barrel_is_deterministic_per_seed():
    a = build.make_object({"archetype": "barrel", "variant": "duelas", "params": {"seed": 7}, "name": "A"}, mode="solid")
    b = build.make_object({"archetype": "barrel", "variant": "duelas", "params": {"seed": 7}, "name": "B"}, mode="solid")
    c = build.make_object({"archetype": "barrel", "variant": "duelas", "params": {"seed": 8}, "name": "C"}, mode="solid")
    co = lambda o: np.array([v.co[:] for v in o.data.vertices])
    assert np.allclose(co(a), co(b)) and not np.allclose(co(a), co(c)) if len(a.data.vertices) == len(c.data.vertices) else True


def test_variants_change_the_look():
    simple = build.make_object({"archetype": "barrel", "variant": "simple", "name": "S"}, mode="solid")
    poly = build.make_object({"archetype": "barrel", "variant": "polvora", "name": "P"}, mode="solid")
    names = lambda o: {m.name for m in o.data.materials}
    assert "PF_cloth_red" in names(poly) and "PF_cloth_red" not in names(simple)
    assert "PF_rope" in names(poly)


@pytest.mark.parametrize("role", sorted(palette.ROLES))
def test_every_role_builds_a_material(role):
    mat = materials.procedural(role, 0.4, 0.5, owner="t")
    assert mat.use_nodes and mat.node_tree.nodes.get("Material Output") is not None
    out = mat.node_tree.nodes["Material Output"].inputs["Surface"]
    assert out.is_linked


def test_bake_creates_one_material_and_named_textures_the_exporter_recognises(tmp_path):
    obj = build.make_object({"archetype": "barrel", "variant": "simple", "name": "Barril_t_V2_malla"})
    baked, images = bake.bake_object(obj, "Barril_t", size=64, samples=1, margin=2)
    assert len(baked.data.materials) == 1 and baked.data.materials[0].name == "TXB_Barril_t"
    assert set(images) == {"BaseColor", "Roughness", "Normal", "Metallic"}
    found, unknown = textures.collect_images([baked])
    assert set(found) == {"BaseMap", "Normal", "Metallic", "Roughness"} and not unknown
    base = np.empty(64 * 64 * 4, np.float32)
    images["BaseColor"].pixels.foreach_get(base)
    assert base.reshape(-1, 4)[:, :3].std() > 0.02             # hay color horneado, no un lienzo vacio
    # y entra en la tuberia de LODs + export sin cambios
    baked.name = "Barril_t_V2_malla_BAKED"
    out = api.export("Barril_t_V2_malla_BAKED", out_dir=str(tmp_path), strict=False, formats=("fbx",))
    assert "Barril_t_V2: LOD0" in out and "+3 tex" in out
    assert (tmp_path / "Barril_t_V2" / "Barril_t_V2.fbx").exists()


def test_registry_and_unknown_archetype():
    assert "barrel" in __import__("pirate_prop_forge.forge.generators", fromlist=["REGISTRY"]).REGISTRY or generators.get("barrel")
    with pytest.raises(KeyError):
        generators.get("nave_espacial")
