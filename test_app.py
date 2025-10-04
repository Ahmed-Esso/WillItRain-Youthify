"""
Test script to verify all components are working
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

def test_imports():
    """Test if all required packages can be imported"""
    print("🔍 Testing imports...")
    try:
        import streamlit
        import pandas
        import numpy
        import sklearn
        import plotly
        print("   ✅ All core packages imported successfully")
        return True
    except ImportError as e:
        print(f"   ❌ Import error: {e}")
        return False

def test_data_loader():
    """Test data loading functionality"""
    print("\n🔍 Testing data loader...")
    try:
        from utils.data_loader import load_weather_data, generate_demo_data
        df = generate_demo_data(days=10)
        print(f"   ✅ Generated {len(df)} demo records")
        return True
    except Exception as e:
        print(f"   ❌ Data loader error: {e}")
        return False

def test_models():
    """Test model initialization"""
    print("\n🔍 Testing models...")
    try:
        from models.weather_models import WeatherModels
        from models.rain_predictor import RainPredictor
        
        weather_models = WeatherModels()
        rain_predictor = RainPredictor()
        
        print("   ✅ Models initialized successfully")
        return True
    except Exception as e:
        print(f"   ❌ Model error: {e}")
        return False

def test_visualizations():
    """Test visualization functions"""
    print("\n🔍 Testing visualizations...")
    try:
        from utils.visualizations import (
            create_temperature_chart,
            create_weather_gauge,
            create_correlation_heatmap
        )
        print("   ✅ Visualization functions loaded")
        return True
    except Exception as e:
        print(f"   ❌ Visualization error: {e}")
        return False

def main():
    print("="*60)
    print("🧪 RUNNING TESTS")
    print("="*60)
    
    tests = [
        test_imports,
        test_data_loader,
        test_models,
        test_visualizations
    ]
    
    results = []
    for test in tests:
        results.append(test())
    
    print("\n" + "="*60)
    print("📊 TEST RESULTS")
    print("="*60)
    
    passed = sum(results)
    total = len(results)
    
    print(f"\n✅ Passed: {passed}/{total}")
    
    if passed == total:
        print("\n🎉 All tests passed! Ready to run the app.")
        print("\n🚀 Run: streamlit run app.py")
    else:
        print("\n⚠️ Some tests failed. Please check the errors above.")
    
    return passed == total

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
