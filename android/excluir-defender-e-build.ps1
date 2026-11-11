# =============================================================================
# Excluir pasta do projeto do Windows Defender e em seguida buildar o APK.
# EXECUTE COMO ADMINISTRADOR: botao direito em PowerShell -> "Executar como administrador"
#   cd D:\dev\caracore-pdv\android-sms-enviar
#   .\excluir-defender-e-build.ps1
# =============================================================================

$ErrorActionPreference = "Stop"
$dir = (Get-Location).Path

function Add-Exclusion {
    param([string]$Path)
    $null = Add-MpPreference -ExclusionPath $Path -ErrorAction SilentlyContinue
    if (-not $?) {
        $msg = if ($Error[0]) { $Error[0].ToString() } else { "Erro ao adicionar exclusao" }
        if ($msg -match '0x800106ba') {
            Write-Host "      Aviso (0x800106ba): Defender gerido por Politica de Grupo ou por outra aplicacao."
            Write-Host "      Adicione a exclusao manualmente: Configuracoes > Privacidade e seguranca >"
            Write-Host "      Seguranca do Windows > Protecao contra virus e ameacas > Gerir definicoes > Exclusoes."
        } else {
            Write-Host "      Aviso: $msg"
        }
        Write-Host "      A continuar o build na mesma (pode ocorrer AccessDenied nos .dex)."
    } else {
        Write-Host "      OK."
    }
}

Write-Host "[1/2] Exclusao do Windows Defender: pasta do projeto (build fica em $dir\build)"
Add-Exclusion -Path $dir

Write-Host ""
Write-Host "[2/2] Executando build.bat clean..."
Push-Location $dir
try {
    & .\build.bat clean
    exit $LASTEXITCODE
} finally {
    Pop-Location
}
