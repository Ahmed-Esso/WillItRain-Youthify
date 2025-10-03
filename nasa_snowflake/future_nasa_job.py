# simple_nasa_pipeline.py
from dagster import job, op, get_dagster_logger
import pandas as pd
import requests
from datetime import datetime

# ==========================
# OPS بسيطة وواضحة
# ==========================
@op
def download_sample_data():
    """تحميل بيانات نموذجية للاختبار"""
    logger = get_dagster_logger()
    logger.info("📥 جاري تحميل بيانات نموذجية...")
    
    # بيانات نموذجية بدلاً من NASA مباشرة (للتجنب المشاكل)
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
    
    logger.info(f"🎣 تم معالجة {len(df)} سجل - أفضل منطقة: {df['fishing_potential'].value_counts().to_dict()}")
    return df

@op
def analyze_results(df):
    """تحليل النتائج وعمل تقرير"""
    logger = get_dagster_logger()
    
    if df.empty:
        return "لا توجد بيانات للتحليل"
    
    # إحصائيات أساسية
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
    """حفظ التقرير (يمكن تعديله لحفظ في Snowflake لاحقاً)"""
    logger = get_dagster_logger()
    
    logger.info("💾 حفظ التقرير...")
    logger.info(f"✅ تم الانتهاء من التحليل: {stats}")
    
    return f"تم تحليل {stats['total_records']} منطقة - {stats['excellent_areas']} منطقة ممتازة للصيد"

# ==========================
# JOBS بسيطة بدون تعقيد
# ==========================
@job
def marine_analysis_job():
    """تحليل البيانات البحرية الأساسي"""
    data = download_sample_data()
    processed_data = process_marine_data(data)
    analysis_results = analyze_results(processed_data)
    save_analysis_report(analysis_results)

@job
def quick_test_job():
    """تست سريع"""
    logger = get_dagster_logger()
    logger.info("🧪 بدء الاختبار السريع...")
    
    data = download_sample_data()
    results = analyze_results(data)
    save_analysis_report(results)

# ==========================
# الإصدار مع بيانات حقيقية (لاحقاً)
# ==========================
@op
def get_real_nasa_data():
    """جلب بيانات حقيقية من NASA (للتطوير المستقبلي)"""
    logger = get_dagster_logger()
    
    try:
        # هنا يمكن إضافة كود جلب البيانات الحقيقية لاحقاً
        logger.info("🌍 جاري محاولة جلب بيانات NASA...")
        
        # بيانات نموذجية مؤقتاً
        sample_real_data = {
            'date': [datetime.now().date()],
            'source': ['NASA_SIMULATION'],
            'status': ['بيانات تجريبية - جاهز للبيانات الحقيقية']
        }
        
        df = pd.DataFrame(sample_real_data)
        return df
        
    except Exception as e:
        logger.error(f"❌ خطأ في جلب البيانات: {e}")
        return pd.DataFrame()

@job
def future_nasa_job():
    """هذا الjob جاهز للبيانات الحقيقية مستقبلاً"""
    real_data = get_real_nasa_data()
    processed = process_marine_data(real_data)
    analyze_results(processed)
