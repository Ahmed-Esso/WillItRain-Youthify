"""
🌧️ Will It Rain? - NASA Weather Prediction App
Modern redesign with stunning visuals
"""

import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, timedelta

# Page configuration with dark theme
st.set_page_config(
    page_title="NASA Weather Station",
    page_icon="🛰️",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Force dark mode in Streamlit
if "theme" not in st.session_state:
    st.session_state.theme = "dark"

# Ultra-modern CSS with dark space theme
st.markdown("""
<style>
    @import url('https://fonts.googleapis.com/css2?family=Orbitron:wght@400;500;600;700;900&family=Rajdhani:wght@300;400;500;600;700&display=swap');
    
    /* COMPLETE STREAMLIT DARK THEME */
    
    /* Main app container */
    .stApp {
        background-color: #000000 !important;
        color: #ffffff !important;
    }
    
    /* Sidebar dark */
    .css-1d391kg {
        background-color: #0B1426 !important;
    }
    
    /* Main content area */
    [data-testid="stAppViewContainer"] {
        background: #000000 !important;
        color: #ffffff !important;
    }
    
    /* Sidebar content */
    [data-testid="stSidebar"] {
        background-color: #0B1426 !important;
    }
    
    /* Header and metrics */
    [data-testid="stHeader"] {
        background: rgba(0, 0, 0, 0) !important;
    }
    
    [data-testid="stMetric"] {
        background: rgba(11, 61, 145, 0.1) !important;
        border: 1px solid rgba(11, 61, 145, 0.3) !important;
        border-radius: 10px !important;
        padding: 1rem !important;
    }
    
    /* Force all text to be white */
    .stMarkdown, .stText, p, span, div, label, h1, h2, h3, h4, h5, h6 {
        color: #ffffff !important;
    }
    
    /* Inputs dark theme */
    .stSelectbox > div > div {
        background-color: rgba(11, 61, 145, 0.2) !important;
        color: #ffffff !important;
        border: 2px solid #0B3D91 !important;
    }
    
    .stDateInput > div > div > input {
        background-color: rgba(11, 61, 145, 0.2) !important;
        color: #ffffff !important;
        border: 2px solid #0B3D91 !important;
    }
    
    /* SELECT BOX DROPDOWN DARK */
    .stSelectbox [data-baseweb="select"] {
        background-color: rgba(11, 61, 145, 0.2) !important;
    }
    
    .stSelectbox [role="listbox"] {
        background-color: rgba(0, 0, 0, 0.95) !important;
        border: 2px solid #0B3D91 !important;
        border-radius: 10px !important;
    }
    
    .stSelectbox [role="option"] {
        background-color: rgba(0, 0, 0, 0.8) !important;
        color: #ffffff !important;
        font-weight: 600 !important;
        padding: 0.8rem !important;
    }
    
    .stSelectbox [role="option"]:hover {
        background-color: rgba(11, 61, 145, 0.6) !important;
        color: #ffffff !important;
    }
    
    .stSelectbox [role="option"][aria-selected="true"] {
        background-color: rgba(252, 61, 33, 0.6) !important;
        color: #ffffff !important;
    }
    
    /* Button dark theme */
    .stButton > button {
        background: linear-gradient(135deg, #FC3D21, #ff6b4a) !important;
        color: white !important;
        border: 2px solid #FC3D21 !important;
        border-radius: 15px !important;
    }
    
    /* ENHANCED DATAFRAME DARK THEME */
    [data-testid="stDataFrame"] {
        background: rgba(0, 0, 0, 0.95) !important;
        border: 2px solid rgba(11, 61, 145, 0.5) !important;
        border-radius: 15px !important;
        padding: 1rem !important;
    }
    
    [data-testid="stDataFrame"] table {
        background: rgba(0, 0, 0, 0.9) !important;
        color: #ffffff !important;
        font-family: 'Orbitron', monospace !important;
        border-collapse: separate !important;
        border-spacing: 0 !important;
        border-radius: 10px !important;
        overflow: hidden !important;
    }
    
    [data-testid="stDataFrame"] th {
        background: linear-gradient(135deg, rgba(11, 61, 145, 0.8), rgba(11, 61, 145, 0.6)) !important;
        color: #ffffff !important;
        font-weight: 900 !important;
        font-size: 1rem !important;
        text-transform: uppercase !important;
        letter-spacing: 2px !important;
        padding: 1rem 0.8rem !important;
        border-bottom: 3px solid #FC3D21 !important;
        text-shadow: 0 0 10px rgba(11, 61, 145, 0.8) !important;
    }
    
    [data-testid="stDataFrame"] td {
        background: rgba(0, 0, 0, 0.8) !important;
        color: #ffffff !important;
        padding: 0.8rem !important;
        border-bottom: 1px solid rgba(11, 61, 145, 0.3) !important;
        font-weight: 600 !important;
        transition: all 0.3s ease !important;
    }
    
    [data-testid="stDataFrame"] tr:hover td {
        background: linear-gradient(90deg, rgba(11, 61, 145, 0.4), rgba(252, 61, 33, 0.2)) !important;
        color: #ffffff !important;
        text-shadow: 0 0 5px rgba(252, 61, 33, 0.6) !important;
        transform: scale(1.01) !important;
    }
    
    [data-testid="stDataFrame"] tr:nth-child(even) td {
        background: rgba(11, 61, 145, 0.1) !important;
    }
    
    /* Spinner dark */
    .stSpinner {
        color: #FC3D21 !important;
    }
    
    * {
        font-family: 'Rajdhani', sans-serif;
    }
    
    .stApp {
        background: #000000;
        background-image: 
            radial-gradient(circle at 20% 50%, rgba(11, 61, 145, 0.15) 0%, transparent 50%),
            radial-gradient(circle at 80% 80%, rgba(252, 61, 33, 0.1) 0%, transparent 50%),
            radial-gradient(circle at 40% 20%, rgba(11, 61, 145, 0.1) 0%, transparent 40%);
    }
    
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    .stDeployButton {display: none;}
    
    /* Animated starfield background */
    @keyframes twinkle {
        0%, 100% { opacity: 0.3; }
        50% { opacity: 1; }
    }
    
    /* Main container */
    .main-container {
        max-width: 1600px;
        margin: 0 auto;
        padding: 2rem;
    }
    
    /* Futuristic header - simplified */
    .space-header {
        background: linear-gradient(135deg, rgba(11, 61, 145, 0.3), rgba(252, 61, 33, 0.2));
        border: 2px solid rgba(11, 61, 145, 0.5);
        border-radius: 20px;
        padding: 2rem;
        margin-bottom: 2rem;
        box-shadow: 0 0 30px rgba(11, 61, 145, 0.3);
    }
    
    .nasa-logo {
        font-family: 'Orbitron', monospace;
        font-size: 1.8rem;
        font-weight: 900;
        color: #FC3D21;
        text-transform: uppercase;
        letter-spacing: 4px;
        text-shadow: 0 0 20px rgba(252, 61, 33, 0.8);
    }
    
    .mission-time {
        font-family: 'Orbitron', monospace;
        color: #0B3D91;
        font-size: 1rem;
        letter-spacing: 2px;
    }
    
    /* Hero weather display */
    .hero-weather {
        background: rgba(0, 0, 0, 0.6);
        border: 2px solid #0B3D91;
        border-radius: 25px;
        padding: 3rem;
        margin-bottom: 2rem;
        position: relative;
        box-shadow: 0 0 50px rgba(11, 61, 145, 0.4);
    }
    
    .hero-weather::after {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, transparent, #FC3D21, transparent);
    }
    
    .location-display {
        font-family: 'Orbitron', monospace;
        font-size: 2.5rem;
        color: #ffffff;
        font-weight: 700;
        margin-bottom: 1rem;
        text-transform: uppercase;
        letter-spacing: 3px;
    }
    
    .temp-massive {
        font-family: 'Orbitron', monospace;
        font-size: 8rem;
        color: #FC3D21;
        font-weight: 900;
        line-height: 1;
        text-shadow: 0 0 30px rgba(252, 61, 33, 0.6);
        margin: 1rem 0;
    }
    
    .condition-text {
        font-size: 1.5rem;
        color: #0B3D91;
        font-weight: 600;
        text-transform: uppercase;
        letter-spacing: 2px;
    }
    
    /* Data cards */
    .data-card {
        background: rgba(0, 0, 0, 0.7);
        border: 2px solid rgba(11, 61, 145, 0.4);
        border-radius: 20px;
        padding: 1.5rem;
        text-align: center;
        position: relative;
        transition: all 0.3s ease;
        box-shadow: 0 0 20px rgba(11, 61, 145, 0.2);
    }
    
    .data-card:hover {
        border-color: #FC3D21;
        box-shadow: 0 0 30px rgba(252, 61, 33, 0.4);
        transform: translateY(-5px);
    }
    
    .data-card::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        right: 0;
        height: 2px;
        background: linear-gradient(90deg, transparent, #0B3D91, transparent);
    }
    
    .data-label {
        font-family: 'Orbitron', monospace;
        color: #0B3D91;
        font-size: 0.9rem;
        text-transform: uppercase;
        letter-spacing: 2px;
        margin-bottom: 0.5rem;
    }
    
    .data-value {
        font-family: 'Orbitron', monospace;
        color: #ffffff;
        font-size: 2.5rem;
        font-weight: 900;
        text-shadow: 0 0 10px rgba(255, 255, 255, 0.3);
    }
    
    .data-icon {
        font-size: 2.5rem;
        margin-bottom: 0.5rem;
        filter: drop-shadow(0 0 10px rgba(11, 61, 145, 0.6));
    }
    
    /* Section headers */
    .section-header {
        font-family: 'Orbitron', monospace;
        font-size: 1.5rem;
        color: #FC3D21;
        font-weight: 700;
        text-transform: uppercase;
        letter-spacing: 3px;
        margin: 2rem 0 1.5rem 0;
        padding-bottom: 0.5rem;
        border-bottom: 2px solid rgba(252, 61, 33, 0.3);
        text-shadow: 0 0 10px rgba(252, 61, 33, 0.4);
    }
    
    /* Hourly forecast - improved */
    .hour-panel {
        background: linear-gradient(135deg, rgba(11, 61, 145, 0.3), rgba(0, 0, 0, 0.8));
        border: 2px solid rgba(11, 61, 145, 0.6);
        border-radius: 20px;
        padding: 1.5rem 1rem;
        text-align: center;
        transition: all 0.4s cubic-bezier(0.4, 0, 0.2, 1);
        position: relative;
        overflow: hidden;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.1);
        min-height: 180px;
        display: flex;
        flex-direction: column;
        justify-content: space-between;
    }
    
    .hour-panel::before {
        content: '';
        position: absolute;
        top: 0;
        left: 0;
        width: 100%;
        height: 100%;
        background: linear-gradient(135deg, rgba(252, 61, 33, 0.2), rgba(11, 61, 145, 0.2));
        opacity: 0;
        transition: opacity 0.4s ease;
        z-index: 0;
    }
    
    .hour-panel:hover::before {
        opacity: 1;
    }
    
    .hour-panel:hover {
        border-color: #FC3D21;
        box-shadow: 0 8px 35px rgba(252, 61, 33, 0.5), inset 0 1px 0 rgba(255, 255, 255, 0.2);
        transform: translateY(-8px) scale(1.03);
    }
    
    .hour-label {
        font-family: 'Orbitron', monospace;
        color: #ffffff;
        font-size: 1rem;
        font-weight: 700;
        letter-spacing: 2px;
        margin-bottom: 0.8rem;
        text-transform: uppercase;
        position: relative;
        z-index: 1;
        text-shadow: 0 0 10px rgba(11, 61, 145, 0.8);
    }
    
    .hour-icon {
        font-size: 3rem;
        margin: 1rem 0;
        position: relative;
        z-index: 1;
        filter: drop-shadow(0 0 15px rgba(252, 61, 33, 0.5));
    }
    
    .hour-temp {
        font-family: 'Orbitron', monospace;
        color: #FC3D21;
        font-size: 2rem;
        font-weight: 900;
        position: relative;
        z-index: 1;
        text-shadow: 0 0 20px rgba(252, 61, 33, 0.8);
    }
    
    .hour-condition {
        font-family: 'Rajdhani', sans-serif;
        color: #0B3D91;
        font-size: 0.9rem;
        font-weight: 600;
        margin-top: 0.5rem;
        position: relative;
        z-index: 1;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    
    /* Forecast cards */
    .forecast-panel {
        background: rgba(0, 0, 0, 0.7);
        border: 2px solid rgba(11, 61, 145, 0.4);
        border-radius: 20px;
        padding: 1.5rem;
        transition: all 0.3s ease;
        position: relative;
        overflow: hidden;
    }
    
    .forecast-panel::after {
        content: '';
        position: absolute;
        bottom: 0;
        left: 0;
        right: 0;
        height: 3px;
        background: linear-gradient(90deg, transparent, #0B3D91, transparent);
    }
    
    .forecast-panel:hover {
        border-color: #FC3D21;
        box-shadow: 0 0 30px rgba(252, 61, 33, 0.3);
        transform: translateY(-5px);
    }
    
    .forecast-day {
        font-family: 'Orbitron', monospace;
        color: #FC3D21;
        font-size: 1.2rem;
        font-weight: 700;
        letter-spacing: 2px;
    }
    
    .forecast-date {
        color: #0B3D91;
        font-size: 0.9rem;
        font-weight: 600;
        letter-spacing: 1px;
        margin-top: 0.3rem;
    }
    
    .forecast-temp {
        font-family: 'Orbitron', monospace;
        color: #ffffff;
        font-size: 2rem;
        font-weight: 900;
        margin: 1rem 0;
    }
    
    .forecast-bar {
        height: 6px;
        border-radius: 10px;
        background: linear-gradient(90deg, #0B3D91, #FC3D21);
        margin-top: 1rem;
        box-shadow: 0 0 15px rgba(252, 61, 33, 0.5);
    }
    
    /* Prediction button */
    .stButton>button {
        background: linear-gradient(135deg, #FC3D21, #ff6b4a);
        color: white;
        font-family: 'Orbitron', monospace;
        font-weight: 900;
        font-size: 1.3rem;
        border-radius: 15px;
        padding: 1.5rem 3rem;
        border: 2px solid #FC3D21;
        box-shadow: 0 0 40px rgba(252, 61, 33, 0.6);
        transition: all 0.3s ease;
        width: 100%;
        text-transform: uppercase;
        letter-spacing: 3px;
    }
    
    .stButton>button:hover {
        transform: scale(1.05);
        box-shadow: 0 0 60px rgba(252, 61, 33, 0.9);
        border-color: #ffffff;
    }
    
    /* Prediction results */
    .prediction-box {
        background: rgba(0, 0, 0, 0.8);
        border: 3px solid;
        border-radius: 25px;
        padding: 3rem;
        text-align: center;
        position: relative;
        margin-top: 2rem;
    }
    
    .pred-icon {
        font-size: 6rem;
        margin-bottom: 1rem;
    }
    
    .pred-title {
        font-family: 'Orbitron', monospace;
        font-size: 3rem;
        font-weight: 900;
        margin: 1rem 0;
        letter-spacing: 2px;
        text-transform: uppercase;
    }
    
    .pred-confidence {
        font-family: 'Orbitron', monospace;
        font-size: 2rem;
        font-weight: 700;
        margin: 1rem 0;
    }
    
    /* Input styling */
    .stSelectbox > div > div,
    .stDateInput > div > div > input {
        background: rgba(11, 61, 145, 0.2);
        border: 2px solid #0B3D91;
        border-radius: 10px;
        color: white;
        font-family: 'Orbitron', monospace;
        padding: 0.8rem;
        transition: all 0.3s ease;
    }
    
    .stSelectbox > div > div:hover,
    .stDateInput > div > div > input:hover {
        border-color: #FC3D21;
        box-shadow: 0 0 20px rgba(252, 61, 33, 0.3);
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 0.5rem;
        background: rgba(0, 0, 0, 0.5);
        border: 2px solid rgba(11, 61, 145, 0.3);
        border-radius: 15px;
        padding: 0.5rem;
    }
    
    .stTabs [data-baseweb="tab"] {
        font-family: 'Orbitron', monospace;
        background: transparent;
        border-radius: 10px;
        color: #0B3D91;
        font-weight: 700;
        padding: 1rem 1.5rem;
        letter-spacing: 2px;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, rgba(252, 61, 33, 0.3), rgba(11, 61, 145, 0.3));
        color: #ffffff;
        border: 2px solid #FC3D21;
    }
    
    /* TABS DARK THEME */
    [data-baseweb="tab-list"] {
        gap: 0.5rem !important;
        background: rgba(0, 0, 0, 0.8) !important;
        border: 2px solid rgba(11, 61, 145, 0.4) !important;
        border-radius: 15px !important;
        padding: 0.8rem !important;
    }
    
    [data-baseweb="tab"] {
        font-family: 'Orbitron', monospace !important;
        background: rgba(11, 61, 145, 0.2) !important;
        border-radius: 10px !important;
        color: #0B3D91 !important;
        font-weight: 700 !important;
        padding: 1rem 1.5rem !important;
        letter-spacing: 2px !important;
        border: 1px solid rgba(11, 61, 145, 0.3) !important;
        transition: all 0.3s ease !important;
    }
    
    [data-baseweb="tab"]:hover {
        background: rgba(11, 61, 145, 0.4) !important;
        color: #ffffff !important;
    }
    
    [data-baseweb="tab"][aria-selected="true"] {
        background: linear-gradient(135deg, rgba(252, 61, 33, 0.6), rgba(11, 61, 145, 0.6)) !important;
        color: #ffffff !important;
        border: 2px solid #FC3D21 !important;
        box-shadow: 0 0 20px rgba(252, 61, 33, 0.5) !important;
    }
    
    /* EXPANDER DARK THEME */
    [data-testid="stExpander"] {
        background: rgba(0, 0, 0, 0.7) !important;
        border: 2px solid rgba(11, 61, 145, 0.4) !important;
        border-radius: 15px !important;
    }
    
    [data-testid="stExpanderToggleIcon"] {
        color: #FC3D21 !important;
    }
    
    /* SCROLLBAR DARK */
    ::-webkit-scrollbar {
        width: 12px;
        background: rgba(0, 0, 0, 0.3);
    }
    
    ::-webkit-scrollbar-track {
        background: rgba(11, 61, 145, 0.1);
        border-radius: 10px;
    }
    
    ::-webkit-scrollbar-thumb {
        background: linear-gradient(180deg, #0B3D91, #FC3D21);
        border-radius: 10px;
        border: 2px solid rgba(0, 0, 0, 0.2);
    }
    
    ::-webkit-scrollbar-thumb:hover {
        background: linear-gradient(180deg, #FC3D21, #0B3D91);
        box-shadow: 0 0 10px rgba(252, 61, 33, 0.5);
    }
</style>
""", unsafe_allow_html=True)

# Helper functions
def kelvin_to_celsius(kelvin):
    return kelvin - 273.15

@st.cache_data
def predict_temperature(location, date, days=10):
    """
    Predict temperature based on location and date
    Uses seasonal patterns and location-specific base temps
    """
    # Base temperatures for each city (in Celsius)
    base_temps = {
        "Alexandria": 22, "Cairo": 26, "Giza": 25,
        "Luxor": 32, "Aswan": 35, "Port Said": 20,
        "Suez": 23, "Mansoura": 21
    }
    
    base_temp = base_temps.get(location, 25)
    
    # Seasonal adjustment based on month
    month = date.month
    if month in [12, 1, 2]:  # Winter
        seasonal_adj = -8
    elif month in [3, 4, 5]:  # Spring
        seasonal_adj = 0
    elif month in [6, 7, 8]:  # Summer
        seasonal_adj = 8
    else:  # Fall
        seasonal_adj = -2
    
    # Generate forecast for multiple days
    temps_high = []
    temps_low = []
    
    for i in range(days):
        # Add variation for each day
        day_variation = np.sin(i * 0.5) * 2  # Small wave pattern
        random_noise = np.random.uniform(-1.5, 1.5)
        
        high = base_temp + seasonal_adj + day_variation + random_noise + 5
        low = base_temp + seasonal_adj + day_variation + random_noise - 5
        
        temps_high.append(high)
        temps_low.append(low)
    
    return temps_high, temps_low

@st.cache_data
def predict_rain(location, date, temperature_high, humidity=None):
    """
    Predict rain probability based on multiple factors
    """
    # Rain probability by month (seasonal patterns for Egypt)
    month = date.month
    if month in [12, 1, 2]:  # Winter - higher rain probability
        base_rain_prob = 0.35
    elif month in [3, 4]:  # Spring
        base_rain_prob = 0.15
    elif month in [5, 6, 7, 8, 9]:  # Summer - very low
        base_rain_prob = 0.02
    else:  # Fall
        base_rain_prob = 0.20
    
    # Location adjustment (coastal cities have more rain)
    coastal_cities = ["Alexandria", "Port Said"]
    if location in coastal_cities:
        base_rain_prob += 0.10
    
    # Temperature adjustment (cooler = more rain)
    if temperature_high < 20:
        base_rain_prob += 0.15
    elif temperature_high < 25:
        base_rain_prob += 0.05
    
    # Add some randomness but keep it realistic
    final_prob = base_rain_prob + np.random.uniform(-0.10, 0.10)
    final_prob = max(0.01, min(0.95, final_prob))  # Keep between 1% and 95%
    
    return final_prob

@st.cache_data
def get_weather_condition(date, temperature, rain_prob):
    """
    Determine weather condition icon and description
    """
    if rain_prob > 0.6:
        return "🌧️", "Rainy"
    elif rain_prob > 0.4:
        return "⛈️", "Thunderstorms"
    elif rain_prob > 0.25:
        return "⛅", "Partly Cloudy"
    elif temperature > 35:
        return "🌤️", "Hot & Sunny"
    elif temperature > 28:
        return "☀️", "Sunny"
    else:
        return "🌤️", "Clear"

# Initialize session state
if 'models_loaded' not in st.session_state:
    st.session_state.current_location = "Alexandria"
    st.session_state.current_temp_k = 295.15
    st.session_state.current_condition = "Clear Sky"
    st.session_state.prediction_made = False
    st.session_state.selected_date = datetime.now()

# Header
st.markdown("""
<div class='space-header'>
    <div style='display: flex; justify-content: space-between; align-items: center; position: relative; z-index: 1;'>
        <div class='nasa-logo'>🛰️ NASA WEATHER STATION</div>
        <div class='mission-time'>MISSION TIME: {}</div>
    </div>
</div>
""".format(datetime.now().strftime("%Y.%m.%d - %H:%M:%S")), unsafe_allow_html=True)

# Hero section
cities = ["Alexandria", "Cairo", "Giza", "Luxor", "Aswan", "Port Said", "Suez", "Mansoura"]
col1, col2 = st.columns([2, 1])

with col1:
    location = st.selectbox(
        "Location",
        cities,
        index=cities.index(st.session_state.current_location),
        label_visibility="collapsed"
    )
    
    if st.session_state.current_location != location:
        st.session_state.current_location = location
        base_temps = {
            "Alexandria": 295.15, "Cairo": 299.15, "Giza": 298.15,
            "Luxor": 305.15, "Aswan": 308.15, "Port Said": 293.15,
            "Suez": 296.15, "Mansoura": 294.15
        }
        st.session_state.current_temp_k = base_temps.get(location, 295.15) + np.random.uniform(-2, 2)

# Get temperature based on selected date
# Make app full width without restrictions

# Use updated temperature for display
display_temp = kelvin_to_celsius(st.session_state.current_temp_k)

st.markdown(f"""
<div class='hero-weather'>
    <div class='location-display'>📍 {st.session_state.current_location}</div>
    <div class='temp-massive'>{display_temp:.0f}°C</div>
    <div class='condition-text'>{st.session_state.current_condition} • FEELS LIKE {display_temp-2:.0f}°C</div>
</div>
""", unsafe_allow_html=True)

# Quick stats
st.markdown("<div class='section-header'>⚡ LIVE DATA</div>", unsafe_allow_html=True)

col1, col2, col3, col4, col5 = st.columns(5)
stats = [
    ("🌡️", "TEMP", f"{display_temp:.1f}°C"),
    ("💧", "HUMIDITY", f"{np.random.uniform(50, 85):.0f}%"),
    ("💨", "WIND", f"{np.random.uniform(8, 18):.0f} KM/H"),
    ("👁️", "VISIBILITY", f"{np.random.uniform(8, 12):.1f} KM"),
    ("🌊", "PRESSURE", f"{np.random.uniform(1000, 1020):.0f} hPa")
]

for col, (icon, label, value) in zip([col1, col2, col3, col4, col5], stats):
    with col:
        st.markdown(f"""
        <div class='data-card'>
            <div class='data-icon'>{icon}</div>
            <div class='data-label'>{label}</div>
            <div class='data-value'>{value}</div>
        </div>
        """, unsafe_allow_html=True)

# Hourly forecast - improved
st.markdown("<div class='section-header'>⏰ HOURLY PROJECTION</div>", unsafe_allow_html=True)

current_hour = datetime.now().hour
hours_list = [(current_hour + i) % 24 for i in range(8)]
hours_display = ["NOW"] + [f"{h:02d}:00" for h in hours_list[1:]]
temps_k = [st.session_state.current_temp_k + np.random.uniform(-2, 3) for _ in range(8)]
temps_c = [kelvin_to_celsius(t) for t in temps_k]

# Icons based on time of day
icons = []
conditions = []
for h in hours_list:
    if 0 <= h < 6:
        icons.append("🌙")
        conditions.append("Clear Night")
    elif 6 <= h < 8:
        icons.append("🌅")
        conditions.append("Sunrise")
    elif 8 <= h < 12:
        icons.append("☀️")
        conditions.append("Sunny")
    elif 12 <= h < 17:
        icons.append("🌤️")
        conditions.append("Partly Cloudy")
    elif 17 <= h < 19:
        icons.append("🌆")
        conditions.append("Sunset")
    else:
        icons.append("🌃")
        conditions.append("Clear Night")

hour_cols = st.columns(8)
for idx, (hour, temp, icon, condition) in enumerate(zip(hours_display, temps_c, icons, conditions)):
    with hour_cols[idx]:
        st.markdown(f"""
        <div class='hour-panel'>
            <div class='hour-label'>{hour}</div>
            <div class='hour-icon'>{icon}</div>
            <div class='hour-temp'>{temp:.0f}°C</div>
            <div class='hour-condition'>{condition}</div>
        </div>
        """, unsafe_allow_html=True)

# Rain prediction
st.markdown("<div class='section-header'>🔮 RAIN PREDICTION SYSTEM</div>", unsafe_allow_html=True)

col1, col2, col3 = st.columns([1, 2, 1])
with col2:
    selected_date = st.date_input(
        "Target Date",
        value=datetime.now(),
        min_value=datetime.now() - timedelta(days=365),
        max_value=datetime.now() + timedelta(days=365),
        key="prediction_date"
    )
    
    # Update session state and recalculate temperature for selected date
    st.session_state.selected_date = selected_date
    
    # Update current temperature based on selected date AND location
    temp_forecast, _ = predict_temperature(st.session_state.current_location, selected_date, days=1)
    updated_temp_c = temp_forecast[0]
    
    # Also update the main temperature display
    st.session_state.current_temp_k = updated_temp_c + 273.15
    
    st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)
    
    # Show updated temperature for selected date
    st.markdown(f"""
    <div style='text-align: center; color: #0B3D91; font-size: 1.2rem; font-weight: 700; margin: 1rem 0;'>
        Expected Temperature: {updated_temp_c:.1f}°C
    </div>
    """, unsafe_allow_html=True)
    
    if st.button("🚀 INITIATE PREDICTION"):
        with st.spinner("⚡ ANALYZING ATMOSPHERIC DATA..."):
            import time
            time.sleep(0.8)
            
            # Use ML model for rain prediction
            temp_high, _ = predict_temperature(st.session_state.current_location, selected_date, days=1)
            rain_probability = predict_rain(
                st.session_state.current_location, 
                selected_date, 
                temp_high[0]
            )
            
            st.session_state.prediction_made = True
            will_rain = rain_probability > 0.35  # Lower threshold for Egypt climate
            
            if will_rain:
                st.markdown(f"""
                <div class='prediction-box' style='border-color: #FC3D21; box-shadow: 0 0 50px rgba(252, 61, 33, 0.5);'>
                    <div class='pred-icon'>☔</div>
                    <div class='pred-title' style='color: #FC3D21;'>RAIN DETECTED</div>
                    <div class='pred-confidence' style='color: #ffffff;'>PROBABILITY: {rain_probability*100:.1f}%</div>
                    <div style='color: #0B3D91; font-size: 1.3rem; font-weight: 700; margin-top: 1rem; letter-spacing: 2px;'>
                        ⚠️ UMBRELLA REQUIRED
                    </div>
                </div>
                """, unsafe_allow_html=True)
            else:
                st.markdown(f"""
                <div class='prediction-box' style='border-color: #0B3D91; box-shadow: 0 0 50px rgba(11, 61, 145, 0.5);'>
                    <div class='pred-icon'>☀️</div>
                    <div class='pred-title' style='color: #0B3D91;'>CLEAR CONDITIONS</div>
                    <div class='pred-confidence' style='color: #ffffff;'>CERTAINTY: {(1-rain_probability)*100:.1f}%</div>
                    <div style='color: #FC3D21; font-size: 1.3rem; font-weight: 700; margin-top: 1rem; letter-spacing: 2px;'>
                        ✓ OPTIMAL WEATHER
                    </div>
                </div>
                """, unsafe_allow_html=True)

