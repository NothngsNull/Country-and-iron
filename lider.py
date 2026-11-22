"""Líderes countryball: cuerpo + bandera + ojos (+ accesorios en el futuro).

Las imágenes están en datos/lideres/ (ver LEEME.txt ahí).
"""
from __future__ import annotations

import random
from collections import OrderedDict
from dataclasses import dataclass, field
from pathlib import Path

import pygame

from banderas import Bandera

CARPETA = Path(__file__).resolve().parent / "datos" / "lideres"
TAM = 240

NOMBRES = ["Bartolomé", "Pancracio", "Gertrudis", "Federico", "Eustaquio", "Remedios", "Anacleto",
           "Filomena", "Casimiro", "Leopoldina", "Segismundo", "Hermenegilda", "Rigoberto", "Clotilde",
           "Wenceslao", "Petronila", "Ataúlfo", "Brunilda", "Teodoro", "Gumersinda"]
APODOS = ["el Redondo", "la Esférica", "el Breve", "el Sin Brazos", "el Rodante", "el Grande",
          "el Pequeño", "el Mal Dibujado", "el Temible", "el Dormilón", "I", "II", "III", "el Sabio",
          "el Gruñón", "el Pintado en Paint"]


def nombre_lider_aleatorio(rng: random.Random | None = None) -> str:
    rng = rng or random.Random()
    return f"{rng.choice(NOMBRES)} {rng.choice(APODOS)}"


@dataclass
class Lider:
    nombre: str
    cuerpo: str
    ojos: str
    accesorios: list[str] = field(default_factory=list)


def _cargar_carpeta(carpeta: Path) -> dict[str, pygame.Surface]:
    imgs = {}
    for ruta in sorted(carpeta.glob("*.png")):
        try:
            img = pygame.image.load(str(ruta))
            sup = pygame.Surface(img.get_size(), pygame.SRCALPHA)
            sup.fill((0, 0, 0, 0))
            sup.blit(img, (0, 0))
            if sup.get_size() != (TAM, TAM):
                sup = pygame.transform.smoothscale(sup, (TAM, TAM))
            imgs[ruta.stem] = sup
        except pygame.error as e:
            print(f"[líderes] no se pudo leer {ruta.name}: {e}")
    return imgs


class GestorLideres:
    def __init__(self, gestor_banderas, carpeta: Path = CARPETA):
        self.banderas = gestor_banderas
        self.cuerpos = _cargar_carpeta(carpeta / "cuerpos")
        self.ojos = _cargar_carpeta(carpeta / "ojos")
        self.accesorios = _cargar_carpeta(carpeta / "accesorios")
        # El cuerpo "clasica" primero (el dibujado a mano original)
        if "clasica" in self.cuerpos:
            self.cuerpos = {"clasica": self.cuerpos.pop("clasica"), **self.cuerpos}
        if "normales" in self.ojos:
            self.ojos = {"normales": self.ojos.pop("normales"), **self.ojos}
        self._cache: OrderedDict[tuple, pygame.Surface] = OrderedDict()

    def aleatorio(self, rng: random.Random) -> Lider:
        return Lider(nombre_lider_aleatorio(rng), rng.choice(list(self.cuerpos)), rng.choice(list(self.ojos)))

    def dibujar(self, lider: Lider, bandera: Bandera, tam: int) -> pygame.Surface:
        clave = (lider.cuerpo, lider.ojos, tuple(lider.accesorios), bandera.firma(), tam)
        if clave in self._cache:
            self._cache.move_to_end(clave)
            return self._cache[clave]
        sup = self._componer(lider, bandera)
        if tam != TAM:
            sup = pygame.transform.smoothscale(sup, (tam, tam))
        self._cache[clave] = sup
        if len(self._cache) > 256:
            self._cache.popitem(last=False)
        return sup

    def _componer(self, lider: Lider, bandera: Bandera) -> pygame.Surface:
        cuerpo = self.cuerpos.get(lider.cuerpo) or next(iter(self.cuerpos.values()))
        sup = cuerpo.copy()
        # La bandera se estira sobre la zona del cuerpo y se multiplica:
        # el interior blanco toma los colores de la bandera y el contorno negro queda negro.
        caja = cuerpo.get_bounding_rect()
        tinte = pygame.Surface((TAM, TAM), pygame.SRCALPHA)
        tinte.fill((255, 255, 255, 255))
        tinte.blit(self.banderas.dibujar(bandera, caja.width, caja.height), caja.topleft)
        sup.blit(tinte, (0, 0), special_flags=pygame.BLEND_RGB_MULT)
        if lider.ojos in self.ojos:
            sup.blit(self.ojos[lider.ojos], (0, 0))
        for acc in lider.accesorios:
            if acc in self.accesorios:
                sup.blit(self.accesorios[acc], (0, 0))
        return sup
