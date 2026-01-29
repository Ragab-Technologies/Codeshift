"""
Stress test for aiohttp 2.x to 3.x migration.

This file contains complex aiohttp 2.x patterns that need to be migrated to 3.x:
- Server with 20+ routes
- Client sessions with connection pooling
- WebSocket handlers
- Middleware chains
- Form data and file uploads
- Streaming responses
- SSE (Server-Sent Events)
- Custom connectors
- SSL/TLS configuration
- Timeout handling
- Cookie handling
- Basic auth and custom auth
- Request/response hooks
- Tracing and logging
- Deprecated loop parameter removal
"""

import asyncio
import json
import logging
import ssl
from pathlib import Path

import aiohttp
from aiohttp import web

# ==============================================================================
# DEPRECATED: loop parameter usage (aiohttp 2.x style)
# These should all have loop= parameters removed in 3.x
# ==============================================================================

# Global event loop (2.x pattern)
loop = asyncio.get_event_loop()

# TCPConnector with deprecated loop parameter
tcp_connector = aiohttp.TCPConnector(
    loop=loop,
    limit=100,
    limit_per_host=10,
    keepalive_timeout=30,
    enable_cleanup_closed=True,
)

# UnixConnector with deprecated loop parameter
unix_connector = aiohttp.UnixConnector(
    path="/var/run/app.sock",
    loop=loop,
)

# ClientSession with deprecated loop parameter
client_session = aiohttp.ClientSession(
    loop=loop,
    connector=tcp_connector,
    connector_owner=False,
)

# ClientSession with multiple deprecated parameters
advanced_session = aiohttp.ClientSession(
    loop=loop,
    connector=tcp_connector,
    read_timeout=30,
    conn_timeout=10,
)

# web.Application with deprecated loop parameter
app = web.Application(loop=loop)

# ClientTimeout with loop (though ClientTimeout didn't have loop, testing edge case)
timeout_config = aiohttp.ClientTimeout(total=60, connect=10, sock_read=30)


# ==============================================================================
# MIDDLEWARE CHAINS (2.x vs 3.x style)
# Old style: async def middleware(app, handler)
# New style: @web.middleware async def middleware(request, handler)
# ==============================================================================

# Old-style middleware (2.x) - needs migration
async def auth_middleware_old(app, handler):
    """Authentication middleware - old 2.x style."""
    async def middleware_handler(request):
        token = request.headers.get("Authorization")
        if not token and request.path not in ["/health", "/login", "/"]:
            return web.json_response({"error": "Unauthorized"}, status=401)
        request["user"] = await validate_token(token) if token else None
        return await handler(request)
    return middleware_handler


async def logging_middleware_old(app, handler):
    """Logging middleware - old 2.x style."""
    async def middleware_handler(request):
        logging.info(f"Request: {request.method} {request.path}")
        response = await handler(request)
        logging.info(f"Response: {response.status}")
        return response
    return middleware_handler


async def timing_middleware_old(app, handler):
    """Request timing middleware - old 2.x style."""
    async def middleware_handler(request):
        import time
        start = time.time()
        response = await handler(request)
        duration = time.time() - start
        response.headers["X-Request-Time"] = f"{duration:.3f}s"
        return response
    return middleware_handler


async def cors_middleware_old(app, handler):
    """CORS middleware - old 2.x style."""
    async def middleware_handler(request):
        if request.method == "OPTIONS":
            return web.Response(
                status=200,
                headers={
                    "Access-Control-Allow-Origin": "*",
                    "Access-Control-Allow-Methods": "GET, POST, PUT, DELETE, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization",
                }
            )
        response = await handler(request)
        response.headers["Access-Control-Allow-Origin"] = "*"
        return response
    return middleware_handler


async def error_middleware_old(app, handler):
    """Error handling middleware - old 2.x style."""
    async def middleware_handler(request):
        try:
            return await handler(request)
        except web.HTTPException:
            raise
        except Exception as e:
            logging.exception("Unhandled error")
            return web.json_response(
                {"error": "Internal Server Error", "detail": str(e)},
                status=500
            )
    return middleware_handler


