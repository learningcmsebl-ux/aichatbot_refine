# Fix LightRAG_New configuration to match working LightRAG_30092025
# Add missing environment variables that prevent dimension mismatch

$separator = "=" * 70
Write-Host $separator
Write-Host "Fix LightRAG_New Configuration"
Write-Host $separator
Write-Host ""

# Get OpenAI API key from .env file
$envFile = "bank_chatbot\.env"
$openaiKey = $null

if (Test-Path $envFile) {
    $envContent = Get-Content $envFile
    $keyLine = $envContent | Where-Object { $_ -match "^OPENAI_API_KEY=" }
    if ($keyLine) {
        $openaiKey = $keyLine -replace "^OPENAI_API_KEY=", "" | ForEach-Object { $_.Trim() }
    }
}

if (-not $openaiKey) {
    Write-Host "Please provide your OpenAI API key:" -ForegroundColor Yellow
    $openaiKey = Read-Host "Enter OpenAI API Key"
}

if (-not $openaiKey) {
    Write-Host "ERROR: OpenAI API key is required. Exiting." -ForegroundColor Red
    exit 1
}

$containerName = "LightRAG_New"

Write-Host "Stopping container..."
docker stop $containerName | Out-Null
Write-Host "Container stopped" -ForegroundColor Green

Write-Host ""
Write-Host "Removing old container..."
docker rm $containerName | Out-Null
Write-Host "Container removed" -ForegroundColor Green

Write-Host ""
Write-Host "Creating new container with complete OpenAI configuration..."
Write-Host ""

# Create container with ALL required settings (matching LightRAG_30092025)
# Optimized settings: SUMMARY_CONTEXT_SIZE=6000, CHUNK_SIZE=800, CHUNK_OVERLAP=100
docker run -d `
  --name LightRAG_New `
  -p 9262:9621 `
  -e LIGHTRAG_API_KEY=MyCustomLightRagKey456 `
  -e EMBEDDING_MODEL=text-embedding-3-small `
  -e EMBEDDING_DIM=1536 `
  -e EMBEDDING_BINDING=openai `
  -e EMBEDDING_BINDING_HOST=https://api.openai.com/v1 `
  -e EMBEDDING_BINDING_API_KEY=$openaiKey `
  -e EMBEDDING_FUNC_MAX_ASYNC=6 `
  -e EMBEDDING_BATCH_NUM=64 `
  -e LLM_BINDING=openai `
  -e LLM_MODEL=gpt-4o-mini `
  -e LLM_BINDING_HOST=https://api.openai.com/v1 `
  -e LLM_BINDING_API_KEY=$openaiKey `
  -e LLM_FUNC_MAX_ASYNC=4 `
  -e SUMMARY_CONTEXT_SIZE=6000 `
  -e CHUNK_SIZE=800 `
  -e CHUNK_OVERLAP=100 `
  -e TOP_K=12 `
  -e OPENAI_API_KEY=$openaiKey `
  -e WORKING_DIR=/app/data/rag_storage `
  -e INPUT_DIR=/app/data/inputs `
  ghcr.io/hkuds/lightrag:v1.4.9

if ($LASTEXITCODE -eq 0) {
    Write-Host ""
    Write-Host "Container created successfully!" -ForegroundColor Green
    Write-Host ""
    
    Write-Host "Key settings added:" -ForegroundColor Green
    Write-Host "  EMBEDDING_DIM=1536 (explicit dimension)"
    Write-Host "  EMBEDDING_BINDING_HOST=https://api.openai.com/v1"
    Write-Host "  EMBEDDING_BINDING_API_KEY=***"
    Write-Host "  LLM_BINDING_HOST=https://api.openai.com/v1"
    Write-Host "  LLM_BINDING_API_KEY=***"
    Write-Host "  SUMMARY_CONTEXT_SIZE=6000 (optimized for speed)"
    Write-Host "  CHUNK_SIZE=800 (optimized for precision)"
    Write-Host "  CHUNK_OVERLAP=100 (good default)"
    Write-Host "  TOP_K=12 (reduced from 40 for faster queries)"
    Write-Host ""
    
    Write-Host "Waiting for container to initialize..."
    Start-Sleep -Seconds 15
    
    $status = docker ps --filter "name=$containerName" --format "{{.Status}}"
    if ($status) {
        Write-Host "Container is running: $status" -ForegroundColor Green
    }
    
    Write-Host ""
    Write-Host $separator
    Write-Host "Configuration Fixed!"
    Write-Host $separator
    Write-Host ""
    Write-Host "Next steps:"
    Write-Host "1. Wait 30 seconds for LightRAG to fully start"
    Write-Host "2. Delete failed document in web UI"
    Write-Host "3. Re-upload document - should process successfully now!"
    Write-Host ""
    
} else {
    Write-Host ""
    Write-Host "ERROR: Failed to create container" -ForegroundColor Red
    exit 1
}
