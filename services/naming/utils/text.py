# services/naming/utils/text.py
from __future__ import annotations

import re
import unicodedata

ASCII_MAX = 127

# Conectores que ficam em minúsculo no Title Case (exceto se forem o 1º token)
_TITLECASE_KEEP_LOWER = {
    # pt
    "da", "das", "de", "do", "dos", "e",
    # en
    "a", "an", "and", "of", "the",
    # fr/it/es (mínimo útil)
    "d", "de", "del", "des", "du", "la", "le", "les", "di", "da", "do",
    "y", "e",
    # ar/fa
    "al", "el", "ye",
    # de
    "von", "und", "der", "die", "das", "zu",
    # outros conectores que você já usa
    "no", "ui",
}

# Token "palavra" Unicode:
# - [^\W_] = "qualquer char de palavra exceto underscore" (unicode-aware)
# - permite hífen/apóstrofo dentro do token: foo-bar, d'Azur
_WORD_RE = re.compile(r"[^\W_]+(?:[-'][^\W_]+)*", flags=re.UNICODE)

# Mapa “ocidental amigável”:
# - remove letras latinas “raras/estranhas” (como Đ) sem destruir acentos comuns (á, ç, ü, ö...)
# - objetivo: manter leitura confortável para público ocidental médio
_WESTERN_MAP: dict[str, str] = {
    # Vietnamese
    "Đ": "D",
    "đ": "d",
    # Germanic / Nordic / Slavic Latin (alguns)
    "ß": "ss",
    "Ø": "O",
    "ø": "o",
    "Ł": "L",
    "ł": "l",
    "Þ": "Th",
    "þ": "th",
    "Æ": "Ae",
    "æ": "ae",
    "Œ": "Oe",
    "œ": "oe",
}


def clean_spaces(s: str) -> str:
    return re.sub(r"\s+", " ", s).strip()


# ---------------------------------------------------------------------
# Sanitização de texto (3 níveis úteis)
# ---------------------------------------------------------------------

def strip_combining_marks(s: str) -> str:
    """
    Remove marcas combinantes (acentos/diacríticos do tipo Mn).
    Ex.: "á" (a+´) -> "a", "ç" (c+¸) -> "c" quando decomposto.
    """
    s = unicodedata.normalize("NFD", s)
    return "".join(ch for ch in s if unicodedata.category(ch) != "Mn")


def to_ascii(s: str) -> str:
    """
    Compatibilidade legada:
    - remove SOMENTE marcas combinantes (Mn).
    - NÃO garante ASCII puro (0..127). Ex.: 'Đ' permanece.
    Use `to_ascii_strict` se você realmente precisa ASCII puro.
    """
    return strip_combining_marks(s)


def to_western_friendly(s: str) -> str:
    """
    Padrão recomendado para “agradável aos olhos ocidentais”:
    - mantém acentos comuns (á, é, ç, ñ, ü, ö, â, etc.)
    - mas substitui letras latinas “raras”/visualmente estranhas no ocidente (ex.: Đ/đ)
    """
    for a, b in _WESTERN_MAP.items():
        s = s.replace(a, b)
    return s


def to_ascii_strict(s: str) -> str:
    """
    ASCII PURO (0..127), sem exceções:
    - remove marcas combinantes
    - aplica mapeamento ocidental (ex.: Đ->D, ß->ss)
    - remove qualquer caractere restante fora de ASCII (0..127)

    Útil para:
      - export/serialization legada
      - fontes/engines que quebram com Unicode
      - testes que exigem ASCII “de verdade”
    """
    s = strip_combining_marks(s)
    for a, b in _WESTERN_MAP.items():
        s = s.replace(a, b)
    return "".join(ch for ch in s if ord(ch) <= ASCII_MAX)


# ---------------------------------------------------------------------
# Title Case Unicode (mantém compatibilidade com diacríticos)
# ---------------------------------------------------------------------

def title_words(s: str, keep_lower: set[str] | None = None) -> str:
    """
    Title Case Unicode para nomes romanizados:
    - Tokeniza com Unicode (não quebra ş/ı/Đ/ß/Ø etc.)
    - Conectores em minúsculo quando não são o 1º token
    - Hífen: capitaliza o segmento seguinte, exceto conectores
    - Apóstrofo: NÃO capitaliza o segmento seguinte (mantém lower)

    keep_lower:
      - None -> usa _TITLECASE_KEEP_LOWER (compatível com o comportamento atual)
      - set  -> usa este conjunto de tokens (em lowercase) que devem ficar minúsculos
    """
    keep = _TITLECASE_KEEP_LOWER if keep_lower is None else keep_lower

    def cap1(seg: str) -> str:
        return seg[:1].upper() + seg[1:] if seg else seg

    def fix_token(tok: str, is_first: bool) -> str:
        low = tok.lower()
        if (not is_first) and (low in keep):
            return low

        if "-" not in tok and "'" not in tok:
            return cap1(tok)

        parts = re.split(r"([-'])", tok)
        if not parts:
            return tok

        parts[0] = cap1(parts[0])

        i = 1
        while i < len(parts) - 1:
            sep = parts[i]
            seg = parts[i + 1]
            seg_low = seg.lower()

            if sep == "-":
                parts[i + 1] = seg_low if seg_low in keep else cap1(seg)
            else:  # "'"
                parts[i + 1] = seg_low

            i += 2

        return "".join(parts)

    out: list[str] = []
    last_end = 0
    token_index = 0

    for m in _WORD_RE.finditer(s):
        out.append(s[last_end:m.start()])
        out.append(fix_token(m.group(0), is_first=(token_index == 0)))
        last_end = m.end()
        token_index += 1

    out.append(s[last_end:])
    return "".join(out)