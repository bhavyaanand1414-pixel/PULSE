from sqlalchemy.orm import DeclarativeBase #foundation for the classes
from sqlalchemy import Column,Integer,String,DateTime
class Base(DeclarativeBase): #inherits class for foundation 
    pass #no additional code needed right now
class Endpoint(Base):
    __tablename__="endpoints"#double underscore are called dunders
    id=Column(Integer,primary_key=True)
    name=Column(String,nullable=False)
    url=Column(String,nullable=False)
    created_at=Column(DateTime,nullable=False)
