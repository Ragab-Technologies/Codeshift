"""
Old httpx patterns that need migration.
Uses deprecated patterns from httpx 0.23.x that changed in newer versions
"""
import httpx
from httpx import AsyncClient, Client

# Old pattern: Using deprecated timeout configuration
client = Client(
    # Deprecated: Using single timeout value instead of Timeout object
    timeout=30.0,
    # Old pattern: Using deprecated verify parameter style
    verify=False,
    # Deprecated: Using cert parameter without proper tuple
    cert='/path/to/client.pem'
)

# Old pattern: Using deprecated HTTPStatusError handling
def make_request_old_style(url):
    """Old request pattern with deprecated error handling."""
    try:
        response = client.get(url)
        # Old pattern: Using deprecated status_code check
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        # Old pattern: Accessing deprecated attributes
        print(f"Error: {e.response.status_code}")
        return None

# Old pattern: Using deprecated async context manager style
async def async_request_old():
    """Old async client pattern."""
    # Deprecated: Creating client without async context manager
    client = AsyncClient()
    try:
        response = await client.get('https://api.example.com/data')
        return response.json()
    finally:
        await client.aclose()  # Old explicit close pattern

# Old pattern: Using deprecated auth parameter style
def request_with_auth_old(url, username, password):
    """Old authentication pattern."""
    # Deprecated: Using tuple for basic auth directly
    response = client.get(
        url,
        auth=(username, password),
        # Old pattern: Using deprecated headers dict style
        headers={'Accept': 'application/json'}
    )
    return response

# Old pattern: Using deprecated stream context manager
def download_file_old(url, filepath):
    """Old streaming download pattern."""
    # Deprecated: Using stream() method
    with client.stream('GET', url) as response:
        with open(filepath, 'wb') as f:
            # Old pattern: Using deprecated iter_bytes
            for chunk in response.iter_bytes():
                f.write(chunk)

# Old pattern: Using deprecated pooling configuration
pool_limits = httpx.PoolLimits(  # Deprecated: Use Limits
    max_keepalive=5,
    max_connections=10
)

# Old pattern: Using deprecated dispatch configuration
old_client = Client(
    # Deprecated: Using pool_limits
    pool_limits=pool_limits,
    # Old pattern: Using deprecated trust_env
    trust_env=True
)

# Old pattern: Using deprecated request hooks
def log_request(request):
    """Old request hook."""
    print(f"Request: {request.url}")

def log_response(response):
    """Old response hook."""
    print(f"Response: {response.status_code}")

hooked_client = Client(
    # Deprecated: Using event_hooks style
    event_hooks={
        'request': [log_request],
        'response': [log_response]
    }
)

# Old pattern: Using deprecated Proxy configuration
proxied_client = Client(
    # Deprecated: Using proxies dict instead of proxy parameter
    proxies={
        'http://': 'http://proxy.example.com:8080',
        'https://': 'http://proxy.example.com:8080'
    }
)
