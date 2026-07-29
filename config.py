import os

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Base de datos SQLite: un solo archivo dentro de database/
DATABASE_PATH = os.path.join(BASE_DIR, "database", "inventario.db")
