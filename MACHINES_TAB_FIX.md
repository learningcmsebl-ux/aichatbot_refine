# ATM/CRM/RTDM Tab Fix

## Problem
The ATM/CRM/RTDM tab was showing "No machines found" even though the location service has 218 machines.

## Root Cause
The JavaScript was calling `/api/locations` without specifying a `type` parameter, which caused the API to return all location types (branches, machines, priority centers) mixed together. The client-side filtering wasn't working correctly because the API was returning branches first.

## Solution
Updated the JavaScript to:
1. **Default to 'atm' type** when no machine type filter is selected
2. **Always specify a type parameter** when querying the API
3. **Initialize with default filter** when the page loads

## Changes Made

### `script.js` - `loadMachines()` function
- Now defaults to `type=atm` when no type filter is set
- Always includes a type parameter in the API call

### `script.js` - `applyMachineFilters()` function  
- Defaults to 'atm' if no type is selected
- Ensures machines are always queried

### `script.js` - `clearMachineFilters()` function
- Sets default to 'atm' when filters are cleared
- Ensures machines are still shown after clearing

### `script.js` - Initialization
- Initializes `machineCurrentFilters` with `{ type: 'atm' }` on page load

## Result
- The tab now shows ATMs by default (218 machines available)
- Users can filter by machine type (ATM, CRM, RTDM)
- Users can filter by city, region, or search term
- Data loads correctly when the tab is opened

## Testing
1. Open the admin panel
2. Click on "ATM/CRM/RTDM" tab
3. Should see ATMs listed (default view)
4. Try filtering by type (CRM, RTDM)
5. Try filtering by city or region
6. Clear filters - should return to ATM view








