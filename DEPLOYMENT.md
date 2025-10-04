# 🚀 Deployment Guide to Streamlit Cloud

## Prerequisites
- GitHub account
- Streamlit Cloud account (free at streamlit.io/cloud)
- Your repository pushed to GitHub

---

## Step-by-Step Deployment

### 1️⃣ Prepare Your Repository

Make sure all files are committed and pushed:

```bash
cd WillItRain-Youthify
git add .
git commit -m "Ready for deployment"
git push origin main
```

### 2️⃣ Sign Up for Streamlit Cloud

1. Go to [streamlit.io/cloud](https://streamlit.io/cloud)
2. Click "Sign up with GitHub"
3. Authorize Streamlit to access your repositories

### 3️⃣ Create New App

1. Click "New app" button
2. Fill in the details:
   - **Repository:** `Ahmed-Esso/WillItRain-Youthify`
   - **Branch:** `main`
   - **Main file path:** `app.py`
   - **App URL:** Choose your custom URL (e.g., `willit rain-youthify`)

### 4️⃣ Configure Advanced Settings

Click "Advanced settings" and configure:

#### Python Version
```
3.9
```

#### Requirements File
Default: `requirements.txt` ✅

### 5️⃣ Add Secrets (Optional - for Snowflake)

If you want to use real Snowflake data:

1. In your app dashboard, go to **Settings** → **Secrets**
2. Add the following in TOML format:

```toml
# Snowflake Configuration
SNOWFLAKE_ACCOUNT = "your_account_id"
SNOWFLAKE_USER = "your_username"
SNOWFLAKE_PASSWORD = "your_password"
SNOWFLAKE_WAREHOUSE = "NASA_WH"
SNOWFLAKE_DATABASE = "NASA_DB"
SNOWFLAKE_SCHEMA = "PUBLIC"
SNOWFLAKE_ROLE = "ACCOUNTADMIN"
```

> **Note:** If you don't add secrets, the app will automatically use demo data.

### 6️⃣ Deploy! 🎉

1. Click "Deploy!"
2. Wait for the build process (usually 2-5 minutes)
3. Your app will be live at: `https://your-app-name.streamlit.app`

---

## Troubleshooting

### Build Fails

**Error:** Module not found
- **Solution:** Check that all dependencies are in `requirements.txt`

**Error:** Python version mismatch
- **Solution:** Set Python version to 3.9 in Advanced Settings

### App Crashes on Start

**Error:** Import errors
- **Solution:** Test locally first with `python test_app.py`

**Error:** Missing files
- **Solution:** Ensure all required files are pushed to GitHub

### Slow Loading

- **Cause:** Large model files
- **Solution:** Consider using `@st.cache_resource` for model loading

---

## Post-Deployment

### Update Your App

After making changes:

```bash
git add .
git commit -m "Update app"
git push origin main
```

Streamlit Cloud will automatically redeploy! 🔄

### Monitor Usage

- View app analytics in Streamlit Cloud dashboard
- Check logs for errors
- Monitor resource usage

### Share Your App

Share your app URL:
```
https://your-app-name.streamlit.app
```

Add it to:
- GitHub repository description
- README.md
- Social media
- NASA Space Apps Challenge submission

---

## Custom Domain (Optional)

To use a custom domain:

1. Upgrade to Streamlit Cloud Pro
2. Go to Settings → Custom domain
3. Follow DNS configuration instructions

---

## Best Practices

✅ **DO:**
- Test locally before deploying
- Use environment variables for secrets
- Keep requirements.txt minimal
- Add error handling
- Monitor app performance

❌ **DON'T:**
- Commit secrets to GitHub
- Use large data files in repository
- Hardcode API keys
- Ignore error messages

---

## Need Help?

- 📖 [Streamlit Documentation](https://docs.streamlit.io)
- 💬 [Streamlit Community](https://discuss.streamlit.io)
- 🐙 [GitHub Issues](https://github.com/Ahmed-Esso/WillItRain-Youthify/issues)

---

**Happy Deploying! 🚀**
