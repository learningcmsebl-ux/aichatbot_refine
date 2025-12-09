"""
Conversation Analytics Module - PostgreSQL Version
Stores all conversations in PostgreSQL and provides analytics for performance assessment
Optimized for performance with proper indexing and connection pooling
"""
import os
import asyncio
from datetime import datetime, date, timedelta
from typing import Optional, List, Dict
from queue import Queue
import threading
import logging
from contextlib import contextmanager
from sqlalchemy import create_engine, Column, String, Text, DateTime, Integer, Date, Float, Index, func, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import JSONB

logger = logging.getLogger(__name__)

Base = declarative_base()


class Conversation(Base):
    """Conversation model for PostgreSQL"""
    __tablename__ = "conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String, nullable=False, index=True)
    user_message = Column(Text, nullable=False)
    assistant_response = Column(Text, nullable=False)
    is_answered = Column(Integer, default=1, index=True)  # 1 if answered, 0 if unanswered
    knowledge_base = Column(String, nullable=True)
    response_time_ms = Column(Integer, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)
    
    __table_args__ = (
        Index('idx_session_id', 'session_id'),
        Index('idx_created_at', 'created_at'),
        Index('idx_is_answered', 'is_answered'),
    )


class Question(Base):
    """Question statistics model"""
    __tablename__ = "questions"
    
    id = Column(Integer, primary_key=True, index=True)
    question_text = Column(Text, nullable=False, unique=True)
    normalized_question = Column(String, index=True, nullable=True)
    total_asked = Column(Integer, default=1)
    answered_count = Column(Integer, default=0)
    unanswered_count = Column(Integer, default=0)
    first_asked = Column(DateTime, server_default=func.now())
    last_asked = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_normalized', 'normalized_question'),
        Index('idx_total_asked', 'total_asked'),
    )


class PerformanceMetric(Base):
    """Performance metrics model"""
    __tablename__ = "performance_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    total_conversations = Column(Integer, default=0)
    answered_count = Column(Integer, default=0)
    unanswered_count = Column(Integer, default=0)
    avg_response_time_ms = Column(Float, nullable=True)
    
    __table_args__ = (
        Index('idx_date', 'date'),
        UniqueConstraint('date', name='uq_performance_metrics_date'),
    )


# Thread-safe queue for async logging
_log_queue = Queue()
_log_thread = None
_log_thread_running = False

# Database connection
_engine = None
_SessionLocal = None


def _init_database(database_url: str = None):
    """Initialize PostgreSQL database with required tables"""
    global _engine, _SessionLocal
    
    if database_url is None:
        # Get from environment variables
        database_url = os.getenv(
            'ANALYTICS_DB_URL',
            os.getenv('POSTGRES_DB_URL') or 
            f"postgresql://{os.getenv('POSTGRES_USER', 'postgres')}:"
            f"{os.getenv('POSTGRES_PASSWORD', '')}@"
            f"{os.getenv('POSTGRES_HOST', 'localhost')}:"
            f"{os.getenv('POSTGRES_PORT', '5432')}/"
            f"{os.getenv('POSTGRES_DB', 'postgres')}"
        )
    
    _engine = create_engine(
        database_url,
        pool_pre_ping=True,
        pool_size=10,
        max_overflow=20,
        pool_recycle=3600,
        echo=False
    )
    _SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=_engine)
    
    # Create tables
    Base.metadata.create_all(bind=_engine)
    
    logger.info(f"[OK] Analytics PostgreSQL database initialized")


@contextmanager
def _get_session():
    """Context manager for database sessions"""
    if _SessionLocal is None:
        _init_database()
    
    session = _SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _normalize_question(question: str) -> str:
    """Normalize question for grouping similar questions"""
    normalized = question.lower().strip()
    normalized = normalized.replace("?", "").replace("!", "").replace(".", "")
    normalized = " ".join(normalized.split())
    return normalized


def _is_unanswered(response: str) -> bool:
    """Check if response indicates the question was not answered"""
    response_lower = response.lower().strip()
    unanswered_indicators = [
        "no relevant information found in my knowledgebase",
        "no relevant information found",
        "not specified in the provided context",
        "please check the official",
        "information not available"
    ]
    return any(indicator in response_lower for indicator in unanswered_indicators)


