/* ============================================================
   Concurso_Maquila - Esquema de base de datos (SQL Server 2016+)
   Ejecutar con SSMS, Azure Data Studio o sqlcmd (usa lotes GO).
   NO ejecutar este archivo desde pyodbc: no entiende "GO".
   ============================================================ */

IF DB_ID('ConcursoMaquila') IS NULL
    CREATE DATABASE ConcursoMaquila;
GO

USE ConcursoMaquila;
GO

/* sqlcmd deja QUOTED_IDENTIFIER apagado y los indices filtrados, las tablas
   temporales y las vistas lo exigen encendido. Sin estas dos lineas el script
   truena con el error 1934. */
SET QUOTED_IDENTIFIER ON;
SET ANSI_NULLS ON;
GO

/* ------------------------------------------------------------
   1. CATALOGOS BASE
   ------------------------------------------------------------ */

CREATE TABLE dbo.departamento (
    id      INT IDENTITY(1,1) PRIMARY KEY,
    nombre  NVARCHAR(60) NOT NULL UNIQUE,   -- Almacen, Produccion, Calidad, Empaque
    activo  BIT NOT NULL DEFAULT 1
);
GO

CREATE TABLE dbo.turno (
    id          INT IDENTITY(1,1) PRIMARY KEY,
    nombre      NVARCHAR(30) NOT NULL UNIQUE,  -- Matutino, Vespertino, Nocturno
    hora_inicio TIME NULL,
    hora_fin    TIME NULL
);
GO

CREATE TABLE dbo.unidad_medida (
    codigo      NVARCHAR(10) PRIMARY KEY,      -- ea, gl, kg, m, l, pza, caja
    descripcion NVARCHAR(60) NOT NULL
);
GO

CREATE TABLE dbo.proveedor (
    id       INT IDENTITY(1,1) PRIMARY KEY,
    nombre   NVARCHAR(120) NOT NULL,
    contacto NVARCHAR(120) NULL,
    telefono NVARCHAR(30)  NULL,
    email    NVARCHAR(120) NULL,
    activo   BIT NOT NULL DEFAULT 1
);
GO

CREATE TABLE dbo.configuracion (
    clave       NVARCHAR(60) PRIMARY KEY,
    valor       NVARCHAR(200) NOT NULL,
    descripcion NVARCHAR(200) NULL
);
GO

/* ------------------------------------------------------------
   2. USUARIOS
   ------------------------------------------------------------ */

CREATE TABLE dbo.usuario (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    username        NVARCHAR(50)  NOT NULL UNIQUE,
    password_hash   NVARCHAR(255) NOT NULL,   -- werkzeug.security, nunca texto plano
    nombre_completo NVARCHAR(120) NOT NULL,
    rol             NVARCHAR(20)  NOT NULL
                    CONSTRAINT ck_usuario_rol CHECK (rol IN ('administrador','personal')),
    departamento_id INT NULL REFERENCES dbo.departamento(id),
    turno_id        INT NULL REFERENCES dbo.turno(id),
    activo          BIT NOT NULL DEFAULT 1,
    ultimo_acceso   DATETIME2(0) NULL,
    creado_en       DATETIME2(0) NOT NULL DEFAULT SYSDATETIME()
);
GO

/* ------------------------------------------------------------
   3. ARTICULOS (productos terminados Y componentes en una tabla)
      Tabla temporal: SQL Server guarda el historial de cambios solo.
   ------------------------------------------------------------ */

