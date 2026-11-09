from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends, Request
from sqlmodel import Field, SQLModel, create_engine, Session, select
from fastapi.responses import RedirectResponse
from sqlalchemy import func
import secrets
import string
from pydantic import BaseModel, HttpUrl

# define the Pydantic model for the request body
class LinkCreate(BaseModel):
    original_url: HttpUrl
    custom_alias: str | None = None

# define the SQLModel for the database table
class Link(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    short_code: str = Field(index=True, unique=True)
    original_url: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

# define the SQLModel for the clicks table
class clicks(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    link_id: int = Field(foreign_key="link.id", index=True)
    clicked_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

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

# helper function to generate a unique short code
def generate_short_code(session: Session, length: int = 7) -> str:
    characters = string.ascii_letters + string.digits
    while True:
        #generate a random short code of the specified length
        short_code = ''.join(secrets.choice(characters) for _ in range(length))

        #check if the generated short code already exists in the database
        existing_link = session.exec(select(Link).where(Link.short_code == short_code)).first()
        if not existing_link:
            return short_code


app = FastAPI(lifespan=lifespan)

# endpoint to shorten a URL and return the short code and short URL
@app.post("/shorten")
def shorten_url(data: LinkCreate, request: Request, session: Session = Depends(get_session)):
    # check if the original URL already exists in the database
    original_url = str(data.original_url)
    custom_alias = data.custom_alias
    existing_link = session.exec(select(Link).where(Link.original_url == original_url)).first()
    if existing_link:
        return {"short_code": existing_link.short_code, "short_url": f"{request.base_url}{existing_link.short_code}"}

    # generate a unique short code for the new URL
    if custom_alias:
        # check if valid
        if custom_alias.replace('_', '').isalnum() and len(custom_alias) <= 20:
            # check if the custom alias already exists in the database
            existing_link = session.exec(select(Link).where(Link.short_code == custom_alias)).first()
            if existing_link:
                raise HTTPException(status_code=400, detail="Custom alias already exists")
            short_code = custom_alias
        else:
            raise HTTPException(status_code=422, detail="Invalid custom alias")
    else:
        short_code = generate_short_code(session)
    
    # create a new Link object and add it to the database
    new_link = Link(short_code=short_code, original_url=original_url)
    session.add(new_link)
    session.commit()
    session.refresh(new_link) 

    return {"short_code": new_link.short_code, "short_url": f"{request.base_url}{new_link.short_code}"}

# endpoint to redirect to the original URL when a short code is accessed
@app.get("/{short_code}")
def redirect_to_original_url(short_code: str, session: Session = Depends(get_session)):
    # check if the short code exists in the database
    link = session.exec(select(Link).where(Link.short_code == short_code)).first()
    if link is None:
        raise HTTPException(status_code=404, detail="Short code not found")

    if link.id is None:
        raise HTTPException(status_code=404, detail="Link ID not found")

    # record the click in the clicks table
    click = clicks(link_id=link.id)
    session.add(click)
    session.commit()
    return RedirectResponse(url=link.original_url, status_code=307) # use 307 to preserve the original request method and body

# endpoint to get the click statistics for a given short code
@app.get("/stats/{short_code}")
def get_click_stats(short_code: str, session: Session = Depends(get_session)):
    # check if the short code exists in the database
    link = session.exec(select(Link).where(Link.short_code == short_code)).first()
    if link is None:
        raise HTTPException(status_code=404, detail="Short code not found")

    # get the total number of clicks for the short code
    total_clicks = session.exec(select(func.count()).select_from(clicks).where(clicks.link_id == link.id)).one()
    return {"short_code": short_code, "total_clicks": total_clicks}

# get, post, put, delete, patch, options, head, trace - RESTful API methods
# use async def for async functions where you can use await for async calls
@app.get("/")
def example():
    return {"Hello": "World"}