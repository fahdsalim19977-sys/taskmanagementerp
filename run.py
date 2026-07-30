from app import app
from waitress import serve

print("🚀 تشغيل نظام إدارة المهام على Waitress...")
print("📍 http://127.0.0.1:5000")
serve(app, host='0.0.0.0', port=5000)
