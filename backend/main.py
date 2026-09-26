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
# BUILD CONVERSATION HISTORY
# =========================================================

def build_conversation_history(messages):
    """
    Convert database messages into readable conversation
    history for the Gemini prompt.
    """

    if not messages:
        return "No previous conversation."

    history_parts = []

    for message in messages:

        role = message.get("role", "")
        content = message.get("content", "")

        if role == "user":
            history_parts.append(
                f"USER:\n{content}"
            )

        elif role == "assistant":
            history_parts.append(
                f"ASSISTANT:\n{content}"
            )

    return "\n\n".join(history_parts)


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
        # Update conversation title
        # -------------------------------------------------

        if request.messages:

            update_conversation_title(
                conversation_id,
                user_question[:50]
            )


    # -----------------------------------------------------
    # 4. Get previous conversation history
    #
    # IMPORTANT:
    # We retrieve the history BEFORE saving the current
    # message so that we can clearly separate previous
    # messages from the new user question.
    # -----------------------------------------------------

    previous_messages = get_messages(
        conversation_id
    )

    conversation_history = build_conversation_history(
        previous_messages
    )


    # -----------------------------------------------------
    # 5. Save current user message
    # -----------------------------------------------------

    save_message(
        conversation_id,
        "user",
        user_question
    )


    # -----------------------------------------------------
    # 6. Search ChromaDB
    # -----------------------------------------------------

    retrieved_chunks = search_documents(
        user_question,
        top_k=3
    )


    # -----------------------------------------------------
    # 7. Prepare document context
    # -----------------------------------------------------

    if retrieved_chunks:

        context = "\n\n".join(
            retrieved_chunks
        )

    else:

        context = "No relevant document context was found."


    # -----------------------------------------------------
    # 8. Build prompt with conversation history + RAG
    # -----------------------------------------------------

    prompt = f"""
You are Garuda AI, an intelligent AI assistant.

Your job is to answer the user's latest question while
maintaining awareness of the previous conversation.

IMPORTANT CONVERSATION RULES:

1. Use the conversation history to understand references
   to earlier messages.
2. If the user previously provided information such as
   their name, preferences, project details, or other
   facts, use that information when relevant.
3. Do not claim that you do not know something if the
   information was already provided earlier in this
   conversation.
4. Treat the conversation history as the context of the
   current conversation.
5. Do not confuse information from the document context
   with information from the conversation history.


IMPORTANT RESPONSE RULES:

1. Provide a helpful and accurate answer.
2. If the document context contains information relevant
   to the question, use it as the primary source.
3. If the question is general and the document context
   is not relevant, use your general knowledge.
4. Do not claim that information is unavailable simply
   because it is not present in the uploaded document.
5. Only say something is unavailable in the uploaded
   document when the user specifically asks about the
   document or when the question clearly requires
   information from that document.
6. For programming questions, provide working code when
   appropriate.
7. Format answers using Markdown.
8. Use proper Markdown headings with #, ##, ###.
9. Use numbered lists for ordered steps.
10. Use bullet points for unordered items.
11. Use LaTeX notation for mathematical equations.
12. Do not mention ChromaDB, embeddings, or the RAG
    pipeline unless the user asks about them.
13. Give clear and useful explanations.


PREVIOUS CONVERSATION:
----------------------
{conversation_history}
----------------------


DOCUMENT CONTEXT:
-----------------
{context}
-----------------


LATEST USER QUESTION:
---------------------
{user_question}
---------------------
"""


    # -----------------------------------------------------
    # 9. Generate streaming response
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


            # -------------------------------------------------
            # Stream Gemini response
            # -------------------------------------------------

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
    # 10. Return streaming response
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