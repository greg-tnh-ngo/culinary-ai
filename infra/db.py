from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

# Replace with your actual DB URL
DATABASE_URL = "postgresql://user:password@localhost:5432/mydatabase"

# Create engine
engine = create_engine(DATABASE_URL, echo=True)

# Create a sessionmaker factory
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class for your models
Base = declarative_base()
