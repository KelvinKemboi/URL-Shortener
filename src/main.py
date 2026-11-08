from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI
from sqlmodel import Field, SQLModel, create_engine, Session


class Link(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    short_code: str = Field(index=True, unique=True)
    original_url: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    
# create the database engine, and connect to the SQLite database
engine = create_engine("sqlite:///database.db", connect_args={"check_same_thread": False}) 

def create_db_and_tables():
    SQLModel.metadata.create_all(engine)

# get a session to interact with the database
def get_session():
    with Session(engine) as session:
        yield session

# runs once when the app starts (before the yield) and once when it shuts down (after)
@asynccontextmanager
async def lifespan(app: FastAPI):
    create_db_and_tables()
    yield

app = FastAPI(lifespan=lifespan)

# get, post, put, delete, patch, options, head, trace
# use async def for async functions where you can use await for async calls
@app.get("/")
def example():
    return {"Hello": "World"}