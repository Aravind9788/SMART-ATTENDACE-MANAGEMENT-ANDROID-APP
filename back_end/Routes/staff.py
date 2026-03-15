from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date, datetime, time as dt_time

from database import get_db
import models, schema

staff_router = APIRouter()

# ----------------- Dashboard -----------------
@staff_router.get("/dashboard-stats", response_model=schema.StaffDashboardStats)
def get_staff_dashboard_stats(
    staff_id: int, 
    program: str, 
    year: str, 
    shift: str, 
    db: Session = Depends(get_db)
):
    # Get staff details
    staff = db.query(models.Staff).filter(models.Staff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")

    # Get class matches for filters
    base_students_query = db.query(models.Student).filter(
        models.Student.program == program,
        models.Student.year == year,
        models.Student.shift == shift
    )
    
    total_students = base_students_query.count()
    
    # Get today's attendance records for these specific students
    today = date.today()
    
    today_attendances = db.query(models.Attendance).join(models.Period).join(models.Student).filter(
        models.Period.date == today,
        models.Student.program == program,
        models.Student.year == year,
        models.Student.shift == shift
    ).all()
    
    student_period_counts = {} 
    for att in today_attendances:
        sid = att.student_id
        if sid not in student_period_counts:
            student_period_counts[sid] = {
                "info": {
                    "id": att.student.id,
                    "name": att.student.name,
                    "reg_no": att.student.reg_no,
                },
                "total": 0,
                "absent": 0
            }
        student_period_counts[sid]["total"] += 1
        if att.status == "absent":
            student_period_counts[sid]["absent"] += 1

    # Build daily status: absent only if absent in ALL conducted periods
    student_daily_status = {}
    for sid, data in student_period_counts.items():
        is_full_day_absent = (data["total"] > 0 and data["absent"] == data["total"])
        student_daily_status[sid] = {
            **data["info"],
            "status": "absent" if is_full_day_absent else "present"
        }

    present_today = sum(1 for s in student_daily_status.values() if s["status"] == "present")
    absent_today = sum(1 for s in student_daily_status.values() if s["status"] == "absent")
    
    recent_records = list(student_daily_status.values())
    
    return {
        "admin_name": staff.name,
        "role": staff.role or "Staff",
        "staff_department": staff.department.name if staff.department else "None",
        "staff_shift": staff.shift,
        "is_tutor": staff.is_tutor,
        "tutor_program": staff.tutor_program,
        "tutor_year": staff.tutor_class_year,
        "tutor_shift": staff.tutor_shift,
        "total_students": total_students,
        "present_today": present_today,
        "absent_today": absent_today,
        "recent_records": recent_records
    }

@staff_router.get("/profile/{staff_id}")
def get_staff_profile(staff_id: int, db: Session = Depends(get_db)):
    staff = db.query(models.Staff).filter(models.Staff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")
        
    tutor_string = "None"
    if staff.is_tutor:
        tutor_string = f"Class Tutor: {staff.tutor_program}, Year {staff.tutor_class_year}, Shift {staff.tutor_shift}"
        
    return {
        "name": staff.name,
        "shift": staff.shift or "1",
        "tutor_assignment": tutor_string
    }

# ----------------- Students Management -----------------
@staff_router.get("/students", response_model=List[schema.StudentResponse])
def get_students(
    staff_id: int,
    program: str, 
    year: str, 
    shift: str, 
    db: Session = Depends(get_db)
):
    staff = db.query(models.Staff).filter(models.Staff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")

    # Get class matching the program/year
    target_class = db.query(models.ClassModel).filter(
        models.ClassModel.program == program,
        models.ClassModel.year == year
    ).first()

    if not target_class:
        return []

    # Enforce strict Department Attendance Policy
    if target_class.department_id != staff.department_id:
        return [] # Securely block returning students from another department

    students = db.query(models.Student).filter(
        models.Student.class_id == target_class.id,
        models.Student.program == program,
        models.Student.year == year,
        models.Student.shift == shift
    ).all()
    return students

@staff_router.post("/students", response_model=schema.StudentResponse)
def create_student(
    student: schema.StudentBase,
    staff_id: int = None,
    db: Session = Depends(get_db)
):
    # 1. Verify staff exists and is a tutor
    if not staff_id:
        raise HTTPException(status_code=400, detail="staff_id is required")
    
    staff = db.query(models.Staff).filter(models.Staff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")
    
    if not staff.is_tutor:
        raise HTTPException(status_code=403, detail="Only assigned tutors can add students.")
    
    # 2. Verify the student's program/year matches the tutor's assigned class
    if staff.tutor_program != student.program or staff.tutor_class_year != student.year:
        raise HTTPException(
            status_code=403, 
            detail=f"You are assigned to {staff.tutor_program} Year {staff.tutor_class_year}. You cannot add students to {student.program} Year {student.year}."
        )

    # 2b. Verify shift assignment matches
    if staff.tutor_shift != student.shift:
        raise HTTPException(
            status_code=403, 
            detail=f"You are assigned to Shift {staff.tutor_shift}. You cannot add students to Shift {student.shift}."
        )

    # 3. Ensure no duplicates by reg_no
    existing = db.query(models.Student).filter(models.Student.reg_no == student.reg_no).first()
    if existing:
        raise HTTPException(status_code=400, detail="Student with this Register Number already exists")
    
    # 4. Auto-assign class_id based on program/year
    target_class = db.query(models.ClassModel).filter(
        models.ClassModel.program == student.program,
        models.ClassModel.year == student.year
    ).first()
    
    if not target_class:
        # Auto-create the class if the system is fresh
        new_class_name = f"{student.program} - Year {student.year}"
        target_class = models.ClassModel(
            name=new_class_name,
            program=student.program,
            year=student.year,
            department_id=staff.department_id
        )
        db.add(target_class)
        db.commit()
        db.refresh(target_class)
    
    student_data = student.dict()
    student_data["class_id"] = target_class.id
        
    db_student = models.Student(**student_data)
    db.add(db_student)
    db.commit()
    db.refresh(db_student)
    return db_student


@staff_router.delete("/students/{student_id}")
def delete_student(student_id: int, staff_id: int = None, db: Session = Depends(get_db)):
    # 1. Verify staff exists and is a tutor
    if not staff_id:
        raise HTTPException(status_code=400, detail="staff_id is required")
    
    staff = db.query(models.Staff).filter(models.Staff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")
    
    if not staff.is_tutor:
        raise HTTPException(status_code=403, detail="Only assigned tutors can delete students.")
    
    # 2. Verify student exists
    student = db.query(models.Student).filter(models.Student.id == student_id).first()
    if not student:
        raise HTTPException(status_code=404, detail="Student not found")
    
    # 3. Verify the student belongs to the tutor's assigned class
    if staff.tutor_program != student.program or staff.tutor_class_year != student.year:
        raise HTTPException(
            status_code=403,
            detail="You can only delete students from your assigned class."
        )

    # 3b. Verify shift matching
    if staff.shift != student.shift:
        raise HTTPException(
            status_code=403,
            detail="You can only delete students from your assigned shift."
        )
    
    db.delete(student)
    db.commit()
    return {"detail": "Student deleted"}


# ----------------- Attendance Management -----------------
@staff_router.get("/attendance/percentage", response_model=List[schema.StudentAttendancePercentage])
def get_attendance_percentage(
    staff_id: int,
    program: str, 
    year: str, 
    shift: str,
    date_from: Optional[date] = None,
    db: Session = Depends(get_db)
):
    """
    Returns the attendance percentage of all students in a specific class.
    Percentage = (Total Present Periods / Total Conducted Periods for Class) * 100
    """
    staff = db.query(models.Staff).filter(models.Staff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")

    if staff.is_tutor:
        if staff.tutor_program != program or staff.tutor_class_year != year:
            raise HTTPException(
                status_code=403, 
                detail=f"You are assigned to {staff.tutor_program} Year {staff.tutor_class_year}. You cannot view reports for {program} Year {year}."
            )

    # Find all periods conducted for this class
    target_class = db.query(models.ClassModel).filter(
        models.ClassModel.program == program,
        models.ClassModel.year == year
    ).first()

    if not target_class:
        return []

    if not staff.is_tutor and target_class.department_id != staff.department_id:
        return []

    period_query = db.query(models.Period).filter(
        models.Period.class_id == target_class.id,
        models.Period.status == "conducted"
    )
    if date_from:
        period_query = period_query.filter(models.Period.date >= date_from)
    
    conducted_periods = period_query.all()
    
    total_conducted = len(conducted_periods)

    # Get all students for this class and shift
    students = db.query(models.Student).filter(
        models.Student.program == program,
        models.Student.year == year,
        models.Student.shift == shift
    ).all()

    if total_conducted == 0:
         # If no classes conducted, return 0% to avoid misleading 100%
         return [
             schema.StudentAttendancePercentage(
                 id=s.id, name=s.name, reg_no=s.reg_no, total_conducted=0, total_present=0, percent=0, color="#64748b" # Gray out classes with 0 periods
             ) for s in students
         ]

    period_ids = [p.id for p in conducted_periods]

    response = []
    for s in students:
        present_count = db.query(models.Attendance).filter(
            models.Attendance.student_id == s.id,
            models.Attendance.period_id.in_(period_ids),
            models.Attendance.status == 'present'
        ).count()

        percent = int((present_count / total_conducted) * 100)
        
        # Color rules: Green > 75%, Yellow 50-75%, Red < 50%
        color = "#16a34a" # Green
        if percent < 75 and percent >= 50:
            color = "#ca8a04" # Yellow
        elif percent < 50:
            color = "#dc2626" # Red

        response.append(
            schema.StudentAttendancePercentage(
                id=s.id,
                name=s.name,
                reg_no=s.reg_no,
                total_conducted=total_conducted,
                total_present=present_count,
                percent=percent,
                color=color
            )
        )
        
    return response

@staff_router.put("/attendance/update-daily")
def update_daily_attendance(
    req: schema.UpdateDailyAttendanceRequest,
    db: Session = Depends(get_db)
):
    """
    Updates all attendance records for a specific student for the current date.
    Used by the Staff Dashboard Edit popup.
    """
    today = date.today()
    status_lower = req.status.lower()

    if status_lower not in ["present", "absent"]:
        raise HTTPException(status_code=400, detail="Invalid status")

    # Find today's periods where this student was marked
    today_attendances = db.query(models.Attendance).join(models.Period).filter(
        models.Period.date == today,
        models.Attendance.student_id == req.student_id
    ).all()

    if not today_attendances:
        raise HTTPException(status_code=404, detail="No attendance records found for this student today")

    # Update all found records
    for att in today_attendances:
        att.status = status_lower
        
    db.commit()
    
    return {"detail": f"Successfully updated attendance to {req.status}"}

@staff_router.get("/attendance/periods", response_model=List[schema.PeriodResponse])
def get_periods_for_class(
    staff_id: int,
    program: str, 
    year: str, 
    date: date,
    shift: Optional[str] = Query(None, description="Shift to filter periods by"),
    db: Session = Depends(get_db)
):
    staff = db.query(models.Staff).filter(models.Staff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")

    if staff.is_tutor:
        if staff.tutor_program != program or staff.tutor_class_year != year:
            raise HTTPException(
                status_code=403, 
                detail=f"You are assigned to {staff.tutor_program} Year {staff.tutor_class_year}. You cannot edit attendance for {program} Year {year}."
            )

    # Find classes that match program and year AND belong to the staff's department
    classes = db.query(models.ClassModel).filter(
        models.ClassModel.program == program,
        models.ClassModel.year == year,
        models.ClassModel.department_id == staff.department_id
    ).all()
    class_ids = [c.id for c in classes]
    
    if not class_ids:
        return []

    if staff.shift and shift and staff.shift != shift:
        raise HTTPException(
            status_code=403, 
            detail=f"You are assigned to Shift {staff.shift}. You cannot edit attendance for Shift {shift}."
        )

    query = db.query(models.Period).filter(
        models.Period.date == date,
        models.Period.class_id.in_(class_ids)
    )

    if shift == '1':
        query = query.filter(models.Period.start_time < dt_time(14, 0))
    elif shift == '2':
        query = query.filter(models.Period.start_time >= dt_time(14, 0))

    periods = query.all()
    return periods

@staff_router.get("/attendance/periods/{period_id}/previous-present-students", response_model=List[schema.StudentResponse])
def get_previous_present_students(period_id: int, db: Session = Depends(get_db)):
    """
    Finds the students who were present in the last 'conducted' period for the same class on the same day.
    Used by Tutors to pre-populate the attendance marking modal.
    """
    current_period = db.query(models.Period).filter(models.Period.id == period_id).first()
    if not current_period:
        raise HTTPException(status_code=404, detail="Period not found")
        
    # Find previous conducted period for same class and date
    prev_period = db.query(models.Period).filter(
        models.Period.date == current_period.date,
        models.Period.class_id == current_period.class_id,
        models.Period.status == "conducted",
        models.Period.start_time < current_period.start_time
    ).order_by(models.Period.start_time.desc()).first()
    
    if not prev_period:
        return [] # No previous period, return empty
        
    # Get students present in prev_period
    present_attendances = db.query(models.Attendance).filter(
        models.Attendance.period_id == prev_period.id,
        models.Attendance.status == 'present'
    ).all()
    
    student_ids = [a.student_id for a in present_attendances]
    
    if not student_ids:
        return []
        
    students = db.query(models.Student).filter(models.Student.id.in_(student_ids)).all()
    return students

@staff_router.put("/attendance/periods/{period_id}/mark")
def mark_attendance_staff(
    period_id: int, 
    req: schema.MarkAttendanceRequest, 
    shift: str = Query(None, description="Optional shift filter for marking"), 
    staff_id: int = Query(None, description="ID of staff marking attendance"),
    db: Session = Depends(get_db)
):
    period = db.query(models.Period).filter(models.Period.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")
    
    # Look up staff name to save who conducted it
    staff_name = None
    if staff_id:
        staff = db.query(models.Staff).filter(models.Staff.id == staff_id).first()
        if staff:
            staff_name = staff.name

    period.status = "conducted"
    if staff_name:
        period.conducted_by_name = staff_name
    
    # Get students for this class, optionally filtered by shift
    students_query = db.query(models.Student).filter(models.Student.class_id == period.class_id)
    if shift:
        students_query = students_query.filter(models.Student.shift == shift)
        
    class_students = students_query.all()
    
    for student in class_students:
        status = "present" if student.id in req.present_student_ids else "absent"
        existing_att = db.query(models.Attendance).filter(
            models.Attendance.period_id == period_id, 
            models.Attendance.student_id == student.id
        ).first()
        
        if existing_att:
            existing_att.status = status
        else:
            new_att = models.Attendance(period_id=period_id, student_id=student.id, status=status)
            db.add(new_att)
            
    db.commit()
    return {"detail": "Attendance marked successfully"}

@staff_router.post("/attendance/mark-hourly")
def mark_hourly_attendance(
    staff_id: int,
    program: str,
    year: str,
    shift: str,
    req: schema.HourlyAttendanceRequest,
    db: Session = Depends(get_db)
):
    """
    Dynamically marks attendance for a specific hour or full day.
    Instead of relying on pre-existing period rows, this automatically creates the missing Period
    rows for today based on the requested hour/full day.
    """
    staff = db.query(models.Staff).filter(models.Staff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")

    today = date.today()
    
    # 1. Identify the target class
    target_class = db.query(models.ClassModel).filter(
        models.ClassModel.program == program,
        models.ClassModel.year == year
    ).first()
    
    if not target_class:
        raise HTTPException(status_code=404, detail="Class not found for given Program/Year")

    if target_class.department_id != staff.department_id:
        raise HTTPException(status_code=403, detail="Unauthorised. You can only mark attendance for classes in your department.")

    # 1a. Enforce shift-based access: staff can only mark attendance for their own shift
    if staff.shift and staff.shift != shift:
        raise HTTPException(
            status_code=403, 
            detail=f"You are assigned to Shift {staff.shift}. You cannot mark attendance for Shift {shift}."
        )

    # 1b. Check if today is declared a Holiday or Unexpected Leave
    # Check Admin Default Holidays
    is_holiday = db.query(models.Holiday).filter(models.Holiday.date == today).first()
    if is_holiday:
        raise HTTPException(status_code=400, detail=f"Cannot mark attendance. Today is a holiday: {is_holiday.reason}")
        
    # Check Unexpected Leaves (Global or Class Specific)
    is_leave = db.query(models.UnexpectedLeave).filter(
        models.UnexpectedLeave.date == today,
        (models.UnexpectedLeave.class_id == target_class.id) | (models.UnexpectedLeave.class_id == None)
    ).first()
    if is_leave:
        raise HTTPException(status_code=400, detail=f"Cannot mark attendance. Today is declared as a leave: {is_leave.reason}")

    # 2. Get the students to strictly loop over the correct shift
    class_students = db.query(models.Student).filter(
        models.Student.class_id == target_class.id,
        models.Student.shift == shift
    ).all()

    hours_to_mark = [req.hour] if not req.is_full_day else [1, 2, 3, 4, 5]

    # --- Shift-aware period time mappings ---
    from datetime import time
    SHIFT_TIMINGS = {
        "1": {
            "start": {
                1: time(9, 0),
                2: time(9, 50),
                3: time(10, 40),
                4: time(11, 45),
                5: time(12, 35),
            },
            "end": {
                1: time(9, 50),
                2: time(10, 40),
                3: time(11, 30),
                4: time(12, 35),
                5: time(13, 25),
            },
            "break_start": time(11, 30),
            "break_end": time(11, 45),
        },
        "2": {
            "start": {
                1: time(14, 0),
                2: time(14, 50),
                3: time(15, 40),
                4: time(16, 45),
                5: time(17, 35),
            },
            "end": {
                1: time(14, 50),
                2: time(15, 40),
                3: time(16, 30),
                4: time(17, 35),
                5: time(18, 25),
            },
            "break_start": time(16, 30),
            "break_end": time(16, 45),
        },
    }

    # Determine which shift timing to use
    shift_key = shift if shift in SHIFT_TIMINGS else "1"
    timing = SHIFT_TIMINGS[shift_key]

    # --- Break-time blocking ---
    now = datetime.now().time()
    if timing["break_start"] <= now <= timing["break_end"]:
        raise HTTPException(
            status_code=400,
            detail=f"Cannot mark attendance during break time ({timing['break_start'].strftime('%I:%M %p')} – {timing['break_end'].strftime('%I:%M %p')})"
        )

    for h in hours_to_mark:
        target_start = timing["start"].get(h, time(9, 0))
        target_end = timing["end"].get(h, time(10, 0))

        # --- Period-time validation (single hour mode only) ---
        # Staff can only mark attendance DURING the actual period's time window, not before, and not after.
        # Adding a grace period of 10 minutes before and 30 minutes after for flexbility in real world.
        if not req.is_full_day:
            from datetime import timedelta, datetime as dt
            today_dt = dt.now()
            
            # Create full datetime objects for easy timedelta math
            dt_start = dt.combine(today, target_start) - timedelta(minutes=10) # 10 min early allowed
            dt_end = dt.combine(today, target_end) + timedelta(minutes=30)     # 30 min late allowed
            
            if today_dt < dt_start:
                raise HTTPException(
                    status_code=400,
                    detail=f"Period {h} ({target_start.strftime('%I:%M %p')} – {target_end.strftime('%I:%M %p')}) has not started yet."
                )
            if today_dt > dt_end:
                raise HTTPException(
                    status_code=400,
                    detail=f"The window to mark attendance for Period {h} has closed."
                )

        period = db.query(models.Period).filter(
            models.Period.date == today,
            models.Period.class_id == target_class.id,
            models.Period.start_time == target_start
        ).first()

        if not period:
            # We must assign it to a subject. For simple hourly generic tracking, we create a dummy "Hourly Attendance" Subject or pick any
            dummy_subject = db.query(models.Subject).filter(models.Subject.name == "General").first()
            if not dummy_subject:
               dummy_subject = models.Subject(name="General")
               db.add(dummy_subject)
               db.commit()
               db.refresh(dummy_subject)

            period = models.Period(
                class_id=target_class.id,
                subject_id=dummy_subject.id,
                date=today,
                start_time=target_start,
                end_time=target_end,
                status="conducted",
                conducted_by_name=staff.name
            )
            db.add(period)
            db.commit()
            db.refresh(period)
        else:
            period.status = "conducted"
            period.conducted_by_name = staff.name
            db.commit()

        # 3. Apply the Attendances
        for student in class_students:
            status = "present" if student.id in req.present_student_ids else "absent"
            existing_att = db.query(models.Attendance).filter(
                models.Attendance.period_id == period.id,
                models.Attendance.student_id == student.id
            ).first()

            if existing_att:
                existing_att.status = status
            else:
                new_att = models.Attendance(period_id=period.id, student_id=student.id, status=status)
                db.add(new_att)

    db.commit()
    return {"detail": f"Successfully marked {'Full Day' if req.is_full_day else f'Hour {req.hour}'} attendance"}

@staff_router.get("/attendance/today")
def get_today_attendance(
    program: str, 
    year: str, 
    shift: str,
    status: Optional[str] = None, # 'present' or 'absent'
    staff_id: int = Query(None, description="Staff ID to verify tutor permissions"),
    db: Session = Depends(get_db)
):
    if staff_id:
        staff = db.query(models.Staff).filter(models.Staff.id == staff_id).first()
        if staff and staff.is_tutor:
            if staff.tutor_program != program or staff.tutor_class_year != year:
                raise HTTPException(
                    status_code=403, 
                    detail="You can only view today's attendance for your assigned class."
                )

    today = date.today()
    query = db.query(models.Attendance).join(models.Period).join(models.Student).filter(
        models.Period.date == today,
        models.Student.program == program,
        models.Student.year == year,
        models.Student.shift == shift
    )
    
    if status in ["present", "absent"]:
        query = query.filter(models.Attendance.status == status)
        
    attendances = query.all()
    
    # De-duplicate by student: Rule - Present in any period = Present for the day
    result_dict = {}
    for att in attendances:
        sid = att.student.id
        if sid not in result_dict:
            result_dict[sid] = {
                "id": att.student.id,
                "name": att.student.name,
                "reg_no": att.student.reg_no,
                "status": att.status,
                "time": str(att.period.start_time)
            }
        else:
            if att.status == "present":
                result_dict[sid]["status"] = "present"
                result_dict[sid]["time"] = str(att.period.start_time)
        
    return list(result_dict.values())

# ----------------- Timetable Management -----------------
@staff_router.get("/timetable", response_model=List[schema.TimetableEntryResponse])
def get_timetable(
    program: str, 
    year: str, 
    staff_id: int = Query(None, description="Staff ID to verify tutor permissions"),
    db: Session = Depends(get_db)
):
    if staff_id:
        staff = db.query(models.Staff).filter(models.Staff.id == staff_id).first()
        if staff and staff.is_tutor:
            if staff.tutor_program != program or staff.tutor_class_year != year:
                raise HTTPException(
                    status_code=403, 
                    detail="You can only view the timetable for your assigned class."
                )

    # Find class matching program and year
    target_class = db.query(models.ClassModel).filter(
        models.ClassModel.program == program,
        models.ClassModel.year == year
    ).first()
    
    if not target_class:
        return []
        
    return db.query(models.Timetable).filter(models.Timetable.class_id == target_class.id).all()

@staff_router.put("/timetable")
def update_timetable(
    program: str, 
    year: str, 
    entries: List[schema.TimetableEntryCreate], 
    staff_id: int = Query(None, description="Staff ID to verify tutor permissions"),
    db: Session = Depends(get_db)
):
    if staff_id:
        staff = db.query(models.Staff).filter(models.Staff.id == staff_id).first()
        if staff and staff.is_tutor:
            if staff.tutor_program != program or staff.tutor_class_year != year:
                raise HTTPException(
                    status_code=403, 
                    detail="You can only edit the timetable for your assigned class."
                )

    target_class = db.query(models.ClassModel).filter(
        models.ClassModel.program == program,
        models.ClassModel.year == year
    ).first()
    
    if not target_class:
        raise HTTPException(status_code=404, detail="Class not found for given Program/Year")

    # Wipe existing and insert new
    db.query(models.Timetable).filter(models.Timetable.class_id == target_class.id).delete()
    
    new_entries = []
    for entry in entries:
        new_entry = models.Timetable(
            class_id=target_class.id,
            day=entry.day,
            period=entry.period,
            subject_name=entry.subject_name,
            staff_name=entry.staff_name
        )
        new_entries.append(new_entry)
        
    db.add_all(new_entries)
    db.commit()
    return {"detail": "Timetable updated successfully"}

# ----------------- Leave Management (Calendar) -----------------
@staff_router.get("/leaves", response_model=List[schema.LeaveDayResponse])
def get_leave_calendar(
    program: str, 
    year: str, 
    db: Session = Depends(get_db)
):
    """
    Aggregates holidays and unexpected leaves for the given class context.
    Returns days of the current month (Dec 2025 simulated MVP).
    """
    target_class = db.query(models.ClassModel).filter(
        models.ClassModel.program == program,
        models.ClassModel.year == year
    ).first()

    # 1. Base Admin Holidays
    # For MVP we simulate mapping dates strictly as day of month integers, but normally we check date ranges
    # We will cast the date objects back to just their day for the UI
    admin_holidays = db.query(models.Holiday).all()
    
    # 2. Unexpected Leaves (Global and Class Specific)
    global_leaves = db.query(models.UnexpectedLeave).filter(models.UnexpectedLeave.class_id == None).all()
    class_leaves = db.query(models.UnexpectedLeave).filter(models.UnexpectedLeave.class_id == target_class.id).all() if target_class else []

    response = []

    # Map Admin Holidays
    for h in admin_holidays:
        response.append({
            "day": h.date.day,
            "reason": h.reason,
            "type": "Default Holiday"
        })

    # Map Global Leaves
    for gl in global_leaves:
        # Check if already a default holiday
        if not any(r["day"] == gl.date.day for r in response):
            response.append({
                "day": gl.date.day,
                "reason": gl.reason,
                "type": "College Unexpected"
            })

    # Map Class Specific Leaves
    for cl in class_leaves:
        if not any(r["day"] == cl.date.day for r in response):
            response.append({
                "day": cl.date.day,
                "reason": cl.reason,
                "type": "Class Unexpected"
            })

    return response

@staff_router.post("/leaves/declare")
def declare_unexpected_leave(
    req: schema.UnexpectedLeaveCreate,
    db: Session = Depends(get_db)
):
    """
    Declares a leave. Enforces Admin and Tutor access logic.
    """
    # 1. Fetch Staff Information
    staff = db.query(models.Staff).filter(models.Staff.id == req.staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff member not found")

    is_admin = (staff.role == "Admin")
    is_tutor = staff.is_tutor

    if not is_admin and not is_tutor:
        raise HTTPException(status_code=403, detail="Unauthorised. Only Admins or Tutors can declare leaves.")

    # 2. Enforce "ALL" Logic
    target_class_id = None
    if req.target_program == "ALL":
        if not is_admin:
            raise HTTPException(status_code=403, detail="Only Admin can declare College-Wide (ALL) leaves")
    else:
        # Match class
        target_class = db.query(models.ClassModel).filter(
            models.ClassModel.program == req.target_program,
            models.ClassModel.year == req.target_year
        ).first()
        
        if not target_class:
            raise HTTPException(status_code=404, detail="Target class not found")
        
        target_class_id = target_class.id

        # If Tutor but not Admin, ensure they are modifying their exact assigned class
        if not is_admin:
            if staff.tutor_program != req.target_program or staff.tutor_class_year != req.target_year:
                raise HTTPException(status_code=403, detail="Tutors can only declare leaves for their assigned designated class.")

    # For MVP, assuming current month/year is Dec 2025 for simplistic date generation
    month = 12
    year_val = 2025

    new_leaves = []
    from datetime import date as dt_date
    
    for day in range(req.start_date, req.end_date + 1):
        target_date = dt_date(year_val, month, day)

        # 1. Check if Default Holiday
        is_holiday = db.query(models.Holiday).filter(models.Holiday.date == target_date).first()
        if is_holiday:
            raise HTTPException(status_code=400, detail=f"Day {day} is already an Admin Holiday: {is_holiday.reason}")

        # 2. Check if identical global/class leave already exists
        existing_leave = db.query(models.UnexpectedLeave).filter(
            models.UnexpectedLeave.date == target_date,
            models.UnexpectedLeave.class_id == target_class_id
        ).first()

        if not existing_leave:
            new_leave = models.UnexpectedLeave(
                date=target_date,
                reason=req.reason,
                class_id=target_class_id,
                shift=staff.shift if not (req.target_program == "ALL") else None
            )
            new_leaves.append(new_leave)

    if new_leaves:
        db.add_all(new_leaves)
        db.commit()

    return {"detail": f"Leave successfully declared from day {req.start_date} to {req.end_date}"}

@staff_router.get("/daily-updates", response_model=List[schema.DailyUpdateResponse])
def get_daily_updates(
    role: str = "Student",
    program: Optional[str] = None,
    year: Optional[str] = None,
    shift: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Returns a unified list of UnexpectedLeaves based on role-based access constraints.
    - Admin: Sees all leaves (Global + All Classes)
    - Tutor/Student: Sees Global Leaves (class_id = null) + Leaves specific to their Class
    Shift filtering: only shows leaves matching the given shift or college-wide (shift=null)
    """
    query = db.query(models.UnexpectedLeave).order_by(models.UnexpectedLeave.date.desc())

    if role.upper() not in ["ADMIN"]:
        # Standard Staff/Student Rule: Filter by explicit class assignment OR Global (Null)
        if program and year:
            target_class = db.query(models.ClassModel).filter(
                models.ClassModel.program == program,
                models.ClassModel.year == year
            ).first()
            
            if target_class:
                query = query.filter(
                    (models.UnexpectedLeave.class_id == target_class.id) | 
                    (models.UnexpectedLeave.class_id == None)
                )
            else:
                # If no valid class found for the given string parameters, only return Globals
                query = query.filter(models.UnexpectedLeave.class_id == None)
        else:
             # Just return global
             query = query.filter(models.UnexpectedLeave.class_id == None)

    # Shift filtering: show only leaves matching the given shift OR college-wide (null shift)
    if shift:
        query = query.filter(
            (models.UnexpectedLeave.shift == shift) | 
            (models.UnexpectedLeave.shift == None)
        )

    leaves = query.all()
    
    response = []
    for l in leaves:
        target_str = "College-Wide"
        if l.class_id:
             # It's a localized class leave 
             c_model = db.query(models.ClassModel).filter(models.ClassModel.id == l.class_id).first()
             if c_model:
                 target_str = f"{c_model.program} Year {c_model.year}"
        
        response.append(
            schema.DailyUpdateResponse(
                id=l.id,
                date=l.date,
                reason=l.reason,
                target=target_str
            )
        )
        
    return response
