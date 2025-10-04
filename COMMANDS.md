# ⚡ Command Reference - Will It Rain?

Quick reference for all commands you'll need.

---

## 📦 Installation & Setup

### Initial Setup
```bash
# Clone repository
git clone https://github.com/Ahmed-Esso/WillItRain-Youthify.git
cd WillItRain-Youthify

# Run automated setup
python setup.py
```

### Manual Setup
```bash
# Create virtual environment (optional but recommended)
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Create .env file
copy .env.example .env   # Windows
cp .env.example .env     # macOS/Linux
```

---

## 🚀 Running the App

### Start Streamlit App
```bash
streamlit run app.py
```

### Run on Custom Port
```bash
streamlit run app.py --server.port 8502
```

### Run with External Access
```bash
streamlit run app.py --server.address 0.0.0.0
```

---

## 🧪 Testing

### Run All Tests
```bash
python test_app.py
```

### Test Specific Component
```python
# In Python REPL
from utils.data_loader import generate_demo_data
df = generate_demo_data(days=10)
print(df.head())
```

---

## 🤖 Model Training

### Train All Models
```bash
python train_models.py
```

### Train Specific Model (in Python)
```python
from models.weather_models import WeatherModels
from utils.data_loader import load_weather_data

df = load_weather_data()
models = WeatherModels()
models.train_all_models(df)
models.save_models()
```

---

## 🐙 Git Commands

### Initial Commit
```bash
git init
git add .
git commit -m "Initial commit: NASA Weather App"
```

### Connect to GitHub
```bash
git remote add origin https://github.com/Ahmed-Esso/WillItRain-Youthify.git
git branch -M main
git push -u origin main
```

### Regular Updates
```bash
# Check status
git status

# Add all changes
git add .

# Commit with message
git commit -m "Your commit message"

# Push to GitHub
git push
```

### Useful Git Commands
```bash
# View commit history
git log --oneline

# Check differences
git diff

# Discard changes
git checkout -- filename

# Pull latest changes
git pull origin main
```

---

## 📊 Data Management

### Load Data
```python
# Demo data
from utils.data_loader import generate_demo_data
df = generate_demo_data(days=365)

# From CSV
from utils.data_loader import load_from_csv
df = load_from_csv('data/weather_data.csv')

# From Snowflake
from utils.data_loader import load_from_snowflake
df = load_from_snowflake()
```

### Export Data
```python
# Save predictions
from utils.data_loader import save_prediction_history
save_prediction_history(prediction_result)
```

---

## 🎨 Customization

### Update Theme Colors
Edit `.streamlit/config.toml`:
```toml
[theme]
primaryColor = "#00cccb"      # Your cyan
backgroundColor = "#d8d8d8"   # Your grey
textColor = "#6640b2"         # Your purple
```

### Add New Page
Create new file in root:
```python
# pages/1_New_Page.py
import streamlit as st
st.title("New Page")
```

---

## 🌐 Deployment

### Deploy to Streamlit Cloud
```bash
# 1. Ensure all files are committed
git add .
git commit -m "Ready for deployment"
git push

# 2. Go to streamlit.io/cloud
# 3. Click "New app"
# 4. Select your repository
# 5. Main file: app.py
# 6. Click Deploy
```

### Update Deployed App
```bash
# Just push to GitHub - auto-deploys!
git push origin main
```

---

## 📦 Package Management

### Update All Packages
```bash
pip install --upgrade -r requirements.txt
```

### Update Specific Package
```bash
pip install --upgrade streamlit
```

### Freeze Dependencies
```bash
pip freeze > requirements.txt
```

### Check Outdated Packages
```bash
pip list --outdated
```

---

## 🔍 Debugging

### Check Streamlit Logs
```bash
# View in terminal while app runs
streamlit run app.py

# Or check specific log file
# Windows: %USERPROFILE%\.streamlit\logs\
# macOS/Linux: ~/.streamlit/logs/
```

### Clear Streamlit Cache
```bash
# Delete cache folder
# Windows:
rmdir /s %USERPROFILE%\.streamlit\cache
# macOS/Linux:
rm -rf ~/.streamlit/cache
```

### Python Debugging
```python
# Add to code for debugging
import pdb; pdb.set_trace()

# Or use print statements
print(f"Debug: {variable_name}")
```

---

## 📝 Documentation

### Generate API Docs
```bash
# Install pdoc
pip install pdoc3

# Generate docs
pdoc --html --output-dir docs models utils
```

### View README Locally
```bash
# Install grip (GitHub-flavored markdown)
pip install grip

# View README
grip README.md
```

---

## 🧹 Maintenance

### Clean Python Cache
```bash
# Windows:
del /s /q __pycache__
del /s /q *.pyc

# macOS/Linux:
find . -type d -name __pycache__ -exec rm -r {} +
find . -type f -name "*.pyc" -delete
```

### Clean Git History
```bash
# Remove large files from history
git filter-branch --tree-filter 'rm -f large_file.dat' HEAD
```

---

## 🔐 Environment Variables

### Set Environment Variables

**Windows (PowerShell):**
```powershell
$env:SNOWFLAKE_USER = "your_username"
$env:SNOWFLAKE_PASSWORD = "your_password"
```

**macOS/Linux:**
```bash
export SNOWFLAKE_USER="your_username"
export SNOWFLAKE_PASSWORD="your_password"
```

**Using .env file (recommended):**
```bash
# Create .env file
echo "SNOWFLAKE_USER=your_username" >> .env
echo "SNOWFLAKE_PASSWORD=your_password" >> .env
```

---

## 📊 Performance

### Profile Code
```python
# Add to code
import cProfile
cProfile.run('your_function()')
```

### Check Memory Usage
```bash
# Install memory_profiler
pip install memory-profiler

# Use in Python
@profile
def your_function():
    pass
```

---

## 🆘 Quick Fixes

### Port Already in Use
```bash
# Kill process on port 8501
# Windows:
netstat -ano | findstr :8501
taskkill /PID <PID> /F

# macOS/Linux:
lsof -ti:8501 | xargs kill -9
```

### Module Not Found
```bash
pip install -r requirements.txt --upgrade
```

### Streamlit Won't Start
```bash
# Clear cache and restart
streamlit cache clear
streamlit run app.py
```

---

## 📚 Additional Resources

### Streamlit Documentation
```bash
# Open in browser
streamlit docs
```

### Get Help
```bash
streamlit --help
python app.py --help
```

---

## 💡 Pro Tips

1. **Use Virtual Environments**
   ```bash
   python -m venv venv
   ```

2. **Commit Often**
   ```bash
   git commit -am "Small changes"
   ```

3. **Test Before Deploying**
   ```bash
   python test_app.py && streamlit run app.py
   ```

4. **Use .gitignore**
   - Already configured!
   - Prevents committing secrets

5. **Document Changes**
   - Update README for major changes
   - Use clear commit messages

---

**Need more help?** Check:
- 📖 README.md
- 🚀 QUICKSTART.md  
- 🌐 DEPLOYMENT.md
- 🐙 GITHUB_SETUP.md

---

**Happy Coding! 🎉**
