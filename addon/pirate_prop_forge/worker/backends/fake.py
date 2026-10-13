"""Backend de prueba: un barril tosco con defectos tipicos de una malla generada por IA (sin escala, fuera
del origen, vertices sueltos, duplicados y un fragmento flotante). No usa IA; sirve para probar el flujo."""
import math
import time

from .base import Backend as _Base, JobCancelled


class Backend(_Base):
    name = "fake"
    output_format = "obj"

    def generate(self, image_path, out_path, params, progress, cancelled):
        delay = float(params.get("fake_delay", 0.0))
        steps = 5
        for i in range(steps):
            if cancelled():
                raise JobCancelled()
            progress((i + 1) / steps, "paso %d/%d" % (i + 1, steps))
            if delay:
                time.sleep(delay / steps)
        seg, rings, r = 16, 6, 40.0          # tamaño arbitrario (como sale de una IA)
        verts, faces = [], []
        for j in range(rings + 1):
            t = j / rings
            z = (t - 0.5) * 100.0 + 300.0    # desplazado del origen
            rr = r * (1.0 + 0.18 * math.sin(math.pi * t))
            for i in range(seg):
                a = 2 * math.pi * i / seg
                verts.append((rr * math.cos(a) + 50.0, rr * math.sin(a) - 20.0, z))
        for j in range(rings):
            for i in range(seg):
                a, b = j * seg + i, j * seg + (i + 1) % seg
                faces.append((a, b, b + seg, a + seg))
        # tapas (indices desde 0; se escriben desde 1)
        verts.append((50.0, -20.0, 250.0)); bot = len(verts) - 1
        verts.append((50.0, -20.0, 350.0)); top = len(verts) - 1
        for i in range(seg):
            faces.append((bot, (i + 1) % seg, i))
            faces.append((top, rings * seg + i, rings * seg + (i + 1) % seg))
        # defectos: vertice suelto, duplicado, fragmento flotante
        verts.append((500.0, 500.0, 500.0))
        verts.append(verts[0])
        base = len(verts)
        verts += [(900.0, 0.0, 0.0), (905.0, 0.0, 0.0), (900.0, 5.0, 0.0)]
        faces.append((base, base + 1, base + 2))
        with open(out_path, "w") as f:
            for v in verts:
                f.write("v %.5f %.5f %.5f\n" % (v[0], v[2], -v[1]))   # OBJ es Y-arriba
            for fc in faces:
                f.write("f " + " ".join(str(i + 1) for i in fc) + "\n")
        return {"has_uv": False, "has_texture": False}
