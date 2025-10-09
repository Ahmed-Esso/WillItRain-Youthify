project:
  name: "Will It Rain?"
  challenge: "NASA Space Apps Challenge 2025"
  theme: "Weather Prediction & Climate Analysis"
  description: >
    Will It Rain? is an AI-powered weather prediction system built for the NASA Space Apps Challenge 2025.
    It uses NASA POWER satellite data to forecast precipitation, fog, air quality, thermal comfort, and storm intensity
    for Alexandria, Egypt (2020–2023). The solution integrates Snowflake Cloud, Python, and Plotly for
    end-to-end analysis, visualization, and model deployment.

  location: "Alexandria, Egypt"
  period: "2020–2023"
  goal: "Predict rainfall, visibility, air quality, comfort, and storm intensity using real NASA data."

  team:
    - role: "Data Science & Machine Learning"
      responsibility: "Model training, feature engineering, evaluation"
    - role: "Visualization & UI"
      responsibility: "Interactive dashboards using Plotly"
    - role: "Climate Data Analysis"
      responsibility: "Data cleaning, extraction, preprocessing"
    - role: "Validation & Testing"
      responsibility: "Model tuning and verification"

  data:
    source: "NASA POWER (Prediction Of Worldwide Energy Resources)"
    link: "https://power.larc.nasa.gov/"
    storage: "Snowflake Cloud Data Warehouse"
    coverage: "Alexandria, Egypt (2020–2023)"
    resolution: "Daily averages"
    variables:
      - { name: "T2M", description: "Temperature at 2 meters", unit: "°C" }
      - { name: "T2MDEW", description: "Dew point temperature", unit: "°C" }
      - { name: "QV2M", description: "Specific humidity", unit: "g/kg" }
      - { name: "TQI", description: "Total ice in clouds", unit: "kg/m²" }
      - { name: "TQL", description: "Total liquid in clouds", unit: "kg/m²" }
      - { name: "OMEGA500", description: "Vertical air velocity", unit: "Pa/s" }
      - { name: "U10M", description: "Wind speed (U component)", unit: "m/s" }
      - { name: "V10M", description: "Wind speed (V component)", unit: "m/s" }
      - { name: "PS", description: "Surface pressure", unit: "kPa" }
      - { name: "SLP", description: "Sea level pressure", unit: "kPa" }

  models:
    - name: "Fog & Visibility"
      type: "Regression"
      purpose: "Predict fog and visibility range"
      features: ["TEMP_DEW_DIFF", "HUMIDITY", "WIND_SPEED"]
      performance: { R2: 0.89, RMSE: 3.21 }

    - name: "Precipitation Amount"
      type: "Regression"
      purpose: "Forecast rainfall (mm)"
      features: ["TQI", "TQL", "HUMIDITY"]
      performance: { R2: 0.82, RMSE: 0.74 }

    - name: "Air Quality"
      type: "Regression"
      purpose: "Estimate air quality index (AQI)"
      features: ["WIND_SPEED", "T2M", "PS"]
      performance: { R2: 0.85, RMSE: 4.12 }

    - name: "Thermal Comfort"
      type: "Regression"
      purpose: "Compute comfort/heat index"
      features: ["T2M", "QV2M", "U10M", "V10M"]
      performance: { R2: 0.91, RMSE: 2.87 }

    - name: "Rain Prediction"
      type: "Classification"
      purpose: "Binary classification (Rain / No Rain)"
      features: ["TOTAL_MOISTURE", "HUMIDITY", "LIQUID_WATER"]
      performance: { Accuracy: 94.7 }

    - name: "Storm Intensity"
      type: "Regression"
      purpose: "Estimate storm strength"
      features: ["OMEGA500", "WIND_SPEED", "ICE_CONTENT", "TEMP_DIFF"]
      performance: { R2: 0.87, RMSE: 2.34 }

  key_findings:
    - "OMEGA500 (vertical motion) was the strongest storm predictor (25% importance)."
    - "Temperature–Dewpoint difference was the most accurate fog indicator."
    - "Combining TQI + TQL improved rainfall classification performance."

  visualization:
    tools: ["Plotly", "Python"]
    features:
      - "Multi-panel dashboard with real-time weather metrics"
      - "Animated time-series of temperature, humidity, and rainfall"
      - "Correlation heatmaps showing variable interactions"
      - "Storm intensity gauge and rainfall distribution charts"
    color_scheme:
      primary: "#6640b2"
      secondary: "#00cccb"
      background: "#000510"

  structure:
    root: "nasa-will-it-rain/"
    files:
      - "NASA_ALL_MODELS_MERGED.ipynb"
      - "Visualization_modifier.ipynb"
      - "requirements.txt"
      - "README.md"

  setup:
    steps:
      - "Clone the repository: git clone https://github.com/mayarhany/nasa-will-it-rain.git"
      - "Install dependencies: pip install -r requirements.txt"
      - "Configure Snowflake credentials in the notebook."
      - "Run: jupyter notebook NASA_ALL_MODELS_MERGED.ipynb"

  performance_summary:
    regression_models_average_R2: 0.87
    classification_model_accuracy: 94.7
    highlights:
      - "High model consistency across features."
      - "Strong correlation between vertical velocity and storm strength."
      - "Accurate short-term rainfall prediction."

  future_work:
    - "Integrate real-time weather APIs."
    - "Develop a mobile app version."
    - "Expand dataset to multiple regions."
    - "Experiment with LSTM and Transformer architectures."
    - "Use ensemble stacking for improved accuracy."
    - "Integrate IoT-based weather sensors."

  license: "MIT License"
  acknowledgments:
    - "NASA POWER project for providing open-access data."
    - "Snowflake for cloud data storage."
    - "Plotly for visualization tools."
    - "NASA Space Apps mentors for technical support."

  contact:
    author: "Mayar Hany Rafik"
    email: "mayarhany1999@gmail.com"
    github: "https://github.com/mayarhany"
    linkedin: "https://linkedin.com/in/mayar-hany-139a2a2a6"