CREATE TABLE dbo.articulo (
    id              INT IDENTITY(1,1) PRIMARY KEY,
    part_number     NVARCHAR(50)  NOT NULL UNIQUE,   -- IS60ENO, 20-001-4-L, LBL-...
    descripcion     NVARCHAR(200) NOT NULL,
    tipo            NVARCHAR(20)  NOT NULL
                    CONSTRAINT ck_articulo_tipo
                    CHECK (tipo IN ('terminado','componente','subensamble')),
    uom             NVARCHAR(10)  NOT NULL REFERENCES dbo.unidad_medida(codigo),
    departamento_id INT NULL REFERENCES dbo.departamento(id),
    proveedor_id    INT NULL REFERENCES dbo.proveedor(id),
    ubicacion       NVARCHAR(30)  NULL,              -- A-03-R2
    stock_minimo    DECIMAL(18,7) NOT NULL DEFAULT 0,
    stock_maximo    DECIMAL(18,7) NULL,
    activo          BIT NOT NULL DEFAULT 1,
    -- versionado automatico del sistema (historial de cambios de minimos, ubicacion, etc.)
    valido_desde DATETIME2 GENERATED ALWAYS AS ROW START HIDDEN NOT NULL,
    valido_hasta DATETIME2 GENERATED ALWAYS AS ROW END   HIDDEN NOT NULL,
    PERIOD FOR SYSTEM_TIME (valido_desde, valido_hasta)
)
WITH (SYSTEM_VERSIONING = ON (HISTORY_TABLE = dbo.articulo_historial));
GO

CREATE INDEX ix_articulo_departamento ON dbo.articulo (departamento_id) WHERE activo = 1;
GO

/* ------------------------------------------------------------
   4. BOM / DMR  (documento versionado: nunca se edita, se revisa)
   ------------------------------------------------------------ */

CREATE TABLE dbo.dmr (
    id             INT IDENTITY(1,1) PRIMARY KEY,
    articulo_id    INT NOT NULL REFERENCES dbo.articulo(id),
    revision       NVARCHAR(10) NOT NULL,            -- B
    dcn            NVARCHAR(20) NULL,                -- 2425
    effective_date DATE NOT NULL,
    case_pack      DECIMAL(18,7) NOT NULL DEFAULT 1, -- 50
    auto_calc_case BIT NOT NULL DEFAULT 1,           -- calcular Case Quantity solo
    especificaciones NVARCHAR(MAX) NOT NULL DEFAULT N'N/A',  -- Technical Specifications
    estado         NVARCHAR(20) NOT NULL DEFAULT 'borrador'
                   CONSTRAINT ck_dmr_estado
                   CHECK (estado IN ('borrador','en_revision','aprobado','obsoleto')),
    CONSTRAINT ux_dmr_articulo_revision UNIQUE (articulo_id, revision)
);
GO

-- Indice filtrado: solo puede haber UNA revision aprobada por articulo
CREATE UNIQUE INDEX ux_dmr_vigente
    ON dbo.dmr (articulo_id)
    WHERE estado = 'aprobado';
GO

CREATE TABLE dbo.bom_linea (
    id            INT IDENTITY(1,1) PRIMARY KEY,
    dmr_id        INT NOT NULL REFERENCES dbo.dmr(id) ON DELETE CASCADE,
    no_linea      INT NOT NULL,
    articulo_id   INT NOT NULL REFERENCES dbo.articulo(id),   -- el componente
    cantidad      DECIMAL(18,7) NOT NULL
                  CONSTRAINT ck_bom_cantidad CHECK (cantidad > 0),
    uom           NVARCHAR(10) NOT NULL REFERENCES dbo.unidad_medida(codigo),
    case_quantity DECIMAL(18,7) NULL,
    CONSTRAINT ux_bom_dmr_articulo UNIQUE (dmr_id, articulo_id)
);
GO

CREATE TABLE dbo.documento_referencia (
    id     INT IDENTITY(1,1) PRIMARY KEY,
    numero NVARCHAR(30)  NOT NULL UNIQUE,   -- WI-001, SOP-103
    titulo NVARCHAR(200) NOT NULL
);
GO

CREATE TABLE dbo.dmr_referencia (
    dmr_id       INT NOT NULL REFERENCES dbo.dmr(id) ON DELETE CASCADE,
    documento_id INT NOT NULL REFERENCES dbo.documento_referencia(id),
    CONSTRAINT pk_dmr_referencia PRIMARY KEY (dmr_id, documento_id)
);
GO

