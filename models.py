"""Acceso a datos del documento BOM / DMR sobre SQL Server.

La interfaz publica es la misma que ya consumia app.py cuando la base era
SQLite, y el JSON que entra y sale no cambio ni un campo:

    obtener_inventario()   -> {"documento": {...}, "materiales": [...], "referencias": [...]}
    guardar_inventario(d)  -> lo mismo, ya guardado

Lo que cambio es a donde va a parar cada dato:

    documento.part_number, descripcion  -> dbo.articulo (el producto terminado)
    documento.revision, dcn, fecha...   -> dbo.dmr
    documento.factor_stock              -> dbo.configuracion
    documento.*_por / *_fecha           -> dbo.dmr_aprobacion (3 renglones)
    materiales[]                        -> dbo.bom_linea + dbo.articulo
    materiales[].stock                  -> movimiento de ajuste en el kardex (*)
    referencias[]                       -> dbo.documento_referencia + dbo.dmr_referencia

(*) La diferencia importante: la existencia no es una columna que se sobrescriba.
    Si el usuario cambia 600 por 560, no se guarda "560": se registra un ajuste
    de -40 en dbo.movimiento_inventario y el trigger recalcula el saldo. Para el
    usuario es el mismo input de siempre; atras queda el rastro de quien lo movio.
"""

from datetime import date, datetime
from decimal import Decimal

import config
from database.conexion_db import fila, filas, obtener_conexion

