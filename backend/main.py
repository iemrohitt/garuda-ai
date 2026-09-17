import os

from dotenv import load_dotenv

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from pydantic import BaseModel

from pypdf import PdfReader

from google import genai

from rag.engine import add_document, search_documents

from database import (
    create_conversation,
    get_conversations,
    get_messages,
    save_message,
    delete_conversation,
    update_conversation_title
)


# =========================================================
# LOAD ENVIRONMENT VARIABLES
# =========================================================

load_dotenv()


# =========================================================
# CREATE FASTAPI APP
# =========================================================

app = FastAPI()


# =========================================================
# CORS
# =========================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["X-Conversation-ID"],
)


# =========================================================
# GEMINI CLIENT
# =========================================================

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    raise RuntimeError(
        "GEMINI_API_KEY is missing from .env"
    )

client = genai.Client(
    api_key=api_key
)


# =========================================================
# GEMINI MODEL
# =========================================================

GEMINI_MODEL = "gemini-3.6-flash"


# =========================================================
# DATA MODELS
# =========================================================

class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]
    conversation_id: int | None = None


class ConversationRequest(BaseModel):
    title: str = "New Chat"


# =========================================================
# HOME
# =========================================================

@app.get("/")
def home():

    return {
        "message": "Garuda AI backend is running!"
    }


# =========================================================
# CREATE NEW CONVERSATION
# =========================================================

@app.post("/api/conversations")
def create_new_conversation(
    request: ConversationRequest
):

    conversation_id = create_conversation(
        request.title
    )

    return {
        "id": conversation_id,
        "title": request.title,
        "message": "Conversation created successfully."
    }


# =========================================================
# GET ALL CONVERSATIONS
# =========================================================

@app.get("/api/conversations")
def list_conversations():

    conversations = get_conversations()

    return {
        "conversations": conversations
    }


# =========================================================
# GET MESSAGES OF A CONVERSATION
# =========================================================

@app.get(
    "/api/conversations/{conversation_id}/messages"
)
def conversation_messages(
    conversation_id: int
):

    messages = get_messages(
        conversation_id
    )

    return {
        "conversation_id": conversation_id,
        "messages": messages
    }


# =========================================================
# DELETE CONVERSATION
# =========================================================

@app.delete(
    "/api/conversations/{conversation_id}"
)
def remove_conversation(
    conversation_id: int
):

    delete_conversation(
        conversation_id
    )

    return {
        "message": "Conversation deleted successfully."
    }


# =========================================================
# CHAT + RAG
# =========================================================

