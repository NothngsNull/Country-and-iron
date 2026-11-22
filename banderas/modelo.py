"""Datos de una bandera: una pila de capas (plantilla + color)."""
from __future__ import annotations

from dataclasses import dataclass, field

Color = tuple[int, int, int]


@dataclass
class CapaBandera:
    patron: str      # nombre de una plantilla en datos/banderas/patrones/
    color: Color


@dataclass
class Bandera:
    """Las capas se dibujan de abajo hacia arriba."""
    capas: list[CapaBandera] = field(default_factory=list)

    def firma(self) -> tuple:
        return tuple((c.patron, tuple(c.color)) for c in self.capas)

    def copia(self) -> "Bandera":
        return Bandera([CapaBandera(c.patron, tuple(c.color)) for c in self.capas])
