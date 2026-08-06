# routes/__init__.py
from flask import Blueprint

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

from . import auth, users, clients, trainers, tasks, contracts, payments, modules, meetings, reports, settings, backups
#                          ^^^^^^^^
#                          تأكد من وجودها