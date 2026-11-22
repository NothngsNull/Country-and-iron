"""Dibujo del mapa de provincias con estética pixel art.

El mapa se compone a su resolución original (un píxel por píxel de provincias.png)
y se amplía sin suavizado, así se ve "pixelado" a cualquier zoom.
Modos: "politico" (dueños) y "regiones".
"""
from __future__ import annotations

import math

import numpy as np
import pygame

import ui as U
from banderas import tamano_para_alto
from mapa import NOMBRE_TERRENO
from mundo import Mundo, Nacion

COLOR_TERRENO = {
    "llanura": (132, 164, 92), "bosque": (76, 122, 66), "colinas": (156, 150, 100),
    "montana": (134, 126, 118), "desierto": (216, 194, 132), "pantano": (96, 118, 88),
    "tundra": (196, 204, 200),
}
MAR_PROFUNDO = np.array([30, 56, 104], dtype=np.float32)
MAR_COSTA = np.array([62, 104, 156], dtype=np.float32)
SIN_REGION = (210, 60, 200)
FONDO_MAPA = (22, 40, 76)


def _vecino_distinto(arr: np.ndarray) -> np.ndarray:
    """Píxeles cuyo vecino de la derecha o de abajo es distinto (borde de 1 píxel)."""
    m = np.zeros(arr.shape, dtype=bool)
    m[:, :-1] |= arr[:, :-1] != arr[:, 1:]
    m[:-1, :] |= arr[:-1, :] != arr[1:, :]
    return m


def _a_superficie(rgb: np.ndarray) -> pygame.Surface:
    return pygame.surfarray.make_surface(np.clip(rgb, 0, 255).astype(np.uint8).swapaxes(0, 1))