@app.post("/api/chat")
async def chat(request: ChatRequest):

    # -----------------------------------------------------
    # 1. Check messages
    # -----------------------------------------------------

    if not request.messages:

        return {
            "error": "No messages were provided."
        }


    # -----------------------------------------------------
    # 2. Get latest user question
    # -----------------------------------------------------

    user_question = request.messages[-1].content


    # -----------------------------------------------------
    # 3. Create conversation if one doesn't exist
    # -----------------------------------------------------

    conversation_id = request.conversation_id

    if conversation_id is None:

        conversation_id = create_conversation(
            user_question[:50]
        )

    else:

        # -------------------------------------------------
        # Update default conversation title
        # using the user's first message.
        #
        # The frontend creates a new conversation with
        # "New Chat". When the first message arrives,
        # replace that title with the user's message.
        # -------------------------------------------------

        if request.messages:

            update_conversation_title(
                conversation_id,
                user_question[:50]
            )


    # -----------------------------------------------------
    # 4. Save user message
    # -----------------------------------------------------

    save_message(
        conversation_id,
        "user",
        user_question
    )


    # -----------------------------------------------------
    # 5. Search ChromaDB
    # -----------------------------------------------------

    retrieved_chunks = search_documents(
        user_question,
        top_k=3
    )


    # -----------------------------------------------------
    # 6. Prepare document context
    # -----------------------------------------------------

    if retrieved_chunks:

        context = "\n\n".join(
            retrieved_chunks
        )

        prompt = f"""
You are Garuda AI, an intelligent AI assistant.

Answer the user's question using the document
context below when it is relevant.

IMPORTANT RULES:

1. If the document context contains information
   relevant to the question, use it as the primary
   source.
2. If the question is a general question and the
   document context is not relevant, answer using
   your general knowledge.
3. Do NOT claim that information is unavailable
   simply because it is not present in the document.
4. Only say that something is unavailable in the
   uploaded document when the user specifically asks
   about the document or when the question clearly
   requires information from that document.
5. For programming questions, provide working code
   when appropriate.
6. Format answers using Markdown.
7. Use proper Markdown headings with #, ##, ###.
8. Use numbered lists when presenting ordered steps.
9. Use bullet points when presenting unordered items.
10. Use LaTeX notation for mathematical equations.
11. Do not mention ChromaDB, embeddings, or the RAG
    pipeline unless the user asks about them.
12. Give clear and useful explanations.

DOCUMENT CONTEXT:
-----------------
{context}
-----------------

USER QUESTION:
{user_question}
"""

    else:

        prompt = f"""
You are Garuda AI, an intelligent AI assistant.

Answer the user's question using your general
knowledge.

IMPORTANT RULES:

1. Provide a helpful and accurate answer.
2. Do not say that the answer is unavailable in
   an uploaded document.
3. For programming questions, provide working code
   when appropriate.
4. Format answers using Markdown.
5. Use proper Markdown headings with #, ##, ###.
6. Use numbered lists when presenting ordered steps.
7. Use bullet points when presenting unordered items.
8. Use LaTeX notation for mathematical equations.
9. Give clear and useful explanations.
10. Do not mention ChromaDB, embeddings, or RAG unless
    the user asks about them.

USER QUESTION:
{user_question}
"""


    # -----------------------------------------------------
    # 7. Generate streaming response
    # -----------------------------------------------------

    def generate():

        assistant_text = ""

        try:

            print(
                f"Using Gemini model: {GEMINI_MODEL}"
            )

            response = client.models.generate_content_stream(
                model=GEMINI_MODEL,
                contents=prompt,
            )

            for chunk in response:

                if chunk.text:

                    assistant_text += chunk.text

                    yield chunk.text


            # -------------------------------------------------
            # Save complete AI response
            # -------------------------------------------------

            if assistant_text.strip():

                save_message(
                    conversation_id,
                    "assistant",
                    assistant_text
                )


        except Exception as e:

            print(
                "================================================="
            )

            print(
                "GEMINI ERROR:"
            )

            print(
                repr(e)
            )

            print(
                "================================================="
            )

            error_message = (
                "\n\n⚠️ Garuda AI encountered an error while "
                "connecting to the AI model.\n\n"
                f"Error: {str(e)}"
            )

            yield error_message


    # -----------------------------------------------------
    # 8. Return streaming response
    # -----------------------------------------------------

    return StreamingResponse(

        generate(),

        media_type="text/plain",

        headers={
            "X-Conversation-ID": str(
                conversation_id
            )
        }

    )


# =========================================================
# PDF UPLOAD
# =========================================================

@app.post("/api/upload")
async def upload_pdf(
    file: UploadFile = File(...)
):

    # -----------------------------------------------------
    # 1. Check file type
    # -----------------------------------------------------

    if not file.filename.lower().endswith(".pdf"):

        return {
            "error": "Only PDF files are allowed."
        }


    # -----------------------------------------------------
    # 2. Create documents directory
    # -----------------------------------------------------

    os.makedirs(
        "documents",
        exist_ok=True
    )


    # -----------------------------------------------------
    # 3. Save PDF
    # -----------------------------------------------------

    file_path = os.path.join(
        "documents",
        file.filename
    )

    file_content = await file.read()


    with open(
        file_path,
        "wb"
    ) as f:

        f.write(file_content)


    # -----------------------------------------------------
    # 4. Read PDF
    # -----------------------------------------------------

    reader = PdfReader(
        file_path
    )

    text = ""


    # -----------------------------------------------------
    # 5. Extract text
    # -----------------------------------------------------

    for page in reader.pages:

        page_text = page.extract_text()

        if page_text:

            text += page_text + "\n"


    text = text.strip()


    # -----------------------------------------------------
    # 6. Check extracted text
    # -----------------------------------------------------

    if not text:

        return {
            "error":
                "Could not extract text from this PDF."
        }


    # -----------------------------------------------------
    # 7. Create chunks + embeddings
    #    and store in ChromaDB
    # -----------------------------------------------------

    result = add_document(
        text,
        file.filename
    )


    # -----------------------------------------------------
    # 8. Return result
    # -----------------------------------------------------

    return {

        "filename":
            file.filename,

        "pages":
            len(reader.pages),

        "characters":
            len(text),

        "chunks":
            result["chunks"],

        "message":
            "PDF processed and stored in ChromaDB successfully."

    }