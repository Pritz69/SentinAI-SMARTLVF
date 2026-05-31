from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from config.settings import settings
from schemas.response import HealthResponse

# Import Middleware
from core.middleware import SecurityTelemetryMiddleware

# Import Routers
from api.v1.target import router as target_router
from api.v1.simulation import router as simulation_router
from api.v1.hitl import router as hitl_router
from api.v1.targets import router as targets_router

app = FastAPI(
    title=settings.PROJECT_NAME,
    version="0.1.0",
    description="Stateful Multi-Agent Adversarial Red-Teaming Framework"
)

# 1. Add Custom Middleware
app.add_middleware(SecurityTelemetryMiddleware)

# 2. Register API Routers
app.include_router(target_router)
app.include_router(simulation_router)
app.include_router(hitl_router)
app.include_router(targets_router)

# 3. Mount Static Files & Serve HTML Dashboard
app.mount("/static", StaticFiles(directory="static"), name="static")

@app.get("/")
@app.get("/dashboard")
async def serve_dashboard():
    return FileResponse("static/index.html")

@app.get("/health", response_model=HealthResponse, tags=["Diagnostics"])
async def health_check():
    return HealthResponse(
        status="ok",
        project=settings.PROJECT_NAME,
        environment=settings.ENV
    )