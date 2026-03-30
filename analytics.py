from __future__ import annotations

import numpy as np
import pandas as pd


def _pct(x: pd.Series, p: int) -> float:
    x = x.dropna().to_numpy()
    if x.size == 0:
        return 0.0
    return float(np.percentile(x, p))


def tabla_estadisticos(df: pd.DataFrame, group_cols: list[str], total_base: int) -> pd.DataFrame:

    agg = (
        df
        .groupby(group_cols)
        .agg(
            Cantidad=("dias_diff", "size"),
            P25_dias=("dias_diff", lambda x: _pct(x, 25)),
            P50_dias=("dias_diff", lambda x: _pct(x, 50)),
            P75_dias=("dias_diff", lambda x: _pct(x, 75)),
            P90_dias=("dias_diff", lambda x: _pct(x, 90)),
            Promedio_dias=("dias_diff", "mean"),
            Promedio_CalificacionFisica=("CalificacionFisica", "mean"),
            Promedio_PrecioMercado=("PrecioMercado", "mean"),
            Promedio_PrecioVenta=("PrecioVenta", "mean"),
        )
        .reset_index()
        .sort_values("Cantidad", ascending=False)
    )

    agg["%Del_total"] = np.where(total_base > 0, agg["Cantidad"] / total_base, 0)
    agg["%Del_acumulado"] = agg["%Del_total"].cumsum()

    agg["Ingreso_por_dia"] = np.where(
        agg["P50_dias"] > 0,
        agg["Promedio_PrecioVenta"] / agg["P50_dias"],
        0
    )

    return agg


def construir_analisis_score(tabla_referencia_ciudad: pd.DataFrame) -> pd.DataFrame:

    df_score = tabla_referencia_ciudad.copy()

    ventas_por_referencia = (
        df_score
        .groupby("LINEA_RUNT")["Cantidad"]
        .sum()
        .reset_index()
        .rename(columns={"Cantidad": "Ventas_Totales"})
    )

    total_ventas_global = ventas_por_referencia["Ventas_Totales"].sum()

    ventas_por_referencia["%_Sobre_Total"] = np.where(
        total_ventas_global > 0,
        ventas_por_referencia["Ventas_Totales"] / total_ventas_global * 100,
        0
    )

    analisis_score = (
        df_score
        .groupby("LINEA_RUNT")
        .agg(
            Score_Max=("Ingreso_por_dia", "max"),
            Score_Min=("Ingreso_por_dia", "min"),
            Score_Promedio=("Ingreso_por_dia", "mean"),
            Score_Std=("Ingreso_por_dia", "std"),
            Ciudades_Analizadas=("ciudad_homologada", "nunique")
        )
        .reset_index()
    )

    analisis_score = analisis_score.merge(
        ventas_por_referencia,
        on="LINEA_RUNT",
        how="left"
    )

    analisis_score["Rango_Relativo_%"] = np.where(
        analisis_score["Score_Promedio"] != 0,
        (analisis_score["Score_Max"] - analisis_score["Score_Min"])
        / np.abs(analisis_score["Score_Promedio"]) * 100,
        0
    )

    def clasificar_impacto(x):
        if x < 10:
            return "Bajo"
        elif x < 25:
            return "Medio"
        else:
            return "Alto"

    analisis_score["Impacto_Ingreso_por_dia"] = (
        analisis_score["Rango_Relativo_%"].apply(clasificar_impacto)
    )

    return analisis_score.sort_values("Rango_Relativo_%", ascending=False)