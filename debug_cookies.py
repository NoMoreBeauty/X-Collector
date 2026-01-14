from src.api.client import load_cookies_from_file
from pathlib import Path
import os

print(f"CWD: {os.getcwd()}")
print(f"File exists: {Path('config/cookies.txt').exists()}")
try:
    cookies = load_cookies_from_file()
    print(f"Cookies loaded: {cookies}")
    print(f"Auth Token: {cookies.get('auth_token')}")
except Exception as e:
    print(f"Error: {e}")
