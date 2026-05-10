from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session, joinedload
from typing import List
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import Project, ProjectMember, Task, ActivityLog, User
from app.schemas.schemas import (
    ProjectCreate, ProjectUpdate, ProjectResponse,
    ProjectDetail, MessageResponse, AddMemberRequest, ProjectMemberInfo
)

router = APIRouter(prefix="/projects", tags=["Projects"])

def log_activity(db, action, entity_type, entity_id, entity_name, user_id):
    log = ActivityLog(action=action, entity_type=entity_type,
                      entity_id=entity_id, entity_name=entity_name, user_id=user_id)
    db.add(log)

def get_project_or_404(project_id: int, db: Session):
    project = db.query(Project).filter(Project.id == project_id, Project.is_active == True).first()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project

def is_project_member(project_id: int, user_id: int, db: Session):
    return db.query(ProjectMember).filter(
        ProjectMember.project_id == project_id,
        ProjectMember.user_id == user_id
    ).first()

def can_access_project(project, user, db):
    if user.role == "admin":
        return True
    if project.owner_id == user.id:
        return True
    if is_project_member(project.id, user.id, db):
        return True
    return False

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(payload: ProjectCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role not in ["admin", "member"]:
        raise HTTPException(status_code=403, detail="Not authorized")

    project = Project(
        name=payload.name,
        description=payload.description,
        color=payload.color or "#6366f1",
        owner_id=current_user.id
    )
    db.add(project)
    db.flush()

    # Auto-add owner as member
    membership = ProjectMember(project_id=project.id, user_id=current_user.id)
    db.add(membership)
    db.commit()
    db.refresh(project)

    log_activity(db, "created", "project", project.id, project.name, current_user.id)
    db.commit()

    project.task_count = 0
    project.member_count = 1
    return project

@router.get("", response_model=List[ProjectResponse])
def list_projects(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role == "admin":
        projects = db.query(Project).filter(Project.is_active == True).all()
    else:
        # Get projects where user is member or owner
        member_project_ids = db.query(ProjectMember.project_id).filter(
            ProjectMember.user_id == current_user.id
        ).subquery()
        projects = db.query(Project).filter(
            Project.is_active == True,
            Project.id.in_(member_project_ids)
        ).all()

    result = []
    for p in projects:
        p.task_count = db.query(Task).filter(Task.project_id == p.id).count()
        p.member_count = db.query(ProjectMember).filter(ProjectMember.project_id == p.id).count()
        result.append(p)
    return result

@router.get("/{project_id}", response_model=ProjectDetail)
def get_project(project_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    project = get_project_or_404(project_id, db)
    if not can_access_project(project, current_user, db):
        raise HTTPException(status_code=403, detail="Access denied")

    project.task_count = db.query(Task).filter(Task.project_id == project.id).count()
    members_data = db.query(ProjectMember).filter(ProjectMember.project_id == project_id).all()
    project.member_count = len(members_data)

    members = []
    for pm in members_data:
        u = db.query(User).filter(User.id == pm.user_id).first()
        if u:
            members.append(ProjectMemberInfo(id=u.id, name=u.name, email=u.email,
                                              role=u.role, avatar_color=u.avatar_color))
    return {
        "id": project.id,
        "name": project.name,
        "description": project.description,
        "color": project.color,
        "owner_id": project.owner_id,
        "owner": project.owner,
        "is_active": project.is_active,
        "created_at": project.created_at,
        "task_count": project.task_count,
        "member_count": project.member_count,
        "members": members
    }

@router.patch("/{project_id}", response_model=ProjectResponse)
def update_project(project_id: int, payload: ProjectUpdate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    project = get_project_or_404(project_id, db)
    if current_user.role != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only admin or project owner can update")

    if payload.name: project.name = payload.name
    if payload.description is not None: project.description = payload.description
    if payload.color: project.color = payload.color

    db.commit()
    db.refresh(project)
    log_activity(db, "updated", "project", project.id, project.name, current_user.id)
    db.commit()

    project.task_count = db.query(Task).filter(Task.project_id == project.id).count()
    project.member_count = db.query(ProjectMember).filter(ProjectMember.project_id == project.id).count()
    return project

@router.delete("/{project_id}", response_model=MessageResponse)
def delete_project(project_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    project = get_project_or_404(project_id, db)
    if current_user.role != "admin" and project.owner_id != current_user.id:
        raise HTTPException(status_code=403, detail="Only admin or project owner can delete")

    project.is_active = False
    log_activity(db, "deleted", "project", project.id, project.name, current_user.id)
    db.commit()
    return {"message": "Project deleted successfully"}

@router.post("/{project_id}/members", response_model=MessageResponse)
def add_member(project_id: int, payload: AddMemberRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    project = get_project_or_404(project_id, db)
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can add members")

    user = db.query(User).filter(User.id == payload.user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = is_project_member(project_id, payload.user_id, db)
    if existing:
        raise HTTPException(status_code=400, detail="User is already a member")

    membership = ProjectMember(project_id=project_id, user_id=payload.user_id)
    db.add(membership)
    log_activity(db, "added_member", "project", project.id, f"{user.name} → {project.name}", current_user.id)
    db.commit()
    return {"message": f"{user.name} added to project"}

@router.delete("/{project_id}/members/{user_id}", response_model=MessageResponse)
def remove_member(project_id: int, user_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    project = get_project_or_404(project_id, db)
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admin can remove members")

    if user_id == project.owner_id:
        raise HTTPException(status_code=400, detail="Cannot remove project owner")

    membership = is_project_member(project_id, user_id, db)
    if not membership:
        raise HTTPException(status_code=404, detail="User is not a member")

    db.delete(membership)
    db.commit()
    return {"message": "Member removed successfully"}
