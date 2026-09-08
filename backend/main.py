import os

from dotenv import load_dotenv

from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse

from pydantic import BaseModel

from pypdf import PdfReader

from google import genai

from rag.engine import add_document, search_documents


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
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
# DATA MODELS
# =========================================================

class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    messages: list[Message]


# =========================================================
# HOME
# =========================================================

@app.get("/")
def home():

    return {
        "message": "Garuda AI backend is running!"
    }


# =========================================================
# CHAT + RAG
# =========================================================

@app.post("/api/chat")
async def chat(request: ChatRequest):

    # -----------------------------------------------------
    # 1. Get latest user question
    # -----------------------------------------------------

    user_question = request.messages[-1].content


    # -----------------------------------------------------
    # 2. Search ChromaDB
    # -----------------------------------------------------

    retrieved_chunks = search_documents(
        user_question,
        top_k=3
    )


    # -----------------------------------------------------
    # 3. Check if relevant documents were found
    # -----------------------------------------------------

    if not retrieved_chunks:

        context = (
            "No relevant information was found "
            "in the uploaded documents."
        )

    else:

        context = "\n\n".join(
            retrieved_chunks
        )


    # -----------------------------------------------------
    # 4. Create RAG prompt
    # -----------------------------------------------------

    prompt = f"""
You are Garuda AI, an intelligent AI assistant.

Your job is to answer the user's question using
the provided document context.

IMPORTANT RULES:

1. Use the document context as the primary source.
2. Do not invent information that is not present
   in the context.
3. If the answer cannot be found in the context,
   clearly say that the information is not available
   in the uploaded document.
4. Give a clear and concise answer.
5. Do not mention that you are using ChromaDB,
   embeddings, or a RAG pipeline unless asked.

DOCUMENT CONTEXT:
-----------------
{context}
-----------------

USER QUESTION:
{user_question}
"""


    # -----------------------------------------------------
    # 5. Generate streaming response
    # -----------------------------------------------------

    def generate():

        try:

            response = client.models.generate_content_stream(
                model="gemini-3.6-flash",
                contents=prompt,
            )

            for chunk in response:

                if chunk.text:

                    yield chunk.text

        except Exception as e:

            print(
                "Gemini error:",
                e
            )

            yield (
                "\n\n⚠️ Garuda AI: "
                "The AI model is temporarily unavailable. "
                "Please try again."
            )


    # -----------------------------------------------------
    # 6. Return streaming response
    # -----------------------------------------------------

    return StreamingResponse(
        generate(),
        media_type="text/plain",
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
    # 2. Save PDF
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
    # 3. Read PDF
    # -----------------------------------------------------

    reader = PdfReader(
        file_path
    )

    text = ""


    # -----------------------------------------------------
    # 4. Extract text
    # -----------------------------------------------------

    for page in reader.pages:

        page_text = page.extract_text()

        if page_text:

            text += page_text + "\n"


    # -----------------------------------------------------
    # 5. Create chunks + embeddings
    #    and store in ChromaDB
    # -----------------------------------------------------

    result = add_document(
        text,
        file.filename
    )


    # -----------------------------------------------------
    # 6. Return result
    # -----------------------------------------------------

    return {

        "filename": file.filename,

        "pages": len(
            reader.pages
        ),

        "characters": len(
            text
        ),

        "chunks": result["chunks"],

        "message":
            "PDF processed and stored in ChromaDB successfully."
    }