async def rate_limit_middleware_old(app, handler):
    """Rate limiting middleware - old 2.x style."""
    async def middleware_handler(request):
        client_ip = request.remote
        # Rate limiting logic here
        if await is_rate_limited(client_ip):
            return web.json_response({"error": "Rate limited"}, status=429)
        return await handler(request)
    return middleware_handler


# ==============================================================================
# BASIC AUTH AND CUSTOM AUTH (2.x patterns)
# BasicAuth.encode() is deprecated in 3.x
# ==============================================================================

# BasicAuth with encode() - deprecated method
auth = aiohttp.BasicAuth("username", "password")
encoded_auth = auth.encode()

# Multiple auth patterns
def get_auth_header():
    """Get auth header using deprecated encode()."""
    basic_auth = aiohttp.BasicAuth("api_user", "api_secret")
    return basic_auth.encode()


def create_authenticated_session(user: str, password: str, event_loop):
    """Create session with basic auth - uses deprecated loop parameter."""
    auth = aiohttp.BasicAuth(user, password)
    encoded = auth.encode()  # Deprecated

    connector = aiohttp.TCPConnector(loop=event_loop, ssl=False)
    session = aiohttp.ClientSession(
        loop=event_loop,
        connector=connector,
        auth=auth,
    )
    return session


# ==============================================================================
# WEBSOCKET HANDLERS (2.x patterns)
# ws.protocol -> ws_protocol in 3.x
# ws_connect timeout -> receive_timeout
# ==============================================================================

async def websocket_handler(request):
    """WebSocket handler with 2.x patterns."""
    ws = web.WebSocketResponse()
    await ws.prepare(request)

    # Deprecated: .protocol attribute renamed to .ws_protocol
    protocol_info = ws.protocol
    logging.info(f"WebSocket protocol: {protocol_info}")

    async for msg in ws:
        if msg.type == aiohttp.WSMsgType.TEXT:
            if msg.data == "close":
                await ws.close()
            else:
                await ws.send_str(f"Echo: {msg.data}")
        elif msg.type == aiohttp.WSMsgType.ERROR:
            logging.error(f"WebSocket error: {ws.exception()}")

    return ws


async def websocket_client_example():
    """WebSocket client with deprecated timeout parameter."""
    async with aiohttp.ClientSession(loop=loop) as session:
        # Deprecated: timeout parameter renamed to receive_timeout
        async with session.ws_connect(
            "wss://example.com/ws",
            timeout=30,  # Should become receive_timeout
            heartbeat=20,
        ) as ws:
            websocket = ws
            # Deprecated: .protocol attribute
            print(f"Connected with protocol: {websocket.protocol}")

            await ws.send_str("Hello")
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    print(f"Received: {msg.data}")
                    break


# ==============================================================================
# 20+ ROUTE HANDLERS
# ==============================================================================

async def validate_token(token: str | None) -> dict | None:
    """Validate authentication token."""
    if token and token.startswith("Bearer "):
        return {"user_id": "123", "role": "admin"}
    return None


async def is_rate_limited(client_ip: str) -> bool:
    """Check if client is rate limited."""
    return False


# Route 1: Health check
async def health_check(request):
    """Health check endpoint."""
    return web.json_response({"status": "healthy"})


# Route 2: Home page
async def home(request):
    """Home page."""
    return web.Response(text="Welcome to the API")


# Route 3: User list
async def list_users(request):
    """List all users."""
    users = [{"id": 1, "name": "Alice"}, {"id": 2, "name": "Bob"}]
    return web.json_response(users)


# Route 4: Get user by ID
async def get_user(request):
    """Get user by ID."""
    user_id = request.match_info["user_id"]
    return web.json_response({"id": user_id, "name": "User"})


# Route 5: Create user
async def create_user(request):
    """Create a new user."""
    data = await request.json()
    return web.json_response({"id": 1, **data}, status=201)


