from google.cloud import bigquery

client = bigquery.Client(project="meli-bi-data")

query = """
SELECT *
FROM `meli-bi-data.WHOWNER.BT_KPI_PRODUTIVIDADE_COMPRAS__COE`
LIMIT 5
"""

df = client.query(query).to_dataframe()

print("=== COLUNAS ===")
for col in df.columns:
    print(f"  {col} — {df[col].dtype}")

print("\n=== AMOSTRA DE DADOS ===")
print(df.to_string())
