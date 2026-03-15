from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date

from database import get_db
import models, schema

admin_router = APIRouter()

# ----------------- Dashboard -----------------
@admin_router.get("/dashboard-stats", response_model=schema.DashboardStats)
def get_dashboard_stats(admin_id: int = None, db: Session = Depends(get_db)):
    staff_count = db.query(models.Staff).count()
    student_count = db.query(models.Student).count()
    dept_count = db.query(models.Department).count()
    
    response_data = {
        "total_staff": staff_count, 
        "total_students": student_count, 
        "total_departments": dept_count
    }
    
    if admin_id:
        admin = db.query(models.Staff).filter(models.Staff.id == admin_id).first()
        if admin:
            response_data["role"] = admin.role
            response_data["admin_name"] = admin.name
            if admin.department:
                response_data["department_name"] = admin.department.name

    return response_data


# ----------------- Departments -----------------
@admin_router.get("/departments", response_model=List[schema.DepartmentResponse])
def get_departments(db: Session = Depends(get_db)):
    return db.query(models.Department).all()

@admin_router.post("/departments", response_model=schema.DepartmentResponse)
def create_department(dept: schema.DepartmentCreate, db: Session = Depends(get_db)):
    db_dept = models.Department(name=dept.name, head=dept.head)
    db.add(db_dept)
    db.commit()
    db.refresh(db_dept)
    return db_dept

# ----------------- Staff -----------------
@admin_router.get("/staff", response_model=List[schema.StaffResponse])
def get_staff(admin_id: int = Query(..., description="ID of the HOD fetching the staff"), db: Session = Depends(get_db)):
    admin = db.query(models.Staff).filter(models.Staff.id == admin_id).first()
    if not admin or not admin.department_id:
        return []
    
    return db.query(models.Staff).filter(models.Staff.department_id == admin.department_id).all()

@admin_router.post("/staff", response_model=schema.StaffResponse)
def create_staff(staff: schema.StaffCreate, admin_id: int = Query(..., description="ID of the HOD creating this staff"), db: Session = Depends(get_db)):
    # Get the admin's department
    admin = db.query(models.Staff).filter(models.Staff.id == admin_id).first()
    if not admin or not admin.department_id:
        raise HTTPException(status_code=400, detail="Creating admin must be assigned to a department first")
    
    # 1 department = 1 HOD: Force staff to belong to the HOD's department
    staff_data = staff.dict()
    staff_data['department_id'] = admin.department_id

    db_staff = models.Staff(**staff_data)
    db.add(db_staff)
    db.commit()
    db.refresh(db_staff)
    return db_staff

@admin_router.delete("/staff/{staff_id}")
def delete_staff(staff_id: int, db: Session = Depends(get_db)):
    staff = db.query(models.Staff).filter(models.Staff.id == staff_id).first()
    if not staff:
        raise HTTPException(status_code=404, detail="Staff not found")
    db.delete(staff)
    db.commit()
    return {"detail": "Deleted successfully"}


# ----------------- Subject Allocation -----------------
@admin_router.get("/allocations", response_model=List[schema.SubjectAllocationResponse])
def get_allocations(db: Session = Depends(get_db)):
    return db.query(models.SubjectAllocation).all()

@admin_router.post("/allocations", response_model=schema.SubjectAllocationResponse)
def create_allocation(allocation: schema.SubjectAllocationCreate, db: Session = Depends(get_db)):
    db_allocation = models.SubjectAllocation(**allocation.dict())
    db.add(db_allocation)
    db.commit()
    db.refresh(db_allocation)
    return db_allocation

@admin_router.delete("/allocations/{allocation_id}")
def delete_allocation(allocation_id: int, db: Session = Depends(get_db)):
    alloc = db.query(models.SubjectAllocation).filter(models.SubjectAllocation.id == allocation_id).first()
    if not alloc:
        raise HTTPException(status_code=404, detail="Allocation not found")
    db.delete(alloc)
    db.commit()
    return {"detail": "Deleted successfully"}


# ----------------- Helper endpoints for Dropdowns -----------------
@admin_router.get("/classes", response_model=List[schema.ClassResponse])
def get_classes(db: Session = Depends(get_db)):
    return db.query(models.ClassModel).all()

