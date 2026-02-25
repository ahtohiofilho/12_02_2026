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
# Budget por turno (em "turnos-custo")
# ──────────────────────────────────────────────
TURN_BUDGET: int = 1


# ──────────────────────────────────────────────
# Helpers públicos
# ──────────────────────────────────────────────
def allowed_biomes_for_stack(
    graph: nx.DiGraph,
    stack,
    stacks_repo=None,
) -> set[str]:
    if not stack or not stack.units:
        return set()

    result: set[str] | None = None

    for unit in stack.units:
        stats = get_unit_stats(unit.unit_key)
        if stats is None:
            continue

        cat_name = stats.category.name.lower()
        biomes = set(ALLOWED_BIOMES_PER_CATEGORY.get(cat_name, []))

        if result is None:
            result = biomes.copy()
        else:
            result &= biomes

    return result or set()


def movement_budget_for_stack(stack) -> int:
    return TURN_BUDGET


def tiles_reachable_this_turn(
    graph: nx.DiGraph,
    origin: Tile,
    path: list[Tile],
    unit_keys: list[str],
    allowed_biomes: set[str] | None = None,
    budget: int = TURN_BUDGET,
) -> int:
    if not path or len(path) < 2:
        return 0

    spent = 0
    last_reachable = 0

    for i in range(1, len(path)):
        tile = path[i]
        biome = graph.nodes[tile].get("bioma", "Meadow") if tile in graph else "Meadow"

        if allowed_biomes is not None and biome not in allowed_biomes:
            break

        cost = get_stack_entry_cost(unit_keys, biome)
        if cost is None:
            break

        spent += cost
        if spent <= budget:
            last_reachable = i
        else:
            break

    return last_reachable


def max_movement_for_stack(stack) -> int:
    if not stack or not stack.units:
        return 0

    min_mov = 999
    for unit in stack.units:
        stats = get_unit_stats(unit.unit_key)
        if stats:
            min_mov = min(min_mov, stats.movement)

    return min_mov if min_mov < 999 else 0


# ──────────────────────────────────────────────
# Tile passability helper
# ──────────────────────────────────────────────
def _build_passable_set(
    planet,
    owner_id: int,
) -> set[Tile] | None:
    """
    Retorna o conjunto de tiles por onde a civ `owner_id` pode passar:
      - Tiles sem dono (sem província)
      - Tiles da própria civ
      - Tiles de civs ALIADAS

    Retorna None se planet não foi fornecido (desabilita filtro).
    """
    if planet is None:
        return None

    from core.diplomacy import Relation

    passable: set[Tile] = set()

    all_tiles = set(planet.graph.nodes)
    owned_tiles = set(planet.provinces_by_tile.keys())

    # Tiles sem dono → sempre passáveis
    passable |= (all_tiles - owned_tiles)

    # Tiles com dono → só se for aliado ou próprio
    for tile, province in planet.provinces_by_tile.items():
        if province.owner is None:
            passable.add(tile)
            continue

        tile_owner_id = province.owner.id

        if tile_owner_id == owner_id:
            passable.add(tile)
            continue

        rel = planet.diplomacy.relation(owner_id, tile_owner_id)
        if rel == Relation.ALLY:
            passable.add(tile)

    return passable


# ──────────────────────────────────────────────
# Weight function factory (para NetworkX)
# ──────────────────────────────────────────────
def _make_weight_fn(
    graph: nx.DiGraph,
    unit_keys: list[str],
    allowed_biomes: set[str] | None,
    passable_tiles: set[Tile] | None = None,
):
    """
    Retorna uma função de peso compatível com nx.shortest_path(weight=fn).

    Agora também verifica se o tile de destino é passável (território
    próprio, aliado ou sem dono).
    """
    def weight_fn(u, v, edge_data):
        # ── Filtro de território ──
        if passable_tiles is not None and v not in passable_tiles:
            return None

        biome = graph.nodes[v].get("bioma", "Meadow")

        if allowed_biomes is not None and biome not in allowed_biomes:
            return None

        cost = get_stack_entry_cost(unit_keys, biome)
        if cost is None:
            return None

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
    planet=None,
    owner_id: int | None = None,
) -> Optional[list[Tile]]:
    """
    Dijkstra entre origin e destination com custos variáveis por unidade×bioma.

    Args:
        graph:            NetworkX DiGraph do planeta
        origin:           tile de origem
        destination:      tile de destino
        movement_points:  custo máximo total permitido (None = sem limite)
        allowed_biomes:   biomas permitidos para filtragem
        unit_keys:        lista de unit_keys da stack (ativa custos variáveis)
        weight:           fallback — nome do atributo de aresta (usado se unit_keys=None)
        planet:           instância do Planet (para filtro de território)
        owner_id:         id da civ dona da stack (para filtro de território)

    Returns:
        Lista de tiles [origin, ..., destination] ou None se impossível.
    """
    if origin == destination:
        return [origin]

    if origin not in graph or destination not in graph:
        return None

    # ── Constrói conjunto de tiles passáveis ──
    passable_tiles = None
    if planet is not None and owner_id is not None:
        passable_tiles = _build_passable_set(planet, owner_id)

        # Destino bloqueado → sem rota (evita cálculo desnecessário)
        if passable_tiles is not None and destination not in passable_tiles:
            return None

    # ── Modo com custos variáveis (unit_keys fornecido) ──
    if unit_keys:
        w_fn = _make_weight_fn(graph, unit_keys, allowed_biomes, passable_tiles)

        try:
            cost, path = nx.single_source_dijkstra(
                graph, origin, destination, weight=w_fn,
            )
        except (nx.NetworkXNoPath, nx.NodeNotFound):
            return None

        if movement_points is not None and cost > movement_points:
            return None

        return list(path)

    # ── Modo legado (peso fixo nas arestas) ──
    try:
        path = nx.shortest_path(graph, origin, destination, weight=weight)
    except (nx.NetworkXNoPath, nx.NodeNotFound):
        return None

    if allowed_biomes is not None:
        for tile in path[1:]:
            biome = graph.nodes.get(tile, {}).get("bioma", "")
            if biome not in allowed_biomes:
                return None

    # ── Filtro de território no modo legado ──
    if passable_tiles is not None:
        for tile in path[1:]:
            if tile not in passable_tiles:
                return None

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
    planet=None,
    owner_id: int | None = None,
) -> dict[Tile, float]:
    """
    Retorna todos os tiles alcançáveis a partir de `origin`
    com até `movement_points` de custo acumulado.
    """
    if movement_points <= 0:
        return {}

    passable_tiles = None
    if planet is not None and owner_id is not None:
        passable_tiles = _build_passable_set(planet, owner_id)

    if unit_keys:
        w_fn = _make_weight_fn(graph, unit_keys, allowed_biomes, passable_tiles)

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
        # ── Filtro de território ──
        if passable_tiles is not None and tile not in passable_tiles:
            continue
        reachable[tile] = float(cost)

    return reachable
