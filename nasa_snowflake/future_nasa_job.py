# working_pipeline.py
from dagster import job, op, get_dagster_logger, Definitions, EnvVar
from dagster import ConfigurableResource
import pandas as pd
from datetime import datetime
import snowflake.connector

# ==========================
# 1. Snowflake Resource - الطريقة الصحيحة
# ==========================
class SnowflakeResource(ConfigurableResource):
    account: str = "KBZQPZO-WX06551"
    user: str = "A7MEDESSO" 
    password: str = "Ahmedesso@2005"
    warehouse: str = "NASA_WH"
    database: str = "NASA_DB" 
    schema: str = "PUBLIC"
    role: str = "ACCOUNTADMIN"

    def get_connection(self):
        return snowflake.connector.connect(
            account=self.account,
            user=self.user,
            password=self.password,
            warehouse=self.warehouse,
            database=self.database,
            schema=self.schema,
            role=self.role
        )

# ==========================
# 2. Ops بسيطة بدون تعقيد
# ==========================
@op
def download_sample_data():
    """تحميل بيانات نموذجية"""
    logger = get_dagster_logger()
    logger.info("📥 جاري تحميل بيانات نموذجية...")
    
    sample_data = {
        'date': ['2022-01-01', '2022-01-02', '2022-01-03'],
        'latitude': [30.0, 30.5, 31.0],
        'longitude': [32.0, 32.5, 33.0], 
        'chlorophyll': [0.25, 0.30, 0.28],
        'temperature': [22.5, 23.1, 22.8]
    }
    
    df = pd.DataFrame(sample_data)
    logger.info(f"✅ تم تحميل {len(df)} سجل نموذجي")
    return df

@op
def process_marine_data(df):
    """معالجة البيانات البحرية"""
    logger = get_dagster_logger()
    
    if df.empty:
        return df
    
    # إضافة عمود جديد للجودة
    df['data_quality'] = 'high'
    
    # تصنيف مناطق الصيد
    def classify_fishing_area(chlorophyll, temperature):
        if chlorophyll > 0.25 and temperature > 22:
            return 'ممتاز'
        elif chlorophyll > 0.20:
            return 'جيد'
        else:
            return 'ضعيف'
    
    df['fishing_potential'] = df.apply(
        lambda row: classify_fishing_area(row['chlorophyll'], row['temperature']), 
        axis=1
    )
    
    logger.info(f"🎣 تم معالجة {len(df)} سجل")
    return df

@op
def load_to_snowflake(df, snowflake: SnowflakeResource):
    """تحميل البيانات إلى Snowflake"""
    logger = get_dagster_logger()
    
    if df.empty:
        logger.info("⏭️ لا توجد بيانات للتحميل")
        return "skipped"
    
    conn = None
    try:
        conn = snowflake.get_connection()
        cur = conn.cursor()
        
        # إنشاء الجدول إذا لم يكن موجوداً
        cur.execute("""
            CREATE TABLE IF NOT EXISTS marine_analysis_results (
                date DATE,
                latitude FLOAT,
                longitude FLOAT,
                chlorophyll FLOAT,
                temperature FLOAT,
                data_quality STRING,
                fishing_potential STRING,
                loaded_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
            )
        """)
        
        # تحضير البيانات للإدخال
        data_to_insert = [
            (
                row["date"],
                float(row["latitude"]),
                float(row["longitude"]),
                float(row["chlorophyll"]),
                float(row["temperature"]),
                row["data_quality"],
                row["fishing_potential"]
            )
            for _, row in df.iterrows()
        ]
        
        # إدخال البيانات
        insert_query = """
            INSERT INTO marine_analysis_results 
            (date, latitude, longitude, chlorophyll, temperature, data_quality, fishing_potential)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """
        
        cur.executemany(insert_query, data_to_insert)
        conn.commit()
        
        logger.info(f"✅ تم تحميل {len(df)} سجل إلى Snowflake بنجاح")
        return f"success_{len(df)}_records"
        
    except Exception as e:
        logger.error(f"❌ خطأ في التحميل إلى Snowflake: {e}")
        return "failed"
    finally:
        if conn:
            cur.close()
            conn.close()

@op
def generate_report(df):
    """إنشاء تقرير النتائج"""
    logger = get_dagster_logger()
    
    if df.empty:
        return "لا توجد بيانات للتقرير"
    
    stats = {
        'total_records': len(df),
        'excellent_areas': len(df[df['fishing_potential'] == 'ممتاز']),
        'good_areas': len(df[df['fishing_potential'] == 'جيد']),
        'avg_chlorophyll': df['chlorophyll'].mean(),
        'avg_temperature': df['temperature'].mean(),
        'processing_time': datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }
    
    logger.info(f"📊 التقرير: {stats}")
    
    return stats

# ==========================
# 3. Jobs - مع تعريف الResources
# ==========================
@job
def marine_analysis_with_snowflake():
    """تحليل البيانات البحرية مع Snowflake"""
    data = download_sample_data()
    processed_data = process_marine_data(data)
    load_result = load_to_snowflake(processed_data)
    report = generate_report(processed_data)

@job
def simple_analysis_only():
    """تحليل بسيط بدون Snowflake"""
    data = download_sample_data()
    processed_data = process_marine_data(data)
    generate_report(processed_data)

# ==========================
# 4. التعريفات النهائية - الجزء الأهم!
# ==========================
defs = Definitions(
    jobs=[marine_analysis_with_snowflake, simple_analysis_only],
    resources={
        "snowflake": SnowflakeResource()  # هذا هو المفتاح!
    }
)
