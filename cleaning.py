from __future__ import annotations

import re
import unicodedata
import numpy as np
import pandas as pd

from config import (
    PRECIO_MAXIMO,
    KILOMETRAJE_MAXIMO,
    CALIFICACION_MAXIMA,
    TIPOS_INVENTARIO_ROTAR,
)

from runt_client import fetch_runt_by_chasis


# -----------------------------
# Normalización ciudad
# -----------------------------
def _norm_ciudad(s: str) -> str:
    if s is None:
        return ""
    s = str(s).strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"\s+", " ", s)
    return s.upper()


HOMOLOGACION_CIUDAD_NORM = {
    # Armenia
    _norm_ciudad("Armenia"): "Armenia",

    # Barranquilla
    _norm_ciudad("BARRANQUILLA"): "Barranquilla",
    _norm_ciudad("Barranquilla"): "Barranquilla",
    _norm_ciudad("Barranquilla ruta 66"): "Barranquilla",

    # Bucaramanga
    _norm_ciudad("BUCARAMANGA"): "Bucaramanga",
    _norm_ciudad("Bucaramanga"): "Bucaramanga",

    # Bogota
    _norm_ciudad("Bogota"): "Bogota",
    _norm_ciudad("Bodega 2 Bogota"): "Bogota",
    _norm_ciudad("Punto de Venta Bogota"): "Bogota",
    _norm_ciudad("Punto de venta Bogota"): "Bogota",
    _norm_ciudad("Bog 2R la Plaza"): "Bogota",
    _norm_ciudad("Bog 2R PDV"): "Bogota",
    _norm_ciudad("Bog AVL la 15"): "Bogota",
    
    # Cali
    _norm_ciudad("Cali"): "Cali",
    _norm_ciudad("Cali 7 de agosto"): "Cali",
    _norm_ciudad("Bodega Cali"): "Cali",
    _norm_ciudad("Bodega 2 Cali"): "Cali",
    _norm_ciudad("Calima"): "Cali",
    _norm_ciudad("Pradera"): "Cali",

    # Cartagena
    _norm_ciudad("CARTAGENA"): "Cartagena",
    _norm_ciudad("Cartagena"): "Cartagena",
    _norm_ciudad("Punto de venta Cartagena"): "Cartagena",

    # Ibague
    _norm_ciudad("Ibague"): "Ibague",

    # Medellin
    _norm_ciudad("MEDELLIN"): "Medellin",
    _norm_ciudad("Medellin"): "Medellin",
    _norm_ciudad("Serviautec"): "Medellin",
    _norm_ciudad("Dos serviautec"): "Medellin",
    _norm_ciudad("Medellin DosR"): "Medellin",

    # Neiva
    _norm_ciudad("Neiva"): "Neiva",

    # Pereira
    _norm_ciudad("Pereira"): "Pereira",

    # Santander de Quilichao
    _norm_ciudad("SANTANDER DE QUILICHAO"): "Santander de Quilichao",
    _norm_ciudad("Santander de Quilichao"): "Santander de Quilichao",

    # Santa Marta
    _norm_ciudad("Bodega Santa Marta"): "Santa Marta",
}


def homologar_ciudad(valor) -> str:
    if valor is None or str(valor).strip() == "":
        return "SinSeleccionar"
    k = _norm_ciudad(valor)
    return HOMOLOGACION_CIUDAD_NORM.get(k, str(valor).strip())


# -----------------------------
# Enriquecimiento RUNT
# -----------------------------
def enriquecer_con_runt(df: pd.DataFrame) -> pd.DataFrame:
    """
    Usa df['Chasis'] para consultar BigQuery RUNT y anexar:
    MARCA_RUNT y LINEA_RUNT
    """
    lista_chasis = (
        df["Chasis"]
        .dropna()
        .astype(str)
        .str.strip()
        .unique()
        .tolist()
    )

    if not lista_chasis:
        out = df.copy()
        out["MARCA_RUNT"] = None
        out["LINEA_RUNT"] = None
        return out

    df_runt = fetch_runt_by_chasis(lista_chasis)

    out = df.merge(
        df_runt,
        left_on="Chasis",
        right_on="CHASIS",
        how="left"
    )
    out.drop(columns=["CHASIS"], inplace=True, errors="ignore")
    out.rename(columns={"MARCA": "MARCA_RUNT", "LINEA": "LINEA_RUNT"}, inplace=True)
    return out


# -----------------------------
# OUTLIERS: Limpieza base (reglas negocio)
# -----------------------------
def limpiar_base(df: pd.DataFrame) -> pd.DataFrame:
    """
    - Quita lo que no encontró en RUNT
    - Quita outliers por PrecioVenta/KM/CalificacionFisica
    """
    df = df[df["MARCA_RUNT"].notna()].copy()

    condicion_eliminar = (
        (df["PrecioVenta"] > PRECIO_MAXIMO) |
        (df["Kilometraje"] > KILOMETRAJE_MAXIMO) #|
        #(df["CalificacionFisica"] > CALIFICACION_MAXIMA)
    )
    return df.loc[~condicion_eliminar].copy()


# -----------------------------
# Ventas (con días)
# -----------------------------
def obtener_ventas(
    df: pd.DataFrame,
    excluir_canales: list[str] | None = None
) -> pd.DataFrame:
    if excluir_canales is None:
        excluir_canales = ["MotosDesensamble"]

    df_ventas = df[
        df["FechaLegalizacion"].notna() &
        df["FechaDisponible"].notna() &
        (~df["Canal"].isin(excluir_canales))
    ].copy()

    df_ventas["dias_diff"] = (
        df_ventas["FechaLegalizacion"] -
        df_ventas["FechaDisponible"]
    ).dt.days.abs()

    df_ventas["Ciudad_Asesor"] = df_ventas["Ciudad_Asesor"].fillna("SinSeleccionar")

    df_ventas["ciudad_add"] = np.where(
        df_ventas["Ciudad_Asesor"] == "SinSeleccionar",
        df_ventas["UbicacionActual"],
        df_ventas["Ciudad_Asesor"]
    )

    df_ventas["ciudad_homologada"] = (
        df_ventas["ciudad_add"].apply(homologar_ciudad)
    )

    return df_ventas


# -----------------------------
# Inventario a rotar
# -----------------------------
def obtener_inventario_rotar(df: pd.DataFrame) -> pd.DataFrame:
    out = df[
        df["FechaLegalizacion"].isna() &
        df["TipoInventario"].isin(TIPOS_INVENTARIO_ROTAR)
    ].copy()
    return out.drop_duplicates(keep="first")