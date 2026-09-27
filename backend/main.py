import os
import json

from dotenv import load_dotenv

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from pydantic import BaseModel

from pypdf import PdfReader

from google import genai

from rag.engine import add_pages, search_documents

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
    expose_headers=[
        "X-Conversation-ID",
        "X-Sources"
    ],
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

    # Name of the currently selected PDF.
    # RAG will search only inside this document.
    document_name: str | None = None


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

        role = message.get(
            "role",
            ""
        )

        content = message.get(
            "content",
            ""
        )

        if role == "user":

            history_parts.append(
                f"USER:\n{content}"
            )

        elif role == "assistant":

            history_parts.append(
                f"ASSISTANT:\n{content}"
            )

    return "\n\n".join(
        history_parts
    )


# =========================================================
# BUILD DOCUMENT CONTEXT
# =========================================================

def build_document_context(
    retrieved_results
):
    """
    Convert structured RAG search results into
    readable context for the Gemini prompt.

    Each result contains:

        text
        metadata
        distance

    Metadata contains:

        document
        page
        chunk
    """

    if not retrieved_results:

        return (
            "No sufficiently relevant document context "
            "was found."
        )

    context_parts = []

    for result in retrieved_results:

        document_text = result.get(
            "text",
            ""
        )

        metadata = result.get(
            "metadata",
            {}
        )

        distance = result.get(
            "distance"
        )

        document_name = metadata.get(
            "document",
            "Unknown document"
        )

        chunk_number = metadata.get(
            "chunk",
            "Unknown"
        )

        page_number = metadata.get(
            "page",
            "Unknown"
        )

        if distance is not None:

            retrieval_information = (
                f"Retrieval distance: {distance:.4f}"
            )

        else:

            retrieval_information = (
                "Retrieval distance: Unknown"
            )

        context_parts.append(
            f"""
SOURCE:
Document: {document_name}
Page: {page_number}
Chunk: {chunk_number}
{retrieval_information}

CONTENT:
{document_text}
"""
        )

    return "\n\n".join(
        context_parts
    )


# =========================================================
# BUILD SOURCE INFORMATION
# =========================================================

def build_sources(
    retrieved_results
):
    """
    Extract document/page information from
    retrieved RAG results.

    This metadata is sent to the frontend so
    Garuda AI can display the sources used
    for an answer.
    """

    sources = []

    seen = set()

    for result in retrieved_results:

        metadata = result.get(
            "metadata",
            {}
        )

        document_name = metadata.get(
            "document",
            "Unknown document"
        )

        page_number = metadata.get(
            "page",
            "Unknown"
        )

        chunk_number = metadata.get(
            "chunk",
            "Unknown"
        )

        source_key = (
            document_name,
            page_number,
            chunk_number
        )

        if source_key in seen:
            continue

        seen.add(source_key)

        sources.append({
            "document": document_name,
            "page": page_number,
            "chunk": chunk_number
        })

    return sources


# =========================================================
# CHAT + RAG
# =========================================================

