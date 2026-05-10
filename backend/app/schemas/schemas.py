from pydantic import BaseModel, EmailStr, Field, validator
from typing import Optional, List
from datetime import datetime
from enum import Enum

# Enums
class RoleEnum(str, Enum):
    admin = "admin"
    member = "member"

class TaskStatusEnum(str, Enum):
    todo = "todo"
    in_progress = "in_progress"
    in_review = "in_review"
    done = "done"

class TaskPriorityEnum(str, Enum):
    low = "low"
    medium = "medium"
    high = "high"
    urgent = "urgent"

# ─── Auth Schemas ───────────────────────────────────────────────────────────

class UserRegister(BaseModel):
    name: str = Field(..., min_length=2, max_length=100)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=100)
    role: RoleEnum = RoleEnum.member

    @validator('password')
    def password_complexity(cls, v):
        import re
        if not re.search(r"[A-Z]", v):
            raise ValueError("Password must contain at least one uppercase letter")
        if not re.search(r"[a-z]", v):
            raise ValueError("Password must contain at least one lowercase letter")
        if not re.search(r"\d", v):
            raise ValueError("Password must contain at least one number")
        if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", v):
            raise ValueError("Password must contain at least one special character")
        return v

class UserLogin(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"

class RefreshTokenRequest(BaseModel):
    refresh_token: str

# ─── User Schemas ────────────────────────────────────────────────────────────

class UserBase(BaseModel):
    id: int
    name: str
    email: str
    role: str
    avatar_color: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True

class UserPublic(BaseModel):
    id: int
    name: str
    email: str
    role: str
    avatar_color: str

    class Config:
        from_attributes = True

class UserUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=100)
    avatar_color: Optional[str] = None

# ─── Project Schemas ─────────────────────────────────────────────────────────

class ProjectCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = Field(None, max_length=1000)
    color: Optional[str] = "#6366f1"

class ProjectUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=2, max_length=200)
    description: Optional[str] = None
    color: Optional[str] = None

class ProjectMemberInfo(BaseModel):
    id: int
    name: str
    email: str
    role: str
    avatar_color: str

    class Config:
        from_attributes = True

class ProjectResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    color: str
    owner_id: int
    owner: UserPublic
    is_active: bool
    created_at: datetime
    task_count: Optional[int] = 0
    member_count: Optional[int] = 0

    class Config:
        from_attributes = True

class ProjectDetail(ProjectResponse):
    members: List[ProjectMemberInfo] = []

# ─── Task Schemas ─────────────────────────────────────────────────────────────

class TaskCreate(BaseModel):
    title: str = Field(..., min_length=2, max_length=300)
    description: Optional[str] = Field(None, max_length=2000)
    status: TaskStatusEnum = TaskStatusEnum.todo
    priority: TaskPriorityEnum = TaskPriorityEnum.medium
    assignee_id: Optional[int] = None
    due_date: Optional[datetime] = None

class TaskUpdate(BaseModel):
    title: Optional[str] = Field(None, min_length=2, max_length=300)
    description: Optional[str] = None
    status: Optional[TaskStatusEnum] = None
    priority: Optional[TaskPriorityEnum] = None
    assignee_id: Optional[int] = None
    due_date: Optional[datetime] = None

class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    status: str
    priority: str
    project_id: int
    assignee_id: Optional[int]
    assignee: Optional[UserPublic]
    creator_id: int
    creator: UserPublic
    due_date: Optional[datetime]
    created_at: datetime
    updated_at: Optional[datetime]
    is_overdue: Optional[bool] = False

    class Config:
        from_attributes = True

# ─── Comment Schemas ──────────────────────────────────────────────────────────

class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

class CommentResponse(BaseModel):
    id: int
    content: str
    task_id: int
    author_id: int
    author: UserPublic
    created_at: datetime

    class Config:
        from_attributes = True

# ─── Dashboard Schemas ────────────────────────────────────────────────────────

class DashboardStats(BaseModel):
    total_tasks: int
    todo: int
    in_progress: int
    in_review: int
    done: int
    overdue: int
    total_projects: int
    my_tasks: int

class ActivityLogResponse(BaseModel):
    id: int
    action: str
    entity_type: str
    entity_id: int
    entity_name: Optional[str]
    user_id: Optional[int]
    user: Optional[UserPublic]
    created_at: datetime

    class Config:
        from_attributes = True

# ─── Generic ──────────────────────────────────────────────────────────────────

class MessageResponse(BaseModel):
    message: str

class AddMemberRequest(BaseModel):
    user_id: int

# ─── Team Schemas ─────────────────────────────────────────────────────────────

class TeamCreate(BaseModel):
    name: str = Field(..., min_length=2, max_length=200)
    description: Optional[str] = None
    color: Optional[str] = "#6366f1"

class TeamMemberInfo(BaseModel):
    id: int
    name: str
    email: str
    role: str
    avatar_color: str

    class Config:
        from_attributes = True

class TeamResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]
    color: str
    created_at: datetime
    member_count: Optional[int] = 0

    class Config:
        from_attributes = True

class TeamDetail(TeamResponse):
    members: List[TeamMemberInfo] = []

# ─── Analytics Schemas ────────────────────────────────────────────────────────

class UserAnalytics(BaseModel):
    user: UserBase
    total_assigned: int
    completed: int
    in_progress: int
    overdue: int
    on_time_rate: float
    ai_rating: Optional[float] = None
    ai_summary: Optional[str] = None
    projects: List[dict] = []

class WorkforceOverview(BaseModel):
    total_users: int
    assigned_users: int
    unassigned_users: int
    users: List[dict] = []
