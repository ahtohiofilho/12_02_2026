# shared/naming/datasets/zh.py
# Pinyin (Mandarim) sem tons, romanizado e "compacto" (sem espaços internos)
#
# Convenções:
# - Todos os tokens são ASCII e sem tons.
# - Sem espaços dentro de um token (ex.: "bandao", "xiagu", "shendian").
# - A gramática fica a cargo do gerador (ex.: "ADJ NOUN" ou "X de Y").

NOUNS = [
    "shan",      # montanha
    "ling",      # cordilheira/serra
    "he",        # rio
    "hu",        # lago
    "hai",       # mar
    "wan",       # baía
    "an",        # costa/escosta de margem (uso livre)
    "dao",       # ilha
    "bandao",    # península
    "gu",        # vale/garganta
    "xiagu",     # desfiladeiro
    "pingyuan",  # planície
    "gaoyuan",   # planalto
    "senlin",    # floresta
    "zhaoze",    # pântano
    "shamo",     # deserto
    "dong",      # caverna
    "qiao",      # ponte
    "lu",        # caminho/estrada
    "guan",      # passagem/forte
    "bao",       # fortaleza
    "cheng",     # cidade
    "cun",       # vila
    "yizhi",     # assentamento
    "shendian",  # templo/santuário (uso livre)
    "feixu",     # ruínas
]

ADJ = [
    "gu",        # antigo
    "xin",       # novo
    "da",        # grande
    "xiao",      # pequeno
    "gao",       # alto
    "shen",      # profundo
    "bei",       # norte
    "nan",       # sul
    "dong",      # leste
    "xi",        # oeste
    "anjing",    # silencioso
    "heian",     # escuro
    "mingliang", # claro/brilhante
    "leng",      # frio
    "re",        # quente
    "wu",        # nebuloso
    "feng",      # ventoso
    "lv",        # verde
    "bai",       # branco
    "hei",       # preto
    "hong",      # vermelho
    "lan",       # azul
    "jin",       # dourado
    "yin",       # prateado
    "shenmi",    # misterioso
    "beiwang",   # esquecido
    "gulao",     # ancestral
    "gudu",      # solitário
]

# Base para o padrão "X de Y" (ex.: "feng de shan", "xue de senlin")
DE_BASE = [
    "wu",    # névoa
    "feng",  # vento
    "xue",   # neve
    "yan",   # fumaça/neblina (uso livre)
    "jin",   # ouro/dourado (base nominal)
    "yin",   # prata/prateado (base nominal)
    "huo",   # fogo
    "yue",   # lua
    "xing",  # estrela
    "hai",   # mar
]
