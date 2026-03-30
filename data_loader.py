# =====================================================
# DATA LOADER Y TRANSFORMACIONES BASE
# =====================================================

import pandas as pd
import numpy as np
import unicodedata
import re

from google.cloud import bigquery
from google.oauth2 import service_account

from config import *


# =====================================================
# CARGA ARCHIVOS BASE
# =====================================================

def load_tablas_base():
    df_inventario = pd.read_excel(TABLAS_PATH, sheet_name=SHEET_INVENTARIO)
    df_lineas = pd.read_excel(TABLAS_PATH, sheet_name=SHEET_LINEAS_OFERTA)
    df_accounts = pd.read_excel(TABLAS_PATH, sheet_name=SHEET_ACCOUNTS)
    return df_inventario, df_lineas, df_accounts


def load_costos():
    df_traslados = pd.read_excel(COSTOS_PATH, sheet_name=SHEET_TRASLADOS)
    df_custodia = pd.read_excel(COSTOS_PATH, sheet_name=SHEET_CUSTODIA)
    return df_traslados, df_custodia


def load_referencia_ciudad():
    return pd.read_excel(
        REFERENCIA_CIUDAD_PATH,
        sheet_name=SHEET_REFERENCIA_CIUDAD
    )


# =====================================================
# PREPARAR LINEAS OFERTA
# =====================================================

def preparar_lineas(df_lineas, df_accounts):

    df_lineas = df_lineas.merge(
        df_accounts[["AccountName", "Ciudad"]],
        left_on="CreatedBy",
        right_on="AccountName",
        how="left"
    )

    df_lineas["Ciudad_Asesor"] = df_lineas["Ciudad"].fillna("SinSeleccionar")
    df_lineas.drop(columns=["AccountName", "Ciudad"], inplace=True)

    return df_lineas


# =====================================================
# CONSTRUIR DF FINAL
# =====================================================

def construir_df_final(df_inventario, df_lineas):

    # =============================
    # Columnas EXACTAS del notebook
    # =============================

    cols_inventario = [
        "Placa",
        "Chasis",
        "Referencia",
        "Marca",
        "Modelo",
        "UbicacionActual",
        "CalificacionFisica",
        "Kilometraje",
        "ClasificacionVenta",
        "TipoInventario",
        "PrecioMercado",
        "ValorFasecoldaGM",
        "FechaEntregaMoto",
        "FechaDisponible"
    ]

    cols_lineas = [
        "FK_Placa",
        "Canal",
        "Ciudad_Asesor",
        "ContraOferta",
        "VlrTotalCompra",
        "FechaLegalizacion",
        "TotalPasivosActuales"
    ]

    # =============================
    # Selección EXACTA como notebook
    # =============================

    df_inv_sel = df_inventario[cols_inventario].copy()
    df_lin_sel = df_lineas[cols_lineas].copy()

    df_final = df_inv_sel.merge(
        df_lin_sel,
        left_on="Placa",
        right_on="FK_Placa",
        how="left"
    )

    df_final["FechaLegalizacion"] = pd.to_datetime(
        df_final["FechaLegalizacion"],
        errors="coerce"
    )

    # =============================
    # Cálculo PrecioVenta
    # =============================

    from config import FECHA_CORTE
    import numpy as np

    df_final["PrecioVenta"] = np.select(
        [
            df_final["Canal"] == "Venta Directa",
            df_final["Canal"] == "Desensamble",
            (df_final["Canal"] == "Compraventero") &
            (df_final["FechaLegalizacion"] < FECHA_CORTE),
            (df_final["Canal"] == "Compraventero") &
            (df_final["FechaLegalizacion"] >= FECHA_CORTE),
            df_final["Canal"] == "Aliados"
        ],
        [
            df_final["VlrTotalCompra"],
            df_final["ContraOferta"],
            df_final["ContraOferta"] + df_final["TotalPasivosActuales"],
            df_final["ContraOferta"],
            df_final["VlrTotalCompra"]
        ],
        default=0
    )

    return df_final


# =====================================================
# ENRIQUECER CON RUNT
# =====================================================

def enriquecer_con_runt(df):

    lista_chasis = (
        df["Chasis"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
        .tolist()
    )

    if not lista_chasis:
        df["MARCA_RUNT"] = None
        df["LINEA_RUNT"] = None
        return df

    credentials = service_account.Credentials.from_service_account_file(
        BQ_CREDENTIALS_FILE,
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )

    client = bigquery.Client(
        credentials=credentials,
        project=BQ_PROJECT
    )

    query = """
        SELECT
            chasis AS CHASIS,
            r.MARCA,
            r.LINEA
        FROM UNNEST(@lista_chasis) AS chasis
        LEFT JOIN `lucia-stg.runt.RUNT` r
            ON r.CHASIS = chasis
    """

    job_config = bigquery.QueryJobConfig(
        query_parameters=[
            bigquery.ArrayQueryParameter(
                "lista_chasis",
                "STRING",
                lista_chasis
            )
        ]
    )

    df_runt = client.query(query, job_config=job_config).to_dataframe()

    df_out = df.merge(
        df_runt,
        left_on="Chasis",
        right_on="CHASIS",
        how="left"
    )

    df_out.drop(columns=["CHASIS"], inplace=True, errors="ignore")
    df_out.rename(
        columns={"MARCA": "MARCA_RUNT", "LINEA": "LINEA_RUNT"},
        inplace=True
    )

    return df_out


# =====================================================
# LIMPIEZA BASE
# =====================================================

def limpiar_base(df):

    df = df[df["MARCA_RUNT"].notna()].copy()

    condicion_eliminar = (
        (df["PrecioVenta"] > PRECIO_MAXIMO) |
        (df["Kilometraje"] > KILOMETRAJE_MAXIMO) |
        (df["CalificacionFisica"] > CALIFICACION_MAXIMA)
    )

    return df.loc[~condicion_eliminar].copy()


# =====================================================
# SEPARAR INVENTARIO A ROTAR
# =====================================================

def obtener_inventario_rotar(df):

    df_inv = df[
        df["FechaLegalizacion"].isna() &
        df["TipoInventario"].isin(TIPOS_INVENTARIO_ROTAR)
    ].copy()

    return df_inv.drop_duplicates(keep="first")