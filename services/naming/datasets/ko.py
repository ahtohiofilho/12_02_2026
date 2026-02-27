# shared/naming/datasets/ko.py
# Korean (Revised Romanization / RR), sem Hangul
#
# Convenções:
# - Todos os tokens são romanizados em RR e em ASCII.
# - Sem espaços dentro de um token (ex.: "bada", "gowon", "nopeun").
# - O gerador decide a gramática (ex.: "ADJ NOUN" ou "X ui Y").

NOUNS = [
    "san",       # montanha
    "bong",      # pico
    "nyeong",    # passo/montanha (uso livre)
    "gang",      # rio
    "ho",        # lago
    "bada",      # mar
    "man",       # baía/golfo (uso livre)
    "haean",     # costa
    "seom",      # ilha
    "gok",       # vale (uso livre)
    "hyeopgok",  # desfiladeiro
    "pyeongwon", # planície
    "gowon",     # planalto (uso livre)
    "sup",       # floresta
    "neup",      # pântano
    "samak",     # deserto
    "donggul",   # caverna
    "dari",      # ponte
    "gil",       # caminho/estrada
    "gwanmun",   # portão
    "seong",     # fortaleza/castelo
    "tap",       # torre
    "seongsi",   # cidade (uso livre)
    "maeul",     # vila
    "jeon",      # ruína (uso livre)
    "sa",        # templo
    "seongso",   # santuário (uso livre)
]

ADJ = [
    "oraen",      # antigo (≈ 오래된)
    "saeroun",    # novo (≈ 새로운)
    "keun",       # grande
    "jageun",     # pequeno
    "nopeun",     # alto
    "gipeun",     # profundo
    "buk",        # norte (como modificador)
    "nam",        # sul
    "dong",       # leste
    "seo",        # oeste
    "joyonghan",  # silencioso
    "eoduun",     # escuro
    "balkeun",    # claro/brilhante
    "chuun",      # frio
    "tteugeoun",  # quente
    "angaekkijin",# com neblina (uso livre)
    "pureun",     # azul/verde
    "huin",       # branco
    "geomeun",    # preto
    "ppalgan",    # vermelho
    "geumsaek",   # dourado
    "eunsaek",    # prateado
    "sinbiroun",  # misterioso
    "ijeun",      # esquecido (uso livre)
    "honjainneun",# solitário (uso livre)
]

# Base para o padrão "X ui Y" (의 = "de")
UI_BASE = [
    "baram",     # vento
    "angae",     # neblina
    "nun",       # neve
    "bul",       # fogo
    "dal",       # lua
    "byeol",     # estrela
    "bawi",      # pedra
    "geurimja",  # sombra
]
