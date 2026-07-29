import sqlite3

from config import DATABASE_PATH

_esquema_listo = False

ESQUEMA_MATERIALES = """
CREATE TABLE IF NOT EXISTS materiales (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    numero        INTEGER,
    descripcion   TEXT    NOT NULL DEFAULT '',
    parte         TEXT    NOT NULL DEFAULT '',
    cantidad      REAL    NOT NULL DEFAULT 0,
    unidad        TEXT    NOT NULL DEFAULT 'ea',
    cantidad_caja REAL    NOT NULL DEFAULT 0,
    existencia    REAL    NOT NULL DEFAULT 0,
    minimo        REAL    NOT NULL DEFAULT 0
)
"""

# BOM inicial del documento IS60ENO Rev. B (DCN 2425).
# Orden: numero, descripcion, parte, cantidad, unidad, cantidad_caja, existencia, minimo
MATERIALES_SEMILLA = [
    (1, 'PVC Tubing Clear (.047x.085x60")', '20-001-4-L', 1, 'ea', 50, 560, 200),
    (2, 'Legacy Enteral Male Connector', '20-003-L', 1, 'ea', 50, 480, 200),
    (3, 'Legacy Enteral Female Connector', '20-004-L', 1, 'ea', 50, 480, 200),
    (4, 'Slide Clamp', '10-010-L', 1, 'ea', 50, 610, 200),
    (5, 'Cyclohexanone (Bonding Agent)', '10-014-L', 0.0000075, 'gl', 0.000375, 0.9, 2),
    (6, 'Paper Tape 2"', '10-015-L', 0.0015, 'ea', 0.075, 4, 10),
    (7, '6" x 6" (15cm x 15cm) Plain Pouch', '10-016-L', 1, 'ea', 50, 700, 300),
    (8, 'IS60ENO Label Insert (insert Label)', 'LBL-IS60ENO-PI', 1, 'ea', 50, 650, 300),
    (9, 'Box 10" x 8" x 6"', '10-019-L', 0.02, 'ea', 1, 1250, 500),
    (9, 'IS60ENO Shipper Box Label (Exterior Labels)', 'LBL-IS60ENO-CI', 0.02, 'ea', 1, 30, 50),
    (9, 'Enteral Extension Sets Instructions For Use', 'NC-EES-IFU', 0.02, 'ea', 1, 25, 50),
]


def obtener_conexion():
    """Devuelve una conexion a SQLite con filas accesibles por nombre de columna."""
    conexion = sqlite3.connect(DATABASE_PATH)
    conexion.row_factory = sqlite3.Row
    _preparar(conexion)
    return conexion


def _preparar(conexion):
    """Crea el esquema y siembra el BOM inicial una sola vez por proceso."""
    global _esquema_listo
    if _esquema_listo:
        return

    with conexion:
        conexion.execute(ESQUEMA_MATERIALES)
        vacia = conexion.execute("SELECT COUNT(*) FROM materiales").fetchone()[0] == 0
        if vacia:
            conexion.executemany(
                """
                INSERT INTO materiales
                    (numero, descripcion, parte, cantidad, unidad, cantidad_caja, existencia, minimo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                MATERIALES_SEMILLA,
            )

    _esquema_listo = True
