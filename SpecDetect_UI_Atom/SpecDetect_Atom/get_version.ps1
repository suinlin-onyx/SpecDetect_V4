$versionPy = Join-Path $PSScriptRoot 'src\version.py'
if (Test-Path $versionPy) {
    $content = Get-Content -Path $versionPy -Raw
    if ($content -match 'ATOM_VERSION\s*=\s*"([^"]+)"') {
        $matches[1]
    } else {
        '1.1.4'
    }
} else {
    '1.1.4'
}
