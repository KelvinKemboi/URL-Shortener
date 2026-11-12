from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, Depends, Request
from sqlmodel import Field, SQLModel, create_engine, Session, select
from fastapi.responses import RedirectResponse
from sqlalchemy import func
import secrets
import string
from pydantic import AwareDatetime, BaseModel, HttpUrl
from redis import Redis
from redis.exceptions import ConnectionError as RedisConnectionError
import json

redis_client = Redis(host='localhost', port=6379, db=0, decode_responses=True) # decode_responses=True ensures that Redis returns strings instead of bytes


# define the Pydantic model for the request body
class LinkCreate(BaseModel):
    original_url: HttpUrl
    custom_alias: str | None = None
    # AwareDatetime rejects dates without a timezone (422) instead of crashing on save
    expiration_date: AwareDatetime | None = None


# define the SQLModel for the database table
class Link(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    short_code: str = Field(index=True, unique=True)
    original_url: str
    expiration_date: datetime | None = None
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


# helper used by /shorten (to skip expired links) and the redirect route (to return 410)
def is_expired(link: Link) -> bool:
    return link.expiration_date is not None and link.expiration_date < datetime.now(timezone.utc)


app = FastAPI(lifespan=lifespan)

# endpoint to shorten a URL and return the short code and short URL
@app.post("/shorten")
def shorten_url(data: LinkCreate, request: Request, session: Session = Depends(get_session)):
    # check if the original URL already exists in the database
    original_url = str(data.original_url)
    custom_alias = data.custom_alias

    # an expiry in the past would create a link that is dead on arrival
    if data.expiration_date and data.expiration_date <= datetime.now(timezone.utc):
        raise HTTPException(status_code=422, detail="Expiration date must be in the future")

    # reuse an existing link for this URL, but only one that hasn't expired
    for existing_link in session.exec(select(Link).where(Link.original_url == original_url)).all():
        if not is_expired(existing_link):
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
    new_link = Link(short_code=short_code, original_url=original_url, expiration_date=data.expiration_date)
    session.add(new_link)
    session.commit()
    session.refresh(new_link) 

    return {"short_code": new_link.short_code, "short_url": f"{request.base_url}{new_link.short_code}"}

# endpoint to redirect to the original URL when a short code is accessed
@app.get("/{short_code}")
def redirect_to_original_url(short_code: str, session: Session = Depends(get_session)):
    # check redis cache first - if Redis is down, treat it as a cache miss and use the database
    try:
        cached_url = redis_client.get(short_code)
    except RedisConnectionError:
        cached_url = None

    # cache hit - when the short code is found in Redis, we can skip the database query and just redirect to the cached URL
    if cached_url:
        # load the cached value from Redis and check if the link has expired
        cached_value = json.loads(cached_url) # to dictionary
        original_url = cached_value.get("original_url")
        expiration_date = cached_value.get("expiration_date")
        link_id = cached_value.get("id")

        if expiration_date is not None:
            expiration_date = datetime.fromisoformat(expiration_date)
            if expiration_date <= datetime.now(timezone.utc):
                try:
                    redis_client.delete(short_code)  # remove the expired link from Redis cache
                except RedisConnectionError:
                    pass
                raise HTTPException(status_code=410, detail="Link has expired")

        session.add(clicks(link_id=link_id))  # increment click count in the database
        session.commit()
        return RedirectResponse(original_url, status_code=307)

    # cache miss - check if the short code exists in the database
    link = session.exec(select(Link).where(Link.short_code == short_code)).first()
    if link is None:
        raise HTTPException(status_code=404, detail="Short code not found")

    # check if the link has expired
    if is_expired(link):
        raise HTTPException(status_code=410, detail="Link has expired")

    # increment click count in the database
    new_click = clicks(link_id=link.id)
    session.add(new_click)
    session.commit()

    # dict to store the link data in Redis cache
    cache_value = {
        "id": link.id,
        "original_url": link.original_url,
        "expiration_date": link.expiration_date.isoformat() if link.expiration_date else None
    }
    # cache the link in Redis for future requests - if Redis is down, skip caching; the redirect still works
    try:
        redis_client.set(short_code, json.dumps(cache_value), ex=3600)  # cache for 1 hour
    except RedisConnectionError:
        pass

    # redirect to the original URL
    return RedirectResponse(link.original_url, status_code=307)

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