# ============================================================
# 🌌 PROJECT METADATA (for GitHub / Docs / Pages integration)
# ============================================================

metadata:
  title: "🌌 WILL IT RAIN? — NASA Space Apps Challenge 2025"
  subtitle: "AI-Powered Weather Prediction System for Alexandria, Egypt"
  theme:
    name: "NeoSpace Dark"
    background: "#000510"
    card: "#0a0f2c"
    accent_primary: "#6640b2"
    accent_secondary: "#00cccb"
    accent_highlight: "#b47aff"
    text_primary: "#ffffff"
    text_secondary: "#b0b8ff"
    chart_colors:
      - "#6640b2"
      - "#00cccb"
      - "#d8d8d8"
      - "#b47aff"
  tags:
    - NASA
    - SpaceApps2025
    - WeatherPrediction
    - MachineLearning
    - ClimateData
    - Python
    - Plotly
    - Snowflake
    - AI
  github:
    repository: "https://github.com/mayarhany/nasa-will-it-rain"
    stars: true
    license: "MIT"
    badges:
      - name: "Python"
        color: "#3776AB"
        label: "Python 3.8+"
      - name: "Plotly"
        color: "#3F4F75"
        label: "Interactive Dashboards"
      - name: "Scikit-Learn"
        color: "#F7931E"
        label: "ML Models"
      - name: "NASA Space Apps"
        color: "#6640b2"
        label: "2025 Edition"
  author:
    name: "Mayar Hany Rafik"
    role: "Data Analyst & ML Engineer"
    email: "mayarhany1999@gmail.com"
    linkedin: "https://linkedin.com/in/mayar-hany-139a2a2a6"
    github_profile: "https://github.com/mayarhany"
  preview:
    image: "assets/ui_dashboard_preview.png"
    description: >
      Neon-themed futuristic weather dashboard inspired by NASA’s mission interfaces.
      Displays a 10-day forecast, precipitation predictions, and model certainty levels.
    colors: ["#000510", "#6640b2", "#00cccb"]
  visibility: "public"
  license: "MIT License"
  created: "2025-10-09"
  last_updated: "2025-10-09"
  version: "1.0.0"

# ============================================================
# 🌠 README CONTENT (Markdown - GitHub Display)
# ============================================================

