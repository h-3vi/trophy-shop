"""Расширения Flask вынесены отдельно во избежание циклических импортов."""
from flask_login import LoginManager
from flask_sqlalchemy import SQLAlchemy
from flask_wtf.csrf import CSRFProtect

db = SQLAlchemy()
login_manager = LoginManager()
csrf = CSRFProtect()

login_manager.login_view = "auth.login"
login_manager.login_message = "Для доступа к панели управления войдите в систему."
login_manager.login_message_category = "warning"