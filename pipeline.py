from __future__ import annotations

import pandas as pd
import numpy as np

from config import *
from data_loader import load_tablas_base, preparar_lineas, construir_df_final
from cleaning import enriquecer_con_runt, limpiar_base, obtener_ventas, homologar_ciudad
from analytics import tabla_estadisticos, construir_analisis_score
from reporte_export import exportar_dual_v4, formatear_excel_profesional


def run_pipeline(export_path=OUTPUT_ESTADISTICOS) -> dict:

    # =====================================================
    # ESTADÍSTICOS
    # =====================================================

    print("1️⃣ Cargando tablas base...")
    df_inv, df_lin, df_acc = load_tablas_base()

    print("2️⃣ Preparando LINEASOFERTA...")
    df_lin = preparar_lineas(df_lin, df_acc)

    print("3️⃣ Construyendo df_final...")
    df_final = construir_df_final(df_inv, df_lin)

    print("4️⃣ Enriqueciendo con RUNT...")
    df_final_runt = enriquecer_con_runt(df_final)

    print("5️⃣ Limpieza base...")
    df_base_limpio = limpiar_base(df_final_runt)

    print("6️⃣ Generando ventas...")
    df_ventas = obtener_ventas(df_base_limpio)

    total_ventas = len(df_ventas)
    print(f"   Ventas: {total_ventas:,}")

    print("7️⃣ Calculando estadísticas...")

    tabla_referencia_ciudad = tabla_estadisticos(
        df_ventas,
        ["LINEA_RUNT", "ciudad_homologada"],
        total_ventas
    ).round(3)

    tabla_referencia = tabla_estadisticos(
        df_ventas,
        ["LINEA_RUNT"],
        total_ventas
    ).round(3)
    tabla_marca = tabla_estadisticos(
        df_ventas,
        ["MARCA_RUNT"],
        total_ventas
    ).round(3)

    tabla_marca_ciudad = tabla_estadisticos(
        df_ventas,
        ["MARCA_RUNT", "ciudad_homologada"],
        total_ventas
    ).round(3)

    analisis_score = construir_analisis_score(tabla_referencia_ciudad).round(3)
    # =========================
    # Exportar estadísticos
    # =========================
    with pd.ExcelWriter(export_path, engine="xlsxwriter") as writer:
        tabla_marca.to_excel(writer, sheet_name="Marca", index=False)
        tabla_marca_ciudad.to_excel(writer, sheet_name="Marca_Ciudad", index=False)
        tabla_referencia.to_excel(writer, sheet_name="Referencia", index=False)
        tabla_referencia_ciudad.to_excel(writer, sheet_name="Referencia_Ciudad", index=False)
        analisis_score.to_excel(writer, sheet_name="Analisis_Ingreso_por_dia", index=False)

    print("✅ Estadísticos exportados.")

    # =====================================================
    # 2️⃣ INVENTARIO A ROTAR
    # =====================================================

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

    print("INVENTARIO_A_ROTAR shape:", df_inventario_rotar_final.shape)

    # Placas que van a entrar al juego de la optimizacion
    df_inventario_rotar_final.to_excel(
        "inventario_a_rotar.xlsx",
        index=False
    )
    df_inventario_rotar_final["UbicacionActual"] = (
    df_inventario_rotar_final["UbicacionActual"]
        .apply(homologar_ciudad)
)
    print("✅ Inventario a rotar exportado.")

    # =====================================================
    # MODELO LOGÍSTICO
    # =====================================================

    print("9️⃣ Cargando costos para modelo...")

    df_traslados = pd.read_excel(COSTOS_PATH, sheet_name=SHEET_TRASLADOS)
    df_custodia = pd.read_excel(COSTOS_PATH, sheet_name=SHEET_CUSTODIA)

    print("🔟 Ejecutando modelo dual (estricto + estimado)...")

    modelo_file = exportar_dual_v4(
        df_inventario_rotar_final=df_inventario_rotar_final,
        df_referencia_ciudad=tabla_referencia_ciudad,
        df_traslados=df_traslados,
        df_custodia=df_custodia,
        top_n=999,
        filename=OUTPUT_MODELO
    )

    # =====================================================
    # FORMATO LINDO
    # =====================================================

    print("1️⃣1️⃣ Formateando Excel final...")

    formatear_excel_profesional(
        input_file=modelo_file,
        output_file=OUTPUT_MODELO_FORMATO
    )

    print("🚀 Pipeline finalizado correctamente.")

    return {
        "df_base": df_base_limpio,
        "df_ventas": df_ventas,
        "tabla_referencia": tabla_referencia,
        "tabla_referencia_ciudad": tabla_referencia_ciudad,
        "inventario_rotar": df_inventario_rotar_final,
        "modelo_output": OUTPUT_MODELO_FORMATO,
    }