"""Pantalla para elegir en qué mapa jugar (las carpetas de datos/mapas/)."""
from __future__ import annotations

import pygame

import ui as U
from mapa import Mapa, listar_mapas
from mapa_vista import miniatura

TIPOS = {"colonizacion": "Colonización · creas tu propia nación",
         "establecido": "Naciones establecidas · eliges una existente"}


class SeleccionMapa:
    def __init__(self, ui: U.UI):
        self.ui = ui
        self.mapas = []
        for info in listar_mapas():
            try:
                m = Mapa(info.carpeta)
            except (OSError, ValueError, KeyError, pygame.error) as e:
                print(f"[mapas] no se pudo cargar {info.carpeta.name}: {e}")
                continue
            tierra = sum(1 for p in m.provincias.values() if p.es_tierra)
            naciones = len({p.dueno_inicial for p in m.provincias.values() if p.dueno_inicial})
            self.mapas.append((info, miniatura(m), len(m.provincias), tierra, naciones))

    def ejecutar(self, pantalla, reloj):
        """Devuelve la carpeta del mapa elegido."""
        if len(self.mapas) == 1:
            return self.mapas[0][0].carpeta
        while True:
            reloj.tick(60)
            eventos = pygame.event.get()
            U.eventos_comunes(eventos)
            self.ui.nuevo_fotograma(eventos)
            elegido = self.dibujar(pantalla)
            if elegido is not None:
                return elegido
            pygame.display.flip()

    def dibujar(self, sup):
        ui, P = self.ui, self.ui.px
        W, H = sup.get_size()
        sup.fill(U.FONDO)
        ui.texto(sup, "Elige un mapa", (P(80), P(40)), 44, U.TEXTO, True)
        ui.texto(sup, "Haz clic en el mapa en el que quieres jugar. ESC para salir.", (P(82), P(102)), 18,
                 U.TEXTO_SUAVE)

        ancho = P(600)
        sep = P(40)
        cols = max(1, min(len(self.mapas), (W - P(160) + sep) // (ancho + sep)))
        total = cols * ancho + (cols - 1) * sep
        x0 = (W - total) // 2
        alto_img = ancho * 270 // 480 - P(24)
        alto = alto_img + P(190)
        for k, (info, img, n_prov, n_tierra, n_nac) in enumerate(self.mapas):
            x = x0 + (k % cols) * (ancho + sep)
            y = P(170) + (k // cols) * (alto + sep)
            tarjeta = pygame.Rect(x, y, ancho, alto)
            encima = ui.sobre(tarjeta)
            pygame.draw.rect(sup, U.TARJETA_SOBRE if encima else U.TARJETA, tarjeta, border_radius=P(10))
            pygame.draw.rect(sup, U.ACENTO if encima else U.BORDE, tarjeta, 2, border_radius=P(10))
            w_img = ancho - P(24)
            sup.blit(pygame.transform.scale(img, (w_img, alto_img)), (x + P(12), y + P(12)))
            ty = y + alto_img + P(24)
            ui.texto(sup, info.nombre, (x + P(18), ty), 28, U.TEXTO, True)
            ui.texto(sup, TIPOS.get(info.tipo, info.tipo), (x + P(18), ty + P(44)), 17, (230, 190, 90))
            ui.texto(sup, info.descripcion, (x + P(18), ty + P(72)), 16, U.TEXTO_SUAVE)
            datos = f"{n_prov} provincias ({n_tierra} de tierra)"
            if n_nac:
                datos += f" · {n_nac} naciones"
            ui.texto(sup, datos, (x + P(18), ty + P(100)), 15, U.TEXTO_APAGADO)
            if ui.clic_en(tarjeta):
                return info.carpeta
        return None
