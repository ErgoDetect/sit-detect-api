import logging
import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi

from api.routes.files_router import files_router
from api.routes.auth_router import auth_router
from api.routes.google_router import google_router
from api.routes.user_router import user_router
from api.routes.websocket_router import websocket_router
from api.routes.delete_router import delete_router
from database.database import engine
import database.model as model

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
script_dir = os.path.dirname(os.path.abspath(__file__))
env_path = os.path.join(script_dir, ".env")
load_dotenv(dotenv_path=env_path)
logger.info("Loaded .env file")


# Initialize FastAPI app
app = FastAPI()

# CORS configuration
origins = ["http://localhost:1212"]
app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Create all database tables
model.Base.metadata.create_all(bind=engine)


# Custom OpenAPI schema
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    openapi_schema = get_openapi(
        title="WebSocket API",
        version="1.0.0",
        description="This is a simple WebSocket API",
        routes=app.routes,
    )
    # Add documentation for the WebSocket endpoint
    openapi_schema["paths"]["/landmark/results/"] = {
        "get": {
            "summary": "WebSocket connection",
            "description": "Connect to the WebSocket server. Send a message and receive a response.",
            "responses": {
                "101": {
                    "description": "Switching Protocols - The client is switching protocols as requested by the server.",
                }
            },
        }
    }
    app.openapi_schema = openapi_schema
    return app.openapi_schema


app.openapi = custom_openapi

# Include routers
app.include_router(auth_router, prefix="/auth", tags=["Authentication"])
app.include_router(user_router, prefix="/user", tags=["User"])
app.include_router(google_router, prefix="/auth/google", tags=["Google OAuth"])
app.include_router(websocket_router, prefix="/landmark", tags=["WebSocket"])
app.include_router(files_router, prefix="/files", tags=["Files"])
app.include_router(delete_router, prefix="/delete", tags=["Delete"])


@app.get("/")
async def root():
    return {"message": "Hello World"}
