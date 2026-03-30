import streamlit as st
import tempfile
import shutil
from pathlib import Path
import os
import traceback
import sys
import importlib

st.set_page_config(page_title="Modelo de Optimización", layout="wide")

# =========================
# CONFIG LOCAL FIJA
# =========================
BASE_PROYECTO = Path(__file__).resolve().parent
COSTOS_FIJOS = BASE_PROYECTO / "costos_agrupados.xlsx"
CREDENCIALES_FIJAS = BASE_PROYECTO / "bigqery.json"

ARCHIVOS_MODULOS = [
    "config.py",
    "pipeline.py",
    "data_loader.py",
    "cleaning.py",
    "analytics.py",
    "optimizador.py",
    "reporte_export.py",
    "runt_client.py",
]

MODULOS_LIMPIAR = [
    "config",
    "pipeline",
    "data_loader",
    "cleaning",
    "analytics",
    "optimizador",
    "reporte_export",
    "runt_client",
]

# =========================
# HELPERS
# =========================
def guardar_archivo_subido(uploaded_file, destino: Path):
    with open(destino, "wb") as f:
        f.write(uploaded_file.getbuffer())

def copiar_archivo(origen: Path, destino: Path):
    if not origen.exists():
        raise FileNotFoundError(f"No existe el archivo requerido: {origen}")
    shutil.copy(origen, destino)

def limpiar_modulos_cache():
    for mod in MODULOS_LIMPIAR:
        if mod in sys.modules:
            del sys.modules[mod]

# =========================
# UI
# =========================
st.title("Modelo de Optimización de Inventario")
st.write("Sube el archivo de tarifas, ejecuta el modelo y descarga el resultado.")

with st.sidebar:
    st.header("Parámetros")
    top_n = st.number_input("Top N", min_value=1, max_value=9999, value=999, step=1)

tablas_file = st.file_uploader(
    "Sube TABLAS DOSR TARIFAS.xlsx",
    type=["xlsx"],
    key="tablas"
)

ejecutar = st.button("Ejecutar modelo", type="primary")

if ejecutar:
    if not tablas_file:
        st.error("Debes subir el archivo TABLAS DOSR TARIFAS.xlsx")
    else:
        try:
            if not COSTOS_FIJOS.exists():
                st.error(f"No encontré el archivo fijo costos_agrupados.xlsx en:\n{COSTOS_FIJOS}")
                st.stop()

            if not CREDENCIALES_FIJAS.exists():
                st.error(f"No encontré el archivo fijo bigqery.json en:\n{CREDENCIALES_FIJAS}")
                st.stop()

            with st.spinner("Ejecutando modelo..."):
                with tempfile.TemporaryDirectory() as tmpdir:
                    tmp_path = Path(tmpdir)

                    # 1. Guardar archivo subido
                    tablas_path = tmp_path / "TABLAS DOSR TARIFAS.xlsx"
                    guardar_archivo_subido(tablas_file, tablas_path)

                    # 2. Copiar archivos fijos
                    copiar_archivo(COSTOS_FIJOS, tmp_path / "costos_agrupados.xlsx")
                    copiar_archivo(CREDENCIALES_FIJAS, tmp_path / "bigqery.json")

                    # 3. Copiar módulos del proyecto
                    for nombre in ARCHIVOS_MODULOS:
                        copiar_archivo(BASE_PROYECTO / nombre, tmp_path / nombre)

                    # 4. Entrar al entorno temporal
                    cwd_original = Path.cwd()
                    os.chdir(tmp_path)

                    try:
                        # limpiar cache de imports para que cada corrida use el tmp actual
                        limpiar_modulos_cache()

                        if str(tmp_path) not in sys.path:
                            sys.path.insert(0, str(tmp_path))

                        pipeline = importlib.import_module("pipeline")

                        # Si luego modificas run_pipeline para recibir top_n, aquí se lo pasamos.
                        resultado = pipeline.run_pipeline()

                        output_file = Path(resultado["modelo_output"])

                        st.success("Modelo ejecutado correctamente.")

                        if output_file.exists():
                            with open(output_file, "rb") as f:
                                st.download_button(
                                    label="Descargar reporte final",
                                    data=f.read(),
                                    file_name=output_file.name,
                                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                                )
                        else:
                            st.warning("La ejecución terminó, pero no encontré el archivo final.")

                    finally:
                        os.chdir(cwd_original)

        except Exception:
            st.error("Ocurrió un error al ejecutar el modelo.")
            st.code(traceback.format_exc())