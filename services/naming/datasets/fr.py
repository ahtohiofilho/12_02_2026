# shared/naming/datasets/fr.py

# -----------------------------
# Substantivos (com gênero e número)
# -----------------------------

NOUNS_M_SG = [
    "Fleuve", "Lac", "Port", "Cap", "Val", "Bois", "Mont", "Pic",
    "Col", "Pont", "Château", "Fort", "Temple", "Sanctuaire", "Village", "Chemin",
]

NOUNS_F_SG = [
    "Baie", "Côte", "Plage", "Île", "Pointe", "Anse", "Plaine", "Colline", "Chaîne",
    "Montagne", "Forêt", "Grotte", "Tour", "Ville", "Chapelle", "Crypte", "Lagune",
]

NOUNS_M_PL = [
    "Bois",      # invariável no plural
    "Ports", "Monts", "Pics", "Cols", "Ponts", "Forts", "Châteaux", "Chemins",
]

NOUNS_F_PL = [
    "Ruines", "Terres", "Îles", "Montagnes", "Plages", "Tours", "Villes",
]

# -----------------------------
# Adjetivos "gerais" (normalmente pós-nominais)
# (listas prontas; sem tentar gerar automaticamente)
# -----------------------------

ADJ_M_SG = [
    "Ancien", "Arcanique", "Azur", "Beau", "Blanc", "Calme", "Clair", "Doré",
    "Sombre", "Éternel", "Froid", "Fertile", "Grand", "Gardé", "Libre",
    "Mystérieux", "Noble", "Nouveau", "Occulte", "Perdu", "Profond", "Pur",
    "Sacré", "Sévère", "Silencieux", "Solitaire", "Tranquille",
    "Vieux", "Venteux", "Vert", "Rouge", "Vivant",
]

ADJ_F_SG = [
    "Ancienne", "Arcanique", "Azure", "Belle", "Blanche", "Calme", "Claire", "Dorée",
    "Sombre", "Éternelle", "Froide", "Fertile", "Grande", "Gardée", "Libre",
    "Mystérieuse", "Noble", "Nouvelle", "Occulte", "Perdue", "Profonde", "Pure",
    "Sacrée", "Sévère", "Silencieuse", "Solitaire", "Tranquille",
    "Vieille", "Venteuse", "Verte", "Rouge", "Vivante",
]

ADJ_M_PL = [
    "Anciens", "Arcaniques", "Azurs", "Beaux", "Blancs", "Calmes", "Clairs", "Dorés",
    "Sombres", "Éternels", "Froids", "Fertiles", "Grands", "Gardés", "Libres",
    "Mystérieux", "Nobles", "Nouveaux", "Occultes", "Perdus", "Profonds", "Purs",
    "Sacrés", "Sévères", "Silencieux", "Solitaires", "Tranquilles",
    "Vieux", "Venteux", "Verts", "Rouges", "Vivants",
]

ADJ_F_PL = [
    "Anciennes", "Arcaniques", "Azures", "Belles", "Blanches", "Calmes", "Claires", "Dorées",
    "Sombres", "Éternelles", "Froides", "Fertiles", "Grandes", "Gardées", "Libres",
    "Mystérieuses", "Nobles", "Nouvelles", "Occultes", "Perdues", "Profondes", "Pures",
    "Sacrées", "Sévères", "Silencieuses", "Solitaires", "Tranquilles",
    "Vieilles", "Venteuses", "Vertes", "Rouges", "Vivantes",
]

# -----------------------------
# BAGS (adjetivos comumente prepostos em francês)
# Beauty, Age, Goodness, Size
#
# Nota:
# - Aqui a gente mantém simples: listas explícitas por gênero/número.
# - O gerador decide se vai usar a forma preposta (ex.: "Grand Mont") ou pós (ex.: "Mont Sacré").
# - Caso você adicione "Bon/Bonne", "Petit/Petite", etc., coloque aqui também.
# -----------------------------

ADJ_BAGS_M_SG = [
    "Beau", "Ancien", "Nouveau", "Vieux", "Grand",
]

ADJ_BAGS_F_SG = [
    "Belle", "Ancienne", "Nouvelle", "Vieille", "Grande",
]

ADJ_BAGS_M_PL = [
    "Beaux", "Anciens", "Nouveaux", "Vieux", "Grands",
]

ADJ_BAGS_F_PL = [
    "Belles", "Anciennes", "Nouvelles", "Vieilles", "Grandes",
]
