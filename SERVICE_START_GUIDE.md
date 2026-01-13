# Service Start Guide

This guide explains how to start and stop all EBL Chatbot services (Backend, Frontend, and Dashboard).

## Quick Start

### Option 1: Double-Click (Easiest)
- **Start All Services**: Double-click `start_all.bat`
- **Stop All Services**: Double-click `stop_all.bat`

### Option 2: PowerShell Scripts
- **Start All Services**: Run `.\start_all_services.ps1` in PowerShell
- **Stop All Services**: Run `.\stop_all_services.ps1` in PowerShell

### Option 3: Manual Start
If you prefer to start services manually:

#### 1. Backend API (Port 8001)
```powershell
cd E:\Chatbot_refine\bank_chatbot
python run.py
```

#### 2. Frontend (Port 3000)
```powershell
cd E:\Chatbot_refine\bank_chatbot_frontend\vite-project
npm run dev
```

#### 3. Dashboard (Port 3001)
```powershell
cd E:\Chatbot_refine\chatbot_dashboard
npm run dev
```

## Service URLs

After starting all services, access them at:

- **Backend API**: http://localhost:8001
  - Health Check: http://localhost:8001/api/health
  - API Docs: http://localhost:8001/docs

- **Frontend (Chat Interface)**: http://localhost:3000
  - This is the main chatbot interface for users

- **Dashboard (Analytics)**: http://localhost:3001
  - Analytics and monitoring dashboard

## What the Start Script Does

1. **Checks Port Availability**: Verifies that ports 8001, 3000, and 3001 are free
2. **Starts Backend**: Opens a new PowerShell window running the FastAPI backend
3. **Starts Frontend**: Opens a new PowerShell window running the React frontend
4. **Starts Dashboard**: Opens a new PowerShell window running the analytics dashboard
5. **Verifies Services**: Checks if services are responding
6. **Optional Browser Launch**: Asks if you want to open the services in your browser

## Service Windows

Each service runs in its own PowerShell window:
- **Backend Window**: Shows FastAPI/uvicorn logs
- **Frontend Window**: Shows Vite dev server logs
- **Dashboard Window**: Shows Vite dev server logs

**Important**: Keep these windows open while the services are running. Closing a window will stop that service.

## Troubleshooting

### Port Already in Use
If a port is already in use:
1. Run `.\stop_all_services.ps1` first
2. Or manually kill the process using the port:
   ```powershell
   # Find process using port 8001
   Get-NetTCPConnection -LocalPort 8001 | Select-Object OwningProcess
   # Kill it (replace PID with actual process ID)
   Stop-Process -Id <PID> -Force
   ```

### Services Not Starting
1. **Backend Issues**:
   - Check if Python is installed: `python --version`
   - Check if dependencies are installed: `pip install -r requirements.txt`
   - Check if PostgreSQL and Redis are running

2. **Frontend/Dashboard Issues**:
   - Check if Node.js is installed: `node --version`
   - Install dependencies: `npm install` (in the respective directory)
   - Check for port conflicts

### Services Not Responding
1. Wait a few seconds after starting (services need time to initialize)
2. Check the service windows for error messages
3. Verify the service is listening on the correct port:
   ```powershell
   netstat -ano | findstr ":8001"
   netstat -ano | findstr ":3000"
   netstat -ano | findstr ":3001"
   ```

## Service Dependencies

### Backend Requires:
- Python 3.8+
- PostgreSQL database (running)
- Redis cache (running)
- LightRAG service (running on port 9262)

### Frontend Requires:
- Node.js 16+
- npm or yarn
- Backend API running (port 8001)

### Dashboard Requires:
- Node.js 16+
- npm or yarn
- Backend API running (port 8001)

## Production Deployment

For production, you should:
1. Build the frontend: `npm run build` (in frontend directory)
2. Build the dashboard: `npm run build` (in dashboard directory)
3. Use a production WSGI server (e.g., gunicorn) for the backend
4. Use a reverse proxy (e.g., nginx) to serve static files
5. Set up process managers (e.g., PM2, systemd) to keep services running

## Notes

- The start script opens separate windows for each service so you can monitor logs
- Services are started in order: Backend → Frontend → Dashboard
- The script waits a few seconds between starting services to avoid conflicts
- You can close the main script window after services start (but keep service windows open)




