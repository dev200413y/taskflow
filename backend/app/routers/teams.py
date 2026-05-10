from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from typing import List
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import Team, TeamMember, User, ActivityLog
from app.schemas.schemas import (
    TeamCreate, TeamResponse, TeamDetail, TeamMemberInfo, MessageResponse, AddMemberRequest
)

router = APIRouter(prefix="/teams", tags=["Teams"])


def log_activity(db, action, entity_type, entity_id, entity_name, user_id):
    log = ActivityLog(action=action, entity_type=entity_type,
                      entity_id=entity_id, entity_name=entity_name, user_id=user_id)
    db.add(log)


@router.post("", response_model=TeamResponse, status_code=status.HTTP_201_CREATED)
def create_team(payload: TeamCreate, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can create teams")

    existing = db.query(Team).filter(Team.name == payload.name).first()
    if existing:
        raise HTTPException(status_code=400, detail="Team name already exists")

    team = Team(name=payload.name, description=payload.description, color=payload.color or "#6366f1")
    db.add(team)
    db.commit()
    db.refresh(team)

    log_activity(db, "created", "team", team.id, team.name, current_user.id)
    db.commit()

    team.member_count = 0
    return team


@router.get("", response_model=List[TeamResponse])
def list_teams(db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role == "admin":
        teams = db.query(Team).all()
    else:
        my_team_ids = [tm.team_id for tm in current_user.team_memberships]
        teams = db.query(Team).filter(Team.id.in_(my_team_ids)).all()

    result = []
    for t in teams:
        t.member_count = len(t.members)
        result.append(t)
    return result


@router.get("/{team_id}", response_model=TeamDetail)
def get_team(team_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    # Members can only view their own teams
    if current_user.role != "admin":
        my_team_ids = [tm.team_id for tm in current_user.team_memberships]
        if team_id not in my_team_ids:
            raise HTTPException(status_code=403, detail="Access denied")

    members = []
    for tm in team.members:
        u = db.query(User).filter(User.id == tm.user_id).first()
        if u:
            members.append(TeamMemberInfo(id=u.id, name=u.name, email=u.email,
                                          role=u.role, avatar_color=u.avatar_color))

    return {
        "id": team.id,
        "name": team.name,
        "description": team.description,
        "color": team.color,
        "created_at": team.created_at,
        "member_count": len(members),
        "members": members
    }


@router.post("/{team_id}/members", response_model=MessageResponse)
def add_member(team_id: int, payload: AddMemberRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can add members to teams")

    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    user = db.query(User).filter(User.id == payload.user_id, User.is_active == True).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    existing = db.query(TeamMember).filter(
        TeamMember.team_id == team_id, TeamMember.user_id == payload.user_id
    ).first()
    if existing:
        raise HTTPException(status_code=400, detail="User is already in this team")

    membership = TeamMember(team_id=team_id, user_id=payload.user_id)
    db.add(membership)
    log_activity(db, "added_member", "team", team.id, f"{user.name} → {team.name}", current_user.id)
    db.commit()
    return {"message": f"{user.name} added to {team.name}"}


@router.delete("/{team_id}/members/{user_id}", response_model=MessageResponse)
def remove_member(team_id: int, user_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can remove members")

    membership = db.query(TeamMember).filter(
        TeamMember.team_id == team_id, TeamMember.user_id == user_id
    ).first()
    if not membership:
        raise HTTPException(status_code=404, detail="Member not found in team")

    db.delete(membership)
    db.commit()
    return {"message": "Member removed from team"}


@router.delete("/{team_id}", response_model=MessageResponse)
def delete_team(team_id: int, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Only admins can delete teams")

    team = db.query(Team).filter(Team.id == team_id).first()
    if not team:
        raise HTTPException(status_code=404, detail="Team not found")

    db.delete(team)
    db.commit()
    return {"message": "Team deleted"}
