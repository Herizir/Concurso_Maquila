/* ============================================================
   Concurso_Maquila - Datos iniciales
   Son exactamente los datos que hoy estan hardcodeados en el JS
   de inventario.html, produccion.html y dashboard.html.
   Ejecutar DESPUES de schema.sql.
   ============================================================ */

USE ConcursoMaquila;
GO

/* Necesario para escribir en tablas que tienen indices filtrados. */
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

/* ---------- Catalogos ---------- */

INSERT INTO dbo.departamento (nombre) VALUES
    (N'Almacen'), (N'Produccion'), (N'Calidad'), (N'Empaque y etiquetado'), (N'General');

INSERT INTO dbo.turno (nombre, hora_inicio, hora_fin) VALUES
    (N'Matutino',   '06:00', '14:00'),
    (N'Vespertino', '14:00', '22:00'),
    (N'Nocturno',   '22:00', '06:00');

INSERT INTO dbo.unidad_medida (codigo, descripcion) VALUES
    (N'ea',   N'Pieza (each)'),
    (N'gl',   N'Galon'),
    (N'kg',   N'Kilogramo'),
    (N'm',    N'Metro'),
    (N'l',    N'Litro'),
    (N'pza',  N'Pieza'),
    (N'caja', N'Caja');

INSERT INTO dbo.proveedor (nombre) VALUES
    (N'Extrusiones Medicas SA'),
    (N'Componentes Enterales del Norte'),
    (N'Empaques y Etiquetas Delta');

INSERT INTO dbo.configuracion (clave, valor, descripcion) VALUES
    (N'factor_stock_objetivo', N'2',       N'Stock objetivo = stock_minimo * este factor'),
    (N'case_pack_default',     N'50',      N'Unidades por caja por omision'),
    (N'empresa',               N'lifeOutcomes, LLC', N'Razon social del documento DMR');
GO

/* ---------- Usuarios ----------
   OJO: los hash de abajo son PLACEHOLDER. Generalos con:
     from werkzeug.security import generate_password_hash
     generate_password_hash("tu_password")
   y reemplazalos antes de entregar.                              */

INSERT INTO dbo.usuario (username, password_hash, nombre_completo, rol, departamento_id, turno_id)
SELECT N'admin.inventario', N'CAMBIAR_HASH', N'Administrador del sistema', N'administrador',
       (SELECT id FROM dbo.departamento WHERE nombre = N'General'),
       (SELECT id FROM dbo.turno WHERE nombre = N'Matutino')
UNION ALL
SELECT N'personal.almacen', N'CAMBIAR_HASH', N'Personal de almacen', N'personal',
       (SELECT id FROM dbo.departamento WHERE nombre = N'Almacen'),
       (SELECT id FROM dbo.turno WHERE nombre = N'Matutino');
GO

/* ---------- Articulo terminado + los 11 componentes del BOM ---------- */

DECLARE @almacen INT = (SELECT id FROM dbo.departamento WHERE nombre = N'Almacen');
DECLARE @produccion INT = (SELECT id FROM dbo.departamento WHERE nombre = N'Produccion');
DECLARE @empaque INT = (SELECT id FROM dbo.departamento WHERE nombre = N'Empaque y etiquetado');

INSERT INTO dbo.articulo (part_number, descripcion, tipo, uom, departamento_id, ubicacion, stock_minimo, stock_maximo) VALUES
 (N'IS60ENO',        N'Enteral Only Extension Set, 60"',                    N'terminado',  N'ea', @produccion, NULL,      0,   NULL),
 (N'20-001-4-L',     N'PVC Tubing Clear (.047x.085x60")',                   N'componente', N'ea', @almacen,    N'A-03-R2', 200, 900),
 (N'20-003-L',       N'Legacy Enteral Male Connector',                      N'componente', N'ea', @almacen,    N'A-04-R1', 200, 900),
 (N'20-004-L',       N'Legacy Enteral Female Connector',                    N'componente', N'ea', @almacen,    N'A-04-R2', 200, 900),
 (N'10-010-L',       N'Slide Clamp',                                        N'componente', N'ea', @almacen,    N'A-05-R1', 200, 900),
 (N'10-014-L',       N'Cyclohexanone (Bonding Agent)',                      N'componente', N'gl', @produccion, N'B-01-Q1', 2,   10),
 (N'10-015-L',       N'Paper Tape 2"',                                      N'componente', N'ea', @produccion, N'B-01-R3', 10,  60),
 (N'10-016-L',       N'6" x 6" (15cm x 15cm) Plain Pouch',                  N'componente', N'ea', @empaque,    N'C-02-R1', 300, 1500),
 (N'LBL-IS60ENO-PI', N'IS60ENO Label Insert (insert Label)',                N'componente', N'ea', @empaque,    N'C-03-R1', 300, 1500),
 (N'10-019-L',       N'Box 10" x 8" x 6"',                                  N'componente', N'ea', @empaque,    N'C-04-R1', 500, 2000),
 (N'LBL-IS60ENO-CI', N'IS60ENO Shipper Box Label (Exterior Labels)',        N'componente', N'ea', @empaque,    N'C-03-R2', 50,  400),
 (N'NC-EES-IFU',     N'Enteral Extension Sets Instructions For Use',        N'componente', N'ea', @empaque,    N'C-05-R1', 50,  400);