# Route 6: Update user
async def update_user(request):
    """Update user."""
    user_id = request.match_info["user_id"]
    data = await request.json()
    return web.json_response({"id": user_id, **data})


# Route 7: Delete user
async def delete_user(request):
    """Delete user."""
    return web.Response(status=204)


# Route 8: Upload file
async def upload_file(request):
    """Handle file upload with multipart form data."""
    reader = await request.multipart()

    async for part in reader:
        if part.filename:
            file_data = await part.read()
            # Process file
            return web.json_response({
                "filename": part.filename,
                "size": len(file_data),
            })

    return web.json_response({"error": "No file provided"}, status=400)


# Route 9: Download file
async def download_file(request):
    """Streaming file download."""
    file_path = Path("/tmp/large_file.bin")

    response = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "application/octet-stream",
            "Content-Disposition": 'attachment; filename="download.bin"',
        }
    )
    await response.prepare(request)

    # Stream file in chunks
    chunk_size = 64 * 1024
    with open(file_path, "rb") as f:
        while chunk := f.read(chunk_size):
            await response.write(chunk)

    await response.write_eof()
    return response


# Route 10: Server-Sent Events (SSE)
async def sse_handler(request):
    """Server-Sent Events endpoint."""
    response = web.StreamResponse(
        status=200,
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
        }
    )
    await response.prepare(request)

    for i in range(10):
        event_data = json.dumps({"counter": i, "message": f"Event {i}"})
        await response.write(f"data: {event_data}\n\n".encode())
        await asyncio.sleep(1)

    await response.write_eof()
    return response


# Route 11: Form data processing
async def process_form(request):
    """Process URL-encoded form data."""
    data = await request.post()
    return web.json_response({
        "received": {key: str(value) for key, value in data.items()}
    })


# Route 12: JSON API endpoint
async def api_data(request):
    """JSON API endpoint."""
    return web.json_response({
        "data": list(range(100)),
        "metadata": {"count": 100},
    })


# Route 13: Redirect endpoint
async def redirect_handler(request):
    """Redirect to another URL."""
    raise web.HTTPFound("/api/data")


# Route 14: Static file serving simulation
async def serve_static(request):
    """Serve static content."""
    filename = request.match_info.get("filename", "index.html")
    return web.Response(
        text=f"<html><body>Static file: {filename}</body></html>",
        content_type="text/html"
    )


# Route 15: Cookie handling
async def set_cookie(request):
    """Set cookies in response."""
    response = web.json_response({"message": "Cookie set"})
    response.set_cookie("session_id", "abc123", max_age=3600, httponly=True)
    response.set_cookie("preferences", "dark_mode", secure=True)
    return response


# Route 16: Read cookies
async def read_cookies(request):
    """Read cookies from request."""
    cookies = request.cookies
    return web.json_response({
        "cookies": {name: value for name, value in cookies.items()}
    })


# Route 17: Request headers
async def echo_headers(request):
    """Echo request headers."""
    return web.json_response({
        "headers": dict(request.headers)
    })


# Route 18: Query parameters
async def query_params(request):
    """Handle query parameters."""
    params = request.rel_url.query
    return web.json_response({
        "params": dict(params)
    })


# Route 19: Path parameters
async def path_params(request):
    """Handle path parameters."""
    return web.json_response({
        "match_info": dict(request.match_info)
    })


# Route 20: Complex nested routes
async def nested_resource(request):
    """Handle nested resource."""
    parent_id = request.match_info["parent_id"]
    child_id = request.match_info["child_id"]
    return web.json_response({
        "parent_id": parent_id,
        "child_id": child_id,
    })


# Route 21: Batch operations
async def batch_operation(request):
    """Handle batch operations."""
    data = await request.json()
    operations = data.get("operations", [])
    results = []
    for op in operations:
        results.append({"id": op.get("id"), "status": "processed"})
    return web.json_response({"results": results})