class Camara:
    def __init__(self, ancho: int, alto: int, vista: pygame.Rect):
        self.ancho, self.alto = ancho, alto
        self.vista = pygame.Rect(vista)
        self.zoom_min = max(1, min(self.vista.w // ancho, self.vista.h // alto))
        self.zoom_max = max(self.zoom_min + 1, 16)
        self.zoom = self.zoom_min
        self.x = self.y = 0.0
        self.centrar_en(ancho / 2, alto / 2)

    def a_mapa(self, sx, sy):
        return (sx - self.vista.x) / self.zoom + self.x, (sy - self.vista.y) / self.zoom + self.y

    def a_pantalla(self, mx, my):
        return self.vista.x + (mx - self.x) * self.zoom, self.vista.y + (my - self.y) * self.zoom

    def limitar(self):
        for eje, total, tam in (("x", self.ancho, self.vista.w), ("y", self.alto, self.vista.h)):
            visible = tam / self.zoom
            if visible >= total:
                setattr(self, eje, (total - visible) / 2)
            else:
                setattr(self, eje, max(0.0, min(getattr(self, eje), total - visible)))

    def centrar_en(self, mx, my):
        self.x = mx - self.vista.w / self.zoom / 2
        self.y = my - self.vista.h / self.zoom / 2
        self.limitar()

    def zoom_en(self, sx, sy, pasos: int):
        mx, my = self.a_mapa(sx, sy)
        self.zoom = max(self.zoom_min, min(self.zoom_max, self.zoom + pasos))
        self.x = mx - (sx - self.vista.x) / self.zoom
        self.y = my - (sy - self.vista.y) / self.zoom
        self.limitar()

    def mover(self, dx_px, dy_px):
        self.x -= dx_px / self.zoom
        self.y -= dy_px / self.zoom
        self.limitar()


class VistaMapa:
    def __init__(self, ui: U.UI, gestor_banderas, mundo: Mundo, vista: pygame.Rect):
        self.ui, self.gestor, self.mundo = ui, gestor_banderas, mundo
        self.mapa = mundo.mapa
        self.cam = Camara(self.mapa.ancho, self.mapa.alto, vista)
        self.modo = "politico"
        self._clave = None
        self._superficie: pygame.Surface | None = None
        self._capas: dict = {}
        self._preparar_base()

    # --- Preparación (una sola vez) -------------------------------------------
    def _preparar_base(self):
        mapa = self.mapa
        ids = mapa.ids
        h, w = ids.shape
        n = max(mapa.provincias) + 1
        self.es_tierra_lut = np.zeros(n, dtype=bool)
        terreno_lut = np.zeros((n, 3), dtype=np.float32)
        for pid, p in mapa.provincias.items():
            self.es_tierra_lut[pid] = p.es_tierra
            terreno_lut[pid] = COLOR_TERRENO.get(p.terreno, (128, 128, 128))
        tierra = self.es_tierra_lut[ids]
        self.tierra = tierra
        yy, xx = np.mgrid[0:h, 0:w]

        # Textura pixel art: ruido fijo + dibujitos según el terreno
        rng = np.random.default_rng(3)
        detalle = 1 + rng.choice([-0.035, 0, 0, 0.035], size=(h, w))
        nombres = {pid: p.terreno for pid, p in mapa.provincias.items()}
        terr_lut = np.array([nombres.get(i, "mar") for i in range(n)], dtype=object)
        terreno = terr_lut[ids]
        patrones = {
            "bosque": ((xx + 2 * yy) % 4 == 0) & (yy % 2 == 0),
            "montana": ((xx + yy) % 5 == 0) & (yy % 3 != 2),
            "colinas": ((xx - yy) % 7 == 0) & (yy % 2 == 0),
            "desierto": (xx * 3 + yy * 5) % 13 == 0,
            "pantano": (yy % 3 == 0) & (xx % 5 < 2),
            "tundra": (xx * 7 + yy * 3) % 11 == 0,
        }
        factor = {"bosque": 0.72, "montana": 1.22, "colinas": 0.85, "desierto": 0.9,
                  "pantano": 0.8, "tundra": 0.9}
        for t, mascara in patrones.items():
            detalle[(terreno == t) & mascara] *= factor[t]
        self.detalle = detalle.astype(np.float32)

        # Mar: más claro cerca de la costa, con olitas
        dist = np.where(tierra, 0, 99).astype(np.int32)
        cerca = tierra.copy()
        for k in range(1, 7):
            nuevo = cerca.copy()
            nuevo[1:] |= cerca[:-1]
            nuevo[:-1] |= cerca[1:]
            nuevo[:, 1:] |= cerca[:, :-1]
            nuevo[:, :-1] |= cerca[:, 1:]
            dist[nuevo & ~cerca] = k
            cerca = nuevo
        t = (np.clip(dist, 1, 7) - 1)[..., None] / 6
        mar = MAR_COSTA * (1 - t) + MAR_PROFUNDO * t
        olas = (((xx + (yy // 3) * 4) % 11) < 2) & (yy % 5 == 0) & (dist > 2)
        mar[olas] *= 1.12
        self.mar = mar

        # Tierra sin colonizar: color del terreno algo apagado
        base = terreno_lut[ids] * self.detalle[..., None]
        gris = base.mean(axis=2, keepdims=True)
        self.terreno_rgb = base * 0.75 + gris * 0.25

        self.borde_prov = _vecino_distinto(ids)
        self.costa = _vecino_distinto(tierra)

    # --- Composición de los modos ------------------------------------------
    def _clave_actual(self):
        if self.modo == "politico":
            return ("politico", self.mundo.version)
        return ("regiones", self.mapa.version_regiones)

    def _componer(self):
        ids, mapa, mundo = self.mapa.ids, self.mapa, self.mundo
        n = max(mapa.provincias) + 1
        tierra = self.tierra
        rgb = np.where(tierra[..., None], self.terreno_rgb, self.mar)

        if self.modo == "politico":
            dueno_lut = np.full(n, -1, dtype=np.int32)
            for pid, d in mundo.dueno.items():
                if d is not None:
                    dueno_lut[pid] = d
            colores = np.array([nac.color for nac in mundo.naciones] or [(0, 0, 0)], dtype=np.float32)
            dueno = dueno_lut[ids]
            propio = dueno >= 0
            suave = 1 + (self.detalle - 1) * 0.6
            rgb[propio] = colores[dueno[propio]] * suave[propio][:, None]
            # Rayas de colonización
            if mundo.colonias:
                coloniza_lut = np.full(n, -1, dtype=np.int32)
                for c in mundo.colonias:
                    if coloniza_lut[c.provincia] < 0:
                        coloniza_lut[c.provincia] = c.nacion
                col = coloniza_lut[ids]
                h, w = ids.shape
                yy, xx = np.mgrid[0:h, 0:w]
                rayas = (col >= 0) & (((xx + yy) // 2) % 3 == 0)
                rgb[rayas] = colores[col[rayas]]
            rgb[self.borde_prov & tierra] *= 0.82
            frontera = _vecino_distinto(dueno) & tierra
            rgb[frontera] *= 0.5
        else:
            region_lut = np.full(n, -1, dtype=np.int32)
            paleta = []
            for k, (rid, r) in enumerate(sorted(mapa.regiones.items())):
                for pid in r.provincias:
                    region_lut[pid] = k
                paleta.append(self._color_region(rid, r.tipo))
            paleta = np.array(paleta or [(0, 0, 0)], dtype=np.float32)
            reg = region_lut[ids]
            con = reg >= 0
            rgb[con] = paleta[reg[con]] * self.detalle[con][:, None]
            rgb[~con] = SIN_REGION
            rgb[self.borde_prov] *= 0.85
            rgb[_vecino_distinto(reg)] *= 0.45

        rgb[self.borde_prov & ~tierra & ~self.costa] *= 0.94
        rgb[self.costa] = rgb[self.costa] * 0.35
        self._superficie = _a_superficie(rgb)

    @staticmethod
    def _color_region(rid: int, tipo: str):
        rng = np.random.default_rng(rid * 7919)
        if tipo == "mar":
            v = int(rng.integers(0, 40))
            return (24 + v // 2, 52 + v, 100 + v)
        import colorsys
        tono = float(rng.uniform(0, 0.68))          # sin azules/violetas, para no confundir con el mar
        if tono > 0.48:
            tono += 0.32
        r, g, b = colorsys.hsv_to_rgb(tono % 1.0, float(rng.uniform(0.35, 0.6)), float(rng.uniform(0.72, 0.92)))
        return int(r * 255), int(g * 255), int(b * 255)

    # --- Capas resaltadas (provincia bajo el ratón, selección, región activa) ---
    def _capa(self, pids: tuple, color, alfa: int) -> pygame.Surface:
        clave = (pids, color, alfa)
        if clave not in self._capas:
            if len(self._capas) > 32:
                self._capas.clear()
            mascara = np.isin(self.mapa.ids, pids)
            borde = mascara & ~(
                np.pad(mascara, 1)[2:, 1:-1] & np.pad(mascara, 1)[:-2, 1:-1] &
                np.pad(mascara, 1)[1:-1, 2:] & np.pad(mascara, 1)[1:-1, :-2])
            sup = pygame.Surface((self.mapa.ancho, self.mapa.alto), pygame.SRCALPHA)
            sup.fill((*color, 0))
            a = pygame.surfarray.pixels_alpha(sup)
            a[mascara.T] = alfa
            a[borde.T] = min(255, alfa * 3)
            del a
            self._capas[clave] = sup
        return self._capas[clave]

    # --- Dibujo ---------------------------------------------------------------
    def _blit_mapa(self, sup, superficie):
        cam = self.cam
        v = cam.vista
        x0, y0 = max(0, int(math.floor(cam.x))), max(0, int(math.floor(cam.y)))
        x1 = min(self.mapa.ancho, int(math.ceil(cam.x + v.w / cam.zoom)) + 1)
        y1 = min(self.mapa.alto, int(math.ceil(cam.y + v.h / cam.zoom)) + 1)
        if x1 <= x0 or y1 <= y0:
            return
        sub = superficie.subsurface((x0, y0, x1 - x0, y1 - y0))
        esc = pygame.transform.scale(sub, ((x1 - x0) * cam.zoom, (y1 - y0) * cam.zoom))
        sx, sy = cam.a_pantalla(x0, y0)
        sup.blit(esc, (round(sx), round(sy)))

    def dibujar(self, sup, hover=None, seleccion=None, region_activa=None, previa=None, color_previa=None):
        clave = self._clave_actual()
        if clave != self._clave or self._superficie is None:
            self._componer()
            self._clave = clave
        sup.set_clip(self.cam.vista)
        sup.fill(FONDO_MAPA, self.cam.vista)
        self._blit_mapa(sup, self._superficie)
        if region_activa is not None and region_activa.provincias:
            self._blit_mapa(sup, self._capa(tuple(sorted(region_activa.provincias)), (255, 255, 255), 70))
        if previa:
            self._blit_mapa(sup, self._capa(tuple(sorted(previa)), color_previa or (255, 255, 255), 120))
        if seleccion is not None:
            self._blit_mapa(sup, self._capa((seleccion,), (255, 220, 80), 60))
        if hover is not None and hover != seleccion:
            self._blit_mapa(sup, self._capa((hover,), (255, 255, 255), 45))
        if self.modo == "politico":
            for n in self.mundo.naciones:
                self.dibujar_bandera_en(sup, n.bandera, n.capital)
        else:
            self._nombres_regiones(sup)
        sup.set_clip(None)

    def dibujar_bandera_en(self, sup, bandera, pid):
        cx, cy = self.mapa.provincias[pid].centro
        alto = max(10, min(36, int(self.cam.zoom * 3)))
        w, h = tamano_para_alto(alto)
        sx, sy = self.cam.a_pantalla(cx + 0.5, cy + 0.5)
        destino = pygame.Rect(0, 0, w, h)
        destino.center = (round(sx), round(sy))
        pygame.draw.rect(sup, (15, 15, 18), destino.inflate(2, 2))
        sup.blit(self.gestor.dibujar(bandera, w, h), destino)

    def _nombres_regiones(self, sup):
        if self.cam.zoom < 4:
            return
        for r in self.mapa.regiones.values():
            if not r.provincias:
                continue
            xs = [self.mapa.provincias[p].centro[0] for p in r.provincias]
            ys = [self.mapa.provincias[p].centro[1] for p in r.provincias]
            # La provincia más cercana al promedio, para que el nombre caiga dentro
            mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
            pid = min(r.provincias, key=lambda p: (self.mapa.provincias[p].centro[0] - mx) ** 2 +
                                                  (self.mapa.provincias[p].centro[1] - my) ** 2)
            cx, cy = self.mapa.provincias[pid].centro
            pos = self.cam.a_pantalla(cx + 0.5, cy + 0.5)
            fuente = self.ui.fuente(13, True)
            texto = r.nombre
            sombra = fuente.render(texto, True, (0, 0, 0))
            img = fuente.render(texto, True, (255, 255, 255))
            rect = img.get_rect(center=(round(pos[0]), round(pos[1])))
            sup.blit(sombra, rect.move(1, 1))
            sup.blit(img, rect)

    # --- Consultas ------------------------------------------------------------
    def provincia_bajo(self, pos) -> int | None:
        if not self.cam.vista.collidepoint(pos):
            return None
        p = self.mapa.provincia_en(*self.cam.a_mapa(*pos))
        return p.id if p else None

    def info_provincia(self, pid: int) -> list[str]:
        mapa, mundo = self.mapa, self.mundo
        p = mapa.provincias[pid]
        region = mapa.region_de(pid)
        lineas = [f"{p.nombre} · {NOMBRE_TERRENO.get(p.terreno, p.terreno)}",
                  f"Región: {region.nombre if region else 'sin región'}"]
        if not p.es_tierra:
            lineas.append("Mar (no se puede colonizar)")
            return lineas
        d = mundo.dueno[pid]
        if d is None:
            lineas.append("Sin colonizar")
            for c in mundo.colonias:
                if c.provincia == pid:
                    lineas.append(f"Colonizando: {mundo.naciones[c.nacion].nombre} ({c.dias}/{c.dias_totales} días)")
        else:
            n = mundo.naciones[d]
            lineas.append(n.nombre + (" (tú)" if n.es_jugador else ""))
            if n.lider is not None:
                lineas.append(f"Líder: {n.lider.nombre}")
            if n.capital == pid:
                lineas.append("Capital")
        return lineas

    def retrato(self, nacion: Nacion, tam: int):
        gl = self.mundo.gestor_lideres
        if gl is None or nacion.lider is None:
            return None
        return gl.dibujar(nacion.lider, nacion.bandera, tam)

    def tooltip(self, sup, lineas, imagen=None):
        ui, P = self.ui, self.ui.px
        fuente = ui.fuente(16)
        margen_img = imagen.get_width() + P(10) if imagen is not None else 0
        ancho = max(fuente.size(l)[0] for l in lineas) + P(20) + margen_img
        alto = max(len(lineas) * P(24) + P(12), (imagen.get_height() + P(12)) if imagen is not None else 0)
        x, y = ui.raton[0] + P(18), ui.raton[1] + P(18)
        W, H = sup.get_size()
        x, y = min(x, W - ancho - 4), min(y, H - alto - 4)
        caja = pygame.Rect(x, y, ancho, alto)
        pygame.draw.rect(sup, U.PANEL, caja, border_radius=P(5))
        pygame.draw.rect(sup, U.BORDE, caja, 1, border_radius=P(5))
        if imagen is not None:
            sup.blit(imagen, (x + P(6), y + P(6)))
        for i, l in enumerate(lineas):
            ui.texto(sup, l, (x + P(10) + margen_img, y + P(6) + i * P(24)), 16,
                     U.TEXTO if i else U.TEXTO_SUAVE)

    def tooltip_provincia(self, sup, pid):
        d = self.mundo.dueno.get(pid)
        imagen = self.retrato(self.mundo.naciones[d], self.ui.px(84)) if d is not None else None
        self.tooltip(sup, self.info_provincia(pid), imagen)


def miniatura(mapa) -> pygame.Surface:
    """Vista previa del mapa a su tamaño original (terreno + naciones iniciales)."""
    n = max(mapa.provincias) + 1
    lut = np.zeros((n, 3), dtype=np.float32)
    dueno = np.zeros(n, dtype=np.int32)
    tags = {t: i + 1 for i, t in enumerate(mapa.naciones_def)}
    for pid, p in mapa.provincias.items():
        if not p.es_tierra:
            lut[pid] = MAR_COSTA * 0.8
            continue
        lut[pid] = COLOR_TERRENO.get(p.terreno, (128, 128, 128))
        d = mapa.naciones_def.get(str(p.dueno_inicial)) if p.dueno_inicial else None
        if d:
            t = d.get("color", "#808080").lstrip("#")
            lut[pid] = (int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16))
            dueno[pid] = tags[str(p.dueno_inicial)]
        elif p.dueno_inicial:
            lut[pid] = (200, 200, 200)
            dueno[pid] = -1
    rgb = lut[mapa.ids]
    tierra = np.isin(mapa.ids, [pid for pid, p in mapa.provincias.items() if p.es_tierra])
    frontera = _vecino_distinto(dueno[mapa.ids]) & tierra
    rgb[frontera] *= 0.45
    rgb[_vecino_distinto(tierra)] *= 0.35
    return _a_superficie(rgb)


def barra_superior(sup, ui, alto, textos_izq, bandera=None, gestor=None, retrato=None):
    P = ui.px
    pygame.draw.rect(sup, U.PANEL, (0, 0, sup.get_width(), alto))
    pygame.draw.line(sup, U.BORDE, (0, alto - 1), (sup.get_width(), alto - 1))
    x = P(20)
    if retrato is not None:
        sup.blit(retrato, (x, (alto - retrato.get_height()) // 2))
        x += retrato.get_width() + P(10)
    if bandera is not None:
        w, h = tamano_para_alto(alto - P(24))
        img = gestor.dibujar(bandera, w, h)
        sup.blit(img, (x, P(12)))
        pygame.draw.rect(sup, U.BORDE, (x, P(12), w, h), 1)
        x += w + P(16)
    for texto, tam, color, negrita in textos_izq:
        img = ui.fuente(tam, negrita).render(texto, True, color)
        r = img.get_rect(midleft=(x, alto // 2))
        sup.blit(img, r)
        x = r.right + P(24)
