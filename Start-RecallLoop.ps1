param([switch]$AskForApiKey, [switch]$NoEmbeddings, [string]$DataDirectory)
$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if ($AskForApiKey) {
    $recallSecureKey = Read-Host 'OpenAI API key (only stored in this process)' -AsSecureString
    $env:OPENAI_API_KEY = [Net.NetworkCredential]::new('', $recallSecureKey).Password
}
if ($DataDirectory) {
    if ([IO.Path]::IsPathRooted($DataDirectory)) { $env:RECALL_DATA_DIR = [IO.Path]::GetFullPath($DataDirectory) }
    else { $env:RECALL_DATA_DIR = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot $DataDirectory)) }
}
elseif (-not $env:RECALL_DATA_DIR) { $env:RECALL_DATA_DIR = Join-Path $PSScriptRoot 'data' }
$recallArgs = @('-m','recall_loop.cli','serve')
if ($NoEmbeddings) { $recallArgs += '--no-embeddings' }
$recallRuntime = Join-Path $PSScriptRoot '.venv311\Scripts\python.exe'
if (Test-Path -LiteralPath $recallRuntime) {
    & $recallRuntime @recallArgs
} elseif (Get-Command uv -ErrorAction SilentlyContinue) {
    $recallUvArgs = @('run','--python','3.11','--frozen','recall-loop','serve')
    if ($NoEmbeddings) { $recallUvArgs += '--no-embeddings' }
    & uv @recallUvArgs
} else {
    throw 'Install uv or create a Python 3.11 environment using the README instructions.'
}