@admin_router.post("/classes", response_model=schema.ClassResponse)
def create_class(class_data: schema.ClassCreate, db: Session = Depends(get_db)):
    db_class = models.ClassModel(**class_data.dict())
    db.add(db_class)
    db.commit()
    db.refresh(db_class)
    return db_class

@admin_router.get("/subjects", response_model=List[schema.SubjectResponse])
def get_subjects(db: Session = Depends(get_db)):
    return db.query(models.Subject).all()


# ----------------- Holidays -----------------
@admin_router.get("/holidays", response_model=List[schema.HolidayResponse])
def get_holidays(db: Session = Depends(get_db)):
    return db.query(models.Holiday).order_by(models.Holiday.date).all()

@admin_router.post("/holidays", response_model=schema.HolidayResponse)
def create_holiday(holiday: schema.HolidayCreate, db: Session = Depends(get_db)):
    db_holiday = models.Holiday(**holiday.dict())
    db.add(db_holiday)
    db.commit()
    db.refresh(db_holiday)
    return db_holiday

@admin_router.delete("/holidays/{holiday_id}")
def delete_holiday(holiday_id: int, db: Session = Depends(get_db)):
    holiday = db.query(models.Holiday).filter(models.Holiday.id == holiday_id).first()
    if not holiday:
        raise HTTPException(status_code=404, detail="Holiday not found")
    db.delete(holiday)
    db.commit()
    return {"detail": "Deleted successfully"}


# ----------------- Attendance Management -----------------
@admin_router.get("/attendance/periods", response_model=List[schema.PeriodResponse])
def get_periods_for_date(target_date: date, db: Session = Depends(get_db)):
    periods = db.query(models.Period).filter(models.Period.date == target_date).all()
    return periods

@admin_router.get("/attendance/periods/{period_id}/previous-present-students", response_model=List[schema.StudentResponse])
def get_previous_present_students(period_id: int, db: Session = Depends(get_db)):
    """
    Finds the students who were present in the last 'conducted' period for the same class on the same day.
    """
    current_period = db.query(models.Period).filter(models.Period.id == period_id).first()
    if not current_period:
        raise HTTPException(status_code=404, detail="Period not found")
        
    prev_period = db.query(models.Period).filter(
        models.Period.date == current_period.date,
        models.Period.class_id == current_period.class_id,
        models.Period.status == "conducted",
        models.Period.start_time < current_period.start_time
    ).order_by(models.Period.start_time.desc()).first()
    
    if not prev_period:
        return [] 
        
    present_attendances = db.query(models.Attendance).filter(
        models.Attendance.period_id == prev_period.id,
        models.Attendance.status == 'present'
    ).all()
    
    student_ids = [a.student_id for a in present_attendances]
    
    if not student_ids:
        return []
        
    students = db.query(models.Student).filter(models.Student.id.in_(student_ids)).all()
    return students

@admin_router.put("/attendance/periods/{period_id}/mark")
def mark_attendance(period_id: int, req: schema.MarkAttendanceRequest, db: Session = Depends(get_db)):
    period = db.query(models.Period).filter(models.Period.id == period_id).first()
    if not period:
        raise HTTPException(status_code=404, detail="Period not found")
    
    # 1. Update period status
    period.status = "conducted"
    
    # 2. Get all students in the class
    class_students = db.query(models.Student).filter(models.Student.class_id == period.class_id).all()
    
    # 3. Create attendance records
    for student in class_students:
        status = "present" if student.id in req.present_student_ids else "absent"
        # Check if record already exists, if so update it, else create
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

# ----------------- Auth & Setup -----------------

@admin_router.get("/check-setup")
def check_admin_setup(admin_id: int = Query(..., description="ID of the checking Admin"), db: Session = Depends(get_db)):
    """
    Lightweight guard endpoint. Returns whether the admin has completed first-time setup.
    """
    admin = db.query(models.Staff).filter(models.Staff.id == admin_id, models.Staff.role == 'Admin').first()
    if not admin:
        return {"id": admin_id, "is_setup_complete": False}

    is_setup = bool(admin.department_id and admin.security_question and admin.password_changed)
    return {"id": admin.id, "is_setup_complete": is_setup}

