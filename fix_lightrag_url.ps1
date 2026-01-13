# Fix LightRAG URL in .env file
$envFile = "bank_chatbot\.env"

if (Test-Path $envFile) {
    Write-Host "Updating LightRAG URL in .env file..."
    
    # Read current content
    $content = Get-Content $envFile
    
    # Replace LIGHTRAG_URL
    $newContent = $content | ForEach-Object {
        if ($_ -match "^LIGHTRAG_URL=") {
            "LIGHTRAG_URL=http://localhost:9262/query"
        } else {
            $_
        }
    }
    
    # Write back
    $newContent | Set-Content $envFile
    Write-Host "✅ Updated LIGHTRAG_URL to http://localhost:9262/query"
} else {
    Write-Host "Creating .env file with correct LightRAG URL..."
    @"
# LightRAG Configuration
LIGHTRAG_URL=http://localhost:9262/query
LIGHTRAG_API_KEY=MyCustomLightRagKey456
LIGHTRAG_KNOWLEDGE_BASE=default
LIGHTRAG_TIMEOUT=30
"@ | Out-File -FilePath $envFile -Encoding utf8
    Write-Host "✅ Created .env file with correct LightRAG URL"
}

Write-Host "`nPlease restart the chatbot for changes to take effect."

