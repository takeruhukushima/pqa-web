import os
import re
import logging
import json
import uuid
from datetime import datetime
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from paperqa import Docs, Settings
from paperqa.settings import AgentSettings

# Make sure to initialize settings first
from settings import settings as app_settings

app = FastAPI()

# --- Logging Setup ---
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs')
os.makedirs(log_dir, exist_ok=True)
log_file_path = os.path.join(log_dir, f'{datetime.utcnow().strftime("%Y-%m-%d")}.jsonl')

rag_logger = logging.getLogger('rag_logger')
rag_logger.setLevel(logging.INFO)
# Prevent duplicate handlers
if not rag_logger.handlers:
    handler = logging.FileHandler(log_file_path)
    handler.setFormatter(logging.Formatter('%(message)s'))
    rag_logger.addHandler(handler)
# --- End Logging Setup ---

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for simplicity, adjust for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class ChatRequest(BaseModel):
    question: str
    session_id: str | None = None

def clean_answer_text(text: str) -> str:
    """A utility function to clean the answer text from paperqa."""
    if not text:
        return ""
    text = str(text)
    # Remove "Question: ..." line
    text = re.sub(r'^Question:.*\n', '', text, flags=re.MULTILINE)
    # Remove "References" section
    text = re.sub(r'\n\nReferences.*$', '', text, flags=re.DOTALL)
    # Normalize newlines
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()

@app.post("/api/chat")
async def chat_with_papers(request: ChatRequest):
    """
    Receives a question, uses paperqa to find an answer from the documents
    in the local my_papers directory, and returns the answer.
    """
    if not app_settings.gemini_api_key:
        raise HTTPException(status_code=500, detail="API key is not configured on the server.")
    
    if not request.question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    try:
        papers_dir = app_settings.papers_directory
        print(f"DEBUG: Checking for papers in directory: {papers_dir}")

        if not os.path.exists(papers_dir):
            return {"answer": "I could not find the my_papers directory. Please create backend/my_papers and add your documents."}
        
        # Get list of PDF files
        pdf_files = [f for f in os.listdir(papers_dir) if f.endswith('.pdf')]
        
        if not pdf_files:
            return {"answer": "I could not find any PDF files in the my_papers directory. Please add your documents to backend/my_papers."}

        # Set environment variables for Gemini
        os.environ["GEMINI_API_KEY"] = app_settings.gemini_api_key
        os.environ["GOOGLE_API_KEY"] = app_settings.gemini_api_key
        
        # Create Settings object with Gemini configuration
        pqa_settings = Settings(
            llm=app_settings.llm_name,
            summary_llm=app_settings.llm_name,
            embedding=app_settings.embedding_name,
        )
        
        print(f"Settings created - LLM: {pqa_settings.llm}, Embedding: {pqa_settings.embedding}")
        print(f"Found {len(pdf_files)} PDF files: {pdf_files}")
        
        # Create Docs instance
        docs = Docs()
        
        # Try to update internal settings if possible
        if hasattr(docs, 'model_config'):
            print(f"Docs model_config: {docs.model_config}")
        
        # Add all PDF files from the directory
        print(f"Adding {len(pdf_files)} PDF files to index...")
        for pdf_file in pdf_files:
            pdf_path = os.path.join(papers_dir, pdf_file)
            print(f"Adding: {pdf_file}")
            try:
                # Try to add with settings
                await docs.aadd(pdf_path, settings=pqa_settings)
            except TypeError:
                # If settings parameter is not supported, try without it
                await docs.aadd(pdf_path)
        
        print(f"Docs now contains {len(docs.docs)} documents")
        print(f"Asking question: {request.question}")
        
        # Query the documents
        try:
            answer_response = await docs.aquery(request.question, settings=pqa_settings)
        except TypeError:
            # If settings parameter is not supported, try without it
            answer_response = await docs.aquery(request.question)
        
        print(f"Response type: {type(answer_response)}")
        
        final_answer_text = ""
        if hasattr(answer_response, 'answer') and str(answer_response.answer).strip():
            final_answer_text = str(answer_response.answer)
        elif hasattr(answer_response, 'formatted_answer'):
            final_answer_text = str(answer_response.formatted_answer)
        else:
            final_answer_text = str(answer_response)

        cleaned_answer = clean_answer_text(final_answer_text)

        if not cleaned_answer or cleaned_answer.lower() in ["none", ""]:
            cleaned_answer = "I could not find an answer in the provided documents."

        session_id = request.session_id if request.session_id else str(uuid.uuid4())

        # Create the response data dictionary with the desired key order
        response_data = {
            "session_id": session_id,
            "timestamp": datetime.utcnow().isoformat(),
            "question": request.question,
            "answer": cleaned_answer,
            "source": "rag_api",
        }

        # Log the response data, ensuring Japanese characters are handled correctly
        rag_logger.info(json.dumps(response_data, ensure_ascii=False))

        # Return a JSONResponse to ensure proper JSON formatting and headers
        return JSONResponse(content=response_data)

    except Exception as e:
        print(f"Error during chat processing: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"An error occurred while processing your question: {e}")