CREATE TABLE dbo.dmr_aprobacion (
    id         INT IDENTITY(1,1) PRIMARY KEY,
    dmr_id     INT NOT NULL REFERENCES dbo.dmr(id) ON DELETE CASCADE,
    tipo       NVARCHAR(20) NOT NULL
               CONSTRAINT ck_aprobacion_tipo
               CHECK (tipo IN ('creado','revisado','aprobado')),
    usuario_id INT NULL REFERENCES dbo.usuario(id),
    nombre     NVARCHAR(120) NOT NULL DEFAULT N'',
    fecha      DATE NULL,                 -- puede quedar en blanco hasta que se firme
    CONSTRAINT ux_dmr_aprobacion UNIQUE (dmr_id, tipo)
);
GO

/* ------------------------------------------------------------
   5. ORDENES DE PRODUCCION
   ------------------------------------------------------------ */

CREATE SEQUENCE dbo.seq_orden_produccion AS INT START WITH 159 INCREMENT BY 1;
GO

CREATE TABLE dbo.orden_produccion (
    id               INT IDENTITY(1,1) PRIMARY KEY,
    folio            NVARCHAR(20) NOT NULL UNIQUE
                     CONSTRAINT df_orden_folio DEFAULT (
                        'WO-' + CONVERT(NVARCHAR(4), YEAR(GETDATE())) + '-' +
                        RIGHT('0000' + CONVERT(NVARCHAR(10), NEXT VALUE FOR dbo.seq_orden_produccion), 4)
                     ),
    dmr_id           INT NOT NULL REFERENCES dbo.dmr(id),   -- revision congelada
    cantidad         DECIMAL(18,4) NOT NULL
                     CONSTRAINT ck_orden_cantidad CHECK (cantidad > 0),
    turno_id         INT NULL REFERENCES dbo.turno(id),
    departamento_id  INT NULL REFERENCES dbo.departamento(id),
    fecha_programada DATE NULL,
    fecha_inicio     DATETIME2(0) NULL,
    fecha_fin        DATETIME2(0) NULL,
    estado           NVARCHAR(20) NOT NULL DEFAULT 'planeada'
                     CONSTRAINT ck_orden_estado
                     CHECK (estado IN ('planeada','en_proceso','completa','liberada','cancelada')),
    referencia       NVARCHAR(60) NULL,                     -- WI-001
    creado_por       INT NULL REFERENCES dbo.usuario(id),
    creado_en        DATETIME2(0) NOT NULL DEFAULT SYSDATETIME()
);
GO

CREATE INDEX ix_orden_estado ON dbo.orden_produccion (estado, fecha_programada DESC);
GO

-- Snapshot del BOM al momento de crear la orden (no se recalcula nunca)
CREATE TABLE dbo.orden_material (
    id          INT IDENTITY(1,1) PRIMARY KEY,
    orden_id    INT NOT NULL REFERENCES dbo.orden_produccion(id) ON DELETE CASCADE,
    articulo_id INT NOT NULL REFERENCES dbo.articulo(id),
    requerido   DECIMAL(18,7) NOT NULL,   -- cantidad_bom * orden.cantidad
    surtido     DECIMAL(18,7) NOT NULL DEFAULT 0,
    consumido   DECIMAL(18,7) NOT NULL DEFAULT 0,
    merma       DECIMAL(18,7) NOT NULL DEFAULT 0,
    CONSTRAINT ux_orden_material UNIQUE (orden_id, articulo_id)
);
GO

