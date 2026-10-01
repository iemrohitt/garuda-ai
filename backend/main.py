import os
import json
import time

from dotenv import load_dotenv

from fastapi import FastAPI, UploadFile, File, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, JSONResponse

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
    update_conversation_title,
    save_feedback,
    get_feedback_for_message,
    update_message,
    save_user_preference,
    get_user_preferences
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
# GLOBAL ERROR HANDLER
# =========================================================

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):

    print()
    print("=================================================")
    print("UNEXPECTED BACKEND ERROR")
    print("=================================================")
    print(repr(exc))
    print("=================================================")
    print()

    return JSONResponse(
        status_code=500,
        content={
            "error": (
                "Garuda AI encountered an unexpected "
                "server error."
            )
        }
    )


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
        "X-Sources",
        "X-Assistant-Message-ID"
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
# GEMINI MODEL CONFIGURATION
# =========================================================

GEMINI_MODEL = os.getenv(
    "GEMINI_MODEL",
    "gemini-3.6-flash"
)

GEMINI_FALLBACK_MODEL = os.getenv(
    "GEMINI_FALLBACK_MODEL",
    "gemini-3.5-flash-lite"
)

MAX_503_RETRIES = 1

RETRY_DELAY_SECONDS = 2


# =========================================================
# CONVERSATION CONTEXT CONFIGURATION
# =========================================================

MAX_HISTORY_MESSAGES = 12

MAX_MESSAGE_CHARS = 4000

MAX_HISTORY_CHARS = 20000


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


class FeedbackRequest(BaseModel):
    message_id: int
    rating: str
    instruction: str | None = None


class FeedbackRegenerateRequest(BaseModel):
    message_id: int
    instruction: str


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
# MESSAGE FEEDBACK
# =========================================================

