# config/economy.py
"""
Constantes de economia e produção.
Fonte única de verdade para valores numéricos do sistema econômico.
"""

# Multiplicador de jornada: produção = workers_int * produtividade * MULTIPLICADOR
MULTIPLICADOR_JORNADA: int = 16

# Workers iniciais para a PRIMEIRA província (capital) de cada civilização.
# Províncias fundadas depois recebem workers via colonização/transferência.
WORKERS_CAPITAL_INICIAL: int = 2

# Custo de trabalhador: base * (2 ^ workers_na_fila)
CUSTO_TRABALHADOR_BASE: float = 5.0

# Produtividade de minério = COMPLEMENTO - fertilidade
PRODUTIVIDADE_MINERIO_COMPLEMENTO: float = 6.0

# Nomes de alimento por bioma
ALIMENTO_POR_BIOMA: dict[str, str] = {
    "Meadow":    "Wheat",
    "Forest":    "Rice",
    "Hills":     "Corn",
    "Savanna":   "Soybean",
    "Mountains": "Barley",
    "Desert":    "Sorghum",
    "Coast":     None,
    "Sea":       None,
    "Ocean":     None,
    "Ice":       None
}
