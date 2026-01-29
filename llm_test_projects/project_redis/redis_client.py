"""
Old redis-py patterns that need migration.
Uses deprecated patterns from redis 3.x that changed in redis 4.x+
"""
import redis
from redis import StrictRedis, Redis

# Old pattern: Using StrictRedis (deprecated alias in redis 4.x)
client = StrictRedis(
    host='localhost',
    port=6379,
    db=0,
    # Old pattern: decode_responses not commonly used
    charset='utf-8',  # Deprecated: use encoding parameter
    errors='strict'
)

# Old pattern: Using deprecated connection pool initialization
pool = redis.ConnectionPool(
    host='localhost',
    port=6379,
    db=0,
    # Deprecated parameters
    socket_timeout=5.0,
    socket_connect_timeout=5.0,
    retry_on_timeout=False  # Old default behavior
)

redis_from_pool = redis.Redis(connection_pool=pool)

# Old pattern: Using blocking_timeout (renamed in newer versions)
def acquire_lock_old_style(lock_name, timeout=10):
    """Old lock acquisition pattern."""
    lock = client.lock(
        lock_name,
        timeout=timeout,
        sleep=0.1,
        blocking_timeout=5  # Old parameter name
    )
    return lock.acquire()

# Old pattern: Using deprecated SET with separate EX/PX parameters
def set_with_expiry_old(key, value, expiry_seconds):
    """Old SET pattern with separate expiry."""
    # Old pattern: using set + expire separately
    client.set(key, value)
    client.expire(key, expiry_seconds)
    # Should use: client.set(key, value, ex=expiry_seconds)

# Old pattern: Using deprecated SETEX command directly
def setex_old_style(key, seconds, value):
    """Using deprecated setex method."""
    client.setex(key, seconds, value)  # Parameter order changed in newer versions

# Old pattern: Using deprecated scan_iter without proper typing
def scan_keys_old(pattern):
    """Old scan pattern."""
    keys = []
    for key in client.scan_iter(pattern):
        # Old pattern: key is bytes, not str
        keys.append(key.decode('utf-8'))
    return keys

# Old pattern: Using deprecated pipeline syntax
def batch_operations_old():
    """Old pipeline pattern."""
    pipe = client.pipeline(transaction=True)
    pipe.set('key1', 'value1')
    pipe.set('key2', 'value2')
    pipe.get('key1')
    # Old pattern: not using pipe as context manager
    results = pipe.execute()
    return results

# Old pattern: Using deprecated pubsub pattern
def subscribe_old_style(channel):
    """Old pubsub subscription pattern."""
    pubsub = client.pubsub()
    pubsub.subscribe(channel)
    # Old pattern: manual message iteration
    for message in pubsub.listen():
        if message['type'] == 'message':
            print(message['data'])

# Old pattern: Using deprecated hmset (removed in redis-py 4.0)
def set_hash_old(hash_name, mapping):
    """Using deprecated hmset method."""
    client.hmset(hash_name, mapping)  # Deprecated: use hset with mapping parameter

# Old pattern: Using deprecated lrem signature
def remove_from_list_old(list_name, value, count=0):
    """Old lrem signature."""
    client.lrem(list_name, count, value)  # Parameter order may differ
