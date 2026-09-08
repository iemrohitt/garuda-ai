import { useState } from "react";
import "./App.css";

function App() {

  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState([]);
  const [uploading, setUploading] = useState(false);


  // =====================================================
  // SEND MESSAGE
  // =====================================================

  const sendMessage = async () => {

    if (!message.trim()) return;

    const userMessage = {
      role: "user",
      content: message
    };

    setMessages((previous) => [
      ...previous,
      userMessage
    ]);

    setMessage("");


    try {

      const response = await fetch(
        "http://127.0.0.1:8000/api/chat",
        {
          method: "POST",

          headers: {
            "Content-Type": "application/json"
          },

          body: JSON.stringify({
            messages: [
              ...messages,
              userMessage
            ]
          })
        }
      );


      if (!response.ok) {

        throw new Error(
          `Server error: ${response.status}`
        );

      }


      const text = await response.text();


      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content: text
        }
      ]);


    } catch (error) {

      console.error(error);

      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content:
            "Sorry, Garuda AI could not connect to the server."
        }
      ]);

    }

  };


  // =====================================================
  // UPLOAD PDF
  // =====================================================

  const uploadPDF = async (event) => {

    const file = event.target.files[0];

    if (!file) return;


    // Make sure it is a PDF

    if (!file.name.toLowerCase().endsWith(".pdf")) {

      alert("Please select a PDF file.");

      event.target.value = "";

      return;

    }


    setUploading(true);


    const formData = new FormData();

    formData.append("file", file);


    try {

      const response = await fetch(
        "http://127.0.0.1:8000/api/upload",
        {
          method: "POST",
          body: formData
        }
      );


      const data = await response.json();


      if (!response.ok) {

        throw new Error(
          data.error || "PDF upload failed."
        );

      }


      alert(
        `PDF uploaded successfully!\n\n` +
        `File: ${data.filename}\n` +
        `Pages: ${data.pages}\n` +
        `Chunks: ${data.chunks}`
      );


    } catch (error) {

      console.error(error);

      alert(
        "Could not upload the PDF.\n\n" +
        error.message
      );

    } finally {

      setUploading(false);

      event.target.value = "";

    }

  };


  // =====================================================
  // NEW CHAT
  // =====================================================

  const newChat = () => {

    setMessages([]);
    setMessage("");

  };


  // =====================================================
  // UI
  // =====================================================

  return (

    <div className="app">


      {/* =================================================
          SIDEBAR
      ================================================= */}

      <aside className="sidebar">


        {/* NEW CHAT */}

        <button
          className="new-chat"
          onClick={newChat}
        >
          + New Chat
        </button>


        {/* CHAT HISTORY */}

        <div className="history">

          <p>Today</p>

          {messages.length > 0 && (

            <div className="history-item">

              Current conversation

            </div>

          )}

        </div>


        {/* SIDEBAR BOTTOM */}

        <div className="sidebar-bottom">

          <div className="sidebar-option">
            ⚙ Settings
          </div>

          <div className="sidebar-option">
            👤 Garuda User
          </div>

        </div>


      </aside>


      {/* =================================================
          MAIN CHAT
      ================================================= */}

      <main className="chat">


        {/* HEADER */}

        <header className="chat-header">

          <h2>
            🦅 Garuda AI
          </h2>

        </header>


        {/* =================================================
            MESSAGES
        ================================================= */}

        <section className="messages">


          {messages.length === 0 ? (

            <div className="welcome">

              <h1>
                How can I help you?
              </h1>

              <p>
                Ask Garuda AI anything or ask questions
                about your uploaded documents.
              </p>

            </div>

          ) : (

            messages.map((msg, index) => (

              <div
                key={index}
                className={`message ${msg.role}`}
              >

                <div className="message-content">

                  {msg.content}

                </div>

              </div>

            ))

          )}


        </section>


        {/* =================================================
            INPUT AREA
        ================================================= */}

        <div className="input-area">


          <div className="input-box">


            {/* PDF UPLOAD */}

            <label
              htmlFor="pdf-upload"
              className="upload-button"
            >

              {uploading ? "⏳" : "📎"}

            </label>


            <input
              id="pdf-upload"
              type="file"
              accept=".pdf,application/pdf"
              onChange={uploadPDF}
              disabled={uploading}
              hidden
            />


            {/* TEXT INPUT */}

            <input
              value={message}

              onChange={(e) =>
                setMessage(e.target.value)
              }

              onKeyDown={(e) => {

                if (
                  e.key === "Enter" &&
                  !e.shiftKey
                ) {

                  e.preventDefault();

                  sendMessage();

                }

              }}

              placeholder={
                uploading
                  ? "Uploading PDF..."
                  : "Ask Garuda AI..."
              }

              disabled={uploading}

            />


            {/* SEND BUTTON */}

            <button
              onClick={sendMessage}
              disabled={uploading}
            >
              ➤
            </button>


          </div>


          <p>
            Garuda AI can make mistakes.
            Check important information.
          </p>


        </div>


      </main>


    </div>

  );

}


export default App;