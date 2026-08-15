from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.core.config import settings
from app.api.v1.routes import router
@asynccontextmanager
async def lifespan(app:FastAPI):
 settings.storage_root.mkdir(parents=True,exist_ok=True); yield
app=FastAPI(title="EvoThermGuard",version="0.1.0",lifespan=lifespan)
app.add_middleware(CORSMiddleware,allow_origins=[settings.frontend_url],allow_credentials=True,allow_methods=["*"],allow_headers=["*"])
app.include_router(router,prefix="/api/v1")
app.mount('/evidence',StaticFiles(directory=settings.storage_root),name='evidence')
@app.get('/health')
async def root_health(): return {"api":"ok","service":"EvoThermGuard"}
