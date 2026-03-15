import sys
import os

# Ensure back_end directory is on sys.path so absolute imports work everywhere
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from database import engine, Base
from Routes import admin, staff, student

# Create all database tables
Base.metadata.create_all(bind=engine)

# --- Auto-Migration: Add missing columns to existing tables ---
from sqlalchemy import text, inspect
with engine.connect() as conn:
    inspector = inspect(engine)
    # Add 'shift' column to 'unexpected_leaves' if it doesn't exist
    columns = [c['name'] for c in inspector.get_columns('unexpected_leaves')]
    if 'shift' not in columns:
        conn.execute(text("ALTER TABLE unexpected_leaves ADD COLUMN shift VARCHAR(10) NULL"))
        conn.commit()
    # Add 'password' column to 'students' if it doesn't exist
    student_cols = [c['name'] for c in inspector.get_columns('students')]
    if 'password' not in student_cols:
        conn.execute(text("ALTER TABLE students ADD COLUMN password VARCHAR(100) NULL"))
        conn.commit()

app = FastAPI(title="Smart Attendance System API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(admin.admin_router, prefix="/admin", tags=["admin"])
app.include_router(staff.staff_router, prefix="/staff", tags=["staff"])
app.include_router(student.student_router, prefix="/student", tags=["student"])

@app.get("/")
def read_root():
    return {"message": "Welcome to Smart Attendance System API"}

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