GO

/* ---------- DMR IS60ENO Rev. B ---------- */

DECLARE @articulo_terminado INT = (SELECT id FROM dbo.articulo WHERE part_number = N'IS60ENO');

INSERT INTO dbo.dmr (articulo_id, revision, dcn, effective_date, case_pack, auto_calc_case, especificaciones, estado)
VALUES (@articulo_terminado, N'B', N'2425', '2024-10-16', 50, 1, N'N/A', N'aprobado');

DECLARE @dmr INT = SCOPE_IDENTITY();

INSERT INTO dbo.bom_linea (dmr_id, no_linea, articulo_id, cantidad, uom, case_quantity)
SELECT @dmr, v.no_linea, a.id, v.cantidad, v.uom, v.case_quantity
FROM (VALUES
    (1,  N'20-001-4-L',     CAST(1         AS DECIMAL(18,7)), N'ea', CAST(50       AS DECIMAL(18,7))),
    (2,  N'20-003-L',       CAST(1         AS DECIMAL(18,7)), N'ea', CAST(50       AS DECIMAL(18,7))),
    (3,  N'20-004-L',       CAST(1         AS DECIMAL(18,7)), N'ea', CAST(50       AS DECIMAL(18,7))),
    (4,  N'10-010-L',       CAST(1         AS DECIMAL(18,7)), N'ea', CAST(50       AS DECIMAL(18,7))),
    (5,  N'10-014-L',       CAST(0.0000075 AS DECIMAL(18,7)), N'gl', CAST(0.000375 AS DECIMAL(18,7))),
    (6,  N'10-015-L',       CAST(0.0015    AS DECIMAL(18,7)), N'ea', CAST(0.075    AS DECIMAL(18,7))),
    (7,  N'10-016-L',       CAST(1         AS DECIMAL(18,7)), N'ea', CAST(50       AS DECIMAL(18,7))),
    (8,  N'LBL-IS60ENO-PI', CAST(1         AS DECIMAL(18,7)), N'ea', CAST(50       AS DECIMAL(18,7))),
    (9,  N'10-019-L',       CAST(0.02      AS DECIMAL(18,7)), N'ea', CAST(1        AS DECIMAL(18,7))),
    (10, N'LBL-IS60ENO-CI', CAST(0.02      AS DECIMAL(18,7)), N'ea', CAST(1        AS DECIMAL(18,7))),
    (11, N'NC-EES-IFU',     CAST(0.02      AS DECIMAL(18,7)), N'ea', CAST(1        AS DECIMAL(18,7)))
) AS v(no_linea, part_number, cantidad, uom, case_quantity)
JOIN dbo.articulo a ON a.part_number = v.part_number;

/* Reference Documents */
INSERT INTO dbo.documento_referencia (numero, titulo) VALUES
    (N'WI-001',       N'Mfg Work Instructions for Enteral Ext Sets'),
    (N'DWG-IS60ENO',  N'IS60ENO Drawing'),
    (N'SOP-103',      N'Receiving, In-Process and Shipping Inspection'),
    (N'SOP-104',      N'Production Work Orders Processing'),
    (N'SOP-108',      N'Label Control'),
    (N'SOP-106',      N'Control of Non-Conformances');

INSERT INTO dbo.dmr_referencia (dmr_id, documento_id)
SELECT @dmr, id FROM dbo.documento_referencia;

/* Approvals */
INSERT INTO dbo.dmr_aprobacion (dmr_id, tipo, nombre, fecha) VALUES
    (@dmr, N'creado',   N'Luis Padilla',     '2024-10-16'),
    (@dmr, N'revisado', N'Ernesto Ortega',   '2024-10-16'),
    (@dmr, N'aprobado', N'Monica Echeveria', '2024-10-16');
GO

/* ---------- Existencias iniciales como movimientos de entrada ----------
   El stock NO se inserta a mano en dbo.existencia: entra por el kardex
   y el trigger tg_movimiento_aplicar calcula el saldo.                  */