@app.post("/api/feedback")
def submit_feedback(
    request: FeedbackRequest
):
    """
    Save feedback for a specific assistant message.

    rating must be either:
    - up
    - down

    For negative feedback, an instruction is required.

    Negative feedback instructions are also saved as
    user preferences so Garuda AI can use them in
    future responses.
    """

    rating = request.rating.strip().lower()

    if rating not in {"up", "down"}:
        raise HTTPException(
            status_code=400,
            detail="Rating must be either 'up' or 'down'."
        )

    instruction = None

    if request.instruction is not None:

        instruction = request.instruction.strip()

        if not instruction:
            instruction = None

    # -----------------------------------------------------
    # Validate message exists and is an assistant message
    # -----------------------------------------------------

    connection = None

    try:

        import sqlite3

        connection = sqlite3.connect(
            "garuda.db"
        )

        connection.row_factory = sqlite3.Row

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT id, role
            FROM messages
            WHERE id = ?
            """,
            (request.message_id,)
        )

        message = cursor.fetchone()

    finally:

        if connection is not None:
            connection.close()

    if message is None:

        raise HTTPException(
            status_code=404,
            detail="Message not found."
        )

    if message["role"] != "assistant":

        raise HTTPException(
            status_code=400,
            detail=(
                "Feedback can only be submitted "
                "for assistant messages."
            )
        )

    # -----------------------------------------------------
    # Negative feedback requires an instruction
    # -----------------------------------------------------

    if rating == "down" and not instruction:

        raise HTTPException(
            status_code=400,
            detail=(
                "Please provide an instruction "
                "for negative feedback."
            )
        )

    # -----------------------------------------------------
    # Save feedback
    # -----------------------------------------------------

    save_feedback(
        request.message_id,
        rating,
        instruction
    )

    # -----------------------------------------------------
    # Save negative feedback instruction
    # as a user preference
    # -----------------------------------------------------

    if rating == "down" and instruction:

        try:

            save_user_preference(
                preference=instruction,
                source="feedback",
                confidence=0.6
            )

            print()
            print("=================================================")
            print("USER PREFERENCE SAVED")
            print("=================================================")
            print(
                f"Preference: {instruction}"
            )
            print(
                "Source: feedback"
            )
            print(
                "Confidence: 0.6"
            )
            print("=================================================")
            print()

        except Exception as preference_error:

            print()
            print("=================================================")
            print("USER PREFERENCE SAVE ERROR")
            print("=================================================")
            print(
                repr(preference_error)
            )
            print("=================================================")
            print()

    return {
        "message": "Feedback saved successfully.",
        "message_id": request.message_id,
        "rating": rating,
        "instruction": instruction
    }


# =========================================================
# GET MESSAGE FEEDBACK
# =========================================================

@app.get("/api/feedback/{message_id}")
def message_feedback(
    message_id: int
):

    feedback = get_feedback_for_message(
        message_id
    )

    return {
        "message_id": message_id,
        "feedback": feedback
    }


# =========================================================
# REGENERATE RESPONSE AFTER NEGATIVE FEEDBACK
# =========================================================

@app.post("/api/feedback/regenerate")
def regenerate_feedback_response(
    request: FeedbackRegenerateRequest
):
    """
    Regenerate an existing assistant response using
    the user's negative-feedback instruction.

    The original assistant message is updated in-place
    instead of creating a second assistant message.
    """

    # -----------------------------------------------------
    # 1. Validate instruction
    # -----------------------------------------------------

    instruction = request.instruction.strip()

    if not instruction:

        raise HTTPException(
            status_code=400,
            detail=(
                "Feedback instruction cannot be empty."
            )
        )

    # -----------------------------------------------------
    # 2. Get saved feedback
    # -----------------------------------------------------

    feedback = get_feedback_for_message(
        request.message_id
    )

    if not feedback:

        raise HTTPException(
            status_code=404,
            detail="Feedback not found."
        )

    # -----------------------------------------------------
    # 3. Make sure this is negative feedback
    # -----------------------------------------------------

    saved_rating = feedback.get(
        "rating"
    )

    if saved_rating != "down":

        raise HTTPException(
            status_code=400,
            detail=(
                "Response regeneration is only "
                "available for negative feedback."
            )
        )

    # -----------------------------------------------------
    # 4. Get original assistant message
    # -----------------------------------------------------

    connection = None

    try:

        import sqlite3

        connection = sqlite3.connect(
            "garuda.db"
        )

        connection.row_factory = sqlite3.Row

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                id,
                conversation_id,
                role,
                content
            FROM messages
            WHERE id = ?
            """,
            (request.message_id,)
        )

        assistant_message = cursor.fetchone()

    finally:

        if connection is not None:
            connection.close()

    if assistant_message is None:

        raise HTTPException(
            status_code=404,
            detail="Assistant message not found."
        )

    if assistant_message["role"] != "assistant":

        raise HTTPException(
            status_code=400,
            detail=(
                "Only assistant messages can "
                "be regenerated."
            )
        )

    conversation_id = assistant_message[
        "conversation_id"
    ]

    original_answer = assistant_message[
        "content"
    ]

    # -----------------------------------------------------
    # 5. Find the user question immediately before
    #    this assistant response
    # -----------------------------------------------------

    connection = None

    try:

        connection = sqlite3.connect(
            "garuda.db"
        )

        connection.row_factory = sqlite3.Row

        cursor = connection.cursor()

        cursor.execute(
            """
            SELECT
                id,
                role,
                content
            FROM messages
            WHERE
                conversation_id = ?
                AND id < ?
                AND role = 'user'
            ORDER BY id DESC
            LIMIT 1
            """,
            (
                conversation_id,
                request.message_id
            )
        )

        user_message = cursor.fetchone()

    finally:

        if connection is not None:
            connection.close()

    if user_message is None:

        raise HTTPException(
            status_code=404,
            detail=(
                "The user question associated "
                "with this response could not be found."
            )
        )

    user_question = user_message[
        "content"
    ]

    # -----------------------------------------------------
    # 6. Build regeneration prompt
    # -----------------------------------------------------

    regeneration_prompt = f"""
You are Garuda AI.

The user was not satisfied with your previous answer.
Generate a new answer to the same user question while
following the user's feedback instruction carefully.

=================================================
USER QUESTION
=================================================

{user_question}

=================================================
ORIGINAL ANSWER
=================================================

{original_answer}

=================================================
USER FEEDBACK / INSTRUCTION
=================================================

{instruction}

=================================================
REGENERATION RULES
=================================================

1. Answer the original user question again.

2. Follow the user's feedback instruction carefully.

3. Do not mention that the user gave negative feedback.

4. Do not mention this regeneration process.

5. Do not say that you are correcting the previous answer
   unless the user explicitly asks for that.

6. Keep information from the original answer that is still
   useful and correct.

7. Change the response according to the user's instruction.

8. If the instruction asks for a different style, structure,
   length, level of detail, or explanation approach, follow it.

9. Do not invent information.

10. If the original answer contained an error and the feedback
    clearly identifies the desired correction, correct it.

11. Format the response using Markdown.

=================================================
NEW ANSWER
=================================================
"""

    # -----------------------------------------------------
    # 7. Generate revised response
    # -----------------------------------------------------

    regenerated_text = ""

    try:

        print()
        print("=================================================")
        print("REGENERATING RESPONSE FROM USER FEEDBACK")
        print("=================================================")
        print(
            f"Message ID: {request.message_id}"
        )
        print(
            f"Conversation ID: {conversation_id}"
        )
        print(
            f"Feedback instruction: {instruction}"
        )
        print("=================================================")
        print()

        response = client.models.generate_content(
            model=GEMINI_MODEL,
            contents=regeneration_prompt
        )

        regenerated_text = (
            response.text
            if response.text
            else ""
        )

    except Exception as primary_error:

        print()
        print("=================================================")
        print("FEEDBACK REGENERATION PRIMARY ERROR")
        print("=================================================")
        print(repr(primary_error))
        print("=================================================")
        print()

        error_type = classify_gemini_error(
            primary_error
        )

        if error_type in {
            "temporary",
            "quota"
        }:

            try:

                print(
                    f"Trying feedback regeneration "
                    f"with fallback model: "
                    f"{GEMINI_FALLBACK_MODEL}"
                )

                response = client.models.generate_content(
                    model=GEMINI_FALLBACK_MODEL,
                    contents=regeneration_prompt
                )

                regenerated_text = (
                    response.text
                    if response.text
                    else ""
                )

            except Exception as fallback_error:

                print()
                print("=================================================")
                print(
                    "FEEDBACK REGENERATION FALLBACK ERROR"
                )
                print("=================================================")
                print(repr(fallback_error))
                print("=================================================")
                print()

                fallback_error_type = (
                    classify_gemini_error(
                        fallback_error
                    )
                )

                raise HTTPException(
                    status_code=503,
                    detail=build_gemini_error_message(
                        fallback_error_type,
                        GEMINI_FALLBACK_MODEL
                    )
                )

        else:

            raise HTTPException(
                status_code=503,
                detail=build_gemini_error_message(
                    error_type,
                    GEMINI_MODEL
                )
            )

    # -----------------------------------------------------
    # 8. Validate generated response
    # -----------------------------------------------------

    if not regenerated_text.strip():

        raise HTTPException(
            status_code=500,
            detail=(
                "Gemini returned an empty regenerated response."
            )
        )

    regenerated_text = regenerated_text.strip()

    # -----------------------------------------------------
    # 9. Update original assistant message
    # -----------------------------------------------------

    try:

        update_message(
            request.message_id,
            regenerated_text
        )

    except Exception as e:

        print()
        print("=================================================")
        print("MESSAGE UPDATE ERROR")
        print("=================================================")
        print(repr(e))
        print("=================================================")
        print()

        raise HTTPException(
            status_code=500,
            detail=(
                "The regenerated response was created, "
                "but the original message could not be updated."
            )
        )

    # -----------------------------------------------------
    # 10. Return regenerated response
    # -----------------------------------------------------

    return {
        "message": (
            "Response regenerated successfully "
            "using your feedback."
        ),
        "message_id": request.message_id,
        "conversation_id": conversation_id,
        "content": regenerated_text
    }


