"""Conexion a SQL Server con pyodbc.

El esquema NO se crea aqui: se crea una sola vez con database/schema.sql y
database/seed.sql (ver README). Este modulo solo abre y cierra conexiones.

Instalar:  pip install pyodbc python-dotenv
Driver:    "ODBC Driver 17 for SQL Server" (descarga de Microsoft)
"""

import pyodbc
from contextlib import contextmanager

import config


def cadena_conexion():
    """Arma el connection string segun el tipo de autenticacion configurado."""
    partes = [
        f"DRIVER={{{config.DB_DRIVER}}}",
        f"SERVER={config.DB_SERVER}",
        f"DATABASE={config.DB_NAME}",
        "TrustServerCertificate=yes",
    ]

    if config.DB_TRUSTED_CONNECTION:
        partes.append("Trusted_Connection=yes")   # autenticacion de Windows
    else:
        partes.append(f"UID={config.DB_USER}")
        partes.append(f"PWD={config.DB_PASSWORD}")

    return ";".join(partes)


@contextmanager
def obtener_conexion():
    """Abre una conexion y hace commit al salir, o rollback si algo truena.

        with obtener_conexion() as cursor:
            cursor.execute("SELECT ...")
    """
    conexion = pyodbc.connect(cadena_conexion(), autocommit=False)
    cursor = conexion.cursor()
    try:
        yield cursor
        conexion.commit()
    except Exception:
        conexion.rollback()
        raise
    finally:
        conexion.close()


def filas(cursor):
    """Las filas de pyodbc no se indexan por nombre; aqui se vuelven dicts."""
    columnas = [col[0] for col in cursor.description]
    return [dict(zip(columnas, fila)) for fila in cursor.fetchall()]


def fila(cursor):
    """La primera fila como dict, o None si no hubo resultados."""
    resultado = filas(cursor)
    return resultado[0] if resultado else None


def probar_conexion():
    """Diagnostico: imprime la version del servidor si todo esta bien."""
    try:
        with obtener_conexion() as cursor:
            cursor.execute("SELECT @@VERSION AS version")
            print("Conexion correcta:", fila(cursor)["version"].splitlines()[0])
            cursor.execute("SELECT COUNT(*) AS total FROM dbo.articulo")
            print("Articulos en la base:", fila(cursor)["total"])
        return True
    except Exception as error:
        print("Fallo la conexion:", error)
        print("Drivers ODBC instalados:", pyodbc.drivers())
        return False


if __name__ == "__main__":
    probar_conexion()
