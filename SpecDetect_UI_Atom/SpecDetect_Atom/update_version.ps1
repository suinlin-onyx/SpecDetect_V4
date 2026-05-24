param(
    [string]$Version
)

$a = $Version.Split('.')
$content = Get-Content -Path 'packaging\version_info.txt' -Raw
$content = $content -replace 'filevers=\(\d+,\s*\d+,\s*\d+,\s*\d+\)', "filevers=($($a[0]), $($a[1]), $($a[2]), 0)"
$content = $content -replace 'prodvers=\(\d+,\s*\d+,\s*\d+,\s*\d+\)', "prodvers=($($a[0]), $($a[1]), $($a[2]), 0)"
$content = $content -replace "'FileVersion', u'[^']+'", "'FileVersion', u'$Version'"
$content = $content -replace "'ProductVersion', u'[^']+'", "'ProductVersion', u'$Version'"
Set-Content -Path 'packaging\version_info.txt' -Value $content
