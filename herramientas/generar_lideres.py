"""Genera las imágenes (mal dibujadas a propósito) de los líderes countryball.

Uso:  python herramientas/generar_lideres.py

Crea en datos/lideres/:
  cuerpos/<nombre>.png  -> 240x240: contorno NEGRO, interior BLANCO (ahí va la bandera),
                           fuera transparente.
  ojos/<nombre>.png     -> 240x240 transparente: solo los ojos, en la posición de la cara.
  accesorios/           -> vacío por ahora.

Puedes dibujar tus propias imágenes en Paint con el mismo formato y dejarlas en
esas carpetas: el juego las carga solas.
"""
from __future__ import annotations

import math
import os
import random
from pathlib import Path

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
import numpy as np
import pygame

RAIZ = Path(__file__).resolve().parent.parent
DESTINO = RAIZ / "datos" / "lideres"
FUENTE_CLASICA = Path(__file__).resolve().parent / "fuentes" / "cuerpo_clasico.png"
TAM = 240
NEGRO = (0, 0, 0, 255)
BLANCO = (255, 255, 255, 255)
CENTRO = (120, 124)


# ---------------------------------------------------------------------------
# Trazo "a mano": línea gruesa con temblor y grosor irregular
# ---------------------------------------------------------------------------
def trazo(sup, puntos, grosor, rng, cerrado=False):
    pts = list(puntos) + ([puntos[0]] if cerrado else [])
    fase = rng.uniform(0, 2 * math.pi)
    # El grosor cambia de a poco (como la presión de la mano), no tramo a tramo
    for i, ((x1, y1), (x2, y2)) in enumerate(zip(pts, pts[1:])):
        r = max(1.0, grosor / 2 + 0.8 * math.sin(i * 0.12 + fase))
        pasos = max(1, int(math.hypot(x2 - x1, y2 - y1)))
        for k in range(pasos + 1):
            t = k / pasos
            pygame.draw.circle(sup, NEGRO, (x1 + (x2 - x1) * t, y1 + (y2 - y1) * t), r)


def contorno_tembloroso(rng, forma, n=80, temblor=0.035):
    """Puntos de una figura cerrada; forma(t) -> (x, y) relativo al centro."""
    fases = [rng.uniform(0, 2 * math.pi) for _ in range(4)]
    amps = [temblor * rng.uniform(0.4, 1.0) for _ in range(4)]
    pts = []
    for i in range(n):
        t = 2 * math.pi * i / n
        x, y = forma(t)
        k = 1 + sum(a * math.sin((j + 2) * t + f) for j, (a, f) in enumerate(zip(amps, fases)))
        pts.append((CENTRO[0] + x * k + rng.uniform(-0.5, 0.5), CENTRO[1] + y * k + rng.uniform(-0.5, 0.5)))
    return pts


def superelipse(rx, ry, n):
    def f(t):
        c, s = math.cos(t), math.sin(t)
        return (rx * math.copysign(abs(c) ** (2 / n), c), ry * math.copysign(abs(s) ** (2 / n), s))
    return f


# ---------------------------------------------------------------------------
# Cuerpos
# ---------------------------------------------------------------------------
FORMAS_CUERPO = {
    "redonda": superelipse(96, 94, 2),
    "ovalada": superelipse(108, 84, 2),
    "alta": superelipse(80, 106, 2),
    "cuadrada": superelipse(94, 92, 3.6),
    "aplastada": superelipse(108, 76, 2.3),
    "pera": lambda t: ((88 + 12 * math.sin(t)) * math.cos(t), 98 * math.sin(t)),
    "huevo": lambda t: ((90 - 8 * math.sin(t)) * math.cos(t), 102 * math.sin(t)),
}


def cuerpo(nombre, rng):
    sup = pygame.Surface((TAM, TAM), pygame.SRCALPHA)
    pts = contorno_tembloroso(rng, FORMAS_CUERPO[nombre], n=90, temblor=0.028)
    pygame.draw.polygon(sup, BLANCO, pts)
    trazo(sup, pts, 10, rng, cerrado=True)
    return sup


