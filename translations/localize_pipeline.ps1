$addonDir = '../CM3D2 Converter'
$localeDir = './locale'
$potFile = "$localeDir/messages.pot"
$pyOutputPath = "$addonDir/translations/locales.py"

# `--ai-dry-run` が指定されたらAI関連ステップをdry-run実行する
$aiDryRunArgs = @()
if ($args -contains '--ai-dry-run') {
    $aiDryRunArgs += '--dry-run'
    Write-Host "[Mode] Dry run enabled for ai-prepare / ai-translate" -ForegroundColor Magenta
}

function Invoke-PythonStep {
    param(
        [string[]]$PyArgs,
        [string]$FailureLabel
    )

    $commandText = "python " + ($PyArgs -join " ")
    & python @PyArgs
    if ($LASTEXITCODE -ne 0) {
        Write-Host "Critical Error: $FailureLabel failed (exit code: $LASTEXITCODE)." -ForegroundColor Red
        Write-Host "  Command: $commandText" -ForegroundColor DarkGray
        exit 1
    }
}

Write-Host "==================================================" -ForegroundColor Cyan
Write-Host " Starting Full Localization Pipeline" -ForegroundColor Cyan
Write-Host "==================================================" -ForegroundColor Cyan

Write-Host "[Step 1/5] Extracting latest keys from source code..." -ForegroundColor Yellow
if (Test-Path $potFile) { Remove-Item $potFile }
$PyArgs = @('-m', 'translator', 'extract-pot', '-d', $addonDir, '-o', $potFile)
Invoke-PythonStep -PyArgs $PyArgs -FailureLabel "extract-pot"
if (-not (Test-Path $potFile)) {
    Write-Host "Critical Error: Failed to generate POT file at $potFile. Pipeline aborted." -ForegroundColor Red
    exit
}
Write-Host "--> Successfully generated: $potFile" -ForegroundColor Green

Write-Host "[Step 2/5] Merging new keys into existing PO files..." -ForegroundColor Yellow
$poFiles = Get-ChildItem -Path $localeDir -Filter *.po -File
if ($poFiles.Count -eq 0) {
    Write-Warning "No existing .po files found in $localeDir. Please generate or initialize them."
    exit
}
foreach ($po in $poFiles) {
    Write-Host "  -> Merging into $($po.Name)..."
    $PyArgs = @('-m', 'translator', 'merge-po', '-s', $potFile, '-t', $po.FullName)
    Invoke-PythonStep -PyArgs $PyArgs -FailureLabel "merge-po ($($po.Name))"
}
Write-Host "--> All PO files successfully synchronized with the latest template." -ForegroundColor Green

Write-Host "[Step 3/5] Creating Gemini Remote Context Cache..." -ForegroundColor Yellow
$PyArgs = @('-m', 'translator', 'ai-prepare', '-d', $addonDir) + $aiDryRunArgs
Invoke-PythonStep -PyArgs $PyArgs -FailureLabel "ai-prepare"
Write-Host "--> Remote Cache acquired." -ForegroundColor Green

Write-Host "[Step 4/5] Executing AI Translations via Shared Cache..." -ForegroundColor Yellow
foreach ($po in $poFiles) {
    Write-Host "`----------------------------------------" -ForegroundColor Yellow
    Write-Host " Translating Target: $($po.Name)" -ForegroundColor Yellow
    Write-Host "----------------------------------------" -ForegroundColor Yellow
    $PyArgs = @('-m', 'translator', 'ai-translate', '-p', $po.FullName) + $aiDryRunArgs
    Invoke-PythonStep -PyArgs $PyArgs -FailureLabel "ai-translate ($($po.Name))"
}
Write-Host "--> All translations and PO updates completed!" -ForegroundColor Green

Write-Host "[Step 5/5] Compiling updated PO files to runtime scripts..." -ForegroundColor Yellow
$PyArgs = @('-m', 'translator', 'compile-dict', '-l', $localeDir, '-o', $pyOutputPath)
Invoke-PythonStep -PyArgs $PyArgs -FailureLabel "compile-dict"
Write-Host "--> Successfully compiled locales to: $pyOutputPath" -ForegroundColor Green

Write-Host "===================================================" -ForegroundColor Green
Write-Host " PIPELINE SUCCESS: All language files are compiled!" -ForegroundColor Green
Write-Host "===================================================" -ForegroundColor Green
