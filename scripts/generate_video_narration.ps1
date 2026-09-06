param(
    [string]$OutputDir = "output\video\narration"
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Speech
New-Item -ItemType Directory -Path $OutputDir -Force | Out-Null

$narrationPath = Join-Path $PSScriptRoot "video_narration_zh.json"
$segments = Get-Content -LiteralPath $narrationPath -Raw -Encoding UTF8 | ConvertFrom-Json

$synth = New-Object System.Speech.Synthesis.SpeechSynthesizer
$synth.SelectVoice("Microsoft Huihui Desktop")
$synth.Rate = 1
$synth.Volume = 100

foreach ($entry in $segments.PSObject.Properties) {
    $target = Join-Path $OutputDir ($entry.Name + ".wav")
    $synth.SetOutputToWaveFile($target)
    $synth.Speak($entry.Value)
    $synth.SetOutputToNull()
    Write-Output "Generated $target"
}

$synth.Dispose()