@app.post("/api/chat")
async def chat(
    request: ChatRequest
):

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

    user_question = (
        request.messages[-1].content
    )


    # -----------------------------------------------------
    # 3. Create conversation if one doesn't exist
    # -----------------------------------------------------

    conversation_id = (
        request.conversation_id
    )

    if conversation_id is None:

        conversation_id = create_conversation(
            user_question[:50]
        )

    else:

        update_conversation_title(
            conversation_id,
            user_question[:50]
        )


    # -----------------------------------------------------
    # 4. Get previous conversation history
    # -----------------------------------------------------

    previous_messages = get_messages(
        conversation_id
    )

    conversation_history = (
        build_conversation_history(
            previous_messages
        )
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

    retrieved_results = search_documents(
        user_question,
        top_k=3,
        document_name=request.document_name
    )


    # -----------------------------------------------------
    # 7. Prepare document context
    # -----------------------------------------------------

    context = build_document_context(
        retrieved_results
    )


    # -----------------------------------------------------
    # 8. Build source metadata
    # -----------------------------------------------------

    sources = build_sources(
        retrieved_results
    )


    # -----------------------------------------------------
    # 9. Debug information
    # -----------------------------------------------------

    print()
    print("=================================================")
    print("RAG SEARCH")
    print("=================================================")
    print(
        f"Question: {user_question}"
    )
    print(
        f"Selected document: "
        f"{request.document_name}"
    )
    print(
        f"Retrieved chunks: "
        f"{len(retrieved_results)}"
    )

    if retrieved_results:

        print("Retrieved distances:")

        for result in retrieved_results:

            print(
                f"  - "
                f"{result.get('distance', 'Unknown')}"
            )

    else:

        print(
            "No sufficiently relevant chunks found."
        )

    print(
        f"Sources: {sources}"
    )
    print("=================================================")
    print()


    # -----------------------------------------------------
    # 10. Build grounded prompt
    # -----------------------------------------------------

    prompt = f"""
You are Garuda AI, an intelligent AI assistant.

Your job is to answer the user's latest question while
maintaining awareness of the previous conversation.

=================================================
CONVERSATION RULES
=================================================

1. Use the conversation history to understand references
   to earlier messages.

2. If the user previously provided information such as
   their name, preferences, project details, or other
   facts, use that information when relevant.

3. Do not claim that you do not know something if the
   information was already provided earlier in the
   conversation.

4. Treat the conversation history as the context of the
   current conversation.

5. Do not confuse information from the document context
   with information from the conversation history.


=================================================
DOCUMENT / RAG RULES
=================================================

1. DOCUMENT CONTEXT contains information retrieved from
   the currently selected uploaded document.

2. Retrieved document context has already passed a
   relevance filter.

3. When retrieved document context is relevant to the
   user's question, use it as the primary source for
   answering that question.

4. Do not claim that information came from the document
   unless that information is supported by the retrieved
   document context.

5. Pay attention to the SOURCE information associated
   with each retrieved chunk.

6. SOURCE contains:

   - Document name
   - Page number
   - Chunk number

7. Do not invent facts and attribute them to the uploaded
   document.

8. If no sufficiently relevant document context was
   retrieved, do not pretend that the uploaded document
   contains the answer.

9. If the user's question is clearly about the selected
   document but the retrieved context does not contain
   enough information to answer it, clearly state that
   the available document context does not provide enough
   information.

10. If the question is a general question unrelated to
    the selected document and no relevant document
    context was retrieved, you may answer using general
    knowledge.

11. Do not use information from another uploaded document
    when a specific document has been selected.

12. Do not mention ChromaDB, embeddings, vector databases,
    retrieval distances, or the RAG pipeline unless the
    user asks about them.


=================================================
RESPONSE RULES
=================================================

1. Provide a helpful and accurate answer.

2. Prefer retrieved document context when it is relevant.

3. Maintain continuity with the conversation history.

4. Do not claim that information is unavailable merely
   because it is not present in the uploaded document
   when the question is a general question.

5. For document-specific questions, rely on the retrieved
   document context and clearly distinguish when the
   available context is insufficient.

6. For programming questions, provide working code when
   appropriate.

7. Format answers using Markdown.

8. Use proper Markdown headings with #, ##, ###.

9. Use numbered lists for ordered steps.

10. Use bullet points for unordered lists.

11. Use LaTeX notation for mathematical equations.

12. Give clear and useful explanations.


=================================================
CURRENT SELECTED DOCUMENT
=================================================

{request.document_name or "No specific document selected"}


=================================================
PREVIOUS CONVERSATION
=================================================

{conversation_history}


=================================================
RETRIEVED DOCUMENT CONTEXT
=================================================

{context}


=================================================
LATEST USER QUESTION
=================================================

{user_question}


=================================================
FINAL ANSWER
=================================================
"""


    # -----------------------------------------------------
    # 11. Generate streaming response
    # -----------------------------------------------------

    def generate():

        assistant_text = ""

        try:

            print(
                f"Using Gemini model: "
                f"{GEMINI_MODEL}"
            )

            print(
                f"Document filter: "
                f"{request.document_name}"
            )

            response = (
                client.models.generate_content_stream(
                    model=GEMINI_MODEL,
                    contents=prompt,
                )
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
                "\n\n⚠️ Garuda AI encountered an error "
                "while connecting to the AI model.\n\n"
                f"Error: {str(e)}"
            )

            yield error_message


    # -----------------------------------------------------
    # 12. Prepare source header
    # -----------------------------------------------------

    sources_header = json.dumps(
        sources,
        separators=(",", ":"),
        ensure_ascii=True
    )


    # -----------------------------------------------------
    # 13. Return streaming response
    # -----------------------------------------------------

    return StreamingResponse(

        generate(),

        media_type="text/plain",

        headers={
            "X-Conversation-ID": str(
                conversation_id
            ),

            "X-Sources": sources_header
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


    # -----------------------------------------------------
    # 5. Extract text page-by-page
    # -----------------------------------------------------

    pages = []

    total_characters = 0

    for page_number, page in enumerate(
        reader.pages,
        start=1
    ):

        page_text = page.extract_text()

        if page_text:

            page_text = page_text.strip()

            if page_text:

                pages.append({
                    "page": page_number,
                    "text": page_text
                })

                total_characters += len(
                    page_text
                )


    # -----------------------------------------------------
    # 6. Check extracted text
    # -----------------------------------------------------

    if not pages:

        return {
            "error":
                "Could not extract text from this PDF."
        }


    # -----------------------------------------------------
    # 7. Create page-aware chunks + embeddings
    # -----------------------------------------------------

    result = add_pages(
        pages,
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

        "pages_with_text":
            len(pages),

        "characters":
            total_characters,

        "chunks":
            result["chunks"],

        "message":
            "PDF processed and stored in ChromaDB successfully."

    }