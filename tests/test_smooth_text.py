import numpy as np
import pytest

from pirate_prop_forge.core import meshutil, postprocess
from test_postprocess import fake_obj


def roughness(obj):
    """Desviacion media de cada vertice respecto al promedio de sus vecinos (alta = grumoso)."""
    mesh = obj.data
    n = len(mesh.vertices)
    co = np.empty(n * 3, np.float32)
    mesh.vertices.foreach_get("co", co)
    co = co.reshape(n, 3).astype(float)
    ev = np.empty(len(mesh.edges) * 2, np.int32)
    mesh.edges.foreach_get("vertices", ev)
    ev = ev.reshape(-1, 2)
    acc = np.zeros_like(co)
    np.add.at(acc, ev[:, 0], co[ev[:, 1]])
    np.add.at(acc, ev[:, 1], co[ev[:, 0]])
    deg = np.maximum(np.bincount(ev.ravel(), minlength=n), 1)
    return float(np.linalg.norm(acc / deg[:, None] - co, axis=1).mean())


def noisy(obj, amount=2.0, seed=1):
    mesh = obj.data
    n = len(mesh.vertices)
    co = np.empty(n * 3, np.float32)
    mesh.vertices.foreach_get("co", co)
    co += np.random.default_rng(seed).normal(0, amount, co.shape).astype(np.float32)
    mesh.vertices.foreach_set("co", co)
    mesh.update()


def coords(obj):
    n = len(obj.data.vertices)
    co = np.empty(n * 3, np.float32)
    obj.data.vertices.foreach_get("co", co)
    return co.reshape(n, 3).astype(float)


def test_smoothing_moves_a_noisy_mesh_back_towards_the_clean_surface_and_keeps_size(tmp_path):
    obj = postprocess.import_mesh(fake_obj(tmp_path))
    postprocess.clean(obj)
    clean_co = coords(obj)
    noisy(obj, amount=4.0)
    err_before = np.linalg.norm(coords(obj) - clean_co, axis=1).mean()
    rough_before = roughness(obj)
    postprocess.smooth(obj, 2)
    err_after = np.linalg.norm(coords(obj) - clean_co, axis=1).mean()
    assert err_after < err_before * 0.8
    assert roughness(obj) < rough_before
    size0, size1 = clean_co.max(axis=0) - clean_co.min(axis=0), coords(obj).max(axis=0) - coords(obj).min(axis=0)
    assert np.allclose(size1, size0, rtol=0.1)                           # Taubin no encoge la forma


def test_smooth_zero_is_identity(tmp_path):
    obj = postprocess.import_mesh(fake_obj(tmp_path))
    pts = meshutil.world_points(obj).copy()
    postprocess.smooth(obj, 0)
    assert np.allclose(pts, meshutil.world_points(obj))


def test_smooth_option_validated_and_in_pipeline(tmp_path):
    with pytest.raises(Exception):
        postprocess.Options(smooth=11).validate()
    _o, rep = postprocess.process(fake_obj(tmp_path), "B", postprocess.Options(category="barril", material="none", smooth=4))
    assert rep["size_m"][2] == pytest.approx(0.85, abs=1e-3)


def test_higher_triangle_caps():
    assert postprocess.CATEGORIES["llave"][1] >= 5000 and postprocess.CATEGORIES["barril"][1] >= 9000