CREATE TABLE dbo.orden_etapa (
    id           INT IDENTITY(1,1) PRIMARY KEY,
    orden_id     INT NOT NULL REFERENCES dbo.orden_produccion(id) ON DELETE CASCADE,
    secuencia    INT NOT NULL,
    nombre       NVARCHAR(60) NOT NULL,   -- corte, ensamble, empaque, calidad
    estado       NVARCHAR(20) NOT NULL DEFAULT 'pendiente'
                 CONSTRAINT ck_etapa_estado
                 CHECK (estado IN ('pendiente','en_proceso','completa')),
    iniciada_en  DATETIME2(0) NULL,
    terminada_en DATETIME2(0) NULL,
    usuario_id   INT NULL REFERENCES dbo.usuario(id),
    CONSTRAINT ux_orden_etapa UNIQUE (orden_id, secuencia)
);
GO

/* ------------------------------------------------------------
   6. INVENTARIO (kardex = fuente de verdad, existencia = saldo)
   ------------------------------------------------------------ */

CREATE TABLE dbo.movimiento_inventario (
    id              BIGINT IDENTITY(1,1) PRIMARY KEY,
    articulo_id     INT NOT NULL REFERENCES dbo.articulo(id),
    tipo            NVARCHAR(10) NOT NULL
                    CONSTRAINT ck_mov_tipo CHECK (tipo IN ('entrada','salida','ajuste')),
    cantidad        DECIMAL(18,7) NOT NULL
                    CONSTRAINT ck_mov_cantidad CHECK (cantidad <> 0),
    uom             NVARCHAR(10) NOT NULL REFERENCES dbo.unidad_medida(codigo),
    departamento_id INT NULL REFERENCES dbo.departamento(id),
    usuario_id      INT NOT NULL REFERENCES dbo.usuario(id),
    orden_id        INT NULL REFERENCES dbo.orden_produccion(id),
    referencia      NVARCHAR(60)  NULL,   -- WO-2026-0158 / DCN 2425
    lote            NVARCHAR(40)  NULL,   -- trazabilidad / recall
    motivo          NVARCHAR(200) NULL,
    fecha           DATETIME2(0) NOT NULL DEFAULT SYSDATETIME()
);
GO

CREATE INDEX ix_mov_articulo_fecha ON dbo.movimiento_inventario (articulo_id, fecha DESC);
CREATE INDEX ix_mov_fecha_tipo     ON dbo.movimiento_inventario (fecha, tipo);
GO

CREATE TABLE dbo.existencia (
    articulo_id INT PRIMARY KEY REFERENCES dbo.articulo(id),
    cantidad    DECIMAL(18,7) NOT NULL DEFAULT 0,
    actualizado DATETIME2(0) NOT NULL DEFAULT SYSDATETIME()
);
GO

/* Trigger SET-BASED (en SQL Server "inserted" trae TODAS las filas del INSERT,
   no una sola: nunca uses SELECT @var = ... aqui). */
CREATE TRIGGER dbo.tg_movimiento_aplicar
ON dbo.movimiento_inventario
AFTER INSERT
AS
BEGIN
    SET NOCOUNT ON;

    WITH deltas AS (
        SELECT articulo_id,
               SUM(CASE tipo
                       WHEN 'entrada' THEN cantidad
                       WHEN 'salida'  THEN -cantidad
                       ELSE cantidad          -- ajuste: el signo lo pone el usuario
                   END) AS delta
        FROM inserted
        GROUP BY articulo_id
    )
    MERGE dbo.existencia WITH (HOLDLOCK) AS destino
    USING deltas AS origen
        ON destino.articulo_id = origen.articulo_id
    WHEN MATCHED THEN
        UPDATE SET cantidad = destino.cantidad + origen.delta,
                   actualizado = SYSDATETIME()
    WHEN NOT MATCHED THEN
        INSERT (articulo_id, cantidad) VALUES (origen.articulo_id, origen.delta);
END;
GO

/* ------------------------------------------------------------
   7. CALIDAD
   ------------------------------------------------------------ */