# Route 22: Search endpoint
async def search(request):
    """Search endpoint with pagination."""
    query = request.rel_url.query.get("q", "")
    page = int(request.rel_url.query.get("page", 1))
    limit = int(request.rel_url.query.get("limit", 10))
    return web.json_response({
        "query": query,
        "page": page,
        "limit": limit,
        "results": [],
        "total": 0,
    })


# Route 23: Metrics endpoint
async def metrics(request):
    """Prometheus-style metrics endpoint."""
    metrics_text = """
# HELP http_requests_total Total HTTP requests
# TYPE http_requests_total counter
http_requests_total{method="GET"} 1234
http_requests_total{method="POST"} 567
"""
    return web.Response(text=metrics_text, content_type="text/plain")


# Route 24: GraphQL-style endpoint
async def graphql_handler(request):
    """GraphQL endpoint."""
    data = await request.json()
    query = data.get("query", "")
    variables = data.get("variables", {})
    return web.json_response({
        "data": {"result": "GraphQL response"},
        "errors": None,
    })


# ==============================================================================
# SSL/TLS CONFIGURATION
# ==============================================================================

def create_ssl_context():
    """Create SSL context for HTTPS connections."""
    ssl_ctx = ssl.create_default_context(ssl.Purpose.CLIENT_AUTH)
    ssl_ctx.load_cert_chain("cert.pem", "key.pem")
    return ssl_ctx


async def make_https_request():
    """Make HTTPS request with custom SSL context."""
    ssl_ctx = ssl.create_default_context()
    ssl_ctx.check_hostname = False
    ssl_ctx.verify_mode = ssl.CERT_NONE

    connector = aiohttp.TCPConnector(loop=loop, ssl=ssl_ctx)
    async with aiohttp.ClientSession(loop=loop, connector=connector) as session:
        async with session.get("https://example.com/api") as response:
            return await response.json()


# ==============================================================================
# CONNECTION POOLING AND CUSTOM CONNECTORS
# ==============================================================================

def create_production_connector(event_loop):
    """Create production-grade connector with connection pooling."""
    return aiohttp.TCPConnector(
        loop=event_loop,
        limit=200,
        limit_per_host=30,
        keepalive_timeout=60,
        enable_cleanup_closed=True,
        force_close=False,
        ssl=create_ssl_context(),
    )


def create_debug_connector(event_loop):
    """Create debug connector for testing."""
    return aiohttp.TCPConnector(
        loop=event_loop,
        limit=10,
        ssl=False,
        force_close=True,
    )


# ==============================================================================
# TIMEOUT HANDLING (2.x deprecated patterns)
# read_timeout, conn_timeout -> ClientTimeout in 3.x
# ==============================================================================

async def fetch_with_old_timeouts():
    """Fetch with deprecated timeout parameters."""
    # Old 2.x style: read_timeout and conn_timeout
    async with aiohttp.ClientSession(
        loop=loop,
        read_timeout=30,
        conn_timeout=10,
    ) as session:
        async with session.get("https://api.example.com/data") as response:
            return await response.json()


async def fetch_with_mixed_timeouts():
    """Fetch with both old and new timeout patterns."""
    connector = aiohttp.TCPConnector(loop=loop)

    # Old style - should be converted
    session1 = aiohttp.ClientSession(
        loop=loop,
        connector=connector,
        read_timeout=60,
    )

    # Another old style
    session2 = aiohttp.ClientSession(
        loop=loop,
        conn_timeout=5,
    )

    return session1, session2


# ==============================================================================
# REQUEST/RESPONSE HOOKS AND TRACING
# ==============================================================================

async def on_request_start(session, trace_config_ctx, params):
    """Hook called when request starts."""
    logging.info(f"Starting request to {params.url}")


async def on_request_end(session, trace_config_ctx, params):
    """Hook called when request ends."""
    logging.info(f"Request completed: {params.response.status}")


async def on_request_exception(session, trace_config_ctx, params):
    """Hook called on request exception."""
    logging.error(f"Request failed: {params.exception}")


