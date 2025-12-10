# Analytics Endpoints

The Bank Chatbot API now includes comprehensive analytics endpoints for monitoring chat performance, tracking questions, and analyzing conversations.

## Available Endpoints

### Performance Metrics
Get performance metrics for the last N days (default: 30 days):

```
GET http://localhost:8001/api/analytics/performance
GET http://localhost:8001/api/analytics/performance?days=7
```

**Response includes:**
- Overall statistics (total conversations, answered/unanswered counts, answer rate, avg response time)
- Daily metrics breakdown

### Most Asked Questions
Get the most frequently asked questions:

```
GET http://localhost:8001/api/analytics/most-asked
GET http://localhost:8001/api/analytics/most-asked?limit=50
```

**Response includes:**
- Question text
- Total times asked
- Answered/unanswered counts
- Answer rate percentage
- Last asked timestamp

### Unanswered Questions
Get questions that were not answered:

```
GET http://localhost:8001/api/analytics/unanswered
GET http://localhost:8001/api/analytics/unanswered?limit=100
```

**Response includes:**
- Question text
- Unanswered count
- Total times asked
- Last asked timestamp

### Conversation History
Get conversation history (optionally filtered by session):

```
GET http://localhost:8001/api/analytics/history
GET http://localhost:8001/api/analytics/history?session_id=YOUR_SESSION_ID&limit=100
```

**Response includes:**
- Full conversation logs
- User messages and assistant responses
- Answer status
- Knowledge base used
- Response time
- Timestamps

### Health Check
Check system health:

```
GET http://localhost:8001/api/health
GET http://localhost:8001/api/health/detailed
```

### Debug LightRAG
Debug LightRAG status and last query:

```
GET http://localhost:8001/api/debug/lightrag
```

## Analytics Features

The analytics system automatically tracks:
- All user queries and assistant responses
- Question frequency and answer rates
- Daily performance metrics
- Response times
- Knowledge base usage
- Unanswered questions detection

## Database Tables

Analytics data is stored in PostgreSQL:
- `analytics_questions` - Question tracking and statistics
- `analytics_performance_metrics` - Daily performance aggregates
- `analytics_conversations` - Detailed conversation logs

Tables are automatically created when the application starts.

