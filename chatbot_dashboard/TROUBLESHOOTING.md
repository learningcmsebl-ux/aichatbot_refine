# Dashboard Troubleshooting Guide

## Blank Page Issues

If you see a blank page at `http://localhost:3001`, check the following:

### 1. Check Browser Console
Open Developer Tools (F12) and check the Console tab for errors.

### 2. Verify Dev Server is Running
```bash
cd chatbot_dashboard
npm run dev
```

You should see:
```
  VITE v7.x.x  ready in xxx ms

  ➜  Local:   http://localhost:3001/
  ➜  Network: http://0.0.0.0:3001/
```

### 3. Check Backend API
Ensure the backend is running on port 8001:
```bash
curl http://localhost:8001/api/health
```

### 4. Common Issues

**Issue: "Failed to fetch" or CORS errors**
- Solution: Backend must be running and CORS must be configured
- Check: `bank_chatbot/app/core/config.py` has CORS_ORIGINS set correctly

**Issue: "Module not found" errors**
- Solution: Run `npm install` in the dashboard directory
- Check: All dependencies are installed

**Issue: Blank page with no errors**
- Solution: Check if React Router is properly installed
- Run: `npm install react-router-dom@^6.30.2`

**Issue: API connection errors**
- Solution: Verify backend is accessible
- Check: `vite.config.ts` proxy configuration points to `http://localhost:8001`

### 5. Verify File Structure
```
chatbot_dashboard/
├── src/
│   ├── components/
│   │   ├── Dashboard.tsx
│   │   ├── MetricsCards.tsx
│   │   ├── PerformanceChart.tsx
│   │   ├── QuestionsTable.tsx
│   │   ├── ConversationsTable.tsx
│   │   └── HealthStatusPanel.tsx
│   ├── services/
│   │   └── api.ts
│   ├── types/
│   │   └── index.ts
│   ├── App.tsx
│   ├── main.tsx
│   └── index.css
├── public/
│   └── dia-avatar.png
├── index.html
├── package.json
└── vite.config.ts
```

### 6. Test API Endpoints Manually
```bash
# Test health endpoint
curl http://localhost:8001/api/health

# Test analytics endpoint
curl http://localhost:8001/api/analytics/performance
```

### 7. Clear Cache and Rebuild
```bash
# Delete node_modules and reinstall
rm -rf node_modules
npm install

# Clear browser cache (Ctrl+Shift+Delete)
# Or use incognito mode
```

### 8. Check Network Tab
In browser DevTools → Network tab:
- Look for failed requests (red)
- Check if API calls are being made
- Verify response status codes

## Still Having Issues?

1. Check the terminal where `npm run dev` is running for errors
2. Check browser console (F12) for JavaScript errors
3. Verify all files exist in the correct locations
4. Ensure backend is running and accessible

