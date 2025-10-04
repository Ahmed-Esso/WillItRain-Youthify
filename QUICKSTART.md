# 🚀 Quick Start Guide - Will It Rain?

## For First-Time Users

### 1. Install Python
Make sure you have Python 3.8 or higher installed:
```bash
python --version
```

### 2. Clone Repository
```bash
git clone https://github.com/Ahmed-Esso/WillItRain-Youthify.git
cd WillItRain-Youthify
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the App
```bash
streamlit run app.py
```

### 5. Open in Browser
The app will automatically open at: `http://localhost:8501`

---

## Troubleshooting

### Issue: ModuleNotFoundError
**Solution:** Install missing packages
```bash
pip install -r requirements.txt --upgrade
```

### Issue: Streamlit won't start
**Solution:** Try specifying port
```bash
streamlit run app.py --server.port 8502
```

### Issue: No data loading
**Solution:** App will use demo data automatically. To use real data:
1. Copy `.env.example` to `.env`
2. Add your Snowflake credentials
3. Restart the app

---

## Need Help?

- 📧 Email: ahmed.esso@example.com
- 🐙 GitHub Issues: [Report a bug](https://github.com/Ahmed-Esso/WillItRain-Youthify/issues)
- 📖 Full Documentation: [README.md](README.md)

---

**Happy Weather Predicting! 🌧️**