# =========================================================
# BUILD CONVERSATION HISTORY
# =========================================================

def build_conversation_history(
    messages,
    max_messages: int = MAX_HISTORY_MESSAGES,
    max_message_chars: int = MAX_MESSAGE_CHARS,
    max_total_chars: int = MAX_HISTORY_CHARS
):
    """
    Convert database messages into a controlled conversation
    history for the Gemini prompt.
    """

    if not messages:

        return "No previous conversation."

    recent_messages = messages[
        -max_messages:
    ]

    history_parts = []

    total_chars = 0

    for message in recent_messages:

        role = message.get(
            "role",
            ""
        )

        content = message.get(
            "content",
            ""
        )

        if not content:
            continue

        if role == "user":

            role_label = "USER"

        elif role == "assistant":

            role_label = "ASSISTANT"

        else:

            continue

        content = content.strip()

        if len(content) > max_message_chars:

            content = (
                content[:max_message_chars]
                + "\n[Message truncated]"
            )

        formatted_message = (
            f"{role_label}:\n{content}"
        )

        additional_chars = len(
            formatted_message
        )

        if (
            total_chars + additional_chars
            > max_total_chars
        ):

            break

        history_parts.append(
            formatted_message
        )

        total_chars += additional_chars

    if not history_parts:

        return "No previous conversation."

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

        seen.add(
            source_key
        )

        sources.append({
            "document": document_name,
            "page": page_number,
            "chunk": chunk_number
        })

    return sources