CREATE TABLE dbo.liberacion_calidad (
    id            INT IDENTITY(1,1) PRIMARY KEY,
    orden_id      INT NOT NULL REFERENCES dbo.orden_produccion(id),
    resultado     NVARCHAR(20) NOT NULL
                  CONSTRAINT ck_liberacion_resultado
                  CHECK (resultado IN ('conforme','no_conforme')),
    liberado_por  INT NULL REFERENCES dbo.usuario(id),
    fecha         DATE NOT NULL,
    observaciones NVARCHAR(MAX) NULL
);
GO

CREATE TABLE dbo.no_conformidad (          -- SOP-106
    id          INT IDENTITY(1,1) PRIMARY KEY,
    folio       NVARCHAR(20) NOT NULL UNIQUE,
    orden_id    INT NULL REFERENCES dbo.orden_produccion(id),
    articulo_id INT NULL REFERENCES dbo.articulo(id),
    descripcion NVARCHAR(MAX) NOT NULL,
    disposicion NVARCHAR(30) NULL
                CONSTRAINT ck_nc_disposicion
                CHECK (disposicion IN ('retrabajo','scrap','uso_como_esta')),
    estado      NVARCHAR(20) NOT NULL DEFAULT 'abierta'
                CONSTRAINT ck_nc_estado CHECK (estado IN ('abierta','cerrada')),
    abierta_por INT NULL REFERENCES dbo.usuario(id),
    abierta_en  DATETIME2(0) NOT NULL DEFAULT SYSDATETIME(),
    cerrada_en  DATETIME2(0) NULL
);
GO

/* ------------------------------------------------------------
   8. AUDITORIA (para lo que no cubre el versionado del sistema)
   ------------------------------------------------------------ */

CREATE TABLE dbo.auditoria (
    id            BIGINT IDENTITY(1,1) PRIMARY KEY,
    tabla         NVARCHAR(60) NOT NULL,
    registro_id   NVARCHAR(50) NOT NULL,
    accion        NVARCHAR(10) NOT NULL
                  CONSTRAINT ck_auditoria_accion
                  CHECK (accion IN ('INSERT','UPDATE','DELETE')),
    usuario_id    INT NULL REFERENCES dbo.usuario(id),
    datos_antes   NVARCHAR(MAX) NULL CONSTRAINT ck_auditoria_antes   CHECK (datos_antes   IS NULL OR ISJSON(datos_antes)   = 1),
    datos_despues NVARCHAR(MAX) NULL CONSTRAINT ck_auditoria_despues CHECK (datos_despues IS NULL OR ISJSON(datos_despues) = 1),
    fecha         DATETIME2(0) NOT NULL DEFAULT SYSDATETIME()
);
GO

/* ------------------------------------------------------------
   9. VISTAS (una sola definicion del "estado" para las 3 pantallas)
   ------------------------------------------------------------ */

CREATE VIEW dbo.v_estado_inventario AS
SELECT  a.id                AS articulo_id,
        a.part_number,
        a.descripcion,
        a.uom,
        d.nombre            AS departamento,
        a.ubicacion,
        ISNULL(e.cantidad, 0) AS existencia,
        a.stock_minimo,
        a.stock_maximo,
        cfg.factor,
        a.stock_minimo * cfg.factor AS stock_objetivo,
        CASE
            WHEN ISNULL(e.cantidad, 0) <= 0                                          THEN 'Agotado'
            WHEN a.stock_minimo > 0 AND e.cantidad <  a.stock_minimo                 THEN 'Bajo'
            WHEN a.stock_minimo > 0 AND e.cantidad <  a.stock_minimo * cfg.factor     THEN 'Medio'
            ELSE 'Alto'
        END AS estado,
        CASE
            WHEN a.stock_minimo * cfg.factor - ISNULL(e.cantidad, 0) > 0
            THEN a.stock_minimo * cfg.factor - ISNULL(e.cantidad, 0)
            ELSE 0
        END AS sugerido_reabastecer
FROM        dbo.articulo a
LEFT JOIN   dbo.existencia   e ON e.articulo_id = a.id
LEFT JOIN   dbo.departamento d ON d.id = a.departamento_id
CROSS JOIN (SELECT TRY_CAST(valor AS DECIMAL(18,4)) AS factor
            FROM dbo.configuracion
            WHERE clave = 'factor_stock_objetivo') cfg
