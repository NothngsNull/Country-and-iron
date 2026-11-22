"""Estado de la partida: naciones, quién es dueño de cada provincia y colonización."""
from __future__ import annotations

import colorsys
import random
from collections import deque
from dataclasses import dataclass

from banderas import Bandera, bandera_aleatoria
from mapa import Mapa

# Días que tarda en colonizarse una provincia según su terreno
DIAS_COLONIZAR = {"llanura": 20, "bosque": 30, "colinas": 30, "pantano": 40, "desierto": 40,
                  "tundra": 45, "montana": 50}
MAX_COLONIAS = 2                 # colonizaciones a la vez por nación
PROVINCIAS_INICIALES = 3         # capital + vecinas al aparecer
DISTANCIA_APARICION = 2          # pasos mínimos (por tierra) hasta otra nación al aparecer
PROB_IA_COLONIZA = 0.12          # probabilidad diaria de que una IA empiece a colonizar

SILABAS = ["ar", "bel", "cor", "dan", "el", "for", "gal", "har", "is", "kar", "lor", "mar", "nor",
           "or", "pra", "quel", "ros", "sal", "tir", "ur", "val", "zan", "ven", "dor", "mir", "tal"]
SUFIJOS = ["ia", "ania", "or", "heim", "land", "istan", "ica", "ora", "en", "ar"]
FORMAS = ["Reino de {}", "Imperio de {}", "República de {}", "{}", "Gran {}", "Principado de {}",
          "Confederación de {}", "Sultanato de {}"]


@dataclass
class Nacion:
    nombre: str
    color: tuple[int, int, int]
    bandera: Bandera
    capital: int                  # id de provincia
    es_jugador: bool = False
    lider: object = None          # lider.Lider
    tag: str = ""                 # código de 3 letras (naciones.json)


@dataclass
class Colonizacion:
    nacion: int                   # índice en mundo.naciones
    provincia: int
    dias_totales: int
    dias: int = 0

    @property
    def progreso(self) -> float:
        return self.dias / self.dias_totales


def nombre_aleatorio(rng: random.Random) -> str:
    raiz = "".join(rng.choice(SILABAS) for _ in range(rng.randint(1, 2))) + rng.choice(SUFIJOS)
    return rng.choice(FORMAS).format(raiz.capitalize())


def color_aleatorio(rng: random.Random, usados) -> tuple[int, int, int]:
    mejor, mejor_dist = None, -1
    for _ in range(40):
        r, g, b = colorsys.hsv_to_rgb(rng.random(), rng.uniform(0.5, 0.85), rng.uniform(0.55, 0.9))
        c = (int(r * 255), int(g * 255), int(b * 255))
        if b > 0.4 and b > r + 0.15 and b > g + 0.1:
            continue                      # nada demasiado parecido al mar
        dist = min((sum(abs(x - y) for x, y in zip(c, u)) for u in usados), default=999)
        if dist > mejor_dist:
            mejor, mejor_dist = c, dist
    return mejor


