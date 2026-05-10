from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.core.database import engine, Base
from app.core.config import settings
from app.routers import auth, projects, tasks, dashboard, ai, teams, analytics

# Import models to register them with Base
from app.models.user import User, Project, ProjectMember, Task, Comment, ActivityLog, Team, TeamMember

# Create all tables
Base.metadata.create_all(bind=engine)

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
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173", "http://localhost:3000", "*"],
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

@app.get("/")
def root():
    return {"message": "Team Task Manager API", "version": "1.0.0", "docs": "/docs"}

@app.get("/health")
def health():
    return {"status": "healthy"}
