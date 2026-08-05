import sqlite3

from config import DATABASE_PATH

_esquema_listo = False

# El documento es uno solo (BOM/DMR activo), de ahi el CHECK sobre el id.
ESQUEMA_DOCUMENTO = """
CREATE TABLE IF NOT EXISTS documento (
    id             INTEGER PRIMARY KEY CHECK (id = 1),
    part_number    TEXT    NOT NULL DEFAULT '',
    revision       TEXT    NOT NULL DEFAULT '',
    dcn            TEXT    NOT NULL DEFAULT '',
    descripcion    TEXT    NOT NULL DEFAULT '',
    fecha_efectiva TEXT    NOT NULL DEFAULT '',
    case_pack      REAL    NOT NULL DEFAULT 50,
    auto_calc_case INTEGER NOT NULL DEFAULT 1,
    factor_stock   REAL    NOT NULL DEFAULT 2,
    creado_por     TEXT    NOT NULL DEFAULT '',
    creado_fecha   TEXT    NOT NULL DEFAULT '',
    revisado_por   TEXT    NOT NULL DEFAULT '',
    revisado_fecha TEXT    NOT NULL DEFAULT '',
    aprobado_por   TEXT    NOT NULL DEFAULT '',
    aprobado_fecha TEXT    NOT NULL DEFAULT ''
)
"""

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

ESQUEMA_REFERENCIAS = """
CREATE TABLE IF NOT EXISTS referencias (
    id     INTEGER PRIMARY KEY AUTOINCREMENT,
    numero TEXT NOT NULL DEFAULT '',
    titulo TEXT NOT NULL DEFAULT ''
)
"""

DOCUMENTO_SEMILLA = (
    1, 'IS60ENO', 'B', '2425', 'Enteral Only Extension Set, 60"', '2024-10-16',
    50, 1, 2,
    'Luis Padilla', '2024-10-16',
    'Ernesto Ortega', '2024-10-16',
    'Monica Echeveria', '2024-10-16',
)

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
    (10, 'IS60ENO Shipper Box Label (Exterior Labels)', 'LBL-IS60ENO-CI', 0.02, 'ea', 1, 30, 50),
    (11, 'Enteral Extension Sets Instructions For Use', 'NC-EES-IFU', 0.02, 'ea', 1, 25, 50),
]

REFERENCIAS_SEMILLA = [
    ('WI-001', 'Mfg Work Instructions for Enteral Ext Sets'),
    ('DWG-IS60ENO', 'IS60ENO Drawing'),
    ('SOP-103', 'Receiving, In-Process and Shipping Inspection'),
    ('SOP-104', 'Production Work Orders Processing'),
    ('SOP-108', 'Label Control'),
    ('SOP-106', 'Control of Non-Conformances'),
]


def obtener_conexion():
    """Devuelve una conexion a SQLite con filas accesibles por nombre de columna."""
    conexion = sqlite3.connect(DATABASE_PATH)
    conexion.row_factory = sqlite3.Row
    _preparar(conexion)
    return conexion


def _preparar(conexion):
    """Crea el esquema y siembra el documento inicial una sola vez por proceso."""
    global _esquema_listo
    if _esquema_listo:
        return

    with conexion:
        conexion.execute(ESQUEMA_DOCUMENTO)
        conexion.execute(ESQUEMA_MATERIALES)
        conexion.execute(ESQUEMA_REFERENCIAS)

        if _esta_vacia(conexion, "documento"):
            conexion.execute(
                """
                INSERT INTO documento (
                    id, part_number, revision, dcn, descripcion, fecha_efectiva,
                    case_pack, auto_calc_case, factor_stock,
                    creado_por, creado_fecha,
                    revisado_por, revisado_fecha,
                    aprobado_por, aprobado_fecha
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                DOCUMENTO_SEMILLA,
            )

        if _esta_vacia(conexion, "materiales"):
            conexion.executemany(
                """
                INSERT INTO materiales
                    (numero, descripcion, parte, cantidad, unidad, cantidad_caja, existencia, minimo)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                MATERIALES_SEMILLA,
            )

        if _esta_vacia(conexion, "referencias"):
            conexion.executemany(
                "INSERT INTO referencias (numero, titulo) VALUES (?, ?)",
                REFERENCIAS_SEMILLA,
            )

    _esquema_listo = True


def _esta_vacia(conexion, tabla):
    return conexion.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0] == 0
