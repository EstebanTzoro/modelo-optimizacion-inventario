from __future__ import annotations

import pandas as pd
import numpy as np

from config import *
from data_loader import load_tablas_base, preparar_lineas, construir_df_final
from cleaning import enriquecer_con_runt, limpiar_base, obtener_ventas, homologar_ciudad
from analytics import tabla_estadisticos
from optimizador import optimizar_rotacion


def _comparar_rank1(
    resultado_base: pd.DataFrame,
    resultado_sens: pd.DataFrame,
    etiqueta: str
):
    rank1_base = (
        resultado_base[resultado_base["Rank"] == 1][
            ["Placa", "Ciudad_Recomendada", "Costo_Total", "Dias_Esperados", "Nivel_Precio_Origen"]
        ]
        .copy()
        .rename(columns={
            "Ciudad_Recomendada": "Ciudad_Recomendada_base",
            "Costo_Total": "Costo_Total_base",
            "Dias_Esperados": "Dias_Esperados_base",
            "Nivel_Precio_Origen": "Nivel_Precio_Origen_base"
        })
    )

    rank1_sens = (
        resultado_sens[resultado_sens["Rank"] == 1][
            ["Placa", "Ciudad_Recomendada", "Costo_Total", "Dias_Esperados", "Nivel_Precio_Origen"]
        ]
        .copy()
        .rename(columns={
            "Ciudad_Recomendada": "Ciudad_Recomendada_sens",
            "Costo_Total": "Costo_Total_sens",
            "Dias_Esperados": "Dias_Esperados_sens",
            "Nivel_Precio_Origen": "Nivel_Precio_Origen_sens"
        })
    )

    comparacion = rank1_base.merge(rank1_sens, on="Placa", how="outer")

    comparacion["Existe_base"] = comparacion["Ciudad_Recomendada_base"].notna()
    comparacion["Existe_sens"] = comparacion["Ciudad_Recomendada_sens"].notna()

    comparacion["Cambio_Recomendacion"] = np.where(
        comparacion["Existe_base"] & comparacion["Existe_sens"],
        comparacion["Ciudad_Recomendada_base"] != comparacion["Ciudad_Recomendada_sens"],
        False
    )

    comparacion["Delta_Costo_Total"] = (
        pd.to_numeric(comparacion["Costo_Total_sens"], errors="coerce")
        - pd.to_numeric(comparacion["Costo_Total_base"], errors="coerce")
    )

    comparacion["Delta_Dias_Esperados"] = (
        pd.to_numeric(comparacion["Dias_Esperados_sens"], errors="coerce")
        - pd.to_numeric(comparacion["Dias_Esperados_base"], errors="coerce")
    )

    resumen = pd.DataFrame({
        "Indicador": [
            f"Placas con recomendacion {etiqueta} - Base",
            f"Placas con recomendacion {etiqueta} - Sin compraventero",
            f"Placas que cambian recomendacion {etiqueta}",
            f"% placas que cambian recomendacion {etiqueta}",
            f"Delta costo total agregado {etiqueta}",
            f"Delta costo promedio por placa {etiqueta}",
            f"Delta dias promedio por placa {etiqueta}"
        ],
        "Valor": [
            int(comparacion["Existe_base"].sum()),
            int(comparacion["Existe_sens"].sum()),
            int(comparacion["Cambio_Recomendacion"].sum()),
            round(
                comparacion["Cambio_Recomendacion"].sum()
                / max(int(comparacion["Existe_base"].sum()), 1) * 100,
                2
            ),
            round(pd.to_numeric(comparacion["Delta_Costo_Total"], errors="coerce").sum(), 2),
            round(pd.to_numeric(comparacion["Delta_Costo_Total"], errors="coerce").mean(), 2),
            round(pd.to_numeric(comparacion["Delta_Dias_Esperados"], errors="coerce").mean(), 2),
        ]
    })

    ciudades_base = (
        comparacion["Ciudad_Recomendada_base"]
        .fillna("Sin recomendacion")
        .value_counts(dropna=False)
        .rename_axis("Ciudad")
        .reset_index(name="Placas_Base")
    )

    ciudades_sens = (
        comparacion["Ciudad_Recomendada_sens"]
        .fillna("Sin recomendacion")
        .value_counts(dropna=False)
        .rename_axis("Ciudad")
        .reset_index(name="Placas_Sin_Compraventero")
    )

    ciudades = ciudades_base.merge(ciudades_sens, on="Ciudad", how="outer").fillna(0)
    ciudades["Delta_Placas"] = (
        ciudades["Placas_Sin_Compraventero"] - ciudades["Placas_Base"]
    )
    ciudades = ciudades.sort_values("Delta_Placas", ascending=False)

    return comparacion, resumen, ciudades


