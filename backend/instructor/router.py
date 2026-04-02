from fastapi import APIRouter, UploadFile, File, Form
from .service import InstructorService

router = APIRouter(prefix="/instructor", tags=["Instructor"])
service = InstructorService()


@router.post("/upload")
async def upload_material(
    file: UploadFile = File(...),
    session_id: str = Form(...)  # ADD: Associate with session
):
    return await service.upload_material(file, session_id)