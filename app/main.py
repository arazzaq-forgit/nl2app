from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from app.pipeline.orchestrator import run_pipeline
from app.execution.executor import execute_config

app = FastAPI(title="NL -> App Config Compiler")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class GenerateRequest(BaseModel):
    prompt: str


@app.post("/generate")
def generate(req: GenerateRequest):
    if not req.prompt or len(req.prompt.strip()) < 5:
        raise HTTPException(status_code=400, detail="Prompt too short")
    try:
        result = run_pipeline(req.prompt)
        if result.get("status") in ("ok", "ok_with_warnings"):
            try:
                result["execution_report"] = execute_config(result, out_dir="/tmp/nl2app_build")
            except Exception as exec_err:
                result["execution_report"] = {"status": "failed", "error": str(exec_err)}
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/health")
def health():
    return {"status": "ok"}
