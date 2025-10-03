# final_clean_pipeline.py
from dagster import job, op, get_dagster_logger, Definitions
import pandas as pd
from datetime import datetime

# ==========================
# 1. Ops نظيفة تماماً - بدون Snowflake
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
    
    # أفضل 3 مناطق للصيد
    best_spots = df[df['fishing_potential'] == 'ممتاز'][['latitude', 'longitude']].head(3)
    logger.info(f"📍 أفضل مناطق الصيد: {best_spots.to_dict('records')}")
    
    return stats

@op
def save_analysis_report(stats):
    """حفظ التقرير"""
    logger = get_dagster_logger()
    
    logger.info("💾 حفظ التقرير...")
    logger.info(f"✅ تم الانتهاء من التحليل: {stats}")
    
    return f"تم تحليل {stats['total_records']} منطقة - {stats['excellent_areas']} منطقة ممتازة للصيد"

# ==========================
# 2. Jobs نظيفة - بدون أي mention لـ Snowflake
# ==========================
@job
def marine_analysis_job():
    """تحليل البيانات البحرية الأساسي"""
    data = download_sample_data()
    processed_data = process_marine_data(data)
    analysis_results = generate_report(processed_data)
    save_analysis_report(analysis_results)

@job
def quick_test_job():
    """تست سريع"""
    logger = get_dagster_logger()
    logger.info("🧪 بدء الاختبار السريع...")
    
    data = download_sample_data()
    results = generate_report(data)
    save_analysis_report(results)

# ==========================
# 3. التعريفات النهائية - نظيفة تماماً
# ==========================
defs = Definitions(
    jobs=[marine_analysis_job, quick_test_job]
    # ⭐ لا يوجد resources إطلاقاً
)
