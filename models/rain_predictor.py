"""
Rain prediction module - Main model for the app
"""

import numpy as np
import pandas as pd
from datetime import datetime


class RainPredictor:
    """
    Main rain prediction class for the weather app
    """
    
    def __init__(self, weather_models=None):
        self.weather_models = weather_models
    
    def predict(self, weather_data):
        """
        Predict if it will rain based on weather data
        
        Parameters:
        -----------
        weather_data : dict
            Dictionary containing weather parameters:
            - temp: Temperature (°C)
            - humidity: Humidity (%)
            - dewpoint: Dew point (°C)
            - liquid_water: Liquid water content
            - ice_content: Ice content
            - wind_speed: Wind speed (m/s)
            - surface_pressure: Surface pressure (kPa)
        
        Returns:
        --------
        dict with prediction results
        """
        if self.weather_models is None:
            # Fallback to simple rule-based prediction
            return self._simple_prediction(weather_data)
        
        # Use ML model
        return self.weather_models.predict_rain(weather_data)
    
    def _simple_prediction(self, data):
        """Simple rule-based prediction when ML model is not available"""
        # Calculate moisture index
        total_moisture = data.get('liquid_water', 0) + data.get('ice_content', 0)
        humidity = data.get('humidity', 50)
        temp = data.get('temp', 20)
        dewpoint = data.get('dewpoint', 15)
        
        # Calculate dew point depression
        dew_depression = temp - dewpoint
        
        # Rain probability calculation
        rain_score = 0
        
        # High moisture content
        if total_moisture > 0.01:
            rain_score += 30
        elif total_moisture > 0.005:
            rain_score += 15
        
        # High humidity
        if humidity > 80:
            rain_score += 30
        elif humidity > 70:
            rain_score += 20
        elif humidity > 60:
            rain_score += 10
        
        # Low dew point depression
        if dew_depression < 2:
            rain_score += 25
        elif dew_depression < 4:
            rain_score += 15
        
        # Wind speed consideration
        wind_speed = data.get('wind_speed', 5)
        if 5 < wind_speed < 15:
            rain_score += 15
        
        probability = min(rain_score / 100, 0.95)
        will_rain = probability > 0.6
        
        return {
            'will_rain': will_rain,
            'probability': probability,
            'confidence': probability if will_rain else (1 - probability)
        }
    
    def get_recommendation(self, prediction):
        """Get user-friendly recommendation based on prediction"""
        if prediction['will_rain']:
            prob = prediction['probability']
            if prob > 0.8:
                return "🌧️ High chance of rain! Definitely bring an umbrella."
            elif prob > 0.6:
                return "☔ Rain is likely. Better pack an umbrella just in case."
            else:
                return "🌦️ Some chance of rain. You might want to bring an umbrella."
        else:
            return "☀️ No rain expected! Perfect day for outdoor activities."
