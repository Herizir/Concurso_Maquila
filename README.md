# Concurso_Maquila

Sistema de inventario y produccion para maquila de dispositivos medicos (BOM / DMR).
Flask + Bootstrap 5 + SQL Server.

## 1. Entorno virtual

    python -m venv venv
    venv\Scripts\activate

## 2. Dependencias

    pip install flask pyodbc python-dotenv

Ademas hace falta el **ODBC Driver 17 for SQL Server**, que se descarga del sitio
de Microsoft. Para revisar si ya lo tienes instalado:

    python -c "import pyodbc; print(pyodbc.drivers())"

Para el frontend (Bootstrap):

    npm install

## 3. Base de datos

Crear el esquema y cargar los datos iniciales. Se ejecutan con sqlcmd o SSMS,
**no desde Python**, porque usan lotes `GO`:

    sqlcmd -S localhost\SQLEXPRESS -E -C -i database\schema.sql
    sqlcmd -S localhost\SQLEXPRESS -E -C -i database\seed.sql

Si usas usuario de SQL Server en vez de autenticacion de Windows, cambia `-E`
por `-U tu_usuario -P tu_password`.

El seed termina imprimiendo un resumen. Si todo cargo bien debe decir
**11 materiales, 4 bajo minimo, 7 en nivel alto**.

## 4. Credenciales

Copiar el archivo de ejemplo y ajustar los valores:

    copy .env.example .env

El `.env` no se sube a git. Para probar que la conexion funciona:

    python database\conexion_db.py

## 5. Correr el programa

Con el entorno virtual activado:

    flask run

## Base de datos

| Archivo | Contenido |
|---|---|
| `database/schema.sql` | Tablas, trigger del kardex, vistas y stored procedure |
| `database/seed.sql` | BOM del IS60ENO Rev. B, materiales, referencias y ordenes |
| `database/conexion_db.py` | Conexion pyodbc con commit/rollback automatico |
| `models.py` | Lectura y escritura del documento BOM / DMR |

Puntos clave del diseno:

- **El stock no se sobrescribe.** La existencia sale de sumar
  `dbo.movimiento_inventario` (kardex) y un trigger mantiene el saldo en
  `dbo.existencia`. Cuando alguien edita la existencia en la pantalla de
  inventario, se registra un **movimiento de ajuste** con la diferencia, no un
  UPDATE encima del saldo. Asi queda el rastro de quien lo movio y cuando.
- **El DMR se versiona.** Nunca se hace UPDATE sobre una revision aprobada, se
  crea una nueva; solo puede haber una revision aprobada por articulo.
- **Las ordenes congelan el BOM.** `orden_material` guarda las cantidades
  copiadas al crear la orden, para no perder la trazabilidad si el BOM cambia.
- **`DECIMAL(18,7)`, nunca `FLOAT`.** El BOM maneja cantidades como `0.0000075 gl`.
- **`dbo.articulo` es una tabla temporal.** SQL Server guarda solo el historial
  de cambios; se consulta con `FOR SYSTEM_TIME AS OF 'fecha'`.

### Un material no se puede listar dos veces en el mismo BOM

`dbo.bom_linea` tiene `UNIQUE (dmr_id, articulo_id)`. Si necesitas mas cantidad
de un material, sube su campo Quantity en vez de agregar otra fila con el mismo
P/N. La pantalla avisa con un mensaje claro si se intenta.

### Si sqlcmd marca el error 1934

Los scripts ya traen `SET QUOTED_IDENTIFIER ON`, que los indices filtrados y las
tablas temporales exigen. Si corres pedazos sueltos desde SSMS, asegurate de que
esa opcion este encendida en tu sesion.