CAMPOS_DOCUMENTO = (
    "part_number",
    "revision",
    "dcn",
    "descripcion",
    "fecha_efectiva",
    "especificaciones",
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

# tipo en dbo.dmr_aprobacion -> par de campos del JSON
APROBACIONES = {
    "creado": ("creado_por", "creado_fecha"),
    "revisado": ("revisado_por", "revisado_fecha"),
    "aprobado": ("aprobado_por", "aprobado_fecha"),
}


# ---------- Conversiones ----------

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


def _a_fecha(valor):
    """'2024-10-16' -> date. Cadena vacia o basura -> None."""
    texto = _a_texto(valor)
    if not texto:
        return None
    try:
        return datetime.strptime(texto[:10], "%Y-%m-%d").date()
    except ValueError:
        return None


def _de_fecha(valor):
    """date -> '2024-10-16', que es lo que espera un <input type="date">."""
    if isinstance(valor, (date, datetime)):
        return valor.strftime("%Y-%m-%d")
    return _a_texto(valor)


def _de_numero(valor):
    """SQL Server devuelve DECIMAL como Decimal, y jsonify no sabe serializarlo."""
    if isinstance(valor, Decimal):
        return _numero_limpio(float(valor))
    return _numero_limpio(valor)


# ---------- Lectura ----------

def _dmr_activo(cursor):
    """El documento vigente. Si no hay ninguno aprobado, toma el mas reciente."""
    cursor.execute(
        """
        SELECT TOP 1 d.id, d.articulo_id, d.revision, d.dcn, d.effective_date,
                     d.case_pack, d.auto_calc_case, d.especificaciones,
                     a.part_number, a.descripcion
        FROM dbo.dmr d
        JOIN dbo.articulo a ON a.id = d.articulo_id
        ORDER BY CASE WHEN d.estado = 'aprobado' THEN 0 ELSE 1 END, d.id DESC
        """
    )
    documento = fila(cursor)
    if documento is None:
        raise RuntimeError(
            "No hay ningun DMR en la base. Corre database/seed.sql antes de usar la app."
        )
    return documento


def _leer_documento(cursor, dmr):
    cursor.execute(
        "SELECT tipo, nombre, fecha FROM dbo.dmr_aprobacion WHERE dmr_id = ?",
        dmr["id"],
    )
    firmas = {f["tipo"]: f for f in filas(cursor)}

    cursor.execute(
        "SELECT valor FROM dbo.configuracion WHERE clave = 'factor_stock_objetivo'"
    )
    factor = fila(cursor)

    documento = {
        "part_number": _a_texto(dmr["part_number"]),
        "revision": _a_texto(dmr["revision"]),
        "dcn": _a_texto(dmr["dcn"]),
        "descripcion": _a_texto(dmr["descripcion"]),
        "fecha_efectiva": _de_fecha(dmr["effective_date"]),
        "especificaciones": _a_texto(dmr["especificaciones"]),
        "case_pack": _de_numero(dmr["case_pack"]),
        "auto_calc_case": bool(dmr["auto_calc_case"]),
        "factor_stock": _numero_limpio(factor["valor"]) if factor else 2,
    }

    for tipo, (campo_nombre, campo_fecha) in APROBACIONES.items():
        firma = firmas.get(tipo)
        documento[campo_nombre] = _a_texto(firma["nombre"]) if firma else ""
        documento[campo_fecha] = _de_fecha(firma["fecha"]) if firma else ""

    return documento


def _leer_materiales(cursor, dmr_id):
    cursor.execute(
        """
        SELECT  bl.id, bl.no_linea, bl.cantidad, bl.uom, bl.case_quantity,
                a.part_number, a.descripcion, a.stock_minimo,
                ISNULL(e.cantidad, 0) AS existencia
        FROM        dbo.bom_linea bl
        JOIN        dbo.articulo   a ON a.id = bl.articulo_id
        LEFT JOIN   dbo.existencia e ON e.articulo_id = bl.articulo_id
        WHERE bl.dmr_id = ?
        ORDER BY bl.no_linea, bl.id
        """,
        dmr_id,
    )
    return [
        {
            "id": f["id"],
            "no": f["no_linea"],
            "desc": _a_texto(f["descripcion"]),
            "pn": _a_texto(f["part_number"]),
            "qty": _de_numero(f["cantidad"]),
            "uom": _a_texto(f["uom"]),
            "caseQty": _de_numero(f["case_quantity"]),
            "stock": _de_numero(f["existencia"]),
            "minimo": _de_numero(f["stock_minimo"]),
        }
        for f in filas(cursor)
    ]


def _leer_referencias(cursor, dmr_id):
    cursor.execute(
        """
        SELECT r.id, r.numero, r.titulo
        FROM      dbo.dmr_referencia       dr
        JOIN      dbo.documento_referencia r ON r.id = dr.documento_id
        WHERE dr.dmr_id = ?
        ORDER BY r.id
        """,
        dmr_id,
    )
    return [
        {"id": f["id"], "num": _a_texto(f["numero"]), "titulo": _a_texto(f["titulo"])}
        for f in filas(cursor)
    ]


def _leer_todo(cursor):
    dmr = _dmr_activo(cursor)
    return {
        "documento": _leer_documento(cursor, dmr),
        "materiales": _leer_materiales(cursor, dmr["id"]),
        "referencias": _leer_referencias(cursor, dmr["id"]),
    }


# ---------- Escritura ----------

def _usuario_sistema(cursor):
    """Usuario que firma los ajustes de inventario mientras no haya login real."""
    cursor.execute(
        "SELECT TOP 1 id FROM dbo.usuario WHERE username = ? AND activo = 1",
        config.USUARIO_SISTEMA,
    )
    encontrado = fila(cursor)
    if encontrado:
        return encontrado["id"]

    cursor.execute("SELECT TOP 1 id FROM dbo.usuario ORDER BY id")
    encontrado = fila(cursor)
    if encontrado is None:
        raise RuntimeError(
            "No hay usuarios en la base. Corre database/seed.sql antes de usar la app."
        )
    return encontrado["id"]


def _guardar_documento(cursor, dmr, documento):
    """Reparte el encabezado entre articulo, dmr, configuracion y las firmas."""
    cursor.execute(
        "UPDATE dbo.articulo SET part_number = ?, descripcion = ? WHERE id = ?",
        _a_texto(documento.get("part_number")) or dmr["part_number"],
        _a_texto(documento.get("descripcion")),
        dmr["articulo_id"],
    )

    cursor.execute(
        """
        UPDATE dbo.dmr
           SET revision = ?, dcn = ?, effective_date = ?, case_pack = ?,
               auto_calc_case = ?, especificaciones = ?
         WHERE id = ?
        """,
        _a_texto(documento.get("revision")),
        _a_texto(documento.get("dcn")),
        _a_fecha(documento.get("fecha_efectiva")) or dmr["effective_date"],
        _a_decimal(documento.get("case_pack"), 50.0),
        1 if documento.get("auto_calc_case") else 0,
        _a_texto(documento.get("especificaciones")) or "N/A",
        dmr["id"],
    )

    # El factor de stock objetivo es un ajuste global, no del documento.
    factor = str(_a_decimal(documento.get("factor_stock"), 2.0))
    cursor.execute(
        """
        UPDATE dbo.configuracion SET valor = ? WHERE clave = 'factor_stock_objetivo';
        IF @@ROWCOUNT = 0
            INSERT INTO dbo.configuracion (clave, valor, descripcion)
            VALUES ('factor_stock_objetivo', ?, 'Stock objetivo = stock_minimo * este factor');
        """,
        factor, factor,
    )

    for tipo, (campo_nombre, campo_fecha) in APROBACIONES.items():
        nombre = _a_texto(documento.get(campo_nombre))
        fecha_firma = _a_fecha(documento.get(campo_fecha))
        cursor.execute(
            """
            UPDATE dbo.dmr_aprobacion SET nombre = ?, fecha = ?
             WHERE dmr_id = ? AND tipo = ?;
            IF @@ROWCOUNT = 0
                INSERT INTO dbo.dmr_aprobacion (dmr_id, tipo, nombre, fecha)
                VALUES (?, ?, ?, ?);
            """,
            nombre, fecha_firma, dmr["id"], tipo,
            dmr["id"], tipo, nombre, fecha_firma,
        )


def _articulo_de(cursor, material):
    """Busca el articulo por P/N; si no existe lo crea. Devuelve su id."""
    part_number = _a_texto(material.get("pn"))
    descripcion = _a_texto(material.get("desc"))
    uom = _a_texto(material.get("uom")) or "ea"
    minimo = _a_decimal(material.get("minimo"))

    if not part_number:
        raise ValueError(
            f"Falta el P/N del material '{descripcion or 'sin descripcion'}'."
        )

    cursor.execute("SELECT id FROM dbo.articulo WHERE part_number = ?", part_number)
    encontrado = fila(cursor)

    if encontrado:
        cursor.execute(
            """
            UPDATE dbo.articulo
               SET descripcion = ?, uom = ?, stock_minimo = ?, activo = 1
             WHERE id = ?
            """,
            descripcion, uom, minimo, encontrado["id"],
        )
        return encontrado["id"]

    cursor.execute(
        """
        INSERT INTO dbo.articulo (part_number, descripcion, tipo, uom, stock_minimo)
        OUTPUT INSERTED.id
        VALUES (?, ?, 'componente', ?, ?)
        """,
        part_number, descripcion, uom, minimo,
    )
    return fila(cursor)["id"]


def _ajustar_existencia(cursor, articulo_id, uom, stock_pedido, usuario_id):
    """Convierte 'la existencia ahora es X' en un movimiento de ajuste.

    Es el corazon del cambio contra la version en SQLite: el saldo no se
    sobrescribe, se mueve. El trigger tg_movimiento_aplicar recalcula
    dbo.existencia por su cuenta.
    """
    cursor.execute(
        "SELECT ISNULL(cantidad, 0) AS cantidad FROM dbo.existencia WHERE articulo_id = ?",
        articulo_id,
    )
    encontrado = fila(cursor)
    actual = float(encontrado["cantidad"]) if encontrado else 0.0

    diferencia = round(stock_pedido - actual, 7)
    if diferencia == 0:
        return

    cursor.execute(
        """
        INSERT INTO dbo.movimiento_inventario
            (articulo_id, tipo, cantidad, uom, usuario_id, referencia, motivo)
        VALUES (?, 'ajuste', ?, ?, ?, 'BOM/DMR', ?)
        """,
        articulo_id, diferencia, uom, usuario_id,
        f"Ajuste desde el documento: {actual} -> {stock_pedido}",
    )


def _part_numbers_repetidos(materiales):
    vistos, repetidos = set(), []
    for material in materiales:
        part_number = _a_texto(material.get("pn"))
        if not part_number:
            continue
        if part_number in vistos and part_number not in repetidos:
            repetidos.append(part_number)
        vistos.add(part_number)
    return repetidos


def _guardar_materiales(cursor, dmr_id, materiales, usuario_id):
    """Deja bom_linea igual a lo que mando el navegador."""
    duplicados = _part_numbers_repetidos(materiales)
    if duplicados:
        raise ValueError(
            "El BOM no puede listar dos veces el mismo P/N: "
            + ", ".join(duplicados)
            + ". Si necesitas mas cantidad, sube el campo Quantity de esa fila."
        )

    cursor.execute("SELECT id FROM dbo.bom_linea WHERE dmr_id = ?", dmr_id)
    ids_actuales = {f["id"] for f in filas(cursor)}
    ids_conservados = set()

    for material in materiales:
        cantidad = _a_decimal(material.get("qty"))
        if cantidad <= 0:
            raise ValueError(
                f"La cantidad de '{_a_texto(material.get('pn')) or 'la fila nueva'}' "
                "debe ser mayor que cero."
            )

        articulo_id = _articulo_de(cursor, material)
        no_linea = _a_entero(material.get("no"))
        uom = _a_texto(material.get("uom")) or "ea"
        case_qty = _a_decimal(material.get("caseQty"))
        id_fila = material.get("id")

        if id_fila in ids_actuales:
            cursor.execute(
                """
                UPDATE dbo.bom_linea
                   SET no_linea = ?, articulo_id = ?, cantidad = ?, uom = ?, case_quantity = ?
                 WHERE id = ?
                """,
                no_linea, articulo_id, cantidad, uom, case_qty, id_fila,
            )
            ids_conservados.add(id_fila)
        else:
            cursor.execute(
                """
                INSERT INTO dbo.bom_linea (dmr_id, no_linea, articulo_id, cantidad, uom, case_quantity)
                OUTPUT INSERTED.id
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                dmr_id, no_linea, articulo_id, cantidad, uom, case_qty,
            )
            ids_conservados.add(fila(cursor)["id"])

        _ajustar_existencia(
            cursor, articulo_id, uom, _a_decimal(material.get("stock")), usuario_id
        )

    # Sacar una fila del BOM no borra el articulo: conserva su historial de
    # movimientos y puede seguir usandose en otros documentos.
    for id_borrado in ids_actuales - ids_conservados:
        cursor.execute("DELETE FROM dbo.bom_linea WHERE id = ?", id_borrado)


def _guardar_referencias(cursor, dmr_id, referencias):
    cursor.execute(
        "SELECT documento_id FROM dbo.dmr_referencia WHERE dmr_id = ?", dmr_id
    )
    ids_actuales = {f["documento_id"] for f in filas(cursor)}
    ids_conservados = set()

    for referencia in referencias:
        numero = _a_texto(referencia.get("num"))
        titulo = _a_texto(referencia.get("titulo"))
        id_fila = referencia.get("id")

        if id_fila in ids_actuales:
            cursor.execute(
                "UPDATE dbo.documento_referencia SET numero = ?, titulo = ? WHERE id = ?",
                numero, titulo, id_fila,
            )
            ids_conservados.add(id_fila)
            continue

        # El catalogo de documentos es global: si el numero ya existe se
        # reutiliza en vez de duplicarlo.
        cursor.execute(
            "SELECT id FROM dbo.documento_referencia WHERE numero = ?", numero
        )
        encontrado = fila(cursor)

        if encontrado:
            documento_id = encontrado["id"]
            cursor.execute(
                "UPDATE dbo.documento_referencia SET titulo = ? WHERE id = ?",
                titulo, documento_id,
            )
        else:
            cursor.execute(
                """
                INSERT INTO dbo.documento_referencia (numero, titulo)
                OUTPUT INSERTED.id
                VALUES (?, ?)
                """,
                numero, titulo,
            )
            documento_id = fila(cursor)["id"]

        if documento_id not in ids_actuales:
            cursor.execute(
                "INSERT INTO dbo.dmr_referencia (dmr_id, documento_id) VALUES (?, ?)",
                dmr_id, documento_id,
            )
        ids_conservados.add(documento_id)

    # Se desliga del documento, pero el SOP sigue en el catalogo global.
    for id_borrado in ids_actuales - ids_conservados:
        cursor.execute(
            "DELETE FROM dbo.dmr_referencia WHERE dmr_id = ? AND documento_id = ?",
            dmr_id, id_borrado,
        )


# ---------- Interfaz publica ----------

def obtener_inventario():
    """Documento completo: encabezado, materiales y documentos de referencia."""
    with obtener_conexion() as cursor:
        return _leer_todo(cursor)


def guardar_inventario(datos):
    """Guarda el documento entero en una sola transaccion y devuelve el estado final.

    Si algo falla a medio camino, SQL Server revierte todo y la base queda igual.
    """
    with obtener_conexion() as cursor:
        dmr = _dmr_activo(cursor)
        usuario_id = _usuario_sistema(cursor)

        _guardar_documento(cursor, dmr, datos.get("documento") or {})
        _guardar_materiales(cursor, dmr["id"], datos.get("materiales") or [], usuario_id)
        _guardar_referencias(cursor, dmr["id"], datos.get("referencias") or [])

        return _leer_todo(cursor)
