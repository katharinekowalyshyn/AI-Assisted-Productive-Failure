from fastapi import APIRouter, UploadFile, File
from .service import InstructorService

router = APIRouter(prefix="/instructor", tags=["Instructor"])
service = InstructorService()


@router.post("/upload")
async def upload_material(file: UploadFile = File(...)):
    return await service.upload_material(file)