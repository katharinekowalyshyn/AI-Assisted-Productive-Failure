from fastapi import UploadFile
import tempfile
import shutil
import os
from pathlib import Path

class InstructorService:
    def __init__(self):
        self.upload_dir = Path("./uploads")
        self.upload_dir.mkdir(exist_ok=True)
        self.uploaded_files = {}  # session_id -> list of file_paths

    async def upload_material(self, file: UploadFile, session_id: str):
        """Store uploaded material tied to a session."""
        try:
            contents = await file.read()
            file_path = self.upload_dir / f"{session_id}_{file.filename}"
            
            with open(file_path, "wb") as f:
                f.write(contents)
            
            # Store per session
            if session_id not in self.uploaded_files:
                self.uploaded_files[session_id] = []
            self.uploaded_files[session_id].append(str(file_path))
            
            return {
                "filename": file.filename,
                "size": len(contents),
                "path": str(file_path),
                "session_id": session_id,
            }
        except Exception as e:
            return {"error": str(e)}

    def get_session_material(self, session_id: str) -> str:
        """Retrieve concatenated content from uploaded files for RAG."""
        if session_id not in self.uploaded_files:
            return ""
        
        content = ""
        for file_path in self.uploaded_files[session_id]:
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content += f.read() + "\n"
            except Exception as e:
                print(f"Error reading {file_path}: {e}")
        
        return content[:2000]  # Limit to avoid token overflow