def _log_worker():
    """Background worker thread that processes log queue"""
    global _log_thread_running
    _log_thread_running = True
    
    while _log_thread_running or not _log_queue.empty():
        try:
            # Get item from queue with timeout
            try:
                item = _log_queue.get(timeout=1)
            except:
                continue
            
            if item is None:  # Shutdown signal
                break
            
            try:
                with _get_session() as session:
                    # Insert conversation
                    conversation = Conversation(
                        session_id=item['session_id'],
                        user_message=item['user_message'],
                        assistant_response=item['assistant_response'],
                        is_answered=1 if item['is_answered'] else 0,
                        knowledge_base=item.get('knowledge_base'),
                        response_time_ms=item.get('response_time_ms'),
                        created_at=datetime.utcnow()
                    )
                    session.add(conversation)
                    session.flush()  # Get the ID if needed
                    
                    # Update or insert question statistics
                    normalized = _normalize_question(item['user_message'])
                    now = datetime.utcnow()
                    answered_val = 1 if item['is_answered'] else 0
                    unanswered_val = 0 if item['is_answered'] else 1
                    
                    # Use PostgreSQL's ON CONFLICT for upsert
                    question = session.query(Question).filter(
                        Question.question_text == item['user_message']
                    ).first()
                    
                    if question:
                        question.total_asked += 1
                        question.answered_count += answered_val
                        question.unanswered_count += unanswered_val
                        question.last_asked = now
                    else:
                        question = Question(
                            question_text=item['user_message'],
                            normalized_question=normalized,
                            total_asked=1,
                            answered_count=answered_val,
                            unanswered_count=unanswered_val,
                            first_asked=now,
                            last_asked=now
                        )
                        session.add(question)
                    
                    # Update daily performance metrics
                    today = date.today()
                    metric = session.query(PerformanceMetric).filter(
                        PerformanceMetric.date == today
                    ).first()
                    
                    if metric:
                        metric.total_conversations += 1
                        metric.answered_count += answered_val
                        metric.unanswered_count += unanswered_val
                        # Update average response time
                        if item.get('response_time_ms'):
                            current_avg = metric.avg_response_time_ms or 0
                            total = metric.total_conversations
                            metric.avg_response_time_ms = (
                                (current_avg * (total - 1) + item['response_time_ms']) / total
                            )
                    else:
                        metric = PerformanceMetric(
                            date=today,
                            total_conversations=1,
                            answered_count=answered_val,
                            unanswered_count=unanswered_val,
                            avg_response_time_ms=item.get('response_time_ms')
                        )
                        session.add(metric)
                    
                    session.commit()
                    _log_queue.task_done()
                    
            except Exception as e:
                logger.error(f"Error logging conversation: {e}")
                _log_queue.task_done()
                continue
                
        except Exception as e:
            logger.error(f"Error in log worker: {e}")
            continue
    
    logger.info("[INFO] Log worker thread stopped")


def start_log_worker(database_url: str = None):
    """Start background worker thread for logging"""
    global _log_thread
    if _log_thread is None or not _log_thread.is_alive():
        _init_database(database_url)
        _log_thread = threading.Thread(target=_log_worker, daemon=True)
        _log_thread.start()
        logger.info("[OK] Analytics log worker started")


def stop_log_worker():
    """Stop background worker thread"""
    global _log_thread_running, _log_queue
    _log_thread_running = False
    _log_queue.put(None)  # Signal shutdown
    if _log_thread:
        _log_thread.join(timeout=5)


def log_conversation(
    session_id: str,
    user_message: str,
    assistant_response: str,
    knowledge_base: Optional[str] = None,
    response_time_ms: Optional[int] = None
):
    """
    Log a conversation asynchronously (non-blocking)
    
    Args:
        session_id: Session identifier
        user_message: User's question/input
        assistant_response: Bot's response
        knowledge_base: Knowledge base used (optional)
        response_time_ms: Response time in milliseconds (optional)
    """
    if not _log_thread_running:
        start_log_worker()
    
    is_answered = not _is_unanswered(assistant_response)
    
    _log_queue.put({
        'session_id': session_id,
        'user_message': user_message,
        'assistant_response': assistant_response,
        'is_answered': is_answered,
        'knowledge_base': knowledge_base,
        'response_time_ms': response_time_ms
    })


