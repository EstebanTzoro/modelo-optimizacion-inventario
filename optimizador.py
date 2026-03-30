from __future__ import annotations

import pandas as pd
import numpy as np

from config import *


def _valor_serie(serie, default=np.nan):
    if serie is None:
        return default
    try:
        v = serie.iloc[0]
    except Exception:
        return default
    return v


def _buscar_estadistico(df_stats, filtros: dict, col_valor: str):
    df = df_stats.copy()
    for col, val in filtros.items():
        df = df[df[col] == val]
    if df.empty:
        return None
    return df.iloc[0]


def _buscar_ref_ciudad(df_stats, referencia, ciudad):
    df_filtrado = df_stats[
        (df_stats[COL_REFERENCIA] == referencia) &
        (df_stats[COL_CIUDAD_STATS] == ciudad)
    ]
    if df_filtrado.empty:
        return None
    return df_filtrado.iloc[0]


def _buscar_referencia(df_stats, referencia):
    df_filtrado = df_stats[df_stats[COL_REFERENCIA] == referencia]
    if df_filtrado.empty:
        return None

    return pd.Series({
        "Cantidad": df_filtrado["Cantidad"].sum(),
        COL_DIAS: pd.to_numeric(df_filtrado[COL_DIAS], errors="coerce").median(),
        COL_PRECIO_STATS: pd.to_numeric(df_filtrado[COL_PRECIO_STATS], errors="coerce").median(),
    })


def _buscar_marca_ciudad(df_stats_marca_ciudad, marca, ciudad):
    df_filtrado = df_stats_marca_ciudad[
        (df_stats_marca_ciudad["MARCA_RUNT"] == marca) &
        (df_stats_marca_ciudad[COL_CIUDAD_STATS] == ciudad)
    ]
    if df_filtrado.empty:
        return None
    return df_filtrado.iloc[0]


def _buscar_marca(df_stats_marca, marca):
    df_filtrado = df_stats_marca[df_stats_marca["MARCA_RUNT"] == marca]
    if df_filtrado.empty:
        return None
    return df_filtrado.iloc[0]


def _buscar_ciudad(df_stats, ciudad):
    df_filtrado = df_stats[df_stats[COL_CIUDAD_STATS] == ciudad]
    if df_filtrado.empty:
        return None

    return pd.Series({
        "Cantidad": df_filtrado["Cantidad"].sum(),
        COL_DIAS: pd.to_numeric(df_filtrado[COL_DIAS], errors="coerce").median(),
        COL_PRECIO_STATS: pd.to_numeric(df_filtrado[COL_PRECIO_STATS], errors="coerce").median(),
    })


def _resolver_precio_origen(
    moto,
    row_origen_exacta,
    row_ref,
    row_marca,
    precio_global
):
    precio_mercado = pd.to_numeric(moto.get(COL_PRECIO_MERCADO, np.nan), errors="coerce")

    if row_origen_exacta is not None and row_origen_exacta["Cantidad"] >= MIN_MUESTRA_EXACTA:
        return float(row_origen_exacta[COL_PRECIO_STATS]), "Exacto", row_origen_exacta["Cantidad"]

    if not pd.isna(precio_mercado) and precio_mercado > 0:
        return float(precio_mercado), "Inventario", np.nan

    if row_ref is not None and row_ref["Cantidad"] >= MIN_MUESTRA_REFERENCIA:
        return float(row_ref[COL_PRECIO_STATS]), "Referencia", row_ref["Cantidad"]

    if row_marca is not None and row_marca["Cantidad"] >= MIN_MUESTRA_MARCA:
        return float(row_marca[COL_PRECIO_STATS]), "Marca", row_marca["Cantidad"]

    return float(precio_global), "Global", np.nan


