import math
import random

import pygame

from banderas import GestorBanderas
from creacion import CreacionCivilizacion
from creacion_lider import CreacionLider
from lider import GestorLideres
from juego import Partida
from mapa import Mapa
from mundo import Mundo
from seleccion_mapa import SeleccionMapa
from ui import UI, salir

# --- Configuración general (fácil de cambiar cuando definamos el juego) ---
TITULO = "CIVILIZACIONES"
SUBTITULO = "Aprieta cualquier botón para empezar"
COLOR_FONDO_ARRIBA = (15, 15, 35)
COLOR_FONDO_ABAJO = (45, 20, 70)
COLOR_TITULO = (255, 255, 255)
COLOR_SUBTITULO = (200, 200, 255)
FPS = 60


def crear_fondo(ancho, alto):
    """Crea un fondo con degradado vertical."""
    fondo = pygame.Surface((ancho, alto))
    for y in range(alto):
        t = y / alto
        color = [int(a + (b - a) * t) for a, b in zip(COLOR_FONDO_ARRIBA, COLOR_FONDO_ABAJO)]
        pygame.draw.line(fondo, color, (0, y), (ancho, y))
    return fondo


def crear_estrellas(ancho, alto, cantidad=120):
    return [
        [random.uniform(0, ancho), random.uniform(0, alto), random.uniform(0.2, 1.0)]
        for _ in range(cantidad)
    ]


def pantalla_inicio(pantalla, reloj):
    """Muestra la pantalla de inicio. Devuelve True si el jugador quiere empezar."""
    ancho, alto = pantalla.get_size()
    fondo = crear_fondo(ancho, alto)
    estrellas = crear_estrellas(ancho, alto)

    fuente_titulo = pygame.font.Font(None, alto // 6)
    fuente_sub = pygame.font.Font(None, alto // 18)
    fuente_ayuda = pygame.font.Font(None, alto // 40)

    texto_titulo = fuente_titulo.render(TITULO, True, COLOR_TITULO)
    texto_sombra = fuente_titulo.render(TITULO, True, (0, 0, 0))
    texto_sub = fuente_sub.render(SUBTITULO, True, COLOR_SUBTITULO)
    texto_ayuda = fuente_ayuda.render("ESC para salir", True, (130, 130, 160))

    tiempo = 0.0
    while True:
        dt = reloj.tick(FPS) / 1000
        tiempo += dt

        for evento in pygame.event.get():
            if evento.type == pygame.QUIT:
                return False
            if evento.type == pygame.KEYDOWN:
                if evento.key == pygame.K_ESCAPE:
                    return False
                return True
            if evento.type in (pygame.MOUSEBUTTONDOWN, pygame.JOYBUTTONDOWN):
                return True

        # Fondo y estrellas que caen lentamente
        pantalla.blit(fondo, (0, 0))
        for estrella in estrellas:
            estrella[1] += estrella[2] * 40 * dt
            if estrella[1] > alto:
                estrella[0], estrella[1] = random.uniform(0, ancho), 0
            brillo = int(150 + 105 * estrella[2])
            pygame.draw.circle(pantalla, (brillo, brillo, brillo),
                               (int(estrella[0]), int(estrella[1])), max(1, int(estrella[2] * 2.5)))

        # Título flotando suavemente
        desplazamiento = math.sin(tiempo * 2) * 10
        rect_titulo = texto_titulo.get_rect(center=(ancho // 2, alto // 3 + desplazamiento))
        pantalla.blit(texto_sombra, rect_titulo.move(5, 5))
        pantalla.blit(texto_titulo, rect_titulo)

        # Subtítulo parpadeante (fade in/out)
        alfa = int(127 + 128 * math.sin(tiempo * 3))
        texto_sub.set_alpha(alfa)
        pantalla.blit(texto_sub, texto_sub.get_rect(center=(ancho // 2, alto * 2 // 3)))

        pantalla.blit(texto_ayuda, texto_ayuda.get_rect(bottomright=(ancho - 20, alto - 20)))

        pygame.display.flip()


def main():
    pygame.init()
    pygame.joystick.init()
    for i in range(pygame.joystick.get_count()):
        pygame.joystick.Joystick(i).init()

    pantalla = pygame.display.set_mode((0, 0), pygame.FULLSCREEN)
    pygame.display.set_caption(TITULO)
    reloj = pygame.time.Clock()

    if not pantalla_inicio(pantalla, reloj):
        salir()

    W, H = pantalla.get_size()
    ui = UI(escala=H / 1080)
    gestor = GestorBanderas()
    gestor_lideres = GestorLideres(gestor)

    # 1) Elegir mapa
    mapa = Mapa(SeleccionMapa(ui).ejecutar(pantalla, reloj))

    # 2a) Mundo ya repartido: el jugador elige una de las naciones que existen
    if mapa.info.tipo == "establecido":
        mundo = Mundo(mapa, gestor.patrones, gestor_lideres)
        Partida(ui, gestor, mundo, pantalla).ejecutar(pantalla, reloj)
        return

    # 2b) Colonización: el jugador crea su civilización (nombre y bandera) y luego a su líder.
    #     Desde el líder se puede volver a la bandera.
    creacion = CreacionCivilizacion(ui, gestor)
    lider = None
    while True:
        nombre, bandera = creacion.ejecutar(pantalla, reloj)
        resultado = CreacionLider(ui, gestor_lideres, nombre, bandera, lider).ejecutar(pantalla, reloj)
        if resultado is not None:
            lider = resultado
            break

    # 3) Aparecen naciones rivales al azar y el jugador elige dónde aparecer
    mundo = Mundo(mapa, gestor.patrones, gestor_lideres)
    Partida(ui, gestor, mundo, pantalla, nombre, bandera, lider).ejecutar(pantalla, reloj)


if __name__ == "__main__":
    main()
