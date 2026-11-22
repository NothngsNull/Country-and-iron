"""Banderas aleatorias."""
from __future__ import annotations

import random

from banderas.modelo import Bandera, CapaBandera, Color

COLORES_BANDERA: dict[str, Color] = {
    "rojo": (186, 50, 54), "granate": (118, 34, 46), "naranja": (222, 122, 46),
    "amarillo": (236, 190, 52), "dorado": (200, 158, 66), "verde": (32, 118, 74),
    "verde_claro": (110, 168, 92), "azul": (34, 70, 138), "celeste": (120, 176, 220),
    "morado": (92, 58, 128), "blanco": (244, 242, 236), "negro": (28, 28, 30),
}

# Cada diseño es una lista de (plantilla, índice del color que usa esa capa).
DISENOS: list[list[tuple[str, int]]] = [
    [("liso", 0), ("franja_central", 1), ("franja_inferior", 2)],
    [("liso", 0), ("franja_vertical_central", 1), ("franja_derecha", 2)],
    [("liso", 0), ("mitad_inferior", 1)],
    [("liso", 0), ("mitad_derecha", 1)],
    [("liso", 0), ("cruz_nordica", 1)],
    [("liso", 0), ("cruz", 1)],
    [("liso", 0), ("aspa", 1)],
    [("liso", 0), ("franja_central", 1), ("franja_inferior", 0), ("triangulo_asta", 2)],
    [("liso", 0), ("canton", 1), ("estrella_canton", 2)],
    [("liso", 0), ("circulo", 1)],
    [("liso", 0), ("estrella", 1)],
    [("liso", 0), ("diagonal_ascendente", 1)],
    [("liso", 0), ("mitad_inferior", 1), ("circulo_asta", 2)],
    [("liso", 0), ("borde", 1), ("estrella", 1)],
    [("liso", 0), ("rombo", 1), ("circulo", 2)],
    [("liso", 0), ("banda_fina_central", 1)],
    [("liso", 0), ("media_luna", 1)],
]


def _distinto(a: Color, b: Color) -> bool:
    return sum(abs(x - y) for x, y in zip(a, b)) > 120


def bandera_aleatoria(rng: random.Random, patrones_disponibles=None,
                      color_nacion: Color | None = None) -> Bandera:
    disenos = [d for d in DISENOS
               if patrones_disponibles is None or all(p in patrones_disponibles for p, _ in d)]
    if not disenos:
        return Bandera([CapaBandera("liso", color_nacion or (128, 128, 128))])
    diseno = rng.choice(disenos)
    n_colores = max(i for _, i in diseno) + 1
    nombres = list(COLORES_BANDERA)
    colores: list[Color] = []
    if color_nacion is not None and rng.random() < 0.5:
        colores.append(color_nacion)
    while len(colores) < n_colores:
        c = COLORES_BANDERA[rng.choice(nombres)]
        if all(_distinto(c, otro) for otro in colores[-1:]):
            colores.append(c)
    return Bandera([CapaBandera(p, colores[i]) for p, i in diseno])
