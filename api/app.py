import os
import re
import logging
import json
import uuid
from datetime import datetime
from zoneinfo import ZoneInfo
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from typing import TypedDict, Annotated, Sequence, Literal
import operator

from langchain_core.messages import BaseMessage, HumanMessage, ToolMessage, SystemMessage
from langchain.tools import tool
from langchain_google_genai import ChatGoogleGenerativeAI
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

from paperqa import Docs, Settings

# Make sure to initialize settings first
from settings import settings as app_settings
from prompts import prompts

app = FastAPI()

# --- Logging Setup ---
now = datetime.now(ZoneInfo('Asia/Tokyo'))
log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs', now.strftime('%Y'), now.strftime('%m'))
os.makedirs(log_dir, exist_ok=True)
log_file_path = os.path.join(log_dir, f'{now.strftime("%d")}.jsonl')

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
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- PaperQA Tool Definition ---

# Cache for the Docs object to avoid re-indexing
docs_instance = None

def clean_answer_text(text: str) -> str:
    """A utility function to clean the answer text from paperqa."""
    if not text:
        return ""
    text = str(text)
    text = re.sub(r'^Question:.*\n', '', text, flags=re.MULTILINE)
    text = re.sub(r'\n\nReferences.*$', '', text, flags=re.DOTALL)
    text = re.sub(r'\n\s*\n', '\n\n', text)
    return text.strip()

@tool
async def paperqa_query(query: str) -> str:
    """
    Searches and answers questions from the PDF documents found in the 'my_papers' directory.
    Use this tool ONLY when the user asks a specific question about the content of their documents.
    For general conversation, do not use this tool.
    """
    global docs_instance
    print(f"--- Calling PaperQA Tool with query: {query} ---")
    
    try:
        papers_dir = app_settings.papers_directory
        if not os.path.exists(papers_dir):
            return "Error: Could not find the 'my_papers' directory."
        
        pdf_files = [f for f in os.listdir(papers_dir) if f.endswith('.pdf')]
        if not pdf_files:
            return "Error: Could not find any PDF files in the 'my_papers' directory."

        # Initialize Docs object only if it hasn't been initialized or if files changed
        current_files = set(pdf_files)
        if docs_instance is None or getattr(docs_instance, '_indexed_files', set()) != current_files:
            print("Initializing or updating PaperQA Docs index...")
            os.environ["GEMINI_API_KEY"] = app_settings.gemini_api_key
            os.environ["GOOGLE_API_KEY"] = app_settings.gemini_api_key
            
            pqa_settings = Settings(
                llm=f"gemini/{app_settings.llm_name}",
                summary_llm=f"gemini/{app_settings.llm_name}",
                embedding=f"gemini/{app_settings.embedding_name}",
            )
            
            # Initialize Docs without constructor args
            temp_docs = Docs()
            
            # Add files with settings
            for pdf_file in pdf_files:
                pdf_path = os.path.join(papers_dir, pdf_file)
                await temp_docs.aadd(pdf_path, settings=pqa_settings)
            
            # Cache the instance
            docs_instance = temp_docs
            setattr(docs_instance, '_indexed_files', current_files)
            print("PaperQA Docs index updated.")

        # Query the cached documents, passing settings again
        pqa_settings_for_query = Settings(
            llm=f"gemini/{app_settings.llm_name}",
            summary_llm=f"gemini/{app_settings.llm_name}",
            embedding=f"gemini/{app_settings.embedding_name}",
        )
        answer_response = await docs_instance.aquery(query, settings=pqa_settings_for_query)
        
        final_answer_text = getattr(answer_response, 'answer', str(answer_response))
        cleaned_answer = clean_answer_text(final_answer_text)

        if not cleaned_answer or cleaned_answer.lower() in ["none", "", "i cannot answer."]:
            return "I could not find a relevant answer in the documents for your query."
        
        return cleaned_answer

    except Exception as e:
        print(f"Error in paperqa_tool: {e}")
        import traceback
        traceback.print_exc()
        return "An error occurred while searching the documents."

