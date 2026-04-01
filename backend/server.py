"""FastAPI server for DM Game Master web interface."""

from fastapi import FastAPI, Response, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from backend.config import get_config
from backend.game_state import get_character_status
from backend.claude_dm import process_message, load_system_prompt

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


@app.get("/api/status")
async def get_status():
    """Get current character status for sidebar.

    Returns character stats, inventory, and location from world.json via WorldGraph.
    Uses game_state cache to minimize disk operations.

    Returns:
        dict: Character status with keys:
            - name (str): Character name
            - hp (int): Current health
            - max_hp (int): Maximum health
            - xp (int): Experience points
            - gold (int): Gold in base units (copper)
            - inventory (List[Dict]): Items [{name, quantity}]
            - location (str, optional): Current location
            Or error dict if failed:
            - error (str): Error message
    """
    status = get_character_status()
    return status


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

    # Initialize conversation state
    conversation_history = []
    system_prompt = None
    config = None

    # Load configuration and system prompt
    try:
        config = get_config()
        system_prompt = load_system_prompt()
        print(f"✅ WebSocket connected - API key configured, system prompt loaded ({len(system_prompt)} chars)")
    except ValueError as e:
        # No API key configured - send error message and close connection
        await websocket.send_text(f"❌ Configuration error: {str(e)}")
        await websocket.send_text("Please set ANTHROPIC_API_KEY in .env file")
        await websocket.close()
        return

    try:
        while True:
            # Receive message from player
            user_message = await websocket.receive_text()
            print(f"📩 Received message: {user_message[:50]}...")

            # Process message through DM agent with streaming
            try:
                async for text_chunk in process_message(
                    user_message=user_message,
                    conversation_history=conversation_history,
                    api_key=config.anthropic_api_key,
                    model_name=config.model_name,
                    system_prompt=system_prompt
                ):
                    # Stream each text chunk to frontend
                    await websocket.send_text(text_chunk)

                print(f"✅ Completed message processing")

            except Exception as e:
                # Send error to client and log
                error_message = f"Error: {str(e)}"
                print(f"❌ DM Agent error: {error_message}")
                await websocket.send_text(f"\n\n{error_message}")

    except WebSocketDisconnect:
        # Client disconnected, cleanup connection
        print(f"🔌 WebSocket disconnected")
        pass
