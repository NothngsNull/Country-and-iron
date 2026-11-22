"""Carga del mapa de provincias (estilo HOI4).

datos/mapa/provincias.png   cada provincia pintada con un color único
datos/mapa/provincias.json  id, color, nombre, tipo, terreno y dueño inicial de cada provincia
datos/mapa/regiones.json    qué provincias forman cada región (editable a mano o en el juego)
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np
import pygame

CARPETA_MAPAS = Path(__file__).resolve().parent / "datos" / "mapas"
CARPETA = CARPETA_MAPAS / "nuevo_mundo"


@dataclass
class InfoMapa:
    carpeta: Path
    nombre: str
    descripcion: str
    tipo: str                      # "colonizacion" (creas tu nación) o "establecido" (eliges una)


def leer_info(carpeta: Path) -> InfoMapa:
    ruta = Path(carpeta) / "mapa.json"
    datos = json.loads(ruta.read_text(encoding="utf-8")) if ruta.exists() else {}
    return InfoMapa(Path(carpeta), datos.get("nombre", Path(carpeta).name),
                    datos.get("descripcion", ""), datos.get("tipo", "colonizacion"))


def listar_mapas() -> list[InfoMapa]:
    """Todas las carpetas de datos/mapas/ que tengan provincias.png y provincias.json."""
    mapas = []
    for carpeta in sorted(CARPETA_MAPAS.iterdir()) if CARPETA_MAPAS.exists() else []:
        if (carpeta / "provincias.png").exists() and (carpeta / "provincias.json").exists():
            mapas.append(leer_info(carpeta))
    return mapas

NOMBRE_TERRENO = {"llanura": "Llanura", "bosque": "Bosque", "colinas": "Colinas", "montana": "Montaña",
                  "desierto": "Desierto", "pantano": "Pantano", "tundra": "Tundra", "mar": "Mar"}


@dataclass
class Provincia:
    id: int
    nombre: str
    color: tuple[int, int, int]
    tipo: str                      # "tierra" o "mar"
    terreno: str
    dueno_inicial: str | None = None
    centro: tuple[int, int] = (0, 0)       # punto interior (para banderas y nombres)
    area: int = 0
    vecinos: set[int] = field(default_factory=set)
    region: int | None = None

    @property
    def es_tierra(self) -> bool:
        return self.tipo == "tierra"


@dataclass
class Region:
    id: int
    nombre: str
    tipo: str
    provincias: list[int] = field(default_factory=list)


def _hex_a_color(texto: str) -> tuple[int, int, int]:
    texto = texto.lstrip("#")
    return int(texto[0:2], 16), int(texto[2:4], 16), int(texto[4:6], 16)


def json_lista(cabecera: dict, clave: str, elementos: list) -> str:
    """JSON legible: un elemento por línea (fácil de editar a mano)."""
    partes = [f' "{k}": {json.dumps(v, ensure_ascii=False)},' for k, v in cabecera.items()]
    filas = ",\n".join("  " + json.dumps(e, ensure_ascii=False) for e in elementos)
    return "{\n" + "\n".join(partes) + ("\n" if partes else "") + f' "{clave}": [\n{filas}\n ]\n}}\n'


class Mapa:
    def __init__(self, carpeta: Path = CARPETA):
        self.carpeta = Path(carpeta)
        self.info = leer_info(self.carpeta)
        # Naciones predefinidas (mapas "establecido"): naciones.json, opcional
        ruta_nac = self.carpeta / "naciones.json"
        self.naciones_def: dict[str, dict] = {}
        if ruta_nac.exists():
            for n in json.loads(ruta_nac.read_text(encoding="utf-8")).get("naciones", []):
                self.naciones_def[str(n["id"])] = n
        datos = json.loads((self.carpeta / "provincias.json").read_text(encoding="utf-8"))
        self.provincias: dict[int, Provincia] = {}
        for p in datos["provincias"]:
            self.provincias[int(p["id"])] = Provincia(int(p["id"]), p.get("nombre", f"Provincia {p['id']}"),
                                                       _hex_a_color(p["color"]), p.get("tipo", "tierra"),
                                                       p.get("terreno", "llanura"), p.get("dueno"))
        self._cargar_imagen()
        self._calcular_geometria()
        self.version_regiones = 0
        self.cargar_regiones()

    # ------------------------------------------------------------------
    def _cargar_imagen(self):
        img = pygame.image.load(str(self.carpeta / "provincias.png"))
        rgb = pygame.surfarray.array3d(img).swapaxes(0, 1).astype(np.int32)   # (alto, ancho, 3)
        self.alto, self.ancho = rgb.shape[:2]
        clave = (rgb[..., 0] << 16) | (rgb[..., 1] << 8) | rgb[..., 2]
        colores = {(c[0] << 16) | (c[1] << 8) | c[2]: pid for pid, c in
                   ((pid, p.color) for pid, p in self.provincias.items())}
        unicos, inversa = np.unique(clave, return_inverse=True)
        tabla = np.array([colores.get(int(u), 0) for u in unicos], dtype=np.int32)
        self.ids = tabla[inversa].reshape(clave.shape)                      # 0 = color desconocido
        desconocidos = sum(1 for u in unicos if int(u) not in colores)
        if desconocidos:
            print(f"[mapa] {desconocidos} colores de provincias.png no están en provincias.json")

    def _calcular_geometria(self):
        ids = self.ids
        n = max(self.provincias) + 1
        areas = np.bincount(ids.ravel(), minlength=n)
        yy, xx = np.mgrid[0:self.alto, 0:self.ancho]
        sx = np.bincount(ids.ravel(), weights=xx.ravel(), minlength=n)
        sy = np.bincount(ids.ravel(), weights=yy.ravel(), minlength=n)
        # Profundidad: cuántos píxeles hay hasta el borde de la provincia
        prof = np.zeros(ids.shape, dtype=np.int32)
        dentro = np.ones(ids.shape, dtype=bool)
        for k in range(1, 16):
            nuevo = dentro.copy()
            nuevo[1:, :] &= (ids[1:, :] == ids[:-1, :]) & dentro[:-1, :]
            nuevo[:-1, :] &= (ids[:-1, :] == ids[1:, :]) & dentro[1:, :]
            nuevo[:, 1:] &= (ids[:, 1:] == ids[:, :-1]) & dentro[:, :-1]
            nuevo[:, :-1] &= (ids[:, :-1] == ids[:, 1:]) & dentro[:, 1:]
            nuevo[0, :] = nuevo[-1, :] = False
            nuevo[:, 0] = nuevo[:, -1] = False
            dentro = nuevo
            prof[dentro] = k
        # Punto interior: el más profundo, y entre esos el más cercano al centro de masa
        cx = np.divide(sx, np.maximum(areas, 1))
        cy = np.divide(sy, np.maximum(areas, 1))
        plano = ids.ravel()
        dist = (xx.ravel() - cx[plano]) ** 2 + (yy.ravel() - cy[plano]) ** 2
        puntaje = prof.ravel() * 1000.0 - dist
        orden = np.lexsort((puntaje, plano))
        ultimo = np.r_[plano[orden][1:] != plano[orden][:-1], True]
        for idx in orden[ultimo]:
            pid = int(plano[idx])
            if pid in self.provincias:
                self.provincias[pid].centro = (int(idx % self.ancho), int(idx // self.ancho))
        for pid, p in self.provincias.items():
            p.area = int(areas[pid]) if pid < n else 0
        # Vecinos
        for a, b in ((ids[:, :-1], ids[:, 1:]), (ids[:-1, :], ids[1:, :])):
            dif = a != b
            pares = np.unique(np.stack([a[dif], b[dif]], axis=1), axis=0)
            for x, y in pares.tolist():
                if x in self.provincias and y in self.provincias:
                    self.provincias[x].vecinos.add(y)
                    self.provincias[y].vecinos.add(x)
        self.mares_vecinos = {pid: {v for v in p.vecinos if not self.provincias[v].es_tierra}
                              for pid, p in self.provincias.items()}

    # ------------------------------------------------------------------
    def provincia_en(self, x: float, y: float) -> Provincia | None:
        xi, yi = int(x), int(y)
        if 0 <= xi < self.ancho and 0 <= yi < self.alto:
            return self.provincias.get(int(self.ids[yi, xi]))
        return None

    def region_de(self, pid: int) -> Region | None:
        rid = self.provincias[pid].region
        return self.regiones.get(rid) if rid is not None else None

    # --- Regiones -------------------------------------------------------
    def cargar_regiones(self):
        self.regiones: dict[int, Region] = {}
        for p in self.provincias.values():
            p.region = None
        ruta = self.carpeta / "regiones.json"
        if ruta.exists():
            for r in json.loads(ruta.read_text(encoding="utf-8")).get("regiones", []):
                region = Region(int(r["id"]), r.get("nombre", f"Región {r['id']}"), r.get("tipo", "tierra"))
                for pid in r.get("provincias", []):
                    pid = int(pid)
                    if pid in self.provincias and self.provincias[pid].region is None:
                        self.provincias[pid].region = region.id
                        region.provincias.append(pid)
                self.regiones[region.id] = region
        self.version_regiones += 1

    def nueva_region(self, tipo: str, nombre: str | None = None) -> Region:
        rid = max(self.regiones, default=0) + 1
        region = Region(rid, nombre or f"Nueva región {rid}", tipo)
        self.regiones[rid] = region
        self.version_regiones += 1
        return region

    def mover_a_region(self, pid: int, rid: int) -> bool:
        p = self.provincias[pid]
        destino = self.regiones[rid]
        if p.region == rid or p.tipo != destino.tipo:
            return False
        if p.region is not None and p.region in self.regiones:
            self.regiones[p.region].provincias.remove(pid)
        p.region = rid
        destino.provincias.append(pid)
        self.version_regiones += 1
        return True

    def guardar_regiones(self) -> Path:
        vacias = [rid for rid, r in self.regiones.items() if not r.provincias]
        for rid in vacias:
            del self.regiones[rid]
        lista = [{"id": r.id, "nombre": r.nombre, "tipo": r.tipo, "provincias": sorted(r.provincias)}
                 for r in sorted(self.regiones.values(), key=lambda r: r.id)]
        ruta = self.carpeta / "regiones.json"
        ruta.write_text(json_lista({}, "regiones", lista), encoding="utf-8")
        self.version_regiones += 1
        return ruta
