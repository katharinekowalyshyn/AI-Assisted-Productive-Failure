from fastapi import APIRouter
from .models import *
from .service import PFService

router = APIRouter(prefix="/pf", tags=["Productive Failure"])
service = PFService()


@router.post("/attempt", response_model=PFResponse)
def evaluate_attempt(req: AttemptRequest):
    return service.evaluate_attempt(req)


@router.post("/hint", response_model=PFResponse)
def generate_hint(req: HintRequest):
    return service.generate_hint(req)


@router.post("/reflection", response_model=PFResponse)
def analyze_reflection(req: ReflectionRequest):
    return service.analyze_reflection(req)