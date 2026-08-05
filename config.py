"""Configuracion de la aplicacion. Los valores reales van en .env (no se sube a git)."""

import os

from dotenv import load_dotenv

load_dotenv()

SECRET_KEY = os.getenv("SECRET_KEY", "cambiar-en-produccion")

# --- SQL Server ---
DB_DRIVER = os.getenv("DB_DRIVER", "ODBC Driver 17 for SQL Server")
DB_SERVER = os.getenv("DB_SERVER", "localhost\\SQLEXPRESS")
DB_NAME = os.getenv("DB_NAME", "ConcursoMaquila")
DB_USER = os.getenv("DB_USER", "")
DB_PASSWORD = os.getenv("DB_PASSWORD", "")

# "1" = autenticacion de Windows, "0" = usuario/contrasena de SQL Server
DB_TRUSTED_CONNECTION = os.getenv("DB_TRUSTED_CONNECTION", "1") == "1"

# Usuario con el que se firman los movimientos de inventario mientras no
# exista login real. Debe existir en la tabla dbo.usuario.
USUARIO_SISTEMA = os.getenv("USUARIO_SISTEMA", "admin.inventario")