# --- LangGraph Agent Definition ---

class AgentState(TypedDict):
    messages: Annotated[Sequence[BaseMessage], operator.add]

tools = [paperqa_query]


# Use a model that supports tool calling
model = ChatGoogleGenerativeAI(model=app_settings.llm_name, google_api_key=app_settings.gemini_api_key)
model_with_tools = model.bind_tools(tools)

def should_continue(state: AgentState) -> Literal["call_tool", "__end__"]:
    """Decides whether to call a tool or end the conversation."""
    last_message = state['messages'][-1]
    if last_message.tool_calls:
        return "call_tool"
    return "__end__"

async def call_model(state: AgentState):
    """Calls the LLM to decide the next action."""
    messages = state['messages']
    response = await model_with_tools.ainvoke(messages)
    return {"messages": [response]}


# Define the pre-built ToolNode
tool_node = ToolNode(tools)



# Define the graph
workflow = StateGraph(AgentState)
workflow.add_node("agent", call_model)
workflow.add_node("call_tool", tool_node)

workflow.set_entry_point("agent")
workflow.add_conditional_edges(
    "agent",
    should_continue,
    {
        "call_tool": "call_tool",
        "__end__": "__end__"
    }
)
workflow.add_edge('call_tool', 'agent')

app_graph = workflow.compile()

# --- API Endpoints ---

class ChatRequest(BaseModel):
    question: str
    session_id: str | None = None
    # We can add chat_history here in the future
    # chat_history: list[dict] | None = None

@app.post("/api/chat")
async def chat_with_papers(request: ChatRequest):
    """
    Receives a question, uses the LangGraph agent to decide whether to
    use the PaperQA tool or respond directly.
    """
    if not app_settings.gemini_api_key:
        raise HTTPException(status_code=500, detail="API key is not configured on the server.")
    
    if not request.question:
        raise HTTPException(status_code=400, detail="Question cannot be empty.")

    # For now, each request is a new conversation.
    # In the future, we can use session_id to retrieve and continue conversations.
    inputs = {
        "messages": [
            SystemMessage(content=prompts.agent_system_prompt),
            HumanMessage(content=request.question)
        ]
    }

    try:
        # The graph can be streamed or invoked
        final_state = await app_graph.ainvoke(inputs)
        
        # The final answer is the last message from the assistant
        final_answer = final_state['messages'][-1].content
        
        # Determine the source based on whether a tool was used
        source = "conversational_api"
        for msg in final_state['messages']:
            if isinstance(msg, ToolMessage):
                source = "rag_api"
                break

        session_id = request.session_id if request.session_id else str(uuid.uuid4())

        response_data = {
            "session_id": session_id,
            "timestamp": datetime.now(ZoneInfo('Asia/Tokyo')).isoformat(),
            "question": request.question,
            "answer": final_answer,
            "source": source,
        }

        rag_logger.info(json.dumps(response_data, ensure_ascii=False))

        return JSONResponse(content=response_data)

    except Exception as e:
        print(f"Error during chat processing: {e}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail="An internal error occurred.")

@app.get("/api/logs")
async def get_logs():
    all_logs = []
    base_log_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', 'logs')
    if os.path.exists(base_log_dir):
        for year in sorted(os.listdir(base_log_dir), reverse=True):
            year_dir = os.path.join(base_log_dir, year)
            if os.path.isdir(year_dir):
                for month in sorted(os.listdir(year_dir), reverse=True):
                    month_dir = os.path.join(year_dir, month)
                    if os.path.isdir(month_dir):
                        for filename in sorted(os.listdir(month_dir), reverse=True):
                            if filename.endswith(".jsonl"):
                                with open(os.path.join(month_dir, filename), "r") as f:
                                    for line in f:
                                        try:
                                            all_logs.append(json.loads(line))
                                        except json.JSONDecodeError:
                                            pass
    return all_logs

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
