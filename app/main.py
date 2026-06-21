from __future__ import annotations
import os, re
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any, Literal

from fastapi import Body, Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from jose import JWTError, jwt
from passlib.context import CryptContext
from pydantic import BaseModel, Field, field_validator, model_validator
from sqlalchemy import (Boolean, DateTime, ForeignKey, Integer, String,
    case, create_engine, func, select, text)
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import (DeclarativeBase, Mapped, Session,
    mapped_column, relationship, sessionmaker)
from sqlalchemy.types import JSON

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_URL = f"sqlite:///{BASE_DIR / 'event_roster.db'}"
BASE_PATH = os.environ.get("BASE_PATH", "").strip().rstrip("/")
BASE_PATH = "" if BASE_PATH in {"", "/"} else (BASE_PATH if BASE_PATH.startswith("/") else f"/{BASE_PATH}")

engine = create_engine(DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

SECRET_KEY = "booma-secret-key-2024"
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 120


def hash_password(p: str) -> str:
    return pwd_context.hash(p.strip()[:72])

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain.strip()[:72], hashed)

def create_access_token(data: dict) -> str:
    d = data.copy()
    d["exp"] = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode(d, SECRET_KEY, algorithm=ALGORITHM)

def parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    return datetime.strptime(value, "%Y-%m-%d").date()


class Base(DeclarativeBase):
    pass

class User(Base):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    phone: Mapped[str] = mapped_column(String, nullable=False)
    location: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    password: Mapped[str] = mapped_column(String, nullable=False)
    role: Mapped[str] = mapped_column(String, default="user")
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

class CategoryAssignment(Base):
    __tablename__ = "category_assignments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"))
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assigned_by: Mapped[int] = mapped_column(ForeignKey("users.id"))
    assigned_on: Mapped[datetime | None] = mapped_column(DateTime, default=datetime.utcnow)

class Category(Base):
    __tablename__ = "categories"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, unique=True, index=True, nullable=False)
    description: Mapped[str] = mapped_column(String, default="", nullable=False)
    start_date: Mapped[str | None] = mapped_column(String, nullable=True)
    end_date: Mapped[str | None] = mapped_column(String, nullable=True)
    required_fields_schema: Mapped[list[dict[str, Any]]] = mapped_column(JSON, default=list, nullable=False)
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    tasks: Mapped[list["CategoryTask"]] = relationship(back_populates="category", cascade="all, delete-orphan")
    items: Mapped[list["Item"]] = relationship(back_populates="category", cascade="all, delete-orphan")

class CategoryTask(Base):
    __tablename__ = "category_tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, default="", nullable=False)
    category: Mapped[Category] = relationship(back_populates="tasks")

class Item(Base):
    __tablename__ = "items"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    custom_data: Mapped[dict[str, Any]] = mapped_column(JSON, default=dict, nullable=False)
    created_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    category: Mapped[Category] = relationship(back_populates="items")
    tasks: Mapped[list["ItemTask"]] = relationship(back_populates="item", cascade="all, delete-orphan")

class ItemTask(Base):
    __tablename__ = "item_tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    item_id: Mapped[int] = mapped_column(ForeignKey("items.id"), nullable=False)
    title: Mapped[str] = mapped_column(String, nullable=False)
    description: Mapped[str] = mapped_column(String, default="", nullable=True)
    priority: Mapped[str] = mapped_column(String, default="normal", nullable=True)
    due_date: Mapped[str | None] = mapped_column(String, nullable=True)
    is_completed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_custom: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    completed_on: Mapped[str | None] = mapped_column(String, nullable=True)
    remarks: Mapped[str] = mapped_column(String, default="", nullable=True)
    updated_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    updated_by: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
    item: Mapped[Item] = relationship(back_populates="tasks")

class AuditLog(Base):
    __tablename__ = "audit_logs"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"))
    action: Mapped[str] = mapped_column(String)
    entity_type: Mapped[str | None] = mapped_column(String, nullable=True)
    entity_id: Mapped[int | None] = mapped_column(Integer, nullable=True)
    details: Mapped[str | None] = mapped_column(String, nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)


FieldType = Literal["text", "number", "date", "string"]

class UserRegister(BaseModel):
    name: str
    phone: str
    location: str
    email: str
    password: str = Field(min_length=6, max_length=72)

    @field_validator("email")
    @classmethod
    def val_email(cls, v: str) -> str:
        if "@" not in v or "." not in v:
            raise ValueError("Invalid email")
        return v.lower()

    @field_validator("phone")
    @classmethod
    def val_phone(cls, v: str) -> str:
        if not re.fullmatch(r"\d{10}", v):
            raise ValueError("Phone must be 10 digits")
        return v

    @field_validator("password")
    @classmethod
    def val_password(cls, v: str) -> str:
        if not re.fullmatch(r"^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&]).{6,}$", v):
            raise ValueError("Password must have uppercase, lowercase, number, special symbol")
        return v

class UserLogin(BaseModel):
    email: str
    password: str

class UserOut(BaseModel):
    id: int
    name: str
    email: str
    phone: str
    location: str
    role: str
    model_config = {"from_attributes": True}

class UserUpdate(BaseModel):
    name: str
    email: str
    phone: str
    location: str

