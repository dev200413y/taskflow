from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from datetime import datetime
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import Task, Project, ProjectMember, ActivityLog, User, Comment
from app.schemas.schemas import TaskCreate, TaskUpdate, TaskResponse, CommentCreate, CommentResponse, MessageResponse

router = APIRouter(prefix="/projects/{project_id}/tasks", tags=["Tasks"])

def log_activity(db, action, entity_type, entity_id, entity_name, user_id):
    log = ActivityLog(action=action, entity_type=entity_type,
                      entity_id=entity_id, entity_name=entity_name, user_id=user_id)
    db.add(log)

def get_project_and_check_access(project_id: int, user, db: Session):
    project = db.query(Project).filter(Project.id == project_id, Project.is_active == True).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if user.role == "admin":
        return project
    if project.owner_id == user.id:
        return project
    member = db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user.id
    ).first()
    if not member:
        raise HTTPException(status_code=403, detail="Access denied to this project")
    return project

def enrich_task(task):
    now = datetime.utcnow()
    if task.due_date and task.status != "done":
        due = task.due_date.replace(tzinfo=None) if task.due_date.tzinfo else task.due_date
        task.is_overdue = due < now
    else:
        task.is_overdue = False
    return task

@router.post("", response_model=TaskResponse, status_code=status.HTTP_201_CREATED)
def create_task(project_id: int, payload: TaskCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    get_project_and_check_access(project_id, current_user, db)

    if payload.assignee_id:
        if current_user.role != "admin":
            raise HTTPException(status_code=403, detail="Only admin can assign tasks to users")
        assignee = db.query(User).filter(User.id == payload.assignee_id, User.is_active == True).first()
        if not assignee:
            raise HTTPException(status_code=404, detail="Assignee not found")

    task = Task(
        title=payload.title,
        description=payload.description,
        status=payload.status,
        priority=payload.priority,
        project_id=project_id,
        assignee_id=payload.assignee_id,
        creator_id=current_user.id,
        due_date=payload.due_date
    )
    db.add(task)
    db.commit()
    db.refresh(task)

    log_activity(db, "created", "task", task.id, task.title, current_user.id)
    db.commit()
    return enrich_task(task)

@router.get("", response_model=List[TaskResponse])
def list_tasks(
    project_id: int,
    status: Optional[str] = Query(None),
    priority: Optional[str] = Query(None),
    assignee_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user)
):
    get_project_and_check_access(project_id, current_user, db)
    query = db.query(Task).filter(Task.project_id == project_id)

    if status:
        query = query.filter(Task.status == status)
    if priority:
        query = query.filter(Task.priority == priority)
    if assignee_id:
        query = query.filter(Task.assignee_id == assignee_id)

    tasks = query.order_by(Task.created_at.desc()).all()
    return [enrich_task(t) for t in tasks]

@router.get("/{task_id}", response_model=TaskResponse)
def get_task(project_id: int, task_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    get_project_and_check_access(project_id, current_user, db)
    task = db.query(Task).filter(Task.id == task_id, Task.project_id == project_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return enrich_task(task)

@router.patch("/{task_id}", response_model=TaskResponse)
def update_task(project_id: int, task_id: int, payload: TaskUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    get_project_and_check_access(project_id, current_user, db)
    task = db.query(Task).filter(Task.id == task_id, Task.project_id == project_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    if payload.title is not None: task.title = payload.title
    if payload.description is not None: task.description = payload.description
    if payload.status is not None: task.status = payload.status
    if payload.priority is not None: task.priority = payload.priority
    if payload.assignee_id is not None:
        if current_user.role != "admin" and task.assignee_id != payload.assignee_id:
            raise HTTPException(status_code=403, detail="Only admin can change task assignee")
        task.assignee_id = payload.assignee_id
    if payload.due_date is not None: task.due_date = payload.due_date

    db.commit()
    db.refresh(task)
    log_activity(db, "updated", "task", task.id, task.title, current_user.id)
    db.commit()
    return enrich_task(task)

@router.delete("/{task_id}", response_model=MessageResponse)
def delete_task(project_id: int, task_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    project = get_project_and_check_access(project_id, current_user, db)
    task = db.query(Task).filter(Task.id == task_id, Task.project_id == project_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Only admin, project owner, or task creator can delete
    if current_user.role != "admin" and project.owner_id != current_user.id and task.creator_id != current_user.id:
        raise HTTPException(status_code=403, detail="Not authorized to delete this task")

    log_activity(db, "deleted", "task", task.id, task.title, current_user.id)
    db.delete(task)
    db.commit()
    return {"message": "Task deleted successfully"}

# ─── Comments ─────────────────────────────────────────────────────────────────

@router.post("/{task_id}/comments", response_model=CommentResponse, status_code=201)
def add_comment(project_id: int, task_id: int, payload: CommentCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    get_project_and_check_access(project_id, current_user, db)
    task = db.query(Task).filter(Task.id == task_id, Task.project_id == project_id).first()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    comment = Comment(content=payload.content, task_id=task_id, author_id=current_user.id)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return comment

@router.get("/{task_id}/comments", response_model=List[CommentResponse])
def get_comments(project_id: int, task_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    get_project_and_check_access(project_id, current_user, db)
    return db.query(Comment).filter(Comment.task_id == task_id).order_by(Comment.created_at.asc()).all()
