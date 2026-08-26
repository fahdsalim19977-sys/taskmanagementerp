# app.py
import os
import math
from flask import Flask, render_template, redirect, url_for, session, flash, jsonify, request
from config import Config
from models import init_db, get_db
from utils import get_company_settings, get_lang, t, log_activity
from datetime import datetime
from routes import trainers_bp

# ===== إنشاء التطبيق =====
app = Flask(__name__)
app.config.from_object(Config)

# SECRET_KEY is managed centrally by Config/environment variables.
# Never hard-code production secrets in source control.

# ===== مجلدات =====
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs('static', exist_ok=True)
os.makedirs(os.path.join(app.config['UPLOAD_FOLDER'], 'contracts'), exist_ok=True)

# ===== قاعدة البيانات =====
init_db()

# ===== تسجيل Blueprints =====
from routes import (
    auth_bp, users_bp, clients_bp, trainers_bp, tasks_bp,
    contracts_bp, payments_bp, modules_bp, meetings_bp,
    reports_bp, settings_bp, backups_bp
)

app.register_blueprint(auth_bp)
app.register_blueprint(users_bp)
app.register_blueprint(clients_bp)
app.register_blueprint(trainers_bp)
app.register_blueprint(tasks_bp)
app.register_blueprint(contracts_bp)
app.register_blueprint(payments_bp)
app.register_blueprint(modules_bp)
app.register_blueprint(meetings_bp)
app.register_blueprint(reports_bp)
app.register_blueprint(settings_bp)
app.register_blueprint(backups_bp)

# ===== دوال السياق =====
@app.context_processor
def inject_globals():
    return {
        'settings': get_company_settings(),
        'lang': get_lang(),
        't': t,
    }