readme: |
  <div align="center">
  
  # 🌌 **WILL IT RAIN?**
  ### *NASA Space Apps Challenge 2025 – Alexandria, Egypt*
  
  ![Preview](assets/ui_dashboard_preview.png)
  
  **AI-Powered Weather Prediction System** using NASA’s Climate Data  
  Developed with 💜 Python, Plotly & Snowflake
  
  [![Python](https://img.shields.io/badge/Python-3.8+-3776AB?logo=python)]()
  [![Plotly](https://img.shields.io/badge/Plotly-Dashboards-3F4F75?logo=plotly)]()
  [![Scikit-Learn](https://img.shields.io/badge/Scikit--Learn-ML%20Models-F7931E?logo=scikit-learn)]()
  [![NASA Space Apps](https://img.shields.io/badge/NASA%20Space%20Apps-2025-6640b2?logo=nasa)]()
  
  </div>

  ---

  ## 📋 **Project Overview**
  **Will It Rain?** is a comprehensive weather prediction system that leverages NASA’s POWER climate datasets to build six machine learning models predicting various atmospheric conditions — from precipitation and fog to storm intensity and air quality.

  The project combines advanced regression and classification models with **interactive visualizations** using Plotly and Jupyter Notebooks.

  ---

  ## 🎯 **Challenge Description**
  > “Can we predict precipitation using satellite and climate data?”
  
  Our team focused on **Alexandria, Egypt**, analyzing multi-year NASA POWER data to forecast local weather dynamics.  
  Using ensemble ML techniques, we predicted precipitation probability, type, and storm severity.

  ---

  ## ⚙️ **Machine Learning Models**
  | Model | Type | Purpose | Key Variables |
  |--------|------|----------|----------------|
  | ☁️ Fog & Visibility | Regression | Predict visibility levels | TEMP_DEW_DIFF, HUMIDITY, WIND_SPEED |
  | 💧 Precipitation Amount | Regression | Forecast rainfall (mm) | ICE_CONTENT, LIQUID_WATER, HUMIDITY |
  | 🌬️ Air Quality | Regression | Assess AQI | WIND_SPEED, TEMP, PRESSURE |
  | 🌡️ Thermal Comfort | Regression | Compute heat index | HEAT_INDEX, HUMIDITY, WIND_CHILL |
  | 🌦️ Rain Prediction | Classification | Binary rain forecast | TOTAL_MOISTURE, HUMIDITY |
  | ⛈️ Storm Intensity | Regression | Estimate storm strength | OMEGA500, WIND_SPEED, ICE_CONTENT |

  ---

  ## 🎨 **Dashboard & Visualizations**
  Built with **Plotly**, **Matplotlib**, and **Seaborn**, featuring a **neon cyber-space theme**.

  - 📈 Multi-panel dashboards  
  - 🗺️ Interactive heatmaps & infographics  
  - 🎬 Animated time-series  
  - 🍩 Weather distribution charts  
  - 🌀 Storm analysis interface  

  ---

  ## 🧠 **Model Insights**
  - **OMEGA500** → Strongest indicator of storm intensity (25% importance)  
  - **T2M - T2MDEW** → Best fog predictor  
  - **TQI + TQL** → Key to precipitation type (rain/snow/hail)  
  - **Thermal Comfort Index** correlates with humidity + wind speed  
  - **Seasonality** → Rain probability 3× higher in winter months  

  ---

  ## 🧰 **Tech Stack**
  - **Python 3.8+**
  - **Scikit-Learn, Pandas, NumPy**
  - **Plotly & Matplotlib**
  - **Snowflake (Cloud Data Warehouse)**
  - **NASA POWER API (Data Source)**

  ---

  ## 📈 **Performance Summary**
  | Model | R² | RMSE | Accuracy |
  |--------|-----|------|-----------|
  | Fog & Visibility | 0.89 | 3.21 | - |
  | Precipitation Amount | 0.82 | 0.74 | - |
  | Air Quality | 0.85 | 4.12 | - |
  | Thermal Comfort | 0.91 | 2.87 | - |
  | Rain Prediction | - | - | **94.7%** |
  | Storm Intensity | 0.87 | 2.34 | - |

  ---

  ## 🌍 **Data Details**
  - **Source:** NASA POWER (Prediction Of Worldwide Energy Resources)
  - **Location:** Alexandria, Egypt
  - **Period:** 2020–2023
  - **Resolution:** Daily averages

  ---

  ## 🔮 **Future Enhancements**
  - Real-time API integration  
  - Deep learning (LSTM, Transformers)  
  - Expansion to multiple cities  
  - IoT weather station inputs  
  - Streamlit / Web app deployment  

  ---

  ## 🧑‍🚀 **Team & Credits**
  Developed with ❤️ for **NASA Space Apps Challenge 2025**

  **Team Roles:**
  - 👩‍💻 *Data Science & ML Models*  
  - 👨‍🔬 *Climate Analysis & Research*  
  - 👩‍🎨 *Visualization & Dashboard Design*  
  - 👨‍💻 *Testing & Model Evaluation*

  **Acknowledgments:**
  - NASA POWER Project  
  - Snowflake  
  - Plotly Team  
  - Space Apps Mentors

  ---

  ## 📜 **License**
  Licensed under the **MIT License**.  
  © 2025 Mayar Hany Rafik — All Rights Reserved.
