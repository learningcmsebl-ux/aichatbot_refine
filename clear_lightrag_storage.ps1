# Clear LightRAG storage to fix embedding dimension mismatch
# This will remove all indexed documents - you'll need to re-upload

Write-Host ("=" * 70)
Write-Host "Clear LightRAG Storage"
Write-Host ("=" * 70)
Write-Host ""
Write-Host "This will delete all indexed documents in LightRAG."
Write-Host "You will need to re-upload all documents after this."
Write-Host ""
$confirm = Read-Host "Are you sure you want to continue? (yes/no)"

if ($confirm -ne "yes") {
    Write-Host "Cancelled." -ForegroundColor Yellow
    exit 0
}

$containerName = "LightRAG_New"

Write-Host ""
Write-Host "Stopping container..."
docker stop $containerName | Out-Null
Write-Host "Container stopped" -ForegroundColor Green

Write-Host ""
Write-Host "Backing up current storage..."
docker exec $containerName sh -c "cd /app/data && if [ -d rag_storage ]; then mv rag_storage rag_storage.backup.$(date +%Y%m%d_%H%M%S); fi" 2>&1 | Out-Null
Write-Host "Backup created" -ForegroundColor Green

Write-Host ""
Write-Host "Creating fresh storage directory..."
docker exec $containerName sh -c "mkdir -p /app/data/rag_storage" 2>&1 | Out-Null
Write-Host "Fresh storage created" -ForegroundColor Green

Write-Host ""
Write-Host "Restarting container..."
docker start $containerName | Out-Null
Write-Host "Container restarted" -ForegroundColor Green

Write-Host ""
Write-Host ("=" * 70)
Write-Host "Storage Cleared Successfully!"
Write-Host ("=" * 70)
Write-Host ""
Write-Host "Next steps:"
Write-Host "1. Wait 30 seconds for LightRAG to fully restart"
Write-Host "2. Re-upload your documents:"
Write-Host "   python upload_to_knowledge_base.py scraped_text/EBL_Management_Committee.txt --knowledge-base ebl_website"
Write-Host "   python upload_to_knowledge_base.py scraped_text/EBL-ANNUAL-REPORT-2024.txt --knowledge-base ebl_financial_reports"
Write-Host "3. Trigger scan in LightRAG web UI"
Write-Host "4. Documents should process successfully now!"
Write-Host ""
Write-Host "Note: Old storage backed up in container at /app/data/rag_storage.backup.*"
Write-Host ""

