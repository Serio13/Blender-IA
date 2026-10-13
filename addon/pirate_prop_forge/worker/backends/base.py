class JobCancelled(Exception):
    pass


class Backend:
    name = "base"
    output_format = "glb"

    def available(self):
        """(ok, motivo). Comprueba dependencias sin cargar modelos."""
        return True, ""

    def generate(self, image_path, out_path, params, progress, cancelled):
        """Escribe la malla en out_path. progress(fraccion, texto); cancelled() -> bool.

        Devuelve un dict con datos extra (p. ej. {"has_uv": True, "has_texture": True}).
        """
        raise NotImplementedError

    def unload(self):
        pass
