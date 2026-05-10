# TaskFlow - AI-Powered Team Task Manager

TaskFlow is a production-ready, full-stack application designed for seamless team collaboration, robust project management, and AI-driven analytics. It was built explicitly to fulfill the Ethara.AI assessment requirements.

## 🚀 Key Features

### 1. Robust Authentication & RBAC (Role-Based Access Control)
- **JWT-Based Authentication**: Secure login and registration with access/refresh token rotation.
- **Roles**: Users can register as an `admin` or a `member`.
- **Privacy & Isolation**: 
  - Admins have full global visibility across all users, projects, and teams.
  - Members are strictly sandboxed. They can only see users who are part of the same `Teams`, their own assigned tasks, and projects they are explicitly invited to.

### 2. Teams & Project Management
- **Teams**: Admins can create specialized Teams and assign employees to them. This controls visibility across the organization.
- **Projects & Kanban Board**: Create projects with custom colors. View tasks in a dynamic Kanban board or a list view.
- **Task Assignment**: Tasks feature priorities (Low to Urgent), deadlines, and assignees.

### 3. Analytics & Workforce Overview
- **Admin Dashboard**: A specialized "Workforce Overview" dashboard showing exactly how many tasks each employee is handling, highlighting any users who are completely idle.
- **Dynamic Charts**: The dashboard features real-time `Chart.js` visualizations of task distributions and overdue metrics.

### 4. 🤖 Mistral AI Integration
- **Proactive AI Assistant**: A persistent chat widget powered by Mistral AI that proactively checks for urgent or overdue tasks upon login and can answer queries.
- **AI Performance Reviews**: The system automatically compiles a user's task statistics (completion rate, overdue count, total load) and feeds them into Mistral AI to generate a dynamic 0-10 "Overall Performance Rating" and a managerial summary. This is visible on every user's Profile Page.

### 5. Premium UI/UX
- Responsive, single-page React frontend embedded directly into the browser.
- Polished Glassmorphism design elements with CSS variables.
- Persistent **Light/Dark Mode** theme toggle.

---

## 🛠️ Technology Stack

- **Backend**: Python FastAPI, SQLite (Relational DB), SQLAlchemy (ORM), Pydantic (Validation)
- **Frontend**: React (CDN), vanilla CSS, Chart.js
- **AI Integration**: Mistral AI Python SDK (`mistral-large-latest`)

---

## ⚙️ How to Run Locally

### 1. Prerequisites
Ensure you have Python 3.9+ installed.

### 2. Setup Environment
Navigate to the `backend` directory and create a virtual environment:
```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # On Windows use: .\.venv\Scripts\activate
```

Install the required dependencies:
```bash
pip install "fastapi[all]" sqlalchemy pydantic passlib python-jose python-multipart mistralai
```

### 3. Configure API Key
Create a `.env` file in the `backend` folder and add your Mistral API Key:
```env
MISTRAL_API_KEY=your_api_key_here
FRONTEND_URL=http://localhost:5173
```

### 4. Start the Servers
Start the FastAPI backend:
```bash
cd backend
uvicorn main:app --reload --port 8000
```

In a new terminal, start the frontend static server:
```bash
python -m http.server 5173
```

### 5. Access the App
Open your browser and navigate to: `http://localhost:5173/frontend`

---

## 🧪 Testing the Application

To fully test the Role-Based Access Control, follow these steps:
1. **Create an Admin**: Click "Sign Up", select the "Admin" role, and create an account.
2. **Create a Team**: Go to the "Teams" tab and create a new team.
3. **View AI Analytics**: Go to the "Analytics" tab, see the Workforce Overview, and click on your profile badge to see your AI-generated performance rating.
4. **Create a Member**: Log out, click "Sign Up", select the "Member" role, and create a second account. Notice how the Member cannot see the "Teams" or the Admin user until the Admin explicitly adds them to a shared Team.

## 🌐 Deployment
To deploy this application to a cloud platform like **Railway**, **Render**, or **Heroku**:

1. **Backend**:
   - Host the `backend` folder.
   - Set the following environment variables:
     - `DATABASE_URL`: Your production database URL (e.g., PostgreSQL).
     - `MISTRAL_API_KEY`: Your Mistral API Key.
     - `SECRET_KEY`: A long random string (e.g., `openssl rand -hex 32`).
     - `FRONTEND_URL`: The URL of your deployed frontend.

2. **Frontend**:
   - Host the `frontend` folder as a static site.
   - You can configure the backend API URL by setting `window.API_BASE_URL` in the `index.html`.

3. **Database**:
   - The app uses SQLAlchemy, so it will automatically create tables in your production database upon the first request if the connection string is valid.
