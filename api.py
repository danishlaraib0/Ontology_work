from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pydantic import BaseModel
import subprocess
import os
import sys

from intelligence.dynamic_query_engine import DynamicQueryEngine

app = FastAPI(title="Automotive World Model API")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

ui_dir = os.path.join(os.path.dirname(__file__), "ui")

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(ui_dir, "index.html"))

@app.get("/style.css")
def serve_css():
    return FileResponse(os.path.join(ui_dir, "style.css"), media_type="text/css")

@app.get("/app.js")
def serve_js():
    return FileResponse(os.path.join(ui_dir, "app.js"), media_type="application/javascript")

engine = DynamicQueryEngine()

class QueryRequest(BaseModel):
    query: str

class CarRequest(BaseModel):
    make: str
    model: str

@app.post("/api/query")
def process_query(request: QueryRequest):
    try:
        res = engine.execute(request.query)
        return {
            "query": res.query,
            "plan": {
                "intent": res.plan.intent,
                "tool": res.plan.selected_tool,
                "reasoning": res.plan.reasoning,
            },
            "graph_paths": res.tool_result.graph_paths if res.tool_result else [],
            "summary": res.tool_result.summary if res.tool_result else "",
            "causal_synthesis": res.causal_synthesis,
            "markdown_report": res.markdown_report
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

from ingestion.ingestion_manager import get_ingestion_manager

ingestion_manager = get_ingestion_manager()

@app.post("/api/add_car")
def add_car(request: CarRequest, background_tasks: BackgroundTasks):
    make = request.make.strip()
    model = request.model.strip()
    if not make or not model:
        raise HTTPException(status_code=400, detail="Make and model are required.")

    job = ingestion_manager.create_job(make, model)
    background_tasks.add_task(ingestion_manager.run_job_synchronous, job.job_id)
    return {
        "status": "QUEUED",
        "job_id": job.job_id,
        "make": job.make,
        "model": job.model,
        "message": f"Autonomous ingestion started for {job.make} {job.model}.",
        "job": job.to_dict(),
    }

@app.get("/api/ingestion_status/{job_id}")
def get_ingestion_status(job_id: str):
    job = ingestion_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail=f"Ingestion job '{job_id}' not found.")
    return job.to_dict()

@app.get("/api/ingestion_jobs")
def list_ingestion_jobs():
    jobs = ingestion_manager.list_jobs()
    return {"jobs": [j.to_dict() for j in jobs]}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
