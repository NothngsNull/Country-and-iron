"""La partida: elegir dónde aparecer, el paso del tiempo, colonizar y editar regiones.

Controles:
  Rueda del ratón ......... zoom
  Arrastrar clic der./medio  mover el mapa (también WASD o flechas)
  ESPACIO ................. pausa / reanudar
  1-5, + y - .............. velocidad del tiempo
  ESC ..................... salir
"""
from __future__ import annotations

import pygame

import ui as U
from mapa_vista import VistaMapa, barra_superior
from mundo import DIAS_COLONIZAR, MAX_COLONIAS, Mundo, Nacion
from tiempo import Tiempo

VELOCIDAD_TECLADO = 900          # píxeles de pantalla por segundo al mover con teclado


class Partida:
    def __init__(self, ui: U.UI, gestor_banderas, mundo: Mundo, pantalla, nombre=None, bandera=None, lider=None):
        """Con nombre/bandera/líder: el jugador crea su nación y elige dónde aparecer.
        Sin ellos (mapas "establecido"): el jugador elige una nación que ya existe."""
        self.ui, self.gestor, self.mundo = ui, gestor_banderas, mundo
        self.nombre, self.bandera, self.lider = nombre, bandera, lider
        self.color = tuple(bandera.capas[0].color) if bandera and bandera.capas else (200, 200, 200)
        W, H = pantalla.get_size()
        self.alto_barra = ui.px(70)
        self.vista = VistaMapa(ui, gestor_banderas, mundo, pygame.Rect(0, self.alto_barra, W, H - self.alto_barra))
        self.tiempo = Tiempo()
        self.estado = "eligiendo" if nombre is not None else "eligiendo_nacion"
        self.nacion_elegida: int | None = None
        self.scroll_lista = 0
        self.jugador: int | None = None
        self.seleccion: int | None = None
        self.editando = False
        self.region_activa = None
        self.sin_guardar = False
        self.avisos: list[list] = []          # [texto, segundos restantes]
        self._arrastre = None                 # (botón, distancia recorrida)
        self._zonas_previas: list[pygame.Rect] = []

    def avisar(self, texto: str, segundos: float = 4.0):
        self.avisos.append([texto, segundos])
        self.avisos = self.avisos[-4:]

    # ------------------------------------------------------------------
    def ejecutar(self, pantalla, reloj):
        while True:
            dt = reloj.tick(60) / 1000
            eventos = pygame.event.get()
            U.eventos_comunes(eventos)
            self.ui.nuevo_fotograma(eventos)
            sobre_ui = any(r.collidepoint(self.ui.raton) for r in self._zonas_previas)
            self._entrada(eventos, dt, sobre_ui)

            if self.estado == "jugando":
                for _ in range(self.tiempo.actualizar(dt)):
                    self.mundo.nuevo_dia()
                for aviso in self.mundo.avisos:
                    self.avisar(aviso)
                self.mundo.avisos.clear()
            for a in self.avisos:
                a[1] -= dt
            self.avisos = [a for a in self.avisos if a[1] > 0]

            self.dibujar(pantalla, sobre_ui)
            self._zonas_previas = list(self.ui.zonas)
            pygame.display.flip()

    # --- Entrada ----------------------------------------------------------
    def _entrada(self, eventos, dt, sobre_ui):
        cam = self.vista.cam
        for e in eventos:
            if self.estado == "jugando":
                self.tiempo.manejar_evento(e)
            if e.type == pygame.MOUSEWHEEL and not sobre_ui and cam.vista.collidepoint(self.ui.raton):
                cam.zoom_en(*self.ui.raton, e.y)
            elif e.type == pygame.MOUSEBUTTONDOWN and e.button in (2, 3):
                self._arrastre = [e.button, 0]
            elif e.type == pygame.MOUSEMOTION and self._arrastre:
                cam.mover(*e.rel)
                self._arrastre[1] += abs(e.rel[0]) + abs(e.rel[1])
            elif e.type == pygame.MOUSEBUTTONUP and e.button in (2, 3) and self._arrastre:
                if e.button == 3 and self._arrastre[1] < 6 and not sobre_ui:
                    self._clic_derecho()
                self._arrastre = None
        teclas = pygame.key.get_pressed()
        dx = (teclas[pygame.K_a] or teclas[pygame.K_LEFT]) - (teclas[pygame.K_d] or teclas[pygame.K_RIGHT])
        dy = (teclas[pygame.K_w] or teclas[pygame.K_UP]) - (teclas[pygame.K_s] or teclas[pygame.K_DOWN])
        if dx or dy:
            cam.mover(dx * VELOCIDAD_TECLADO * dt, dy * VELOCIDAD_TECLADO * dt)

    def _clic_derecho(self):
        pid = self.vista.provincia_bajo(self.ui.raton)
        if self.editando:
            if pid is not None:
                self.region_activa = self.mundo.mapa.region_de(pid)
        else:
            self.seleccion = None

    def _jugar_con(self, idx: int):
        n = self.mundo.naciones[idx]
        n.es_jugador = True
        self.jugador = idx
        self.color = n.color
        self.estado = "jugando"
        self.avisar(f"Ahora gobiernas {n.nombre}. Pulsa ESPACIO para que avance el tiempo.", 7)

    def _clic_mapa(self, pid):
        mundo = self.mundo
        if self.estado == "eligiendo_nacion":
            self.nacion_elegida = mundo.dueno.get(pid) if pid is not None else None
            return
        if self.estado == "eligiendo":
            if pid is not None and mundo.puede_aparecer(pid):
                nacion = Nacion(self.nombre, self.color, self.bandera, pid, es_jugador=True, lider=self.lider)
                self.jugador = mundo.fundar(nacion)
                self.estado = "jugando"
                self.avisar(f"¡{self.nombre} ha sido fundada! Pulsa ESPACIO para que avance el tiempo.", 7)
            return
        if self.editando:
            if pid is not None and self.region_activa is None:
                self.region_activa = mundo.mapa.region_de(pid)
            return
        self.seleccion = pid

    def _pintar_region(self, pid):
        """Con una región activa, arrastrar con clic izquierdo mueve provincias a ella."""
        mapa = self.mundo.mapa
        if self.region_activa is None or pid is None:
            return
        if mapa.mover_a_region(pid, self.region_activa.id):
            self.sin_guardar = True
        elif self.ui.clic and mapa.provincias[pid].tipo != self.region_activa.tipo:
            self.avisar("Las provincias de mar solo van en regiones de mar (y las de tierra en las de tierra)")

    # --- Dibujo -----------------------------------------------------------
    def dibujar(self, sup, sobre_ui):
        ui, P, mundo = self.ui, self.ui.px, self.mundo
        hover = None if sobre_ui else self.vista.provincia_bajo(ui.raton)

        previa, color_previa = None, None
        if self.estado == "eligiendo" and hover is not None and mundo.puede_aparecer(hover):
            previa, color_previa = mundo.zona_inicial(hover), self.color
        elif self.estado == "eligiendo_nacion" and self.nacion_elegida is not None:
            previa, color_previa = mundo.provincias_de(self.nacion_elegida), (255, 255, 255)
        self.vista.dibujar(sup, hover=hover, seleccion=None if self.editando else self.seleccion,
                           region_activa=self.region_activa if self.editando else None,
                           previa=previa, color_previa=color_previa)

        self._barra_superior(sup)
        self._botones_modo(sup)
        if self.editando:
            self._panel_editor(sup)
        elif self.seleccion is not None and self.estado == "jugando":
            self._panel_provincia(sup)
        if self.estado == "eligiendo_nacion":
            self._lista_naciones(sup)
            if self.nacion_elegida is not None:
                self._panel_nacion_elegida(sup)
        if self.estado == "jugando" and self._hay_tierra_libre():
            self._panel_colonias(sup)
        self._dibujar_avisos(sup)

        # Clics en el mapa (después de la interfaz, para saber si el clic fue en un botón)
        if not ui.sobre_interfaz():
            if ui.clic:
                self._clic_mapa(hover)
            if self.editando and pygame.mouse.get_pressed()[0]:
                self._pintar_region(hover)
            if hover is not None and not self._arrastre:
                if self.estado == "eligiendo" and not mundo.puede_aparecer(hover):
                    p = mundo.mapa.provincias[hover]
                    motivo = ("No puedes fundar en el mar" if not p.es_tierra else
                              "Ya tiene dueño" if mundo.dueno[hover] is not None else
                              "Demasiado cerca de otra nación")
                    self.vista.tooltip(sup, self.vista.info_provincia(hover) + [motivo])
                else:
                    self.vista.tooltip_provincia(sup, hover)

    def _hay_tierra_libre(self) -> bool:
        return any(d is None and self.mundo.mapa.provincias[p].es_tierra for p, d in self.mundo.dueno.items())

    # --- Elegir una nación existente --------------------------------------
    def _lista_naciones(self, sup):
        ui, P, mundo = self.ui, self.ui.px, self.mundo
        W, H = sup.get_size()
        ancho = P(380)
        r = ui.panel(sup, (W - P(20) - ancho, self.alto_barra + P(14), ancho, H - self.alto_barra - P(110)))
        ui.texto(sup, "Naciones", (r.x + P(16), r.y + P(12)), 20, U.TEXTO, True)
        orden = sorted(range(len(mundo.naciones)), key=lambda i: -len(mundo.provincias_de(i)))
        fila_h = P(40)
        zona = pygame.Rect(r.x + P(8), r.y + P(48), r.w - P(16), r.h - P(56))
        visibles = zona.h // fila_h
        if ui.sobre(zona) and ui.rueda:
            self.scroll_lista -= ui.rueda
        self.scroll_lista = max(0, min(self.scroll_lista, len(orden) - visibles))
        for k, idx in enumerate(orden[self.scroll_lista:self.scroll_lista + visibles]):
            n = mundo.naciones[idx]
            fila = pygame.Rect(zona.x, zona.y + k * fila_h, zona.w, fila_h - P(4))
            sel = idx == self.nacion_elegida
            if sel or ui.sobre(fila):
                pygame.draw.rect(sup, U.ACENTO_OSCURO if sel else U.TARJETA_SOBRE, fila, border_radius=P(6))
            sup.blit(self.gestor.dibujar(n.bandera, P(39), P(26)), (fila.x + P(8), fila.y + P(5)))
            ui.texto(sup, n.nombre, (fila.x + P(58), fila.y + P(7)), 16, U.TEXTO, sel)
            cantidad = ui.fuente(14).render(str(len(mundo.provincias_de(idx))), True, U.TEXTO_APAGADO)
            sup.blit(cantidad, cantidad.get_rect(midright=(fila.right - P(10), fila.centery)))
            if ui.clic_en(fila):
                self.nacion_elegida = idx
                self.vista.cam.centrar_en(*mundo.mapa.provincias[n.capital].centro)
        if len(orden) > visibles:
            ui.texto(sup, "Rueda para ver más", (r.x + P(16), r.bottom - P(4) - P(18)), 13, U.TEXTO_APAGADO)

    def _panel_nacion_elegida(self, sup):
        ui, P, mundo = self.ui, self.ui.px, self.mundo
        idx = self.nacion_elegida
        n = mundo.naciones[idx]
        H = sup.get_height()
        ancho, alto = P(560), P(300)
        r = ui.panel(sup, (P(20), H - P(20) - alto, ancho, alto))
        tam = P(170)
        retrato = self.vista.retrato(n, tam)
        pygame.draw.rect(sup, (236, 234, 228), (r.x + P(16), r.y + P(16), tam + P(12), tam + P(12)),
                         border_radius=P(8))
        if retrato is not None:
            sup.blit(retrato, (r.x + P(22), r.y + P(22)))
        x = r.x + tam + P(48)
        y = r.y + P(18)
        w, h = P(78), P(52)
        sup.blit(self.gestor.dibujar(n.bandera, w, h), (x, y))
        pygame.draw.rect(sup, U.BORDE, (x, y, w, h), 1)
        ui.texto(sup, n.nombre, (x, y + h + P(10)), 22, U.TEXTO, True)
        provs = mundo.provincias_de(idx)
        regiones = {mundo.mapa.provincias[p].region for p in provs}
        lineas = [f"Líder: {n.lider.nombre}" if n.lider else "",
                  f"Capital: {mundo.mapa.provincias[n.capital].nombre}",
                  f"{len(provs)} provincias · {len(regiones)} regiones"]
        for i, linea in enumerate(l for l in lineas if l):
            ui.texto(sup, linea, (x, y + h + P(44) + i * P(24)), 16, U.TEXTO_SUAVE)
        if ui.boton(sup, (r.x + P(16), r.bottom - P(62), ancho - P(32), P(46)), f"Jugar con {n.nombre}",
                    primario=True, tam=19):
            self._jugar_con(idx)

    def _barra_superior(self, sup):
        ui, P = self.ui, self.ui.px
        if self.estado == "eligiendo_nacion":
            barra_superior(sup, ui, self.alto_barra,
                           [(self.mundo.mapa.info.nombre, 24, U.TEXTO, True),
                            ("Elige tu nación: haz clic en un país del mapa o de la lista", 20, U.TEXTO_SUAVE,
                             False)])
            ui.ocupar((0, 0, sup.get_width(), self.alto_barra))
            return
        if self.estado == "eligiendo":
            retrato = self.mundo.gestor_lideres.dibujar(self.lider, self.bandera, self.alto_barra - P(8)) \
                if self.mundo.gestor_lideres and self.lider else None
            textos = [(self.nombre, 24, U.TEXTO, True),
                      ("Elige tu zona de inicio: haz clic en una provincia libre", 20, U.TEXTO_SUAVE, False)]
            barra_superior(sup, ui, self.alto_barra, textos, self.bandera, self.gestor, retrato)
            ui.ocupar((0, 0, sup.get_width(), self.alto_barra))
            return
        nacion = self.mundo.naciones[self.jugador]
        textos = [(nacion.nombre, 24, U.TEXTO, True)]
        if nacion.lider is not None:
            textos.append((f"Líder: {nacion.lider.nombre}", 17, U.TEXTO_SUAVE, False))
        textos.append((f"Provincias: {len(self.mundo.provincias_de(self.jugador))}", 17, U.TEXTO_SUAVE, False))
        barra_superior(sup, ui, self.alto_barra, textos, nacion.bandera, self.gestor,
                       self.vista.retrato(nacion, self.alto_barra - P(8)))
        ui.ocupar((0, 0, sup.get_width(), self.alto_barra))
        self._controles_tiempo(sup)

    def _controles_tiempo(self, sup):
        ui, P, t = self.ui, self.ui.px, self.tiempo
        W = sup.get_width()
        alto = self.alto_barra
        # Velocidades: 5 barritas, como en HOI4
        x = W - P(30)
        for v in range(5, 0, -1):
            r = pygame.Rect(0, 0, P(14), P(10) + v * P(4))
            r.bottomright = (x, alto // 2 + P(16))
            activa = v <= t.velocidad
            color = (U.ACENTO if not t.pausado else U.TEXTO_APAGADO) if activa else U.TARJETA
            pygame.draw.rect(sup, color, r, border_radius=P(2))
            if ui.clic_en(r.inflate(P(4), P(30))):
                t.velocidad = v
                t.pausado = False
            x -= P(18)
        boton = pygame.Rect(0, 0, P(44), P(40))
        boton.midright = (x - P(8), alto // 2)
        if ui.boton(sup, boton, "", activo=not t.pausado):
            t.pausado = not t.pausado
        cx, cy = boton.center
        if t.pausado:     # icono "reproducir"
            pygame.draw.polygon(sup, U.TEXTO, [(cx - P(6), cy - P(9)), (cx - P(6), cy + P(9)), (cx + P(9), cy)])
        else:             # icono "pausa"
            pygame.draw.rect(sup, U.TEXTO, (cx - P(8), cy - P(9), P(5), P(18)))
            pygame.draw.rect(sup, U.TEXTO, (cx + P(3), cy - P(9), P(5), P(18)))
        texto = t.texto() + ("  (EN PAUSA)" if t.pausado else "")
        img = ui.fuente(20, True).render(texto, True, U.TEXTO if not t.pausado else (230, 190, 90))
        sup.blit(img, img.get_rect(midright=(boton.left - P(16), alto // 2)))

    def _botones_modo(self, sup):
        ui, P = self.ui, self.ui.px
        W, H = sup.get_size()
        w, h = P(170), P(44)
        x, y = W - P(20) - w, H - P(20) - h
        botones = [("Mapa político", "politico"), ("Mapa de regiones", "regiones")]
        for texto, modo in reversed(botones):
            if ui.boton(sup, ui.ocupar((x, y, w, h)), texto, activo=self.vista.modo == modo):
                self.vista.modo = modo
                if modo == "politico" and self.editando:
                    self.editando = False
            x -= w + P(10)
        if self.vista.modo == "regiones" and self.estado == "jugando":
            r = ui.ocupar((W - P(20) - w, y - h - P(10), w, h))
            if ui.boton(sup, r, "Editar regiones", activo=self.editando):
                self.editando = not self.editando
                self.region_activa = None

    def _panel_provincia(self, sup):
        ui, P, mundo = self.ui, self.ui.px, self.mundo
        mapa = mundo.mapa
        pid = self.seleccion
        p = mapa.provincias[pid]
        H = sup.get_height()
        ancho, alto = P(440), P(250)
        r = ui.panel(sup, (P(20), H - P(20) - alto, ancho, alto))
        x, y = r.x + P(18), r.y + P(14)
        if ui.boton(sup, (r.right - P(44), r.y + P(10), P(32), P(32)), "×"):
            self.seleccion = None
            return
        ui.texto(sup, p.nombre, (x, y), 26, U.TEXTO, True)
        lineas = self.vista.info_provincia(pid)
        lineas[0] = lineas[0].split(" · ", 1)[-1]          # el nombre ya está en el título
        for i, linea in enumerate(lineas):
            ui.texto(sup, linea, (x, y + P(42) + i * P(24)), 17, U.TEXTO_SUAVE)
        by = r.bottom - P(64)
        if not p.es_tierra or mundo.dueno[pid] is not None:
            return
        mia = mundo.colonia_en(self.jugador, pid)
        if mia:
            ui.texto(sup, f"Colonizando: {mia.dias}/{mia.dias_totales} días", (x, by - P(30)), 16, U.TEXTO)
            ui.barra(sup, (x, by - P(6), ancho - P(36), P(8)), mia.progreso, self.color)
            if ui.boton(sup, (x, by + P(10), P(200), P(42)), "Cancelar"):
                mundo.cancelar(self.jugador, pid)
            return
        ok, motivo = mundo.puede_colonizar(self.jugador, pid)
        dias = DIAS_COLONIZAR.get(p.terreno, 30)
        if ui.boton(sup, (x, by + P(10), P(260), P(42)), f"Colonizar ({dias} días)", habilitado=ok, primario=ok):
            mundo.colonizar(self.jugador, pid)
        if not ok:
            ui.texto(sup, motivo, (x, by - P(18)), 15, U.TEXTO_APAGADO)

    def _panel_colonias(self, sup):
        ui, P, mundo = self.ui, self.ui.px, self.mundo
        colonias = mundo.colonias_de(self.jugador)
        W = sup.get_width()
        ancho = P(320)
        alto = P(48) + max(1, len(colonias)) * P(46)
        r = ui.panel(sup, (W - P(20) - ancho, self.alto_barra + P(14), ancho, alto))
        x, y = r.x + P(14), r.y + P(10)
        ui.texto(sup, f"Colonización ({len(colonias)}/{MAX_COLONIAS})", (x, y), 17, U.TEXTO, True)
        y += P(34)
        if not colonias:
            ui.texto(sup, "Elige una provincia libre junto a tu territorio", (x, y), 14, U.TEXTO_APAGADO)
        for c in colonias:
            nombre = mundo.mapa.provincias[c.provincia].nombre
            fila = pygame.Rect(x - P(4), y - P(4), ancho - P(20), P(42))
            if ui.clic_en(fila):
                self.seleccion = c.provincia
            ui.texto(sup, f"{nombre}  ·  {c.dias}/{c.dias_totales} días", (x, y), 15, U.TEXTO_SUAVE)
            ui.barra(sup, (x, y + P(24), ancho - P(28), P(8)), c.progreso, self.color)
            y += P(46)

    def _panel_editor(self, sup):
        ui, P, mapa = self.ui, self.ui.px, self.mundo.mapa
        H = sup.get_height()
        ancho, alto = P(470), P(440)
        r = ui.panel(sup, (P(20), H - P(20) - alto, ancho, alto))
        x, y = r.x + P(18), r.y + P(14)
        ui.texto(sup, "Editor de regiones", (x, y), 24, U.TEXTO, True)
        y += P(40)
        for linea in ("Clic: elegir la región de esa provincia",
                      "Con una región elegida: clic o arrastrar = añadirle provincias",
                      "Clic derecho: cambiar a la región de otra provincia",
                      "Los nombres se cambian en datos/mapa/regiones.json"):
            ui.texto(sup, "· " + linea, (x, y), 15, U.TEXTO_SUAVE)
            y += P(22)
        y += P(10)
        reg = self.region_activa
        if reg is not None and reg.id in mapa.regiones:
            ui.texto(sup, f"Región activa: {reg.nombre}", (x, y), 18, U.TEXTO, True)
            ui.texto(sup, f"{'Tierra' if reg.tipo == 'tierra' else 'Mar'} · {len(reg.provincias)} provincias",
                     (x, y + P(26)), 15, U.TEXTO_SUAVE)
        else:
            self.region_activa = None
            ui.texto(sup, "Ninguna región elegida", (x, y), 18, U.TEXTO_APAGADO)
        y += P(60)
        bw = (ancho - P(46)) // 2
        if ui.boton(sup, (x, y, bw, P(40)), "Nueva región (tierra)", tam=15):
            self.region_activa = mapa.nueva_region("tierra")
        if ui.boton(sup, (x + bw + P(10), y, bw, P(40)), "Nueva región (mar)", tam=15):
            self.region_activa = mapa.nueva_region("mar")
        y += P(50)
        if ui.boton(sup, (x, y, bw, P(40)), "Soltar región", tam=15, habilitado=self.region_activa is not None):
            self.region_activa = None
        if ui.boton(sup, (x + bw + P(10), y, bw, P(40)), "Descartar cambios", tam=15, habilitado=self.sin_guardar):
            mapa.cargar_regiones()
            self.region_activa = None
            self.sin_guardar = False
            self.avisar("Regiones recargadas desde regiones.json")
        y += P(50)
        if ui.boton(sup, (x, y, ancho - P(36), P(44)), "Guardar en regiones.json", primario=self.sin_guardar,
                    habilitado=self.sin_guardar):
            mapa.guardar_regiones()
            self.sin_guardar = False
            if self.region_activa is not None and self.region_activa.id not in mapa.regiones:
                self.region_activa = None
            self.avisar("Regiones guardadas en datos/mapa/regiones.json")
        y += P(52)
        sin_region = sum(1 for p in mapa.provincias.values() if p.region is None)
        estado = "Cambios sin guardar" if self.sin_guardar else "Todo guardado"
        if sin_region:
            estado += f" · {sin_region} provincias sin región (en magenta)"
        ui.texto(sup, estado, (x, y), 15, (230, 190, 90) if self.sin_guardar or sin_region else U.TEXTO_APAGADO)

    def _dibujar_avisos(self, sup):
        ui, P = self.ui, self.ui.px
        W, H = sup.get_size()
        y = H - P(90)
        for texto, resto in reversed(self.avisos):
            img = ui.fuente(18, True).render(texto, True, U.TEXTO)
            caja = img.get_rect(center=(W // 2, y)).inflate(P(30), P(16))
            fondo = pygame.Surface(caja.size, pygame.SRCALPHA)
            alfa = int(230 * min(1.0, resto))
            pygame.draw.rect(fondo, (*U.PANEL, alfa), fondo.get_rect(), border_radius=P(8))
            sup.blit(fondo, caja)
            img.set_alpha(int(255 * min(1.0, resto)))
            sup.blit(img, img.get_rect(center=caja.center))
            y -= caja.h + P(8)