def _resolver_destino_estimado(
    referencia,
    marca,
    ciudad_destino,
    precio_origen,
    mediana_global_dias,
    precio_global,
    row_dest_exacta,
    row_ref,
    row_marca_ciudad,
    row_marca,
    row_ciudad
):
    if row_dest_exacta is not None and row_dest_exacta["Cantidad"] >= MIN_MUESTRA_EXACTA:
        return {
            "dias": float(row_dest_exacta[COL_DIAS]),
            "precio_destino": float(row_dest_exacta[COL_PRECIO_STATS]),
            "nivel_dias": "Exacto",
            "nivel_precio_destino": "Exacto",
            "n_exacto_destino": row_dest_exacta["Cantidad"],
            "bandera_poca_data_destino": False,
        }

    if row_ref is not None and row_ref["Cantidad"] >= MIN_MUESTRA_REFERENCIA:
        return {
            "dias": float(row_ref[COL_DIAS]),
            "precio_destino": float(row_ref[COL_PRECIO_STATS]),
            "nivel_dias": "Referencia",
            "nivel_precio_destino": "Referencia",
            "n_exacto_destino": row_dest_exacta["Cantidad"] if row_dest_exacta is not None else np.nan,
            "bandera_poca_data_destino": row_dest_exacta is not None,
        }

    if row_marca_ciudad is not None and row_marca_ciudad["Cantidad"] >= MIN_MUESTRA_MARCA:
        return {
            "dias": float(row_marca_ciudad[COL_DIAS]),
            "precio_destino": float(row_marca_ciudad[COL_PRECIO_STATS]),
            "nivel_dias": "Marca_Ciudad",
            "nivel_precio_destino": "Marca_Ciudad",
            "n_exacto_destino": row_dest_exacta["Cantidad"] if row_dest_exacta is not None else np.nan,
            "bandera_poca_data_destino": row_dest_exacta is not None,
        }

    if row_marca is not None and row_marca["Cantidad"] >= MIN_MUESTRA_MARCA:
        return {
            "dias": float(row_marca[COL_DIAS]),
            "precio_destino": float(row_marca[COL_PRECIO_STATS]),
            "nivel_dias": "Marca",
            "nivel_precio_destino": "Marca",
            "n_exacto_destino": row_dest_exacta["Cantidad"] if row_dest_exacta is not None else np.nan,
            "bandera_poca_data_destino": row_dest_exacta is not None,
        }

    if row_ciudad is not None and row_ciudad["Cantidad"] > 0:
        return {
            "dias": float(row_ciudad[COL_DIAS]),
            "precio_destino": float(row_ciudad[COL_PRECIO_STATS]),
            "nivel_dias": "Ciudad",
            "nivel_precio_destino": "Ciudad",
            "n_exacto_destino": row_dest_exacta["Cantidad"] if row_dest_exacta is not None else np.nan,
            "bandera_poca_data_destino": row_dest_exacta is not None,
        }

    if not pd.isna(mediana_global_dias) and not pd.isna(precio_global):
        return {
            "dias": float(mediana_global_dias),
            "precio_destino": float(precio_global),
            "nivel_dias": "Global",
            "nivel_precio_destino": "Global",
            "n_exacto_destino": row_dest_exacta["Cantidad"] if row_dest_exacta is not None else np.nan,
            "bandera_poca_data_destino": row_dest_exacta is not None,
        }

    return {
        "dias": float(mediana_global_dias) if not pd.isna(mediana_global_dias) else np.nan,
        "precio_destino": float(precio_origen) if not pd.isna(precio_origen) else np.nan,
        "nivel_dias": "Global",
        "nivel_precio_destino": "Origen",
        "n_exacto_destino": row_dest_exacta["Cantidad"] if row_dest_exacta is not None else np.nan,
        "bandera_poca_data_destino": row_dest_exacta is not None,
    }


def _resolver_destino_estricto(
    row_dest_exacta,
    row_ref
):
    if row_dest_exacta is not None and row_dest_exacta["Cantidad"] >= MIN_MUESTRA_EXACTA:
        return {
            "dias": float(row_dest_exacta[COL_DIAS]),
            "precio_destino": float(row_dest_exacta[COL_PRECIO_STATS]),
            "nivel_dias": "Exacto",
            "nivel_precio_destino": "Exacto",
            "n_exacto_destino": row_dest_exacta["Cantidad"],
            "bandera_poca_data_destino": False,
        }

    if row_ref is not None and row_ref["Cantidad"] >= MIN_MUESTRA_REFERENCIA:
        return {
            "dias": float(row_ref[COL_DIAS]),
            "precio_destino": float(row_ref[COL_PRECIO_STATS]),
            "nivel_dias": "Referencia",
            "nivel_precio_destino": "Referencia",
            "n_exacto_destino": row_dest_exacta["Cantidad"] if row_dest_exacta is not None else np.nan,
            "bandera_poca_data_destino": row_dest_exacta is not None,
        }

    return None