def create_trace_config():
    """Create trace config for request monitoring."""
    trace_config = aiohttp.TraceConfig()
    trace_config.on_request_start.append(on_request_start)
    trace_config.on_request_end.append(on_request_end)
    trace_config.on_request_exception.append(on_request_exception)
    return trace_config


async def monitored_request():
    """Make request with tracing enabled."""
    trace_config = create_trace_config()

    async with aiohttp.ClientSession(
        loop=loop,
        trace_configs=[trace_config],
    ) as session:
        async with session.get("https://api.example.com/") as response:
            return await response.text()


# ==============================================================================
# URL ATTRIBUTE CHANGES
# response.url_obj -> response.url in 3.x
# ==============================================================================

async def handle_redirects():
    """Handle redirects and check final URL."""
    async with aiohttp.ClientSession(loop=loop) as session:
        async with session.get("https://example.com/redirect") as response:
            # Deprecated: url_obj should be just url
            final_url = response.url_obj
            print(f"Final URL: {final_url}")

            # Multiple usages
            host = response.url_obj.host
            path = response.url_obj.path

            return await response.text()


async def analyze_response_url():
    """Analyze response URL using deprecated attribute."""
    async with aiohttp.ClientSession(loop=loop) as session:
        async with session.get("https://api.example.com/v1/users") as resp:
            # Old attribute name
            url_info = {
                "scheme": resp.url_obj.scheme,
                "host": resp.url_obj.host,
                "path": resp.url_obj.path,
                "query": str(resp.url_obj.query),
            }
            return url_info


# ==============================================================================
# APP.LOOP DEPRECATION
# app.loop -> asyncio.get_event_loop() in 3.x
# ==============================================================================

async def startup_handler(app):
    """Application startup handler using deprecated app.loop."""
    # Deprecated: app.loop
    current_loop = app.loop

    # Create background task using app.loop
    app["background_task"] = app.loop.create_task(background_worker())

    # Schedule cleanup
    app.loop.call_later(3600, cleanup_task)


async def shutdown_handler(application):
    """Application shutdown handler."""
    # Deprecated: application.loop
    loop_ref = application.loop

    # Cancel background tasks
    if "background_task" in application:
        application["background_task"].cancel()


async def background_worker():
    """Background worker task."""
    while True:
        await asyncio.sleep(60)
        logging.info("Background worker tick")


def cleanup_task():
    """Scheduled cleanup task."""
    logging.info("Running cleanup")


def get_current_loop_from_app(web_app):
    """Get event loop from application - deprecated pattern."""
    return web_app.loop


# ==============================================================================
# COMPLEX CLIENT OPERATIONS
# ==============================================================================

class APIClient:
    """API client with deprecated patterns."""

    def __init__(self, base_url: str, event_loop=None):
        self.base_url = base_url
        self._loop = event_loop or asyncio.get_event_loop()
        self._connector = aiohttp.TCPConnector(
            loop=self._loop,
            limit=50,
        )
        self._session = aiohttp.ClientSession(
            loop=self._loop,
            connector=self._connector,
            read_timeout=30,
            conn_timeout=10,
        )

    async def get(self, path: str) -> dict:
        """GET request."""
        async with self._session.get(f"{self.base_url}{path}") as response:
            return await response.json()

    async def post(self, path: str, data: dict) -> dict:
        """POST request."""
        async with self._session.post(f"{self.base_url}{path}", json=data) as response:
            return await response.json()

    async def close(self):
        """Close the session."""
        await self._session.close()


class WebSocketClient:
    """WebSocket client with deprecated patterns."""

    def __init__(self, url: str, event_loop=None):
        self.url = url
        self._loop = event_loop or asyncio.get_event_loop()
        self._session = aiohttp.ClientSession(loop=self._loop)
        self._ws = None

    async def connect(self):
        """Connect to WebSocket server."""
        # Deprecated: timeout parameter
        self._ws = await self._session.ws_connect(
            self.url,
            timeout=30,
            heartbeat=20,
        )
        # Deprecated: .protocol attribute
        logging.info(f"Connected with protocol: {self._ws.protocol}")

    async def send(self, message: str):
        """Send message."""
        if self._ws:
            await self._ws.send_str(message)

    async def receive(self) -> str | None:
        """Receive message."""
        if self._ws:
            msg = await self._ws.receive()
            if msg.type == aiohttp.WSMsgType.TEXT:
                return msg.data
        return None

    async def close(self):
        """Close connection."""
        if self._ws:
            await self._ws.close()
        await self._session.close()


