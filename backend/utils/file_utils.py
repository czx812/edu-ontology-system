import os
from pathlib import Path

TEMP_PDF_DIR = "./temp_pdf"
os.makedirs(TEMP_PDF_DIR, exist_ok=True)

def check_pdf_suffix(filename: str) -> bool:
    return filename.lower().endswith(".pdf")

def save_temp_file(file, original_name: str) -> str:
    safe_name = Path(original_name).name
    save_path = os.path.join(TEMP_PDF_DIR, safe_name)
    with open(save_path, "wb") as f:
        f.write(file.read())
    return save_path

def read_file_bytes(file_path: str) -> bytes:
    with open(file_path, "rb") as f:
        return f.read()

def clear_expired_pdf(days=7):
    import time
    now = time.time()
    for f in os.listdir(TEMP_PDF_DIR):
        fp = os.path.join(TEMP_PDF_DIR, f)
        if os.stat(fp).st_mtime < now - days * 86400:
            os.remove(fp)