@admin_router.post("/setup")
def initial_admin_setup(
    req: schema.AdminSetupRequest,
    db: Session = Depends(get_db)
):
    """
    Called by the React Native SettingsScreen "First Time Setup".
    This dynamically creates a NEW HOD since any HOD can use the admin/admin123 gateway.
    """
    # Find or create department
    dept = db.query(models.Department).filter(models.Department.name == req.department_name).first()
    if not dept:
        dept = models.Department(name=req.department_name, head=req.admin_name)
        db.add(dept)
        db.commit()
        db.refresh(dept)

    # Check if username exists
    existing_user = db.query(models.Staff).filter(models.Staff.username == req.admin_username).first()
    if existing_user:
        raise HTTPException(status_code=400, detail="Username already exists. Please pick another username.")

    # Create new HOD account dynamically
    new_admin = models.Staff(
        name=req.admin_name,
        username=req.admin_username,
        password=req.new_password,
        department_id=dept.id,
        role='Admin',
        security_question=req.security_question,
        security_answer=req.security_answer,
        password_changed=True
    )
    db.add(new_admin)
    db.commit()
    return {"detail": "Admin setup completed successfully."}

@admin_router.post("/reset-password")
def reset_admin_password(
    req: schema.AdminPasswordResetRequest,
    db: Session = Depends(get_db)
):
    """
    Called by SettingsScreen "Forgot Password". Evaluates the security answer.
    """
    admin = db.query(models.Staff).filter(models.Staff.username == req.username, models.Staff.role == 'Admin').first()
    if not admin:
        raise HTTPException(status_code=404, detail="HOD account not found.")

    if not admin.security_answer or admin.security_answer.lower() != req.security_answer.lower():
        raise HTTPException(status_code=403, detail="Incorrect security answer.")

    admin.password = req.new_password
    db.commit()
    return {"detail": "Password reset successfully."}

@admin_router.post("/login", response_model=schema.LoginResponse)
def login(req: schema.LoginRequest, db: Session = Depends(get_db)):
    """
    Universal login handler — Dynamic DB-based authentication.
    Admin can login with hardcoded admin/admin123 OR their DB credentials.
    Staff and Students must use their assigned DB credentials.
    """
    # 1. Universal HOD Gateway (admin/admin123 acts as an infinite backdoor to Setup)
    if req.username == "admin" and req.password == "admin123":
        return {
            "id": 0,
            "name": "New HOD Gateway",
            "role": "Admin",
            "is_setup_complete": False,
            "password_changed": False
        }

    # 2. Try Staff login (username + password from DB)
    staff = db.query(models.Staff).filter(
        models.Staff.username == req.username,
        models.Staff.password == req.password
    ).first()

    if staff:
        is_setup = True
        pwd_changed = bool(staff.password_changed)
        if staff.role == "Admin":
            if not staff.department_id or not staff.security_question or not staff.password_changed:
                is_setup = False
        return {
            "id": staff.id,
            "name": staff.name,
            "role": staff.role,
            "is_setup_complete": is_setup,
            "password_changed": pwd_changed
        }

    # 3. Try Student login (reg_no as username + password from DB)
    student = db.query(models.Student).filter(
        models.Student.reg_no == req.username,
        models.Student.password == req.password
    ).first()

    if student:
        return {
            "id": student.id,
            "name": student.name,
            "role": "Student",
            "is_setup_complete": True,
            "password_changed": True
        }

    raise HTTPException(status_code=401, detail="Invalid username or password")

