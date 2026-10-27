-- Base de la aplicación y login propio (no se usa sa desde la API ni el worker).
-- Variables de sqlcmd: DB_NAME, DB_USER, DB_PASSWORD.
SET NOCOUNT ON;

IF DB_ID(N'$(DB_NAME)') IS NULL
BEGIN
    CREATE DATABASE [$(DB_NAME)];
    PRINT 'Base creada: $(DB_NAME)';
END;
GO

-- Snapshot isolation para lecturas de dashboards sin bloquear las escrituras del plan.
IF NOT EXISTS (SELECT 1 FROM sys.databases WHERE name = N'$(DB_NAME)' AND is_read_committed_snapshot_on = 1)
    ALTER DATABASE [$(DB_NAME)] SET READ_COMMITTED_SNAPSHOT ON WITH ROLLBACK IMMEDIATE;
GO

IF NOT EXISTS (SELECT 1 FROM sys.server_principals WHERE name = N'$(DB_USER)')
BEGIN
    CREATE LOGIN [$(DB_USER)] WITH PASSWORD = N'$(DB_PASSWORD)', CHECK_POLICY = ON, DEFAULT_DATABASE = [$(DB_NAME)];
    PRINT 'Login creado: $(DB_USER)';
END
ELSE
    -- Mantiene la contraseña sincronizada con .env.
    ALTER LOGIN [$(DB_USER)] WITH PASSWORD = N'$(DB_PASSWORD)';
GO

USE [$(DB_NAME)];
GO

IF NOT EXISTS (SELECT 1 FROM sys.database_principals WHERE name = N'$(DB_USER)')
    CREATE USER [$(DB_USER)] FOR LOGIN [$(DB_USER)];
GO

-- En desarrollo el usuario de aplicación también ejecuta las migraciones de Alembic.
-- En producción se separan: un usuario de migración (db_owner) y uno de aplicación con permisos mínimos.
IF IS_ROLEMEMBER(N'db_owner', N'$(DB_USER)') = 0
    ALTER ROLE db_owner ADD MEMBER [$(DB_USER)];
GO
