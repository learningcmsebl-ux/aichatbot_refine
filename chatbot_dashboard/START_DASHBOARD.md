# How to Start the Dashboard

## Step-by-Step Instructions

### 1. Ensure Backend is Running
First, make sure your backend API is running:
```bash
cd bank_chatbot
python run.py
```

The backend should be accessible at `http://localhost:8001`

### 2. Start the Dashboard
Open a **new terminal window** and run:
```bash
cd E:\Chatbot_refine\chatbot_dashboard
npm run dev
```

You should see output like:
```
  VITE v7.x.x  ready in xxx ms

  ➜  Local:   http://localhost:3001/
  ➜  Network: http://0.0.0.0:3001/
```

### 3. Open in Browser
Navigate to: **http://localhost:3001**

## Troubleshooting Blank Page

If you see a blank page:

### Check Browser Console
1. Press **F12** to open Developer Tools
2. Go to the **Console** tab
3. Look for any red error messages
4. Share the error messages if you need help

### Check Network Tab
1. In Developer Tools, go to the **Network** tab
2. Refresh the page (F5)
3. Look for failed requests (they'll be red)
4. Check if `/api/health` or `/api/analytics/performance` are failing

### Verify Backend Connection
Test if the backend is accessible:
```bash
curl http://localhost:8001/api/health
```

Should return: `{"status":"healthy","service":"Bank Chatbot API"}`

### Common Issues

**Issue: "Cannot GET /"**
- The dev server might not be running
- Solution: Run `npm run dev` in the dashboard directory

**Issue: "Failed to fetch" or CORS errors**
- Backend might not be running
- Solution: Start the backend with `python run.py` in the `bank_chatbot` directory

**Issue: Blank page with no console errors**
- Check if React is loading
- Solution: Look for any import errors in the terminal where `npm run dev` is running

**Issue: "Module not found"**
- Dependencies might not be installed
- Solution: Run `npm install` in the dashboard directory

## Quick Test

To verify everything is working:

1. **Backend test:**
   ```bash
   curl http://localhost:8001/api/analytics/performance
   ```
   Should return JSON with performance metrics

2. **Dashboard test:**
   - Open browser to `http://localhost:3001`
   - Check console (F12) for errors
   - Should see the dashboard header with "EBL DIA 2.0 - Analytics Dashboard"

## Need Help?

If the dashboard is still blank:
1. Check the terminal running `npm run dev` for errors
2. Check browser console (F12) for JavaScript errors
3. Verify backend is running and accessible
4. Check that all files exist in `chatbot_dashboard/src/`

