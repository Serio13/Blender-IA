"""Herramientas de construccion de mallas con bmesh: superficies parametricas, perfiles de revolucion, cajas
biseladas y esferas, con islas UV de tamano real que se empaquetan al final (densidad de textura uniforme)."""
import random
from math import atan2, cos, pi, radians, sin, sqrt

import bpy
import bmesh  # noqa: E402  (con el modulo bpy, bmesh solo existe tras importar bpy)
from mathutils import Matrix, Vector


class Builder:
    """Acumula caras en un unico BMesh. Cada cara lleva un rol (material), una isla UV y un id de variacion."""

    def __init__(self, name, seed=0):
        self.name = name
        self.bm = bmesh.new()
        self.uv = self.bm.loops.layers.uv.new("UVMap")
        self.isl = self.bm.faces.layers.int.new("pf_island")
        self.pid = self.bm.faces.layers.float.new("pf_id")
        self.islands = []           # (ancho_m, alto_m)
        self.roles = []             # orden de slots de material
        self.rng = random.Random(seed)
        self.density = None         # UV por metro tras empaquetar

    # -- registro ---------------------------------------------------------------------------------
    def role_index(self, role):
        if role not in self.roles:
            self.roles.append(role)
        return self.roles.index(role)

    def island(self, w, h):
        self.islands.append((max(w, 1e-4), max(h, 1e-4)))
        return len(self.islands) - 1

    def vert(self, co):
        return self.bm.verts.new(Vector(co))

    def face(self, verts, uvs, role, island, pid=0.0, smooth=True):
        try:
            f = self.bm.faces.new(verts)
        except ValueError:          # cara duplicada o degenerada
            return None
        f.material_index = self.role_index(role)
        f[self.isl] = island
        f[self.pid] = pid
        f.smooth = smooth
        for loop, st in zip(f.loops, uvs):
            loop[self.uv].uv = st
        return f

    # -- superficies ------------------------------------------------------------------------------
    def surface(self, fn, nu, nv, role, size, pid=0.0, flip=False, smooth=True, island=None):
        """Malla de nu x nv quads sobre fn(u, v) -> posicion, con u, v en [0, 1].

        size = (ancho_m, alto_m) de la isla UV (u recorre el ancho, v el alto). Devuelve el id de isla.
        """
        isl = self.island(*size) if island is None else island
        w, h = self.islands[isl]
        grid = [[self.vert(fn(i / nu, j / nv)) for i in range(nu + 1)] for j in range(nv + 1)]
        for j in range(nv):
            for i in range(nu):
                v00, v10, v11, v01 = grid[j][i], grid[j][i + 1], grid[j + 1][i + 1], grid[j + 1][i]
                quad = [v00, v10, v11, v01]
                uv = [(i / nu * w, j / nv * h), ((i + 1) / nu * w, j / nv * h),
                      ((i + 1) / nu * w, (j + 1) / nv * h), (i / nu * w, (j + 1) / nv * h)]
                if flip:
                    quad, uv = quad[::-1], uv[::-1]
                self.face(quad, uv, role, isl, pid, smooth)
        return isl

    def revolve(self, profile, segments, role, z_off=0.0, pid=0.0, flip=False, smooth=True, closed=True):
        """Superficie de revolucion alrededor de Z. profile = [(radio, z), ...]; cada arista es una isla."""
        pts = list(profile) + ([profile[0]] if closed else [])
        for (r0, z0), (r1, z1) in zip(pts[:-1], pts[1:]):
            length = sqrt((r1 - r0) ** 2 + (z1 - z0) ** 2)
            if length < 1e-6:
                continue
            circ = 2 * pi * (r0 + r1) / 2
            self.surface(lambda u, v, r0=r0, z0=z0, r1=r1, z1=z1: Vector((
                (r0 + (r1 - r0) * v) * cos(2 * pi * u), (r0 + (r1 - r0) * v) * sin(2 * pi * u),
                z_off + z0 + (z1 - z0) * v)), segments, 1, role, (circ, length), pid, flip, smooth)

    def tube(self, path, radius, sides, role, island_len=None, pid=0.0, cap_start=True, cap_end=True):
        """Tubo de seccion circular siguiendo una lista de puntos (radio constante o funcion de t)."""
        n = len(path)
        frames = []
        for k, p in enumerate(path):
            a = Vector(path[min(k + 1, n - 1)]) - Vector(path[max(k - 1, 0)])
            t = a.normalized() if a.length > 1e-9 else Vector((0, 0, 1))
            up = Vector((0, 0, 1)) if abs(t.z) < 0.95 else Vector((1, 0, 0))
            nrm = t.cross(up).normalized()
            frames.append((Vector(p), nrm, t.cross(nrm).normalized()))
        total = sum((Vector(path[i + 1]) - Vector(path[i])).length for i in range(n - 1))
        r_max = radius(0.0) if callable(radius) else radius
        isl = self.island(2 * pi * r_max, max(total, 1e-3))
        w, h = self.islands[isl]
        rings, acc = [], 0.0
        for k, (p, nrm, bn) in enumerate(frames):
            if k:
                acc += (Vector(path[k]) - Vector(path[k - 1])).length
            r = radius(k / (n - 1)) if callable(radius) else radius
            rings.append(([self.vert(p + (nrm * cos(2 * pi * s / sides) + bn * sin(2 * pi * s / sides)) * r)
                           for s in range(sides)], acc))
        for k in range(n - 1):
            (ra, da), (rb, db) = rings[k], rings[k + 1]
            for s in range(sides):
                s2 = (s + 1) % sides
                quad = [ra[s], ra[s2], rb[s2], rb[s]]
                uv = [(s / sides * w, da), ((s + 1) / sides * w, da), ((s + 1) / sides * w, db), (s / sides * w, db)]
                self.face(quad, uv, role, isl, pid)
        for ring, flipc, at in ((rings[0][0], True, 0.0), (rings[-1][0], False, total)):
            if (flipc and cap_start) or (not flipc and cap_end):
                verts = ring[::-1] if flipc else ring
                self.face(verts, [(w * 0.5 + 0.0 * i, at) for i in range(len(verts))], role, isl, pid, smooth=False)
        return isl

    # -- solidos pequenos ---------------------------------------------------------------------------
    def box(self, center, size, role, rot_z=0.0, bevel=0.0, segments=2, pid=0.0, smooth=True):
        """Caja biselada con una unica isla UV (proyeccion de caja en metros)."""
        tmp = bmesh.new()
        bmesh.ops.create_cube(tmp, size=1.0)
        for v in tmp.verts:
            v.co = Vector((v.co.x * size[0], v.co.y * size[1], v.co.z * size[2]))
        if bevel > 0:
            bmesh.ops.bevel(tmp, geom=tmp.edges[:], offset=min(bevel, min(size) * 0.45), segments=segments,
                            affect="EDGES")
        mat = Matrix.Translation(Vector(center)) @ Matrix.Rotation(rot_z, 4, "Z")
        return self._absorb(tmp, mat, role, (max(size) * 2, max(size) * 2), pid, smooth)

    def sphere(self, center, radius, role, u=10, v=6, scale=(1, 1, 1), pid=0.0, smooth=True):
        tmp = bmesh.new()
        bmesh.ops.create_uvsphere(tmp, u_segments=u, v_segments=v, radius=radius)
        for vert in tmp.verts:
            vert.co = Vector((vert.co.x * scale[0], vert.co.y * scale[1], vert.co.z * scale[2]))
        return self._absorb(tmp, Matrix.Translation(Vector(center)), role, (radius * 4, radius * 4), pid, smooth)

    def cylinder(self, center, radius, height, role, segments=12, rot=None, pid=0.0, smooth=True, bevel=0.0):
        tmp = bmesh.new()
        bmesh.ops.create_cone(tmp, cap_ends=True, segments=segments, radius1=radius, radius2=radius, depth=height)
        if bevel > 0:
            bmesh.ops.bevel(tmp, geom=[e for e in tmp.edges if len({f for f in e.link_faces}) == 2 and
                                       abs(e.calc_face_angle(0.0)) > 0.8], offset=bevel, segments=1, affect="EDGES")
        mat = Matrix.Translation(Vector(center)) @ (rot if rot is not None else Matrix.Identity(4))
        return self._absorb(tmp, mat, role, (radius * 4, radius * 4 + height), pid, smooth)

    def _absorb(self, tmp, matrix, role, island_size, pid, smooth):
        """Copia las caras de `tmp` a este constructor con proyeccion de caja como UV (metros)."""
        isl = self.island(*island_size)
        w, h = self.islands[isl]
        mapping = {}
        tmp.normal_update()
        for v in tmp.verts:
            mapping[v] = self.vert(matrix @ v.co)
        rot = matrix.to_3x3()
        for f in tmp.faces:
            n = rot @ f.normal
            axis = max(range(3), key=lambda a: abs(n[a]))
            keep = [a for a in range(3) if a != axis]
            uvs = []
            for loop in f.loops:
                p = matrix @ loop.vert.co
                uvs.append(((p[keep[0]] * 1.0) % w, (p[keep[1]] * 1.0) % h))
            self.face([mapping[v] for v in f.verts], uvs, role, isl, pid, smooth)
        tmp.free()
        return isl

    # -- empaquetado y salida -----------------------------------------------------------------------
    def pack(self, margin=0.004):
        """Coloca todas las islas (rectangulos) en [0,1]^2 con la mayor escala uniforme que quepa."""
        order = sorted(range(len(self.islands)), key=lambda i: -self.islands[i][1])

        def attempt(scale):
            x = y = row_h = 0.0
            pos = {}
            for i in order:
                w, h = self.islands[i][0] * scale, self.islands[i][1] * scale
                if w + 2 * margin > 1.0:
                    return None
                if x + w + margin > 1.0:
                    x, y, row_h = 0.0, y + row_h, 0.0
                pos[i] = (x + margin, y + margin)
                x += w + margin
                row_h = max(row_h, h + margin)
            return pos if y + row_h + margin <= 1.0 else None

        lo, hi = 1e-4, 4.0
        for _ in range(40):
            mid = (lo + hi) / 2
            if attempt(mid) is not None:
                lo = mid
            else:
                hi = mid
        scale = lo
        pos = attempt(scale)
        for f in self.bm.faces:
            ox, oy = pos[f[self.isl]]
            for loop in f.loops:
                u, v = loop[self.uv].uv
                loop[self.uv].uv = (ox + u * scale, oy + v * scale)
        self.density = scale
        return scale

    def finish(self, weld=1e-5, sharp_deg=38.0):
        """Empaqueta, suelda, marca aristas duras y devuelve un Mesh (materiales sin asignar)."""
        if self.density is None:
            self.pack()
        bmesh.ops.remove_doubles(self.bm, verts=self.bm.verts, dist=weld)
        limit = radians(sharp_deg)
        for e in self.bm.edges:
            if e.is_manifold and e.calc_face_angle(0.0) > limit:
                e.smooth = False
        mesh = bpy.data.meshes.new(self.name)
        self.bm.to_mesh(mesh)
        self.bm.free()
        return mesh