def optimizar_rotacion(
    placas,
    df_inventario: pd.DataFrame,
    df_stats: pd.DataFrame,
    df_traslados: pd.DataFrame,
    df_custodia: pd.DataFrame,
    top_n: int = 999,
    modo: str = "estimado"
) -> pd.DataFrame:

    if modo not in ["estimado", "estricto"]:
        raise ValueError("modo debe ser 'estimado' o 'estricto'")

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

    mediana_global_dias = pd.to_numeric(df_stats[COL_DIAS], errors="coerce").median()
    precio_global = pd.to_numeric(df_stats[COL_PRECIO_STATS], errors="coerce").median()

    # Tablas auxiliares para fallbacks robustos
    df_stats_ref = (
        df_stats
        .groupby(COL_REFERENCIA)
        .agg(
            Cantidad=("Cantidad", "sum"),
            P50_dias=(COL_DIAS, "median"),
            Promedio_PrecioVenta=(COL_PRECIO_STATS, "median")
        )
        .reset_index()
    )

    if "MARCA_RUNT" in df_stats.columns:
        df_stats_marca_ciudad = (
            df_stats
            .groupby(["MARCA_RUNT", COL_CIUDAD_STATS])
            .agg(
                Cantidad=("Cantidad", "sum"),
                P50_dias=(COL_DIAS, "median"),
                Promedio_PrecioVenta=(COL_PRECIO_STATS, "median")
            )
            .reset_index()
        )

        df_stats_marca = (
            df_stats
            .groupby(["MARCA_RUNT"])
            .agg(
                Cantidad=("Cantidad", "sum"),
                P50_dias=(COL_DIAS, "median"),
                Promedio_PrecioVenta=(COL_PRECIO_STATS, "median")
            )
            .reset_index()
        )
    else:
        df_stats_marca_ciudad = pd.DataFrame(columns=["MARCA_RUNT", COL_CIUDAD_STATS, "Cantidad", COL_DIAS, COL_PRECIO_STATS])
        df_stats_marca = pd.DataFrame(columns=["MARCA_RUNT", "Cantidad", COL_DIAS, COL_PRECIO_STATS])

    df_custodia_map = df_custodia.set_index(COL_CIUDAD_CUSTODIA)[COL_COSTO_CUSTODIA]

    df_traslados_ref_map = df_traslados.set_index(
        [COL_REFERENCIA_COSTOS, COL_TRAS_ORIGEN, COL_TRAS_DESTINO]
    )[COL_COSTO_TRASLADO]

    df_traslados_avg_map = df_traslados.groupby(
        [COL_TRAS_ORIGEN, COL_TRAS_DESTINO]
    )[COL_COSTO_TRASLADO].median()

    promedio_salida = df_traslados.groupby(COL_TRAS_ORIGEN)[COL_COSTO_TRASLADO].median()
    promedio_llegada = df_traslados.groupby(COL_TRAS_DESTINO)[COL_COSTO_TRASLADO].median()
    promedio_global_traslado = df_traslados[COL_COSTO_TRASLADO].median()

    resultados = []

    for _, moto in df_inv.iterrows():

        placa = moto[COL_PLACA]
        referencia = moto[COL_REFERENCIA]
        ciudad_origen = moto[COL_CIUDAD_ACTUAL]
        marca = moto.get("MARCA_RUNT", np.nan)

        precio_mercado_moto = pd.to_numeric(
            moto.get(COL_PRECIO_MERCADO, np.nan),
            errors="coerce"
        )

        row_origen_exacta = _buscar_ref_ciudad(df_stats, referencia, ciudad_origen)

        row_ref = _buscar_referencia(df_stats_ref, referencia)
        row_ref = row_ref if row_ref is not None else None

        row_marca = _buscar_marca(df_stats_marca, marca) if pd.notna(marca) else None

        precio_origen, nivel_precio_origen, n_precio_origen = _resolver_precio_origen(
            moto=moto,
            row_origen_exacta=row_origen_exacta,
            row_ref=row_ref,
            row_marca=row_marca,
            precio_global=precio_global
        )

        if pd.isna(precio_origen) or precio_origen <= 0:
            continue

        for ciudad_destino in ciudades_validas:

            row_dest_exacta = _buscar_ref_ciudad(df_stats, referencia, ciudad_destino)
            row_marca_ciudad = (
                _buscar_marca_ciudad(df_stats_marca_ciudad, marca, ciudad_destino)
                if pd.notna(marca) else None
            )
            row_ciudad = _buscar_ciudad(df_stats, ciudad_destino)

            if modo == "estimado":
                destino = _resolver_destino_estimado(
                    referencia=referencia,
                    marca=marca,
                    ciudad_destino=ciudad_destino,
                    precio_origen=precio_origen,
                    mediana_global_dias=mediana_global_dias,
                    precio_global=precio_global,
                    row_dest_exacta=row_dest_exacta,
                    row_ref=row_ref,
                    row_marca_ciudad=row_marca_ciudad,
                    row_marca=row_marca,
                    row_ciudad=row_ciudad
                )
            else:
                destino = _resolver_destino_estricto(
                    row_dest_exacta=row_dest_exacta,
                    row_ref=row_ref
                )

            if destino is None:
                continue

            dias = pd.to_numeric(destino["dias"], errors="coerce")
            precio_destino = pd.to_numeric(destino["precio_destino"], errors="coerce")

            if pd.isna(dias) or dias <= 0:
                continue

            if pd.isna(precio_destino) or precio_destino <= 0:
                continue

            if ciudad_origen == ciudad_destino:
                costo_traslado = 0.0
                nivel_traslado = "Misma_Ciudad"
            else:
                costo_traslado = df_traslados_ref_map.get(
                    (referencia, ciudad_origen, ciudad_destino),
                    np.nan
                )
                nivel_traslado = "Exacto"

                if pd.isna(costo_traslado):
                    costo_traslado = df_traslados_avg_map.get(
                        (ciudad_origen, ciudad_destino),
                        np.nan
                    )
                    nivel_traslado = "Ruta"

                if pd.isna(costo_traslado) and modo == "estimado":
                    salida = promedio_salida.get(ciudad_origen, np.nan)
                    llegada = promedio_llegada.get(ciudad_destino, np.nan)

                    if not pd.isna(salida) and not pd.isna(llegada):
                        costo_traslado = (salida + llegada) / 2
                        nivel_traslado = "Salida_Llegada"
                    elif not pd.isna(salida):
                        costo_traslado = salida
                        nivel_traslado = "Salida"
                    elif not pd.isna(llegada):
                        costo_traslado = llegada
                        nivel_traslado = "Llegada"
                    else:
                        costo_traslado = promedio_global_traslado
                        nivel_traslado = "Global"

            if pd.isna(costo_traslado):
                continue

            costo_dia_custodia = df_custodia_map.get(ciudad_destino, np.nan)
            if pd.isna(costo_dia_custodia):
                continue

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
                "Nivel_Dias": destino["nivel_dias"],
                "Nivel_Precio_Destino": destino["nivel_precio_destino"],
                "Nivel_Traslado": nivel_traslado,
                "N_Exacto_Destino": destino["n_exacto_destino"],
                "N_Referencia": row_ref["Cantidad"] if row_ref is not None else np.nan,
                "N_Marca_Ciudad": row_marca_ciudad["Cantidad"] if row_marca_ciudad is not None else np.nan,
                "Bandera_Poca_Data_Destino": destino["bandera_poca_data_destino"],
                "Precio_Origen": round(float(precio_origen), 0),
                "Precio_Destino": round(float(precio_destino), 0),
                "Margen_Incremental": round(float(margen_incremental), 0),
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


