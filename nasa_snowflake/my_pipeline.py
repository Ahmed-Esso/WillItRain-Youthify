import dagster
import earthaccess
import pandas as pd
from snowflake.connector import connect

# المتغيرات المطلوبة
VARIABLES = ["T2M", "QV2M", "T2MDEW", "U10M", "V10M", "PS", "TQV", "SLP", "T2MWET"]

@dagster.op
def extract_variables():
    # login
    earthaccess.login()

    # ابحث عن البيانات (ممكن تغيري الفترة الزمنية)
    results = earthaccess.search_data(
        short_name="MERRA2_400.tavg1_2d_slv_Nx",
        cloud_hosted=True,
        temporal=("2020-01-01", "2020-12-31"),
    )

    datasets = earthaccess.open(results)

    for ds in datasets:
        df = pd.DataFrame({"time": ds["time"].values})
        for var in VARIABLES:
            if var in ds.variables:
                df[var] = ds[var].mean(dim=["lat", "lon"]).values
            else:
                df[var] = None  # لو المتغير مش موجود في granule ده
        yield df


@dagster.op
def load_to_snowflake(dfs):
    conn = connect(
        user="USERNAME",
        password="PASSWORD",
        account="ACCOUNT",
        warehouse="COMPUTE_WH",
        database="CLIMATE",
        schema="PUBLIC",
    )
    cur = conn.cursor()

    # اعملي الجدول لو مش موجود
    cur.execute("""
        CREATE TABLE IF NOT EXISTS climate_data (
            time TIMESTAMP,
            T2M FLOAT,
            QV2M FLOAT,
            T2MDEW FLOAT,
            U10M FLOAT,
            V10M FLOAT,
            PS FLOAT,
            TQV FLOAT,
            SLP FLOAT,
            T2MWET FLOAT
        )
    """)

    # ادخال البيانات
    for df in dfs:
        for _, row in df.iterrows():
            cur.execute(
                """
                INSERT INTO climate_data
                (time, T2M, QV2M, T2MDEW, U10M, V10M, PS, TQV, SLP, T2MWET)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    pd.to_datetime(row["time"]).to_pydatetime(),
                    float(row.get("T2M", None)) if row.get("T2M") is not None else None,
                    float(row.get("QV2M", None)) if row.get("QV2M") is not None else None,
                    float(row.get("T2MDEW", None)) if row.get("T2MDEW") is not None else None,
                    float(row.get("U10M", None)) if row.get("U10M") is not None else None,
                    float(row.get("V10M", None)) if row.get("V10M") is not None else None,
                    float(row.get("PS", None)) if row.get("PS") is not None else None,
                    float(row.get("TQV", None)) if row.get("TQV") is not None else None,
                    float(row.get("SLP", None)) if row.get("SLP") is not None else None,
                    float(row.get("T2MWET", None)) if row.get("T2MWET") is not None else None,
                ),
            )

    cur.close()
    conn.close()


@dagster.job
def nasa_variables_pipeline():
    dfs = extract_variables()
    load_to_snowflake(dfs)


