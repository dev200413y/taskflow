import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import List
from datetime import datetime
from mistralai import Mistral
from app.core.config import settings
from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User, Task, Project

router = APIRouter(prefix="/ai", tags=["AI"])

client = Mistral(api_key=settings.MISTRAL_API_KEY)

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]

tools = [
    {
        "type": "function",
        "function": {
            "name": "get_db_stats",
            "description": "Get statistics about the database, including the number of users, projects, total tasks, uncompleted tasks, and a list of all users and their IDs. Call this whenever the user asks for stats, or when you need user IDs to assign tasks.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "assign_task",
            "description": "Assign a task to a user.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "integer",
                        "description": "The ID of the task to assign."
                    },
                    "user_id": {
                        "type": "integer",
                        "description": "The ID of the user to assign the task to."
                    }
                },
                "required": ["task_id", "user_id"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_urgent_tasks",
            "description": "Fetch a list of urgent or overdue tasks that need immediate attention.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    }
]

def get_db_stats(db: Session):
    user_count = db.query(User).count()
    project_count = db.query(Project).count()
    task_count = db.query(Task).count()
    uncompleted_tasks = db.query(Task).filter(Task.status != "done").count()
    
    users = db.query(User).all()
    user_list = ", ".join([f"{u.name} (ID: {u.id})" for u in users])
    
    # We also need tasks to help the AI map names to IDs
    tasks = db.query(Task).all()
    task_list = ", ".join([f"'{t.title}' (ID: {t.id})" for t in tasks])
    
    return json.dumps({
        "total_users": user_count,
        "total_projects": project_count,
        "total_tasks": task_count,
        "uncompleted_tasks": uncompleted_tasks,
        "users_list": user_list,
        "tasks_list": task_list
    })

def assign_task(db: Session, current_user: User, task_id: int, user_id: int):
    if current_user.role != "admin":
        return json.dumps({"error": "Only admins can assign tasks via AI. Please ask the user to contact an administrator."})
        
    task = db.query(Task).filter(Task.id == task_id).first()
    if not task:
        return json.dumps({"error": f"Task {task_id} not found."})
        
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return json.dumps({"error": f"User {user_id} not found."})
        
    task.assignee_id = user_id
    db.commit()
    return json.dumps({"success": f"Task '{task.title}' successfully assigned to user '{user.name}'."})

def get_urgent_tasks(db: Session, current_user: User):
    now = datetime.utcnow()
    query = db.query(Task).filter(Task.status != "done")
    
    if current_user.role != "admin":
        query = query.filter(Task.assignee_id == current_user.id)
        
    tasks = query.all()
    urgent_tasks = []
    
    for t in tasks:
        due = t.due_date.replace(tzinfo=None) if t.due_date and t.due_date.tzinfo else t.due_date
        is_overdue = due and due < now
        if t.priority == "urgent" or is_overdue:
            urgent_tasks.append({
                "id": t.id,
                "title": t.title,
                "priority": t.priority.value,
                "is_overdue": is_overdue,
                "assignee_id": t.assignee_id
            })
            
    if not urgent_tasks:
        return json.dumps({"message": "No urgent or overdue tasks right now. Great job!"})
        
    return json.dumps({"urgent_tasks": urgent_tasks})

@router.post("/chat")
def chat_with_ai(request: ChatRequest, db: Session = Depends(get_db), current_user=Depends(get_current_user)):
    messages = [{"role": m.role, "content": m.content} for m in request.messages]
    
    system_message = {
        "role": "system", 
        "content": "You are TaskManager AI, powered by Mistral. You help manage tasks and projects. When a user greets you or asks for an overview, ALWAYS proactively use 'get_urgent_tasks' to check for any urgent or overdue tasks and summarize them. Be helpful, concise, and professional."
    }
    messages.insert(0, system_message)
    
    try:
        response = client.chat.complete(
            model="mistral-large-latest",
            messages=messages,
            tools=tools,
            tool_choice="auto"
        )
        
        response_message = response.choices[0].message
        
        if response_message.tool_calls:
            # Mistral expects tool_calls to be dictionaries in the messages list
            # We dump the model to dict then convert it back carefully
            messages.append({
                "role": "assistant",
                "content": response_message.content or "",
                "tool_calls": [t.model_dump() for t in response_message.tool_calls]
            })
            
            for tool_call in response_message.tool_calls:
                function_name = tool_call.function.name
                
                # Check if arguments is a string or a dict. Some SDK versions parse it automatically.
                if isinstance(tool_call.function.arguments, str):
                    function_args = json.loads(tool_call.function.arguments)
                else:
                    function_args = tool_call.function.arguments
                
                if function_name == "get_db_stats":
                    function_response = get_db_stats(db)
                elif function_name == "assign_task":
                    function_response = assign_task(db, current_user, function_args.get("task_id"), function_args.get("user_id"))
                elif function_name == "get_urgent_tasks":
                    function_response = get_urgent_tasks(db, current_user)
                else:
                    function_response = json.dumps({"error": "Unknown function"})
                
                messages.append({
                    "role": "tool",
                    "name": function_name,
                    "content": function_response,
                    "tool_call_id": tool_call.id
                })
            
            final_response = client.chat.complete(
                model="mistral-large-latest",
                messages=messages
            )
            return {"role": "assistant", "content": final_response.choices[0].message.content}
        else:
            return {"role": "assistant", "content": response_message.content}
            
    except Exception as e:
        print("Mistral API Error:", e)
        raise HTTPException(status_code=500, detail=str(e))