def cuerpo_desde_contorno(ruta: Path) -> pygame.Surface:
    """Convierte un dibujo de solo contorno (como el del usuario) al formato de cuerpo."""
    img = pygame.image.load(str(ruta))
    rgba = pygame.Surface(img.get_size(), pygame.SRCALPHA)
    rgba.fill((0, 0, 0, 0))
    rgba.blit(img, (0, 0))
    a = pygame.surfarray.array_alpha(rgba)
    rgb = pygame.surfarray.array3d(rgba).sum(axis=2)
    linea = (a > 128) & (rgb < 200)
    # Relleno por inundación desde los bordes para saber qué es "fuera"
    w, h = linea.shape
    fuera = np.zeros_like(linea)
    pila = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
    while pila:
        x, y = pila.pop()
        if 0 <= x < w and 0 <= y < h and not fuera[x, y] and not linea[x, y]:
            fuera[x, y] = True
            pila.extend(((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)))
    sup = pygame.Surface((w, h), pygame.SRCALPHA)
    sup.fill((255, 255, 255, 255))
    pix = pygame.surfarray.pixels3d(sup)
    pix[linea] = 0
    del pix
    alfa = pygame.surfarray.pixels_alpha(sup)
    alfa[fuera] = 0
    del alfa
    return pygame.transform.smoothscale(sup, (TAM, TAM)) if (w, h) != (TAM, TAM) else sup


# ---------------------------------------------------------------------------
# Ojos
# ---------------------------------------------------------------------------
# Reglas de countryball para los ojos:
#   * Óvalos BLANCOS con contorno negro (más fino que el del cuerpo). NUNCA pupilas.
#   * Un poco más altos que anchos, juntos y en la mitad superior de la bola.
#   * La expresión se hace "cortando" el ojo con un párpado recto
#     (enojado: baja hacia el centro; triste: baja hacia afuera; aburrido: plano).
#   * Para mirar a un lado se desplazan los DOS ojos hacia ese lado.
OJO_IZQ, OJO_DER = (86, 106), (154, 104)
GROSOR_OJO = 5


def _recortar(poligono, a, b, c):
    """Sutherland-Hodgman: deja la parte del polígono donde a*x + b*y + c <= 0."""
    fuera = []
    n = len(poligono)
    for i in range(n):
        p, q = poligono[i], poligono[(i + 1) % n]
        vp, vq = a * p[0] + b * p[1] + c, a * q[0] + b * q[1] + c
        if vp <= 0:
            fuera.append(p)
        if (vp <= 0) != (vq <= 0):
            t = vp / (vp - vq)
            fuera.append((p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t))
    return fuera


def _cortar_por_encima(poligono, p1, p2):
    """Quita lo que queda por encima de la recta p1-p2 (el párpado)."""
    (x1, y1), (x2, y2) = p1, p2
    # recta: (y2-y1)x - (x2-x1)y + c = 0 ; se conserva el lado de abajo
    a, b = (y1 - y2), (x2 - x1)
    c = -(a * x1 + b * y1)
    if a * x1 + b * (y1 + 100) + c > 0:      # orientar para que "abajo" sea <= 0
        a, b, c = -a, -b, -c
    return _recortar(poligono, a, b, c)


def ojo(rng, centro, rx, ry):
    pts = contorno_tembloroso(rng, superelipse(rx, ry, 2), n=48, temblor=0.025)
    dx, dy = centro[0] - CENTRO[0], centro[1] - CENTRO[1]
    return [(x + dx, y + dy) for x, y in pts]


def pintar_ojo(sup, pts, rng):
    if len(pts) >= 3:
        pygame.draw.polygon(sup, BLANCO, pts)
        trazo(sup, pts, GROSOR_OJO, rng, cerrado=True)


