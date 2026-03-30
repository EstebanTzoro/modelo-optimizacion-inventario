from __future__ import annotations

import pandas as pd
import numpy as np

from config import *


# =====================================================
# MODELO PRINCIPAL
# =====================================================

def optimizar_rotacion(
    placas,
    df_inventario: pd.DataFrame,
    df_stats: pd.DataFrame,
    df_traslados: pd.DataFrame,
    df_custodia: pd.DataFrame,
    top_n: int = 999,
    modo: str = "estimado"   # "estimado" | "estricto"
) -> pd.DataFrame:

    if modo not in ["estimado", "estricto"]:
        raise ValueError("modo debe ser 'estimado' o 'estricto'")

    # =========================
    # Normalizar placas
    # =========================
    if isinstance(placas, str):
        placas = [p.strip() for p in placas.split(",")]

    placas = list(set(placas))

    df_inv = df_inventario[df_inventario[COL_PLACA].isin(placas)].copy()

    if df_inv.empty:
        raise ValueError("❌ Ninguna placa válida encontrada en inventario.")

    ciudades_validas = sorted(
        df_custodia[COL_CIUDAD_CUSTODIA]
        .dropna()
        .unique()
    )

    # =========================
    # FALLBACKS
    # =========================
    mediana_por_referencia = df_stats.groupby(COL_REFERENCIA)[COL_DIAS].median()
    mediana_por_ciudad = df_stats.groupby(COL_CIUDAD_STATS)[COL_DIAS].median()
    mediana_global_dias = pd.to_numeric(df_stats[COL_DIAS], errors="coerce").median()

    precio_por_referencia = df_stats.groupby(COL_REFERENCIA)[COL_PRECIO_STATS].median()
    precio_global = pd.to_numeric(df_stats[COL_PRECIO_STATS], errors="coerce").median()

    # =========================
    # MAPAS
    # =========================
    df_custodia_map = df_custodia.set_index(COL_CIUDAD_CUSTODIA)[COL_COSTO_CUSTODIA]

    df_traslados_ref_map = df_traslados.set_index(
        [COL_REFERENCIA_COSTOS, COL_TRAS_ORIGEN, COL_TRAS_DESTINO]
    )[COL_COSTO_TRASLADO]

    df_traslados_avg_map = df_traslados.groupby(
        [COL_TRAS_ORIGEN, COL_TRAS_DESTINO]
    )[COL_COSTO_TRASLADO].mean()

    promedio_salida = df_traslados.groupby(COL_TRAS_ORIGEN)[COL_COSTO_TRASLADO].mean()
    promedio_llegada = df_traslados.groupby(COL_TRAS_DESTINO)[COL_COSTO_TRASLADO].mean()
    promedio_global_traslado = df_traslados[COL_COSTO_TRASLADO].mean()

    resultados = []

    # =====================================================
    # ITERAR INVENTARIO
    # =====================================================

    for _, moto in df_inv.iterrows():

        placa = moto[COL_PLACA]
        referencia = moto[COL_REFERENCIA]
        ciudad_origen = moto[COL_CIUDAD_ACTUAL]
        precio_mercado_moto = pd.to_numeric(
        moto.get(COL_PRECIO_MERCADO, np.nan),
        errors="coerce"
        )
        # =========================
        # PRECIO ORIGEN
        # =========================
        row_origen = df_stats[
            (df_stats[COL_REFERENCIA] == referencia) &
            (df_stats[COL_CIUDAD_STATS] == ciudad_origen)
        ]

        nivel_precio_origen = "Exacto"

        if not row_origen.empty:
            precio_origen = float(row_origen[COL_PRECIO_STATS].values[0])
        else:
            if modo == "estricto":
                continue

            precio_inventario = pd.to_numeric(
                moto.get(COL_PRECIO_MERCADO, np.nan),
                errors="coerce"
            )

            if not pd.isna(precio_inventario) and precio_inventario > 0:
                precio_origen = float(precio_inventario)
                nivel_precio_origen = "Inventario"
            else:
                precio_origen = precio_por_referencia.get(referencia, np.nan)
                nivel_precio_origen = "Ref_Fallback"

                if pd.isna(precio_origen):
                    precio_origen = precio_global
                    nivel_precio_origen = "Global_Fallback"

        if pd.isna(precio_origen) or precio_origen <= 0:
            continue

        # =====================================================
        # ITERAR DESTINOS
        # =====================================================

        for ciudad_destino in ciudades_validas:

            row = df_stats[
                (df_stats[COL_REFERENCIA] == referencia) &
                (df_stats[COL_CIUDAD_STATS] == ciudad_destino)
            ]

            # =========================
            # DÍAS + PRECIO DESTINO
            # =========================
            if not row.empty:
                dias = pd.to_numeric(row[COL_DIAS].values[0], errors="coerce")
                precio_destino = float(row[COL_PRECIO_STATS].values[0])
            else:
                if modo == "estricto":
                    dias = mediana_global_dias
                    precio_destino = precio_origen
                else:
                    dias = mediana_por_referencia.get(referencia, np.nan)
                    if pd.isna(dias):
                        dias = mediana_por_ciudad.get(ciudad_destino, np.nan)
                    if pd.isna(dias):
                        dias = mediana_global_dias

                    precio_destino = precio_origen

            if pd.isna(dias) or dias <= 0:
                continue

            # =========================
            # COSTO TRASLADO
            # =========================
            if ciudad_origen == ciudad_destino:
                costo_traslado = 0.0
            else:
                costo_traslado = df_traslados_ref_map.get(
                    (referencia, ciudad_origen, ciudad_destino),
                    np.nan
                )

                if pd.isna(costo_traslado):
                    costo_traslado = df_traslados_avg_map.get(
                        (ciudad_origen, ciudad_destino),
                        np.nan
                    )

                if pd.isna(costo_traslado) and modo == "estimado":

                    salida = promedio_salida.get(ciudad_origen, np.nan)
                    llegada = promedio_llegada.get(ciudad_destino, np.nan)

                    if not pd.isna(salida) and not pd.isna(llegada):
                        costo_traslado = (salida + llegada) / 2
                    elif not pd.isna(salida):
                        costo_traslado = salida
                    elif not pd.isna(llegada):
                        costo_traslado = llegada
                    else:
                        costo_traslado = promedio_global_traslado

            if pd.isna(costo_traslado):
                continue

            # =========================
            # CUSTODIA
            # =========================
            costo_dia_custodia = df_custodia_map.get(ciudad_destino, np.nan)
            if pd.isna(costo_dia_custodia):
                continue

            # =========================
            # MODELO FINANCIERO
            # =========================
            margen_incremental = precio_destino - precio_origen

            costo_capital = COSTO_CAPITAL_DIARIO * precio_origen * dias
            beneficio_margen = margen_incremental * TASA_BENEFICIO_MARGEN_DIARIA * dias

            costo_total = (
                costo_traslado
                + costo_dia_custodia * dias
                + costo_capital
                - beneficio_margen
            )

            resultados.append({
                "Placa": placa,
                "Referencia": referencia,
                "PrecioMercado": round(float(precio_mercado_moto), 0) if not pd.isna(precio_mercado_moto) else np.nan,
                "Ciudad_Origen": ciudad_origen,
                "Ciudad_Recomendada": ciudad_destino,
                "Modo": modo,
                "Nivel_Precio_Origen": nivel_precio_origen,
                "Precio_Origen": round(precio_origen, 0),
                "Precio_Destino": round(precio_destino, 0),
                "Margen_Incremental": round(margen_incremental, 0),
                "Costo_Traslado": round(float(costo_traslado), 0),
                "Costo_Custodia": round(float(costo_dia_custodia), 0),
                "Costo_Capital": round(float(costo_capital), 0),
                "Dias_Esperados": round(float(dias), 1),
                "Costo_Total": round(float(costo_total), 0)
            })

    df_resultados = pd.DataFrame(resultados)

    if df_resultados.empty:
        raise ValueError("❌ No se pudieron generar recomendaciones.")

    df_resultados["Rank"] = (
        df_resultados.groupby("Placa")["Costo_Total"]
        .rank(method="first")
    )

    df_final = (
        df_resultados[df_resultados["Rank"] <= top_n]
        .sort_values(["Placa", "Costo_Total"])
        .reset_index(drop=True)
    )

    return df_final