# Analytics query functions
def get_most_asked_questions(limit: int = 20) -> List[Dict]:
    """Get most frequently asked questions"""
    with _get_session() as session:
        questions = session.query(Question).order_by(
            Question.total_asked.desc()
        ).limit(limit).all()
        
        results = []
        for q in questions:
            answer_rate = (q.answered_count / q.total_asked * 100) if q.total_asked > 0 else 0
            results.append({
                'question': q.question_text,
                'normalized': q.normalized_question,
                'total_asked': q.total_asked,
                'answered_count': q.answered_count,
                'unanswered_count': q.unanswered_count,
                'answer_rate': round(answer_rate, 2),
                'last_asked': q.last_asked.isoformat() if q.last_asked else None
            })
        return results


def get_unanswered_questions(limit: int = 50) -> List[Dict]:
    """Get questions that were not answered"""
    with _get_session() as session:
        questions = session.query(Question).filter(
            Question.unanswered_count > 0
        ).order_by(
            Question.unanswered_count.desc(),
            Question.last_asked.desc()
        ).limit(limit).all()
        
        results = []
        for q in questions:
            results.append({
                'question': q.question_text,
                'normalized': q.normalized_question,
                'unanswered_count': q.unanswered_count,
                'total_asked': q.total_asked,
                'last_asked': q.last_asked.isoformat() if q.last_asked else None
            })
        return results


def get_performance_metrics(days: int = 30) -> Dict:
    """Get performance metrics for the last N days"""
    with _get_session() as session:
        # Calculate date threshold
        threshold_date = date.today() - timedelta(days=days)
        
        # Daily metrics
        metrics = session.query(PerformanceMetric).filter(
            PerformanceMetric.date >= threshold_date
        ).order_by(PerformanceMetric.date.desc()).all()
        
        daily_metrics = []
        for m in metrics:
            answer_rate = (m.answered_count / m.total_conversations * 100) if m.total_conversations > 0 else 0
            daily_metrics.append({
                'date': m.date.isoformat(),
                'total_conversations': m.total_conversations,
                'answered_count': m.answered_count,
                'unanswered_count': m.unanswered_count,
                'avg_response_time_ms': m.avg_response_time_ms,
                'answer_rate': round(answer_rate, 2)
            })
        
        # Overall statistics
        overall = session.query(
            func.sum(PerformanceMetric.total_conversations).label('total_conversations'),
            func.sum(PerformanceMetric.answered_count).label('total_answered'),
            func.sum(PerformanceMetric.unanswered_count).label('total_unanswered'),
            func.avg(PerformanceMetric.avg_response_time_ms).label('avg_response_time_ms')
        ).filter(
            PerformanceMetric.date >= threshold_date
        ).first()
        
        overall_answer_rate = 0
        if overall.total_conversations and overall.total_conversations > 0:
            overall_answer_rate = (overall.total_answered / overall.total_conversations * 100)
        
        return {
            'period_days': days,
            'overall': {
                'total_conversations': overall.total_conversations or 0,
                'total_answered': overall.total_answered or 0,
                'total_unanswered': overall.total_unanswered or 0,
                'overall_answer_rate': round(overall_answer_rate, 2),
                'avg_response_time_ms': round(overall.avg_response_time_ms or 0, 2)
            },
            'daily_metrics': daily_metrics
        }


def get_conversation_history(session_id: Optional[str] = None, limit: int = 100) -> List[Dict]:
    """Get conversation history"""
    with _get_session() as session:
        if session_id:
            conversations = session.query(Conversation).filter(
                Conversation.session_id == session_id
            ).order_by(Conversation.created_at.desc()).limit(limit).all()
        else:
            conversations = session.query(Conversation).order_by(
                Conversation.created_at.desc()
            ).limit(limit).all()
        
        results = []
        for c in conversations:
            results.append({
                'id': c.id,
                'session_id': c.session_id,
                'user_message': c.user_message,
                'assistant_response': c.assistant_response,
                'is_answered': bool(c.is_answered),
                'knowledge_base': c.knowledge_base,
                'response_time_ms': c.response_time_ms,
                'created_at': c.created_at.isoformat() if c.created_at else None
            })
        return results

