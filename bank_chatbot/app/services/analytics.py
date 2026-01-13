"""
Analytics module for chat monitoring and performance metrics.
Uses PostgreSQL to track questions, answers, and performance.
"""

from sqlalchemy import Column, String, Text, DateTime, Integer, Float, Date, Index, func, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, List, Dict
import logging
import re

from app.database.postgres import Base, get_db

logger = logging.getLogger(__name__)

# Analytics models
class Question(Base):
    """Question tracking model"""
    __tablename__ = "analytics_questions"
    
    id = Column(Integer, primary_key=True, index=True)
    question_text = Column(Text, nullable=False, unique=True, index=True)
    normalized_question = Column(Text, index=True)
    total_asked = Column(Integer, default=1)
    answered_count = Column(Integer, default=0)
    unanswered_count = Column(Integer, default=0)
    first_asked = Column(DateTime(timezone=True), default=func.now())
    last_asked = Column(DateTime(timezone=True), default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_analytics_normalized', 'normalized_question'),
        Index('idx_analytics_total_asked', 'total_asked'),
    )


class PerformanceMetric(Base):
    """Daily performance metrics"""
    __tablename__ = "analytics_performance_metrics"
    
    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False, unique=True, index=True)
    total_conversations = Column(Integer, default=0)
    answered_count = Column(Integer, default=0)
    unanswered_count = Column(Integer, default=0)
    avg_response_time_ms = Column(Float)
    
    __table_args__ = (
        Index('idx_analytics_date', 'date'),
    )


class ConversationLog(Base):
    """Detailed conversation log for analytics"""
    __tablename__ = "analytics_conversations"
    
    id = Column(Integer, primary_key=True, index=True)
    session_id = Column(String(255), index=True, nullable=False)
    user_message = Column(Text, nullable=False)
    assistant_response = Column(Text, nullable=False)
    is_answered = Column(Integer, default=1)  # 1 = answered, 0 = unanswered
    knowledge_base = Column(String(255))
    response_time_ms = Column(Integer)
    client_ip = Column(String(45), index=True)  # IPv6 max length is 45 chars
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False, index=True)
    
    __table_args__ = (
        Index('idx_analytics_session_created', 'session_id', 'created_at'),
        Index('idx_analytics_is_answered', 'is_answered'),
        Index('idx_analytics_client_ip', 'client_ip'),
    )


def _normalize_question(question: str) -> str:
    """Normalize question for grouping similar questions"""
    # Convert to lowercase
    normalized = question.lower().strip()
    
    # Remove extra whitespace
    normalized = re.sub(r'\s+', ' ', normalized)
    
    # Remove common question words for better grouping
    # Keep the core meaning
    return normalized


def _is_unanswered(response: str) -> bool:
    """Detect if response indicates the question was not answered"""
    if not response:
        return True
    
    response_lower = response.lower().strip()
    
    unanswered_indicators = [
        "i don't know", "i don't have", "i cannot", "i can't",
        "i'm sorry", "i apologize", "unable to", "not available",
        "couldn't find", "no information", "not found",
        "i'm not sure", "i'm unable", "don't have access",
        "cannot provide", "unable to provide", "no data available"
    ]
    
    return any(indicator in response_lower for indicator in unanswered_indicators)


def log_conversation(
    session_id: str,
    user_message: str,
    assistant_response: str,
    knowledge_base: Optional[str] = None,
    response_time_ms: Optional[int] = None,
    client_ip: Optional[str] = None
):
    """
    Log a conversation for analytics
    """
    db = get_db()
    if not db:
        logger.warning("Database not available, skipping analytics logging")
        return
    
    try:
        is_answered = 0 if _is_unanswered(assistant_response) else 1
        
        # Log conversation
        try:
            conversation = ConversationLog(
                session_id=session_id,
                user_message=user_message,
                assistant_response=assistant_response,
                is_answered=is_answered,
                knowledge_base=knowledge_base,
                response_time_ms=response_time_ms,
                client_ip=client_ip
            )
            db.add(conversation)
            logger.info(f"Added ConversationLog for session {session_id}")
        except Exception as conv_error:
            logger.error(f"Error creating ConversationLog: {conv_error}", exc_info=True)
            # Continue with other logging even if ConversationLog fails
        
        # Update or insert question statistics
        normalized = _normalize_question(user_message)
        question = db.query(Question).filter(
            Question.question_text == user_message
        ).first()
        
        if question:
            question.total_asked += 1
            if is_answered:
                question.answered_count += 1
            else:
                question.unanswered_count += 1
            question.last_asked = datetime.utcnow()
        else:
            question = Question(
                question_text=user_message,
                normalized_question=normalized,
                total_asked=1,
                answered_count=1 if is_answered else 0,
                unanswered_count=0 if is_answered else 1
            )
            db.add(question)
        
        # Update daily performance metrics
        today = datetime.utcnow().date()
        metric = db.query(PerformanceMetric).filter(
            PerformanceMetric.date == today
        ).first()
        
        if metric:
            metric.total_conversations += 1
            if is_answered:
                metric.answered_count += 1
            else:
                metric.unanswered_count += 1
            if response_time_ms:
                # Update average response time
                if metric.avg_response_time_ms:
                    # Weighted average
                    total = metric.total_conversations
                    metric.avg_response_time_ms = (
                        (metric.avg_response_time_ms * (total - 1) + response_time_ms) / total
                    )
                else:
                    metric.avg_response_time_ms = response_time_ms
        else:
            metric = PerformanceMetric(
                date=today,
                total_conversations=1,
                answered_count=1 if is_answered else 0,
                unanswered_count=0 if is_answered else 1,
                avg_response_time_ms=response_time_ms
            )
            db.add(metric)
        
        db.commit()
        logger.info(f"Successfully committed conversation log for session {session_id}")
        
    except Exception as e:
        logger.error(f"Error logging conversation for analytics: {e}", exc_info=True)
        if db:
            db.rollback()
    finally:
        db.close()