WHERE a.activo = 1 AND a.tipo <> 'terminado';
GO

CREATE VIEW dbo.v_kpi_inventario AS
SELECT
    SUM(CASE WHEN estado = 'Agotado' THEN 1 ELSE 0 END) AS agotado,
    SUM(CASE WHEN estado = 'Bajo'    THEN 1 ELSE 0 END) AS bajo,
    SUM(CASE WHEN estado = 'Medio'   THEN 1 ELSE 0 END) AS medio,
    SUM(CASE WHEN estado = 'Alto'    THEN 1 ELSE 0 END) AS alto,
    COUNT(*)                                            AS total_materiales,
    SUM(existencia)                                     AS stock_total
FROM dbo.v_estado_inventario;
GO

CREATE VIEW dbo.v_consumo_diario AS
SELECT  CAST(m.fecha AS DATE) AS dia,
        m.tipo,
        SUM(m.cantidad)       AS total,
        COUNT(*)              AS movimientos
FROM dbo.movimiento_inventario m
GROUP BY CAST(m.fecha AS DATE), m.tipo;
GO

-- Explosion de materiales de una orden vs existencia real
CREATE VIEW dbo.v_consumo_orden AS
SELECT  o.id       AS orden_id,
        o.folio,
        a.part_number,
        a.descripcion,
        om.requerido,
        om.consumido,
        ISNULL(e.cantidad, 0) AS stock_disponible,
        CASE WHEN ISNULL(e.cantidad, 0) >= om.requerido
             THEN 'Suficiente' ELSE 'Insuficiente' END AS estado_material
FROM        dbo.orden_material   om
JOIN        dbo.orden_produccion o ON o.id = om.orden_id
JOIN        dbo.articulo         a ON a.id = om.articulo_id
LEFT JOIN   dbo.existencia       e ON e.articulo_id = om.articulo_id;
GO

/* ------------------------------------------------------------
   10. PROCEDIMIENTO: crear orden + explotar BOM en una transaccion
   ------------------------------------------------------------ */

CREATE PROCEDURE dbo.sp_crear_orden_produccion
    @dmr_id           INT,
    @cantidad         DECIMAL(18,4),
    @turno_id         INT = NULL,
    @departamento_id  INT = NULL,
    @fecha_programada DATE = NULL,
    @referencia       NVARCHAR(60) = NULL,
    @usuario_id       INT = NULL,
    @orden_id         INT = NULL OUTPUT
AS
BEGIN
    SET NOCOUNT ON;
    SET XACT_ABORT ON;

    BEGIN TRANSACTION;

        INSERT INTO dbo.orden_produccion
            (dmr_id, cantidad, turno_id, departamento_id, fecha_programada, referencia, creado_por, estado)
        VALUES
            (@dmr_id, @cantidad, @turno_id, @departamento_id, @fecha_programada, @referencia, @usuario_id, 'planeada');

        SET @orden_id = SCOPE_IDENTITY();

        -- snapshot del BOM: se congela lo que dice la revision HOY
        INSERT INTO dbo.orden_material (orden_id, articulo_id, requerido)
        SELECT @orden_id, bl.articulo_id, bl.cantidad * @cantidad
        FROM dbo.bom_linea bl
        WHERE bl.dmr_id = @dmr_id;

        -- etapas estandar del proceso
        INSERT INTO dbo.orden_etapa (orden_id, secuencia, nombre, estado)
        VALUES (@orden_id, 1, 'Corte y armado',       'pendiente'),
               (@orden_id, 2, 'Ensamble y bonding',   'pendiente'),
               (@orden_id, 3, 'Empaque y etiquetado', 'pendiente'),
               (@orden_id, 4, 'Calidad y liberacion', 'pendiente');

    COMMIT TRANSACTION;
END;
GO
