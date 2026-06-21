from app.main import SessionLocal, User
from sqlalchemy import select

db = SessionLocal()

user = db.scalar(select(User).where(User.email == "admin@test.com"))

if user:
    user.role = "admin"
    db.commit()
    print("✅ Admin updated successfully")
else:
    print("❌ User not found")

db.close()