import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from app.core.database import engine, Base
from app.core.config import settings
from app.routers import auth, projects, tasks, dashboard, ai, teams, analytics

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import models to register them with Base
from app.models.user import User, Project, ProjectMember, Task, Comment, ActivityLog, Team, TeamMember

# Create all tables
try:
    logger.info("Connecting to database and creating tables...")
    # Base.metadata.drop_all(bind=engine) # Uncomment if schema reset is needed
    Base.metadata.create_all(bind=engine)
    logger.info("Database tables verified/created successfully.")
except Exception as e:
    logger.error(f"Error during database initialization: {e}")

app = FastAPI(
    title="Team Task Manager API",
    description="Full-stack project & task management with RBAC",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(auth.router, prefix="/api/v1")
app.include_router(projects.router, prefix="/api/v1")
app.include_router(tasks.router, prefix="/api/v1")
app.include_router(dashboard.router, prefix="/api/v1")
app.include_router(teams.router, prefix="/api/v1")
app.include_router(analytics.router, prefix="/api/v1")
app.include_router(ai.router, prefix="/api/v1")

@app.get("/health")
def health():
    return {"status": "healthy"}

from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    return JSONResponse(
        status_code=500,
        content={"message": "Internal Server Error", "detail": str(exc)},
    )

# Serve frontend - index.html at root and all other routes
FRONTEND_PATH = os.path.join(os.path.dirname(__file__), "frontend", "index.html")

@app.get("/")
@app.get("/app")
def serve_frontend():
    if os.path.exists(FRONTEND_PATH):
        return FileResponse(FRONTEND_PATH)
    return {"message": "Team Task Manager API", "version": "1.0.0", "docs": "/docs"}
