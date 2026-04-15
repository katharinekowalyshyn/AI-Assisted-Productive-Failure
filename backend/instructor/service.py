from __future__ import annotations

import json
from pathlib import Path

from fastapi import UploadFile
from llmproxy import LLMProxy


SHARED_GRAMMAR_SESSION_ID = "shared_grammar_material"

class InstructorService:
    def __init__(self):
        self.upload_dir = Path("./uploads")
        self.upload_dir.mkdir(exist_ok=True)
        self.uploaded_files = {}  # session_id -> list of file_paths
        self._load_index()

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
            self._save_index()
            
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
        content = self._read_materials(self.uploaded_files[session_id])
        return content[:4000]  # keep prompt context bounded

    def ensure_shared_grammar_uploaded(self):
        """Upload local grammar PDF into shared LLMProxy session exactly once."""
        marker_path = self.upload_dir / ".shared_grammar_uploaded.json"
        if marker_path.exists():
            return

        grammar_files = sorted(self.upload_dir.glob("*.pdf"))
        if not grammar_files:
            return

        grammar_path = grammar_files[0]
        client = LLMProxy()
        response = client.upload_file(
            file_path=grammar_path,
            session_id=SHARED_GRAMMAR_SESSION_ID,
            description="Shared grammar reference for all students",
            strategy="smart",
        )
        if "error" in response:
            print(f"[InstructorService] Shared grammar upload failed: {response['error']}")
            return

        self.uploaded_files.setdefault(SHARED_GRAMMAR_SESSION_ID, [])
        if str(grammar_path) not in self.uploaded_files[SHARED_GRAMMAR_SESSION_ID]:
            self.uploaded_files[SHARED_GRAMMAR_SESSION_ID].append(str(grammar_path))
        self._save_index()
        marker_path.write_text(
            json.dumps({"uploaded_file": str(grammar_path)}, indent=2),
            encoding="utf-8",
        )

    def _read_materials(self, file_paths: list[str]) -> str:
        content = ""
        for file_path in file_paths:
            if not file_path.lower().endswith((".txt", ".md", ".csv", ".json")):
                continue
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    content += f.read() + "\n"
            except Exception as e:
                print(f"Error reading {file_path}: {e}")

        return content

    def _index_path(self) -> Path:
        return self.upload_dir / "uploads_index.json"

    def _load_index(self):
        path = self._index_path()
        if not path.exists():
            return
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, dict):
                self.uploaded_files = data
        except Exception as exc:
            print(f"[InstructorService] Could not load uploads index: {exc}")

    def _save_index(self):
        path = self._index_path()
        path.write_text(json.dumps(self.uploaded_files, indent=2), encoding="utf-8")


instructor_service = InstructorService()