from fastapi import FastAPI
from routers import search

app = FastAPI()
app.include_router(search.router)