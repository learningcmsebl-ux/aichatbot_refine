# EBL DIA 2.0 - Analytics Dashboard

A React-based dashboard for monitoring and analyzing the EBL DIA 2.0 chatbot performance.

## Features

- **Real-time Metrics**: View total conversations, answer rates, and performance trends
- **Question Analytics**: Track most asked questions and unanswered queries
- **Conversation History**: Browse detailed conversation logs
- **System Health**: Monitor LightRAG, Redis, and PostgreSQL status
- **Performance Charts**: Visualize trends with interactive charts
- **Auto-refresh**: Dashboard updates every 30 seconds

## Setup

1. Install dependencies:
```bash
cd chatbot_dashboard
npm install
```

2. Start the development server:
```bash
npm run dev
```

3. Open your browser to `http://localhost:3001`

## Configuration

The dashboard connects to the backend API at `http://localhost:8001` by default. You can configure this by setting the `VITE_API_URL` environment variable.

## API Endpoints Used

- `/api/analytics/performance` - Performance metrics
- `/api/analytics/most-asked` - Most asked questions
- `/api/analytics/unanswered` - Unanswered questions
- `/api/analytics/history` - Conversation history
- `/api/health/detailed` - System health status

## Build for Production

```bash
npm run build
```

The built files will be in the `dist` directory.

