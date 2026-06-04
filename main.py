from fastapi import FastAPI
from fastapi.responses import FileResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from routers import search, meta
from limiter import limiter

app = FastAPI(title="GoatScout API", version="2.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(search.router)
app.include_router(meta.router)


@app.get("/", include_in_schema=False)
def serve_index():
    return FileResponse("index.html")