class Mundo:
    def __init__(self, mapa: Mapa, patrones, gestor_lideres=None, semilla: int | None = None,
                 rivales: tuple[int, int] = (6, 9)):
        self.rng = random.Random(semilla)
        self.mapa = mapa
        self.patrones = patrones
        self.gestor_lideres = gestor_lideres
        self.naciones: list[Nacion] = []
        self.dueno: dict[int, int | None] = {pid: None for pid in mapa.provincias}
        self.colonias: list[Colonizacion] = []
        self.version = 0                  # sube cada vez que cambia algo que se dibuja en el mapa
        self.avisos: list[str] = []       # mensajes para el jugador
        self._naciones_del_json()
        if mapa.info.tipo != "establecido":          # en un mundo ya repartido no aparecen más
            self._generar_rivales(self.rng.randint(*rivales))

    # --- Creación ---------------------------------------------------------
    def _nueva_nacion(self, nombre: str, capital: int) -> Nacion:
        color = color_aleatorio(self.rng, [n.color for n in self.naciones])
        n = Nacion(nombre, color, bandera_aleatoria(self.rng, self.patrones, color), capital)
        if self.gestor_lideres is not None:
            n.lider = self.gestor_lideres.aleatorio(self.rng)
        return n

    def _nacion_definida(self, d: dict, provs: list[int]) -> Nacion:
        """Nación de naciones.json (con su color, bandera, líder y capital)."""
        from banderas import CapaBandera

        def color(texto, defecto=(128, 128, 128)):
            try:
                t = texto.lstrip("#")
                return int(t[0:2], 16), int(t[2:4], 16), int(t[4:6], 16)
            except (AttributeError, ValueError, IndexError):
                return defecto

        col = color(d.get("color"))
        capas = [CapaBandera(c.get("patron", "liso"), color(c.get("color"), col)) for c in d.get("bandera", [])]
        bandera = Bandera(capas) if capas else bandera_aleatoria(self.rng, self.patrones, col)
        capital = d.get("capital")
        if capital not in provs:
            capital = provs[0]
        n = Nacion(d.get("nombre", d["id"]), col, bandera, capital, tag=str(d["id"]))
        if self.gestor_lideres is not None:
            info = d.get("lider") or {}
            from lider import Lider
            al_azar = self.gestor_lideres.aleatorio(self.rng)
            n.lider = Lider(info.get("nombre", al_azar.nombre), info.get("cuerpo", al_azar.cuerpo),
                            info.get("ojos", al_azar.ojos), list(info.get("accesorios", [])))
        return n

    def _naciones_del_json(self):
        """Provincias con "dueno" en provincias.json crean esa nación al empezar.

        Si el dueño es un id de naciones.json se usa esa definición; si no, se
        crea una nación al azar con ese nombre."""
        grupos: dict[str, list[int]] = {}
        for pid, p in self.mapa.provincias.items():
            if p.dueno_inicial and p.es_tierra:
                grupos.setdefault(str(p.dueno_inicial), []).append(pid)
        # Primero en el orden de naciones.json, luego el resto
        orden = [t for t in self.mapa.naciones_def if t in grupos] + \
                [t for t in grupos if t not in self.mapa.naciones_def]
        for tag in orden:
            provs = sorted(grupos[tag])
            idx = len(self.naciones)
            if tag in self.mapa.naciones_def:
                self.naciones.append(self._nacion_definida(self.mapa.naciones_def[tag], provs))
            else:
                n = self._nueva_nacion(tag, provs[0])
                n.tag = tag
                self.naciones.append(n)
            for pid in provs:
                self.dueno[pid] = idx
        self.version += 1

    def _generar_rivales(self, cantidad: int):
        candidatos = [pid for pid, p in self.mapa.provincias.items() if p.es_tierra]
        self.rng.shuffle(candidatos)
        nombres = {n.nombre for n in self.naciones}
        for pid in candidatos:
            if len(self.naciones) >= cantidad:
                break
            if not self.puede_aparecer(pid, distancia=4):
                continue
            nombre = nombre_aleatorio(self.rng)
            while nombre in nombres:
                nombre = nombre_aleatorio(self.rng)
            nombres.add(nombre)
            self.fundar(self._nueva_nacion(nombre, pid))

    def zona_inicial(self, capital: int) -> list[int]:
        """Capital + vecinas libres (primero las de la misma región)."""
        mapa = self.mapa
        region = mapa.provincias[capital].region
        vecinas = [v for v in mapa.provincias[capital].vecinos
                   if mapa.provincias[v].es_tierra and self.dueno[v] is None]
        vecinas.sort(key=lambda v: (mapa.provincias[v].region != region, v))
        return [capital] + vecinas[:PROVINCIAS_INICIALES - 1]

    def fundar(self, nacion: Nacion) -> int:
        idx = len(self.naciones)
        self.naciones.append(nacion)
        for pid in self.zona_inicial(nacion.capital):
            self.dueno[pid] = idx
        self.colonias = [c for c in self.colonias if self.dueno[c.provincia] is None]
        self.version += 1
        return idx

    # --- Consultas ----------------------------------------------------------
    def puede_aparecer(self, pid: int, distancia: int = DISTANCIA_APARICION) -> bool:
        p = self.mapa.provincias.get(pid)
        if p is None or not p.es_tierra or self.dueno[pid] is not None:
            return False
        # Nadie a menos de `distancia` pasos por tierra
        vistos, cola = {pid}, deque([(pid, 0)])
        while cola:
            q, d = cola.popleft()
            if self.dueno[q] is not None:
                return False
            if d < distancia:
                for v in self.mapa.provincias[q].vecinos:
                    if v not in vistos and self.mapa.provincias[v].es_tierra:
                        vistos.add(v)
                        cola.append((v, d + 1))
        return True

    def provincias_de(self, idx: int) -> list[int]:
        return [pid for pid, d in self.dueno.items() if d == idx]

    def colonias_de(self, idx: int) -> list[Colonizacion]:
        return [c for c in self.colonias if c.nacion == idx]

    def colonia_en(self, idx: int, pid: int) -> Colonizacion | None:
        return next((c for c in self.colonias if c.nacion == idx and c.provincia == pid), None)

    def alcanzable(self, idx: int, pid: int) -> bool:
        """Toca una provincia propia por tierra, o comparte mar con una provincia costera propia."""
        mapa = self.mapa
        if any(self.dueno[v] == idx for v in mapa.provincias[pid].vecinos):
            return True
        mares = mapa.mares_vecinos[pid]
        if not mares:
            return False
        return any(self.dueno[q] == idx for m in mares for q in mapa.provincias[m].vecinos)

    def puede_colonizar(self, idx: int, pid: int) -> tuple[bool, str]:
        p = self.mapa.provincias[pid]
        if not p.es_tierra:
            return False, "El mar no se puede colonizar"
        if self.dueno[pid] is not None:
            return False, "Ya tiene dueño"
        if self.colonia_en(idx, pid):
            return False, "Ya la estás colonizando"
        if len(self.colonias_de(idx)) >= MAX_COLONIAS:
            return False, f"Máximo {MAX_COLONIAS} colonizaciones a la vez"
        if not self.alcanzable(idx, pid):
            return False, "Debe tocar tu territorio (por tierra o por mar)"
        return True, ""

    # --- Acciones -----------------------------------------------------------
    def colonizar(self, idx: int, pid: int) -> bool:
        ok, _ = self.puede_colonizar(idx, pid)
        if ok:
            dias = DIAS_COLONIZAR.get(self.mapa.provincias[pid].terreno, 30)
            self.colonias.append(Colonizacion(idx, pid, dias))
            self.version += 1
        return ok

    def cancelar(self, idx: int, pid: int) -> None:
        c = self.colonia_en(idx, pid)
        if c:
            self.colonias.remove(c)
            self.version += 1

    def nuevo_dia(self) -> None:
        for c in list(self.colonias):
            if c not in self.colonias:
                continue
            c.dias += 1
            if c.dias < c.dias_totales:
                continue
            self.colonias.remove(c)
            if self.dueno[c.provincia] is None:
                self.dueno[c.provincia] = c.nacion
                self.version += 1
                prov = self.mapa.provincias[c.provincia]
                if self.naciones[c.nacion].es_jugador:
                    self.avisos.append(f"¡{prov.nombre} ha sido colonizada!")
                # Los demás que la estaban colonizando la pierden
                for otra in [o for o in self.colonias if o.provincia == c.provincia]:
                    self.colonias.remove(otra)
                    if self.naciones[otra.nacion].es_jugador:
                        self.avisos.append(f"{self.naciones[c.nacion].nombre} colonizó {prov.nombre} antes que tú")
        self._ia()

    def _ia(self) -> None:
        for idx, n in enumerate(self.naciones):
            if n.es_jugador or len(self.colonias_de(idx)) >= 1 or self.rng.random() > PROB_IA_COLONIZA:
                continue
            propias = set(self.provincias_de(idx))
            candidatas = {v for p in propias for v in self.mapa.provincias[p].vecinos
                          if self.mapa.provincias[v].es_tierra and self.dueno[v] is None}
            if not candidatas:     # sin vecinas libres por tierra: probar por mar
                candidatas = {pid for pid, p in self.mapa.provincias.items()
                              if p.es_tierra and self.dueno[pid] is None and self.alcanzable(idx, pid)}
            if candidatas:
                self.colonizar(idx, self.rng.choice(sorted(candidatas)))
