# =====================================================
# CONFIGURACIÓN GENERAL DEL PROYECTO
# =====================================================

from pathlib import Path
import pandas as pd

# =====================================================
# PATHS BASE
# =====================================================

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR

# =====================================================
# ARCHIVOS DE ENTRADA
# =====================================================

TABLAS_PATH = DATA_DIR / "TABLAS DOSR TARIFAS.xlsx"
COSTOS_PATH = DATA_DIR / "costos_agrupados.xlsx"
REFERENCIA_CIUDAD_PATH = DATA_DIR / "estadisticos_ventas_v2.xlsx"

# =====================================================
# ARCHIVOS DE SALIDA (VERSIÓN FINAL)
# =====================================================

OUTPUT_ESTADISTICOS = DATA_DIR / "Estadisticos_Modelo.xlsx"
OUTPUT_MODELO = DATA_DIR / "Reporte_Modelo_dev.xlsx"
OUTPUT_MODELO_FORMATO = DATA_DIR / "Reporte_Modelo_prod.xlsx"

# =====================================================
# SHEETS
# =====================================================

SHEET_INVENTARIO = "INVENTARIO"
SHEET_LINEAS_OFERTA = "LINEASOFERTA"
SHEET_ACCOUNTS = "ACCOUNTS"

SHEET_TRASLADOS = "TRASLADOS"
SHEET_CUSTODIA = "CUSTODIA"
SHEET_REFERENCIA_CIUDAD = "Referencia_Ciudad"

# =====================================================
# BIGQUERY
# =====================================================

BQ_PROJECT = "lucia-stg"
BQ_TABLE = "lucia-stg.runt.RUNT"
BQ_CREDENTIALS_FILE = DATA_DIR / "bigqery.json"

# =====================================================
# PARÁMETROS NEGOCIO (LIMPIEZA)
# =====================================================

FECHA_CORTE = pd.Timestamp(2025, 6, 1)

PRECIO_MAXIMO = 20_000_000
KILOMETRAJE_MAXIMO = 300_000
CALIFICACION_MAXIMA = 5

TIPOS_INVENTARIO_ROTAR = [
    "COMERCIALIZABLE DOSR",
    "EN PROCESO"
]

# =====================================================
# CONFIG MODELO LOGÍSTICO
# =====================================================

TOP_N = 999

COL_PLACA = "Placa"
COL_REFERENCIA = "LINEA_RUNT"
COL_CIUDAD_ACTUAL = "UbicacionActual"
COL_PRECIO_MERCADO = "PrecioMercado"

COL_CIUDAD_STATS = "ciudad_homologada"
COL_DIAS = "P50_dias"
COL_PRECIO_STATS = "Promedio_PrecioVenta"

COL_REFERENCIA_COSTOS = "REFERENCIA"
COL_TRAS_ORIGEN = "Origen"
COL_TRAS_DESTINO = "Destino"
COL_COSTO_TRASLADO = "Costo Unitaro"

COL_CIUDAD_CUSTODIA = "ciudad_homologada"
COL_COSTO_CUSTODIA = "Custodia/Día"

# =====================================================
# PARÁMETROS DE ROBUSTEZ / FALLBACKS
# =====================================================

MIN_MUESTRA_EXACTA = 5
MIN_MUESTRA_REFERENCIA = 5
MIN_MUESTRA_MARCA = 5

# =====================================================
# PARÁMETROS FINANCIEROS
# =====================================================

TASA_MENSUAL = 0.02
TASA_DIARIA = TASA_MENSUAL / 30

COSTO_CAPITAL_DIARIO = TASA_DIARIA
TASA_BENEFICIO_MARGEN_DIARIA = TASA_DIARIA