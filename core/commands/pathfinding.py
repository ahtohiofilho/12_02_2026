# core/commands/pathfinding.py
from __future__ import annotations

import networkx as nx
from typing import Optional

from config.gameplay import ALLOWED_BIOMES_PER_CATEGORY
from config.unit_stats import get_unit_stats, UnitCategory
from config.movement_costs import (
    get_entry_cost,
    get_stack_entry_cost,
    get_unit_domain,
)

Tile = tuple[int, int]


# ──────────────────────────────────────────────
# Budget por domínio (custo acumulado máximo por turno)
# ──────────────────────────────────────────────
DOMAIN_BUDGET: dict[str, int] = {
    "land":  12,
    "naval": 12,
    "air":   20,
}


# ──────────────────────────────────────────────
# Helpers públicos
# ──────────────────────────────────────────────
def allowed_biomes_for_stack(
    graph: nx.DiGraph,
    stack,
    stacks_repo=None,
) -> set[str]:
    """
    Biomas permitidos = interseção dos biomas de TODAS as unidades da stack.
    (A unidade mais restrita limita.)
    """
    if not stack or not stack.units:
        return set()

    result: set[str] | None = None

    for unit in stack.units:
        stats = get_unit_stats(unit.unit_key)
        if stats is None:
            continue

        cat_name = stats.category.name.lower()  # "land", "naval", "air"
        biomes = set(ALLOWED_BIOMES_PER_CATEGORY.get(cat_name, []))

        if result is None:
            result = biomes.copy()
        else:
            result &= biomes

    return result or set()


def movement_budget_for_stack(stack) -> int:
    """
    Budget de custo acumulado por turno para a stack.
    Baseado no domínio da unidade mais restritiva.
    """
    if not stack or not stack.units:
        return 0

    domain = get_unit_domain(stack.units[0].unit_key)
    return DOMAIN_BUDGET.get(domain, 12)


def max_movement_for_stack(stack) -> int:
    """Mantido para compatibilidade — retorna stats.movement mínimo."""
    if not stack or not stack.units:
        return 0

    min_mov = 999
    for unit in stack.units:
        stats = get_unit_stats(unit.unit_key)
        if stats:
            min_mov = min(min_mov, stats.movement)

    return min_mov if min_mov < 999 else 0


# ──────────────────────────────────────────────
# Weight function factory (para NetworkX)
# ──────────────────────────────────────────────
def _make_weight_fn(
    graph: nx.DiGraph,
    unit_keys: list[str],
    allowed_biomes: set[str] | None,
):
    """
    Retorna uma função de peso compatível com nx.shortest_path(weight=fn).

    A função recebe (u, v, edge_data) e retorna o custo de ENTRAR em v
    considerando todas as unidades da stack.
    Se v for inacessível → retorna None (NetworkX ignora a aresta).
    """
    def weight_fn(u, v, edge_data):
        biome = graph.nodes[v].get("bioma", "Meadow")

        # Filtro de biomas permitidos
        if allowed_biomes is not None and biome not in allowed_biomes:
            return None

        cost = get_stack_entry_cost(unit_keys, biome)
        if cost is None:
            return None  # bioma inacessível para alguma unidade

        return cost

    return weight_fn


# ──────────────────────────────────────────────
# Pathfinding principal
# ──────────────────────────────────────────────
def find_path(
    graph: nx.DiGraph,
    origin: Tile,
    destination: Tile,
    *,
    movement_points: int | None = None,
    allowed_biomes: set[str] | None = None,
    unit_keys: list[str] | None = None,
    weight: str = "cust_mob",
) -> Optional[list[Tile]]:
    """
    Dijkstra entre origin e destination com custos variáveis por unidade×bioma.

    Args:
        graph:            NetworkX DiGraph do planeta
        origin:           tile de origem
        destination:      tile de destino
        movement_points:  budget máximo de custo acumulado (None = sem limite)
        allowed_biomes:   biomas permitidos para filtragem
        unit_keys:        lista de unit_keys da stack (ativa custos variáveis)
        weight:           fallback — nome do atributo de aresta (usado se unit_keys=None)

    Returns:
        Lista de tiles [origin, ..., destination] ou None se impossível.
    """
    if origin == destination:
        return [origin]

    if origin not in graph or destination not in graph:
        return None

    # ── Modo com custos variáveis (unit_keys fornecido) ──
    if unit_keys:
        w_fn = _make_weight_fn(graph, unit_keys, allowed_biomes)

        try:
            cost, path = nx.single_source_dijkstra(
                graph, origin, destination, weight=w_fn,
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

        # Validar budget
        if movement_points is not None and cost > movement_points:
            return None

        return list(path)

    # ── Modo legado (peso fixo nas arestas) ──
    try:
        path = nx.shortest_path(graph, origin, destination, weight=weight)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None

    # Filtrar por biomas permitidos
    if allowed_biomes is not None:
        for tile in path[1:]:
            biome = graph.nodes.get(tile, {}).get("bioma", "")
            if biome not in allowed_biomes:
                return None

    # Validar range total
    if movement_points is not None:
        total_cost = 0.0
        for i in range(len(path) - 1):
            edge_data = graph.get_edge_data(path[i], path[i + 1])
            if edge_data is None:
                return None
            total_cost += float(edge_data.get(weight, 1.0))
        if total_cost > movement_points:
            return None

    return list(path)


def get_reachable_tiles(
    graph: nx.DiGraph,
    origin: Tile,
    movement_points: int,
    *,
    allowed_biomes: set[str] | None = None,
    unit_keys: list[str] | None = None,
    weight: str = "cust_mob",
) -> dict[Tile, float]:
    """
    Retorna todos os tiles alcançáveis a partir de `origin`
    com até `movement_points` de custo acumulado.

    Returns:
        dict[Tile, custo_acumulado]
    """
    if movement_points <= 0:
        return {}

    # ── Modo com custos variáveis ──
    if unit_keys:
        w_fn = _make_weight_fn(graph, unit_keys, allowed_biomes)

        try:
            lengths = nx.single_source_dijkstra_path_length(
                graph, origin, cutoff=movement_points, weight=w_fn,
            )
        except nx.NodeNotFound:
            return {}

        return {
            tile: float(cost)
            for tile, cost in lengths.items()
            if tile != origin
        }

    # ── Modo legado ──
    try:
        lengths = nx.single_source_dijkstra_path_length(
            graph, origin, cutoff=movement_points, weight=weight,
        )
    except nx.NodeNotFound:
        return {}

    reachable: dict[Tile, float] = {}
    for tile, cost in lengths.items():
        if tile == origin:
            continue
        if allowed_biomes is not None:
            biome = graph.nodes.get(tile, {}).get("bioma", "")
            if biome not in allowed_biomes:
                continue
        reachable[tile] = float(cost)

    return reachable
