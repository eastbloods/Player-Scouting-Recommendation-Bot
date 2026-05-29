from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from routers import search
import os

app = FastAPI(title="GoatScout API", version="2.0")
app.include_router(search.router)


@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse("index.html")