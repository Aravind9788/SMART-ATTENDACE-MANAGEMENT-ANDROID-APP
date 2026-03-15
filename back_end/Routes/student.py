from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func
from datetime import date
from typing import Dict, List
import models, schema
from database import get_db

student_router = APIRouter()

@student_router.get("/profile/{student_id}")
def get_student_profile(student_id: int, db: Session = Depends(get_db)):
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Find their assigned tutor based on their class profile
    tutor = db.query(models.Staff).filter(
        models.Staff.is_tutor == True,
        models.Staff.tutor_program == student.program,
        models.Staff.tutor_class_year == student.year,
        models.Staff.tutor_shift == student.shift
    ).first()
    
    tutor_name = tutor.name if tutor else "Unassigned"

    return {
        "name": student.name,
        "id": student.reg_no,
        "department": "Computer Science & AI", # Mock mapping
        "class_info": f"Class: {student.program}, Year {student.year}, Shift {student.shift}",
        "tutor_name": tutor_name,
        "email": f"{student.reg_no.lower()}@college.edu",
        "phone": "+91 98765 43210" # Mock mapping
    }

# Helper method to calculate time strings
def format_time_range(start_time, end_time):
    return f"{start_time.strftime('%I:%M %p')} - {end_time.strftime('%I:%M %p')}"

@student_router.get("/{student_id}/dashboard-stats", response_model=schema.StudentDashboardOverview)
def get_student_dashboard_stats(student_id: int, db: Session = Depends(get_db)):
    # 1. Verify Student
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # 2. Get attendance data for the student
    attendances = db.query(models.Attendance).filter(models.Attendance.student_id == student_id).all()
    
    total_present = sum(1 for a in attendances if a.status.lower() == 'present')
    total_absent = sum(1 for a in attendances if a.status.lower() == 'absent')
    total_marked = total_present + total_absent
    
    # 3. Calculate percentage
    # In a real app this would be against total periods. We use math against marked periods here.
    # The requirement specifically mentions Total Semester hours = 250 in frontend, we will just send % based on actuals
    percentage = 0
    if total_marked > 0:
        percentage = int((total_present / total_marked) * 100)
    else:
        percentage = 100 # Default if no classes happened yet

    # 4. Determine 'today' status
    today = date.today()
    today_status = "NOT_MARKED"
    
    # Find active periods for today that apply to this student's class (or general if null)
    # Then see if an attendance record exists for this student today
    today_records = db.query(models.Attendance).join(models.Period).filter(
        models.Attendance.student_id == student_id,
        models.Period.date == today
    ).all()

    if today_records:
        # If they were present for ANY period today, we mark them PRESENT overall today. (Standard college heuristic)
        # Otherwise if all are absent, they are ABSENT.
        is_present_today = any(r.status.lower() == 'present' for r in today_records)
        today_status = "PRESENT" if is_present_today else "ABSENT"

    return {
        "id": student.reg_no,
        "name": student.name,
        "role": "Student",
        "program": student.program,
        "year": student.year,
        "shift": student.shift,
        "attendancePercentage": percentage,
        "todayStatus": today_status,
        "monthlySummary": {
            "present": total_present,
            "absent": total_absent,
            "totalHours": total_marked
        }
    }


@student_router.get("/{student_id}/timetable", response_model=Dict[str, List[schema.StudentTimetableEntry]])
def get_student_timetable(student_id: int, db: Session = Depends(get_db)):
    # 1. Getting student class properties to resolve subjects
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")

    # Group response by Day of week (Mon, Tue, Wed, Thu, Fri, Sat)
    timetable_dict = {
        'Mon': [],
        'Tue': [],
        'Wed': [],
        'Thu': [],
        'Fri': [],
        'Sat': []
    }

    if not student.class_id:
        # Fallback if student has no class strictly assigned
        from Routes.staff import get_timetable
        entries = get_timetable(student.program, student.year, db)
    else:
        entries = db.query(models.Timetable).filter(models.Timetable.class_id == student.class_id).all()

    for entry in entries:
        t_day = entry.day
        if t_day in timetable_dict:
            timetable_dict[t_day].append({
                "id": str(entry.id),
                "time": f"Period {entry.period}", 
                "subject": entry.subject_name,
                "staff": entry.staff_name or "TBA",
                "room": "-" # Can be expanded in future DB migrations
            })
            
    # Sort each day's entries by period so they appear sequentially in UI
    for day in timetable_dict:
        # 'Period 1' string parsing is a bit crude for sorting, but valid for MVP where "time" holds "Period X"
        timetable_dict[day].sort(key=lambda x: int(x["time"].replace("Period ", "")))

    return timetable_dict
