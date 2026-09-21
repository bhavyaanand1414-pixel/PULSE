from sqlalchemy import create_engine 
from dotenv import load_dotenv
import os
from models import Base
load_dotenv()
DATABASE_URL = os.getenv("DATABASE_URL")
engine=create_engine(DATABASE_URL)
#with engine.connect() as connection : #temporary connection to check if it it connected or not 
    #print("Database connection successful!")
Base.metadata.create_all(engine)