"""Sistema de banderas por capas (adaptado de Map and Irons)."""
from banderas.modelo import Bandera, CapaBandera
from banderas.render import GestorBanderas, tamano_para_alto
from banderas.generador import COLORES_BANDERA, bandera_aleatoria

__all__ = ["Bandera", "CapaBandera", "GestorBanderas", "tamano_para_alto",
           "COLORES_BANDERA", "bandera_aleatoria"]
