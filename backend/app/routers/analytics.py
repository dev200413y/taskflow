from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, Task, Project, ProjectMember
from app.schemas.schemas import UserAnalytics, WorkforceOverview, UserBase
from mistralai.client.sdk import Mistral
from app.core.config import settings
import json

router = APIRouter(prefix="/analytics", tags=["Analytics"])
client = Mistral(api_key=settings.MISTRAL_API_KEY)


def compute_user_stats(user_id: int, db: Session):
    now = datetime.utcnow()
    tasks = db.query(Task).filter(Task.assignee_id == user_id).all()

    completed = [t for t in tasks if t.status == "done"]
    in_progress = [t for t in tasks if t.status in ("in_progress", "in_review")]
    overdue = []
    for t in tasks:
        if t.status != "done" and t.due_date:
            due = t.due_date.replace(tzinfo=None) if t.due_date.tzinfo else t.due_date
            if due < now:
                overdue.append(t)

    on_time_rate = round((len(completed) / len(tasks) * 100) if tasks else 0, 1)

    # Projects the user is part of
    memberships = db.query(ProjectMember).filter(ProjectMember.user_id == user_id).all()
    projects = []
    for pm in memberships:
        p = db.query(Project).filter(Project.id == pm.project_id, Project.is_active == True).first()
        if p:
            proj_tasks = db.query(Task).filter(Task.project_id == p.id, Task.assignee_id == user_id).count()
            projects.append({"id": p.id, "name": p.name, "color": p.color, "task_count": proj_tasks})

    return {
        "total_assigned": len(tasks),
        "completed": len(completed),
        "in_progress": len(in_progress),
        "overdue": len(overdue),
        "on_time_rate": on_time_rate,
        "projects": projects
    }


def get_ai_rating(user_name: str, stats: dict) -> tuple:
    """Use Mistral to generate a performance rating and summary."""
    try:
        prompt = f"""You are evaluating a team member's performance for a project manager.

User: {user_name}
Stats:
- Total tasks assigned: {stats['total_assigned']}
- Completed tasks: {stats['completed']}
- In progress: {stats['in_progress']}
- Overdue tasks: {stats['overdue']}
- On-time completion rate: {stats['on_time_rate']}%
- Projects involved in: {len(stats['projects'])}

Give a performance rating from 0.0 to 10.0 and a 1-2 sentence summary. Respond ONLY with JSON like:
{{"rating": 7.5, "summary": "Your summary here."}}"""

        response = client.chat.complete(
            model="mistral-large-latest",
            messages=[{"role": "user", "content": prompt}]
        )
        content = response.choices[0].message.content.strip()
        # Extract JSON from response
        start = content.find("{")
        end = content.rfind("}") + 1
        data = json.loads(content[start:end])
        return round(float(data.get("rating", 5.0)), 1), data.get("summary", "")
    except Exception as e:
        print("AI rating error:", e)
        return None, None


@router.get("/user/{user_id}", response_model=UserAnalytics)
def get_user_analytics(user_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    # Admins see everyone; members can only see their own profile
    if current_user.role != "admin" and current_user.id != user_id:
        raise HTTPException(status_code=403, detail="Access denied")

    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    stats = compute_user_stats(user_id, db)
    ai_rating, ai_summary = get_ai_rating(user.name, stats)

    return UserAnalytics(
        user=UserBase(
            id=user.id, name=user.name, email=user.email,
            role=user.role, avatar_color=user.avatar_color,
            is_active=user.is_active, created_at=user.created_at
        ),
        **stats,
        ai_rating=ai_rating,
        ai_summary=ai_summary
    )


@router.get("/overview", response_model=WorkforceOverview)
def get_workforce_overview(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin only")

    all_users = db.query(User).filter(User.is_active == True).all()
    users_data = []
    assigned_count = 0

    for u in all_users:
        task_count = db.query(Task).filter(Task.assignee_id == u.id).count()
        completed = db.query(Task).filter(Task.assignee_id == u.id, Task.status == "done").count()
        if task_count > 0:
            assigned_count += 1
        users_data.append({
            "id": u.id,
            "name": u.name,
            "email": u.email,
            "role": u.role,
            "avatar_color": u.avatar_color,
            "task_count": task_count,
            "completed": completed,
            "has_tasks": task_count > 0
        })

    return WorkforceOverview(
        total_users=len(all_users),
        assigned_users=assigned_count,
        unassigned_users=len(all_users) - assigned_count,
        users=users_data
    )
