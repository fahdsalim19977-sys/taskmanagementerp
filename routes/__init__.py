# routes/__init__.py
from flask import Blueprint
import os
import sys

# ===== تأكد من أن المجلد الحالي في مسار البحث =====
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

auth_bp = Blueprint('auth', __name__, url_prefix='/')
users_bp = Blueprint('users', __name__, url_prefix='/')
clients_bp = Blueprint('clients', __name__, url_prefix='/')
trainers_bp = Blueprint('trainers', __name__, url_prefix='/trainers')
tasks_bp = Blueprint('tasks', __name__, url_prefix='/')
contracts_bp = Blueprint('contracts', __name__, url_prefix='/')
payments_bp = Blueprint('payments', __name__, url_prefix='/')
modules_bp = Blueprint('modules', __name__, url_prefix='/')
meetings_bp = Blueprint('meetings', __name__, url_prefix='/')
reports_bp = Blueprint('reports', __name__, url_prefix='/')
settings_bp = Blueprint('settings', __name__, url_prefix='/')
backups_bp = Blueprint('backups', __name__, url_prefix='/')

# ===== استيراد الملفات =====
from . import auth
from . import users
from . import clients
from . import trainers
from . import tasks
from . import contracts
from . import payments
from . import modules
from . import meetings
from . import reports
from . import settings
from . import backups