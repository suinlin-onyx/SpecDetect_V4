$line = Select-String -Path 'src\atom\service.py' -Pattern '^__version__' | Select-Object -First 1
if ($line) {
    $line.Line.Split('=')[1].Trim().Replace('"', '')
} else {
    '1.1.4'
}
