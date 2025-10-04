# 📝 GitHub Repository Setup Instructions

## Initial Setup

### 1. Initialize Git Repository

```bash
cd WillItRain-Youthify
git init
```

### 2. Connect to GitHub

```bash
# Add remote repository
git remote add origin https://github.com/Ahmed-Esso/WillItRain-Youthify.git

# Verify remote
git remote -v
```

### 3. Create .gitignore (Already included)

The `.gitignore` file is already configured to exclude:
- Python cache files
- Virtual environments
- Secrets and credentials
- Data files (except structure)
- IDE files

### 4. Commit Initial Files

```bash
# Add all files
git add .

# Commit
git commit -m "Initial commit: NASA Weather Prediction App"

# Push to GitHub
git push -u origin main
```

> If you get an error about 'main' branch not existing:
```bash
git branch -M main
git push -u origin main
```

---

## Repository Structure

After setup, your GitHub repo will contain:

```
WillItRain-Youthify/
├── .github/              (optional - for CI/CD)
├── .streamlit/           ✅ Streamlit configuration
│   └── config.toml
├── models/               ✅ ML models
│   ├── __init__.py
│   ├── weather_models.py
│   ├── rain_predictor.py
│   └── saved/            (model files - not tracked)
├── utils/                ✅ Utilities
│   ├── __init__.py
│   ├── data_loader.py
│   └── visualizations.py
├── data/                 ✅ Data directory
│   └── .gitkeep
├── assets/               ✅ Images/logos
├── notebooks/            ✅ Jupyter notebooks
│   ├── NASA_ALL_MODELS_MERGED.ipynb
│   └── Visualization_modifier.ipynb
├── app.py                ✅ Main application
├── train_models.py       ✅ Model training script
├── test_app.py           ✅ Testing script
├── requirements.txt      ✅ Dependencies
├── .gitignore            ✅ Git ignore rules
├── .env.example          ✅ Environment template
├── README.md             ✅ Main documentation
├── QUICKSTART.md         ✅ Quick start guide
├── DEPLOYMENT.md         ✅ Deployment guide
└── LICENSE               ✅ MIT License
```

---

## GitHub Repository Settings

### 1. Update Repository Description

Go to your repository on GitHub and add:

**Description:**
```
🌧️ NASA-powered weather prediction app using ML models to forecast rain and climate conditions
```

**Topics:**
```
nasa, weather, machine-learning, streamlit, python, climate, data-science, 
prediction, random-forest, space-apps-challenge
```

### 2. Enable GitHub Pages (Optional)

For hosting documentation:
1. Go to Settings → Pages
2. Source: Deploy from branch
3. Branch: main, /docs folder
4. Save

### 3. Add Repository Badges

Add these to your README (already included):
- Python version
- Streamlit
- NASA badge
- License badge

### 4. Create GitHub Actions (Optional)

For automated testing:

Create `.github/workflows/test.yml`:

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v2
      - uses: actions/setup-python@v2
        with:
          python-version: '3.9'
      - name: Install dependencies
        run: pip install -r requirements.txt
      - name: Run tests
        run: python test_app.py
```

---

## Collaboration Setup

### Branch Protection Rules

1. Go to Settings → Branches
2. Add rule for `main` branch:
   - ✅ Require pull request before merging
   - ✅ Require status checks to pass
   - ✅ Require branches to be up to date

### Issue Templates

Create `.github/ISSUE_TEMPLATE/bug_report.md`:

```markdown
---
name: Bug Report
about: Report a bug
---

**Describe the bug**
A clear description of the bug.

**To Reproduce**
Steps to reproduce the behavior.

**Expected behavior**
What you expected to happen.

**Screenshots**
If applicable, add screenshots.
```

---

## Maintenance

### Keep Repository Clean

```bash
# Regular cleanup
git gc --prune=now
git remote prune origin
```

### Update Dependencies

```bash
# Check for outdated packages
pip list --outdated

# Update requirements.txt
pip freeze > requirements.txt
```

### Tag Releases

```bash
# Create version tag
git tag -a v1.0.0 -m "Version 1.0.0 - Initial Release"
git push origin v1.0.0
```

---

## Next Steps

1. ✅ Push code to GitHub
2. ✅ Deploy to Streamlit Cloud
3. ✅ Update README with live demo link
4. ✅ Submit to NASA Space Apps Challenge
5. ✅ Share on social media

---

**Need help?** Open an issue on GitHub!