# =====================================================
# HELPERS FECHA
# =====================================================

def preparar_mapas_fechas(df_inventario: pd.DataFrame):

    df_inventario["FechaEntregaMoto"] = pd.to_datetime(
        df_inventario["FechaEntregaMoto"],
        errors="coerce"
    )

    hoy = pd.Timestamp.today().normalize()

    map_fecha = df_inventario.set_index("Placa")["FechaEntregaMoto"]
    map_dias = (hoy - map_fecha).dt.days

    return map_fecha, map_dias


# =====================================================
# REORDENADOR
# =====================================================

def reordenar_columnas_reporte(df: pd.DataFrame) -> pd.DataFrame:

    cols = list(df.columns)

    if "Referencia" in cols:

        columnas_fecha = ["FechaEntregaMoto", "Dias_Desde_Ingreso"]
        columnas_fecha = [c for c in columnas_fecha if c in cols]

        for c in columnas_fecha:
            cols.remove(c)

        pos_ref = cols.index("Referencia") + 1

        for i, c in enumerate(columnas_fecha):
            cols.insert(pos_ref + i, c)

    bloque_objetivo = [
        "Ciudad_Origen",
        "Ciudad_Recomendada",
        "Dias_Esperados_Origen",
        "Dias_Esperados_Destino"
    ]

    columnas_existentes = [c for c in bloque_objetivo if c in cols]

    if "Ciudad_Origen" in cols and "Ciudad_Recomendada" in cols:

        for c in columnas_existentes:
            cols.remove(c)

        if "Referencia" in cols:
            base_pos = cols.index("Referencia") + 1
        elif "Placa" in cols:
            base_pos = cols.index("Placa") + 1
        else:
            base_pos = 0

        for i, c in enumerate(columnas_existentes):
            cols.insert(base_pos + i, c)

    return df[cols]