# =========================================================
# BUILD USER PREFERENCES CONTEXT
# =========================================================

def build_user_preferences_context():
    """
    Load saved user preferences and convert them into
    instructions that can be included in the Gemini prompt.
    """

    try:

        preferences = get_user_preferences()

    except Exception as e:

        print()
        print("=================================================")
        print("USER PREFERENCES LOAD ERROR")
        print("=================================================")
        print(repr(e))
        print("=================================================")
        print()

        return ""

    if not preferences:

        return ""

    preference_lines = []

    for preference in preferences:

        if isinstance(
            preference,
            dict
        ):

            preference_text = preference.get(
                "preference"
            )

        else:

            try:

                preference_text = preference[
                    "preference"
                ]

            except Exception:

                continue

        if not preference_text:

            continue

        preference_lines.append(
            f"- {preference_text}"
        )

    if not preference_lines:

        return ""

    return "\n".join(
        preference_lines
    )


# =========================================================
# GEMINI ERROR CLASSIFICATION
# =========================================================

def classify_gemini_error(error):
    """
    Classify Gemini API errors so Garuda AI can decide
    whether to retry, use a fallback model, or stop.
    """

    error_text = str(
        error
    ).lower()

    # -----------------------------------------------------
    # Quota / rate limit
    # -----------------------------------------------------

    if (
        "429" in error_text
        or "resource_exhausted" in error_text
        or "quota exceeded" in error_text
        or "rate limit" in error_text
    ):

        return "quota"

    # -----------------------------------------------------
    # Temporary server/model availability
    # -----------------------------------------------------

    if (
        "503" in error_text
        or "unavailable" in error_text
        or "high demand" in error_text
        or "service unavailable" in error_text
    ):

        return "temporary"

    # -----------------------------------------------------
    # Authentication
    # -----------------------------------------------------

    if (
        "401" in error_text
        or "403" in error_text
        or "permission" in error_text
        or "api key" in error_text
    ):

        return "authentication"

    # -----------------------------------------------------
    # Everything else
    # -----------------------------------------------------

    return "unknown"


# =========================================================
# USER-FRIENDLY GEMINI ERROR MESSAGE
# =========================================================

def build_gemini_error_message(
    error_type,
    model
):
    """
    Create a useful message for the frontend instead
    of exposing the raw Gemini exception.
    """

    if error_type == "quota":

        return (
            "\n\n⚠️ **Gemini API quota reached.**\n\n"
            f"Garuda AI could not use `{model}` because "
            "the available API quota/rate limit has been "
            "exceeded.\n\n"
            "Please wait for the quota to reset or "
            "check your Gemini API usage and billing "
            "settings."
        )

    if error_type == "temporary":

        return (
            "\n\n⚠️ **Gemini is temporarily unavailable.**\n\n"
            "The model is currently experiencing high "
            "demand. Garuda AI tried to recover "
            "automatically, but the request could not "
            "be completed."
        )

    if error_type == "authentication":

        return (
            "\n\n⚠️ **Gemini API authentication error.**\n\n"
            "Please check the `GEMINI_API_KEY` configured "
            "in the backend `.env` file."
        )

    return (
        "\n\n⚠️ **Garuda AI could not complete the response.**\n\n"
        "The Gemini API returned an unexpected error. "
        "Please try again."
    )


# =========================================================
# GENERATE GEMINI STREAM
# =========================================================

