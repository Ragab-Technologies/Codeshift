"""
Old aiohttp patterns that need migration.
Uses deprecated patterns from aiohttp 3.7.x that changed in newer versions
"""
import aiohttp
from aiohttp import ClientSession, TCPConnector, BasicAuth

# Old pattern: Using deprecated connector configuration
async def create_session_old():
    """Old session creation pattern."""
    # Deprecated: Using old TCPConnector parameters
    connector = TCPConnector(
        verify_ssl=False,  # Deprecated: use ssl=False
        use_dns_cache=True,  # Old parameter name
        limit=100,
        limit_per_host=10,
        # Deprecated: Using keepalive_timeout
        keepalive_timeout=30
    )
    
    # Old pattern: Creating session without async context manager
    session = ClientSession(
        connector=connector,
        # Deprecated: Using loop parameter
        loop=None,
        # Old pattern: Using deprecated timeout configuration
        read_timeout=30,
        conn_timeout=10
    )
    return session

# Old pattern: Using deprecated request methods
async def make_request_old(session, url):
    """Old request pattern."""
    # Deprecated: Using encoding parameter
    async with session.get(url, encoding='utf-8') as response:
        # Old pattern: Using deprecated text() call
        text = await response.text(encoding='utf-8')
        return text

# Old pattern: Using deprecated form data handling
async def post_form_data_old(session, url, data):
    """Old form data pattern."""
    # Deprecated: Using deprecated FormData API
    form = aiohttp.FormData()
    for key, value in data.items():
        form.add_field(key, value)
    
    async with session.post(url, data=form) as response:
        return await response.json()

# Old pattern: Using deprecated authentication
async def authenticated_request_old(session, url, username, password):
    """Old authentication pattern."""
    # Deprecated: Using BasicAuth directly in request
    auth = BasicAuth(username, password, encoding='latin1')  # Deprecated encoding param
    
    async with session.get(url, auth=auth) as response:
        return await response.json()

# Old pattern: Using deprecated WebSocket API
async def websocket_old_style(session, url):
    """Old WebSocket pattern."""
    # Deprecated: Using ws_connect without proper context
    ws = await session.ws_connect(url)
    
    try:
        # Old pattern: Using deprecated receive methods
        async for msg in ws:
            if msg.type == aiohttp.WSMsgType.TEXT:
                if msg.data == 'close':
                    await ws.close()
                    break
                else:
                    # Old pattern: Using deprecated send methods
                    await ws.send_str(msg.data + '/answer')
            elif msg.type == aiohttp.WSMsgType.ERROR:
                break
    finally:
        # Old explicit close
        await ws.close()

# Old pattern: Using deprecated multipart handling
async def upload_file_old(session, url, filepath):
    """Old file upload pattern."""
    # Deprecated: Using deprecated file reading pattern
    with open(filepath, 'rb') as f:
        # Old pattern: Using deprecated data parameter style
        async with session.post(
            url,
            data={'file': f},
            # Deprecated: Using chunked parameter
            chunked=True
        ) as response:
            return await response.json()

# Old pattern: Using deprecated trace config
async def create_traced_session():
    """Old tracing pattern."""
    # Deprecated: Using old TraceConfig API
    trace_config = aiohttp.TraceConfig()
    
    # Old pattern: Using deprecated callback signatures
    async def on_request_start(session, trace_config_ctx, params):
        print(f"Request started: {params.url}")
    
    trace_config.on_request_start.append(on_request_start)
    
    session = ClientSession(trace_configs=[trace_config])
    return session

# Old pattern: Using deprecated cookie handling
async def handle_cookies_old(session, url):
    """Old cookie handling pattern."""
    # Deprecated: Accessing cookies directly
    async with session.get(url) as response:
        # Old pattern: Using deprecated cookie jar access
        cookies = session.cookie_jar.filter_cookies(url)
        for cookie in cookies.values():
            print(f"Cookie: {cookie.key}={cookie.value}")
