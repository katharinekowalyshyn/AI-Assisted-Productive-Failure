from fastapi import APIRouter, UploadFile, File, Form
from .service import instructor_service

router = APIRouter(prefix="/instructor", tags=["Instructor"])
service = instructor_service


@router.post("/upload")
async def upload_material(
    file: UploadFile = File(...),
    session_id: str = Form(...)  # ADD: Associate with session
):
    return await service.upload_material(file, session_id)