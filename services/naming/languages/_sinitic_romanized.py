from __future__ import annotations

from ..types import NamingContext
from ..utils.rng import rng_from_seed, choice, wchoice
from ..utils.text import clean_spaces, title_words, to_ascii


# ---------------------------------------------------------------------
# Wu: compactação seletiva (somente compostos geográficos muito comuns)
# ---------------------------------------------------------------------

# Whitelist de compostos (2 ou 3 tokens) que devem ser “colados” no Wu.
# Mantém o restante com espaços, melhorando legibilidade no mapa.
_WU_COMMON_COMPOUNDS: dict[tuple[str, ...], str] = {
    # Landforms comuns (pinyin-ish)
    ("gao", "yuan"): "gaoyuan",     # 高原
    ("ping", "yuan"): "pingyuan",   # 平原
    ("pen", "di"): "pendi",         # 盆地
    ("gu", "di"): "gudi",           # 谷地 (uso estilizado)
    ("shi", "lin"): "shilin",       # 石林

    # Hidro/coast comuns (inclua se você usar esses tokens com espaço)
    ("hai", "an"): "haian",         # 海岸
    ("he", "kou"): "hekou",         # 河口
    ("shui", "kou"): "shuikou",     # 水口
}


def _compact_common_compounds(tokens: list[str]) -> list[str]:
    """
    Compacta apenas compostos (2 ou 3 tokens) presentes na whitelist.
    Ex.: ["Gao","yuan","sheng"] -> ["gaoyuan","sheng"] (depois Title Case).
    """
    out: list[str] = []
    i = 0

    while i < len(tokens):
        # tenta trigram primeiro (se existir no mapa)
        if i + 3 <= len(tokens):
            tri = tuple(t.lower() for t in tokens[i : i + 3])
            repl = _WU_COMMON_COMPOUNDS.get(tri)
            if repl:
                out.append(repl)
                i += 3
                continue

        # tenta bigram
        if i + 2 <= len(tokens):
            bi = tuple(t.lower() for t in tokens[i : i + 2])
            repl = _WU_COMMON_COMPOUNDS.get(bi)
            if repl:
                out.append(repl)
                i += 2
                continue

        out.append(tokens[i])
        i += 1

    return out


class SiniticRomanizedGenerator:
    """
    Gerador toponímico rico para línguas siníticas em romanização (ASCII).

    Look "mapa ocidental":
      - Title Case em tudo.
      - Yue/Min: usa ESPAÇOS (sem hífens).
      - Wu: mantém espaços, mas compacta SOMENTE compostos geo muito comuns + ADMIN separado.
      - ADMIN permanece romanizado (dialetal), mas em Title Case na exibição.

    Dataset esperado:
      - ADJ_COMMON, ADJ_FANTASY (listas)
      - NOUN_NATURE, NOUN_WATER, NOUN_LAND, NOUN_CIVIL (listas)
      - ADMIN (lista)  # também romanizado
      - CORE (opcional)
    """

    def __init__(self, *, culture: str, dataset):
        self.culture = culture
        self.ds = dataset

    def _format_name(self, raw: str, ctx: NamingContext, admin_tokens: list[str]) -> str:
        raw = clean_spaces(raw)

        parts = raw.split()
        admin = ""
        if parts and parts[-1] in admin_tokens:
            admin = parts[-1]
            base = " ".join(parts[:-1])
        else:
            base = raw

        if getattr(ctx, "ascii_only", False):
            base = to_ascii(base)
            admin = to_ascii(admin)

        culture = (self.culture or "").lower()

        # Wu: compacta apenas compostos conhecidos; mantém resto com espaços.
        if culture == "wu":
            base_tokens = base.split()
            base_tokens = _compact_common_compounds(base_tokens)
            base_fmt = " ".join(base_tokens)
            out = f"{base_fmt} {admin}".strip()
            return title_words(out) if getattr(ctx, "capitalizar", False) else out

        # Yue/Min (e demais siníticos romanizados): mantém espaços
        out = f"{base} {admin}".strip()
        return title_words(out) if getattr(ctx, "capitalizar", False) else out

    def province(self, ctx: NamingContext | None = None) -> str:
        ctx = ctx or NamingContext()
        rng = rng_from_seed(ctx.seed)
        ds = self.ds

        adj = (ds.ADJ_COMMON + ds.ADJ_FANTASY)
        nature = ds.NOUN_NATURE
        water = ds.NOUN_WATER
        land = ds.NOUN_LAND
        civil = ds.NOUN_CIVIL
        admin = ds.ADMIN
        core = getattr(ds, "CORE", [])

        pattern = wchoice(
            rng,
            [
                "ADJ_LAND",
                "ADJ_WATER",
                "LAND_ADMIN",
                "WATER_ADMIN",
                "CIVIL_ADMIN",
                "ADJ_CIVIL",
                "LAND_CIVIL",
                "WATER_CIVIL",
                "ADJ_LAND_ADMIN",
                "ADJ_WATER_ADMIN",
                "CORE_LAND",
                "CORE_WATER",
                "ADJ_CORE_LAND",
                "ADJ_CORE_WATER",
                "LAND_LAND",
                "WATER_WATER",
            ],
            [12, 10, 7, 7, 6, 10, 8, 8, 6, 6, 4, 4, 4, 4, 2, 2],
        )

        def pick(lst: list[str]) -> str:
            return choice(rng, lst) if lst else ""

        if pattern == "ADJ_LAND":
            name = f"{pick(adj)} {pick(land)}"
        elif pattern == "ADJ_WATER":
            name = f"{pick(adj)} {pick(water)}"
        elif pattern == "LAND_ADMIN":
            name = f"{pick(land)} {pick(admin)}"
        elif pattern == "WATER_ADMIN":
            name = f"{pick(water)} {pick(admin)}"
        elif pattern == "CIVIL_ADMIN":
            name = f"{pick(civil)} {pick(admin)}"
        elif pattern == "ADJ_CIVIL":
            name = f"{pick(adj)} {pick(civil)}"
        elif pattern == "LAND_CIVIL":
            name = f"{pick(land)} {pick(civil)}"
        elif pattern == "WATER_CIVIL":
            name = f"{pick(water)} {pick(civil)}"
        elif pattern == "ADJ_LAND_ADMIN":
            name = f"{pick(adj)} {pick(land)} {pick(admin)}"
        elif pattern == "ADJ_WATER_ADMIN":
            name = f"{pick(adj)} {pick(water)} {pick(admin)}"
        elif pattern == "CORE_LAND":
            name = f"{pick(core)} {pick(land)}" if core else f"{pick(adj)} {pick(land)}"
        elif pattern == "CORE_WATER":
            name = f"{pick(core)} {pick(water)}" if core else f"{pick(adj)} {pick(water)}"
        elif pattern == "ADJ_CORE_LAND":
            name = f"{pick(adj)} {pick(core)} {pick(land)}" if core else f"{pick(adj)} {pick(land)}"
        elif pattern == "ADJ_CORE_WATER":
            name = f"{pick(adj)} {pick(core)} {pick(water)}" if core else f"{pick(adj)} {pick(water)}"
        elif pattern == "LAND_LAND":
            name = f"{pick(land)} {pick(nature)}"
        else:  # WATER_WATER
            name = f"{pick(water)} {pick(nature)}"

        return self._format_name(name, ctx, admin_tokens=admin)