# ==============================================================================
# APPLICATION SETUP
# ==============================================================================

def setup_routes(web_app):
    """Setup all application routes."""
    # Basic routes
    web_app.router.add_get("/", home)
    web_app.router.add_get("/health", health_check)

    # User CRUD routes
    web_app.router.add_get("/users", list_users)
    web_app.router.add_get("/users/{user_id}", get_user)
    web_app.router.add_post("/users", create_user)
    web_app.router.add_put("/users/{user_id}", update_user)
    web_app.router.add_delete("/users/{user_id}", delete_user)

    # File operations
    web_app.router.add_post("/upload", upload_file)
    web_app.router.add_get("/download", download_file)

    # Streaming
    web_app.router.add_get("/events", sse_handler)

    # Form handling
    web_app.router.add_post("/form", process_form)

    # API endpoints
    web_app.router.add_get("/api/data", api_data)
    web_app.router.add_get("/redirect", redirect_handler)
    web_app.router.add_get("/static/{filename}", serve_static)

    # Cookie operations
    web_app.router.add_get("/cookies/set", set_cookie)
    web_app.router.add_get("/cookies/read", read_cookies)

    # Header and parameter operations
    web_app.router.add_get("/headers", echo_headers)
    web_app.router.add_get("/query", query_params)
    web_app.router.add_get("/path/{param1}/{param2}", path_params)

    # Nested resources
    web_app.router.add_get("/parent/{parent_id}/child/{child_id}", nested_resource)

    # Advanced endpoints
    web_app.router.add_post("/batch", batch_operation)
    web_app.router.add_get("/search", search)
    web_app.router.add_get("/metrics", metrics)
    web_app.router.add_post("/graphql", graphql_handler)

    # WebSocket
    web_app.router.add_get("/ws", websocket_handler)


def setup_middlewares(web_app):
    """Setup middleware chain using old-style middlewares."""
    # These are 2.x style middlewares
    web_app.middlewares.append(error_middleware_old)
    web_app.middlewares.append(timing_middleware_old)
    web_app.middlewares.append(logging_middleware_old)
    web_app.middlewares.append(cors_middleware_old)
    web_app.middlewares.append(auth_middleware_old)
    web_app.middlewares.append(rate_limit_middleware_old)


def create_app(event_loop=None) -> web.Application:
    """Create and configure the aiohttp application."""
    # Deprecated: loop parameter
    application = web.Application(loop=event_loop or loop)

    # Setup routes
    setup_routes(application)

    # Setup middlewares
    setup_middlewares(application)

    # Setup startup/shutdown handlers
    application.on_startup.append(startup_handler)
    application.on_shutdown.append(shutdown_handler)

    # Store references
    application["config"] = {
        "debug": True,
        "db_url": "postgresql://localhost/app",
    }

    return application


# ==============================================================================
# MAIN ENTRY POINTS
# ==============================================================================

async def main():
    """Main async entry point."""
    # Create application with deprecated loop parameter
    web_app = create_app(loop)

    # Get loop reference from app (deprecated)
    current_loop = web_app.loop

    # Create client for testing
    api_client = APIClient("https://api.example.com", event_loop=loop)

    try:
        # Make some requests
        result = await api_client.get("/users")
        print(f"Users: {result}")
    finally:
        await api_client.close()


def run_server():
    """Run the web server."""
    web_app = create_app()
    web.run_app(web_app, host="0.0.0.0", port=8080)


if __name__ == "__main__":
    # Run with deprecated asyncio pattern
    loop.run_until_complete(main())
