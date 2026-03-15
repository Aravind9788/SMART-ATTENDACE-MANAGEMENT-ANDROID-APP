import os
import sqlalchemy
from dotenv import load_dotenv

# Ensure we import the models so Base knows about them when create_all runs
import models
from database import engine, Base, SessionLocal
from models import Staff

def build_and_seed_db():
    print("Building full database schema...")
    Base.metadata.create_all(bind=engine)
    print("Schema built.")
    
    db = SessionLocal()
    try:
        admin = db.query(Staff).filter(Staff.role == 'Admin').first()
        if not admin:
            print("Creating default Admin account...")
            new_admin = Staff(
                name="System Admin", 
                username="admin", 
                password="123", 
                role="Admin"
            )
            db.add(new_admin)
            db.commit()
            print("Admin created.")
        else:
            print("Admin account already exists.")
            
    except Exception as e:
        print(f"Error seeding database: {e}")
    finally:
        db.close()

if __name__ == '__main__':
    build_and_seed_db()
