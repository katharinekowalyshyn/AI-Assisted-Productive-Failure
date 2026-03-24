from fastapi import UploadFile
import tempfile
import shutil
import os
from llmproxy import LLMProxy


class InstructorService:
    def __init__(self):
        self.client = LLMProxy()

    async def upload_material(self, file: UploadFile):
        # 1️⃣ Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            shutil.copyfileobj(file.file, tmp)
            temp_path = tmp.name

        try:
            # 2️⃣ Upload to LLMProxy RAG storage
            result = self.client.upload_file(
                file_path=temp_path,
                session_id="instructor_material"
            )

            return {
                "filename": file.filename,
                "status": "uploaded",
                "llmproxy_response": result
            }

        finally:
            # 3️⃣ Always clean temp file
            if os.path.exists(temp_path):
                os.remove(temp_path)