"""Dibujo de banderas a cualquier tamaño.

  * Cada plantilla es un PNG en `datos/banderas/patrones/`. Lo NEGRO es la zona
    que se pinta; lo blanco queda transparente (si el PNG tiene alfa, se usa el alfa).
  * Una bandera es una pila de capas (plantilla + color).
  * Las plantillas se escalan con suavizado, así la misma bandera sirve para un
    icono de 16 px o una vista previa grande. Lo ya dibujado se guarda en caché.
"""
from __future__ import annotations

from collections import OrderedDict
from pathlib import Path

import numpy as np
import pygame

from banderas.modelo import Bandera

PROPORCION = 3 / 2          # ancho / alto
COLOR_VACIO = (120, 120, 120)
CARPETA_PATRONES = Path(__file__).resolve().parent.parent / "datos" / "banderas" / "patrones"


def tamano_para_alto(alto: int) -> tuple[int, int]:
    return max(1, round(alto * PROPORCION)), max(1, alto)


class GestorBanderas:
    def __init__(self, carpeta: Path = CARPETA_PATRONES, max_cache: int = 512):
        self.patrones: dict[str, Path] = {p.stem: p for p in sorted(Path(carpeta).glob("*.png"))}
        self._mascaras: dict[str, pygame.Surface | None] = {}
        self._cache: OrderedDict[tuple, pygame.Surface] = OrderedDict()
        self._max_cache = max_cache

    def mascara(self, patron: str) -> pygame.Surface | None:
        if patron not in self._mascaras:
            ruta = self.patrones.get(patron)
            sup = None
            if ruta is not None:
                try:
                    sup = _cargar_mascara(ruta)
                except (OSError, pygame.error) as e:
                    print(f"[banderas] no se pudo leer la plantilla '{patron}': {e}")
            self._mascaras[patron] = sup
        return self._mascaras[patron]

    def dibujar(self, bandera: Bandera, ancho: int, alto: int) -> pygame.Surface:
        ancho, alto = max(1, int(ancho)), max(1, int(alto))
        clave = (bandera.firma(), ancho, alto)
        sup = self._cache.get(clave)
        if sup is not None:
            self._cache.move_to_end(clave)
            return sup
        sup = self._componer(bandera, ancho, alto)
        self._cache[clave] = sup
        if len(self._cache) > self._max_cache:
            self._cache.popitem(last=False)
        return sup

    def _componer(self, bandera: Bandera, ancho: int, alto: int) -> pygame.Surface:
        sup = pygame.Surface((ancho, alto), pygame.SRCALPHA)
        sup.fill((*COLOR_VACIO, 255))
        for capa in bandera.capas:
            m = self.mascara(capa.patron)
            if m is None:
                continue
            tinte = _escalar(m, ancho, alto).copy()
            tinte.fill((*capa.color, 255), special_flags=pygame.BLEND_RGBA_MULT)
            sup.blit(tinte, (0, 0))
        return sup


def _escalar(sup: pygame.Surface, ancho: int, alto: int) -> pygame.Surface:
    if sup.get_size() == (ancho, alto):
        return sup
    return pygame.transform.smoothscale(sup, (ancho, alto))


def _cargar_mascara(ruta: Path) -> pygame.Surface:
    """Convierte un PNG de plantilla en una superficie blanca con alfa = forma."""
    img = pygame.image.load(str(ruta))
    rgb = pygame.surfarray.array3d(img).astype(np.uint16)
    alfa = None
    if img.get_flags() & pygame.SRCALPHA:
        a = pygame.surfarray.array_alpha(img)
        if (a < 255).any():
            alfa = a
    if alfa is None:  # negro = forma, blanco = vacío
        gris = (rgb[..., 0] * 30 + rgb[..., 1] * 59 + rgb[..., 2] * 11) // 100
        alfa = (255 - gris).astype(np.uint8)
    alfa = np.where(alfa >= 250, 255, np.where(alfa <= 5, 0, alfa)).astype(np.uint8)
    w, h = img.get_size()
    sup = pygame.Surface((w, h), pygame.SRCALPHA)
    sup.fill((255, 255, 255, 255))
    pygame.surfarray.pixels_alpha(sup)[:] = alfa
    return sup