def get_most_asked_questions(limit: int = 20) -> List[Dict]:
    """Get most frequently asked questions"""
    db = get_db()
    if not db:
        return []
    
    try:
        questions = db.query(Question).order_by(
            Question.total_asked.desc()
        ).limit(limit).all()
        
        results = []
        for q in questions:
            answer_rate = 0.0
            if q.total_asked > 0:
                answer_rate = round(100.0 * q.answered_count / q.total_asked, 2)
            
            results.append({
                'question': q.question_text,
                'normalized': q.normalized_question,
                'total_asked': q.total_asked,
                'answered_count': q.answered_count,
                'unanswered_count': q.unanswered_count,
                'answer_rate': answer_rate,
                'last_asked': q.last_asked.isoformat() if q.last_asked else None
            })
        
        return results
    except Exception as e:
        logger.error(f"Error getting most asked questions: {e}")
        return []
    finally:
        db.close()


def get_unanswered_questions(limit: int = 50) -> List[Dict]:
    """Get questions that were not answered"""
    db = get_db()
    if not db:
        return []
    
    try:
        questions = db.query(Question).filter(
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
    except Exception as e:
        logger.error(f"Error getting unanswered questions: {e}")
        return []
    finally:
        db.close()


def get_performance_metrics(days: int = 30) -> Dict:
    """Get performance metrics for the last N days"""
    db = get_db()
    if not db:
        return {
            'period_days': days,
            'overall': {
                'total_conversations': 0,
                'total_answered': 0,
                'total_unanswered': 0,
                'overall_answer_rate': 0,
                'avg_response_time_ms': 0
            },
            'daily_metrics': []
        }
    
    try:
        start_date = datetime.utcnow().date() - timedelta(days=days)
        
        # Daily metrics
        daily_metrics_query = db.query(PerformanceMetric).filter(
            PerformanceMetric.date >= start_date
        ).order_by(PerformanceMetric.date.desc()).all()
        
        daily_metrics = []
        for metric in daily_metrics_query:
            answer_rate = 0.0
            if metric.total_conversations > 0:
                answer_rate = round(100.0 * metric.answered_count / metric.total_conversations, 2)
            
            daily_metrics.append({
                'date': metric.date.isoformat(),
                'total_conversations': metric.total_conversations,
                'answered_count': metric.answered_count,
                'unanswered_count': metric.unanswered_count,
                'avg_response_time_ms': metric.avg_response_time_ms,
                'answer_rate': answer_rate
            })
        
        # Overall statistics
        overall_query = db.query(
            func.sum(PerformanceMetric.total_conversations).label('total_conversations'),
            func.sum(PerformanceMetric.answered_count).label('total_answered'),
            func.sum(PerformanceMetric.unanswered_count).label('total_unanswered'),
            func.avg(PerformanceMetric.avg_response_time_ms).label('avg_response_time_ms')
        ).filter(
            PerformanceMetric.date >= start_date
        ).first()
        
        total_conv = overall_query.total_conversations or 0
        total_ans = overall_query.total_answered or 0
        total_unans = overall_query.total_unanswered or 0
        avg_rt = overall_query.avg_response_time_ms or 0
        
        overall_answer_rate = 0.0
        if total_conv > 0:
            overall_answer_rate = round(100.0 * total_ans / total_conv, 2)
        
        return {
            'period_days': days,
            'overall': {
                'total_conversations': int(total_conv),
                'total_answered': int(total_ans),
                'total_unanswered': int(total_unans),
                'overall_answer_rate': overall_answer_rate,
                'avg_response_time_ms': round(avg_rt, 2) if avg_rt else 0
            },
            'daily_metrics': daily_metrics
        }
    except Exception as e:
        logger.error(f"Error getting performance metrics: {e}")
        return {
            'period_days': days,
            'overall': {
                'total_conversations': 0,
                'total_answered': 0,
                'total_unanswered': 0,
                'overall_answer_rate': 0,
                'avg_response_time_ms': 0
            },
            'daily_metrics': []
        }
    finally:
        db.close()


def get_conversation_history(session_id: Optional[str] = None, limit: int = 100) -> List[Dict]:
    """Get conversation history"""
    db = get_db()
    if not db:
        logger.warning("Database not available for conversation history")
        return []
    
    try:
        query = db.query(ConversationLog)
        
        if session_id:
            query = query.filter(ConversationLog.session_id == session_id)
        
        conversations = query.order_by(
            ConversationLog.created_at.desc()
        ).limit(limit).all()
        
        logger.info(f"Found {len(conversations)} conversations in database")
        
        results = []
        for conv in conversations:
            results.append({
                'id': conv.id,
                'session_id': conv.session_id,
                'user_message': conv.user_message,
                'assistant_response': conv.assistant_response,
                'is_answered': bool(conv.is_answered),
                'knowledge_base': conv.knowledge_base,
                'response_time_ms': conv.response_time_ms,
                'client_ip': conv.client_ip,
                'created_at': conv.created_at.isoformat() if conv.created_at else None
            })
        
        logger.info(f"Returning {len(results)} conversation results")
        return results
    except Exception as e:
        logger.error(f"Error getting conversation history: {e}", exc_info=True)
        return []
    finally:
        if db:
            db.close()

