from fastapi import FastAPI
from app.api.v1 import auth, todos
from app.db.session import engine, Base

app = FastAPI(title="FastAPI Todo API", version="1.0.0")

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(todos.router, prefix="/todos", tags=["todos"])

@app.on_event("startup")
async def startup():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

@app.get("/")
async def root():
    return {"message": "FastAPI Todo API is running"}