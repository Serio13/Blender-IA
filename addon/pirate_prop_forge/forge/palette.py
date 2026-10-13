"""Paleta de estilo del proyecto (valores lineales tomados de la hoja de estilo HOJA_ESTILO).

Cada rol de material tiene color base, rugosidad y metalico. Los roles de madera usan una rampa de tonos
(clara -> profunda) que se reparte entre las tablas.
"""

# rol -> (color lineal RGB, rugosidad, metalico)
ROLES = {
    "wood_light": ((0.48, 0.30, 0.15), 0.55, 0.0),
    "wood": ((0.32, 0.191, 0.094), 0.50, 0.0),
    "wood_dark": ((0.20, 0.115, 0.058), 0.50, 0.0),
    "wood_deep": ((0.12, 0.068, 0.034), 0.50, 0.0),
    "iron": ((0.111, 0.133, 0.164), 0.45, 0.0),
    "iron_light": ((0.272, 0.311, 0.364), 0.40, 0.0),
    "gold": ((0.924, 0.659, 0.119), 0.30, 0.0),
    "copper": ((0.592, 0.201, 0.066), 0.40, 0.0),
    "rope": ((0.592, 0.453, 0.212), 0.70, 0.0),
    "cloth_red": ((0.723, 0.101, 0.07), 0.70, 0.0),
    "cloth_red_d": ((0.50, 0.06, 0.049), 0.70, 0.0),
    "cloth_blue": ((0.13, 0.302, 0.599), 0.70, 0.0),
    "cream": ((0.883, 0.82, 0.659), 0.70, 0.0),
    "stone": ((0.384, 0.354, 0.311), 0.70, 0.0),
    "stone_dark": ((0.212, 0.198, 0.18), 0.70, 0.0),
    "sand": ((0.812, 0.652, 0.359), 0.70, 0.0),
    "leaf": ((0.16, 0.431, 0.104), 0.70, 0.0),
    "water": ((0.068, 0.374, 0.58), 0.30, 0.0),
}

WOODS = ("wood_light", "wood", "wood_dark", "wood_deep")
METALS = ("iron", "iron_light", "copper", "gold")
CLOTHS = ("cloth_red", "cloth_red_d", "cloth_blue", "cream")

# palabras (es/en) -> rol, para el resolutor por reglas
ALIASES = {
    "madera clara": "wood_light", "light wood": "wood_light", "clara": "wood_light",
    "madera oscura": "wood_dark", "dark wood": "wood_dark", "oscura": "wood_dark",
    "madera": "wood", "wood": "wood",
    "hierro": "iron", "iron": "iron", "acero": "iron_light", "steel": "iron_light",
    "oro": "gold", "dorado": "gold", "gold": "gold", "golden": "gold",
    "cobre": "copper", "copper": "copper", "bronce": "copper",
    "cuerda": "rope", "rope": "rope",
    "rojo": "cloth_red", "red": "cloth_red", "azul": "cloth_blue", "blue": "cloth_blue",
    "crema": "cream", "cream": "cream",
}


def role_color(role):
    return ROLES[role][0]


def role_rough(role):
    return ROLES[role][1]


def role_metal(role):
    return ROLES[role][2]
