"""Pantalla de creación de la civilización del jugador (nombre y bandera).

El editor de bandera está adaptado del de Map and Irons: cada capa es una
plantilla PNG pintada de un color, y las capas se dibujan de abajo hacia arriba.
"""
from __future__ import annotations

import random

import pygame

import ui as U
from banderas import Bandera, CapaBandera, COLORES_BANDERA, bandera_aleatoria, tamano_para_alto

MAX_CAPAS = 12
MAX_NOMBRE = 24
PALETA = list(COLORES_BANDERA.values()) + [
    (60, 60, 64), (140, 140, 144), (210, 120, 150), (120, 80, 50), (40, 140, 150), (20, 40, 80),
    (150, 160, 70), (250, 220, 120), (160, 40, 90), (70, 110, 60), (200, 90, 70), (110, 130, 170),
]


def nombre_patron(pid: str) -> str:
    return "Fondo liso" if pid == "liso" else pid.replace("_", " ").capitalize()


class CreacionCivilizacion:
    def __init__(self, ui: U.UI, gestor):
        self.ui = ui
        self.gestor = gestor
        self.nombre = ""
        self.bandera = bandera_aleatoria(random.Random(), gestor.patrones)
        self.capa_sel = len(self.bandera.capas) - 1
        self.scroll_patrones = 0
        self.parpadeo = 0.0

    def ejecutar(self, pantalla, reloj):
        """Bucle de la pantalla. Devuelve (nombre, bandera) al pulsar Continuar."""
        pygame.key.start_text_input()
        while True:
            self.parpadeo += reloj.tick(60) / 1000
            eventos = pygame.event.get()
            U.eventos_comunes(eventos)
            self.ui.nuevo_fotograma(eventos)
            for e in eventos:
                if e.type == pygame.TEXTINPUT and len(self.nombre) < MAX_NOMBRE:
                    self.nombre += e.text
                elif e.type == pygame.KEYDOWN:
                    if e.key == pygame.K_BACKSPACE:
                        self.nombre = self.nombre[:-1]
                    elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self._valido():
                        pygame.key.stop_text_input()
                        return self.nombre.strip(), self.bandera
            if self.dibujar(pantalla):
                pygame.key.stop_text_input()
                return self.nombre.strip(), self.bandera
            pygame.display.flip()

    def _valido(self) -> bool:
        return bool(self.nombre.strip())

    def _capa(self) -> CapaBandera | None:
        if 0 <= self.capa_sel < len(self.bandera.capas):
            return self.bandera.capas[self.capa_sel]
        return None

    # ------------------------------------------------------------------
    def dibujar(self, sup) -> bool:
        ui, P = self.ui, self.ui.px
        W, H = sup.get_size()
        sup.fill(U.FONDO)

        ui.texto(sup, "Crea tu civilización", (P(80), P(40)), 44, U.TEXTO, True)
        ui.texto(sup, "Por ahora puedes elegir el nombre y la bandera. ESC para salir.",
                 (P(82), P(102)), 18, U.TEXTO_SUAVE)

        # --- Columna izquierda: nombre y vista previa -------------------------
        x = P(80)
        ui.texto(sup, "Nombre de la civilización", (x, P(150)), 18, U.TEXTO_SUAVE)
        caja = pygame.Rect(x, P(178), P(540), P(56))
        pygame.draw.rect(sup, U.PANEL, caja, border_radius=P(6))
        pygame.draw.rect(sup, U.ACENTO, caja, 2, border_radius=P(6))
        texto = self.nombre + ("|" if int(self.parpadeo * 2) % 2 == 0 else "")
        if self.nombre:
            ui.texto(sup, texto, (caja.x + P(14), caja.y + P(10)), 26, U.TEXTO)
        else:
            ui.texto(sup, "Escribe un nombre...", (caja.x + P(14), caja.y + P(12)), 24, U.TEXTO_APAGADO)

        y = P(270)
        w_prev, h_prev = tamano_para_alto(P(360))
        sup.blit(self.gestor.dibujar(self.bandera, w_prev, h_prev), (x, y))
        pygame.draw.rect(sup, U.BORDE, (x, y, w_prev, h_prev), 1)
        px, py = x, y + h_prev + P(16)
        for alto in (64, 40, 24):
            s = self.gestor.dibujar(self.bandera, *tamano_para_alto(P(alto)))
            sup.blit(s, (px, py))
            px += s.get_width() + P(12)
        if ui.boton(sup, (x, py + P(90), P(260), P(50)), "Bandera aleatoria"):
            self.bandera = bandera_aleatoria(random.Random(), self.gestor.patrones)
            self.capa_sel = len(self.bandera.capas) - 1

        # --- Columna central: capas -------------------------------------------
        cx, cw = P(700), P(440)
        cy = P(150)
        ui.texto(sup, f"Capas ({len(self.bandera.capas)}/{MAX_CAPAS})  ·  la de arriba se dibuja encima",
                 (cx, cy), 18, U.TEXTO_SUAVE)
        cy += P(30)
        alto_fila = P(56)
        for i in reversed(range(len(self.bandera.capas))):
            capa = self.bandera.capas[i]
            fila = pygame.Rect(cx, cy, cw, alto_fila - P(6))
            sel = i == self.capa_sel
            pygame.draw.rect(sup, U.ACENTO_OSCURO if sel else (U.TARJETA_SOBRE if ui.sobre(fila) else U.TARJETA),
                             fila, border_radius=P(6))
            mini = self.gestor.dibujar(Bandera([CapaBandera("liso", (52, 55, 60)), capa]), P(54), P(36))
            sup.blit(mini, (fila.x + P(8), fila.y + P(7)))
            ui.texto(sup, nombre_patron(capa.patron), (fila.x + P(76), fila.y + P(12)), 18, U.TEXTO, sel)
            botones_capa = False
            for k, simbolo in enumerate(("↑", "↓", "×")):
                r = pygame.Rect(fila.right - P(126) + k * P(40), fila.y + P(8), P(34), P(34))
                if ui.boton(sup, r, simbolo, tam=18):
                    self._accion_capa(i, simbolo)
                    botones_capa = True
            if not botones_capa and ui.clic_en(fila):
                self.capa_sel = i
            cy += alto_fila
        if ui.boton(sup, (cx, cy + P(6), cw, P(46)), "+ Añadir capa",
                    habilitado=len(self.bandera.capas) < MAX_CAPAS):
            self.bandera.capas.append(CapaBandera("franja_central", (244, 242, 236)))
            self.capa_sel = len(self.bandera.capas) - 1

        # --- Columna derecha: plantilla y color de la capa seleccionada --------
        capa = self._capa()
        dx = P(1200)
        dw = W - dx - P(80)
        dy = P(150)
        ui.texto(sup, "Plantilla de la capa", (dx, dy), 18, U.TEXTO_SUAVE)
        dy += P(30)
        tw, th, sep = P(90), P(60), P(10)
        cols = max(1, dw // (tw + sep))
        patrones = list(self.gestor.patrones)
        filas_totales = (len(patrones) + cols - 1) // cols
        filas_visibles = min(filas_totales, 5)
        zona = pygame.Rect(dx, dy, dw, filas_visibles * (th + sep))
        if ui.sobre(zona) and ui.rueda:
            self.scroll_patrones -= ui.rueda
        max_scroll = max(0, filas_totales - filas_visibles)
        self.scroll_patrones = max(0, min(self.scroll_patrones, max_scroll))
        inicio = self.scroll_patrones * cols
        for k, pid in enumerate(patrones[inicio:inicio + cols * filas_visibles]):
            r = pygame.Rect(dx + (k % cols) * (tw + sep), dy + (k // cols) * (th + sep), tw, th)
            color = capa.color if capa else (220, 222, 226)
            sup.blit(self.gestor.dibujar(Bandera([CapaBandera("liso", (52, 55, 60)),
                                                  CapaBandera(pid, color)]), tw, th), r)
            activo = capa is not None and capa.patron == pid
            if activo or ui.sobre(r):
                pygame.draw.rect(sup, U.TEXTO if activo else U.TEXTO_SUAVE, r.inflate(P(6), P(6)), 2,
                                 border_radius=P(3))
            if ui.clic_en(r) and capa is not None:
                capa.patron = pid
        dy += zona.height
        if max_scroll:
            ui.texto(sup, f"Rueda del ratón para ver más ({self.scroll_patrones + 1}/{max_scroll + 1})",
                     (dx, dy), 15, U.TEXTO_APAGADO)
        dy += P(36)

        ui.texto(sup, "Color de la capa", (dx, dy), 18, U.TEXTO_SUAVE)
        dy += P(30)
        lado, sep = P(40), P(8)
        cols_c = max(1, dw // (lado + sep))
        for k, c in enumerate(PALETA):
            r = pygame.Rect(dx + (k % cols_c) * (lado + sep), dy + (k // cols_c) * (lado + sep), lado, lado)
            pygame.draw.rect(sup, c, r, border_radius=P(4))
            if capa is not None and tuple(capa.color) == tuple(c):
                pygame.draw.rect(sup, U.TEXTO, r.inflate(P(6), P(6)), 2, border_radius=P(5))
            if ui.clic_en(r) and capa is not None:
                capa.color = tuple(c)

        # --- Continuar ------------------------------------------------------------
        boton = pygame.Rect(W - P(380), H - P(110), P(300), P(64))
        if not self._valido():
            ui.texto(sup, "Escribe un nombre para continuar",
                     (boton.x, boton.y - P(30)), 16, U.TEXTO_APAGADO)
        return ui.boton(sup, boton, "Crear líder →", habilitado=self._valido(),
                        primario=True, tam=20)

    def _accion_capa(self, i: int, simbolo: str) -> None:
        capas = self.bandera.capas
        if simbolo == "×":
            if len(capas) > 1:
                capas.pop(i)
                self.capa_sel = min(self.capa_sel, len(capas) - 1)
        elif simbolo == "↑" and i < len(capas) - 1:
            capas[i], capas[i + 1] = capas[i + 1], capas[i]
            self.capa_sel = i + 1
        elif simbolo == "↓" and i > 0:
            capas[i], capas[i - 1] = capas[i - 1], capas[i]
            self.capa_sel = i - 1
