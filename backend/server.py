"""FastAPI server for DM Game Master web interface."""

from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_config

# Initialize FastAPI app
app = FastAPI(
    title="DM Game Master API",
    description="Backend server for AI Dungeon Master web interface",
    version="1.0.0",
)

# CRITICAL: Add CORS middleware BEFORE route definitions
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for localhost development
    allow_credentials=True,
    allow_methods=["*"],  # Allow all HTTP methods
    allow_headers=["*"],  # Allow all headers
)


@app.on_event("startup")
async def startup_event():
    """Initialize application on startup."""
    print(f"🚀 DM Game Master backend starting...")

    # Try to load configuration, but don't fail if API key is missing
    # (API key will be validated when actually using the Anthropic API)
    try:
        config = get_config()
        print(f"📍 Server: {config.backend_host}:{config.backend_port}")
        print(f"🤖 Model: {config.model_name}")
        if config.campaign_name:
            print(f"🎲 Active campaign: {config.campaign_name}")
        else:
            print(f"⚠️  No active campaign loaded")
    except ValueError as e:
        print(f"⚠️  Configuration warning: {e}")
        print(f"⚠️  Server will start but AI features will be unavailable until configured")


@app.get("/api/health")
async def health_check():
    """Health check endpoint.

    Returns:
        dict: Status message indicating server is healthy
    """
    return {"status": "healthy"}


@app.get("/")
async def root():
    """Root endpoint with basic server info.

    Returns:
        dict: Welcome message and API documentation link
    """
    return {
        "message": "DM Game Master API",
        "version": "1.0.0",
        "docs": "/docs",
        "health": "/api/health",
    }


@app.get("/ws/game")
async def game_websocket_info():
    """HTTP GET handler for WebSocket endpoint.

    Returns 426 Upgrade Required to indicate this is a WebSocket endpoint.

    Returns:
        Response: 426 status code with Upgrade header
    """
    return Response(
        content="This endpoint requires WebSocket connection",
        status_code=426,
        headers={"Upgrade": "websocket"}
    )


@app.websocket("/ws/game")
async def game_websocket(websocket: WebSocket):
    """WebSocket endpoint for real-time game communication.

    Handles bi-directional communication between player and DM agent.
    Streams responses from Claude API and executes game tools.

    Args:
        websocket: WebSocket connection instance
    """
    await websocket.accept()

    try:
        while True:
            # Receive message from player
            message = await websocket.receive_text()

            # Echo back for now (DM agent integration will come in next subtasks)
            await websocket.send_text(f"Received: {message}")

    except WebSocketDisconnect:
        # Client disconnected, cleanup connection
        pass
