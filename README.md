# BOOMA — Roster Management Platform

A full-stack task roster and checklist management platform built with **FastAPI** and **Vue.js**. BOOMA enables administrators to create categories (projects/segments), add items (assets/inventory entries), define baseline task checklists, and assign categories to staff members — who can then track progress by marking tasks as completed.

---

## Table of Contents

- [Features](#features)
- [Tech Stack](#tech-stack)
- [Project Structure](#project-structure)
- [Prerequisites](#prerequisites)
- [Installation & Setup](#installation--setup)
- [Running the Application](#running-the-application)
- [Default Admin Account](#default-admin-account)
- [User Guide](#user-guide)
  - [Login & Registration](#1-login--registration)
  - [Dashboard](#2-dashboard)
  - [Roster Board (Main Page)](#3-roster-board-main-page)
  - [Managing Categories](#4-managing-categories)
  - [Adding Items](#5-adding-items)
  - [Task Checklists](#6-task-checklists)
  - [Assigning Users to Categories](#7-assigning-users-to-categories)
  - [Editing Your Profile](#8-editing-your-profile)
  - [Admin Panel](#9-admin-panel)
- [API Reference](#api-reference)
- [Database](#database)
- [Troubleshooting](#troubleshooting)

---

## Features

| Feature | Description |
|---------|-------------|
| **User Authentication** | JWT-based login & self-service registration with password validation |
| **Role-Based Access** | Admin and Standard User roles with fine-grained permissions |
| **Category Management** | Create project segments with date ranges, custom fields, and task templates |
| **Item Management** | Bulk-import items via CSV format with optional comments |
| **Task Checklists** | Baseline task templates auto-applied to items + custom per-item tasks |
| **User Assignment** | Assign multiple users to categories; users see only their assigned data |
| **Dashboard Analytics** | Charts, completion rates, category breakdown, and activity timeline |
| **Audit Logging** | Full activity trail of all create/update/delete/assignment actions |
| **Profile Management** | Users can edit their own name, phone, location, and email |
| **Dark Glassmorphism UI** | Modern, premium dark theme with blur effects and smooth animations |

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| **Backend** | Python 3.10+, FastAPI, SQLAlchemy 2.0, Pydantic v2 |
| **Frontend** | Vue.js 3 (CDN), Vanilla CSS (dark glassmorphism theme) |
| **Database** | SQLite (`event_roster.db`) |
| **Auth** | JWT tokens via `python-jose`, bcrypt password hashing |
| **Charts** | Chart.js (CDN) |
| **Server** | Uvicorn (ASGI) |

---

## Project Structure

```
anvetion-main/
├── app/
│   ├── __init__.py
│   └── main.py              # All backend logic: models, schemas, routes, migrations
├── static/
│   ├── login.html            # Login & registration page
│   ├── dashboard.html        # Dashboard with charts & analytics
│   ├── index.html            # Main roster board (categories, items, tasks)
│   ├── admin.html            # Admin panel (user & category management)
│   └── vue.global.prod.js    # Vue.js 3 production build (local CDN)
├── event_roster.db           # SQLite database (auto-created on first run)
├── requirements.txt          # Python dependencies
├── start.sh                  # Linux/Mac startup script
├── build.sh                  # Build script
├── update_admin.py           # Utility to reset admin password
└── README.md                 # This file
```

---

## Prerequisites

- **Python 3.10** or newer
- **pip** (Python package manager)

---

## Installation & Setup

### 1. Clone the repository

```bash
git clone <repository-url>
cd anvetion-main
```

### 2. Create a virtual environment (recommended)

**Windows:**
```bash
python -m venv venv
venv\Scripts\activate
```

**macOS / Linux:**
```bash
python3 -m venv venv
source venv/bin/activate
```

### 3. Install dependencies

```bash
pip install -r requirements.txt
pip install python-jose[cryptography] passlib[bcrypt]
```

> **Note:** `python-jose` and `passlib` are required for JWT authentication and password hashing but may not be listed in `requirements.txt`. Install them explicitly.

---

## Running the Application

### Windows

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8001 --reload
```

### macOS / Linux

```bash
bash start.sh
```

Then open your browser to: **http://127.0.0.1:8001**

The application will automatically:
- Create the SQLite database file (`event_roster.db`) if it doesn't exist
- Run schema migrations to add any missing tables or columns
- Seed a default admin account if no admin user exists

---

## Default Admin Account

On first startup, if no admin user exists, one is created automatically:

| Field | Value |
|-------|-------|
| **Email** | `admin@booma.com` |
| **Password** | `Admin@123` |

> ⚠️ **Change the default password immediately** after first login via the **Edit Profile** option or by running `update_admin.py`.

### Resetting Admin Password

If you need to reset the admin password manually:

```bash
python -c "
from app.main import SessionLocal, User, hash_password
from sqlalchemy import select
db = SessionLocal()
admin = db.scalar(select(User).where(User.role == 'admin'))
if admin:
    admin.password = hash_password('YourNewPassword1!')
    db.commit()
    print(f'Password reset for {admin.email}')
else:
    print('No admin user found')
db.close()
"
```

> **Password requirements:** Minimum 6 characters, must contain uppercase, lowercase, number, and special character (e.g. `@$!%*?&`).

---

## User Guide

### 1. Login & Registration

- **URL:** `http://127.0.0.1:8001/login`
- **Login:** Enter your email and password, then click **Sign In**.
- **Register:** Click **Sign up now** to create a new account with your name, phone (10 digits), location, email, and password.
- After login:
  - **Admin users** are redirected to the **Dashboard** (`/dashboard`).
  - **Standard users** are redirected to the **Roster Board** (`/`).

---

### 2. Dashboard

- **URL:** `http://127.0.0.1:8001/dashboard`
- Displays analytics tailored to your role:

| Admin View | User View |
|-----------|-----------|
| Total Users, Categories, Tasks | My Categories, My Items, My Tasks |
| Global Completion Rate | My Completion Rate |
| Tasks per Category (bar chart) | Personal category breakdown |
| Recent Activity Log (all users) | My Recent Activities |

- Click **Refresh Data** to reload live statistics.

---

### 3. Roster Board (Main Page)

- **URL:** `http://127.0.0.1:8001/`
- The main workspace for managing categories, items, and tasks.

**Layout:**
- **Left Sidebar:** Your profile card, categories list, and admin actions.
- **Center Panel:** Items table for the selected category.
- **Right Panel:** Task checklist for the selected item.

---

### 4. Managing Categories

> 🔒 *Admin only*

1. In the sidebar, click **+ New Category**.
2. Fill in:
   - **Category Name** — e.g. "Solar Panels Check"
   - **Description** — brief summary
   - **Start Date / End Date** — operational date range
   - **Required Custom Fields** — define schema fields (one per line, format: `fieldName,fieldType`)
     - Supported types: `text`, `number`, `date`
     - Example: `status,text`
   - **Baseline Tasks** *(optional)* — pre-defined checklist items (one per line, format: `TaskTitle,TaskDescription`)
     - Example: `Check wiring,Inspect all electrical connections`
3. Click **Create Category**.

**Editing:** Click the ✏️ (edit) button next to the category name in the top bar.

**Deleting:** Click the 🗑️ (delete) button. This removes all items and tasks under the category.

---

### 5. Adding Items

> 🔒 *Admin only*

Items represent the individual entities within a category (e.g., equipment, assets, inventory entries).

#### Step-by-step:

1. **Select a category** from the sidebar.
2. Click the **+ Add New Items** button.
3. In the modal that opens, follow the guided steps:

   **Step 1:** Type each item on a **new line** in the text box.

   **Step 2:** Optionally add a **comma followed by a comment** after the item name.

   **Step 3:** Click **Import Items** to add them all at once.

#### Format:

```
ItemName
ItemName,Optional Comment
```

#### Example:

```
Generator A,Check battery life
AC Unit 2,Needs filter change
Solar Panel B3
Transformer T1,Annual inspection due
```

- The modal shows a **live item counter** so you know how many items will be imported.
- All baseline tasks from the category template are automatically applied to each new item.
- Custom fields defined in the category schema are auto-initialized with default values.

**Editing an item:** Click on the item row, then click the ✏️ edit button to update its name or custom field values.

**Deleting an item:** Click the 🗑️ delete button next to the item row.

---

### 6. Task Checklists

Each item has a task checklist composed of:

- **Baseline Tasks** — auto-created from the category template (tagged as "Baseline")
- **Custom Tasks** — added manually per item (tagged as "Custom")

#### Marking tasks complete:

1. Select an item from the items table.
2. In the right panel, check/uncheck the checkbox next to each task.
3. Tasks are saved immediately via the API.

#### Adding a custom task:

1. Type a task name in the **"Add a task checklist item..."** field.
2. Click **Add Task**.

#### Deleting a task:

> 🔒 *Admin only*

1. Click on a task to select it.
2. Click **Delete Selected**.

---

### 7. Assigning Users to Categories

> 🔒 *Admin only*

Assignments control which categories (and their items/tasks) are visible to standard users.

1. Select a category from the sidebar.
2. Click **Manage Assignments** in the top bar.
3. In the modal, check/uncheck staff members.
4. Click **Save Assignments**.

**Result:** Assigned users will immediately see the category on their Roster Board and Dashboard, including all items and tasks under it.

To **unassign** a user: Simply uncheck them in the assignment modal and save.

---

### 8. Editing Your Profile

Available to **all users** (admin and standard).

1. In the sidebar, click **Edit Profile**.
2. A modal opens with your current details:
   - Full Name
   - Phone Number
   - Location
   - Email Address
3. Make your changes and click **Save Changes**.

---

### 9. Admin Panel

- **URL:** `http://127.0.0.1:8001/admin`
- Provides bulk management tools for users and categories.
- Accessible only by admin users.

---

## API Reference

All API endpoints are prefixed with `/api`. Authentication is via `Authorization: Bearer <token>` header.

### Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/register` | Register a new user |
| `POST` | `/api/login` | Login and receive JWT token |
| `GET` | `/api/me` | Get current user profile |
| `PUT` | `/api/me` | Update current user profile |

### Users (Admin only)

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/users` | List all users |
| `DELETE` | `/api/users/{id}` | Delete a user |

### Categories

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/categories` | List categories (filtered by assignment for users) |
| `POST` | `/api/categories` | Create category (admin) |
| `PUT` | `/api/categories/{id}` | Update category (admin) |
| `DELETE` | `/api/categories/{id}` | Delete category and cascade (admin) |

### Category Assignments

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/categories/{id}/assigned-users` | List assigned users |
| `POST` | `/api/categories/{id}/assign` | Assign users to category (admin) |
| `DELETE` | `/api/categories/{id}/assign/{user_id}` | Remove single assignment (admin) |
| `GET` | `/api/users/{id}/assignments` | Get categories assigned to a user (admin) |

### Items

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/items?category_id={id}` | List items (filtered by category) |
| `GET` | `/api/items/{id}` | Get single item |
| `POST` | `/api/items` | Create item (admin) |
| `PUT` | `/api/items/{id}` | Update item (admin or assigned user) |
| `DELETE` | `/api/items/{id}` | Delete item (admin) |

### Tasks

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/items/{id}/tasks` | List tasks for an item |
| `POST` | `/api/items/{id}/tasks` | Create custom task (admin) |
| `PUT` | `/api/tasks/{id}` | Update task details (admin) |
| `PATCH` | `/api/tasks/{id}` | Update task status (any assigned user) |
| `PUT` | `/api/tasks/{id}/toggle` | Toggle task completion (any assigned user) |
| `DELETE` | `/api/tasks/{id}` | Delete task (admin) |

### Category Task Templates

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/categories/{id}/tasks` | List baseline task templates |
| `POST` | `/api/categories/{id}/tasks` | Add baseline task template (admin) |

### Dashboard & Audit

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/dashboard` | Dashboard analytics (role-aware) |
| `GET` | `/api/audit-logs` | Audit log entries |
| `GET` | `/api/categories/{id}/progress` | Daily progress data for a category |

---

## Database

BOOMA uses **SQLite** with the database file `event_roster.db` stored in the project root.

### Tables

| Table | Purpose |
|-------|---------|
| `users` | User accounts (name, email, password hash, role) |
| `categories` | Project segments with date ranges and custom field schemas |
| `category_assignments` | Many-to-many junction: which users are assigned to which categories |
| `category_tasks` | Baseline task templates per category |
| `items` | Individual entries under a category (with custom data JSON) |
| `item_tasks` | Per-item task checklist (baseline + custom tasks) |
| `audit_logs` | Activity trail of all system actions |

### Automatic Migrations

On every startup, `migrate_database()` runs and automatically adds any missing tables or columns. No manual migration steps are needed.

---

## Troubleshooting

### Port already in use

```
ERROR: [Errno 10048] error while attempting to bind on address ('127.0.0.1', 8001)
```

**Fix:** Kill the existing process or use a different port:

```bash
python -m uvicorn app.main:app --host 127.0.0.1 --port 8002 --reload
```

### Module not found errors

```
ModuleNotFoundError: No module named 'jose'
```

**Fix:** Install missing dependencies:

```bash
pip install python-jose[cryptography] passlib[bcrypt]
```

### Database locked

This can happen if multiple processes access the SQLite file simultaneously.

**Fix:** Ensure only one server instance is running. Kill any stale Python processes.

### Password validation errors during registration

Passwords must satisfy all of these rules:
- Minimum 6 characters
- At least one uppercase letter (`A-Z`)
- At least one lowercase letter (`a-z`)
- At least one digit (`0-9`)
- At least one special character (`@$!%*?&`)

**Example valid password:** `Admin@123`

---

## License

This project is proprietary. All rights reserved.
