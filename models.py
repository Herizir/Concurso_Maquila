from database.conexion_db import obtener_conexion

CAMPOS_MATERIAL = (
    "numero",
    "descripcion",
    "parte",
    "cantidad",
    "unidad",
    "cantidad_caja",
    "existencia",
    "minimo",
)


def _a_decimal(valor, por_defecto=0.0):
    try:
        return float(valor)
    except (TypeError, ValueError):
        return por_defecto


def _a_entero(valor, por_defecto=0):
    try:
        return int(float(valor))
    except (TypeError, ValueError):
        return por_defecto


def _fila_a_dict(fila):
    """Convierte una fila de la tabla materiales al formato que consume la vista."""
    return {
        "id": fila["id"],
        "no": fila["numero"],
        "desc": fila["descripcion"],
        "pn": fila["parte"],
        "qty": fila["cantidad"],
        "uom": fila["unidad"],
        "caseQty": fila["cantidad_caja"],
        "stock": fila["existencia"],
        "minimo": fila["minimo"],
    }


def _dict_a_valores(material):
    """Normaliza el material recibido del navegador al orden de CAMPOS_MATERIAL."""
    return (
        _a_entero(material.get("no")),
        str(material.get("desc") or "").strip(),
        str(material.get("pn") or "").strip(),
        _a_decimal(material.get("qty")),
        str(material.get("uom") or "ea").strip(),
        _a_decimal(material.get("caseQty")),
        _a_decimal(material.get("stock")),
        _a_decimal(material.get("minimo")),
    )


def obtener_materiales():
    """Lista completa del BOM, en el orden en que se capturo."""
    conexion = obtener_conexion()
    try:
        filas = conexion.execute("SELECT * FROM materiales ORDER BY id").fetchall()
        return [_fila_a_dict(fila) for fila in filas]
    finally:
        conexion.close()


def guardar_materiales(materiales):
    """Sincroniza la tabla con lo que envio la vista y devuelve el estado ya guardado.

    Los materiales con id existente se actualizan, los que llegan sin id se
    insertan y los que ya no aparecen en la lista se eliminan.
    """
    conexion = obtener_conexion()
    try:
        with conexion:
            ids_actuales = {
                fila["id"]
                for fila in conexion.execute("SELECT id FROM materiales").fetchall()
            }
            ids_conservados = set()

            for material in materiales:
                valores = _dict_a_valores(material)
                id_material = material.get("id")

                if id_material in ids_actuales:
                    asignaciones = ", ".join(f"{campo} = ?" for campo in CAMPOS_MATERIAL)
                    conexion.execute(
                        f"UPDATE materiales SET {asignaciones} WHERE id = ?",
                        (*valores, id_material),
                    )
                    ids_conservados.add(id_material)
                else:
                    columnas = ", ".join(CAMPOS_MATERIAL)
                    marcadores = ", ".join("?" for _ in CAMPOS_MATERIAL)
                    cursor = conexion.execute(
                        f"INSERT INTO materiales ({columnas}) VALUES ({marcadores})",
                        valores,
                    )
                    ids_conservados.add(cursor.lastrowid)

            for id_eliminado in ids_actuales - ids_conservados:
                conexion.execute("DELETE FROM materiales WHERE id = ?", (id_eliminado,))

        filas = conexion.execute("SELECT * FROM materiales ORDER BY id").fetchall()
        return [_fila_a_dict(fila) for fila in filas]
    finally:
        conexion.close()
