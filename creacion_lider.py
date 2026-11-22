"""Pantalla de creación del líder: nombre, tipo de cuerpo, ojos y accesorios."""
from __future__ import annotations

import random

import pygame

import ui as U
from lider import Lider, nombre_lider_aleatorio

MAX_NOMBRE = 28


class CreacionLider:
    def __init__(self, ui: U.UI, gestor_lideres, nombre_civ: str, bandera, lider: Lider | None = None):
        self.ui = ui
        self.gl = gestor_lideres
        self.nombre_civ = nombre_civ
        self.bandera = bandera
        self.lider = lider or Lider(nombre_lider_aleatorio(), next(iter(gestor_lideres.cuerpos)),
                                    next(iter(gestor_lideres.ojos)))
        self.parpadeo = 0.0

    def ejecutar(self, pantalla, reloj):
        """Devuelve el Lider al continuar, o None si el jugador quiere volver a la bandera."""
        pygame.key.start_text_input()
        try:
            while True:
                self.parpadeo += reloj.tick(60) / 1000
                eventos = pygame.event.get()
                U.eventos_comunes(eventos)
                self.ui.nuevo_fotograma(eventos)
                for e in eventos:
                    if e.type == pygame.TEXTINPUT and len(self.lider.nombre) < MAX_NOMBRE:
                        self.lider.nombre += e.text
                    elif e.type == pygame.KEYDOWN:
                        if e.key == pygame.K_BACKSPACE:
                            self.lider.nombre = self.lider.nombre[:-1]
                        elif e.key in (pygame.K_RETURN, pygame.K_KP_ENTER) and self._valido():
                            return self._final()
                resultado = self.dibujar(pantalla)
                if resultado == "continuar":
                    return self._final()
                if resultado == "volver":
                    return None
                pygame.display.flip()
        finally:
            pygame.key.stop_text_input()

    def _valido(self) -> bool:
        return bool(self.lider.nombre.strip())

    def _final(self) -> Lider:
        self.lider.nombre = self.lider.nombre.strip()
        return self.lider

    # ------------------------------------------------------------------
    def dibujar(self, sup) -> str | None:
        ui, P = self.ui, self.ui.px
        W, H = sup.get_size()
        sup.fill(U.FONDO)
        ui.texto(sup, "Crea a tu líder", (P(80), P(40)), 44, U.TEXTO, True)
        ui.texto(sup, f"Quien gobernará {self.nombre_civ}. Mientras peor dibujado, mejor.",
                 (P(82), P(102)), 18, U.TEXTO_SUAVE)

        # --- Vista previa grande ---------------------------------------------
        x = P(80)
        tam_prev = P(480)
        marco = pygame.Rect(x, P(150), tam_prev + P(40), tam_prev + P(40))
        pygame.draw.rect(sup, (236, 234, 228), marco, border_radius=P(10))   # "papel" de fondo
        sup.blit(self.gl.dibujar(self.lider, self.bandera, tam_prev), (marco.x + P(20), marco.y + P(20)))
        ui.texto(sup, self.lider.nombre or "...", (marco.centerx, marco.bottom + P(30)), 26, U.TEXTO, True,
                 centro=True)
        ui.texto(sup, f"Líder de {self.nombre_civ}", (marco.centerx, marco.bottom + P(62)), 18, U.TEXTO_SUAVE,
                 centro=True)

        # --- Columna derecha ----------------------------------------------------
        dx = marco.right + P(80)
        dw = W - dx - P(80)
        dy = P(150)
        ui.texto(sup, "Nombre del líder", (dx, dy), 18, U.TEXTO_SUAVE)
        caja = pygame.Rect(dx, dy + P(28), min(P(600), dw - P(200)), P(56))
        pygame.draw.rect(sup, U.PANEL, caja, border_radius=P(6))
        pygame.draw.rect(sup, U.ACENTO, caja, 2, border_radius=P(6))
        cursor = "|" if int(self.parpadeo * 2) % 2 == 0 else ""
        ui.texto(sup, self.lider.nombre + cursor, (caja.x + P(14), caja.y + P(10)), 26, U.TEXTO)
        if ui.boton(sup, (caja.right + P(16), caja.y, P(180), caja.height), "Nombre al azar"):
            self.lider.nombre = nombre_lider_aleatorio()
        dy = caja.bottom + P(36)

        # Selectores con miniaturas (cuerpo y ojos)
        dy = self._selector(sup, "Tipo de esfera", self.gl.cuerpos, "cuerpo", dx, dy, dw)
        dy = self._selector(sup, "Ojos", self.gl.ojos, "ojos", dx, dy, dw)

        # Accesorios (vacío por ahora)
        ui.texto(sup, "Accesorios", (dx, dy), 18, U.TEXTO_SUAVE)
        zona = pygame.Rect(dx, dy + P(28), dw, P(90))
        pygame.draw.rect(sup, U.PANEL, zona, border_radius=P(6))
        pygame.draw.rect(sup, U.BORDE, zona, 1, border_radius=P(6))
        if self.gl.accesorios:
            self._selector_accesorios(sup, zona)
        else:
            ui.texto(sup, "Todavía no hay accesorios. Pronto: sombreros, bigotes, monóculos...",
                     zona.center, 18, U.TEXTO_APAGADO, centro=True)

        if ui.boton(sup, (dx, H - P(110), P(240), P(64)), "Aleatorio"):
            rng = random.Random()
            self.lider = self.gl.aleatorio(rng)

        # --- Navegación ---------------------------------------------------------
        if ui.boton(sup, (P(80), H - P(110), P(300), P(64)), "← Volver a la bandera", tam=20):
            return "volver"
        if ui.boton(sup, (W - P(380), H - P(110), P(300), P(64)), "Elegir zona de inicio →",
                    habilitado=self._valido(), primario=True, tam=20):
            return "continuar"
        return None

    def _selector(self, sup, titulo, opciones: dict, atributo: str, dx, dy, dw) -> int:
        ui, P = self.ui, self.ui.px
        ui.texto(sup, titulo, (dx, dy), 18, U.TEXTO_SUAVE)
        dy += P(28)
        lado, sep = P(104), P(12)
        cols = max(1, dw // (lado + sep))
        for k, nombre in enumerate(opciones):
            r = pygame.Rect(dx + (k % cols) * (lado + sep), dy + (k // cols) * (lado + sep + P(22)), lado, lado)
            activo = getattr(self.lider, atributo) == nombre
            pygame.draw.rect(sup, U.ACENTO_OSCURO if activo else (U.TARJETA_SOBRE if ui.sobre(r) else U.TARJETA),
                             r, border_radius=P(8))
            prueba = Lider(self.lider.nombre, self.lider.cuerpo, self.lider.ojos, self.lider.accesorios)
            setattr(prueba, atributo, nombre)
            sup.blit(self.gl.dibujar(prueba, self.bandera, lado - P(12)), (r.x + P(6), r.y + P(6)))
            if activo:
                pygame.draw.rect(sup, U.TEXTO, r, 2, border_radius=P(8))
            ui.texto(sup, nombre.capitalize(), (r.centerx, r.bottom + P(11)), 14,
                     U.TEXTO if activo else U.TEXTO_SUAVE, centro=True)
            if ui.clic_en(r):
                setattr(self.lider, atributo, nombre)
        filas = (len(opciones) + cols - 1) // cols
        return dy + filas * (lado + sep + P(22)) + P(14)

    def _selector_accesorios(self, sup, zona):
        """Para cuando existan accesorios: clic para ponerlos/quitarlos."""
        ui, P = self.ui, self.ui.px
        lado = zona.height - P(16)
        for k, nombre in enumerate(self.gl.accesorios):
            r = pygame.Rect(zona.x + P(8) + k * (lado + P(8)), zona.y + P(8), lado, lado)
            puesto = nombre in self.lider.accesorios
            pygame.draw.rect(sup, U.ACENTO_OSCURO if puesto else U.TARJETA, r, border_radius=P(6))
            sup.blit(pygame.transform.smoothscale(self.gl.accesorios[nombre], (lado, lado)), r)
            if ui.clic_en(r):
                if puesto:
                    self.lider.accesorios.remove(nombre)
                else:
                    self.lider.accesorios.append(nombre)
