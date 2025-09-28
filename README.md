# 🌍 Climate Forecasting with NASA Earth Data

## 📌 Project Overview

This project was developed for the **NASA Space Apps Challenge 2025 – Cairo**.
Our goal is to build a **data-driven forecasting system** that leverages NASA Earth observation datasets to predict **temperature, humidity, and rainfall likelihood**. Using AI and statistical modeling, the system can generate forecasts for up to **6 months ahead**, helping communities, farmers, and decision-makers plan for climate variability.

---

## 🚀 Features

* ✅ Integration of NASA Earth observation data (MERRA-2, ERA5, etc.)
* ✅ Preprocessing pipeline for handling large climate datasets
* ✅ Machine Learning & Time Series Models (ARIMA, SARIMA, Random Forest, XGBoost)
* ✅ Forecasting **temperature & rainfall likelihood**
* ✅ Visualization dashboards using **Plotly** and **Matplotlib**
* ✅ Exported datasets for reproducibility

---

## 🗂️ Repository Structure

```
├── data/                # Processed datasets (NetCDF/CSV)
├── notebooks/           # Jupyter notebooks with preprocessing & modeling
├── src/                 # Core Python scripts
│   ├── preprocessing.py
│   ├── models.py
│   ├── visualization.py
│   └── utils.py
├── results/             # Forecast outputs, plots, evaluation metrics
├── README.md            # Project documentation
└── requirements.txt     # Dependencies
```

---

## ⚙️ Installation & Usage

1. Clone the repository:

   ```bash
   git clone https://github.com/<your-team-repo>.git
   cd <your-team-repo>
   ```
2. Install dependencies:

   ```bash
   pip install -r requirements.txt
   ```
3. Run preprocessing:

   ```bash
   python src/preprocessing.py
   ```
4. Train models:

   ```bash
   python src/models.py
   ```
5. Visualize results:

   ```bash
   python src/visualization.py
   ```

---

## 📊 Example Output

* 📈 Forecasts of **temperature trends** (daily/hourly)
* 🌧️ Probabilities of rainfall events
* 🔍 Evaluation metrics: RMSE, Accuracy, F1-score
* 📊 Interactive Plotly visualizations

---

## 🎯 Impact & Use Cases

* 👨‍🌾 **Farmers** → Plan crop cycles and irrigation
* 🏙️ **Cities** → Prepare for heatwaves or heavy rainfall
* 🌎 **Communities** → Improve resilience to climate variability

---

## 👥 Team

* Ahmed Essam (Team Lead)
* [Add team member names here]

---

## 📜 License

This project is released under the **MIT License**.

---

## 🛰️ Acknowledgments

* NASA Earth Science Data (MERRA-2, GES DISC, ECMWF ERA5)
* Open-source Python libraries: **xarray, pandas, scikit-learn, statsmodels, plotly, xgboost**
* **NASA Space Apps Cairo 2025** Organizers

---