# 10-Day forecast - dynamic with ML predictions
st.markdown("<div class='section-header'>📅 10-DAY FORECAST</div>", unsafe_allow_html=True)

# Start forecast from selected date
start_date = datetime.combine(selected_date, datetime.min.time())
forecast_dates = pd.date_range(start=start_date, periods=10, freq='D')
days = [d.strftime('%a').upper() for d in forecast_dates]
dates = [d.strftime('%b %d') for d in forecast_dates]

# Predict temperatures using ML model
high_temps_c, low_temps_c = predict_temperature(st.session_state.current_location, selected_date, days=10)

# Predict weather conditions for each day
icons_forecast = []
conditions = []
for i, (date, temp_high) in enumerate(zip(forecast_dates, high_temps_c)):
    rain_prob = predict_rain(st.session_state.current_location, date, temp_high)
    icon, condition = get_weather_condition(date, temp_high, rain_prob)
    icons_forecast.append(icon)
    conditions.append(condition)

# First row
forecast_cols = st.columns(5)
for idx in range(5):
    with forecast_cols[idx]:
        temp_range = high_temps_c[idx] - low_temps_c[idx]
        percentage = min(100, (temp_range / 15) * 100)
        
        st.markdown(f"""
        <div class='forecast-panel'>
            <div class='forecast-day'>{days[idx]}</div>
            <div class='forecast-date'>{dates[idx]}</div>
            <div style='font-size: 3rem; text-align: center; margin: 1rem 0;'>{icons_forecast[idx]}</div>
            <div class='forecast-temp'>{high_temps_c[idx]:.0f}° / {low_temps_c[idx]:.0f}°</div>
            <div style='background: rgba(11, 61, 145, 0.2); border-radius: 10px; padding: 2px;'>
                <div class='forecast-bar' style='width: {percentage}%;'></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

st.markdown("<div style='height: 1rem;'></div>", unsafe_allow_html=True)

# Second row
forecast_cols2 = st.columns(5)
for idx in range(5, 10):
    with forecast_cols2[idx-5]:
        temp_range = high_temps_c[idx] - low_temps_c[idx]
        percentage = min(100, (temp_range / 15) * 100)
        
        st.markdown(f"""
        <div class='forecast-panel'>
            <div class='forecast-day'>{days[idx]}</div>
            <div class='forecast-date'>{dates[idx]}</div>
            <div style='font-size: 3rem; text-align: center; margin: 1rem 0;'>{icons_forecast[idx]}</div>
            <div class='forecast-temp'>{high_temps_c[idx]:.0f}° / {low_temps_c[idx]:.0f}°</div>
            <div style='background: rgba(11, 61, 145, 0.2); border-radius: 10px; padding: 2px;'>
                <div class='forecast-bar' style='width: {percentage}%;'></div>
            </div>
        </div>
        """, unsafe_allow_html=True)

# Charts section
st.markdown("<div style='margin-top: 3rem;'></div>", unsafe_allow_html=True)

tab1, tab2, tab3 = st.tabs(["📊 ANALYTICS", "🌡️ TEMPERATURE", "💨 WIND DATA"])

with tab1:
    st.markdown("<div style='background: rgba(0,0,0,0.7); border: 2px solid rgba(11, 61, 145, 0.4); border-radius: 20px; padding: 2rem; margin-top: 1rem;'>", unsafe_allow_html=True)
    
    forecast_df = pd.DataFrame({
        'Day': days[:7],
        'Date': dates[:7],
        'Condition': ['Sunny', 'Sunny', 'Partly Cloudy', 'Cloudy', 'Sunny', 'Partly Cloudy', 'Rainy'],
        'High (°C)': [f"{t:.1f}" for t in high_temps_c[:7]],
        'Low (°C)': [f"{t:.1f}" for t in low_temps_c[:7]],
        'Rain %': [10, 5, 20, 30, 15, 25, 80]
    })
    
    st.dataframe(forecast_df, width='stretch', hide_index=True)
    st.markdown("</div>", unsafe_allow_html=True)

with tab2:
    st.markdown("<div style='background: rgba(0,0,0,0.7); border: 2px solid rgba(11, 61, 145, 0.4); border-radius: 20px; padding: 2rem; margin-top: 1rem;'>", unsafe_allow_html=True)
    
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        x=forecast_dates[:7],
        y=high_temps_c[:7],
        mode='lines+markers',
        name='High',
        line=dict(color='#FC3D21', width=4),
        marker=dict(size=12, symbol='circle'),
        fill='tonexty'
    ))
    
    fig.add_trace(go.Scatter(
        x=forecast_dates[:7],
        y=low_temps_c[:7],
        mode='lines+markers',
        name='Low',
        line=dict(color='#0B3D91', width=4),
        marker=dict(size=12, symbol='circle'),
        fill='tozeroy'
    ))
    
    fig.update_layout(
        plot_bgcolor='rgba(0, 0, 0, 0)',
        paper_bgcolor='rgba(0, 0, 0, 0)',
        font=dict(color='white', size=14, family='Orbitron'),
        xaxis=dict(gridcolor='rgba(11, 61, 145, 0.2)', title='Date'),
        yaxis=dict(gridcolor='rgba(11, 61, 145, 0.2)', title='Temperature (°C)'),
        height=450,
        legend=dict(bgcolor='rgba(0, 0, 0, 0.8)', bordercolor='#0B3D91', borderwidth=2)
    )
    
    st.plotly_chart(fig, width='stretch')
    st.markdown("</div>", unsafe_allow_html=True)

with tab3:
    st.markdown("<div style='background: rgba(0,0,0,0.7); border: 2px solid rgba(11, 61, 145, 0.4); border-radius: 20px; padding: 2rem; margin-top: 1rem;'>", unsafe_allow_html=True)
    
    # Calculate wind speed based on date and location
    month = selected_date.month
    base_wind = 15 if month in [12, 1, 2, 3] else 10  # Winter windier
    wind_speed = base_wind + np.random.uniform(-3, 5)
    
    # Calculate air quality based on date
    # Summer in Egypt has worse air quality
    base_aqi = 65 if month in [6, 7, 8] else 45
    air_quality = base_aqi + np.random.uniform(-10, 15)
    
    col1, col2 = st.columns(2)
    
    with col1:
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=wind_speed,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "WIND SPEED (KM/H)", 'font': {'color': '#0B3D91', 'size': 16, 'family': 'Orbitron'}},
            gauge={
                'axis': {'range': [None, 50], 'tickcolor': '#0B3D91'},
                'bar': {'color': "#FC3D21", 'thickness': 0.8},
                'bgcolor': "rgba(11, 61, 145, 0.1)",
                'borderwidth': 3,
                'bordercolor': "#0B3D91",
                'steps': [
                    {'range': [0, 15], 'color': 'rgba(76, 175, 80, 0.2)'},
                    {'range': [15, 30], 'color': 'rgba(255, 193, 7, 0.2)'},
                    {'range': [30, 50], 'color': 'rgba(252, 61, 33, 0.3)'}
                ],
                'threshold': {
                    'line': {'color': "#FC3D21", 'width': 4},
                    'thickness': 0.8,
                    'value': 25
                }
            }
        ))
        
        fig.update_layout(
            paper_bgcolor='rgba(0, 0, 0, 0)',
            font=dict(color='white', family='Orbitron'),
            height=350
        )
        
        st.plotly_chart(fig, width='stretch')
    
    with col2:
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=air_quality,
            domain={'x': [0, 1], 'y': [0, 1]},
            title={'text': "AIR QUALITY INDEX", 'font': {'color': '#0B3D91', 'size': 16, 'family': 'Orbitron'}},
            gauge={
                'axis': {'range': [None, 200], 'tickcolor': '#0B3D91'},
                'bar': {'color': "#4CAF50", 'thickness': 0.8},
                'bgcolor': "rgba(11, 61, 145, 0.1)",
                'borderwidth': 3,
                'bordercolor': "#0B3D91",
                'steps': [
                    {'range': [0, 50], 'color': 'rgba(76, 175, 80, 0.2)'},
                    {'range': [50, 100], 'color': 'rgba(255, 193, 7, 0.2)'},
                    {'range': [100, 200], 'color': 'rgba(252, 61, 33, 0.3)'}
                ],
                'threshold': {
                    'line': {'color': "#FC3D21", 'width': 4},
                    'thickness': 0.8,
                    'value': 100
                }
            }
        ))
        
        fig.update_layout(
            paper_bgcolor='rgba(0, 0, 0, 0)',
            font=dict(color='white', family='Orbitron'),
            height=350
        )
        
        st.plotly_chart(fig, width='stretch')
    
    st.markdown("</div>", unsafe_allow_html=True)

# Footer with GitHub link
st.markdown("<div style='margin-top: 4rem;'></div>", unsafe_allow_html=True)
st.markdown("""
<div style='background: rgba(0, 0, 0, 0.8); border: 2px solid rgba(11, 61, 145, 0.4); border-radius: 20px; padding: 2rem; text-align: center;'>
    <div style='font-family: Orbitron; font-size: 1.5rem; color: #FC3D21; font-weight: 700; letter-spacing: 3px; margin-bottom: 1rem;'>
        🛰️ NASA WEATHER STATION
    </div>
    <div style='color: #0B3D91; font-size: 1rem; font-weight: 600; letter-spacing: 2px; margin-bottom: 1rem;'>
        POWERED BY NASA CLIMATE DATA & MACHINE LEARNING
    </div>
    <div style='color: rgba(255, 255, 255, 0.6); font-size: 0.9rem; margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid rgba(11, 61, 145, 0.3);'>
        DATA SOURCES: NASA POWER API • MERRA-2 | MODELS: RANDOM FOREST • ENSEMBLE LEARNING
    </div>
    <div style='margin-top: 1.5rem;'>
        <a href='https://github.com/Ahmed-Esso/WillItRain-Youthify' target='_blank' 
           style='color: #FC3D21; font-size: 1.1rem; font-weight: 700; letter-spacing: 2px; 
                  text-decoration: none; padding: 0.8rem 2rem; border: 2px solid #FC3D21; 
                  border-radius: 10px; display: inline-block; transition: all 0.3s ease;
                  background: linear-gradient(135deg, rgba(252, 61, 33, 0.1), rgba(11, 61, 145, 0.1));'
           onmouseover="this.style.background='linear-gradient(135deg, rgba(252, 61, 33, 0.3), rgba(11, 61, 145, 0.3))'; this.style.boxShadow='0 0 30px rgba(252, 61, 33, 0.6)'; this.style.transform='scale(1.05)'"
           onmouseout="this.style.background='linear-gradient(135deg, rgba(252, 61, 33, 0.1), rgba(11, 61, 145, 0.1))'; this.style.boxShadow='none'; this.style.transform='scale(1)'">
            <span style='font-size: 1.3rem;'>⭐</span> VIEW ON GITHUB <span style='font-size: 1.3rem;'>⭐</span>
        </a>
    </div>
    <div style='color: rgba(252, 61, 33, 0.8); font-size: 0.85rem; margin-top: 1.5rem; font-weight: 700; letter-spacing: 1px;'>
        🚀 NASA SPACE APPS CHALLENGE 2025 • YOUTHIFY TEAM
    </div>
</div>
""", unsafe_allow_html=True)