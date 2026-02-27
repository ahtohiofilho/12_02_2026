# shared/naming/datasets/ar.py
# Arabic (romanized) - ASCII only (A-Za-z + space + apostrophe + hyphen)

NOUNS = [
    # Land / relief
    "Jabal", "Tall", "Hadba", "Sahl", "Wadi", "Shi'b", "Naqb", "Fajj",
    "Madiq", "Khanq", "Jurf",
    "Kahf", "Maghara",
    "Sahra", "Ramla", "Hima", "Marj", "Rawda", "Ghaba",
    "Sakhr", "Hajar",

    # Water / coast
    "Nahr", "Ayn", "Bir", "Buhayra", "Ghadir",
    "Sabkha", "Khalij", "Khawr",
    "Marsa", "Mina",
    "Sahil", "Shati",
    "Jazira", "Ras",

    # Civil / settlement / defense / religion
    "Qarya", "Day'a", "Balda", "Madinah",
    "Hisn", "Qal'a", "Burj", "Sur", "Bab",
    "Jisr", "Dar", "Sabil", "Suq",
    "Masjid", "Jami'", "Ma'bad",
    "Maqam", "Mazar", "Qubba",
    "Kharaba", "Athar",
]

ADJ = [
    # Time / condition
    "Qadim", "Jadid", "Atiqa",
    "Mahjur", "Kharib",
    "Mansiy", "Mafqud",
    "Sirri", "Khafi", "Maknun",

    # Size / shape
    "Kabir", "Saghir",
    "Tawil", "Qasir",
    "Wasi'", "Dayyiq",
    "Ali", "Murtafi'", "Amiq",

    # Directions
    "Shamali", "Janubi", "Sharqi", "Gharbi", "Awsat",

    # Light / atmosphere
    "Munir", "Muzlim", "Mu'tim",
    "Sakin", "Hadi",
    "Dhababi", "Gha'im",

    # Climate / nature
    "Barid", "Har",
    "Rihiy", "Asif",
    "Jaf", "Ratib",

    # Colors / materials
    "Akhdar", "Ahmar", "Abyad", "Aswad", "Azraq",
    "Dhahabi", "Fiddi", "Nahasi", "Hadidi",

    # Fantasy / flavor
    "Muqaddas", "Mal'un", "Mubarak",
    "Azali", "Abadi",
    "Gharib", "Wahid",
]

IDAFA_BASE = [
    "Rih", "Dabab", "Layl", "Fajr",
    "Shams", "Qamar", "Nujum",
    "Nur", "Zill", "Zulma",
    "Nar", "Ramad", "Dukhan",
    "Matar", "Barq", "Ra'd",
    "Sakhr", "Hajar", "Tin",
    "Dhahab", "Fidda", "Hadid",
    "Bahr", "Yamm", "Mawj",
]

TOPONYMS = [
    "Nur", "Shams", "Qamar", "Najm",
    "Salam", "Amal", "Wafa", "Najah",
    "Rih", "Layl", "Fajr",
    "Dhahab", "Fidda",
]

# Dicas por bioma: tudo árabe romanizado (tokens já existentes ou compatíveis)
# Chaves seguem teu padrão do inglês; use só as que você realmente passar em ctx.biome.
BIOME_HINTS = {
    "Desert":    ["Sahra", "Ramla", "Sabkha", "Jaf", "Har", "Rihiy", "Asif", "Dabab", "Ramad"],
    "Mountains": ["Jabal", "Hadba", "Tall", "Naqb", "Fajj", "Sakhr", "Hajar", "Murtafi'", "Ali", "Amiq"],
    "Forest":    ["Ghaba", "Hima", "Marj", "Rawda", "Akhdar"],
    "Swamp":     ["Sabkha", "Ghadir", "Ratib", "Dhababi", "Zulma"],
    "River":      ["Nahr", "Wadi", "Ayn", "Bir", "Matar"],
    "Lake":      ["Buhayra", "Ghadir", "Ayn", "Bir"],
    "Sea":       ["Bahr", "Mawj", "Sahil", "Shati", "Khalij", "Khawr", "Marsa", "Mina", "Jazira", "Ras"],
    "Coast":     ["Sahil", "Shati", "Khalij", "Khawr", "Marsa", "Mina", "Jazira", "Ras", "Bahr", "Mawj"],
}
