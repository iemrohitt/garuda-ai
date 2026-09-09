import { useEffect, useState } from "react";
import "./App.css";

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [loading, setLoading] = useState(false);
  const [loadingHistory, setLoadingHistory] = useState(true);
  const [uploading, setUploading] = useState(false);

  useEffect(() => {
    loadConversations();
  }, []);

  const loadConversations = async () => {
    try {
      const response = await fetch(
        "http://127.0.0.1:8000/api/conversations"
      );

      const data = await response.json();
      setConversations(data.conversations || []);
    } catch (error) {
      console.error("Error loading conversations:", error);
    } finally {
      setLoadingHistory(false);
    }
  };

  const loadConversation = async (id) => {
    try {
      setLoadingHistory(true);

      const response = await fetch(
        `http://127.0.0.1:8000/api/conversations/${id}/messages`
      );

      const data = await response.json();

      setConversationId(id);

      setMessages(
        (data.messages || []).map((message) => ({
          role: message.role,
          content: message.content,
        }))
      );
    } catch (error) {
      console.error("Error loading conversation:", error);
    } finally {
      setLoadingHistory(false);
    }
  };

  const sendMessage = async () => {
    if (!input.trim() || loading) return;

    const userMessage = {
      role: "user",
      content: input.trim(),
    };

    const updatedMessages = [...messages, userMessage];

    setMessages(updatedMessages);
    setInput("");
    setLoading(true);

    try {
      const response = await fetch(
        "http://127.0.0.1:8000/api/chat",
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
          },
          body: JSON.stringify({
            messages: updatedMessages,
            conversation_id: conversationId,
          }),
        }
      );

      if (!response.ok) {
        throw new Error("Chat request failed");
      }

      const returnedConversationId =
        response.headers.get("X-Conversation-ID");

      if (returnedConversationId) {
        setConversationId(Number(returnedConversationId));
      }

      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content: "",
        },
      ]);

      if (!response.body) {
        throw new Error("Response body is empty");
      }

      const reader = response.body.getReader();
      const decoder = new TextDecoder();

      let assistantText = "";

      while (true) {
        const { done, value } = await reader.read();

        if (done) break;

        const chunk = decoder.decode(value, {
          stream: true,
        });

        assistantText += chunk;

        setMessages((previous) => {
          const updated = [...previous];

          updated[updated.length - 1] = {
            role: "assistant",
            content: assistantText,
          };

          return updated;
        });
      }

      await loadConversations();
    } catch (error) {
      console.error("Chat error:", error);

      setMessages((previous) => [
        ...previous,
        {
          role: "assistant",
          content:
            "⚠️ Something went wrong. Please check that the backend is running.",
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  const handleKeyDown = (event) => {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault();
      sendMessage();
    }
  };

  const newChat = () => {
    setMessages([]);
    setConversationId(null);
    setInput("");
  };

  const deleteConversation = async (id) => {
    try {
      await fetch(
        `http://127.0.0.1:8000/api/conversations/${id}`,
        {
          method: "DELETE",
        }
      );

      if (conversationId === id) {
        setMessages([]);
        setConversationId(null);
      }

      await loadConversations();
    } catch (error) {
      console.error("Delete error:", error);
    }
  };

  const handleFileUpload = async (event) => {
    const file = event.target.files[0];

    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      alert("Please select a PDF file.");
      event.target.value = "";
      return;
    }

    const formData = new FormData();
    formData.append("file", file);

    try {
      setUploading(true);

      const response = await fetch(
        "http://127.0.0.1:8000/api/upload",
        {
          method: "POST",
          body: formData,
        }
      );

      const data = await response.json();

      if (!response.ok || data.error) {
        alert(data.error || "PDF upload failed.");
        return;
      }

      alert(
        `PDF uploaded successfully!\n\nFile: ${data.filename}\nPages: ${data.pages}\nChunks: ${data.chunks}`
      );
    } catch (error) {
      console.error("Upload error:", error);

      alert(
        "Unable to upload PDF. Make sure the backend is running."
      );
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  };

  const formatDate = (dateString) => {
    if (!dateString) return "";

    const date = new Date(
      dateString.replace(" ", "T") + "Z"
    );

    return date.toLocaleDateString();
  };

  return (
    <div className="app">
      <aside className="sidebar">
        <div className="sidebar-header">
          <h1>🦅 Garuda AI</h1>
        </div>

        <button
          className="new-chat-button"
          onClick={newChat}
        >
          ＋ New Chat
        </button>

        <div className="recent-chats">
          <h3>Recent Chats</h3>

          {loadingHistory ? (
            <p className="sidebar-message">Loading...</p>
          ) : conversations.length === 0 ? (
            <p className="sidebar-message">
              No conversations yet.
            </p>
          ) : (
            conversations.map((conversation) => (
              <div
                key={conversation.id}
                className={`conversation-item ${
                  conversationId === conversation.id
                    ? "active"
                    : ""
                }`}
              >
                <button
                  className="conversation-button"
                  onClick={() =>
                    loadConversation(conversation.id)
                  }
                >
                  <span className="conversation-title">
                    {conversation.title}
                  </span>

                  <span className="conversation-date">
                    {formatDate(
                      conversation.updated_at
                    )}
                  </span>
                </button>

                <button
                  className="delete-button"
                  onClick={() =>
                    deleteConversation(conversation.id)
                  }
                  title="Delete conversation"
                >
                  🗑️
                </button>
              </div>
            ))
          )}
        </div>
      </aside>

      <main className="main">
        <header className="header">
          <div>
            <h2>Garuda AI</h2>
            <p>AI-powered document assistant</p>
          </div>
        </header>

        <div className="chat-container">
          {messages.length === 0 ? (
            <div className="welcome">
              <div className="welcome-icon">🦅</div>

              <h1>Welcome to Garuda AI</h1>

              <p>
                Ask questions, upload documents,
                and get intelligent answers.
              </p>

              <div className="welcome-features">
                <div className="feature-card">
                  <span>📄</span>
                  <h3>Document RAG</h3>
                  <p>
                    Ask questions about your
                    uploaded PDFs.
                  </p>
                </div>

                <div className="feature-card">
                  <span>🧠</span>
                  <h3>AI Powered</h3>
                  <p>
                    Uses Gemini to generate
                    intelligent responses.
                  </p>
                </div>

                <div className="feature-card">
                  <span>💬</span>
                  <h3>Chat History</h3>
                  <p>
                    Your conversations are
                    stored locally.
                  </p>
                </div>
              </div>
            </div>
          ) : (
            <div className="messages">
              {messages.map((message, index) => (
                <div
                  key={index}
                  className={`message ${
                    message.role === "user"
                      ? "user-message"
                      : "assistant-message"
                  }`}
                >
                  <div className="message-avatar">
                    {message.role === "user"
                      ? "👤"
                      : "🦅"}
                  </div>

                  <div className="message-content">
                    <div className="message-role">
                      {message.role === "user"
                        ? "You"
                        : "Garuda AI"}
                    </div>

                    <div className="message-text">
                      {message.content}
                    </div>
                  </div>
                </div>
              ))}

              {loading && (
                <div className="message assistant-message">
                  <div className="message-avatar">
                    🦅
                  </div>

                  <div className="message-content">
                    <div className="message-role">
                      Garuda AI
                    </div>

                    <div className="typing">
                      Thinking...
                    </div>
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="input-area">
          <div className="input-wrapper">
            <label
              className={`upload-button ${
                uploading ? "disabled" : ""
              }`}
              title="Upload PDF"
            >
              📎

              <input
                type="file"
                accept=".pdf,application/pdf"
                onChange={handleFileUpload}
                disabled={uploading}
                hidden
              />
            </label>

            <textarea
              value={input}
              onChange={(event) =>
                setInput(event.target.value)
              }
              onKeyDown={handleKeyDown}
              placeholder={
                uploading
                  ? "Uploading document..."
                  : "Message Garuda AI..."
              }
              disabled={uploading}
              rows={1}
            />

            <button
              className="send-button"
              onClick={sendMessage}
              disabled={
                loading ||
                uploading ||
                !input.trim()
              }
              title="Send message"
            >
              ➤
            </button>
          </div>

          <p className="input-disclaimer">
            Garuda AI can make mistakes. Verify
            important information.
          </p>
        </div>
      </main>
    </div>
  );
}

export default App;