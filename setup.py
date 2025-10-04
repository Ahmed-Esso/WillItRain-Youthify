"""
Complete setup script for the Will It Rain app
Run this after cloning the repository
"""

import os
import sys
import subprocess

def print_header(text):
    """Print formatted header"""
    print("\n" + "="*60)
    print(f"  {text}")
    print("="*60 + "\n")

def check_python_version():
    """Check if Python version is adequate"""
    print_header("🐍 Checking Python Version")
    version = sys.version_info
    print(f"Python version: {version.major}.{version.minor}.{version.micro}")
    
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print("❌ Python 3.8 or higher is required!")
        return False
    
    print("✅ Python version is adequate")
    return True

def create_directories():
    """Create necessary directories"""
    print_header("📁 Creating Directories")
    
    dirs = [
        'data',
        'models/saved',
        'assets'
    ]
    
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True)
        print(f"   ✅ Created: {dir_path}")
    
    return True

def install_dependencies():
    """Install required packages"""
    print_header("📦 Installing Dependencies")
    
    try:
        print("Installing packages from requirements.txt...")
        subprocess.check_call([
            sys.executable, '-m', 'pip', 'install', '-r', 'requirements.txt'
        ])
        print("✅ All packages installed successfully")
        return True
    except subprocess.CalledProcessError:
        print("❌ Error installing packages")
        return False

def setup_environment():
    """Set up environment variables"""
    print_header("🔧 Setting Up Environment")
    
    if not os.path.exists('.env'):
        if os.path.exists('.env.example'):
            print("Creating .env file from template...")
            with open('.env.example', 'r') as src:
                with open('.env', 'w') as dst:
                    dst.write(src.read())
            print("✅ Created .env file")
            print("⚠️  Please edit .env and add your credentials")
        else:
            print("⚠️  .env.example not found")
    else:
        print("✅ .env file already exists")
    
    return True

def run_tests():
    """Run tests to verify setup"""
    print_header("🧪 Running Tests")
    
    try:
        subprocess.check_call([sys.executable, 'test_app.py'])
        return True
    except subprocess.CalledProcessError:
        print("⚠️  Some tests failed, but you can still proceed")
        return True

def main():
    """Main setup function"""
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║                                                           ║
    ║           🌧️  WILL IT RAIN? - SETUP SCRIPT  🌧️           ║
    ║                                                           ║
    ║        NASA Weather Prediction App Setup Wizard          ║
    ║                                                           ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    steps = [
        ("Checking Python version", check_python_version),
        ("Creating directories", create_directories),
        ("Installing dependencies", install_dependencies),
        ("Setting up environment", setup_environment),
        ("Running tests", run_tests)
    ]
    
    for step_name, step_func in steps:
        if not step_func():
            print(f"\n❌ Setup failed at: {step_name}")
            print("Please fix the errors and run setup.py again")
            return False
    
    # Success message
    print_header("🎉 SETUP COMPLETE!")
    
    print("""
    ✅ Your environment is ready!
    
    📝 Next Steps:
    
    1. Edit .env file with your Snowflake credentials (optional)
       Or use demo data without credentials
    
    2. Train models (optional):
       python train_models.py
    
    3. Run the app:
       streamlit run app.py
    
    4. Deploy to Streamlit Cloud:
       See DEPLOYMENT.md for instructions
    
    📖 Documentation:
       - README.md - Full documentation
       - QUICKSTART.md - Quick start guide
       - DEPLOYMENT.md - Deployment instructions
    
    🌐 GitHub Repository:
       https://github.com/Ahmed-Esso/WillItRain-Youthify
    
    ❓ Need help?
       - Open an issue on GitHub
       - Read the documentation
       - Check QUICKSTART.md
    
    Happy weather predicting! 🌤️
    """)
    
    return True

if __name__ == "__main__":
    try:
        success = main()
        sys.exit(0 if success else 1)
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n❌ Unexpected error: {e}")
        sys.exit(1)
