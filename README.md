# AiVentra Global Education

**Your AI-Powered Global Education Partner**

A complete full-stack web application for study abroad planning, university search, AI admission analysis, and application tracking.

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Next.js 15 (App Router), TypeScript, Tailwind CSS, ShadCN UI |
| Backend | FastAPI, Python, Pydantic, JWT Authentication |
| Database | MongoDB Atlas |
| State | React Context API |
| Forms | React Hook Form + Zod Validation |
| HTTP | Axios |

## Project Structure

```
Ai-Ventra Global Eduction/
├── frontend/          # Next.js application
│   ├── src/
│   │   ├── app/       # Pages (App Router)
│   │   ├── components/# Reusable UI components
│   │   ├── context/   # Auth context
│   │   └── lib/       # API client, types, utils
│   └── package.json
├── backend/           # FastAPI application
│   ├── app/
│   │   ├── routers/   # API route handlers
│   │   ├── schemas/   # Pydantic models
│   │   ├── middleware/# Auth middleware
│   │   └── utils/     # Security, helpers
│   └── requirements.txt
└── README.md
```

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.11+
- MongoDB Atlas account (or local MongoDB)

### Backend Setup

```bash
cd backend

# Create virtual environment
python -m venv venv
venv\Scripts\activate        # Windows
# source venv/bin/activate   # macOS/Linux

# Install dependencies
pip install -r requirements.txt

# Configure environment
copy .env.example .env       # Windows
# cp .env.example .env       # macOS/Linux
# Edit .env with your MongoDB URL and JWT secrets

# Seed database (creates admin user + sample universities)
python -m app.seed

# Start server
uvicorn app.main:app --reload --port 8000
```

API docs available at: http://localhost:8000/docs

### Frontend Setup

```bash
cd frontend

# Install dependencies
npm install

# Configure environment
copy .env.example .env.local  # Windows
# cp .env.example .env.local    # macOS/Linux

# Start development server
npm run dev
```

App available at: http://localhost:3000

## Default Credentials

| Role | Email | Password | Login URL |
|------|-------|----------|-----------|
| Admin | admin@aiventra.com | Admin@123 | /secure/admin/login |
| Student | Register at /register | — | /login |
| Employee | Created by Admin | — | /portal/employee/login |

## User Roles & Access

### Student (Public)
- Self-registration at `/register`
- Dashboard, Profile, University Search, Shortlist, AI Analysis, Roadmap, Applications, Documents, Settings

### Employee (Hidden)
- Created only by Admin
- Login: `/portal/employee/login`
- Assigned students, counselling notes, meeting management

### Admin (Hidden)
- Created manually in database
- Login: `/secure/admin/login`
- Student/employee management, analytics, subscriptions, settings

## API Endpoints

| Module | Base Path | Auth |
|--------|-----------|------|
| Auth | `/api/v1/auth` | Public |
| Profiles | `/api/v1/profiles` | Student |
| Universities | `/api/v1/universities` | All roles |
| Shortlists | `/api/v1/shortlists` | Student |
| Applications | `/api/v1/applications` | Student/Employee |
| Documents | `/api/v1/documents` | Student/Employee |
| Roadmaps | `/api/v1/roadmaps` | Student |
| AI Analysis | `/api/v1/analysis` | Student |
| Employee | `/api/v1/employee` | Employee |
| Admin | `/api/v1/admin` | Admin |
| Dashboard | `/api/v1/dashboard` | Student |

## Deployment

### Frontend (Vercel)

1. Push `frontend/` to GitHub
2. Import project in Vercel
3. Set environment variable: `NEXT_PUBLIC_API_URL=https://your-api.onrender.com/api/v1`
4. Deploy

### Backend (Render)

1. Push `backend/` to GitHub
2. Create Web Service on Render
3. Use `render.yaml` for configuration
4. Set environment variables from `.env.example`
5. Deploy

## Theme Colors

| Color | Hex | Usage |
|-------|-----|-------|
| Primary | #4A154B | Brand, sidebar |
| Secondary | #6D28D9 | Accents, buttons |
| Accent | #D4A017 | Highlights, gold |
| Background | #FAF9F7 | Page background |
| Cards | #FFFFFF | Card surfaces |
| Text | #1F2937 | Body text |

## License

Private — AiVentra Global Education
