from services.llm_client import LLMTutorClient
from services.rag import RAGService
from instructor.service import InstructorService  # ADD: To access uploads
from .analytics import AnalyticsLogger

from llmproxy import LLMProxy
from core.config import settings


class PFService:
    def __init__(self):
        self.llm = LLMProxy()
        self.rag = RAGService()  # ADD: Instantiate RAG
        self.instructor = InstructorService()  # ADD: Access uploads
        self.sessions = {}  # store session state

    def start_session(self, session_id: str, topic: str = "general", level: str = "intermediate"):
        """Generate a problem based on topic, level, and uploaded material via RAG."""
        
        # Retrieve uploaded material for this session
        uploaded_content = self.instructor.get_session_material(session_id)
        
        # Difficulty-based prompt engineering
        difficulty_hints = {
            "novice": "Create a simple, introductory problem",
            "intermediate": "Create a moderately challenging problem that requires some steps",
            "advanced": "Create a complex, multi-step problem requiring deep reasoning",
        }

        # Build prompt with RAG context
        context = f"Reference this uploaded material if relevant: {uploaded_content}" if uploaded_content else "No uploaded material available."
        
        prompt = f"""{context}

Generate a single {topic} problem for a student at {level} level.
        
{difficulty_hints.get(level, difficulty_hints['intermediate'])}

Requirements:
- ONE clear problem statement only
- No solution or hints
- Make it challenging but solvable with effort
- Format: Just the problem text, nothing else

Problem:"""

        try:
            response = self.llm.generate(
                model=settings.llm_model,
                system="You are an expert problem generator for productive failure learning. Use provided context to tailor problems.",
                query=prompt,
                session_id=session_id,
                temperature=0.7,
                rag_usage=True,  # ENABLE RAG
            )
            
            problem = response.get("result", "Solve: 2x + 5 = 15")
            
            # Store session state
            self.sessions[session_id] = {
                "problem": problem,
                "topic": topic,
                "level": level,
                "attempts": [],
                "uploaded_content": uploaded_content,  # Store for later RAG use
            }
            
            return problem
            
        except Exception as e:
            print(f"Error generating problem: {e}")
            return f"Problem generation failed: {str(e)}"

    def handle_attempt(self, session_id: str, answer: str):
        """Evaluate student attempt using PF pedagogy, with RAG context."""
        if session_id not in self.sessions:
            return "Session not found. Start a new problem."
        
        session = self.sessions[session_id]
        problem = session["problem"]
        uploaded_content = session.get("uploaded_content", "")
        
        # Store attempt
        session["attempts"].append(answer)
        
        # Build PF prompt with RAG context
        context = f"Reference this uploaded material for feedback: {uploaded_content}" if uploaded_content else ""
        
        pf_prompt = f"""{context}

You are a tutor using Productive Failure pedagogy.

Student's attempt #{len(session['attempts'])}: {answer}

Problem was: {problem}

Rules:
1. DO NOT give the solution
2. Acknowledge their thinking
3. Ask clarifying questions
4. After 3+ failed attempts, give ONE hint
5. Keep response brief (2-3 sentences)

Feedback:"""

        try:
            response = self.llm.generate(
                model=settings.llm_model,
                system=settings.llm_system_prompt,
                query=pf_prompt,
                session_id=session_id,
                temperature=0.5,
                rag_usage=True,  # ENABLE RAG for feedback too
            )
            
            return response.get("result", "Keep trying!")
            
        except Exception as e:
            print(f"Error evaluating attempt: {e}")
            return f"Evaluation failed: {str(e)}"
        
        def get_hint(self, session_id: str, problem_text: str, hint_level: int):
            """Generate a hint based on problem and level, with RAG."""
            if session_id not in self.sessions:
                return "Session not found."
            
            uploaded_content = self.sessions[session_id].get("uploaded_content", "")
            context = f"Reference this uploaded material: {uploaded_content}" if uploaded_content else ""
            
            hint_prompt = f"""{context}
    
    Problem: {problem_text}
    Hint level: {hint_level}
    
    Generate a helpful hint that guides without revealing the solution."""
            
            try:
                response = self.llm.generate(
                    model=settings.llm_model,
                    system="You are a helpful tutor providing hints for students struggling with problems. Use any provided context to tailor your hint.",
                    query=hint_prompt,
                    session_id=session_id,
                    temperature=0.5,
                    rag_usage=True,  # ENABLE RAG for hints
                )
                
                return response.get("result", "Here's a hint: Think about the underlying concepts.")
                
            except Exception as e:
                print(f"Error generating hint: {e}")
                return f"Hint generation failed: {str(e)}"