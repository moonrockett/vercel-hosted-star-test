import logging
from datetime import datetime, timedelta
from .supabase_config import supabase

logger = logging.getLogger(__name__)

def init_db():
    """Initialize the database tables if they don't exist."""
    # Supabase tables are created via the web interface
    logger.info("Database connection initialized")
    pass

def add_new_user(user_id):
    """Add a new user to the database."""
    try:
        data = supabase.table('users').insert({
            'user_id': user_id,
            'first_seen': datetime.now().isoformat()
        }).execute()
        logger.info(f"Added new user: {user_id}")
        return data
    except Exception as e:
        logger.error(f"Error adding new user: {e}")
        return None

def increment_referral_count(referrer_id):
    """Increment the referral count for a user."""
    try:
        # First try to get existing record
        result = supabase.table('referrals').select('count').eq('referrer_id', referrer_id).execute()
        
        if result.data:
            # Update existing record
            new_count = result.data[0]['count'] + 1
            data = supabase.table('referrals').update({
                'count': new_count
            }).eq('referrer_id', referrer_id).execute()
        else:
            # Create new record
            data = supabase.table('referrals').insert({
                'referrer_id': referrer_id,
                'count': 1
            }).execute()
        return data
    except Exception as e:
        logger.error(f"Error incrementing referral count: {e}")
        return None

def get_referral_count(user_id):
    """Get the number of referrals for a user."""
    try:
        result = supabase.table('referrals').select('count').eq('referrer_id', user_id).execute()
        return result.data[0]['count'] if result.data else 0
    except Exception as e:
        logger.error(f"Error getting referral count: {e}")
        return 0

def update_usage_stats():
    """Update current connection count."""
    try:
        data = supabase.table('usage_stats').insert({
            'timestamp': datetime.now().isoformat(),
            'connections': 1
        }).execute()
        return data
    except Exception as e:
        logger.error(f"Error updating usage stats: {e}")
        return None

def cleanup_old_stats():
    """Remove stats older than 24 hours."""
    try:
        cleanup_time = (datetime.now() - timedelta(hours=24)).isoformat()
        data = supabase.table('usage_stats').delete().lt('timestamp', cleanup_time).execute()
        return data
    except Exception as e:
        logger.error(f"Error cleaning up old stats: {e}")
        return None

def get_usage_stats():
    """Get usage statistics."""
    try:
        hour_ago = (datetime.now() - timedelta(hours=1)).isoformat()
        
        # Get current connections
        current = supabase.table('usage_stats').select('count').execute()
        current_connections = len(current.data) if current.data else 0
        
        # Get stats for last hour
        stats = supabase.table('usage_stats').select('connections').gte('timestamp', hour_ago).execute()
        
        if stats.data:
            connections = [row['connections'] for row in stats.data]
            peak_last_hour = max(connections)
            avg_last_hour = sum(connections) / len(connections)
        else:
            peak_last_hour = 0
            avg_last_hour = 0
            
        # Get all-time max
        all_time = supabase.table('usage_stats').select('connections').execute()
        all_time_max = max([row['connections'] for row in all_time.data]) if all_time.data else 0
        
        return {
            'current_connections': current_connections,
            'peak_last_hour': peak_last_hour,
            'avg_last_hour': avg_last_hour,
            'all_time_max': all_time_max
        }
    except Exception as e:
        logger.error(f"Error getting usage stats: {e}")
        return {
            'current_connections': 0,
            'peak_last_hour': 0,
            'avg_last_hour': 0,
            'all_time_max': 0
        }

def get_unique_users_count():
    """Get the total number of unique users."""
    try:
        result = supabase.table('users').select('user_id', count='exact').execute()
        return result.count if result.count is not None else 0
    except Exception as e:
        logger.error(f"Error getting unique users count: {e}")
        return 0 