# shared/naming/datasets/pt.py

# --- Substantivos (por gênero e número) ---

NOUNS_M_SG = [
    "Rio","Riacho","Córrego","Lago","Porto","Cabo",
    "Vale","Campo","Prado","Morro","Bosque",
    "Mangue","Pântano","Brejo",
    "Caminho","Forte","Castelo","Templo",
    "Povoado","Santuário",
]

NOUNS_F_SG = [
    "Baía","Costa","Praia","Ilha","Ponta","Enseada",
    "Várzea","Planície","Colina","Serra","Montanha",
    "Floresta","Mata","Selva",
    "Caverna","Gruta","Ponte","Estrada","Passagem",
    "Fortaleza","Torre","Vigia",
    "Vila","Aldeia","Cidade",
    "Capela","Cripta","Lagoa",
]

# Plural: use com parcimônia (nomes no plural são menos comuns, mas funcionam)
NOUNS_M_PL = [
    "Campos", "Morros",  # se não gostar, remova; eu recomendo manter plural pequeno
    "Bosques", "Templos", "Castelos", "Portos",
]

NOUNS_F_PL = [
    "Ruínas", "Terras", "Ilhas", "Montanhas", "Matas", "Florestas",
    "Praias", "Serras", "Pontes",
]

# --- Adjetivos em 4 formas (concordância básica) ---
# Mantive um conjunto moderado. Você pode expandir depois sem mudar o algoritmo.

ADJ_M_SG = [
    "Antigo","Arcano","Azul","Belo","Branco","Calmo","Claro","Dourado",
    "Escuro","Eterno","Frio","Fértil","Grande","Guardado","Largo","Livre",
    "Luminoso","Misterioso","Nobre","Novo","Oculto","Perdido","Profundo",
    "Puro","Quente","Quieto","Sagrado","Severo","Silencioso","Sombrio",
    "Solitário","Tranquilo","Velho","Ventoso","Verde","Vermelho","Vivo",
]

ADJ_F_SG = [
    "Antiga","Arcana","Azul","Bela","Branca","Calma","Clara","Dourada",
    "Escura","Eterna","Fria","Fértil","Grande","Guardada","Larga","Livre",
    "Luminosa","Misteriosa","Nobre","Nova","Oculta","Perdida","Profunda",
    "Pura","Quente","Quieta","Sagrada","Severa","Silenciosa","Sombria",
    "Solitária","Tranquila","Velha","Ventosa","Verde","Vermelha","Viva",
]

# Plural: regra “básica e segura”: s no final
# (sem tentar pluralizar automaticamente; só lista pronta)
ADJ_M_PL = [
    "Antigos","Arcanos","Azuis","Belos","Brancos","Calmos","Claros","Dourados",
    "Escuros","Eternos","Frios","Férteis","Grandes","Guardados","Largos","Livres",
    "Luminosos","Misteriosos","Nobres","Novos","Ocultos","Perdidos","Profundos",
    "Puros","Quentes","Quietos","Sagrados","Severos","Silenciosos","Sombrios",
    "Solitários","Tranquilos","Velhos","Ventosos","Verdes","Vermelhos","Vivos",
]

ADJ_F_PL = [
    "Antigas","Arcanas","Azuis","Belas","Brancas","Calmas","Claras","Douradas",
    "Escuras","Eternas","Frias","Férteis","Grandes","Guardadas","Largas","Livres",
    "Luminosas","Misteriosas","Nobres","Novas","Ocultas","Perdidas","Profundas",
    "Puras","Quentes","Quietas","Sagradas","Severas","Silenciosas","Sombrias",
    "Solitárias","Tranquilas","Velhas","Ventosas","Verdes","Vermelhas","Vivas",
]
