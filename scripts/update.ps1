param(
    [ValidateSet('local', 'source', 'release')]
    [string] $Mode = 'local'
)

$ErrorActionPreference = 'Stop'
Set-Location (Resolve-Path (Join-Path $PSScriptRoot '..'))

function Invoke-Checked {
    param([string] $Program, [string[]] $Arguments)
    & $Program @Arguments
    if ($LASTEXITCODE -ne 0) {
        throw "$Program falló con código $LASTEXITCODE"
    }
}

if (-not (Test-Path '.env')) {
    throw 'Falta .env. Cópialo desde .env.example y configura tus secretos.'
}
if ($Mode -eq 'source') {
    & git rev-parse --is-inside-work-tree *> $null
    if ($LASTEXITCODE -ne 0) {
        throw 'El modo source requiere un clon Git. Usa local o release.'
    }
}

$base = @('compose', '-f', 'compose.yaml')
$published = @('compose', '-f', 'compose.yaml', '-f', 'compose.release.yaml')
if ($Mode -eq 'release') {
    Invoke-Checked 'docker' ($published + @('config', '--quiet'))
} else {
    Invoke-Checked 'docker' ($base + @('config', '--quiet'))
}

$backupDir = Join-Path (Get-Location) 'backups'
New-Item -ItemType Directory -Force -Path $backupDir | Out-Null
$stamp = (Get-Date).ToUniversalTime().ToString('yyyyMMddTHHmmssZ') + "-$PID"
$containerBackup = "/tmp/spiderfinance-$stamp.dump"
$backup = Join-Path $backupDir "spiderfinance-$stamp.dump"

try {
    Write-Host 'Creando copia de PostgreSQL...'
    Invoke-Checked 'docker' ($base + @('exec', '-T', 'postgres', 'sh', '-c', 'pg_dump -Fc -U "$POSTGRES_USER" "$POSTGRES_DB" -f "$1"', 'sh', $containerBackup))
    Invoke-Checked 'docker' ($base + @('cp', "postgres:${containerBackup}", $backup))
    Write-Host "Copia guardada en $backup"

    switch ($Mode) {
        'local' {
            Invoke-Checked 'docker' ($base + @('up', '-d', '--build', '--wait', '--wait-timeout', '180'))
        }
        'source' {
            Invoke-Checked 'git' @('pull', '--ff-only')
            Invoke-Checked 'docker' ($base + @('up', '-d', '--build', '--wait', '--wait-timeout', '180'))
        }
        'release' {
            Invoke-Checked 'docker' ($published + @('pull', 'postgres', 'backend', 'frontend', 'admin'))
            Invoke-Checked 'docker' ($published + @('up', '-d', '--no-build', '--wait', '--wait-timeout', '180'))
        }
    }
    Write-Host 'Actualización terminada. El volumen de PostgreSQL y .env se han conservado.'
} finally {
    & docker @base exec -T postgres rm -f $containerBackup *> $null
}
