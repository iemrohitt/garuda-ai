import { useState } from "react";
import "./App.css";

function App() {

  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState([]);
  const [uploading, setUploading] = useState(false);
  const [generating, setGenerating] = useState(false);


  // =====================================================
  // SEND MESSAGE
  // =====================================================

  const sendMessage = async () => {

    if (!message.trim() || generating || uploading) {
      return;
    }


    const userMessage = {
      role: "user",
      content: message
    };


    // Save the current conversation before
    // adding the new user message
    const conversation = [
      ...messages,
      userMessage
    ];


    // Show user message immediately
    setMessages(conversation);

    setMessage("");

    setGenerating(true);


    // Add an empty assistant message
    // which will be filled while streaming
    setMessages([
      ...conversation,
      {
        role: "assistant",
        content: ""
      }
    ]);


    try {

      const response = await fetch(
        "http://127.0.0.1:8000/api/chat",
        {
          method: "POST",

          headers: {
            "Content-Type": "application/json"
          },

          body: JSON.stringify({
            messages: conversation
          })
        }
      );


      if (!response.ok) {

        throw new Error(
          `Server error: ${response.status}`
        );

      }


      // =================================================
      // STREAM RESPONSE
      // =================================================

      if (!response.body) {

        throw new Error(
          "Streaming is not supported by this browser."
        );

      }


      const reader = response.body.getReader();

      const decoder = new TextDecoder();

      let assistantText = "";


      while (true) {

        const { value, done } =
          await reader.read();


        if (done) {
          break;
        }


        // Convert received bytes into text
        const chunk = decoder.decode(
          value,
          {
            stream: true
          }
        );


        assistantText += chunk;


        // Update the last assistant message
        setMessages((previous) => {

          const updatedMessages = [
            ...previous
          ];


          updatedMessages[
            updatedMessages.length - 1
          ] = {

            role: "assistant",

            content: assistantText

          };


          return updatedMessages;

        });

      }


    } catch (error) {

      console.error(
        "Chat error:",
        error
      );


      setMessages((previous) => {

        const updatedMessages = [
          ...previous
        ];


        updatedMessages[
          updatedMessages.length - 1
        ] = {

          role: "assistant",

          content:
            "Sorry, Garuda AI could not connect to the server."

        };


        return updatedMessages;

      });

    } finally {

      setGenerating(false);

    }

  };


  // =====================================================
  // UPLOAD PDF
  // =====================================================

  const uploadPDF = async (event) => {

    const file = event.target.files[0];

    if (!file) {
      return;
    }


    // ---------------------------------------------------
    // Check file type
    // ---------------------------------------------------

    if (
      !file.name
        .toLowerCase()
        .endsWith(".pdf")
    ) {

      alert(
        "Please select a PDF file."
      );

      event.target.value = "";

      return;

    }


    setUploading(true);


    const formData = new FormData();

    formData.append(
      "file",
      file
    );


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
          data.error ||
          "PDF upload failed."
        );

      }


      alert(
        `PDF uploaded successfully!\n\n` +
        `File: ${data.filename}\n` +
        `Pages: ${data.pages}\n` +
        `Chunks: ${data.chunks}`
      );


    } catch (error) {

      console.error(
        "Upload error:",
        error
      );


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

    if (generating) {
      return;
    }

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
          disabled={generating}
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

                  {/* Streaming indicator */}

                  {generating &&
                    index === messages.length - 1 &&
                    msg.role === "assistant" && (

                    <span className="typing-indicator">
                      ▌
                    </span>

                  )}

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

              {uploading
                ? "⏳"
                : "📎"}

            </label>


            <input
              id="pdf-upload"
              type="file"
              accept=".pdf,application/pdf"
              onChange={uploadPDF}
              disabled={
                uploading ||
                generating
              }
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
                  : generating
                    ? "Garuda AI is thinking..."
                    : "Ask Garuda AI..."
              }

              disabled={
                uploading ||
                generating
              }

            />


            {/* SEND BUTTON */}

            <button
              onClick={sendMessage}
              disabled={
                uploading ||
                generating ||
                !message.trim()
              }
            >

              {generating
                ? "⏳"
                : "➤"}

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