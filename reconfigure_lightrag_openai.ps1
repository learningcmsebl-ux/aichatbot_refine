# Reconfigure LightRAG to use OpenAI instead of Ollama
# This script will stop the current container and restart it with OpenAI configuration

$separator = "=" * 70
Write-Host $separator
Write-Host "Reconfiguring LightRAG to use OpenAI"
Write-Host $separator
Write-Host ""

# Load OpenAI API key from .env file
$envFile = "bank_chatbot\.env"
$openaiKey = $null

if (Test-Path $envFile) {
    $envContent = Get-Content $envFile
    $keyLine = $envContent | Where-Object { $_ -match "^OPENAI_API_KEY=" }
    if ($keyLine) {
        $openaiKey = $keyLine -replace "^OPENAI_API_KEY=", "" | ForEach-Object { $_.Trim() }
        Write-Host "Found OpenAI API key in $envFile" -ForegroundColor Green
    }
}

if (-not $openaiKey -or $openaiKey -eq "your_openai_api_key_here") {
    Write-Host "Please provide your OpenAI API key:" -ForegroundColor Yellow
    $openaiKey = Read-Host "Enter OpenAI API Key"
}

if (-not $openaiKey) {
    Write-Host "ERROR: Valid OpenAI API key is required. Exiting." -ForegroundColor Red
    exit 1
}

Write-Host "Using OpenAI API key" -ForegroundColor Green
Write-Host ""

# Container name
$containerName = "LightRAG_New"

# Check if container exists
Write-Host "Checking current LightRAG container..."
$containerExists = docker ps -a --filter "name=$containerName" --format "{{.Names}}"

if ($containerExists) {
    Write-Host "Found container: $containerName" -ForegroundColor Green
    
    # Stop the container
    Write-Host ""
    Write-Host "Stopping current container..."
    docker stop $containerName | Out-Null
    Write-Host "Container stopped" -ForegroundColor Green
    
    # Remove the container
    Write-Host "Removing old container..."
    docker rm $containerName | Out-Null
    Write-Host "Container removed" -ForegroundColor Green
} else {
    Write-Host "Container not found. Will create new one." -ForegroundColor Yellow
}

Write-Host ""

# Create new container with OpenAI configuration
# Optimized settings: SUMMARY_CONTEXT_SIZE=6000, CHUNK_SIZE=800, CHUNK_OVERLAP=100
Write-Host "Creating new container with OpenAI configuration..."
Write-Host ""

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
    
    # Wait for container to start
    Write-Host "Waiting for container to initialize (10 seconds)..."
    Start-Sleep -Seconds 10
    
    # Check container status
    Write-Host ""
    Write-Host "Checking container status..."
    $status = docker ps --filter "name=$containerName" --format "{{.Status}}"
    if ($status) {
        Write-Host "Container is running: $status" -ForegroundColor Green
    } else {
        Write-Host "Container status unclear. Check with: docker ps" -ForegroundColor Yellow
    }
    
    Write-Host ""
    Write-Host $separator
    Write-Host "Configuration Complete!"
    Write-Host $separator
    Write-Host ""
    Write-Host "LightRAG is now configured to use OpenAI instead of Ollama."
    Write-Host ""
    Write-Host "Next steps:"
    Write-Host "1. Wait a few more seconds for LightRAG to fully start"
    Write-Host "2. Check health with: python -c 'from connect_lightrag import LightRAGClient; client = LightRAGClient(); print(client.health_check())'"
    Write-Host "3. Re-upload your documents in LightRAG web UI (http://localhost:9262/webui)"
    Write-Host "4. Trigger scan to process documents"
    Write-Host ""
    Write-Host "Documents should now process successfully without Ollama errors!"
    Write-Host ""
    
} else {
    Write-Host ""
    Write-Host "ERROR: Failed to create container. Check the error above." -ForegroundColor Red
    Write-Host ""
    Write-Host "You may need to check:"
    Write-Host "- Docker is running"
    Write-Host "- Port 9262 is not in use"
    Write-Host "- OpenAI API key is valid"
    exit 1
}