def generate_with_model(
    model,
    prompt
):
    """
    Start a Gemini streaming request using the supplied
    model.

    The returned object is a Gemini streaming iterator.
    """

    print()
    print("-------------------------------------------------")
    print(
        f"Attempting Gemini model: {model}"
    )
    print("-------------------------------------------------")

    return client.models.generate_content_stream(
        model=model,
        contents=prompt,
    )


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

        raise HTTPException(
            status_code=400,
            detail="No messages were provided."
        )

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

    try:

        retrieved_results = search_documents(
            user_question,
            top_k=3,
            document_name=request.document_name
        )

    except Exception as e:

        print()
        print("=================================================")
        print("RAG SEARCH ERROR")
        print("=================================================")
        print(repr(e))
        print("=================================================")
        print()

        retrieved_results = []

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
    # 9. Load user preferences
    # -----------------------------------------------------

    user_preferences = (
        build_user_preferences_context()
    )

    # -----------------------------------------------------
    # 10. Debug information
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

    print(
        f"Conversation history messages included: "
        f"{min(len(previous_messages), MAX_HISTORY_MESSAGES)}"
    )

    print(
        f"Conversation history characters: "
        f"{len(conversation_history)}"
    )

    print()
    print("=================================================")
    print("USER PREFERENCES")
    print("=================================================")

    if user_preferences:

        print(
            user_preferences
        )

    else:

        print(
            "No saved user preferences."
        )

    print("=================================================")
    print()

    # -----------------------------------------------------
    # 11. Build grounded prompt
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

6. Conversation history may be limited to the most recent
   messages. Do not assume that omitted older messages
   are available.

=================================================
USER RESPONSE PREFERENCES
=================================================

The following preferences were learned from the user's
previous feedback.

Follow these preferences when they are relevant to the
current request.

{user_preferences or "No saved response preferences."}

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

4. Follow the user's saved response preferences when
   they are relevant to the current request.

5. Do not claim that information is unavailable merely
   because it is not present in the uploaded document
   when the question is a general question.

6. For document-specific questions, rely on the retrieved
   document context and clearly distinguish when the
   available context is insufficient.

7. For programming questions, provide working code when
   appropriate.

8. Format answers using Markdown.

9. Use proper Markdown headings with #, ##, ###.

10. Use numbered lists for ordered steps.

11. Use bullet points for unordered lists.

12. Use LaTeX notation for mathematical equations.

