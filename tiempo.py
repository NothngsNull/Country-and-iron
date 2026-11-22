"""Sistema de tiempo por tics, al estilo HOI4.

* 1 tic = 1 hora de juego.
* 5 velocidades: cuántas horas de juego pasan por segundo real.
* Cada vez que cambia el día se avisa (la lógica diaria del mundo va ahí).
* Controles: ESPACIO pausa/reanuda, teclas 1-5 eligen velocidad, + y - la cambian.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import pygame

# Horas de juego por segundo real para cada velocidad (1 = lenta ... 5 = lo más rápido)
HORAS_POR_SEGUNDO = {1: 3, 2: 8, 3: 24, 4: 72, 5: 240}
MAX_TICS_POR_FOTOGRAMA = 48            # evita congelar el juego si un fotograma tarda mucho
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre",
         "octubre", "noviembre", "diciembre"]


class Tiempo:
    def __init__(self, inicio: datetime = datetime(1836, 1, 1, 0)):
        self.fecha = inicio
        self.velocidad = 1
        self.pausado = True
        self._acumulado = 0.0
        self.tics = 0

    # ------------------------------------------------------------------
    def actualizar(self, dt: float) -> int:
        """Avanza el reloj. Devuelve cuántos días nuevos empezaron en este fotograma."""
        if self.pausado:
            return 0
        self._acumulado += dt * HORAS_POR_SEGUNDO[self.velocidad]
        tics = min(int(self._acumulado), MAX_TICS_POR_FOTOGRAMA)
        self._acumulado = min(self._acumulado - tics, 1.0)
        dias = 0
        for _ in range(tics):
            self.fecha += timedelta(hours=1)
            self.tics += 1
            if self.fecha.hour == 0:
                dias += 1
        return dias

    def manejar_evento(self, e) -> None:
        if e.type != pygame.KEYDOWN:
            return
        if e.key == pygame.K_SPACE:
            self.pausado = not self.pausado
        elif pygame.K_1 <= e.key <= pygame.K_5:
            self.velocidad = e.key - pygame.K_0
        elif pygame.K_KP1 <= e.key <= pygame.K_KP5:
            self.velocidad = e.key - pygame.K_KP1 + 1
        elif e.key in (pygame.K_PLUS, pygame.K_KP_PLUS, pygame.K_EQUALS):
            self.velocidad = min(5, self.velocidad + 1)
        elif e.key in (pygame.K_MINUS, pygame.K_KP_MINUS):
            self.velocidad = max(1, self.velocidad - 1)

    def texto(self) -> str:
        f = self.fecha
        return f"{f.hour:02d}:00, {f.day} de {MESES[f.month - 1]} de {f.year}"
