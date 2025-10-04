"""
Script to train and save all weather prediction models
Run this before deploying the app to Streamlit Cloud
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from models.weather_models import WeatherModels
from utils.data_loader import load_weather_data
import pickle

def main():
    print("="*60)
    print("🚀 TRAINING WEATHER PREDICTION MODELS")
    print("="*60)
    
    # Load data
    print("\n📊 Loading weather data...")
    df = load_weather_data(source='demo')  # Change to 'snowflake' for production
    print(f"✅ Loaded {len(df)} records")
    
    # Initialize models
    print("\n🤖 Initializing models...")
    weather_models = WeatherModels()
    
    # Train all models
    print("\n⚙️ Training all models...")
    weather_models.train_all_models(df)
    
    # Save models
    print("\n💾 Saving models...")
    os.makedirs('models/saved', exist_ok=True)
    weather_models.save_models('models/saved')
    
    # Test prediction
    print("\n🧪 Testing prediction...")
    test_data = {
        'TEMP': 25.0,
        'HUMIDITY': 75.0,
        'DEWPOINT': 20.0,
        'LIQUID_WATER': 0.01,
        'ICE_CONTENT': 0.005,
        'WIND_SPEED': 10.0,
        'SURFACE_PRESSURE': 101.3,
        'TOTAL_MOISTURE': 0.015,
        'DEW_POINT_DEPRESSION': 5.0,
        'HUMIDITY_LIQUID_INTERACTION': 0.75
    }
    
    result = weather_models.predict_rain(test_data)
    print(f"\n📈 Test Prediction:")
    print(f"   Will Rain: {result['will_rain']}")
    print(f"   Probability: {result['probability']:.2%}")
    
    print("\n" + "="*60)
    print("✅ MODEL TRAINING COMPLETE!")
    print("="*60)
    print("\n📁 Models saved in: models/saved/")
    print("🚀 Ready to deploy!")

if __name__ == "__main__":
    main()
