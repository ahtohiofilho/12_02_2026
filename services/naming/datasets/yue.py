# shared/naming/datasets/yue.py
# Yue (Cantonês) em Jyutping sem tons (ASCII). Espaços ok; clean_spaces normaliza.

ADJ_COMMON = [
    "lou","san","gou","dai","soeng","haa","dung","sai","naam","bak",
    "daai","siu","coeng","yuen","fun","zaak",
    "sam","cin","hung","mat","zing","naau",
    "on","cing","zok",
    "hak","baak","hung","laam","luk","fui",
    "gam","ngan","tit","tung",
    "hon","jit","laang","sap","gon","mou","fung","jyu",
    "ming","ning zing","an zing",
]

ADJ_FANTASY = [
    "gu","san mi","yi wong","sing","sin","hin",
    "bei zong","mai zong","mo fung","ying bai",
    "jyut ying","sing gwong","sing can","cam mo",
    "ci hung","cang laam","feicui","hoeng nga","wu a",
    "wing hang","mou meng","yan mat",
    "caan","gu duk","mo",
]

NOUN_NATURE = [
    "lam","sam lam","yuen","tin","je","ging","mung",
    "gu","sam","ying","gwong","wan","mou","fung","leoi","jyu",
]

NOUN_WATER = [
    "ho","gong","kei","wu","ci","zaap","cyun","zing",
    "seoi hau","ho hau","gong hau","waan","ou","hoi on","taan",
    "pok bou","zat taam",
]

NOUN_LAND = [
    "saan","leng","gaang leng","fung","ding","gwaan","haap","a",
    "ping jyun","gou yuen","pun dei","guk dei","guk","dung","guk dei",
    "saa mo","saa taan","dyun","sek lam",
]

NOUN_CIVIL = [
    "sing","zan","cyun","si","gwaan","mun","mun lau","kiu",
    "lou","dou","gaai","yi zaan","gwaan so",
    "bou","zaai","pou","dim",
    "ji fong","tit fong","kwong","hang","coi coeng",
    "miu","si","gung","tong",
    "si coeng","gwong coeng",
    "yuen","gwo yuen",
    "wai zi","ling mou",
]

ADMIN = [
    "saang",  # province (approx. cantonês, sem tons)
    "fu",     # prefecture (hist./fantasia; comum em romanização)
    "zau",    # zhou
    "gwan",   # jun (commandery) approx.
    "jin",    # xian (county) approx.
    "keoi",   # qu (district) approx.
    "dou",    # dao (circuit/ilha) approx.
]

CORE = [
    "gwong","ying","wan","mou","fung","leoi","fo","seoi",
    "syut","soeng","jin","cam","mung","mat","mou mou",
    "sing","san mi","yi wong",
]