def run_analisis_impacto_compraventero(
    output_file: str = "Analisis_Impacto_Compraventero.xlsx",
    umbral_poca_data: int = 3
) -> dict:

    print("1️⃣ Cargando tablas base...")
    df_inv, df_lin, df_acc = load_tablas_base()

    auditoria_canales_lineas = (
        df_lin["Canal"]
        .fillna("SinValor")
        .value_counts(dropna=False)
        .rename_axis("Canal")
        .reset_index(name="Cantidad")
    )
    auditoria_canales_lineas["%"] = (
        auditoria_canales_lineas["Cantidad"]
        / auditoria_canales_lineas["Cantidad"].sum() * 100
    ).round(2)

    print("2️⃣ Preparando LINEASOFERTA...")
    df_lin = preparar_lineas(df_lin, df_acc)

    print("3️⃣ Construyendo df_final...")
    df_final = construir_df_final(df_inv, df_lin)

    print("4️⃣ Enriqueciendo con RUNT...")
    df_final_runt = enriquecer_con_runt(df_final)

    print("5️⃣ Limpieza base...")
    df_base_limpio = limpiar_base(df_final_runt)

    df_hist_total = df_base_limpio[
        df_base_limpio["FechaLegalizacion"].notna() &
        df_base_limpio["FechaDisponible"].notna()
    ].copy()

    auditoria_canales_hist = (
        df_hist_total["Canal"]
        .fillna("SinValor")
        .value_counts(dropna=False)
        .rename_axis("Canal")
        .reset_index(name="Cantidad")
    )
    auditoria_canales_hist["%"] = (
        auditoria_canales_hist["Cantidad"]
        / auditoria_canales_hist["Cantidad"].sum() * 100
    ).round(2)

    print("6️⃣ Construyendo escenarios de ventas...")
    df_ventas_base = obtener_ventas(
        df_base_limpio,
        excluir_canales=["MotosDesensamble"]
    )

    df_ventas_sens = obtener_ventas(
        df_base_limpio,
        excluir_canales=["MotosDesensamble", "Compraventero"]
    )

    print("7️⃣ Calculando estadísticos...")
    stats_base = tabla_estadisticos(
        df_ventas_base,
        ["LINEA_RUNT", "ciudad_homologada"],
        len(df_ventas_base)
    ).round(3)

    stats_sens = tabla_estadisticos(
        df_ventas_sens,
        ["LINEA_RUNT", "ciudad_homologada"],
        len(df_ventas_sens)
    ).round(3)

    ventas_compraventero = int((df_ventas_base["Canal"] == "Compraventero").sum())
    refs_base_total = int(df_ventas_base["LINEA_RUNT"].nunique())
    refs_compraventero = int(
        df_ventas_base.loc[
            df_ventas_base["Canal"] == "Compraventero",
            "LINEA_RUNT"
        ].nunique()
    )

    resumen_participacion = pd.DataFrame({
        "Indicador": [
            "Ventas base",
            "Ventas compraventero",
            "% ventas compraventero",
            "Referencias base",
            "Referencias tocadas por compraventero",
            "% referencias afectadas por compraventero"
        ],
        "Valor": [
            len(df_ventas_base),
            ventas_compraventero,
            round(ventas_compraventero / max(len(df_ventas_base), 1) * 100, 2),
            refs_base_total,
            refs_compraventero,
            round(refs_compraventero / max(refs_base_total, 1) * 100, 2)
        ]
    })

    refs_sens_total = int(df_ventas_sens["LINEA_RUNT"].nunique())

    ref_base = set(df_ventas_base["LINEA_RUNT"].dropna().unique())
    ref_sens = set(df_ventas_sens["LINEA_RUNT"].dropna().unique())

    pares_base = set(
        stats_base[["LINEA_RUNT", "ciudad_homologada"]]
        .dropna()
        .itertuples(index=False, name=None)
    )
    pares_sens = set(
        stats_sens[["LINEA_RUNT", "ciudad_homologada"]]
        .dropna()
        .itertuples(index=False, name=None)
    )

    resumen_ejecutivo = pd.DataFrame({
        "Indicador": [
            "Ventas base",
            "Ventas sin compraventero",
            "Ventas perdidas",
            "% ventas perdidas",
            "Referencias con historia - base",
            "Referencias con historia - sin compraventero",
            "Referencias que se quedan sin historia",
            "Combinaciones referencia-ciudad - base",
            "Combinaciones referencia-ciudad - sin compraventero",
            "Combinaciones referencia-ciudad que se quedan sin historia"
        ],
        "Valor": [
            len(df_ventas_base),
            len(df_ventas_sens),
            len(df_ventas_base) - len(df_ventas_sens),
            round((len(df_ventas_base) - len(df_ventas_sens)) / max(len(df_ventas_base), 1) * 100, 2),
            refs_base_total,
            refs_sens_total,
            len(ref_base - ref_sens),
            len(pares_base),
            len(pares_sens),
            len(pares_base - pares_sens)
        ]
    })

    comparacion_stats = stats_base.merge(
        stats_sens,
        on=["LINEA_RUNT", "ciudad_homologada"],
        how="outer",
        suffixes=("_base", "_sens")
    )

    for col in [
        "Cantidad_base", "Cantidad_sens",
        "P50_dias_base", "P50_dias_sens",
        "Promedio_PrecioVenta_base", "Promedio_PrecioVenta_sens",
        "Ingreso_por_dia_base", "Ingreso_por_dia_sens"
    ]:
        if col in comparacion_stats.columns:
            comparacion_stats[col] = pd.to_numeric(comparacion_stats[col], errors="coerce")

    comparacion_stats["Delta_Cantidad"] = (
        comparacion_stats["Cantidad_sens"] - comparacion_stats["Cantidad_base"]
    )
    comparacion_stats["Delta_P50_dias"] = (
        comparacion_stats["P50_dias_sens"] - comparacion_stats["P50_dias_base"]
    )
    comparacion_stats["Delta_Promedio_PrecioVenta"] = (
        comparacion_stats["Promedio_PrecioVenta_sens"] - comparacion_stats["Promedio_PrecioVenta_base"]
    )
    comparacion_stats["Delta_Ingreso_por_dia"] = (
        comparacion_stats["Ingreso_por_dia_sens"] - comparacion_stats["Ingreso_por_dia_base"]
    )

    comparacion_stats["Sin_Historia_Tras_Quitar_Compraventero"] = (
        comparacion_stats["Cantidad_base"].notna() &
        comparacion_stats["Cantidad_sens"].isna()
    )

    comparacion_stats["Poca_Data_Base"] = comparacion_stats["Cantidad_base"].fillna(0) < umbral_poca_data
    comparacion_stats["Poca_Data_Sens"] = comparacion_stats["Cantidad_sens"].fillna(0) < umbral_poca_data

    resumen_stats = pd.DataFrame({
        "Indicador": [
            "Delta promedio P50_dias",
            "Delta mediano P50_dias",
            "Delta promedio PrecioVenta",
            "Delta mediano PrecioVenta",
            "Delta promedio Ingreso_por_dia",
            "Delta mediano Ingreso_por_dia",
            f"Combinaciones con poca data base (<{umbral_poca_data})",
            f"Combinaciones con poca data sin compraventero (<{umbral_poca_data})"
        ],
        "Valor": [
            round(comparacion_stats["Delta_P50_dias"].mean(), 3),
            round(comparacion_stats["Delta_P50_dias"].median(), 3),
            round(comparacion_stats["Delta_Promedio_PrecioVenta"].mean(), 3),
            round(comparacion_stats["Delta_Promedio_PrecioVenta"].median(), 3),
            round(comparacion_stats["Delta_Ingreso_por_dia"].mean(), 3),
            round(comparacion_stats["Delta_Ingreso_por_dia"].median(), 3),
            int(comparacion_stats["Poca_Data_Base"].sum()),
            int(comparacion_stats["Poca_Data_Sens"].sum())
        ]
    })

    top_mas_sensibles = comparacion_stats.copy()
    top_mas_sensibles["Impacto_Absoluto_Ingreso"] = top_mas_sensibles["Delta_Ingreso_por_dia"].abs()
    top_mas_sensibles["Impacto_Absoluto_P50"] = top_mas_sensibles["Delta_P50_dias"].abs()
    top_mas_sensibles["Impacto_Absoluto_Precio"] = top_mas_sensibles["Delta_Promedio_PrecioVenta"].abs()
    top_mas_sensibles = top_mas_sensibles.sort_values(
        ["Impacto_Absoluto_Ingreso", "Impacto_Absoluto_P50", "Impacto_Absoluto_Precio"],
        ascending=False
    )

    print("8️⃣ Construyendo inventario a rotar...")
    df_inventario_rotar = df_base_limpio[
        df_base_limpio["FechaLegalizacion"].isna() &
        df_base_limpio["TipoInventario"].isin(["COMERCIALIZABLE DOSR", "EN PROCESO"])
    ].copy()

    cols_inventario_rotar = [
        "Placa",
        "Chasis",
        "MARCA_RUNT",
        "LINEA_RUNT",
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

    df_inventario_rotar_final = (
        df_inventario_rotar[cols_inventario_rotar]
        .copy()
        .drop_duplicates(keep="first")
    )

    df_inventario_rotar_final["UbicacionActual"] = (
        df_inventario_rotar_final["UbicacionActual"].apply(homologar_ciudad)
    )

    parejas_base = stats_base[["LINEA_RUNT", "ciudad_homologada"]].drop_duplicates().copy()
    parejas_base["Exacto_Origen_Base"] = True

    parejas_sens = stats_sens[["LINEA_RUNT", "ciudad_homologada"]].drop_duplicates().copy()
    parejas_sens["Exacto_Origen_Sens"] = True

    ciudades_por_ref_base = (
        stats_base.groupby("LINEA_RUNT")["ciudad_homologada"]
        .nunique()
        .reset_index(name="Ciudades_Exactas_Base")
    )

    ciudades_por_ref_sens = (
        stats_sens.groupby("LINEA_RUNT")["ciudad_homologada"]
        .nunique()
        .reset_index(name="Ciudades_Exactas_Sens")
    )

    fallback_inv = df_inventario_rotar_final.merge(
        parejas_base,
        left_on=["LINEA_RUNT", "UbicacionActual"],
        right_on=["LINEA_RUNT", "ciudad_homologada"],
        how="left"
    ).drop(columns=["ciudad_homologada"], errors="ignore")

    fallback_inv = fallback_inv.merge(
        parejas_sens,
        left_on=["LINEA_RUNT", "UbicacionActual"],
        right_on=["LINEA_RUNT", "ciudad_homologada"],
        how="left"
    ).drop(columns=["ciudad_homologada"], errors="ignore")

    fallback_inv = fallback_inv.merge(ciudades_por_ref_base, on="LINEA_RUNT", how="left")
    fallback_inv = fallback_inv.merge(ciudades_por_ref_sens, on="LINEA_RUNT", how="left")

    fallback_inv["Exacto_Origen_Base"] = fallback_inv["Exacto_Origen_Base"].fillna(False)
    fallback_inv["Exacto_Origen_Sens"] = fallback_inv["Exacto_Origen_Sens"].fillna(False)

    fallback_inv["Ciudades_Exactas_Base"] = fallback_inv["Ciudades_Exactas_Base"].fillna(0)
    fallback_inv["Ciudades_Exactas_Sens"] = fallback_inv["Ciudades_Exactas_Sens"].fillna(0)

    fallback_inv["Pasa_A_Fallback_Origen"] = (
        fallback_inv["Exacto_Origen_Base"] & ~fallback_inv["Exacto_Origen_Sens"]
    )

    fallback_inv["Delta_Ciudades_Exactas"] = (
        fallback_inv["Ciudades_Exactas_Sens"] - fallback_inv["Ciudades_Exactas_Base"]
    )

    fallback_inv["Pierde_Cobertura_Destinos"] = fallback_inv["Delta_Ciudades_Exactas"] < 0

    resumen_fallback = pd.DataFrame({
        "Indicador": [
            "Motos inventario",
            "Motos con match exacto origen - base",
            "Motos con match exacto origen - sin compraventero",
            "Motos que pasan a fallback de origen",
            "Motos que pierden cobertura de destinos exactos",
            "Delta promedio de ciudades exactas por referencia"
        ],
        "Valor": [
            len(fallback_inv),
            int(fallback_inv["Exacto_Origen_Base"].sum()),
            int(fallback_inv["Exacto_Origen_Sens"].sum()),
            int(fallback_inv["Pasa_A_Fallback_Origen"].sum()),
            int(fallback_inv["Pierde_Cobertura_Destinos"].sum()),
            round(fallback_inv["Delta_Ciudades_Exactas"].mean(), 3)
        ]
    })

    print("9️⃣ Cargando costos...")
    df_traslados = pd.read_excel(COSTOS_PATH, sheet_name=SHEET_TRASLADOS)
    df_custodia = pd.read_excel(COSTOS_PATH, sheet_name=SHEET_CUSTODIA)

    placas_inventario = df_inventario_rotar_final["Placa"].tolist()

    print("🔟 Corriendo optimizador base y sensibilidad...")
    resultado_base_estimado = optimizar_rotacion(
        placas=placas_inventario,
        df_inventario=df_inventario_rotar_final,
        df_stats=stats_base,
        df_traslados=df_traslados,
        df_custodia=df_custodia,
        top_n=TOP_N,
        modo="estimado"
    )

    resultado_sens_estimado = optimizar_rotacion(
        placas=placas_inventario,
        df_inventario=df_inventario_rotar_final,
        df_stats=stats_sens,
        df_traslados=df_traslados,
        df_custodia=df_custodia,
        top_n=TOP_N,
        modo="estimado"
    )

    resultado_base_estricto = optimizar_rotacion(
        placas=placas_inventario,
        df_inventario=df_inventario_rotar_final,
        df_stats=stats_base,
        df_traslados=df_traslados,
        df_custodia=df_custodia,
        top_n=TOP_N,
        modo="estricto"
    )

    resultado_sens_estricto = optimizar_rotacion(
        placas=placas_inventario,
        df_inventario=df_inventario_rotar_final,
        df_stats=stats_sens,
        df_traslados=df_traslados,
        df_custodia=df_custodia,
        top_n=TOP_N,
        modo="estricto"
    )

    comp_est, resumen_opt_est, ciudades_est = _comparar_rank1(
        resultado_base_estimado,
        resultado_sens_estimado,
        "estimado"
    )

    comp_estx, resumen_opt_estx, ciudades_estx = _comparar_rank1(
        resultado_base_estricto,
        resultado_sens_estricto,
        "estricto"
    )

    print("1️⃣1️⃣ Exportando análisis...")
    with pd.ExcelWriter(output_file, engine="xlsxwriter") as writer:
        auditoria_canales_lineas.to_excel(writer, sheet_name="Auditoria_Canales_Lineas", index=False)
        auditoria_canales_hist.to_excel(writer, sheet_name="Auditoria_Canales_Hist", index=False)

        resumen_participacion.to_excel(writer, sheet_name="Resumen_Participacion", index=False)
        resumen_ejecutivo.to_excel(writer, sheet_name="Resumen_Ejecutivo", index=False)

        stats_base.to_excel(writer, sheet_name="Stats_Base", index=False)
        stats_sens.to_excel(writer, sheet_name="Stats_Sin_Comprav", index=False)
        comparacion_stats.to_excel(writer, sheet_name="Comparacion_Stats", index=False)
        resumen_stats.to_excel(writer, sheet_name="Resumen_Stats", index=False)
        top_mas_sensibles.to_excel(writer, sheet_name="Top_Mas_Sensibles", index=False)

        fallback_inv.to_excel(writer, sheet_name="Fallback_Inventario", index=False)
        resumen_fallback.to_excel(writer, sheet_name="Resumen_Fallback", index=False)

        comp_est.to_excel(writer, sheet_name="Comp_Reco_Estimado", index=False)
        resumen_opt_est.to_excel(writer, sheet_name="Resumen_Opt_Estimado", index=False)
        ciudades_est.to_excel(writer, sheet_name="Ciudades_Estimado", index=False)

        comp_estx.to_excel(writer, sheet_name="Comp_Reco_Estricto", index=False)
        resumen_opt_estx.to_excel(writer, sheet_name="Resumen_Opt_Estricto", index=False)
        ciudades_estx.to_excel(writer, sheet_name="Ciudades_Estricto", index=False)

    print(f"✅ Análisis exportado en: {output_file}")

    return {
        "auditoria_canales_lineas": auditoria_canales_lineas,
        "auditoria_canales_hist": auditoria_canales_hist,
        "resumen_participacion": resumen_participacion,
        "resumen_ejecutivo": resumen_ejecutivo,
        "comparacion_stats": comparacion_stats,
        "fallback_inv": fallback_inv,
        "comp_est": comp_est,
        "comp_estx": comp_estx,
        "output_file": output_file,
    }