def ojos(estilo, rng):
    sup = pygame.Surface((TAM, TAM), pygame.SRCALPHA)
    grande = estilo == "sorprendidos"
    desplazamiento = -16 if estilo == "mirando_al_lado" else 0
    for i, base in enumerate((OJO_IZQ, OJO_DER)):
        lado = -1 if i == 0 else 1                       # -1 ojo izquierdo, 1 ojo derecho
        x, y = base[0] + desplazamiento + rng.randint(-1, 1), base[1] + rng.randint(-1, 1)
        rx = (28 if grande else 21) + rng.randint(0, 2)
        ry = (34 if grande else 27) + rng.randint(0, 2)

        if estilo == "felices":                          # ^ ^
            pts = [(x - rx + 2 * rx * k / 12, y + 8 - math.sin(math.pi * k / 12) * ry * 0.75)
                   for k in range(13)]
            trazo(sup, pts, 7, rng)
            continue
        if estilo == "dormidos":                         # ‿ ‿ (cerrados)
            pts = [(x - rx + 2 * rx * k / 12, y + 2 + math.sin(math.pi * k / 12) * 7) for k in range(13)]
            trazo(sup, pts, 7, rng)
            continue

        pts = ojo(rng, (x, y), rx, ry)
        if estilo in ("enojados",):
            # el párpado baja hacia el centro de la cara
            pts = _cortar_por_encima(pts, (x + lado * rx * 1.5, y - ry * 0.8), (x - lado * rx * 1.5, y + ry * 0.05))
        elif estilo in ("tristes", "llorando"):
            # el párpado baja hacia afuera
            pts = _cortar_por_encima(pts, (x - lado * rx * 1.5, y - ry * 0.7), (x + lado * rx * 1.5, y - ry * 0.05))
        elif estilo == "aburridos":
            pts = _cortar_por_encima(pts, (x - rx * 2, y - 2), (x + rx * 2, y - 3))
        elif estilo == "sospechosos":
            pts = _cortar_por_encima(pts, (x - rx * 2, y - 7), (x + rx * 2, y - 5))
            pts = _recortar(pts, 0, -1, y + 9)           # quita lo de abajo: queda una rendija
        pintar_ojo(sup, pts, rng)

        if estilo == "llorando":                         # chorrito de lágrimas hacia abajo
            bx = x + lado * 4
            gota = [(bx - 6, y + ry - 4), (bx + 6, y + ry - 4), (bx + 7 + rng.randint(-1, 1), y + ry + 55),
                    (bx - 7, y + ry + 58)]
            pygame.draw.polygon(sup, (120, 190, 255, 255), gota)
            trazo(sup, gota, 3, rng, cerrado=True)
    return sup


ESTILOS_OJOS = ["normales", "enojados", "tristes", "felices", "aburridos", "sospechosos",
                "sorprendidos", "mirando_al_lado", "dormidos", "llorando"]
OJOS_VIEJOS = ["pupilas", "bizcos", "cansados"]   # estilos anteriores que no siguen las reglas

LEEME = """Líderes countryball
====================

cuerpos/     240x240 px. Contorno NEGRO, interior BLANCO (ahí se pinta la bandera),
             fuera TRANSPARENTE. El nombre del archivo es el nombre del cuerpo.
ojos/        240x240 px, fondo transparente, solo los ojos en la zona de la cara
             (más o menos a la altura y = 105). Reglas countryball: óvalos blancos
             con contorno negro, SIN pupilas; la expresión se hace cortando el ojo
             con un párpado recto, y para mirar a un lado se mueven los dos ojos.
accesorios/  vacío por ahora (sombreros, bigotes, monóculos... más adelante).

Puedes dibujar los tuyos en Paint/GIMP con ese formato y dejarlos en la carpeta:
el juego los carga solos. Para regenerar los de ejemplo:
    python herramientas/generar_lideres.py
"""


def main():
    pygame.init()
    for carpeta in ("cuerpos", "ojos", "accesorios"):
        (DESTINO / carpeta).mkdir(parents=True, exist_ok=True)

    if FUENTE_CLASICA.exists():
        pygame.image.save(cuerpo_desde_contorno(FUENTE_CLASICA), str(DESTINO / "cuerpos" / "clasica.png"))
    for i, nombre in enumerate(FORMAS_CUERPO):
        pygame.image.save(cuerpo(nombre, random.Random(100 + i)), str(DESTINO / "cuerpos" / f"{nombre}.png"))
    for viejo in OJOS_VIEJOS:
        (DESTINO / "ojos" / f"{viejo}.png").unlink(missing_ok=True)
    for i, estilo in enumerate(ESTILOS_OJOS):
        pygame.image.save(ojos(estilo, random.Random(200 + i)), str(DESTINO / "ojos" / f"{estilo}.png"))

    (DESTINO / "LEEME.txt").write_text(LEEME, encoding="utf-8")
    (DESTINO / "accesorios" / "LEEME.txt").write_text(
        "Aquí irán los accesorios (240x240, fondo transparente). Por ahora no hay ninguno.\n",
        encoding="utf-8")
    print("Imágenes generadas en", DESTINO)


if __name__ == "__main__":
    main()
