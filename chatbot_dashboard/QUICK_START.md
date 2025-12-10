# Quick Start Guide - Analytics Dashboard

## Prerequisites

1. Backend API must be running on `http://localhost:8001`
2. Node.js and npm installed

## Installation & Running

1. **Navigate to dashboard directory:**
   ```bash
   cd chatbot_dashboard
   ```

2. **Install dependencies (if not already done):**
   ```bash
   npm install
   ```

3. **Start the development server:**
   ```bash
   npm run dev
   ```

4. **Open your browser:**
   Navigate to `http://localhost:3001`

## Dashboard Features

### 📊 Metrics Overview
- Total conversations count
- Answered vs unanswered breakdown
- Overall answer rate percentage

### 📈 Performance Charts
- Daily conversation trends
- Answer rate over time
- Visual charts using Recharts

### ❓ Question Analytics
- Most frequently asked questions
- Unanswered questions tracking
- Answer rate per question

### 💬 Conversation History
- Recent conversations list
- Expandable conversation details
- Filter by session ID

### 🏥 System Health
- LightRAG status
- Redis cache status
- PostgreSQL database status

## Configuration

The dashboard automatically connects to the backend API. To change the API URL, create a `.env` file:

```env
VITE_API_URL=http://localhost:8001
```

## Auto-Refresh

The dashboard automatically refreshes data every 30 seconds. You can also manually refresh using the "Refresh" button in the header.

## Time Period Filter

Use the dropdown in the header to filter performance metrics:
- Last 7 days
- Last 30 days
- Last 90 days
- Last year

## Troubleshooting

**Dashboard not loading?**
- Ensure backend is running on port 8001
- Check browser console for errors
- Verify API endpoints are accessible

**No data showing?**
- Check if analytics tables exist in PostgreSQL
- Verify backend analytics endpoints are working
- Check browser network tab for API errors

