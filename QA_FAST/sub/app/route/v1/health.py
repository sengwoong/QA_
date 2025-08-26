from fastapi import APIRouter


router = APIRouter()


@router.get("/healthz", tags=["system"])  # liveness probe
def healthz() -> dict:
    return {"status": "ok"}


