# shared/naming/datasets/wu.py
# Wu (aprox.) em romanização estilo pinyin (ASCII). Sem tons.

ADJ_COMMON = [
    "Lao","Xin","Gao","Di","Shang","Xia","Dong","Xi","Nan","Bei",
    "Da","Xiao","Chang","Yuan","Kuan","Zhai",
    "Shen","Qian","Kong","Mi","Jing","Nao",
    "An","Qing","Zhuo",
    "Hei","Bai","Hong","Lan","Lu","Hui",
    "Jin","Yin","Tie","Tong",
    "Han","Re","Leng","Shi","Gan","Wu","Feng","Yu",
    "Ming","Anjing","Ningjing",
]

ADJ_FANTASY = [
    "Gu","Shenmi","Yiwang","Sheng","Shenzu","Xian",
    "Beizang","Mizang","Mofeng","Yingbi",
    "Yueying","Xingguang","Xingchen","Chenmo",
    "Chihong","Canglan","Feicui","Xiangya","Wuya",
    "Yongheng","Wuming","Yinmi",
    "Can","Gudu","Mo",
]

# “Nature” genérico (para compor LAND_LAND e WATER_WATER)
NOUN_NATURE = [
    "Lin","Senlin","Yuan","Tian","Ye","Jing","Meng",
    "Gu","Shen","Ying","Guang","Yun","Wu","Feng","Lei","Yu",
]

NOUN_WATER = [
    "He","Jiang","Xi","Hu","Chi","Ze","Quan","Jing",
    "Hekou","Shuikou","Gang","Wan","Ao","Haian","Tan",
    "Pubu","Jitan","Daba",  # “grande barragem” vibe
]

NOUN_LAND = [
    "Shan","Ling","Gangling","Feng","Ding","Guan","Xia","Ya",
    "Pingyuan","Gao yuan","Pen di","Gu di","Gu","Dong","Gudi",
    "Shamo","Shatan","Dun","Shi lin",
]

NOUN_CIVIL = [
    "Cheng","Zhen","Cun","Shi","Guan","Men","Menlou","Qiao",
    "Lu","Dao","Jie","Yizhan","Guansuo",
    "Bao","Zhai","Pu","Dian",
    "Yao","Fang","Kuang","Keng","Caichang",
    "Miao","Si","Gong","Tang",
    "Shichang","Guangchang",
    "Yuan","Guoyuan",
    "Yiji","Lingmu",
]

ADMIN = [
    "sheng",  # província
    "fu",     # prefeitura (hist./fantasia)
    "zhou",   # zhou
    "jun",    # comandância (hist.)
    "xian",   # condado
    "qu",     # distrito
    "dao",    # circuito / ilha (se você usar)
]

CORE = [
    "Guang","Ying","Yun","Wu","Feng","Lei","Huo","Shui",
    "Xue","Shuang","Yan","Chen","Meng","Mi","Miwu",
    "Sheng","Shenmi","Yiwang",
]
