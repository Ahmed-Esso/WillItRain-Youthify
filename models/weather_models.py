"""
Weather prediction models module
Contains all 6 ML models for weather forecasting
"""

import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor, RandomForestClassifier
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score, accuracy_score
import pickle
import os


class WeatherModels:
    """
    Comprehensive weather prediction models based on NASA climate data
    """
    
    def __init__(self):
        self.models = {
            'fog_visibility': None,
            'precipitation_amount': None,
            'air_quality': None,
            'thermal_comfort': None,
            'rain_prediction': None,
            'storm_intensity': None
        }
        self.is_trained = False
    
    def prepare_fog_visibility_features(self, df):
        """Prepare features for Fog & Visibility Model"""
        df_fog = df.copy()
        df_fog['TEMP_DEW_DIFF'] = df_fog['TEMP'] - df_fog['DEWPOINT']
        df_fog['HUMIDITY_WIND_INTERACTION'] = df_fog['HUMIDITY'] * df_fog['WIND_SPEED']
        df_fog['PRESSURE_HUMIDITY_RATIO'] = df_fog['SURFACE_PRESSURE'] / np.where(
            df_fog['HUMIDITY'] == 0, 1, df_fog['HUMIDITY']
        )
        
        # Target: Visibility Index
        df_fog['VISIBILITY_INDEX'] = (
            (100 - df_fog['HUMIDITY']) * 0.4 +
            df_fog['WIND_SPEED'] * 0.3 +
            df_fog['TEMP_DEW_DIFF'] * 0.3
        )
        
        features = ['TEMP', 'HUMIDITY', 'WIND_SPEED', 'SURFACE_PRESSURE', 'DEWPOINT',
                   'TEMP_DEW_DIFF', 'HUMIDITY_WIND_INTERACTION', 'PRESSURE_HUMIDITY_RATIO']
        
        X = df_fog[features]
        y = df_fog['VISIBILITY_INDEX']
        
        return X, y, features
    
    def prepare_precipitation_features(self, df):
        """Prepare features for Precipitation Amount Model"""
        df_precip = df.copy()
        
        # Calculate total moisture content
        df_precip['TOTAL_MOISTURE'] = df_precip['LIQUID_WATER'] + df_precip['ICE_CONTENT']
        df_precip['MOISTURE_RATIO'] = df_precip['LIQUID_WATER'] / (df_precip['ICE_CONTENT'] + 0.001)
        df_precip['TEMP_HUMIDITY'] = df_precip['TEMP'] * df_precip['HUMIDITY']
        
        # Target: Precipitation amount (mm)
        df_precip['PRECIPITATION_MM'] = (
            df_precip['TOTAL_MOISTURE'] * 100 +
            (df_precip['HUMIDITY'] / 100) * df_precip['LIQUID_WATER'] * 50
        )
        
        features = ['TEMP', 'HUMIDITY', 'LIQUID_WATER', 'ICE_CONTENT', 
                   'WIND_SPEED', 'SURFACE_PRESSURE', 'TOTAL_MOISTURE', 
                   'MOISTURE_RATIO', 'TEMP_HUMIDITY']
        
        X = df_precip[features]
        y = df_precip['PRECIPITATION_MM']
        
        return X, y, features
    
    def prepare_air_quality_features(self, df):
        """Prepare features for Air Quality Model"""
        df_aq = df.copy()
        
        # Air Quality Index calculation
        df_aq['WIND_TEMP_INTERACTION'] = df_aq['WIND_SPEED'] * df_aq['TEMP']
        df_aq['PRESSURE_DEVIATION'] = abs(df_aq['SURFACE_PRESSURE'] - 101.325)
        
        # Target: Air Quality Index (0-100, lower is better)
        df_aq['AIR_QUALITY_INDEX'] = (
            (1 - df_aq['WIND_SPEED'] / 20) * 40 +
            (df_aq['HUMIDITY'] / 100) * 30 +
            (df_aq['PRESSURE_DEVIATION'] / 10) * 30
        ).clip(0, 100)
        
        features = ['TEMP', 'WIND_SPEED', 'HUMIDITY', 'SURFACE_PRESSURE',
                   'WIND_TEMP_INTERACTION', 'PRESSURE_DEVIATION']
        
        X = df_aq[features]
        y = df_aq['AIR_QUALITY_INDEX']
        
        return X, y, features
    
    def prepare_thermal_comfort_features(self, df):
        """Prepare features for Thermal Comfort Model"""
        df_thermal = df.copy()
        
        # Calculate heat index and wind chill
        df_thermal['HEAT_INDEX'] = (
            df_thermal['TEMP'] + 
            0.33 * (df_thermal['HUMIDITY'] / 100) * 6.105 * 
            np.exp(17.27 * df_thermal['TEMP'] / (237.7 + df_thermal['TEMP'])) - 0.70
        )
        
        df_thermal['WIND_CHILL'] = np.where(
            df_thermal['TEMP'] < 10,
            13.12 + 0.6215 * df_thermal['TEMP'] - 
            11.37 * (df_thermal['WIND_SPEED'] ** 0.16) +
            0.3965 * df_thermal['TEMP'] * (df_thermal['WIND_SPEED'] ** 0.16),
            df_thermal['TEMP']
        )
        
        # Comfort Index (0-10, 10 is most comfortable)
        df_thermal['COMFORT_INDEX'] = (
            10 - abs(df_thermal['TEMP'] - 22) * 0.3 -
            abs(df_thermal['HUMIDITY'] - 50) * 0.05 -
            df_thermal['WIND_SPEED'] * 0.2
        ).clip(0, 10)
        
        features = ['TEMP', 'HUMIDITY', 'WIND_SPEED', 'DEWPOINT',
                   'HEAT_INDEX', 'WIND_CHILL']
        
        X = df_thermal[features]
        y = df_thermal['COMFORT_INDEX']
        
        return X, y, features
    
    def prepare_rain_prediction_features(self, df):
        """Prepare features for Rain Prediction (Classification)"""
        df_rain = df.copy()
        
        # Calculate moisture indicators
        df_rain['TOTAL_MOISTURE'] = df_rain['LIQUID_WATER'] + df_rain['ICE_CONTENT']
        df_rain['DEW_POINT_DEPRESSION'] = df_rain['TEMP'] - df_rain['DEWPOINT']
        df_rain['HUMIDITY_LIQUID_INTERACTION'] = df_rain['HUMIDITY'] * df_rain['LIQUID_WATER']
        
        # Target: Will it rain? (Binary classification)
        df_rain['WILL_RAIN'] = (
            (df_rain['TOTAL_MOISTURE'] > 0.01) & 
            (df_rain['HUMIDITY'] > 70) &
            (df_rain['DEW_POINT_DEPRESSION'] < 3)
        ).astype(int)
        
        features = ['TEMP', 'HUMIDITY', 'DEWPOINT', 'LIQUID_WATER', 
                   'ICE_CONTENT', 'WIND_SPEED', 'SURFACE_PRESSURE',
                   'TOTAL_MOISTURE', 'DEW_POINT_DEPRESSION', 
                   'HUMIDITY_LIQUID_INTERACTION']
        
        X = df_rain[features]
        y = df_rain['WILL_RAIN']
        
        return X, y, features
    
    def prepare_storm_intensity_features(self, df):
        """Prepare features for Storm Intensity Model"""
        if 'OMEGA500' not in df.columns:
            raise ValueError("OMEGA500 column not found in data")
        
        df_storm = df.copy()
        
        # Storm indicators
        df_storm['WIND_PRESSURE_INTERACTION'] = df_storm['WIND_SPEED'] * (
            101.325 - df_storm['SURFACE_PRESSURE']
        )
        df_storm['MOISTURE_WIND'] = (
            df_storm['LIQUID_WATER'] + df_storm['ICE_CONTENT']
        ) * df_storm['WIND_SPEED']
        
        # Storm Intensity Index (0-10)
        df_storm['STORM_INTENSITY'] = (
            abs(df_storm['OMEGA500']) * 0.3 +
            df_storm['WIND_SPEED'] * 0.3 +
            (df_storm['LIQUID_WATER'] + df_storm['ICE_CONTENT']) * 100 * 0.2 +
            (100 - df_storm['SURFACE_PRESSURE']) * 0.2
        ).clip(0, 10)
        
        features = ['TEMP', 'WIND_SPEED', 'SURFACE_PRESSURE', 'HUMIDITY',
                   'LIQUID_WATER', 'ICE_CONTENT', 'OMEGA500',
                   'WIND_PRESSURE_INTERACTION', 'MOISTURE_WIND']
        
        X = df_storm[features]
        y = df_storm['STORM_INTENSITY']
        
        return X, y, features
    
    def train_all_models(self, df):
        """Train all 6 weather prediction models"""
        print("🚀 Training all weather prediction models...")
        
        # 1. Fog & Visibility Model
        print("\n1️⃣ Training Fog & Visibility Model...")
        X, y, features = self.prepare_fog_visibility_features(df)
        self.models['fog_visibility'] = {
            'model': RandomForestRegressor(n_estimators=100, random_state=42),
            'features': features
        }
        self.models['fog_visibility']['model'].fit(X, y)
        print(f"   ✅ R² Score: {r2_score(y, self.models['fog_visibility']['model'].predict(X)):.4f}")
        
        # 2. Precipitation Amount Model
        print("\n2️⃣ Training Precipitation Amount Model...")
        X, y, features = self.prepare_precipitation_features(df)
        self.models['precipitation_amount'] = {
            'model': RandomForestRegressor(n_estimators=100, random_state=42),
            'features': features
        }
        self.models['precipitation_amount']['model'].fit(X, y)
        print(f"   ✅ R² Score: {r2_score(y, self.models['precipitation_amount']['model'].predict(X)):.4f}")
        
        # 3. Air Quality Model
        print("\n3️⃣ Training Air Quality Model...")
        X, y, features = self.prepare_air_quality_features(df)
        self.models['air_quality'] = {
            'model': RandomForestRegressor(n_estimators=100, random_state=42),
            'features': features
        }
        self.models['air_quality']['model'].fit(X, y)
        print(f"   ✅ R² Score: {r2_score(y, self.models['air_quality']['model'].predict(X)):.4f}")
        
        # 4. Thermal Comfort Model
        print("\n4️⃣ Training Thermal Comfort Model...")
        X, y, features = self.prepare_thermal_comfort_features(df)
        self.models['thermal_comfort'] = {
            'model': RandomForestRegressor(n_estimators=100, random_state=42),
            'features': features
        }
        self.models['thermal_comfort']['model'].fit(X, y)
        print(f"   ✅ R² Score: {r2_score(y, self.models['thermal_comfort']['model'].predict(X)):.4f}")
        
        # 5. Rain Prediction Model (Classification)
        print("\n5️⃣ Training Rain Prediction Model...")
        X, y, features = self.prepare_rain_prediction_features(df)
        self.models['rain_prediction'] = {
            'model': RandomForestClassifier(n_estimators=100, random_state=42),
            'features': features
        }
        self.models['rain_prediction']['model'].fit(X, y)
        print(f"   ✅ Accuracy: {accuracy_score(y, self.models['rain_prediction']['model'].predict(X)):.4f}")
        
        # 6. Storm Intensity Model
        if 'OMEGA500' in df.columns:
            print("\n6️⃣ Training Storm Intensity Model...")
            X, y, features = self.prepare_storm_intensity_features(df)
            self.models['storm_intensity'] = {
                'model': RandomForestRegressor(n_estimators=100, random_state=42),
                'features': features
            }
            self.models['storm_intensity']['model'].fit(X, y)
            print(f"   ✅ R² Score: {r2_score(y, self.models['storm_intensity']['model'].predict(X)):.4f}")
        else:
            print("\n⚠️ OMEGA500 not available, skipping Storm Intensity Model")
        
        self.is_trained = True
        print("\n✅ All models trained successfully!")
    
    def predict_rain(self, input_data):
        """Predict if it will rain"""
        if not self.is_trained:
            raise ValueError("Models not trained yet!")
        
        model_info = self.models['rain_prediction']
        features = model_info['features']
        
        # Prepare input
        X = pd.DataFrame([input_data])[features]
        
        prediction = model_info['model'].predict(X)[0]
        probability = model_info['model'].predict_proba(X)[0]
        
        return {
            'will_rain': bool(prediction),
            'probability': float(probability[1])
        }
    
    def save_models(self, directory='models/saved'):
        """Save all trained models to disk"""
        os.makedirs(directory, exist_ok=True)
        
        for model_name, model_info in self.models.items():
            if model_info is not None:
                filepath = os.path.join(directory, f'{model_name}.pkl')
                with open(filepath, 'wb') as f:
                    pickle.dump(model_info, f)
        
        print(f"✅ Models saved to {directory}")
    
    def load_models(self, directory='models/saved'):
        """Load trained models from disk"""
        for model_name in self.models.keys():
            filepath = os.path.join(directory, f'{model_name}.pkl')
            if os.path.exists(filepath):
                with open(filepath, 'rb') as f:
                    self.models[model_name] = pickle.load(f)
        
        self.is_trained = True
        print(f"✅ Models loaded from {directory}")
