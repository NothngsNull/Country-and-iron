"""Herramientas sencillas de interfaz (botones, textos) en modo inmediato.

Cada fotograma se llama a `ui.nuevo_fotograma(eventos)` y luego a `ui.boton(...)`,
que dibuja el botón y devuelve True si se hizo clic en él.
"""
from __future__ import annotations

import sys

import pygame

# Colores de la interfaz
FONDO = (18, 20, 28)
PANEL = (30, 33, 44)
TARJETA = (42, 46, 60)
TARJETA_SOBRE = (56, 61, 80)
ACENTO = (110, 120, 230)
ACENTO_OSCURO = (60, 66, 140)
TEXTO = (235, 235, 245)
TEXTO_SUAVE = (160, 165, 185)
TEXTO_APAGADO = (100, 104, 122)
BORDE = (70, 75, 95)
ERROR = (220, 90, 90)


def salir():
    pygame.quit()
    sys.exit()


def eventos_comunes(eventos):
    """ESC o cerrar la ventana salen del juego desde cualquier pantalla."""
    for e in eventos:
        if e.type == pygame.QUIT or (e.type == pygame.KEYDOWN and e.key == pygame.K_ESCAPE):
            salir()


class UI:
    def __init__(self, escala: float = 1.0):
        self.escala = escala
        self._fuentes: dict[tuple[int, bool], pygame.font.Font] = {}
        self.raton = (0, 0)
        self.clic = False
        self.rueda = 0
        self.zonas: list[pygame.Rect] = []     # zonas ocupadas por la interfaz en este fotograma

    def px(self, valor: float) -> int:
        """Convierte un tamaño pensado para 1080p al tamaño real de la pantalla."""
        return max(1, round(valor * self.escala))

    def fuente(self, tam: int, negrita: bool = False) -> pygame.font.Font:
        tam = self.px(tam)
        clave = (tam, negrita)
        if clave not in self._fuentes:
            f = pygame.font.SysFont("segoeui,arial", tam, bold=negrita)
            self._fuentes[clave] = f
        return self._fuentes[clave]

    def nuevo_fotograma(self, eventos):
        self.raton = pygame.mouse.get_pos()
        self.clic = False
        self.rueda = 0
        self.zonas = []
        for e in eventos:
            if e.type == pygame.MOUSEBUTTONDOWN and e.button == 1:
                self.clic = True
            elif e.type == pygame.MOUSEWHEEL:
                self.rueda += e.y

    def ocupar(self, rect) -> pygame.Rect:
        """Marca una zona como interfaz (los clics ahí no llegan al mapa)."""
        rect = pygame.Rect(rect)
        self.zonas.append(rect)
        return rect

    def sobre_interfaz(self) -> bool:
        return any(r.collidepoint(self.raton) for r in self.zonas)

    def panel(self, sup, rect, alfa=235) -> pygame.Rect:
        rect = self.ocupar(rect)
        fondo = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(fondo, (*PANEL, alfa), fondo.get_rect(), border_radius=self.px(8))
        sup.blit(fondo, rect)
        pygame.draw.rect(sup, BORDE, rect, 1, border_radius=self.px(8))
        return rect

    def barra(self, sup, rect, valor, color=ACENTO):
        rect = pygame.Rect(rect)
        pygame.draw.rect(sup, TARJETA, rect, border_radius=rect.h // 2)
        lleno = rect.copy()
        lleno.w = max(0, int(rect.w * max(0.0, min(1.0, valor))))
        if lleno.w:
            pygame.draw.rect(sup, color, lleno, border_radius=rect.h // 2)

    def sobre(self, rect) -> bool:
        return pygame.Rect(rect).collidepoint(self.raton)

    def clic_en(self, rect) -> bool:
        return self.clic and self.sobre(rect)

    def texto(self, sup, texto, pos, tam=20, color=TEXTO, negrita=False, centro=False):
        img = self.fuente(tam, negrita).render(str(texto), True, color)
        r = img.get_rect(center=pos) if centro else img.get_rect(topleft=pos)
        sup.blit(img, r)
        return r

    def boton(self, sup, rect, texto, activo=False, habilitado=True, primario=False, tam=18) -> bool:
        rect = pygame.Rect(rect)
        encima = habilitado and self.sobre(rect)
        if not habilitado:
            fondo = PANEL
        elif primario:
            fondo = ACENTO if encima else ACENTO_OSCURO
        elif activo:
            fondo = ACENTO_OSCURO
        else:
            fondo = TARJETA_SOBRE if encima else TARJETA
        radio = self.px(6)
        pygame.draw.rect(sup, fondo, rect, border_radius=radio)
        pygame.draw.rect(sup, BORDE, rect, 1, border_radius=radio)
        self.texto(sup, texto, rect.center, tam, TEXTO if habilitado else TEXTO_APAGADO, centro=True)
        return encima and self.clic