class RequiredField(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    type: FieldType = "text"

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Field name required")
        return v

    @field_validator("type")
    @classmethod
    def norm_type(cls, v: str) -> str:
        return "text" if v == "string" else v

class CategoryTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = ""

    @field_validator("title", "description")
    @classmethod
    def strip_str(cls, v: str) -> str:
        return v.strip()

class CategoryCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    start_date: str | None = None
    end_date: str | None = None
    required_fields_schema: list[RequiredField] = Field(default_factory=list)
    tasks: list[CategoryTaskCreate] = Field(default_factory=list)

    @field_validator("name", "description")
    @classmethod
    def strip_str(cls, v: str) -> str:
        return v.strip()

    @field_validator("start_date", "end_date")
    @classmethod
    def val_date(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError("Date must be YYYY-MM-DD") from e
        return v

    @model_validator(mode="after")
    def val_range(self):
        s = parse_iso_date(self.start_date)
        e = parse_iso_date(self.end_date)
        if s and e and e < s:
            raise ValueError("End date before start date")
        return self

class CategoryUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    description: str = ""
    start_date: str | None = None
    end_date: str | None = None
    required_fields_schema: list[RequiredField] = Field(default_factory=list)

    @field_validator("name", "description")
    @classmethod
    def strip_str(cls, v: str) -> str:
        return v.strip()

    @field_validator("start_date", "end_date")
    @classmethod
    def val_date(cls, v: str | None) -> str | None:
        if v in (None, ""):
            return None
        try:
            datetime.strptime(v, "%Y-%m-%d")
        except ValueError as e:
            raise ValueError("Date must be YYYY-MM-DD") from e
        return v

    @model_validator(mode="after")
    def val_range(self):
        s = parse_iso_date(self.start_date)
        e = parse_iso_date(self.end_date)
        if s and e and e < s:
            raise ValueError("End date before start date")
        return self

class CategoryTaskOut(BaseModel):
    id: int
    category_id: int
    title: str
    description: str
    model_config = {"from_attributes": True}

class CategoryOut(BaseModel):
    id: int
    name: str
    description: str
    start_date: str | None
    end_date: str | None
    required_fields_schema: list[RequiredField]
    tasks: list[CategoryTaskOut] = []
    model_config = {"from_attributes": True}

class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    category_id: int
    custom_data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("Name required")
        return v

class ItemUpdate(BaseModel):
    name: str = Field(min_length=1, max_length=120)
    custom_data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("name")
    @classmethod
    def strip_name(cls, v: str) -> str:
        return v.strip()

class ItemOut(BaseModel):
    id: int
    name: str
    category_id: int
    category_name: str
    custom_data: dict[str, Any]
    created_at: str | None = None
    updated_at: str | None = None

class ItemTaskCreate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = ""
    priority: str = "normal"
    due_date: str | None = None

    @field_validator("title", "description")
    @classmethod
    def strip_str(cls, v: str) -> str:
        return v.strip()

class ItemTaskUpdate(BaseModel):
    title: str = Field(min_length=1, max_length=160)
    description: str = ""
    priority: str = "normal"
    due_date: str | None = None

class ItemTaskUserUpdate(BaseModel):
    is_completed: bool
    remarks: str = ""

class ItemTaskOut(BaseModel):
    id: int
    item_id: int
    title: str
    description: str | None
    priority: str | None
    due_date: str | None
    is_completed: bool
    is_custom: bool
    completed_on: str | None
    remarks: str | None
    updated_at: str | None = None
    model_config = {"from_attributes": True}

class CategoryAssignRequest(BaseModel):
    user_ids: list[int]

class UserAssignRequest(BaseModel):
    category_ids: list[int]

class CategoryProgressOut(BaseModel):
    date: str
    label: str
    pending_tasks: int
    completed_to_date: int
    total_tasks: int


# ── App Setup ───────────────────────────────────────────────────────────────────

app = FastAPI(title="BOOMA")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Not authenticated")
    token = auth.split(" ", 1)[1]
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id = payload.get("user_id")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token")
    except JWTError:
        raise HTTPException(status_code=401, detail="Invalid token")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return user


def require_admin(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status_code=403, detail="Admin access required")
    return current_user


def log_action(db: Session, user: User, action: str,
               entity_type: str | None = None,
               entity_id: int | None = None,
               details: str | None = None) -> None:
    db.add(AuditLog(
        user_id=user.id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        details=details,
        timestamp=datetime.utcnow(),
    ))


# ── DB Helpers ──────────────────────────────────────────────────────────────────

def ensure_category(db: Session, cid: int) -> Category:
    c = db.get(Category, cid)
    if not c:
        raise HTTPException(status_code=404, detail="Category not found")
    return c


def ensure_item(db: Session, iid: int) -> Item:
    item = db.get(Item, iid)
    if not item:
        raise HTTPException(status_code=404, detail="Item not found")
    return item


def ensure_task(db: Session, tid: int) -> ItemTask:
    task = db.get(ItemTask, tid)
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")
    return task


def validate_custom_data(category: Category, custom_data: dict) -> dict:
    """Validate and clean custom data against the category's required fields schema.
    Missing fields are defaulted to empty values rather than rejected, so items
    can be created via CSV import and filled in later."""
    cleaned = dict(custom_data)
    for field in category.required_fields_schema:
        fname = field["name"]
        ftype = field.get("type", "text")
        value = custom_data.get(fname)
        if value in (None, ""):
            # Default missing fields instead of rejecting
            cleaned[fname] = 0 if ftype == "number" else ""
            continue
        if ftype == "number":
            try:
                value = float(value)
            except (TypeError, ValueError):
                raise HTTPException(status_code=422, detail=f"{fname} must be a number")
        cleaned[fname] = value
    return cleaned


def serialize_item(item: Item) -> ItemOut:
    return ItemOut(
        id=item.id,
        name=item.name,
        category_id=item.category_id,
        category_name=item.category.name,
        custom_data=item.custom_data,
        created_at=item.created_at.isoformat() if item.created_at else None,
        updated_at=item.updated_at.isoformat() if item.updated_at else None,
    )


def serialize_task(task: ItemTask) -> ItemTaskOut:
    return ItemTaskOut(
        id=task.id,
        item_id=task.item_id,
        title=task.title,
        description=task.description or "",
        priority=task.priority or "normal",
        due_date=task.due_date,
        is_completed=task.is_completed,
        is_custom=task.is_custom,
        completed_on=task.completed_on,
        remarks=task.remarks or "",
        updated_at=task.updated_at.isoformat() if task.updated_at else None,
    )


def user_assigned_category_ids(db: Session, user: User) -> list[int]:
    return list(db.scalars(
        select(CategoryAssignment.category_id)
        .where(CategoryAssignment.user_id == user.id)
    ).all())


def sync_baseline_task_to_item(db: Session, item: Item, title: str, description: str = "") -> None:
    existing = db.scalar(
        select(ItemTask).where(ItemTask.item_id == item.id, ItemTask.title == title, ItemTask.is_custom.is_(False))
    )
    if existing:
        return
    db.add(ItemTask(item_id=item.id, title=title, description=description, is_completed=False, is_custom=False))


def category_date_range(category: Category) -> list[date]:
    today = date.today()
    start = parse_iso_date(category.start_date) or today
    end = parse_iso_date(category.end_date) or (start + timedelta(days=6))
    days, cur = [], start
    while cur <= end:
        days.append(cur)
        cur += timedelta(days=1)
    return days


# ── Migration ───────────────────────────────────────────────────────────────────

def migrate_database() -> None:
    with engine.begin() as conn:
        def cols(table: str) -> set:
            return {r[1] for r in conn.execute(text(f"PRAGMA table_info({table})")).all()}

        # users
        uc = cols("users")
        if "created_at" not in uc:
            conn.execute(text("ALTER TABLE users ADD COLUMN created_at DATETIME"))

        # categories — make user_id nullable (already is in sqlite, just ensure column exists)
        cc = cols("categories")
        if "user_id" not in cc:
            conn.execute(text("ALTER TABLE categories ADD COLUMN user_id INTEGER REFERENCES users(id)"))

        # items
        ic = cols("items")
        if "created_at" not in ic:
            conn.execute(text("ALTER TABLE items ADD COLUMN created_at DATETIME"))
        if "updated_at" not in ic:
            conn.execute(text("ALTER TABLE items ADD COLUMN updated_at DATETIME"))

        # item_tasks
        tc = cols("item_tasks")
        if "description" not in tc:
            conn.execute(text("ALTER TABLE item_tasks ADD COLUMN description VARCHAR DEFAULT ''"))
        if "priority" not in tc:
            conn.execute(text("ALTER TABLE item_tasks ADD COLUMN priority VARCHAR DEFAULT 'normal'"))
        if "due_date" not in tc:
            conn.execute(text("ALTER TABLE item_tasks ADD COLUMN due_date VARCHAR"))
        if "completed_on" not in tc:
            conn.execute(text("ALTER TABLE item_tasks ADD COLUMN completed_on VARCHAR"))
            conn.execute(text(
                "UPDATE item_tasks SET completed_on = :today WHERE is_completed = 1 AND completed_on IS NULL"
            ), {"today": date.today().isoformat()})
        if "remarks" not in tc:
            conn.execute(text("ALTER TABLE item_tasks ADD COLUMN remarks VARCHAR DEFAULT ''"))
        if "updated_at" not in tc:
            conn.execute(text("ALTER TABLE item_tasks ADD COLUMN updated_at DATETIME"))
        if "updated_by" not in tc:
            conn.execute(text("ALTER TABLE item_tasks ADD COLUMN updated_by INTEGER REFERENCES users(id)"))
        if "is_custom" not in tc:
            conn.execute(text("ALTER TABLE item_tasks ADD COLUMN is_custom BOOLEAN DEFAULT 1"))

        # audit_logs
        ac = cols("audit_logs")
        if "entity_type" not in ac:
            conn.execute(text("ALTER TABLE audit_logs ADD COLUMN entity_type VARCHAR"))
        if "entity_id" not in ac:
            conn.execute(text("ALTER TABLE audit_logs ADD COLUMN entity_id INTEGER"))
        if "details" not in ac:
            conn.execute(text("ALTER TABLE audit_logs ADD COLUMN details VARCHAR"))

        # category_tasks
        ctc = cols("category_tasks")
        if "description" not in ctc:
            conn.execute(text("ALTER TABLE category_tasks ADD COLUMN description VARCHAR DEFAULT ''"))


def initialize_database() -> None:
    Base.metadata.create_all(bind=engine)
    migrate_database()


@app.on_event("startup")
def on_startup() -> None:
    initialize_database()


# ── Page Routes ─────────────────────────────────────────────────────────────────

def render_page(filename: str) -> HTMLResponse:
    html = (BASE_DIR / "static" / filename).read_text(encoding="utf-8")
    base_href = f"{BASE_PATH}/" if BASE_PATH else "/"
    return HTMLResponse(html.replace("__BASE_PATH__", base_href))


@app.get("/")
def index() -> HTMLResponse:
    return render_page("index.html")

@app.get("/login")
def login_page() -> HTMLResponse:
    return render_page("login.html")

@app.get("/dashboard")
def dashboard_page() -> HTMLResponse:
    return render_page("dashboard.html")

@app.get("/admin")
def admin_page() -> HTMLResponse:
    return render_page("admin.html")


# ── Auth API ─────────────────────────────────────────────────────────────────────

@app.post("/api/register", status_code=201)
def register_user(payload: UserRegister, db: Session = Depends(get_db)):
    if db.scalar(select(User).where(User.email == payload.email)):
        raise HTTPException(status_code=400, detail="Email already registered")
    user = User(
        name=payload.name, phone=payload.phone, location=payload.location,
        email=payload.email, password=hash_password(payload.password),
        role="user", created_at=datetime.utcnow()
    )
    db.add(user)
    db.flush()
    log_action(db, user, "USER_REGISTERED", "user", user.id, f"New user: {user.name}")
    db.commit()
    return {"message": "Registered successfully"}


@app.post("/api/login")
def login_user(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.scalar(select(User).where(User.email == payload.email))
    if not user or not verify_password(payload.password, user.password):
        raise HTTPException(status_code=400, detail="Invalid email or password")
    token = create_access_token({"sub": user.email, "role": user.role, "user_id": user.id})
    return {"access_token": token, "token_type": "bearer", "role": user.role}


@app.get("/api/me")
def get_me(current_user: User = Depends(get_current_user)):
    return UserOut.model_validate(current_user)


@app.put("/api/me", response_model=UserOut)
def update_profile(
    payload: UserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if payload.email != current_user.email:
        existing = db.scalar(select(User).where(User.email == payload.email))
        if existing:
            raise HTTPException(status_code=400, detail="Email already taken")
            
    current_user.name = payload.name
    current_user.phone = payload.phone
    current_user.location = payload.location
    current_user.email = payload.email
    db.commit()
    db.refresh(current_user)
    return current_user


# ── User Management API ──────────────────────────────────────────────────────────

@app.get("/api/users", response_model=list[UserOut])
def list_users(admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    return db.scalars(select(User).order_by(User.name)).all()


@app.delete("/api/users/{user_id}", status_code=204)
def delete_user(user_id: int, admin: User = Depends(require_admin), db: Session = Depends(get_db)):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if user.id == admin.id:
        raise HTTPException(status_code=400, detail="Cannot delete yourself")
    log_action(db, admin, "USER_DELETED", "user", user_id, f"Deleted user: {user.name}")
    db.delete(user)
    db.commit()


# ── Category Assignment API ──────────────────────────────────────────────────────

@app.get("/api/categories/{category_id}/assignments")
@app.get("/api/categories/{category_id}/assigned-users")
def get_category_assignments(
    category_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    ensure_category(db, category_id)
    if current_user.role != "admin":
        assigned_ids = user_assigned_category_ids(db, current_user)
        if category_id not in assigned_ids:
            raise HTTPException(status_code=403, detail="Access denied to this category")
            
    ids = list(db.scalars(
        select(CategoryAssignment.user_id).where(CategoryAssignment.category_id == category_id)
    ).all())
    users = db.scalars(select(User).where(User.id.in_(ids))).all() if ids else []
    return [UserOut.model_validate(u) for u in users]


@app.post("/api/categories/{category_id}/assignments")
@app.post("/api/categories/{category_id}/assign")
def assign_category(
    category_id: int,
    payload: CategoryAssignRequest,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    ensure_category(db, category_id)
    users = db.scalars(select(User).where(User.id.in_(payload.user_ids))).all()
    if len(users) != len(payload.user_ids):
        raise HTTPException(status_code=400, detail="One or more users not found")
    db.query(CategoryAssignment).filter(CategoryAssignment.category_id == category_id).delete()
    for uid in payload.user_ids:
        db.add(CategoryAssignment(
            category_id=category_id, user_id=uid,
            assigned_by=admin.id, assigned_on=datetime.utcnow()
        ))
    cat = db.get(Category, category_id)
    log_action(db, admin, "CATEGORY_ASSIGNED", "category", category_id,
               f"Assigned users {payload.user_ids} to '{cat.name}'")
    db.commit()
    return {"message": "Assigned", "user_ids": payload.user_ids}


@app.delete("/api/categories/{category_id}/assign/{user_id}", status_code=204)
def remove_category_assignment(
    category_id: int,
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    ensure_category(db, category_id)
    assignment = db.scalar(
        select(CategoryAssignment).where(
            CategoryAssignment.category_id == category_id,
            CategoryAssignment.user_id == user_id
        )
    )
    if assignment:
        db.delete(assignment)
        cat = db.get(Category, category_id)
        log_action(db, admin, "CATEGORY_UNASSIGNED", "category", category_id,
                   f"Unassigned user ID {user_id} from '{cat.name}'")
        db.commit()


@app.get("/api/users/{user_id}/assignments")
def get_user_assignments(
    user_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    cat_ids = list(db.scalars(
        select(CategoryAssignment.category_id).where(CategoryAssignment.user_id == user_id)
    ).all())
    cats = db.scalars(select(Category).where(Category.id.in_(cat_ids))).all() if cat_ids else []
    return [CategoryOut.model_validate(c) for c in cats]


# ── Category API ────────────────────────────────────────────────────────────────

@app.get("/api/categories", response_model=list[CategoryOut])
def list_categories(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role == "admin":
        return db.scalars(select(Category).order_by(Category.name)).all()
    
    assigned_ids = user_assigned_category_ids(db, current_user)
    if not assigned_ids:
        return []
    return db.scalars(select(Category).where(Category.id.in_(assigned_ids)).order_by(Category.name)).all()


@app.post("/api/categories", response_model=CategoryOut, status_code=201)
def create_category(
    payload: CategoryCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    # Check duplicate name
    existing = db.scalar(select(Category).where(Category.name == payload.name))
    if existing:
        raise HTTPException(status_code=409, detail="Category name already exists")

    fields = [f.model_dump() for f in payload.required_fields_schema]
    category = Category(
        name=payload.name,
        description=payload.description,
        start_date=payload.start_date,
        end_date=payload.end_date,
        required_fields_schema=fields,
        user_id=admin.id # optional backward compatibility
    )
    db.add(category)
    db.flush()

    # Create initial tasks
    for task_data in payload.tasks:
        db.add(CategoryTask(category_id=category.id, title=task_data.title, description=task_data.description))
    
    log_action(db, admin, "CATEGORY_CREATED", "category", category.id, f"Created category '{category.name}'")
    db.commit()
    db.refresh(category)
    return category


@app.put("/api/categories/{category_id}", response_model=CategoryOut)
def update_category(
    category_id: int,
    payload: CategoryUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    category = ensure_category(db, category_id)
    # Check duplicate name
    existing = db.scalar(select(Category).where(Category.name == payload.name, Category.id != category_id))
    if existing:
        raise HTTPException(status_code=409, detail="Category name already exists")

    category.name = payload.name
    category.description = payload.description
    category.start_date = payload.start_date
    category.end_date = payload.end_date
    category.required_fields_schema = [f.model_dump() for f in payload.required_fields_schema]
    
    log_action(db, admin, "CATEGORY_UPDATED", "category", category_id, f"Updated category '{category.name}'")
    db.commit()
    db.refresh(category)
    return category


@app.delete("/api/categories/{category_id}", status_code=204)
def delete_category(
    category_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    category = ensure_category(db, category_id)
    name = category.name
    
    # Cascade delete assignments explicitly
    db.query(CategoryAssignment).filter(CategoryAssignment.category_id == category_id).delete()
    
    # Rest is deleted via cascade relationship
    db.delete(category)
    log_action(db, admin, "CATEGORY_DELETED", "category", category_id, f"Deleted category '{name}' and cascaded children")
    db.commit()


# ── Category Task Templates API ─────────────────────────────────────────────────

@app.get("/api/categories/{category_id}/tasks", response_model=list[CategoryTaskOut])
def list_category_tasks(
    category_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    if current_user.role != "admin":
        assigned_ids = user_assigned_category_ids(db, current_user)
        if category_id not in assigned_ids:
            raise HTTPException(status_code=403, detail="Access denied to category tasks")
            
    ensure_category(db, category_id)
    return db.scalars(
        select(CategoryTask).where(CategoryTask.category_id == category_id).order_by(CategoryTask.id)
    ).all()


@app.post("/api/categories/{category_id}/tasks", response_model=CategoryTaskOut, status_code=201)
def create_category_task(
    category_id: int,
    payload: CategoryTaskCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    category = ensure_category(db, category_id)
    
    # Check if duplicate in category tasks
    dup = db.scalar(select(CategoryTask).where(CategoryTask.category_id == category_id, CategoryTask.title == payload.title))
    if dup:
        raise HTTPException(status_code=400, detail="Task title already exists in category template")
        
    task = CategoryTask(category_id=category_id, title=payload.title, description=payload.description)
    db.add(task)
    db.flush()
    
    # Sync task to existing items under this category
    for item in category.items:
        sync_baseline_task_to_item(db, item, payload.title, payload.description)
        
    log_action(db, admin, "TASK_TEMPLATE_CREATED", "category_task", task.id, f"Created template task '{task.title}' in '{category.name}'")
    db.commit()
    db.refresh(task)
    return task


# ── Item API ────────────────────────────────────────────────────────────────────

@app.get("/api/items", response_model=list[ItemOut])
def list_items(
    category_id: int | None = Query(default=None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Determine allowed categories
    if current_user.role == "admin":
        stmt = select(Item).join(Category)
        if category_id is not None:
            stmt = stmt.where(Item.category_id == category_id)
    else:
        assigned_ids = user_assigned_category_ids(db, current_user)
        if not assigned_ids:
            return []
        stmt = select(Item).join(Category).where(Item.category_id.in_(assigned_ids))
        if category_id is not None:
            if category_id not in assigned_ids:
                raise HTTPException(status_code=403, detail="Access denied to this category")
            stmt = stmt.where(Item.category_id == category_id)
            
    items = db.scalars(stmt.order_by(Item.id.desc())).all()
    return [serialize_item(item) for item in items]


@app.get("/api/items/{item_id}", response_model=ItemOut)
def get_item(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    item = ensure_item(db, item_id)
    if current_user.role != "admin":
        assigned_ids = user_assigned_category_ids(db, current_user)
        if item.category_id not in assigned_ids:
            raise HTTPException(status_code=403, detail="Access denied to this item")
    return serialize_item(item)


@app.post("/api/items", response_model=ItemOut, status_code=201)
def create_item(
    payload: ItemCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    category = ensure_category(db, payload.category_id)
    custom_data = validate_custom_data(category, payload.custom_data)
    
    item = Item(
        name=payload.name,
        category_id=category.id,
        custom_data=custom_data,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow()
    )
    db.add(item)
    db.flush()
    
    # Pre-populate tasks from category tasks templates
    for t_template in category.tasks:
        db.add(ItemTask(
            item_id=item.id,
            title=t_template.title,
            description=t_template.description,
            is_completed=False,
            is_custom=False
        ))
        
    log_action(db, admin, "ITEM_CREATED", "item", item.id, f"Created item '{item.name}' under category '{category.name}'")
    db.commit()
    db.refresh(item)
    return serialize_item(item)


@app.put("/api/items/{item_id}", response_model=ItemOut)
def update_item(
    item_id: int,
    payload: ItemUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    item = ensure_item(db, item_id)
    # Allow admins and assigned users to update items (e.g. save comments)
    if current_user.role != "admin":
        assigned_ids = user_assigned_category_ids(db, current_user)
        if item.category_id not in assigned_ids:
            raise HTTPException(status_code=403, detail="Access denied to update this item")
    custom_data = validate_custom_data(item.category, payload.custom_data)
    
    item.name = payload.name
    item.custom_data = custom_data
    item.updated_at = datetime.utcnow()
    
    log_action(db, current_user, "ITEM_UPDATED", "item", item_id, f"Updated item '{item.name}'")
    db.commit()
    db.refresh(item)
    return serialize_item(item)


@app.delete("/api/items/{item_id}", status_code=204)
def delete_item(
    item_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    item = ensure_item(db, item_id)
    name = item.name
    db.delete(item)
    log_action(db, admin, "ITEM_DELETED", "item", item_id, f"Deleted item '{name}'")
    db.commit()


# ── Task API ────────────────────────────────────────────────────────────────────

@app.get("/api/items/{item_id}/tasks", response_model=list[ItemTaskOut])
def list_item_tasks(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    item = ensure_item(db, item_id)
    if current_user.role != "admin":
        assigned_ids = user_assigned_category_ids(db, current_user)
        if item.category_id not in assigned_ids:
            raise HTTPException(status_code=403, detail="Access denied to tasks for this item")
            
    tasks = db.scalars(select(ItemTask).where(ItemTask.item_id == item_id).order_by(ItemTask.id)).all()
    return [serialize_task(t) for t in tasks]


@app.post("/api/items/{item_id}/tasks", response_model=ItemTaskOut, status_code=201)
def create_item_task(
    item_id: int,
    payload: ItemTaskCreate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    item = ensure_item(db, item_id)
    task = ItemTask(
        item_id=item_id,
        title=payload.title,
        description=payload.description,
        priority=payload.priority,
        due_date=payload.due_date,
        is_completed=False,
        is_custom=True
    )
    db.add(task)
    log_action(db, admin, "TASK_CREATED", "item_task", task.id, f"Created custom task '{task.title}' on item '{item.name}'")
    db.commit()
    db.refresh(task)
    return serialize_task(task)


@app.put("/api/tasks/{task_id}", response_model=ItemTaskOut)
def update_task_admin(
    task_id: int,
    payload: ItemTaskUpdate,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    task = ensure_task(db, task_id)
    task.title = payload.title
    task.description = payload.description
    task.priority = payload.priority
    task.due_date = payload.due_date
    task.updated_at = datetime.utcnow()
    task.updated_by = admin.id
    
    log_action(db, admin, "TASK_UPDATED", "item_task", task_id, f"Admin updated task '{task.title}' details")
    db.commit()
    db.refresh(task)
    return serialize_task(task)


@app.patch("/api/tasks/{task_id}", response_model=ItemTaskOut)
def update_task_status(
    task_id: int,
    payload: ItemTaskUserUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = ensure_task(db, task_id)
    
    # Verify permission
    if current_user.role != "admin":
        assigned_ids = user_assigned_category_ids(db, current_user)
        if task.item.category_id not in assigned_ids:
            raise HTTPException(status_code=403, detail="Access denied to update this task")
            
    # Check if is_completed toggled
    toggled = (task.is_completed != payload.is_completed)
    task.is_completed = payload.is_completed
    task.remarks = payload.remarks
    task.updated_at = datetime.utcnow()
    task.updated_by = current_user.id
    
    if task.is_completed:
        if toggled or not task.completed_on:
            task.completed_on = date.today().isoformat()
    else:
        task.completed_on = None
        
    action_type = "TASK_COMPLETED" if task.is_completed else "TASK_UNCOMPLETED"
    log_action(db, current_user, action_type, "item_task", task_id, 
               f"User '{current_user.name}' updated status. Completed={task.is_completed}. Remarks='{task.remarks}'")
               
    db.commit()
    db.refresh(task)
    return serialize_task(task)


@app.put("/api/tasks/{task_id}/toggle", response_model=ItemTaskOut)
def toggle_task_status(
    task_id: int,
    body: dict = Body(None),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = ensure_task(db, task_id)
    if current_user.role != "admin":
        assigned_ids = user_assigned_category_ids(db, current_user)
        if task.item.category_id not in assigned_ids:
            raise HTTPException(status_code=403, detail="Access denied")
            
    task.is_completed = not task.is_completed
    task.updated_at = datetime.utcnow()
    task.updated_by = current_user.id
    if task.is_completed:
        task.completed_on = (body.get("completed_on") if body else None) or date.today().isoformat()
    else:
        task.completed_on = None
        
    action_type = "TASK_COMPLETED" if task.is_completed else "TASK_UNCOMPLETED"
    log_action(db, current_user, action_type, "item_task", task_id, 
               f"User '{current_user.name}' toggled task status. Completed={task.is_completed}")
    db.commit()
    db.refresh(task)
    return serialize_task(task)


@app.delete("/api/tasks/{task_id}", status_code=204)
def delete_task(
    task_id: int,
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    task = ensure_task(db, task_id)
    name = task.title
    db.delete(task)
    log_action(db, admin, "TASK_DELETED", "item_task", task_id, f"Deleted task '{name}'")
    db.commit()


# ── Progress APIs ───────────────────────────────────────────────────────────────

@app.get("/api/categories/{category_id}/progress", response_model=list[CategoryProgressOut])
def category_progress(
    category_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    category = ensure_category(db, category_id)
    if current_user.role != "admin":
        assigned_ids = user_assigned_category_ids(db, current_user)
        if category_id not in assigned_ids:
            raise HTTPException(status_code=403, detail="Access denied to this category progress")
            
    tasks = db.scalars(select(ItemTask).join(Item).where(Item.category_id == category_id)).all()
    total_tasks = len(tasks)
    progress = []
    
    for day in category_date_range(category):
        completed_to_date = sum(
            1 for t in tasks if t.is_completed and t.completed_on and parse_iso_date(t.completed_on) <= day
        )
        progress.append(CategoryProgressOut(
            date=day.isoformat(),
            label=day.strftime("%b %d"),
            pending_tasks=total_tasks - completed_to_date,
            completed_to_date=completed_to_date,
            total_tasks=total_tasks
        ))
    return progress


@app.get("/api/items/{item_id}/progress", response_model=list[CategoryProgressOut])
def item_progress(
    item_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    item = ensure_item(db, item_id)
    if current_user.role != "admin":
        assigned_ids = user_assigned_category_ids(db, current_user)
        if item.category_id not in assigned_ids:
            raise HTTPException(status_code=403, detail="Access denied to this item progress")
            
    tasks = db.scalars(select(ItemTask).where(ItemTask.item_id == item_id)).all()
    total_tasks = len(tasks)
    progress = []
    
    for day in category_date_range(item.category):
        completed_to_date = sum(
            1 for t in tasks if t.is_completed and t.completed_on and parse_iso_date(t.completed_on) <= day
        )
        progress.append(CategoryProgressOut(
            date=day.isoformat(),
            label=day.strftime("%b %d"),
            pending_tasks=total_tasks - completed_to_date,
            completed_to_date=completed_to_date,
            total_tasks=total_tasks
        ))
    return progress


@app.get("/api/tasks/{task_id}/progress", response_model=list[CategoryProgressOut])
def task_progress(
    task_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    task = ensure_task(db, task_id)
    if current_user.role != "admin":
        assigned_ids = user_assigned_category_ids(db, current_user)
        if task.item.category_id not in assigned_ids:
            raise HTTPException(status_code=403, detail="Access denied to this task progress")
            
    total_tasks = 1
    progress = []
    
    for day in category_date_range(task.item.category):
        completed_to_date = 1 if (
            task.is_completed and task.completed_on and parse_iso_date(task.completed_on) <= day
        ) else 0
        progress.append(CategoryProgressOut(
            date=day.isoformat(),
            label=day.strftime("%b %d"),
            pending_tasks=total_tasks - completed_to_date,
            completed_to_date=completed_to_date,
            total_tasks=total_tasks
        ))
    return progress


# ── Audit Log API ───────────────────────────────────────────────────────────────

@app.get("/api/audit-logs")
def get_audit_logs(
    admin: User = Depends(require_admin),
    db: Session = Depends(get_db)
):
    logs = db.execute(
        select(AuditLog, User.name)
        .join(User, AuditLog.user_id == User.id)
        .order_by(AuditLog.timestamp.desc())
        .limit(100)
    ).all()
    
    return [
        {
            "id": row.AuditLog.id,
            "user": row.name,
            "action": row.AuditLog.action,
            "entity_type": row.AuditLog.entity_type,
            "entity_id": row.AuditLog.entity_id,
            "details": row.AuditLog.details,
            "timestamp": row.AuditLog.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        }
        for row in logs
    ]


# ── Dashboard API ───────────────────────────────────────────────────────────────

@app.get("/api/dashboard")
def get_dashboard(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    today_str = date.today().isoformat()
    
    if current_user.role == "admin":
        # 1. Total counts
        total_users = db.scalar(select(func.count(User.id)))
        total_categories = db.scalar(select(func.count(Category.id)))
        total_items = db.scalar(select(func.count(Item.id)))
        total_tasks = db.scalar(select(func.count(ItemTask.id)))
        
        # Completed/Updated today
        # Today completions: completed_on matches today
        completed_today = db.scalar(
            select(func.count(ItemTask.id))
            .where(ItemTask.is_completed.is_(True), ItemTask.completed_on == today_str)
        ) or 0
        
        # Today updates (any updates today)
        today_start = datetime.combine(date.today(), datetime.min.time())
        updated_today = db.scalar(
            select(func.count(ItemTask.id))
            .where(ItemTask.updated_at >= today_start)
        ) or 0
        
        # completion rate
        completed_tasks = db.scalar(select(func.count(ItemTask.id)).where(ItemTask.is_completed.is_(True))) or 0
        completion_rate = round((completed_tasks / total_tasks * 100), 1) if total_tasks else 0.0
        
        # Tasks per category
        cats = db.scalars(select(Category)).all()
        tasks_per_category = []
        for c in cats:
            t_total = db.scalar(
                select(func.count(ItemTask.id)).join(Item).where(Item.category_id == c.id)
            ) or 0
            t_completed = db.scalar(
                select(func.count(ItemTask.id)).join(Item).where(Item.category_id == c.id, ItemTask.is_completed.is_(True))
            ) or 0
            tasks_per_category.append({
                "id": c.id,
                "name": c.name,
                "total": t_total,
                "completed": t_completed,
                "pending": t_total - t_completed,
                "rate": round(t_completed / t_total * 100, 1) if t_total else 0.0
            })
            
        # Recent activities
        recent_logs = db.execute(
            select(AuditLog, User.name)
            .join(User, AuditLog.user_id == User.id)
            .order_by(AuditLog.timestamp.desc())
            .limit(10)
        ).all()
        recent_activity = [
            {
                "user": log.name,
                "action": log.AuditLog.action,
                "details": log.AuditLog.details,
                "timestamp": log.AuditLog.timestamp.strftime("%H:%M")
            }
            for log in recent_logs
        ]
        
        return {
            "role": "admin",
            "total_users": total_users,
            "total_categories": total_categories,
            "total_items": total_items,
            "total_tasks": total_tasks,
            "completed_today": completed_today,
            "updated_today": updated_today,
            "completion_rate": completion_rate,
            "tasks_per_category": tasks_per_category,
            "recent_activity": recent_activity
        }
        
    else:
        # User Dashboard
        assigned_ids = user_assigned_category_ids(db, current_user)
        if not assigned_ids:
            return {
                "role": "user",
                "my_categories": 0,
                "my_items": 0,
                "my_tasks": 0,
                "my_completed": 0,
                "my_completion_rate": 0.0,
                "categories": [],
                "recent_activity": []
            }
            
        my_cats_count = len(assigned_ids)
        my_items_count = db.scalar(select(func.count(Item.id)).where(Item.category_id.in_(assigned_ids))) or 0
        my_tasks_count = db.scalar(select(func.count(ItemTask.id)).join(Item).where(Item.category_id.in_(assigned_ids))) or 0
        my_completed_count = db.scalar(
            select(func.count(ItemTask.id)).join(Item)
            .where(Item.category_id.in_(assigned_ids), ItemTask.is_completed.is_(True))
        ) or 0
        my_completion_rate = round(my_completed_count / my_tasks_count * 100, 1) if my_tasks_count else 0.0
        
        # User's Category list breakdown
        cats = db.scalars(select(Category).where(Category.id.in_(assigned_ids))).all()
        categories_breakdown = []
        for c in cats:
            t_total = db.scalar(
                select(func.count(ItemTask.id)).join(Item).where(Item.category_id == c.id)
            ) or 0
            t_completed = db.scalar(
                select(func.count(ItemTask.id)).join(Item).where(Item.category_id == c.id, ItemTask.is_completed.is_(True))
            ) or 0
            categories_breakdown.append({
                "id": c.id,
                "name": c.name,
                "total": t_total,
                "completed": t_completed,
                "pending": t_total - t_completed,
                "rate": round(t_completed / t_total * 100, 1) if t_total else 0.0
            })
            
        # User's recent activities (activities performed by current user)
        recent_logs = db.execute(
            select(AuditLog, User.name)
            .join(User, AuditLog.user_id == User.id)
            .where(AuditLog.user_id == current_user.id)
            .order_by(AuditLog.timestamp.desc())
            .limit(10)
        ).all()
        recent_activity = [
            {
                "user": log.name,
                "action": log.AuditLog.action,
                "details": log.AuditLog.details,
                "timestamp": log.AuditLog.timestamp.strftime("%H:%M")
            }
            for log in recent_logs
        ]
        
        return {
            "role": "user",
            "my_categories": my_cats_count,
            "my_items": my_items_count,
            "my_tasks": my_tasks_count,
            "my_completed": my_completed_count,
            "my_completion_rate": my_completion_rate,
            "categories": categories_breakdown,
            "recent_activity": recent_activity
        }


