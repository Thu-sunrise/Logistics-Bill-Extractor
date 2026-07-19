import urllib.request
import json
import os
import sys
import subprocess
import tkinter as tk
from tkinter import messagebox

# Đường dẫn tới file version.json trên kho GitHub của bạn
# Đảm bảo đường dẫn này là dạng RAW (Raw data)
VERSION_URL = "https://raw.githubusercontent.com/Thu-sunrise/Logistics-Bill-Extractor/main/version.json"
CURRENT_VERSION = "1.0.0"

def check_for_updates():
    try:
        # Tải file version.json
        req = urllib.request.Request(VERSION_URL, headers={'User-Agent': 'Mozilla/5.0'})
        with urllib.request.urlopen(req, timeout=5) as response:
            data = json.loads(response.read().decode('utf-8'))
            
        latest_version = data.get("version")
        download_url = data.get("download_url")
        changelog = data.get("changelog", "Không có thông tin thay đổi.")
        
        # So sánh phiên bản (Đơn giản)
        if latest_version and latest_version != CURRENT_VERSION:
            prompt_update(latest_version, changelog, download_url)
            
    except Exception as e:
        # Bỏ qua nếu không có mạng hoặc lỗi server
        print("Lỗi kiểm tra bản cập nhật:", e)

def prompt_update(latest_version, changelog, download_url):
    root = tk.Tk()
    root.withdraw() # Ẩn cửa sổ chính
    
    msg = f"Đã có phiên bản mới: v{latest_version}\n\nChi tiết thay đổi:\n{changelog}\n\nBạn có muốn cập nhật ngay không?"
    result = messagebox.askyesno("Cập nhật phần mềm", msg)
    
    if result:
        perform_update(download_url)
    root.destroy()

def perform_update(download_url):
    import tempfile
    
    # Tải file exe mới về thư mục tạm
    temp_dir = tempfile.gettempdir()
    new_exe_path = os.path.join(temp_dir, "LogisticsBillExtractor_Update.exe")
    
    try:
        urllib.request.urlretrieve(download_url, new_exe_path)
    except Exception as e:
        messagebox.showerror("Lỗi", "Không thể tải bản cập nhật. Vui lòng thử lại sau.")
        return

    # Lấy đường dẫn file exe hiện tại đang chạy
    current_exe_path = sys.executable
    
    # Tạo script .bat để xóa file cũ và ghi đè file mới
    bat_path = os.path.join(temp_dir, "update.bat")
    bat_content = f"""
    @echo off
    timeout /t 2 /nobreak > NUL
    del "{current_exe_path}"
    copy "{new_exe_path}" "{current_exe_path}"
    del "{new_exe_path}"
    start "" "{current_exe_path}"
    del "%~f0"
    """
    with open(bat_path, "w") as f:
        f.write(bat_content)
        
    # Chạy script bat ẩn và thoát phần mềm hiện tại
    subprocess.Popen([bat_path], creationflags=subprocess.CREATE_NO_WINDOW)
    sys.exit()
