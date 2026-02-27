# shared/naming/datasets/fa.py
# Romanização simples + Ezafe (será aplicado na geração)

NOUNS = [
    # Relevo / natureza
    "Kuh",          # montanha
    "Kuhestan",     # região montanhosa
    "Tappeh",       # colina
    "Daman",        # encosta
    "Darreh",       # vale
    "Tang",         # desfiladeiro estreito
    "Kanon",        # cânion (empréstimo)
    "Sang",         # rocha/pedra
    "Sangestan",    # terreno pedregoso
    "Cheshmeh",     # nascente/fonte
    "Abshar",       # cachoeira
    "Ghar",         # caverna
    "Gonbad",       # domo/cúpula

    # Água / litoral
    "Rud",          # rio
    "Juy",          # córrego/canal
    "Darya",        # mar
    "Daryacheh",    # lago
    "Howz",         # lagoa/tanque
    "Khalij",       # golfo/baía
    "Sahil",        # costa
    "Bandar",       # porto
    "Jazireh",      # ilha
    "Ras",          # cabo/promontório

    # Terras / biomas
    "Dasht",        # planície
    "Sahra",        # deserto
    "Biyaban",      # ermo/deserto
    "Jangal",       # floresta
    "Bagh",         # jardim/pomar
    "Golestan",     # jardim de flores (topônimo comum)
    "Margzar",      # pradaria/pasto
    "Neyzar",       # juncal/caniçal

    # Construções / lugares
    "Pol",          # ponte
    "Rah",          # caminho/rota
    "Rahgozar",     # passagem
    "Dargah",       # portal/entrada
    "Darvazeh",     # portão
    "Qaleh",        # fortaleza (sem apóstrofo pra simplificar)
    "Borj",         # torre
    "Hisar",        # fortificação/muralha
    "Karvansara",   # caravançará
    "Bazaar",       # mercado
    "Shahr",        # cidade
    "Deh",          # vila
    "Kuy",          # bairro/quarter

    # Sagrado / ruínas
    "Atashkadeh",   # templo do fogo
    "Ziaratgah",    # santuário
    "Aramgah",      # mausoléu/túmulo
    "Kharabeh",     # ruína
]

ADJ = [
    # Tempo / estado
    "Ghadimi", "Jadid",
    "Kohan",          # antigo
    "Viraneh",        # arruinado
    "Abad",           # próspero/habitado

    # Tamanho / forma
    "Bozorg", "Kuchak",
    "Boland",         # alto
    "Kotah",          # baixo/curto
    "Pahn",           # largo
    "Tang",           # estreito

    # Posição / direção
    "Bala", "Payin",
    "Shomali", "Jonubi", "Sharghi", "Gharbi",
    "Markazi",

    # Atmosfera / qualidade
    "Aram",           # calmo
    "Porseda",        # barulhento
    "Tarik", "Roshan",
    "Mahv",           # apagado/vago
    "Makhfi",         # escondido

    # Clima / natureza
    "Sard", "Garm",
    "Khoshk",         # seco
    "Namnak",         # úmido
    "Badkhiz",        # ventoso
    "Sookhteh",       # queimado
    "Yakhzadeh",      # gelado

    # Cores / materiais
    "Sabz", "Sorkh", "Sefid", "Siah", "Abi",
    "Zard",
    "Nili",
    "Zarrin",
    "Simini",
    "Ahani",

    # Fantasia / místico
    "Moqaddas",       # sagrado
    "Malun",          # amaldiçoado (sem apóstrofo)
    "Gomshodeh",      # perdido
    "Faramoosh Shodeh",  # esquecido (2 tokens)
    "Razalud",        # misterioso
    "Tanha",          # solitário
]
