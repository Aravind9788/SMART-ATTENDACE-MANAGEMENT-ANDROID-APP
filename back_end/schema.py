from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import date, time

# -- Department Schemas --
class DepartmentBase(BaseModel):
    name: str = Field(..., max_length=50)
    head: Optional[str] = Field(None, max_length=100)

class DepartmentCreate(DepartmentBase):
    pass

class DepartmentResponse(DepartmentBase):
    id: int

    class Config:
        from_attributes = True

# -- Staff Schemas --
class StaffBase(BaseModel):
    name: str = Field(..., max_length=100)
    username: str = Field(..., max_length=50)
    department_id: Optional[int] = None
    role: Optional[str] = Field(None, max_length=50)
    shift: Optional[str] = Field(None, max_length=10)
    is_tutor: bool = False
    tutor_class_year: Optional[str] = Field(None, max_length=10)
    tutor_program: Optional[str] = Field(None, max_length=10)
    tutor_shift: Optional[str] = Field(None, max_length=10)
    
class StaffCreate(StaffBase):
    password: str = Field(..., max_length=100)

class StaffResponse(StaffBase):
    id: int
    department: Optional[DepartmentResponse] = None

    class Config:
        from_attributes = True

# -- Subject Schemas --
class SubjectBase(BaseModel):
    name: str = Field(..., max_length=100)

class SubjectCreate(SubjectBase):
    pass

class SubjectResponse(SubjectBase):
    id: int

    class Config:
        from_attributes = True

# -- Class Schemas --
class ClassBase(BaseModel):
    name: str = Field(..., max_length=50)
    program: Optional[str] = Field(None, max_length=10)
    year: Optional[str] = Field(None, max_length=10)
    department_id: Optional[int] = None

class ClassCreate(ClassBase):
    pass

class ClassResponse(ClassBase):
    id: int
    department: Optional[DepartmentResponse] = None

    class Config:
        from_attributes = True


# -- Subject Allocation Schemas --
class SubjectAllocationBase(BaseModel):
    class_id: int
    subject_id: int

class SubjectAllocationCreate(SubjectAllocationBase):
    pass

class SubjectAllocationResponse(SubjectAllocationBase):
    id: int
    class_: Optional[ClassResponse] = None
    subject: Optional[SubjectResponse] = None

    class Config:
        from_attributes = True


# -- Student Schemas --
class StudentBase(BaseModel):
    name: str = Field(..., max_length=100)
    reg_no: str = Field(..., max_length=50)
    password: Optional[str] = Field(None, max_length=100)
    program: Optional[str] = Field(None, max_length=10)
    year: Optional[str] = Field(None, max_length=10)
    shift: Optional[str] = Field(None, max_length=10)
    class_id: Optional[int] = None

class StudentResponse(StudentBase):
    id: int

    class Config:
        from_attributes = True


# -- Holiday Schemas --
class HolidayBase(BaseModel):
    date: date
    reason: str = Field(..., max_length=200)

class HolidayCreate(HolidayBase):
    pass

class HolidayResponse(HolidayBase):
    id: int

    class Config:
        from_attributes = True


# -- Period & Attendance Schemas --
class PeriodBase(BaseModel):
    class_id: int
    subject_id: int
    date: date
    start_time: time
    end_time: time
    status: str = "pending"

class PeriodResponse(PeriodBase):
    id: int
    subject: Optional[SubjectResponse] = None
    conducted_by_name: Optional[str] = None

    class Config:
        from_attributes = True


class AttendanceBase(BaseModel):
    period_id: int
    student_id: int
    status: str = "present"

class UpdateDailyAttendanceRequest(BaseModel):
    student_id: int
    status: str # "Present" or "Absent"

class TimetableEntryBase(BaseModel):
    class_id: int
    day: str
    period: int
    subject_name: str
    staff_name: Optional[str] = None

class TimetableEntryCreate(TimetableEntryBase):
    pass

class TimetableEntryResponse(TimetableEntryBase):
    id: int

    class Config:
        from_attributes = True

class UnexpectedLeaveCreate(BaseModel):
    staff_id: int
    start_date: int # Day of month
    end_date: int   # Day of month
    reason: str
    target_program: str # "ALL", "UG", "PG"
    target_year: str # '1', '2', '3'

class LeaveDayResponse(BaseModel):
    day: int
    reason: str
    type: str # "Default Holiday", "College Unexpected", "Class Unexpected"

class LoginRequest(BaseModel):
    username: str
    password: str

class LoginResponse(BaseModel):
    id: int
    name: str
    role: str
    is_setup_complete: bool
    password_changed: bool

# -- Admin Security Schemas --
class AdminSetupRequest(BaseModel):
    department_name: str
    admin_name: str
    admin_username: str
    new_password: str
    security_question: str
    security_answer: str

class AdminPasswordResetRequest(BaseModel):
    username: str
    security_answer: str
    new_password: str

class DailyUpdateResponse(BaseModel):
    id: int
    date: date
    reason: str
    target: str # "College-Wide" or "Class Specific"

class StudentAttendancePercentage(BaseModel):
    id: int
    name: str
    reg_no: str
    total_conducted: int
    total_present: int
    percent: int
    color: str

class MarkAttendanceRequest(BaseModel):
    present_student_ids: List[int]

class HourlyAttendanceRequest(BaseModel):
    hour: int = 1
    is_full_day: bool = False
    present_student_ids: List[int]

class DashboardStats(BaseModel):
    total_staff: int
    total_students: int
    total_departments: int
    role: Optional[str] = None
    department_name: Optional[str] = None
    admin_name: Optional[str] = None

# -- All Timetables Overview Schema (Admin) --
class ActiveClassResponse(BaseModel):
    class_id: int
    class_name: str
    tutor_name: str
    created_by: str

# -- Staff Dashboard Schemas --
class StaffAttendanceRecord(BaseModel):
    id: int
    name: str
    reg_no: str
    status: str
    
class StaffDashboardStats(BaseModel):
    admin_name: str
    role: str
    staff_department: Optional[str] = None
    staff_shift: Optional[str] = None
    is_tutor: bool
    tutor_program: Optional[str] = None
    tutor_year: Optional[str] = None
    tutor_shift: Optional[str] = None
    total_students: int
    present_today: int
    absent_today: int
    recent_records: List[StaffAttendanceRecord]

# -- Student Dashboard Schemas --
class MonthlySummary(BaseModel):
    present: int
    absent: int
    totalHours: int

class StudentDashboardOverview(BaseModel):
    id: str
    name: str
    role: str
    program: Optional[str] = None
    year: Optional[str] = None
    shift: Optional[str] = None
    attendancePercentage: int
    todayStatus: str
    monthlySummary: MonthlySummary

class StudentTimetableEntry(BaseModel):
    id: str
    time: str
    subject: str
    staff: str
    room: str