DECLARE @usuario INT = (SELECT id FROM dbo.usuario WHERE username = N'admin.inventario');

INSERT INTO dbo.movimiento_inventario (articulo_id, tipo, cantidad, uom, departamento_id, usuario_id, referencia, motivo)
SELECT a.id, N'entrada', v.cantidad, a.uom, a.departamento_id, @usuario, N'INV-INICIAL', N'Carga inicial de inventario'
FROM (VALUES
    (N'20-001-4-L',     CAST(560   AS DECIMAL(18,7))),
    (N'20-003-L',       CAST(480   AS DECIMAL(18,7))),
    (N'20-004-L',       CAST(480   AS DECIMAL(18,7))),
    (N'10-010-L',       CAST(610   AS DECIMAL(18,7))),
    (N'10-014-L',       CAST(0.9   AS DECIMAL(18,7))),
    (N'10-015-L',       CAST(4     AS DECIMAL(18,7))),
    (N'10-016-L',       CAST(700   AS DECIMAL(18,7))),
    (N'LBL-IS60ENO-PI', CAST(650   AS DECIMAL(18,7))),
    (N'10-019-L',       CAST(1250  AS DECIMAL(18,7))),
    (N'LBL-IS60ENO-CI', CAST(30    AS DECIMAL(18,7))),
    (N'NC-EES-IFU',     CAST(25    AS DECIMAL(18,7)))
) AS v(part_number, cantidad)
JOIN dbo.articulo a ON a.part_number = v.part_number;
GO

/* ---------- Ordenes de produccion de ejemplo ---------- */

DECLARE @dmr INT        = (SELECT id FROM dbo.dmr WHERE dcn = N'2425');
DECLARE @usuario INT    = (SELECT id FROM dbo.usuario WHERE username = N'admin.inventario');
DECLARE @matutino INT   = (SELECT id FROM dbo.turno WHERE nombre = N'Matutino');
DECLARE @vespertino INT = (SELECT id FROM dbo.turno WHERE nombre = N'Vespertino');
DECLARE @produccion INT = (SELECT id FROM dbo.departamento WHERE nombre = N'Produccion');
DECLARE @empaque INT    = (SELECT id FROM dbo.departamento WHERE nombre = N'Empaque y etiquetado');
DECLARE @calidad INT    = (SELECT id FROM dbo.departamento WHERE nombre = N'Calidad');

INSERT INTO dbo.orden_produccion (folio, dmr_id, cantidad, turno_id, departamento_id, fecha_programada, estado, referencia, creado_por) VALUES
    (N'WO-2026-0156', @dmr, 420, @matutino,   @calidad,    '2026-07-25', N'liberada',   N'WI-001', @usuario),
    (N'WO-2026-0157', @dmr, 300, @vespertino, @empaque,    '2026-07-26', N'completa',   N'WI-001', @usuario),
    (N'WO-2026-0158', @dmr, 500, @matutino,   @produccion, '2026-07-27', N'en_proceso', N'WI-001', @usuario);

/* Snapshot del BOM para cada orden */
INSERT INTO dbo.orden_material (orden_id, articulo_id, requerido)
SELECT o.id, bl.articulo_id, bl.cantidad * o.cantidad
FROM dbo.orden_produccion o
JOIN dbo.bom_linea bl ON bl.dmr_id = o.dmr_id;

/* Etapas: WO-0158 va en "Ensamble y bonding" (igual que el tablero actual) */
INSERT INTO dbo.orden_etapa (orden_id, secuencia, nombre, estado)
SELECT o.id, e.secuencia, e.nombre,
       CASE WHEN o.folio <> N'WO-2026-0158' THEN N'completa'
            WHEN e.secuencia = 1 THEN N'completa'
            WHEN e.secuencia = 2 THEN N'en_proceso'
            ELSE N'pendiente' END
FROM dbo.orden_produccion o
CROSS JOIN (VALUES (1, N'Corte y armado'),
                   (2, N'Ensamble y bonding'),
                   (3, N'Empaque y etiquetado'),
                   (4, N'Calidad y liberacion')) AS e(secuencia, nombre);

/* Liberacion de la orden ya liberada */
INSERT INTO dbo.liberacion_calidad (orden_id, resultado, liberado_por, fecha, observaciones)
SELECT id, N'conforme', @usuario, '2026-07-25', N'Inspeccion final conforme (SOP-103)'
FROM dbo.orden_produccion WHERE folio = N'WO-2026-0156';
GO

/* ---------- Verificacion rapida ---------- */
SELECT * FROM dbo.v_kpi_inventario;
SELECT part_number, existencia, stock_minimo, estado, sugerido_reabastecer
FROM dbo.v_estado_inventario ORDER BY estado;
GO
