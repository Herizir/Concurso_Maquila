from database.conexion_db import obtener_conexion

CAMPOS_DOCUMENTO = (
    "part_number",
    "revision",
    "dcn",
    "descripcion",
    "fecha_efectiva",
    "case_pack",
    "auto_calc_case",
    "factor_stock",
    "creado_por",
    "creado_fecha",
    "revisado_por",
    "revisado_fecha",
    "aprobado_por",
    "aprobado_fecha",
)

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

CAMPOS_REFERENCIA = ("numero", "titulo")


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


def _a_texto(valor):
    return "" if valor is None else str(valor).strip()


def _numero_limpio(valor):
    """50.0 -> 50, 12.5 -> 12.5. Evita mostrar decimales que nadie escribio."""
    numero = _a_decimal(valor)
    return int(numero) if numero == int(numero) else numero


# ---------- Documento (encabezado, ajustes de calculo y firmas) ----------

def _fila_a_documento(fila):
    documento = {campo: fila[campo] for campo in CAMPOS_DOCUMENTO}
    documento["auto_calc_case"] = bool(fila["auto_calc_case"])
    documento["case_pack"] = _numero_limpio(fila["case_pack"])
    documento["factor_stock"] = _numero_limpio(fila["factor_stock"])
    return documento


def _documento_a_valores(documento):
    return (
        _a_texto(documento.get("part_number")),
        _a_texto(documento.get("revision")),
        _a_texto(documento.get("dcn")),
        _a_texto(documento.get("descripcion")),
        _a_texto(documento.get("fecha_efectiva")),
        _a_decimal(documento.get("case_pack"), 50.0),
        1 if documento.get("auto_calc_case") else 0,
        _a_decimal(documento.get("factor_stock"), 2.0),
        _a_texto(documento.get("creado_por")),
        _a_texto(documento.get("creado_fecha")),
        _a_texto(documento.get("revisado_por")),
        _a_texto(documento.get("revisado_fecha")),
        _a_texto(documento.get("aprobado_por")),
        _a_texto(documento.get("aprobado_fecha")),
    )


# ---------- Materiales ----------

def _fila_a_material(fila):
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


def _material_a_valores(material):
    return (
        _a_entero(material.get("no")),
        _a_texto(material.get("desc")),
        _a_texto(material.get("pn")),
        _a_decimal(material.get("qty")),
        _a_texto(material.get("uom")) or "ea",
        _a_decimal(material.get("caseQty")),
        _a_decimal(material.get("stock")),
        _a_decimal(material.get("minimo")),
    )


# ---------- Reference Documents ----------

def _fila_a_referencia(fila):
    return {"id": fila["id"], "num": fila["numero"], "titulo": fila["titulo"]}


def _referencia_a_valores(referencia):
    return (_a_texto(referencia.get("num")), _a_texto(referencia.get("titulo")))


# ---------- Lectura y escritura ----------

def _leer_todo(conexion):
    documento = conexion.execute("SELECT * FROM documento WHERE id = 1").fetchone()
    materiales = conexion.execute("SELECT * FROM materiales ORDER BY id").fetchall()
    referencias = conexion.execute("SELECT * FROM referencias ORDER BY id").fetchall()
    return {
        "documento": _fila_a_documento(documento),
        "materiales": [_fila_a_material(fila) for fila in materiales],
        "referencias": [_fila_a_referencia(fila) for fila in referencias],
    }


def _sincronizar(conexion, tabla, campos, filas, a_valores):
    """Deja `tabla` identica a `filas`: actualiza, inserta e borra lo que sobra."""
    ids_actuales = {
        fila["id"] for fila in conexion.execute(f"SELECT id FROM {tabla}").fetchall()
    }
    ids_conservados = set()

    for fila in filas:
        valores = a_valores(fila)
        id_fila = fila.get("id")

        if id_fila in ids_actuales:
            asignaciones = ", ".join(f"{campo} = ?" for campo in campos)
            conexion.execute(
                f"UPDATE {tabla} SET {asignaciones} WHERE id = ?",
                (*valores, id_fila),
            )
            ids_conservados.add(id_fila)
        else:
            columnas = ", ".join(campos)
            marcadores = ", ".join("?" for _ in campos)
            cursor = conexion.execute(
                f"INSERT INTO {tabla} ({columnas}) VALUES ({marcadores})",
                valores,
            )
            ids_conservados.add(cursor.lastrowid)

    for id_borrado in ids_actuales - ids_conservados:
        conexion.execute(f"DELETE FROM {tabla} WHERE id = ?", (id_borrado,))


def obtener_inventario():
    """Documento completo: encabezado, materiales y documentos de referencia."""
    conexion = obtener_conexion()
    try:
        return _leer_todo(conexion)
    finally:
        conexion.close()


def guardar_inventario(datos):
    """Guarda el documento entero en una sola transaccion y devuelve el estado final.

    Si algo falla a medio camino, SQLite revierte todo y la base queda como estaba.
    """
    conexion = obtener_conexion()
    try:
        with conexion:
            asignaciones = ", ".join(f"{campo} = ?" for campo in CAMPOS_DOCUMENTO)
            conexion.execute(
                f"UPDATE documento SET {asignaciones} WHERE id = 1",
                _documento_a_valores(datos.get("documento") or {}),
            )
            _sincronizar(
                conexion, "materiales", CAMPOS_MATERIAL,
                datos.get("materiales") or [], _material_a_valores,
            )
            _sincronizar(
                conexion, "referencias", CAMPOS_REFERENCIA,
                datos.get("referencias") or [], _referencia_a_valores,
            )

        return _leer_todo(conexion)
    finally:
        conexion.close()
