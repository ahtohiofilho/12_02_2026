# core/generation/_geography.py
from __future__ import annotations

import math
import random
from contextlib import contextmanager
from statistics import mean
from typing import Iterator

import networkx


# CUSTOS BASE
CUSTOS_BASE = {
    "Ice": 32,
    "Mountains": 16,
    "Hills": 8,
    "Forest": 8,
    "Desert": 8,
    "Meadow": 4,
    "Savanna": 4,
    "Coast": 4,
    "Sea": 2,
    "Ocean": 1,
}

PENALIDADE_TRANSICAO = 32

produtividade_base = {
    "Meadow": 6,
    "Forest": 5,
    "Hills": 4,
    "Savanna": 3,
    "Coast": 3,
    "Desert": 2,
    "Sea": 2,
    "Mountains": 1,
    "Ocean": 1,
    "Ice": 0,
}


def seed_from_planet_id(planet_id: str) -> int:
    """
    Converte um UUID (string) em um seed estável (32-bit).
    Para o mesmo planet_id, retorna sempre o mesmo seed.
    """
    return int(planet_id.replace("-", ""), 16) % (2**32)


@contextmanager
def _temporary_random_seed(seed: int) -> Iterator[None]:
    """
    Semeia o RNG global do módulo `random` temporariamente e restaura o estado ao final.

    Por que isso existe:
    - máxima modularidade: não exige passar `rng` para todas as funções internas agora;
    - tudo que usa `random.*` (ou `from random import choice`) dentro do escopo vira determinístico.

    Observações:
    - não cobre numpy.random, secrets, etc.
    - não é thread-safe.
    """
    state = random.getstate()
    random.seed(seed)
    try:
        yield
    finally:
        random.setstate(state)


def letra_grega(placa: str) -> str | None:
    letras_gregas_dict = {
        "Alpha": "Α",
        "Beta": "Β",
        "Gamma": "Γ",
        "Delta": "Δ",
        "Epsilon": "Ε",
        "Zeta": "Ζ",
        "Eta": "Η",
        "Theta": "Θ",
        "Iota": "Ι",
        "Kappa": "Κ",
        "Lambda": "Λ",
        "Mu": "Μ",
        "Nu": "Ν",
        "Xi": "Ξ",
        "Omicron": "Ο",
        "Pi": "Π",
        "Rho": "Ρ",
        "Sigma": "Σ",
        "Tau": "Τ",
        "Upsilon": "Υ",
        "Phi": "Φ",
        "Chi": "Χ",
        "Psi": "Ψ",
        "Omega": "Ω",
    }
    return letras_gregas_dict.get(placa)


def definir_geografia(poligonos, fator: int, bioma: str, *, seed: int | None = None):
    """
    Define geografia (grafo + capitais).

    Se `seed` for fornecida:
    - toda aleatoriedade baseada no módulo `random` dentro desta função torna-se determinística,
      preservando a modularidade (sem refatorar para passar rng por todos os helpers).

    Se `seed` for None:
    - comportamento original (não determinístico).
    """
    if seed is None:
        return _definir_geografia_impl(poligonos, fator, bioma)

    with _temporary_random_seed(int(seed)):
        return _definir_geografia_impl(poligonos, fator, bioma)


