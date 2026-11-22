"""Genera el mapa de provincias (estilo HOI4: una imagen con un color único por provincia).

Uso:
  python herramientas/generar_mapa.py                       (Nuevo Mundo: sin colonizar, semilla 7)
  python herramientas/generar_mapa.py --carpeta otro --semilla 1234 --nombre "Otro mapa"
  python herramientas/generar_mapa.py --carpeta viejo_mundo --semilla 1453 --establecido

Crea en datos/mapas/<carpeta>/:
  mapa.json        -> nombre, descripción y tipo del mapa
  provincias.png   -> cada provincia pintada con su color único (como provinces.bmp de HOI4)
  provincias.json  -> id, color, nombre, tipo (tierra/mar), terreno y dueño de cada provincia
  regiones.json    -> qué provincias forman cada región (se puede editar a mano o en el juego)
  naciones.json    -> (solo con --establecido) las naciones que ya existen en el mapa

¡Ojo! Regenerar un mapa sobrescribe sus archivos (también tus cambios de regiones o naciones).
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, deque
from pathlib import Path

import numpy as np
from scipy import ndimage

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
CARPETA_MAPAS = RAIZ / "datos" / "mapas"
ANCHO, ALTO = 480, 270
PROVINCIAS_TIERRA = 240
PROVINCIAS_MAR = 50              # las de mar son mucho más grandes
PROVINCIAS_POR_REGION = 5
PROVINCIAS_MAR_POR_REGION = 5
PORCENTAJE_TIERRA = 0.44

SILABAS = ["al", "ba", "cor", "da", "el", "fen", "gar", "hel", "ir", "ka", "lo", "mar", "nor", "os", "pa",
           "ques", "ri", "sa", "tor", "ul", "va", "ze", "bri", "dun", "mon", "sel", "ter", "vin", "ast", "ber"]
FINALES = ["a", "ia", "on", "en", "ar", "or", "is", "um", "ana", "eth", "ur", "ia", "es", "ino"]


# ---------------------------------------------------------------------------
def ruido(rng, escala: int) -> np.ndarray:
    """Ruido de valor suave en [0, 1] del tamaño del mapa."""
    gh, gw = ALTO // escala + 3, ANCHO // escala + 3
    base = rng.random((gh, gw))
    ys = np.arange(ALTO) / escala
    xs = np.arange(ANCHO) / escala
    y0, x0 = ys.astype(int), xs.astype(int)
    ty, tx = ys - y0, xs - x0
    ty, tx = ty * ty * (3 - 2 * ty), tx * tx * (3 - 2 * tx)
    a = base[y0][:, x0] * (1 - tx) + base[y0][:, x0 + 1] * tx
    b = base[y0 + 1][:, x0] * (1 - tx) + base[y0 + 1][:, x0 + 1] * tx
    return a * (1 - ty)[:, None] + b * ty[:, None]


def fractal(rng, escalas):
    total = sum(ruido(rng, s) * a for s, a in escalas)
    return (total - total.min()) / (total.max() - total.min())


def nombre(rng, usados: set) -> str:
    while True:
        n = "".join(rng.choice(SILABAS) for _ in range(rng.integers(1, 3))) + rng.choice(FINALES)
        n = n.capitalize()
        if n not in usados and len(n) > 3:
            usados.add(n)
            return n


# ---------------------------------------------------------------------------
def generar_tierra(rng):
    detalle = fractal(rng, [(60, 1.0), (30, 0.5), (15, 0.25), (7, 0.13), (3, 0.06)])
    yy, xx = np.mgrid[0:ALTO, 0:ANCHO].astype(float)
    # Coordenadas deformadas para costas irregulares
    dx = (fractal(rng, [(40, 1.0), (15, 0.4)]) - 0.5) * 70
    dy = (fractal(rng, [(40, 1.0), (15, 0.4)]) - 0.5) * 70
    # Varios continentes: manchas elípticas de distinto tamaño
    continentes = np.zeros((ALTO, ANCHO))
    for _ in range(int(rng.integers(3, 6))):
        cx, cy = rng.uniform(0.15, 0.85) * ANCHO, rng.uniform(0.2, 0.8) * ALTO
        rx, ry = rng.uniform(45, 110), rng.uniform(35, 80)
        d = ((xx + dx - cx) / rx) ** 2 + ((yy + dy - cy) / ry) ** 2
        continentes = np.maximum(continentes, np.exp(-d * 1.4))
    altura = continentes * 0.75 + detalle * 0.45
    # Bordes del mapa hacia el mar
    borde = np.minimum.reduce([xx / ANCHO, 1 - xx / ANCHO, yy / ALTO, 1 - yy / ALTO])
    altura = altura - np.clip(1 - borde / 0.12, 0, 1) * 0.9
    umbral = np.quantile(altura, 1 - PORCENTAJE_TIERRA)
    tierra = altura > umbral

    # Limpieza: islas diminutas al mar y lagos pequeños a tierra
    etiquetas, n = ndimage.label(tierra)
    tam = ndimage.sum(tierra, etiquetas, range(1, n + 1))
    for i, t in enumerate(tam, 1):
        if t < 30:
            tierra[etiquetas == i] = False
    agua_et, n = ndimage.label(~tierra)
    tam = ndimage.sum(~tierra, agua_et, range(1, n + 1))
    for i, t in enumerate(tam, 1):
        if t < 120:
            tierra[agua_et == i] = True
    alt_norm = (altura - umbral) / (altura.max() - umbral)
    return tierra, np.clip(alt_norm, 0, 1)


def semillas(rng, mascara, cantidad):
    ys, xs = np.nonzero(mascara)
    dist_min = np.sqrt(len(ys) / cantidad) * 0.8
    elegidas = []
    for _ in range(cantidad * 200):
        if len(elegidas) >= cantidad:
            break
        i = rng.integers(len(ys))
        p = (xs[i], ys[i])
        if all((p[0] - q[0]) ** 2 + (p[1] - q[1]) ** 2 >= dist_min ** 2 for q in elegidas):
            elegidas.append(p)
    return np.array(elegidas, dtype=float)


def asignar(mascara, puntos, wx, wy, primer_id):
    """Voronoi deformado: cada píxel de la máscara va a la semilla más cercana."""
    ids = np.zeros((ALTO, ANCHO), dtype=np.int32)
    ys, xs = np.nonzero(mascara)
    px, py = xs + wx[ys, xs], ys + wy[ys, xs]
    mejor = np.full(len(xs), np.inf)
    cual = np.zeros(len(xs), dtype=np.int32)
    for k, (sx, sy) in enumerate(puntos):
        d = (px - sx) ** 2 + (py - sy) ** 2
        menor = d < mejor
        mejor[menor] = d[menor]
        cual[menor] = k
    ids[ys, xs] = cual + primer_id
    return ids


def vecinos_de_zona(ids, zona):
    borde = ndimage.binary_dilation(zona) & ~zona
    return Counter(ids[borde].tolist())


def limpiar(ids, tierra):
    """Cada provincia debe ser una sola pieza y no demasiado pequeña."""
    siguiente = int(ids.max()) + 1
    for _ in range(4):
        cambios = False
        for pid in np.unique(ids):
            zona_total = ids == pid
            et, n = ndimage.label(zona_total)
            if n <= 1:
                continue
            tam = ndimage.sum(zona_total, et, range(1, n + 1))
            mayor = int(np.argmax(tam)) + 1
            for i in range(1, n + 1):
                if i == mayor:
                    continue
                zona = et == i
                es_tierra = tierra[zona][0]
                vec = {v: c for v, c in vecinos_de_zona(ids, zona).items() if tierra[ids == v][0] == es_tierra}
                if vec:
                    ids[zona] = max(vec, key=vec.get)
                elif tam[i - 1] >= 25:
                    ids[zona] = siguiente           # isla sin semilla: provincia propia
                    siguiente += 1
                else:
                    ids[zona] = max(vecinos_de_zona(ids, zona), key=lambda v: 1)
                    tierra[zona] = not es_tierra
                cambios = True
        # Provincias de tierra muy pequeñas se funden con su vecina
        for pid in np.unique(ids):
            zona = ids == pid
            if tierra[zona][0] and zona.sum() < 45:
                vec = {v: c for v, c in vecinos_de_zona(ids, zona).items() if tierra[ids == v][0]}
                if vec:
                    ids[zona] = max(vec, key=vec.get)
                    cambios = True
        if not cambios:
            break
    return ids


def adyacencias(ids):
    pares = set()
    for a, b in ((ids[:, :-1], ids[:, 1:]), (ids[:-1, :], ids[1:, :])):
        dif = a != b
        for x, y in zip(a[dif].tolist(), b[dif].tolist()):
            pares.add((min(x, y), max(x, y)))
    vec = {}
    for x, y in pares:
        vec.setdefault(x, set()).add(y)
        vec.setdefault(y, set()).add(x)
    return vec


def agrupar(rng, provs, vec, centros, por_grupo):
    """Agrupa provincias conectadas en regiones de tamaño parecido (crecimiento por turnos)."""
    provs = list(provs)
    conjunto = set(provs)
    n_grupos = max(1, round(len(provs) / por_grupo))
    # Semillas lo más separadas posible
    semillas_g = [provs[rng.integers(len(provs))]]
    while len(semillas_g) < n_grupos:
        lejos = max(provs, key=lambda p: min((centros[p][0] - centros[s][0]) ** 2 +
                                              (centros[p][1] - centros[s][1]) ** 2 for s in semillas_g))
        semillas_g.append(lejos)
    grupo = {s: i for i, s in enumerate(semillas_g)}
    fronteras = [deque([s]) for s in semillas_g]
    tam = [1] * len(semillas_g)
    activo = True
    while activo:
        activo = False
        for i in sorted(range(len(fronteras)), key=lambda i: tam[i]):
            f = fronteras[i]
            while f:
                p = f[0]
                libres = [v for v in vec.get(p, ()) if v in conjunto and v not in grupo]
                if not libres:
                    f.popleft()
                    continue
                v = libres[rng.integers(len(libres))]
                grupo[v] = i
                tam[i] += 1
                f.append(v)
                activo = True
                break
    # Lo que no se alcanzó (islas): cada componente es un grupo nuevo
    siguiente = len(semillas_g)
    for p in provs:
        if p in grupo:
            continue
        cola = deque([p])
        grupo[p] = siguiente
        while cola:
            q = cola.popleft()
            for v in vec.get(q, ()):
                if v in conjunto and v not in grupo:
                    grupo[v] = siguiente
                    cola.append(v)
        siguiente += 1
    resultado = {}
    for p, g in grupo.items():
        resultado.setdefault(g, []).append(p)
    return list(resultado.values())


def elegir_terreno(alt, hum, lat, cresta):
    # Las montañas salen en cordilleras (crestas del ruido), no en manchas enormes
    if cresta > 0.88 and alt > 0.2:
        return "montana"
    if lat > 0.7:
        return "tundra"
    if cresta > 0.8 or alt > 0.93:
        return "colinas"
    if hum < 0.32 and lat < 0.55:
        return "desierto"
    if hum > 0.68 and alt < 0.18:
        return "pantano"
    if hum > 0.5:
        return "bosque"
    return "llanura"


def json_lista(cabecera: dict, clave: str, elementos: list) -> str:
    """JSON legible: un elemento por línea (fácil de editar a mano)."""
    partes = [f' "{k}": {json.dumps(v, ensure_ascii=False)},' for k, v in cabecera.items()]
    filas = ",\n".join("  " + json.dumps(e, ensure_ascii=False) for e in elementos)
    return "{\n" + "\n".join(partes) + ("\n" if partes else "") + f' "{clave}": [\n{filas}\n ]\n}}\n'


# ---------------------------------------------------------------------------
def crear_naciones(semilla, regiones, provincias, vec, centros, cantidad):
    """Reparte TODA la tierra entre naciones hechas de regiones enteras, de tamaños variados."""
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    from banderas.generador import bandera_aleatoria
    from lider import APODOS, NOMBRES
    from mundo import color_aleatorio, nombre_aleatorio

    rng = random.Random(semilla)
    reg_tierra = [r for r in regiones if r["tipo"] == "tierra"]
    region_de = {p: r["id"] for r in reg_tierra for p in r["provincias"]}
    vec_reg = {r["id"]: set() for r in reg_tierra}
    for p, rid in region_de.items():
        for v in vec.get(p, ()):
            if v in region_de and region_de[v] != rid:
                vec_reg[rid].add(region_de[v])
    centro_reg = {r["id"]: (np.mean([centros[p][0] for p in r["provincias"]]),
                            np.mean([centros[p][1] for p in r["provincias"]])) for r in reg_tierra}

    # Semillas separadas; cada nación crece a su ritmo (unas serán imperios y otras pequeñas)
    ids_reg = list(vec_reg)
    semillas_n = [rng.choice(ids_reg)]
    while len(semillas_n) < min(cantidad, len(ids_reg)):
        semillas_n.append(max(ids_reg, key=lambda r: min(
            (centro_reg[r][0] - centro_reg[s][0]) ** 2 + (centro_reg[r][1] - centro_reg[s][1]) ** 2
            for s in semillas_n)))
    dueno = {s: i for i, s in enumerate(semillas_n)}
    pesos = [rng.uniform(0.3, 3.0) for _ in semillas_n]
    while True:
        opciones = [(i, v) for r, i in dueno.items() for v in vec_reg[r] if v not in dueno]
        if not opciones:
            break
        por_nacion = {}
        for i, v in opciones:
            por_nacion.setdefault(i, []).append(v)
        i = rng.choices(list(por_nacion), weights=[pesos[k] for k in por_nacion])[0]
        dueno[rng.choice(por_nacion[i])] = i
    # Islas sin alcanzar: cada grupo conectado es una nación nueva
    for r in ids_reg:
        if r in dueno:
            continue
        nuevo = max(dueno.values()) + 1
        cola = deque([r])
        dueno[r] = nuevo
        while cola:
            q = cola.popleft()
            for v in vec_reg[q]:
                if v not in dueno:
                    dueno[v] = nuevo
                    cola.append(v)
    # Naciones diminutas (menos de 3 provincias) pasan a la nación más cercana
    def provincias_de(i):
        return [p for r, k in dueno.items() if k == i for p in next(x for x in reg_tierra if x["id"] == r)["provincias"]]
    for i in sorted(set(dueno.values())):
        if 0 < len(provincias_de(i)) < 3:
            mis = [r for r, k in dueno.items() if k == i]
            otros = [r for r, k in dueno.items() if k != i]
            cerca = min(otros, key=lambda o: min((centro_reg[o][0] - centro_reg[m][0]) ** 2 +
                                                 (centro_reg[o][1] - centro_reg[m][1]) ** 2 for m in mis))
            for m in mis:
                dueno[m] = dueno[cerca]

    patrones = [p.stem for p in (RAIZ / "datos" / "banderas" / "patrones").glob("*.png")]
    cuerpos = sorted(p.stem for p in (RAIZ / "datos" / "lideres" / "cuerpos").glob("*.png"))
    ojos = sorted(p.stem for p in (RAIZ / "datos" / "lideres" / "ojos").glob("*.png"))
    naciones, tags, colores = [], set(), []
    dueno_prov = {}
    for i in sorted(set(dueno.values())):
        provs = provincias_de(i)
        nombre_n = nombre_aleatorio(rng)
        while any(n["nombre"] == nombre_n for n in naciones):
            nombre_n = nombre_aleatorio(rng)
        raiz = "".join(ch for ch in nombre_n.split()[-1].upper() if ch.isalpha())
        # Código de 3 letras: primero las 3 iniciales del nombre, si no, otras letras del nombre
        opciones = [raiz[:3]] + [raiz[0] + a + b for i, a in enumerate(raiz[1:], 1) for b in raiz[i + 1:]]
        tag = next((t for t in opciones if len(t) == 3 and t not in tags), None)
        while tag is None or tag in tags:
            tag = "".join(rng.choice("ABCDEFGHIJKLMNOPRSTUVZ") for _ in range(3))
        tags.add(tag)
        color = color_aleatorio(rng, colores)
        colores.append(color)
        bandera = bandera_aleatoria(rng, patrones, color)
        mx = np.mean([centros[p][0] for p in provs])
        my = np.mean([centros[p][1] for p in provs])
        capital = min(provs, key=lambda p: (centros[p][0] - mx) ** 2 + (centros[p][1] - my) ** 2)
        naciones.append({
            "id": tag,
            "nombre": nombre_n,
            "color": "#%02x%02x%02x" % color,
            "capital": int(capital),
            "bandera": [{"patron": c.patron, "color": "#%02x%02x%02x" % tuple(c.color)} for c in bandera.capas],
            "lider": {"nombre": f"{rng.choice(NOMBRES)} {rng.choice(APODOS)}",
                      "cuerpo": rng.choice(cuerpos), "ojos": rng.choice(ojos)},
        })
        for p in provs:
            dueno_prov[p] = tag
    for p in provincias:
        p["dueno"] = dueno_prov.get(p["id"])
    naciones.sort(key=lambda n: -sum(1 for p in provincias if p["dueno"] == n["id"]))
    return naciones


def main():
    args = argparse.ArgumentParser(description="Genera un mapa de provincias")
    args.add_argument("--carpeta", default="nuevo_mundo", help="carpeta dentro de datos/mapas/")
    args.add_argument("--semilla", type=int, default=7)
    args.add_argument("--establecido", action="store_true",
                      help="toda la tierra ya pertenece a naciones (se crea naciones.json)")
    args.add_argument("--naciones", type=int, default=22, help="cuántas naciones (con --establecido)")
    args.add_argument("--nombre", default=None, help="nombre del mapa que se ve en el juego")
    args = args.parse_args()
    semilla = args.semilla
    DESTINO = CARPETA_MAPAS / args.carpeta
    rng = np.random.default_rng(semilla)
    tierra, altura = generar_tierra(rng)
    humedad = fractal(rng, [(50, 1.0), (20, 0.4), (8, 0.15)])
    # 1 en las "crestas" (cordilleras). Generador aparte para no cambiar la forma del mapa.
    cresta = 1 - np.abs(fractal(np.random.default_rng(semilla + 1), [(45, 1.0), (20, 0.4)]) * 2 - 1)
    wx = (fractal(rng, [(14, 1.0), (6, 0.5)]) - 0.5) * 14
    wy = (fractal(rng, [(14, 1.0), (6, 0.5)]) - 0.5) * 14

    pt = semillas(rng, tierra, PROVINCIAS_TIERRA)
    pm = semillas(rng, ~tierra, PROVINCIAS_MAR)
    ids = asignar(tierra, pt, wx, wy, 1) + asignar(~tierra, pm, wx * 2, wy * 2, len(pt) + 1)
    ids = limpiar(ids, tierra)

    # Renumerar: primero tierra, luego mar, empezando en 1
    viejos = sorted(np.unique(ids), key=lambda p: (not tierra[ids == p][0], p))
    tabla = np.zeros(ids.max() + 1, dtype=np.int32)
    for nuevo, viejo in enumerate(viejos, 1):
        tabla[viejo] = nuevo
    ids = tabla[ids]
    n = len(viejos)

    es_tierra = {p: bool(tierra[ids == p][0]) for p in range(1, n + 1)}
    vec = adyacencias(ids)
    centros = {}
    for p in range(1, n + 1):
        ys, xs = np.nonzero(ids == p)
        centros[p] = (float(xs.mean()), float(ys.mean()))

    # Colores únicos por provincia
    colores, usados_c = {}, set()
    for p in range(1, n + 1):
        while True:
            c = tuple(int(v) for v in rng.integers(20, 236, 3))
            if es_tierra[p] and c[2] > max(c[0], c[1]) + 30:
                continue                     # tierra sin tonos "de mar" para no confundirse
            if es_tierra[p] is False:
                c = (int(rng.integers(0, 60)), int(rng.integers(40, 140)), int(rng.integers(150, 256)))
            if c not in usados_c:
                usados_c.add(c)
                colores[p] = c
                break

    usados_n = set()
    provincias = []
    for p in range(1, n + 1):
        zona = ids == p
        if es_tierra[p]:
            lat = abs(centros[p][1] / ALTO - 0.5) * 2
            terreno = elegir_terreno(float(altura[zona].mean()), float(humedad[zona].mean()), lat,
                                     float(cresta[zona].mean()))
        else:
            terreno = "mar"
        provincias.append({
            "id": p,
            "nombre": nombre(rng, usados_n),
            "color": "#%02x%02x%02x" % colores[p],
            "tipo": "tierra" if es_tierra[p] else "mar",
            "terreno": terreno,
            "dueno": None,
        })

    # Regiones
    tierra_p = [p for p in range(1, n + 1) if es_tierra[p]]
    mar_p = [p for p in range(1, n + 1) if not es_tierra[p]]
    regiones = []
    prefijos_t = ["Tierras de", "Valle de", "Marca de", "Llanos de", "Condado de", "Ducado de", "Comarca de"]
    prefijos_m = ["Mar de", "Golfo de", "Estrecho de", "Océano de", "Bahía de"]
    for tipo, provs, por, prefijos in (("tierra", tierra_p, PROVINCIAS_POR_REGION, prefijos_t),
                                       ("mar", mar_p, PROVINCIAS_MAR_POR_REGION, prefijos_m)):
        for grupo in agrupar(rng, provs, vec, centros, por):
            regiones.append({
                "id": len(regiones) + 1,
                "nombre": f"{rng.choice(prefijos)} {nombre(rng, usados_n)}",
                "tipo": tipo,
                "provincias": sorted(int(p) for p in grupo),
            })

    naciones = None
    if args.establecido:
        naciones = crear_naciones(semilla, regiones, provincias, vec, centros, args.naciones)

    # Guardar
    DESTINO.mkdir(parents=True, exist_ok=True)
    info = {"nombre": args.nombre or ("Viejo Mundo" if args.establecido else "Nuevo Mundo"),
            "descripcion": ("Un mundo ya repartido entre naciones. Elige una y gobiérnala."
                            if args.establecido else
                            "Tierras sin colonizar. Crea tu civilización, elige dónde aparecer y expándete."),
            "tipo": "establecido" if args.establecido else "colonizacion"}
    (DESTINO / "mapa.json").write_text(json.dumps(info, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    if naciones is not None:
        (DESTINO / "naciones.json").write_text(json_lista({}, "naciones", naciones), encoding="utf-8")
    img = np.zeros((ALTO, ANCHO, 3), dtype=np.uint8)
    for p, c in colores.items():
        img[ids == p] = c
    import os
    os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
    import pygame
    pygame.image.save(pygame.surfarray.make_surface(img.swapaxes(0, 1)), str(DESTINO / "provincias.png"))
    (DESTINO / "provincias.json").write_text(
        json_lista({"ancho": ANCHO, "alto": ALTO}, "provincias", provincias), encoding="utf-8")
    (DESTINO / "regiones.json").write_text(json_lista({}, "regiones", regiones), encoding="utf-8")
    print(f"Mapa generado: {len(tierra_p)} provincias de tierra, {len(mar_p)} de mar, "
          f"{len(regiones)} regiones" + (f", {len(naciones)} naciones" if naciones else "") + f" -> {DESTINO}")


if __name__ == "__main__":
    main()
