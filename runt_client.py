from __future__ import annotations

from typing import List
import pandas as pd
from google.cloud import bigquery
from google.oauth2 import service_account

from config import BQ_PROJECT, BQ_CREDENTIALS_FILE


def fetch_runt_by_chasis(lista_chasis: List[str]) -> pd.DataFrame:
    """
    Trae MARCA y LINEA del RUNT para una lista de chasis.
    Retorna DF con columnas: CHASIS, MARCA, LINEA
    """
    if not lista_chasis:
        return pd.DataFrame(columns=["CHASIS", "MARCA", "LINEA"])

    credentials = service_account.Credentials.from_service_account_file(
        str(BQ_CREDENTIALS_FILE),
        scopes=["https://www.googleapis.com/auth/cloud-platform"]
    )

    client = bigquery.Client(credentials=credentials, project=BQ_PROJECT)

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
            bigquery.ArrayQueryParameter("lista_chasis", "STRING", lista_chasis)
        ]
    )

    return client.query(query, job_config=job_config).to_dataframe()