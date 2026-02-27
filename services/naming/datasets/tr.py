# shared/naming/datasets/tr.py

NOUNS = [
    "Nehir", "Irmak", "Çay", "Dere", "Pınar", "Kaynak",
    "Göl", "Gölet", "Baraj", "Şelale",
    "Vadi", "Kanyon", "Yarık", "Boğaz", "Geçit",
    "Ova", "Düzlük", "Yayla", "Plato",
    "Tepe", "Zirve", "Dağ", "Sırt", "Yamaç",
    "Uçurum", "Kayalık", "Mağara",
    "Orman", "Koruluk", "Çalılık", "Çayır", "Koru",
    "Bataklık", "Sazlık",
    "Köprü", "Yol", "Patika",
    "Kale", "Hisar", "Kule", "Kapı",
    "Köy", "Kasaba", "Şehir",
    "Tapınak", "Türbe", "Harabe",
    "Körfez", "Kıyı", "Sahil", "Liman", "İskele",
    "Ada", "Adacık", "Burun", "Fener",
]

ADJ = [
    "Eski", "Yeni", "Kadim", "Unutulmuş", "Kayıp", "Gizli", "Saklı",
    "Büyük", "Küçük", "Yüksek", "Alçak", "Derin", "Sığ",
    "Uzun", "Kısa", "Geniş", "Dar", "Dik", "Sarp",
    "Kuzey", "Güney", "Doğu", "Batı", "Orta",
    "Açık", "Karanlık", "Sessiz", "Rüzgarlı", "Sisli",
    "Soğuk", "Sıcak", "Ilık", "Kuru", "Nemli",
    "Yeşil", "Gri", "Siyah", "Beyaz", "Kırmızı", "Mavi", "Sarı",
    "Altın", "Gümüş", "Demir",
    "Kutsal", "Lanetli", "Tekinsiz", "Uzak", "Yalnız", "Vahşi",
    "Tuzlu", "Fırtınalı",
]

LI_BASE = [
    "Deniz", "Rüzgâr", "Sis", "Duman", "Gölge", "Işık",
    "Taş", "Kaya", "Toprak", "Kum", "Çakıl", "Çamur", "Tuz",
    "Buz", "Kar", "Yağmur",
    "Ateş", "Kül", "Kor",
    "Çiçek", "Çam", "Meşe", "Saz",
    "Kızıl", "Kara", "Ak", "Gök", "Yeşil",
    "Yol", "Sır", "Efsane",
]

COLOR_PREFIX = ["Ak", "Kara", "Kızıl", "Yeşil", "Gök", "Sarı"]

TOPO_HEADS = [
    "Vadisi", "Dağı", "Tepesi", "Ovası", "Gölü", "Adası",
    "Burnu", "Kıyısı", "Geçidi", "Boğazı",
]

# Seus biomas colonizáveis
COLONIZABLE_BIOMES = {"Meadow", "Forest", "Hills", "Savanna", "Mountains", "Desert"}

# Hints só para biomas que de fato geram província
BIOME_HINTS = {
    "Meadow": {
        "nouns": ["Ova", "Düzlük", "Çayır", "Yayla", "Dere", "Köy", "Kasaba"],
        "adjs":  ["Açık", "Geniş", "Sakin", "Yeşil", "Ilık"],
        "bases": ["Çiçek", "Toprak", "Işık", "Rüzgâr"],
        "heads": ["Ovası", "Vadisi"],
        "patterns": {"ADJ_NOUN": 1.15, "BASE_TOPO": 1.15},
    },
    "Forest": {
        "nouns": ["Orman", "Koruluk", "Çalılık", "Koru", "Pınar", "Dere", "Mağara"],
        "adjs":  ["Yeşil", "Nemli", "Sisli", "Sessiz", "Karanlık", "Vahşi"],
        "bases": ["Gölge", "Sis", "Çam", "Meşe", "Yağmur", "Işık"],
        "heads": ["Vadisi"],
        "patterns": {"LI_NOUN": 1.30, "ADJ_NOUN": 1.10, "ADJ_TOPO": 1.10},
    },
    "Hills": {
        "nouns": ["Tepe", "Sırt", "Yamaç", "Geçit", "Vadi", "Koruluk", "Köy"],
        "adjs":  ["Yüksek", "Dik", "Rüzgarlı", "Sisli", "Sessiz"],
        "bases": ["Taş", "Kaya", "Rüzgâr", "Çam"],
        "heads": ["Tepesi", "Geçidi", "Vadisi"],
        "patterns": {"BASE_TOPO": 1.25, "ADJ_TOPO": 1.15},
    },
    "Savanna": {
        "nouns": ["Ova", "Düzlük", "Yol", "Patika", "Kasaba", "Köy"],
        "adjs":  ["Sıcak", "Kuru", "Açık", "Uzak", "Rüzgarlı"],
        "bases": ["Kum", "Toprak", "Rüzgâr", "Tuz"],
        "heads": ["Ovası"],
        "patterns": {"ADJ_NOUN": 1.15, "LI_NOUN": 1.10},
    },
    "Mountains": {
        "nouns": ["Dağ", "Zirve", "Geçit", "Boğaz", "Uçurum", "Kayalık", "Kanyon", "Mağara"],
        "adjs":  ["Yüksek", "Sarp", "Soğuk", "Sisli", "Rüzgarlı", "Vahşi"],
        "bases": ["Taş", "Kaya", "Rüzgâr", "Buz", "Kar", "Kor"],
        "heads": ["Dağı", "Tepesi", "Geçidi", "Boğazı", "Vadisi"],
        "patterns": {"BASE_TOPO": 1.35, "ADJ_TOPO": 1.20, "ADJ_NOUN": 1.10},
    },
    "Desert": {
        "nouns": ["Çöl", "Kumluk", "Düzlük", "Kanyon", "Yarık", "Uçurum", "Geçit"],
        "adjs":  ["Kuru", "Sıcak", "Rüzgarlı", "Uzak", "Sessiz", "Tekinsiz"],
        "bases": ["Kum", "Tuz", "Ateş", "Duman", "Taş"],
        "heads": ["Ovası", "Geçidi"],
        "patterns": {"BASE_TOPO": 1.25, "LI_NOUN": 1.15, "ADJ_TOPO": 1.10},
    },
}
