from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import Task, Project, ProjectMember, ActivityLog, User
from app.schemas.schemas import DashboardStats, ActivityLogResponse

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])

@router.get("/stats", response_model=DashboardStats)
def get_stats(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    now = datetime.utcnow()

    if current_user.role == "admin":
        all_tasks = db.query(Task).all()
        total_projects = db.query(Project).filter(Project.is_active == True).count()
    else:
        member_project_ids = db.query(ProjectMember.project_id).filter(
            ProjectMember.user_id == current_user.id
        ).subquery()
        all_tasks = db.query(Task).filter(Task.project_id.in_(member_project_ids)).all()
        total_projects = db.query(Project).filter(
            Project.is_active == True,
            Project.id.in_(member_project_ids)
        ).count()

    todo = sum(1 for t in all_tasks if t.status == "todo")
    in_progress = sum(1 for t in all_tasks if t.status == "in_progress")
    in_review = sum(1 for t in all_tasks if t.status == "in_review")
    done = sum(1 for t in all_tasks if t.status == "done")
    overdue = sum(
        1 for t in all_tasks
        if t.due_date and t.status != "done" and
        (t.due_date.replace(tzinfo=None) if t.due_date.tzinfo else t.due_date) < now
    )
    my_tasks = sum(1 for t in all_tasks if t.assignee_id == current_user.id)

    return DashboardStats(
        total_tasks=len(all_tasks),
        todo=todo,
        in_progress=in_progress,
        in_review=in_review,
        done=done,
        overdue=overdue,
        total_projects=total_projects,
        my_tasks=my_tasks
    )

@router.get("/activity", response_model=list[ActivityLogResponse])
def get_activity(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role == "admin":
        logs = db.query(ActivityLog).order_by(ActivityLog.created_at.desc()).limit(20).all()
    else:
        logs = db.query(ActivityLog).filter(ActivityLog.user_id == current_user.id).order_by(ActivityLog.created_at.desc()).limit(20).all()
    return logs

@router.get("/my-tasks")
def get_my_tasks(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    tasks = db.query(Task).filter(Task.assignee_id == current_user.id).order_by(Task.due_date.asc()).all()
    now = datetime.utcnow()
    result = []
    for t in tasks:
        is_overdue = False
        if t.due_date and t.status != "done":
            due = t.due_date.replace(tzinfo=None) if t.due_date.tzinfo else t.due_date
            is_overdue = due < now
        result.append({
            "id": t.id, "title": t.title, "status": t.status,
            "priority": t.priority, "due_date": t.due_date,
            "project_id": t.project_id, "is_overdue": is_overdue
        })
    return result
