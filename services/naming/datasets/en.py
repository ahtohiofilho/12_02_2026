# shared/naming/datasets/en.py
# Dataset “toponímico” (fantasia-realista) para nomes em inglês.
# Objetivo: boa variedade, combinações naturais, pouco “nonsense”.

ADJ_COMMON = [
    "Old","New","High","Low","Upper","Lower","North","South","East","West",
    "Great","Grand","Lesser","Outer","Inner","Far","Near",
    "Long","Wide","Narrow","Broad",
    "Deep","Shallow","Hollow","Hidden","Open","Closed",
    "Quiet","Still","Silent","Loud",
    "Bright","Dim","Dark","Pale",
    "Clear","Misty","Foggy","Stormy","Windy",
    "Cold","Frozen","Icy","Warm","Sunny","Dry","Wet",
    "Green","Gray","Black","White","Red","Blue","Gold","Silver","Iron","Copper",
]

ADJ_FANTASY = [
    "Ancient","Arcane","Elder","Forgotten","Lost","Forsaken","Hallowed","Sacred",
    "Cursed","Blessed","Fallen","Shattered","Broken","Wandering","Restless",
    "Moonlit","Starless","Starlit","Sunken",
    "Crimson","Scarlet","Azure","Emerald","Ivory","Obsidian",
    "Enchanted","Eternal","Nameless","Veiled",
    "Grim","Bleak","Lonely","Last","First",
]

# Substantivos “geográficos” (cabeças)
NOUN_GEO = [
    "Bay","Bight","Coast","Cove","Harbor","Haven","Shore","Strand","Sound",
    "Cape","Headland","Point","Spit",
    "Reef","Shoal",
    "Lake","Loch","Pond","Spring","Well",
    "Brook","Creek","Stream","River","Ford","Mouth",
    "Marsh","Bog","Fen","Swamp","Mire",
    "Delta","Estuary",
    "Falls","Rapids",
    "Glen","Vale","Valley","Hollow","Basin",
    "Hill","Heights","Downs","Ridge","Range","Pass","Gap",
    "Peak","Summit","Mount",
    "Cliff","Crag","Bluff","Escarpment",
    "Gorge","Ravine","Canyon",
    "Forest","Woods","Grove","Thicket","Glade","Clearing",
    "Plain","Steppe","Heath","Moor","Meadow","Field",
    "Dune","Sands","Desert",
    "Isle","Island","Key",
]

# Substantivos “humanos / construção” (cabeças)
NOUN_CIVIL = [
    "Town","Village","Hamlet","City","Port","Harbor","Outpost","Post",
    "Hold","Keep","Fort","Castle","Tower","Watch","Beacon","Gate","Bridge",
    "Road","Way","Trail","Passage","Crossing",
    "Mill","Forge","Quarry","Mine",
    "Abbey","Chapel","Shrine","Temple","Sanctuary","Monastery",
    "Market","Square","Hall",
    "Garden","Orchard",
    "Ruins","Crypt","Tomb",
]

# “Raízes” que funcionam bem em padrões do tipo “Noun of the X”
NOUN_ABSTRACT = [
    "Dawn","Dusk","Twilight","Midnight","Sunrise","Sunset",
    "Silence","Whisper","Echo","Song",
    "Shadow","Light","Flame","Ember","Ash",
    "Frost","Snow","Ice","Storm","Thunder",
    "Mist","Fog","Rain","Wind",
    "Hope","Sorrow","Memory","Oath","Crown","Throne",
    "Dream","Secret","Mirage","Horizon",
]

# Sufixos administrativos (p/ província mesmo)
ADMIN = [
    "Province","County","March","Shire","Reach","Territory","Hold","Prefecture",
]

# Partículas/padrões
OF = "of the"
THE = "the"

# “Bases” para possessivo (King's, Raven's, etc.)
NOUN_POSSESSOR = [
    "King","Queen","Saint","Abbot","Warden","Hunter","Ranger","Smith","Mason",
    "Wolf","Raven","Hawk","Stag","Boar","Bear","Serpent",
    "Dragon","Giant","Witch","Mage",
]

# Sugestões por bioma (só um “pool extra”)
BIOME_HINTS = {
    "Ice":     ["Frost","Snow","Ice","Frozen","Icy","Loch","Fjord","Peak","Pass"],
    "Sea":     ["Bay","Coast","Harbor","Shore","Reef","Sound","Cape","Port"],
    "Ocean":   ["Bay","Coast","Harbor","Shore","Reef","Sound","Cape","Port"],
    "Coast":   ["Bay","Coast","Harbor","Shore","Reef","Sound","Cape","Port"],
    "Desert":  ["Dune","Sands","Desert","Dry","Windy","Mirage","Oasis"],
    "Meadow":  ["Meadow","Field","Glen","Vale","River","Green","Sunny"],
    "Forest":  ["Forest","Woods","Grove","Thicket","Glade","Clearing","Green"],
    "Swamp":   ["Marsh","Bog","Fen","Mire","Mist","Fog"],
    "Mountain":["Peak","Summit","Mount","Ridge","Pass","Crag","Cliff"],
}