13. Give clear and useful explanations.

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
    # 12. Generate streaming response
    # -----------------------------------------------------

    def generate():

        assistant_text = ""

        primary_model_failed = False

        primary_error_type = None

        assistant_message_id = None

        # =================================================
        # ATTEMPT PRIMARY MODEL
        # =================================================

        try:

            print(
                f"Using primary Gemini model: "
                f"{GEMINI_MODEL}"
            )

            print(
                f"Document filter: "
                f"{request.document_name}"
            )

            response = None

            # -------------------------------------------------
            # First attempt
            # -------------------------------------------------

            try:

                response = generate_with_model(
                    GEMINI_MODEL,
                    prompt
                )

            except Exception as e:

                primary_model_failed = True

                primary_error_type = (
                    classify_gemini_error(e)
                )

                print()
                print("=================================================")
                print("PRIMARY GEMINI MODEL ERROR")
                print("=================================================")
                print(
                    f"Model: {GEMINI_MODEL}"
                )
                print(
                    f"Error type: {primary_error_type}"
                )
                print(
                    repr(e)
                )
                print("=================================================")
                print()

            # -------------------------------------------------
            # Temporary 503 retry
            # -------------------------------------------------

            if (
                primary_model_failed
                and primary_error_type == "temporary"
            ):

                for retry_number in range(
                    MAX_503_RETRIES
                ):

                    print(
                        f"Retrying primary model "
                        f"after temporary error "
                        f"(attempt {retry_number + 1})..."
                    )

                    time.sleep(
                        RETRY_DELAY_SECONDS
                    )

                    try:

                        response = generate_with_model(
                            GEMINI_MODEL,
                            prompt
                        )

                        primary_model_failed = False
                        primary_error_type = None

                        print(
                            "Primary model retry succeeded."
                        )

                        break

                    except Exception as e:

                        primary_error_type = (
                            classify_gemini_error(e)
                        )

                        print(
                            "Primary model retry failed:"
                        )

                        print(
                            repr(e)
                        )

            # -------------------------------------------------
            # Stream primary response
            # -------------------------------------------------

            if response is not None:

                try:

                    for chunk in response:

                        if chunk.text:

                            assistant_text += chunk.text

                            yield chunk.text

                except Exception as e:

                    primary_model_failed = True

                    primary_error_type = (
                        classify_gemini_error(e)
                    )

                    print()
                    print("=================================================")
                    print("PRIMARY GEMINI STREAM ERROR")
                    print("=================================================")
                    print(
                        f"Error type: {primary_error_type}"
                    )
                    print(
                        repr(e)
                    )
                    print("=================================================")
                    print()

            # =================================================
            # FALLBACK MODEL
            # =================================================

            if (
                primary_model_failed
                and not assistant_text.strip()
            ):

                print()
                print("=================================================")
                print("USING GEMINI FALLBACK MODEL")
                print("=================================================")
                print(
                    f"Primary: {GEMINI_MODEL}"
                )
                print(
                    f"Fallback: {GEMINI_FALLBACK_MODEL}"
                )
                print("=================================================")
                print()

                try:

                    fallback_response = (
                        generate_with_model(
                            GEMINI_FALLBACK_MODEL,
                            prompt
                        )
                    )

                    for chunk in fallback_response:

                        if chunk.text:

                            assistant_text += chunk.text

                            yield chunk.text

                except Exception as fallback_error:

                    fallback_error_type = (
                        classify_gemini_error(
                            fallback_error
                        )
                    )

                    print()
                    print("=================================================")
                    print("FALLBACK GEMINI ERROR")
                    print("=================================================")
                    print(
                        f"Model: "
                        f"{GEMINI_FALLBACK_MODEL}"
                    )
                    print(
                        f"Error type: "
                        f"{fallback_error_type}"
                    )
                    print(
                        repr(fallback_error)
                    )
                    print("=================================================")
                    print()

                    if fallback_error_type == "quota":

                        error_message = (
                            "\n\n⚠️ **Gemini API quota reached.**\n\n"
                            "Both the primary and fallback "
                            "Gemini models are currently unable "
                            "to process this request because "
                            "their available API quota/rate "
                            "limits are exhausted.\n\n"
                            "Please wait for the quota to reset "
                            "before trying again."
                        )

                    elif fallback_error_type == "temporary":

                        error_message = (
                            "\n\n⚠️ **Gemini is temporarily unavailable.**\n\n"
                            "Garuda AI tried both configured "
                            "Gemini models, but neither was "
                            "available right now.\n\n"
                            "Please try again shortly."
                        )

                    else:

                        error_message = (
                            build_gemini_error_message(
                                fallback_error_type,
                                GEMINI_FALLBACK_MODEL
                            )
                        )

                    yield error_message

            # =================================================
            # PRIMARY FAILED BUT PARTIAL RESPONSE EXISTS
            # =================================================

            elif (
                primary_model_failed
                and assistant_text.strip()
            ):

                print(
                    "Primary model failed after "
                    "partial output. "
                    "Fallback was not started to avoid "
                    "duplicating the response."
                )

                yield (
                    "\n\n⚠️ The Gemini connection was "
                    "interrupted before the response "
                    "was fully completed."
                )

            # =================================================
            # PRIMARY ERROR WITHOUT RESPONSE
            # =================================================

            elif (
                primary_model_failed
                and not assistant_text.strip()
            ):

                error_message = (
                    build_gemini_error_message(
                        primary_error_type,
                        GEMINI_MODEL
                    )
                )

                yield error_message

            # =================================================
            # SAVE COMPLETE AI RESPONSE
            # =================================================

            if assistant_text.strip():

                assistant_message_id = save_message(
                    conversation_id,
                    "assistant",
                    assistant_text
                )

                print(
                    f"Assistant message saved with ID: "
                    f"{assistant_message_id}"
                )

        except Exception as e:

            print()
            print("=================================================")
            print("GEMINI GENERATION ERROR")
            print("=================================================")
            print(
                repr(e)
            )
            print("=================================================")
            print()

            error_type = (
                classify_gemini_error(e)
            )

            error_message = (
                build_gemini_error_message(
                    error_type,
                    GEMINI_MODEL
                )
            )

            yield error_message

    # -----------------------------------------------------
    # 13. Prepare source header
    # -----------------------------------------------------

    sources_header = json.dumps(
        sources,
        separators=(",", ":"),
        ensure_ascii=True
    )

    # -----------------------------------------------------
    # 14. Return streaming response
    # -----------------------------------------------------

    return StreamingResponse(

        generate(),

        media_type="text/plain",

        headers={
            "X-Conversation-ID": str(
                conversation_id
            ),

            "X-Sources": sources_header,

            # The generator executes after the response
            # starts, so the frontend can recover the real
            # assistant message ID by reloading the
            # conversation.
            "X-Assistant-Message-ID": ""
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
    # 1. Check file name
    # -----------------------------------------------------

    if not file.filename:

        raise HTTPException(
            status_code=400,
            detail="No file was provided."
        )

    # -----------------------------------------------------
    # 2. Check file type
    # -----------------------------------------------------

    if not file.filename.lower().endswith(".pdf"):

        raise HTTPException(
            status_code=400,
            detail="Only PDF files are allowed."
        )

    # -----------------------------------------------------
    # 3. Create documents directory
    # -----------------------------------------------------

    os.makedirs(
        "documents",
        exist_ok=True
    )

    # -----------------------------------------------------
    # 4. Create a safe local filename
    # -----------------------------------------------------

    safe_filename = os.path.basename(
        file.filename
    )

    file_path = os.path.join(
        "documents",
        safe_filename
    )

    # -----------------------------------------------------
    # 5. Read uploaded file
    # -----------------------------------------------------

    try:

        file_content = await file.read()

    except Exception as e:

        print()
        print("=================================================")
        print("FILE READ ERROR")
        print("=================================================")
        print(repr(e))
        print("=================================================")
        print()

        raise HTTPException(
            status_code=400,
            detail="The uploaded file could not be read."
        )

    # -----------------------------------------------------
    # 6. Check empty file
    # -----------------------------------------------------

    if not file_content:

        raise HTTPException(
            status_code=400,
            detail="The uploaded PDF is empty."
        )

    # -----------------------------------------------------
    # 7. Save PDF
    # -----------------------------------------------------

    try:

        with open(
            file_path,
            "wb"
        ) as f:

            f.write(file_content)

    except Exception as e:

        print()
        print("=================================================")
        print("FILE SAVE ERROR")
        print("=================================================")
        print(repr(e))
        print("=================================================")
        print()

        raise HTTPException(
            status_code=500,
            detail="The uploaded PDF could not be saved."
        )

    # -----------------------------------------------------
    # 8. Read PDF
    # -----------------------------------------------------

    try:

        reader = PdfReader(
            file_path
        )

    except Exception as e:

        print()
        print("=================================================")
        print("PDF READ ERROR")
        print("=================================================")
        print(repr(e))
        print("=================================================")
        print()

        return {
            "error": (
                "The uploaded PDF could not be read. "
                "It may be corrupted or invalid."
            )
        }

    # -----------------------------------------------------
    # 9. Extract text page-by-page
    # -----------------------------------------------------

    pages = []

    total_characters = 0

    try:

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

    except Exception as e:

        print()
        print("=================================================")
        print("PDF TEXT EXTRACTION ERROR")
        print("=================================================")
        print(repr(e))
        print("=================================================")
        print()

        return {
            "error": (
                "The PDF was opened, but its text "
                "could not be extracted."
            )
        }

    # -----------------------------------------------------
    # 10. Check extracted text
    # -----------------------------------------------------

    if not pages:

        return {
            "error": (
                "Could not extract text from this PDF. "
                "The PDF may contain only scanned images "
                "or otherwise have no extractable text."
            )
        }

    # -----------------------------------------------------
    # 11. Create page-aware chunks + embeddings
    # -----------------------------------------------------

    try:

        result = add_pages(
            pages,
            safe_filename
        )

    except Exception as e:

        print()
        print("=================================================")
        print("RAG PROCESSING ERROR")
        print("=================================================")
        print(repr(e))
        print("=================================================")
        print()

        return {
            "error": (
                "The PDF was read successfully, "
                "but an error occurred while processing it."
            )
        }

    # -----------------------------------------------------
    # 12. Return result
    # -----------------------------------------------------

    return {

        "filename":
            safe_filename,

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