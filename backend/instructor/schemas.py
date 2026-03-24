from pydantic import BaseModel

class UploadResponse(BaseModel):
    filename: str
    document_id: str
    status: str