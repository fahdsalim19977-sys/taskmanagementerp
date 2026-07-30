# index.py
from app import app
import sys
import os

# ===== إعدادات CGI =====
if os.name == 'nt':
    sys.stdout = sys.stdout  # تأكد من الـ stdout

# ===== تشغيل التطبيق =====
if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
