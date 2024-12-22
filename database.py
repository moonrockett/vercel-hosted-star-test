import sqlite3
import os
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# Database path - store in api directory for Vercel
DB_PATH = os.path.join('api', 'bot.db')

def init_db():
    """Initialize the database with required tables."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()

        # Create users table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')

        # Create referrals table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS referrals (
                referrer_id INTEGER,
                count INTEGER DEFAULT 0,
                PRIMARY KEY (referrer_id)
            )
        ''')

        # Create usage stats table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS usage_stats (
                timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                connections INTEGER DEFAULT 0
            )
        ''')

        conn.commit()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.error(f"Database initialization error: {e}")
    finally:
        conn.close()

def add_new_user(user_id):
    """Add a new user to the database."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT OR IGNORE INTO users (user_id) VALUES (?)
        ''', (user_id,))
        
        conn.commit()
    except Exception as e:
        logger.error(f"Error adding new user: {e}")
    finally:
        conn.close()

def increment_referral_count(referrer_id):
    """Increment the referral count for a user."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO referrals (referrer_id, count) 
            VALUES (?, 1)
            ON CONFLICT(referrer_id) 
            DO UPDATE SET count = count + 1
        ''', (referrer_id,))
        
        conn.commit()
    except Exception as e:
        logger.error(f"Error incrementing referral count: {e}")
    finally:
        conn.close()

def get_referral_count(user_id):
    """Get the number of referrals for a user."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT count FROM referrals WHERE referrer_id = ?', (user_id,))
        result = cursor.fetchone()
        
        return result[0] if result else 0
    except Exception as e:
        logger.error(f"Error getting referral count: {e}")
        return 0
    finally:
        conn.close()

def update_usage_stats():
    """Update current connection count."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        current_time = datetime.now()
        cursor.execute('''
            INSERT INTO usage_stats (timestamp, connections)
            VALUES (?, 1)
        ''', (current_time,))
        
        conn.commit()
    except Exception as e:
        logger.error(f"Error updating usage stats: {e}")
    finally:
        conn.close()

def cleanup_old_stats():
    """Remove stats older than 24 hours."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cleanup_time = datetime.now() - timedelta(hours=24)
        cursor.execute('DELETE FROM usage_stats WHERE timestamp < ?', (cleanup_time,))
        
        conn.commit()
    except Exception as e:
        logger.error(f"Error cleaning up old stats: {e}")
    finally:
        conn.close()

def get_usage_stats():
    """Get usage statistics."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        # Get current hour stats
        hour_ago = datetime.now() - timedelta(hours=1)
        cursor.execute('''
            SELECT 
                COUNT(*) as current_connections,
                MAX(connections) as peak_last_hour,
                AVG(connections) as avg_last_hour,
                (SELECT MAX(connections) FROM usage_stats) as all_time_max
            FROM usage_stats 
            WHERE timestamp > ?
        ''', (hour_ago,))
        
        result = cursor.fetchone()
        
        return {
            'current_connections': result[0],
            'peak_last_hour': result[1],
            'avg_last_hour': result[2],
            'all_time_max': result[3]
        }
    except Exception as e:
        logger.error(f"Error getting usage stats: {e}")
        return {
            'current_connections': 0,
            'peak_last_hour': 0,
            'avg_last_hour': 0,
            'all_time_max': 0
        }
    finally:
        conn.close()

def get_unique_users_count():
    """Get the total number of unique users."""
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute('SELECT COUNT(DISTINCT user_id) FROM users')
        result = cursor.fetchone()
        
        return result[0] if result else 0
    except Exception as e:
        logger.error(f"Error getting unique users count: {e}")
        return 0
    finally:
        conn.close() 