@admin_router.get("/attendance/history")
def get_attendance_history(target_date: date, status: Optional[str] = None, db: Session = Depends(get_db)):
    """
    Fetch attendance history for a specific date, aggregated per student.
    Rule: Present in ANY period = Present for the day. Absent in ALL periods = Full-day Absent.
    """
    attendances = db.query(models.Attendance).join(models.Period).filter(
        models.Period.date == target_date
    ).all()

    # Aggregate per student
    student_map = {}  # {student_id: {"info": {...}, "total": N, "absent": N}}
    for att in attendances:
        sid = att.student_id
        if sid not in student_map:
            student_map[sid] = {
                "info": {
                    "id": att.student.id if att.student else 0,
                    "student_name": att.student.name if att.student else "Unknown",
                    "reg_no": att.student.reg_no if att.student else "Unknown",
                },
                "total": 0,
                "absent": 0
            }
        student_map[sid]["total"] += 1
        if att.status == "absent":
            student_map[sid]["absent"] += 1

    # Build result with full-day logic
    result = []
    for sid, data in student_map.items():
        is_full_day_absent = (data["total"] > 0 and data["absent"] == data["total"])
        daily_status = "absent" if is_full_day_absent else "present"
        result.append({
            **data["info"],
            "status": daily_status,
            "date": str(target_date)
        })

    # Filter by status if requested
    if status in ["present", "absent"]:
        result = [r for r in result if r["status"] == status]

    present_count = sum(1 for r in student_map.values() if not (r["total"] > 0 and r["absent"] == r["total"]))
    absent_count = sum(1 for r in student_map.values() if r["total"] > 0 and r["absent"] == r["total"])

    return {
        "records": result,
        "summary": {
            "present": present_count,
            "absent": absent_count,
            "total": len(student_map)
        }
    }

# ----------------- Timetable Management (Admin View) -----------------
@admin_router.get("/active-classes", response_model=List[schema.ActiveClassResponse])
def get_active_classes(db: Session = Depends(get_db)):
    """
    Returns unique classes currently assigned to a Class Tutor.
    """
    tutors = db.query(models.Staff).filter(models.Staff.is_tutor == True).all()
    
    active_classes = []
    for tutor in tutors:
        # Resolve class if program and year are set
        if tutor.tutor_program and tutor.tutor_class_year:
            target_class = db.query(models.ClassModel).filter(
                models.ClassModel.program == tutor.tutor_program,
                models.ClassModel.year == tutor.tutor_class_year
            ).first()
            
            if target_class:
                class_str = f"{tutor.tutor_program} - Year {tutor.tutor_class_year}"
                if tutor.tutor_shift:
                    class_str += f" - Shift {tutor.tutor_shift}"
                    
                active_classes.append({
                    "class_id": target_class.id,
                    "class_name": class_str,
                    "tutor_name": tutor.name,
                    "created_by": tutor.name # Assumed tutor is the one creating it for now
                })
                
    return active_classes

@admin_router.get("/timetable/class/{class_id}", response_model=List[schema.TimetableEntryResponse])
def get_admin_timetable(class_id: int, db: Session = Depends(get_db)):
    """
    Allows Admin to view the timetable grid for any specific class.
    """
    target_class = db.query(models.ClassModel).filter(
        models.ClassModel.id == class_id
    ).first()
    
    if not target_class:
        return []
        
    return db.query(models.Timetable).filter(models.Timetable.class_id == target_class.id).all()

# ----------------- Reports -----------------
@admin_router.get("/reports/attendance")
def get_attendance_reports(program: Optional[str] = None, year: Optional[str] = None, shift: Optional[str] = None, date_from: Optional[date] = None, db: Session = Depends(get_db)):
    """Calculate attendance percentages for students, optionally filtered by date range"""
    query = db.query(models.Student)
    if program:
        query = query.filter(models.Student.program == program)
    if year:
        query = query.filter(models.Student.year == year)
    if shift:
        query = query.filter(models.Student.shift == shift)
        
    students = query.all()
    
    report_data = []
    for student in students:
        att_query = db.query(models.Attendance).filter(models.Attendance.student_id == student.id)
        if date_from:
            att_query = att_query.join(models.Period).filter(models.Period.date >= date_from)
        
        total_classes = att_query.count()
        present_query = att_query.filter(models.Attendance.status == 'present')
        present_classes = present_query.count()
        
        percentage = (present_classes / total_classes * 100) if total_classes > 0 else 0
        
        report_data.append({
            "id": student.id,
            "name": student.name,
            "reg_no": student.reg_no,
            "program": student.program,
            "year": student.year,
            "shift": student.shift,
            "percentage": round(percentage, 2)
        })
        
    return report_data