def _definir_geografia_impl(poligonos, fator: int, bioma: str):
    # Import local: mantém compatibilidade mesmo que antes você tivesse `from random import choice`
    # e garante que escolha de capitais use o mesmo RNG global já seedado pelo context manager.
    from random import choice

    geografia = networkx.DiGraph()

    for coordenadas in poligonos:
        geografia.add_node(coordenadas)

    def tipo_de_poligono(c):
        if c == (0, 0):
            geografia.nodes[c]["tipo"] = "pn"  # Polar-Norte
            geografia.nodes[c]["formato"] = "pent_up"
            return "pn"
        elif 0 < c[0] < fator and c[1] % c[0] == 0:
            geografia.nodes[c]["tipo"] = "ipn"  # Internodular-Polar-Norte
            geografia.nodes[c]["formato"] = "hex_side"
            return "ipn"
        elif 0 < c[0] < fator and c[1] % c[0] != 0:
            geografia.nodes[c]["tipo"] = "cpn"  # Central-Polar-Norte
            geografia.nodes[c]["formato"] = "hex_up"
            return "cpn"
        elif c[0] == fator and c[1] % c[0] == 0:
            geografia.nodes[c]["tipo"] = "ntn"  # Nodular-Tropical-Norte
            geografia.nodes[c]["formato"] = "pent_down"
            return "ntn"
        elif c[0] == fator and c[1] % c[0] != 0:
            geografia.nodes[c]["tipo"] = "itn"  # Internodular-Tropical-Norte
            geografia.nodes[c]["formato"] = "hex_up"
            return "itn"
        elif fator < c[0] < fator * 2:
            geografia.nodes[c]["tipo"] = "e"  # Equatorial
            geografia.nodes[c]["formato"] = "hex_up"
            return "e"
        elif c[0] == fator * 2 and c[1] % fator != 0:
            geografia.nodes[c]["tipo"] = "its"  # Internodular-Tropical-Sul
            geografia.nodes[c]["formato"] = "hex_up"
            return "its"
        elif c[0] == fator * 2 and c[1] % fator == 0:
            geografia.nodes[c]["tipo"] = "nts"  # Nodular-Tropical-Sul
            geografia.nodes[c]["formato"] = "pent_up"
            return "nts"
        elif fator * 2 < c[0] < fator * 3 and c[1] % (fator * 3 - c[0]) != 0:
            geografia.nodes[c]["tipo"] = "cps"  # Central-Polar-Sul
            geografia.nodes[c]["formato"] = "hex_up"
            return "cps"
        elif fator * 2 < c[0] < fator * 3 and c[1] % (fator * 3 - c[0]) == 0:
            geografia.nodes[c]["tipo"] = "ips"  # Internodular-Polar-Sul
            geografia.nodes[c]["formato"] = "hex_side"
            return "ips"
        elif c[0] == fator * 3:
            geografia.nodes[c]["tipo"] = "ps"  # Polar-Sul
            geografia.nodes[c]["formato"] = "pent_down"
            return "ps"

    for n in list(geografia.nodes):
        no = tipo_de_poligono(n)
        if no == "pn":
            for y in range(5):
                geografia.add_edge(n, (1, y), direcao=f"S{y + 1}")
            continue
        if no == "ps":
            for y in range(5):
                geografia.add_edge(n, (fator * 3 - 1, y), direcao=f"N{y + 1}")
            continue
        x = n[1] // n[0]
        y = n[1] // (fator * 3 - n[0])
        if no == "ipn":
            if n[1] != n[0] * 5 - 1:
                geografia.add_edge(n, (n[0] + 1, n[1] + x), direcao="S")
                geografia.add_edge(n, (n[0] + 1, n[1] + x + 1), direcao="SE")
                geografia.add_edge(n, (n[0], n[1] + 1), direcao="E")
                geografia.add_edge(n, (n[0] - 1, n[1] - x), direcao="N")
                geografia.add_edge(n, (n[0], n[1] - 1), direcao="W") if n[1] != 0 else geografia.add_edge(
                    n, (n[0], n[0] * 5 - 1), direcao="W"
                )
                (
                    geografia.add_edge(n, (n[0] + 1, n[1] + x - 1), direcao="SW")
                    if n[1] != 0
                    else geografia.add_edge(n, (n[0] + 1, (n[0] + 1) * 5 - 1), direcao="SW")
                )
            else:
                geografia.add_edge(n, (n[0] + 1, n[1] + x), direcao="S")
                geografia.add_edge(n, (n[0] + 1, n[1] + x + 1), direcao="SE")
                geografia.add_edge(n, (n[0], 0), direcao="E")
                geografia.add_edge(n, (n[0] - 1, n[1] - x), direcao="N")
                geografia.add_edge(n, (n[0], n[1] - 1), direcao="W")
                geografia.add_edge(n, (n[0] + 1, n[1] + x - 1), direcao="SW")
        elif no == "cpn":
            if n[1] != n[0] * 5 - 1:
                geografia.add_edge(n, (n[0] + 1, n[1] + x + 1), direcao="SE")
                geografia.add_edge(n, (n[0], n[1] + 1), direcao="E")
                geografia.add_edge(n, (n[0] - 1, n[1] - x), direcao="NE")
                geografia.add_edge(n, (n[0] - 1, n[1] - x - 1), direcao="NW")
                geografia.add_edge(n, (n[0], n[1] - 1), direcao="W")
                geografia.add_edge(n, (n[0] + 1, n[1] + x), direcao="SW")
            else:
                geografia.add_edge(n, (n[0] + 1, n[1] + x + 1), direcao="SE")
                geografia.add_edge(n, (n[0], 0), direcao="E")
                geografia.add_edge(n, (n[0] - 1, 0), direcao="NE")
                geografia.add_edge(n, (n[0] - 1, n[1] - x - 1), direcao="NW")
                geografia.add_edge(n, (n[0], n[1] - 1), direcao="W")
                geografia.add_edge(n, (n[0] + 1, n[1] + x), direcao="SW")
        elif no == "ntn":
            geografia.add_edge(n, (n[0] + 1, n[1]), direcao="SW")
            geografia.add_edge(n, (n[0] + 1, n[1] + 1), direcao="SE")
            geografia.add_edge(n, (n[0], n[1] + 1), direcao="E")
            geografia.add_edge(n, (n[0] - 1, n[1] - x), direcao="N")
            geografia.add_edge(n, (n[0], n[1] - 1), direcao="W") if n[1] != 0 else geografia.add_edge(
                n, (n[0], n[0] * 5 - 1), direcao="W"
            )
        elif no == "itn":
            if n[1] != fator * 5 - 1:
                geografia.add_edge(n, (n[0] + 1, n[1]), direcao="SW")
                geografia.add_edge(n, (n[0] + 1, n[1] + 1), direcao="SE")
                geografia.add_edge(n, (n[0], n[1] + 1), direcao="E")
                geografia.add_edge(n, (n[0] - 1, n[1] - x), direcao="NE")
                geografia.add_edge(n, (n[0] - 1, n[1] - x - 1), direcao="NW")
                geografia.add_edge(n, (n[0], n[1] - 1), direcao="W")
            else:
                geografia.add_edge(n, (n[0] + 1, n[1]), direcao="SW")
                geografia.add_edge(n, (n[0] + 1, 0), direcao="SE")
                geografia.add_edge(n, (n[0], 0), direcao="E")
                geografia.add_edge(n, (n[0] - 1, 0), direcao="NE")
                geografia.add_edge(n, (n[0] - 1, n[1] - x - 1), direcao="NW")
                geografia.add_edge(n, (n[0], n[1] - 1), direcao="W")
        elif no == "e":
            if n[1] != fator * 5 - 1:
                geografia.add_edge(n, (n[0] + 1, n[1]), direcao="SW")
                geografia.add_edge(n, (n[0] + 1, n[1] + 1), direcao="SE")
                geografia.add_edge(n, (n[0], n[1] + 1), direcao="E")
                geografia.add_edge(n, (n[0] - 1, n[1]), direcao="NE")
                geografia.add_edge(n, (n[0] - 1, n[1] - 1), direcao="NW") if n[1] != 0 else geografia.add_edge(
                    n, (n[0] - 1, fator * 5 - 1), direcao="NW"
                )
                geografia.add_edge(n, (n[0], n[1] - 1), direcao="W") if n[1] != 0 else geografia.add_edge(
                    n, (n[0], fator * 5 - 1), direcao="W"
                )
            else:
                geografia.add_edge(n, (n[0] + 1, n[1]), direcao="SW")
                geografia.add_edge(n, (n[0] + 1, 0), direcao="SE")
                geografia.add_edge(n, (n[0], 0), direcao="E")
                geografia.add_edge(n, (n[0] - 1, n[1]), direcao="NE")
                geografia.add_edge(n, (n[0] - 1, n[1] - 1), direcao="NW")
                geografia.add_edge(n, (n[0], n[1] - 1), direcao="W")
        elif no == "its":
            if n[1] != fator * 5 - 1:
                geografia.add_edge(n, (n[0] + 1, n[1] - y), direcao="SE")
                geografia.add_edge(n, (n[0], n[1] + 1), direcao="E")
                geografia.add_edge(n, (n[0] - 1, n[1]), direcao="NE")
                geografia.add_edge(n, (n[0] - 1, n[1] - 1), direcao="NW")
                geografia.add_edge(n, (n[0], n[1] - 1), direcao="W")
                geografia.add_edge(n, (n[0] + 1, n[1] - y - 1), direcao="SW")
            else:
                geografia.add_edge(n, (n[0] + 1, 0), direcao="SE")
                geografia.add_edge(n, (n[0], 0), direcao="E")
                geografia.add_edge(n, (n[0] - 1, n[1]), direcao="NE")
                geografia.add_edge(n, (n[0] - 1, n[1] - 1), direcao="NW")
                geografia.add_edge(n, (n[0], n[1] - 1), direcao="W")
                geografia.add_edge(n, (n[0] + 1, n[1] - y - 1), direcao="SW")
        elif no == "nts":
            geografia.add_edge(n, (n[0] + 1, n[1] - y), direcao="S")
            geografia.add_edge(n, (n[0], n[1] + 1), direcao="E")
            geografia.add_edge(n, (n[0] - 1, n[1]), direcao="NE")
            geografia.add_edge(n, (n[0] - 1, n[1] - 1), direcao="NW") if n[1] != 0 else geografia.add_edge(
                n, (n[0] - 1, fator * 5 - 1), direcao="NW"
            )
            geografia.add_edge(n, (n[0], n[1] - 1), direcao="W") if n[1] != 0 else geografia.add_edge(
                n, (n[0], fator * 5 - 1), direcao="W"
            )
        elif no == "cps":
            if n[1] != (fator * 3 - n[0]) * 5 - 1:
                geografia.add_edge(n, (n[0] + 1, n[1] - y), direcao="SE")
                geografia.add_edge(n, (n[0], n[1] + 1), direcao="E")
                geografia.add_edge(n, (n[0] - 1, n[1] + y + 1), direcao="NE")
                geografia.add_edge(n, (n[0] - 1, n[1] + y), direcao="NW")
                geografia.add_edge(n, (n[0], n[1] - 1), direcao="W")
                geografia.add_edge(n, (n[0] + 1, n[1] - y - 1), direcao="SW")
            else:
                geografia.add_edge(n, (n[0] + 1, 0), direcao="SE")
                geografia.add_edge(n, (n[0], 0), direcao="E")
                geografia.add_edge(n, (n[0] - 1, n[1] + y + 1), direcao="NE")
                geografia.add_edge(n, (n[0] - 1, n[1] + y), direcao="NW")
                geografia.add_edge(n, (n[0], n[1] - 1), direcao="W")
                geografia.add_edge(n, (n[0] + 1, n[1] - y - 1), direcao="SW")
        elif no == "ips":
            if n[1] != (fator * 3 - n[0]) * 5 - 1:
                geografia.add_edge(n, (n[0] + 1, n[1] - y), direcao="S")
                geografia.add_edge(n, (n[0], n[1] + 1), direcao="E")
                geografia.add_edge(n, (n[0] - 1, n[1] + y + 1), direcao="NE")
                geografia.add_edge(n, (n[0] - 1, n[1] + y), direcao="N")
                (
                    geografia.add_edge(n, (n[0] - 1, n[1] + y - 1), direcao="NW")
                    if n[1] != 0
                    else geografia.add_edge(n, (n[0] - 1, (fator * 3 - n[0] + 1) * 5 - 1), direcao="NW")
                )
                (
                    geografia.add_edge(n, (n[0], n[1] - 1), direcao="W")
                    if n[1] != 0
                    else geografia.add_edge(n, (n[0], (fator * 3 - n[0]) * 5 - 1), direcao="W")
                )
            else:
                geografia.add_edge(n, (n[0] + 1, n[1] - y), direcao="S")
                geografia.add_edge(n, (n[0], 0), direcao="E")
                geografia.add_edge(n, (n[0] - 1, n[1] + y + 1), direcao="NE")
                geografia.add_edge(n, (n[0] - 1, n[1] + y), direcao="N")
                geografia.add_edge(n, (n[0] - 1, n[1] + y - 1), direcao="NW")
                geografia.add_edge(n, (n[0], n[1] - 1), direcao="W")

    areas = list(poligonos.keys())
    areas_sem_definicao: dict = {}
    areas_definidas: dict = {}
    referencias_relevo = random.sample(areas, fator * 20)

    for area in areas:
        areas_sem_definicao[area] = []
        areas_definidas[area] = []

    for n in range(fator * 3 // 2):
        if not areas_sem_definicao:
            break
        for node in referencias_relevo:
            altitude = random.randint(0, 12)
            areas_definidas[node].append(altitude)
            if node in areas_sem_definicao:
                del areas_sem_definicao[node]
            distancias = networkx.single_source_shortest_path_length(geografia, node)
            nos_a_n_arestas = [node for node, distance in distancias.items() if distance == n + 1]
            for neighbor in nos_a_n_arestas:
                if neighbor in areas_sem_definicao and neighbor not in referencias_relevo:
                    areas_sem_definicao[neighbor].append(altitude)
        for chave in list(areas_sem_definicao.keys()):
            if areas_sem_definicao[chave]:
                areas_definidas[chave].append(round(mean(areas_sem_definicao[chave]), 3))
                del areas_sem_definicao[chave]

    chaves = list(areas_definidas.keys())
    random.shuffle(chaves)
    chaves_ordenadas = sorted(chaves, key=lambda chave: areas_definidas[chave])
    percentual_terra = random.randint(35, 45)
    limite_abissal = (100 - percentual_terra) // 2
    limite_barreira = limite_abissal + (100 - percentual_terra) // 3
    nivel_do_mar = 100 - percentual_terra
    limite_planicie = nivel_do_mar + (100 - nivel_do_mar) * 4 // 6
    limite_planalto = limite_planicie + (100 - limite_planicie) // 2

    for i, chave in enumerate(chaves_ordenadas):
        if i <= len(chaves_ordenadas) * limite_abissal // 100:
            geografia.nodes[chave]["altitude"] = "abissal"
        elif i <= len(chaves_ordenadas) * limite_barreira // 100:
            geografia.nodes[chave]["altitude"] = "barreira"
        elif i <= len(chaves_ordenadas) * nivel_do_mar // 100:
            geografia.nodes[chave]["altitude"] = "plataforma"
        elif i <= len(chaves_ordenadas) * limite_planicie // 100:
            geografia.nodes[chave]["altitude"] = "planicie"
        elif i <= len(chaves_ordenadas) * limite_planalto // 100:
            geografia.nodes[chave]["altitude"] = "planalto"
        else:
            geografia.nodes[chave]["altitude"] = "cordilheira"

    areas_sem_definicao = {}
    areas_definidas = {}
    referencias_umidade = random.sample(areas, 60)

    for area in areas:
        areas_sem_definicao[area] = []
        areas_definidas[area] = []

    for n in range(fator * 3 // 2):
        if not areas_sem_definicao:
            break
        for node in referencias_umidade:
            altitude = random.randint(0, 12)
            areas_definidas[node].append(altitude)
            if node in areas_sem_definicao:
                del areas_sem_definicao[node]
            distancias = networkx.single_source_shortest_path_length(geografia, node)
            nos_a_n_arestas = [node for node, distance in distancias.items() if distance == n + 1]
            for neighbor in nos_a_n_arestas:
                if neighbor in areas_sem_definicao and neighbor not in referencias_umidade:
                    areas_sem_definicao[neighbor].append(altitude)
        for chave in list(areas_sem_definicao.keys()):
            if areas_sem_definicao[chave]:
                areas_definidas[chave].append(round(mean(areas_sem_definicao[chave]), 3))
                del areas_sem_definicao[chave]

    chaves = list(areas_definidas.keys())
    random.shuffle(chaves)
    chaves_ordenadas = sorted(chaves, key=lambda chave: areas_definidas[chave])

    for i, chave in enumerate(chaves_ordenadas):
        if i <= len(chaves_ordenadas) * 25 // 100:
            geografia.nodes[chave]["umidade"] = "arido"
        elif i <= len(chaves_ordenadas) * 50 // 100:
            geografia.nodes[chave]["umidade"] = "semi-arido"
        elif i <= len(chaves_ordenadas) * 75 // 100:
            geografia.nodes[chave]["umidade"] = "fertil"
        else:
            geografia.nodes[chave]["umidade"] = "umido"

    placas = [
        "Alpha",
        "Beta",
        "Gamma",
        "Delta",
        "Epsilon",
        "Zeta",
        "Eta",
        "Theta",
        "Iota",
        "Kappa",
        "Lambda",
        "Mu",
        "Nu",
        "Xi",
        "Omicron",
        "Pi",
        "Rho",
        "Sigma",
        "Tau",
        "Upsilon",
        "Phi",
        "Chi",
        "Psi",
        "Omega",
    ]

    placas_duplicadas = placas * 2
    random.shuffle(placas_duplicadas)
    referencias_geologia = random.sample(areas, 48)

    areas_definidas = {area: None for area in areas}
    for i, node in enumerate(referencias_geologia):
        areas_definidas[node] = placas_duplicadas[i]

    for node in areas_definidas:
        if areas_definidas[node] is not None:
            continue

        distancias = []
        for ref in referencias_geologia:
            try:
                dist = networkx.shortest_path_length(geografia, ref, node)
                distancias.append((ref, dist))
            except networkx.exception.NetworkXNoPath:
                continue

        if not distancias:
            areas_definidas[node] = random.choice(placas)
            continue

        min_dist = min(d[1] for d in distancias)
        candidatos = [d[0] for d in distancias if d[1] == min_dist]
        ref_escolhida = random.choice(candidatos)
        areas_definidas[node] = areas_definidas[ref_escolhida]

    coeficiente_movimento = 1

    cores_placas = []
    for _ in range(24):
        while True:
            r = random.randint(0, 255)
            g = random.randint(0, 255)
            b = random.randint(0, 255)
            if (r + g + b) > 127.5:
                cores_placas.append((r, g, b))
                break

    latitude_equador = fator * 3 / 2

    for chave, valor in areas_definidas.items():
        geografia.nodes[chave]["placa"] = valor
        geografia.nodes[chave]["cor_placa"] = cores_placas[placas.index(valor)]
        geografia.nodes[chave]["letra_grega"] = letra_grega(geografia.nodes[chave]["placa"])
        if chave[0] < latitude_equador:
            distancia_para_equador = latitude_equador - chave[0]
            angulo = distancia_para_equador * 90 / latitude_equador
            incidencia_solar = math.cos(math.radians(angulo))
        elif chave[0] == latitude_equador:
            distancia_para_equador = 0
            angulo = distancia_para_equador * 90 / latitude_equador
            incidencia_solar = math.cos(math.radians(angulo))
        else:
            distancia_para_equador = chave[0] - latitude_equador
            angulo = distancia_para_equador * 90 / latitude_equador
            incidencia_solar = math.cos(math.radians(angulo))

        if geografia.nodes[chave]["altitude"] in ("abissal", "barreira", "plataforma"):
            fator_altitude = 3
        elif geografia.nodes[chave]["altitude"] == "planicie":
            fator_altitude = 1
        elif geografia.nodes[chave]["altitude"] == "planalto":
            fator_altitude = -1
        elif geografia.nodes[chave]["altitude"] == "cordilheira":
            fator_altitude = -3
        else:
            fator_altitude = 0

        if geografia.nodes[chave]["umidade"] == "umido":
            fator_umidade = 1.5
        elif geografia.nodes[chave]["umidade"] == "fertil":
            fator_umidade = 0.5
        elif geografia.nodes[chave]["umidade"] == "semi-arido":
            fator_umidade = -0.5
        elif geografia.nodes[chave]["umidade"] == "arido":
            fator_umidade = -1.5
        else:
            fator_umidade = 0.0

        geografia.nodes[chave]["temperatura"] = round(40 * incidencia_solar - 8 + fator_altitude + fator_umidade, 1) - 4

    for node, atributos in geografia.nodes(data=True):
        temperatura = atributos.get("temperatura")
        altitude = atributos.get("altitude")
        umidade = atributos.get("umidade")

        if temperatura < 0:
            atributos["bioma"] = "Ice"
        else:
            if altitude == "cordilheira":
                atributos["bioma"] = "Mountains"
            elif altitude == "planalto":
                atributos["bioma"] = "Hills"
            elif altitude == "planicie":
                if umidade == "umido":
                    atributos["bioma"] = "Forest"
                elif umidade == "fertil":
                    atributos["bioma"] = "Meadow"
                elif umidade == "semi-arido":
                    atributos["bioma"] = "Savanna"
                else:
                    atributos["bioma"] = "Desert"
            elif altitude == "plataforma":
                atributos["bioma"] = "Coast"
            elif altitude == "barreira":
                atributos["bioma"] = "Sea"
            else:
                atributos["bioma"] = "Ocean"

        atributos["cust_mob"] = CUSTOS_BASE[atributos["bioma"]] * coeficiente_movimento

    def calcular_produtividade_agricola_ponderada(node, grafo_geografia):
        bioma_atual = grafo_geografia.nodes[node]["bioma"]
        prod_base_atual = produtividade_base[bioma_atual]

        vizinhos = list(grafo_geografia.neighbors(node))
        biomas_vizinhos = [grafo_geografia.nodes[v]["bioma"] for v in vizinhos]
        prods_base_vizinhos = [produtividade_base[b] for b in biomas_vizinhos]

        num_lados = len(vizinhos)

        if num_lados == 5:
            soma_ponderada = (prod_base_atual * 5) + sum(prods_base_vizinhos)
            divisor = 10
        elif num_lados == 6:
            soma_ponderada = (prod_base_atual * 6) + sum(prods_base_vizinhos)
            divisor = 12
        else:
            print(f"[CalcularProd] Aviso: Tile {node} tem {num_lados} lados. Usando média simples como fallback.")
            soma_ponderada = prod_base_atual + sum(prods_base_vizinhos)
            divisor = 1 + len(prods_base_vizinhos)

        return soma_ponderada / divisor if divisor != 0 else 0

    for node, atributos in geografia.nodes(data=True):
        fertilidade = calcular_produtividade_agricola_ponderada(node, geografia)
        geografia.nodes[node]["fertilidade"] = fertilidade

    for u, v in geografia.edges():
        mob_u = geografia.nodes[u]["cust_mob"]
        mob_v = geografia.nodes[v]["cust_mob"]

        u_maritimo = geografia.nodes[u]["bioma"] in ["Coast", "Sea", "Ocean"]
        v_maritimo = geografia.nodes[v]["bioma"] in ["Coast", "Sea", "Ocean"]

        if u_maritimo != v_maritimo:
            geografia[u][v]["cust_mob"] = (mob_u + mob_v) / 2 + PENALIDADE_TRANSICAO * coeficiente_movimento
        else:
            geografia[u][v]["cust_mob"] = (mob_u + mob_v) / 2

    bioma_escolhido = [n for n, attr in geografia.nodes(data=True) if attr["bioma"] == f"{bioma}"]

    bioma_escolhido_filtrado = []
    for node in bioma_escolhido:
        prod_calc = calcular_produtividade_agricola_ponderada(node, geografia)
        if prod_calc > 1.0:
            bioma_escolhido_filtrado.append(node)

    bioma_escolhido = bioma_escolhido_filtrado

    if not bioma_escolhido:
        raise ValueError(
            "Nenhum tile do bioma especificado tem produtividade agrícola ponderada > 1. "
            "Impossível selecionar capitais iniciais."
        )

    # Seleção de capitais: agora determinística sob seed (via random.choice seedado no context manager)
    lista_capitais = [choice(bioma_escolhido)]
    while len(lista_capitais) < len(bioma_escolhido) // 2:
        d2 = {}
        for candidato in bioma_escolhido:
            if candidato in lista_capitais:
                continue
            d = {}
            for capital in lista_capitais:
                # IMPORTANTE: seu grafo usa 'cust_mob' nas arestas.
                d[capital] = networkx.shortest_path_length(
                    geografia,
                    source=candidato,
                    target=capital,
                    weight="cust_mob",
                )
            d2[candidato] = min(d.values())

        if not d2:
            print("d2 vazio após filtragem por produtividade")
            raise ValueError(
                "O planeta não comporta essa quantidade de civilizações mesmo após filtragem por produtividade!"
            )

        maior_valor = max(d2.values())
        chaves_maior_valor = [chave for chave, valor in d2.items() if valor == maior_valor]
        lista_capitais.append(choice(chaves_maior_valor))

    print(f"Número de {bioma} com prod > 1 selecionados como candidatos iniciais:", len(bioma_escolhido))
    return geografia, lista_capitais
