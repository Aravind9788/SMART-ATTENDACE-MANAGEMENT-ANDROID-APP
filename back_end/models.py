from sqlalchemy import Column, Integer, String, Boolean, ForeignKey, Date, Time, Float
from sqlalchemy.orm import relationship
from database import Base

class Department(Base):
    __tablename__ = "departments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), unique=True, index=True, nullable=False)
    head = Column(String(100), nullable=True)

    staff = relationship("Staff", back_populates="department")
    classes = relationship("ClassModel", back_populates="department")

class Staff(Base):
    __tablename__ = "staff"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password = Column(String(100), nullable=False)
    department_id = Column(Integer, ForeignKey("departments.id"))
    role = Column(String(50)) # e.g., 'Admin', 'Staff'
    shift = Column(String(10)) # e.g., '1', '2'
    
    # Security properties
    security_question = Column(String(200), nullable=True)
    security_answer = Column(String(200), nullable=True)
    password_changed = Column(Boolean, default=False)
    
    # Tutor details
    is_tutor = Column(Boolean, default=False)
    tutor_class_year = Column(String(10), nullable=True) # e.g., '1st', '2nd', '3rd'
    tutor_program = Column(String(10), nullable=True)    # e.g., 'UG', 'PG'
    tutor_shift = Column(String(10), nullable=True)      # e.g., '1', '2'

    department = relationship("Department", back_populates="staff")

class ClassModel(Base):
    __tablename__ = "classes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(50), nullable=False) # e.g., "CSE - Year 2 - A"
    program = Column(String(10)) # 'UG' or 'PG'
    year = Column(String(10)) # '1', '2', '3'
    department_id = Column(Integer, ForeignKey("departments.id"), nullable=True)

    allocations = relationship("SubjectAllocation", back_populates="class_")
    students = relationship("Student", back_populates="class_")
    periods = relationship("Period", back_populates="class_")
    department = relationship("Department", back_populates="classes")

class Subject(Base):
    __tablename__ = "subjects"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)

    allocations = relationship("SubjectAllocation", back_populates="subject")
    periods = relationship("Period", back_populates="subject")

class SubjectAllocation(Base):
    __tablename__ = "subject_allocations"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)

    class_ = relationship("ClassModel", back_populates="allocations")
    subject = relationship("Subject", back_populates="allocations")

class Student(Base):
    __tablename__ = "students"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    reg_no = Column(String(50), unique=True, index=True, nullable=False)
    password = Column(String(100), nullable=True)
    program = Column(String(10))
    year = Column(String(10))
    shift = Column(String(10))
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=True)

    class_ = relationship("ClassModel", back_populates="students")
    attendances = relationship("Attendance", back_populates="student")

class Holiday(Base):
    __tablename__ = "holidays"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, unique=True, nullable=False)
    reason = Column(String(200), nullable=False)

class UnexpectedLeave(Base):
    __tablename__ = "unexpected_leaves"

    id = Column(Integer, primary_key=True, index=True)
    date = Column(Date, nullable=False)
    reason = Column(String(200), nullable=False)
    
    # Optional mapping. If null, implies "ALL" College leave.
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=True) 
    
    # Shift filter. If null, applies to all shifts (college-wide). '1' or '2' for shift-specific.
    shift = Column(String(10), nullable=True)

    class_ = relationship("ClassModel")

class Period(Base):
    __tablename__ = "periods"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    subject_id = Column(Integer, ForeignKey("subjects.id"), nullable=False)
    date = Column(Date, nullable=False)
    start_time = Column(Time, nullable=False)
    end_time = Column(Time, nullable=False)
    status = Column(String(20), default="pending") # 'pending', 'conducted'
    conducted_by_name = Column(String(100), nullable=True) # Name of staff who marked attendance


    class_ = relationship("ClassModel", back_populates="periods")
    subject = relationship("Subject", back_populates="periods")
    attendances = relationship("Attendance", back_populates="period")

class Timetable(Base):
    __tablename__ = "timetables"

    id = Column(Integer, primary_key=True, index=True)
    class_id = Column(Integer, ForeignKey("classes.id"), nullable=False)
    day = Column(String(15), nullable=False) # e.g. Mon, Tue
    period = Column(Integer, nullable=False) # 1, 2, 3..
    subject_name = Column(String(100), nullable=False)
    staff_name = Column(String(100), nullable=True)

    class_ = relationship("ClassModel")

class Attendance(Base):
    __tablename__ = "attendances"

    id = Column(Integer, primary_key=True, index=True)
    period_id = Column(Integer, ForeignKey("periods.id"), nullable=False)
    student_id = Column(Integer, ForeignKey("students.id"), nullable=False)
    status = Column(String(20), default="present") # 'present', 'absent'

    period = relationship("Period", back_populates="attendances")
    student = relationship("Student", back_populates="attendances")
