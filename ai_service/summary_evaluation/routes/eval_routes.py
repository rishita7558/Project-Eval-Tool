import asyncio
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/eval", tags=["evaluation"])


class BatchEvalRequest(BaseModel):
    sessionId: str
    transcriptPath: str
    uploadZipPath: str
    webhookUrl: str
    agenticMode: int = 0


class SingleSummaryEvalRequest(BaseModel):
    studentSummary: str
    referencePackage: dict = {}
    coreConcepts: list = []
    deterministicMetrics: dict = {}
    agenticMode: int = 0


@router.post("/batch-summary")
async def trigger_batch_evaluation(req: BatchEvalRequest):
    """
    Receives the Node.js fire-and-forget payload containing paths.
    Delegates the processing to the pipeline orchestrator asynchronously.
    """
    if not req.transcriptPath or not req.uploadZipPath:
        raise HTTPException(status_code=400, detail="Missing required paths configuration")

    try:
        from summary_evaluation.pipelines.orchestrator import run_evaluation_pipeline
    except Exception as exc:
        print(f"ERROR: Failed to import orchestrator: {exc}")
        raise HTTPException(status_code=500, detail="Could not start evaluation pipeline")

    print(
        "DEBUG: Queued batch evaluation",
        f"session={req.sessionId}",
        f"webhook={req.webhookUrl}"
    )

    asyncio.create_task(
        run_evaluation_pipeline(
            session_id=req.sessionId,
            transcript_path=req.transcriptPath,
            zip_path=req.uploadZipPath,
            webhook_url=req.webhookUrl
        )
    )

    return {"status": "accepted", "message": "Background evaluation job started successfully"}


@router.post("/single-summary")
async def trigger_single_summary_evaluation(req: SingleSummaryEvalRequest):
    """
    Evaluates an individual summary submission.
    Coordinates through AgenticOrchestrator when agenticMode > 0.
    """
    try:
        from agentic_eval.orchestrator import default_orchestrator
        from agentic_eval.config import ConfigOverride

        eval_enabled = req.agenticMode > 0
        with ConfigOverride(eval_enabled=eval_enabled, mode=req.agenticMode):
            result = await default_orchestrator.evaluate_single_summary(
                student_summary=req.studentSummary,
                reference_package=req.referencePackage,
                core_concepts=req.coreConcepts,
                deterministic_metrics=req.deterministicMetrics,
            )

        return {"success": True, "result": result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Could not execute single summary evaluator: {exc}")