def preparar_mapas_fechas(df_inventario: pd.DataFrame):

    df_inventario["FechaEntregaMoto"] = pd.to_datetime(
        df_inventario["FechaEntregaMoto"],
        errors="coerce"
    )

    hoy = pd.Timestamp.today().normalize()

    map_fecha = df_inventario.set_index("Placa")["FechaEntregaMoto"]
    map_dias = (hoy - map_fecha).dt.days

    return map_fecha, map_dias


def reordenar_columnas_reporte(df: pd.DataFrame) -> pd.DataFrame:

    cols = list(df.columns)

    if "Referencia" in cols:

        columnas_fecha = ["PrecioMercado", "FechaEntregaMoto", "Dias_Desde_Ingreso"]
        columnas_fecha = [c for c in columnas_fecha if c in cols]

        for c in columnas_fecha:
            if c in cols:
                cols.remove(c)

        pos_ref = cols.index("Referencia") + 1

        for i, c in enumerate(columnas_fecha):
            cols.insert(pos_ref + i, c)

    bloque_objetivo = [
        "Ciudad_Origen",
        "Ciudad_Recomendada",
        "Dias_Esperados_Origen",
        "Dias_Esperados_Destino",
        "Nivel_Dias",
        "Nivel_Precio_Destino",
        "Nivel_Traslado",
        "Bandera_Poca_Data_Destino",
        "N_Exacto_Destino",
        "N_Referencia",
        "N_Marca_Ciudad"
    ]

    columnas_existentes = [c for c in bloque_objetivo if c in cols]

    if "Ciudad_Origen" in cols and "Ciudad_Recomendada" in cols:

        for c in columnas_existentes:
            if c in cols:
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