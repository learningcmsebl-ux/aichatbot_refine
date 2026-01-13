# ATM/CRM/RTDM Tab - Troubleshooting Guide

## Issue
The tab shows "No machines found" even though the location service has 218 machines.

## Verification Steps

### 1. Check API Endpoint Directly
```bash
# Test the API endpoint
curl -u admin:admin123 "http://localhost:8009/api/locations?type=atm&limit=10&offset=0"
```

Should return JSON with machines data.

### 2. Check Browser Console
Open browser developer tools (F12) and check:
- **Console tab**: Look for JavaScript errors
- **Network tab**: Check if `/api/locations?type=atm...` request is being made
- Check the response from the API call

### 3. Hard Refresh Browser
The JavaScript file might be cached. Try:
- **Ctrl+F5** (Windows) or **Cmd+Shift+R** (Mac) to hard refresh
- Or clear browser cache

### 4. Check Admin Panel Service
Make sure the admin panel service is running and serving the updated files:
```bash
# Check if service is running
docker ps | grep admin
# Or check process
netstat -ano | findstr :8009
```

### 5. Verify JavaScript Changes
The key changes made:
- `machineCurrentFilters` is initialized with `{ type: 'atm' }` on page load
- `loadMachines()` always includes `type=atm` parameter
- Better error handling and console logging added

## Expected Behavior

1. When the page loads, `machineCurrentFilters` should be `{ type: 'atm' }`
2. The API call should be: `/api/locations?type=atm&limit=50&offset=0`
3. Should return 218 machines total
4. Should display first 50 machines in the table

## Debug Steps

1. Open browser console (F12)
2. Go to the ATM/CRM/RTDM tab
3. Check console for:
   - "Machines API response:" log message
   - Any error messages
   - Network request to `/api/locations`

4. If you see the API response in console, check:
   - Does `data.locations` have items?
   - Does `data.total` show 218?
   - Are there any errors in the forEach loop?

## Quick Fix

If the issue persists, try:
1. **Hard refresh the page** (Ctrl+F5)
2. **Clear browser cache** completely
3. **Restart the admin panel service** if running in Docker
4. **Check browser console** for specific errors

## Current Code State

- ✅ Default filter set to 'atm' on page load
- ✅ API call always includes type parameter
- ✅ Better error handling added
- ✅ Console logging for debugging








