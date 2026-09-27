import { useEffect, useState } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import remarkMath from "remark-math";
import rehypeKatex from "rehype-katex";
import { Prism as SyntaxHighlighter } from "react-syntax-highlighter";
import { oneDark } from "react-syntax-highlighter/dist/esm/styles/prism";
import "katex/dist/katex.min.css";
import "./App.css";

const API_URL = "http://127.0.0.1:8000";

function App() {
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [conversations, setConversations] = useState([]);
  const [conversationId, setConversationId] = useState(null);
  const [uploading, setUploading] = useState(false);
  const [loading, setLoading] = useState(false);

  /*
   * =====================================================
   * SELECTED DOCUMENT
   *
   * Stores the name of the PDF currently being used
   * for RAG retrieval.
   * =====================================================
   */
  const [selectedDocument, setSelectedDocument] =
    useState(null);

  useEffect(() => {
    loadConversations();
  }, []);

  /* =====================================================
     LOAD ALL CONVERSATIONS
  ===================================================== */

  const loadConversations = async () => {
    try {
      const response = await fetch(
        `${API_URL}/api/conversations`
      );

      if (!response.ok) {
        throw new Error(
          "Failed to load conversations"
        );
      }

      const data = await response.json();

      if (Array.isArray(data)) {
        setConversations(data);
      } else if (
        Array.isArray(data.conversations)
      ) {
        setConversations(
          data.conversations
        );
      } else {
        setConversations([]);
      }
    } catch (error) {
      console.error(
        "Error loading conversations:",
        error
      );

      setConversations([]);
    }
  };

  /* =====================================================
     LOAD SINGLE CONVERSATION
  ===================================================== */

  const loadConversation = async (id) => {
    try {
      const response = await fetch(
        `${API_URL}/api/conversations/${id}/messages`
      );

      if (!response.ok) {
        throw new Error(
          "Failed to load conversation messages"
        );
      }

      const data = await response.json();

      setConversationId(id);

      if (Array.isArray(data)) {
        setMessages(data);
      } else if (
        Array.isArray(data.messages)
      ) {
        setMessages(data.messages);
      } else {
        setMessages([]);
      }

      /*
       * The current database stores conversation messages,
       * but not the selected PDF name.
       *
       * Therefore, clear the selected document when
       * loading an older conversation.
       */
      setSelectedDocument(null);

      setInput("");
    } catch (error) {
      console.error(
        "Error loading conversation:",
        error
      );
    }
  };

  /* =====================================================
     NEW CHAT
  ===================================================== */

  const newChat = () => {
    setConversationId(null);
    setMessages([]);
    setInput("");

    /*
     * Clear the currently selected PDF
     * when starting a completely new chat.
     */
    setSelectedDocument(null);
  };

  /* =====================================================
     DELETE CONVERSATION
  ===================================================== */

  const deleteConversation = async (id) => {
    try {
      const response = await fetch(
        `${API_URL}/api/conversations/${id}`,
        {
          method: "DELETE",
        }
      );

      if (!response.ok) {
        throw new Error(
          "Failed to delete conversation"
        );
      }

      if (conversationId === id) {
        newChat();
      }

      await loadConversations();
    } catch (error) {
      console.error(
        "Error deleting conversation:",
        error
      );
    }
  };

  /* =====================================================
     SEND MESSAGE
  ===================================================== */

  const sendMessage = async () => {
    if (!input.trim() || loading) {
      return;
    }

    const userMessage = {
      role: "user",
      content: input.trim(),
    };

    const updatedMessages = [
      ...messages,
      userMessage,
    ];

    setMessages(updatedMessages);
    setInput("");
    setLoading(true);

    try {
      const response = await fetch(
        `${API_URL}/api/chat`,
        {
          method: "POST",

          headers: {
            "Content-Type": "application/json",
          },

          /*
           * document_name tells the backend which
           * uploaded PDF should be searched.
           */
          body: JSON.stringify({
            messages: updatedMessages,
            conversation_id: conversationId,
            document_name: selectedDocument,
          }),
        }
      );

      if (!response.ok) {
        const errorText =
          await response.text();

        console.error(
          "Backend error:",
          errorText
        );

        throw new Error(
          `Chat request failed: ${response.status}`
        );
      }

      /* =================================================
         GET CONVERSATION ID
      ================================================= */

      const newConversationId =
        response.headers.get(
          "X-Conversation-ID"
        ) ||
        response.headers.get(
          "x-conversation-id"
        );

      if (
        newConversationId &&
        !conversationId
      ) {
        setConversationId(
          newConversationId
        );
      }

      /* =================================================
         GET RAG SOURCES
      ================================================= */

      const sourcesHeader =
        response.headers.get(
          "X-Sources"
        ) ||
        response.headers.get(
          "x-sources"
        );

      let retrievedSources = [];

      if (sourcesHeader) {
        try {
          retrievedSources =
            JSON.parse(
              sourcesHeader
            );
        } catch (error) {
          console.error(
            "Failed to parse RAG sources:",
            error
          );
        }
      }

      if (!response.body) {
        throw new Error(
          "No response body received from backend"
        );
      }

      /* =================================================
         CREATE EMPTY ASSISTANT MESSAGE
      ================================================= */

      const assistantMessage = {
        role: "assistant",
        content: "",
        sources: retrievedSources,
      };

      setMessages((prev) => [
        ...prev,
        assistantMessage,
      ]);

      /* =================================================
         STREAM RESPONSE
      ================================================= */

      const reader =
        response.body.getReader();

      const decoder =
        new TextDecoder();

      let assistantText = "";

      while (true) {
        const {
          value,
          done,
        } = await reader.read();

        if (done) {
          break;
        }

        const chunk =
          decoder.decode(value, {
            stream: true,
          });

        assistantText += chunk;

        setMessages((prev) => {
          const updated = [...prev];

          if (
            updated.length > 0 &&
            updated[
              updated.length - 1
            ].role === "assistant"
          ) {
            updated[
              updated.length - 1
            ] = {
              ...updated[
                updated.length - 1
              ],
              content: assistantText,
              sources: retrievedSources,
            };
          }

          return updated;
        });
      }

      /* =================================================
         REFRESH SIDEBAR
      ================================================= */

      await loadConversations();
    } catch (error) {
      console.error(
        "Error sending message:",
        error
      );

      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content:
            "Sorry, something went wrong while processing your request.",
          sources: [],
        },
      ]);
    } finally {
      setLoading(false);
    }
  };

  /* =====================================================
     ENTER KEY
  ===================================================== */

  const handleKeyDown = (event) => {
    if (
      event.key === "Enter" &&
      !event.shiftKey
    ) {
      event.preventDefault();
      sendMessage();
    }
  };

  /* =====================================================
     PDF UPLOAD
  ===================================================== */

  const uploadPDF = async (event) => {
    const file =
      event.target.files?.[0];

    if (!file) {
      return;
    }

    if (
      file.type !==
      "application/pdf"
    ) {
      alert(
        "Please select a PDF file."
      );

      event.target.value = "";
      return;
    }

    setUploading(true);

    try {
      const formData =
        new FormData();

      formData.append(
        "file",
        file
      );

      const response =
        await fetch(
          `${API_URL}/api/upload`,
          {
            method: "POST",
            body: formData,
          }
        );

      if (!response.ok) {
        throw new Error(
          "PDF upload failed"
        );
      }

      const data =
        await response.json();

      /*
       * Remember the uploaded document.
       *
       * Future chat requests will send this
       * filename to the backend.
       */
      setSelectedDocument(
        data.filename || file.name
      );

      alert(
        `PDF uploaded successfully!\n\nFile: ${file.name}\nPages: ${
          data.pages ?? "N/A"
        }\nChunks: ${
          data.chunks ?? "N/A"
        }`
      );
    } catch (error) {
      console.error(
        "Error uploading PDF:",
        error
      );

      alert(
        "Failed to upload PDF."
      );
    } finally {
      setUploading(false);
      event.target.value = "";
    }
  };

  /* =====================================================
     COPY CODE BUTTON
  ===================================================== */

  const CopyButton = ({ code }) => {
    const [copied, setCopied] =
      useState(false);

    const copyCode = async () => {
      try {
        await navigator.clipboard.writeText(
          code
        );

        setCopied(true);

        setTimeout(() => {
          setCopied(false);
        }, 1500);
      } catch (error) {
        console.error(
          "Copy failed:",
          error
        );
      }
    };

    return (
      <button
        type="button"
        className="copy-code-button"
        onClick={copyCode}
      >
        {copied
          ? "Copied!"
          : "Copy"}
      </button>
    );
  };

  /* =====================================================
     MARKDOWN COMPONENTS
  ===================================================== */

  const markdownComponents = {
    /*
     * ReactMarkdown normally wraps code blocks
     * inside a <pre> element.
     *
     * We already create our own code-block wrapper,
     * so remove the default <pre> wrapper.
     */

    pre({ children }) {
      return children;
    },

    /* =================================================
       CODE BLOCK
    ================================================= */

    code({
      inline,
      className,
      children,
      ...props
    }) {
      const match =
        /language-([\w+-]+)/.exec(
          className || ""
        );

      const code =
        String(children).replace(
          /\n$/,
          ""
        );

      const language =
        match?.[1] || "text";

      /* -----------------------------------------------
         INLINE CODE
      ----------------------------------------------- */

      if (inline) {
        return (
          <code
            className={className}
            {...props}
          >
            {children}
          </code>
        );
      }

      /* -----------------------------------------------
         FULL CODE BLOCK
      ----------------------------------------------- */

      return (
        <div className="code-block-wrapper">

          <div className="code-block-header">

            <span className="code-language">
              {language}
            </span>

            <CopyButton
              code={code}
            />

          </div>

          <SyntaxHighlighter
            style={oneDark}
            language={language}
            PreTag="div"
            className="syntax-highlighter"
            wrapLongLines={false}
          >
            {code}
          </SyntaxHighlighter>

        </div>
      );
    },

    /* =================================================
       HEADINGS
    ================================================= */

    h1({ children }) {
      return (
        <h1 className="markdown-h1">
          {children}
        </h1>
      );
    },

    h2({ children }) {
      return (
        <h2 className="markdown-h2">
          {children}
        </h2>
      );
    },

    h3({ children }) {
      return (
        <h3 className="markdown-h3">
          {children}
        </h3>
      );
    },

    h4({ children }) {
      return (
        <h4 className="markdown-h4">
          {children}
        </h4>
      );
    },

    /* =================================================
       LISTS
    ================================================= */

    ol({ children }) {
      return (
        <ol className="markdown-ordered-list">
          {children}
        </ol>
      );
    },

    ul({ children }) {
      return (
        <ul className="markdown-unordered-list">
          {children}
        </ul>
      );
    },

    li({ children }) {
      return (
        <li className="markdown-list-item">
          {children}
        </li>
      );
    },

    /* =================================================
       PARAGRAPHS
    ================================================= */

    p({ children }) {
      return (
        <p className="markdown-paragraph">
          {children}
        </p>
      );
    },

    /* =================================================
       BLOCKQUOTE
    ================================================= */

    blockquote({ children }) {
      return (
        <blockquote className="markdown-blockquote">
          {children}
        </blockquote>
      );
    },

    /* =================================================
       TABLE
    ================================================= */

    table({ children }) {
      return (
        <div className="markdown-table-wrapper">
          <table className="markdown-table">
            {children}
          </table>
        </div>
      );
    },

    /* =================================================
       LINKS
    ================================================= */

    a({
      href,
      children,
    }) {
      return (
        <a
          href={href}
          target="_blank"
          rel="noopener noreferrer"
          className="markdown-link"
        >
          {children}
        </a>
      );
    },

    /* =================================================
       HORIZONTAL RULE
    ================================================= */

    hr() {
      return (
        <hr className="markdown-horizontal-rule" />
      );
    },
  };

  /* =====================================================
     UI
  ===================================================== */

  return (
    <div className="app">

      {/* =================================================
          SIDEBAR
      ================================================= */}

      <aside className="sidebar">

        <div className="sidebar-header">

          <h1>
            🦅 Garuda AI
          </h1>

        </div>

        <button
          type="button"
          className="new-chat-button"
          onClick={newChat}
        >
          + New Chat
        </button>

        <div className="recent-chats">

          <h3>
            Recent Chats
          </h3>

          {conversations.length ===
          0 ? (
            <p className="sidebar-message">
              No conversations yet.
            </p>
          ) : (
            conversations.map(
              (conversation) => (
                <div
                  key={
                    conversation.id
                  }
                  className={`conversation-item ${
                    conversationId ===
                    conversation.id
                      ? "active"
                      : ""
                  }`}
                >

                  <button
                    type="button"
                    className="conversation-button"
                    onClick={() =>
                      loadConversation(
                        conversation.id
                      )
                    }
                  >

                    <div className="conversation-title">
                      {conversation.title ||
                        "New Conversation"}
                    </div>

                    {conversation.created_at && (
                      <div className="conversation-date">
                        {new Date(
                          conversation.created_at
                        ).toLocaleDateString()}
                      </div>
                    )}

                  </button>

                  <button
                    type="button"
                    className="delete-button"
                    onClick={() =>
                      deleteConversation(
                        conversation.id
                      )
                    }
                    title="Delete conversation"
                  >
                    🗑
                  </button>

                </div>
              )
            )
          )}

        </div>
      </aside>

      {/* =================================================
          MAIN
      ================================================= */}

      <main className="main">

        {/* HEADER */}

        <header className="header">

          <div>

            <h2>
              Garuda AI
            </h2>

            <p>
              Your intelligent AI assistant
            </p>

          </div>

          {/* =================================================
              SELECTED DOCUMENT
          ================================================= */}

          {selectedDocument && (
            <div className="selected-document">

              <span className="document-icon">
                📄
              </span>

              <span
                className="document-name"
                title={selectedDocument}
              >
                {selectedDocument}
              </span>

            </div>
          )}

        </header>

        {/* CHAT */}

        <div className="chat-container">

          {messages.length ===
            0 && (
            <div className="welcome">

              <div className="welcome-icon">
                🦅
              </div>

              <h1>
                Welcome to Garuda AI
              </h1>

              <p>
                Ask questions, upload
                documents, and interact
                with your AI assistant.
              </p>

            </div>
          )}

          {messages.length >
            0 && (
            <div className="messages">

              {messages.map(
                (
                  message,
                  index
                ) => (
                  <div
                    key={index}
                    className={`message ${
                      message.role ===
                      "user"
                        ? "user-message"
                        : "assistant-message"
                    }`}
                  >

                    <div className="message-avatar">

                      {message.role ===
                      "user"
                        ? "👤"
                        : "🦅"}

                    </div>

                    <div className="message-content">

                      <div className="message-role">

                        {message.role ===
                        "user"
                          ? "You"
                          : "Garuda AI"}

                      </div>

                      <div className="message-text">

                        {message.role ===
                        "assistant" ? (
                          <>
                            <ReactMarkdown
                              remarkPlugins={[
                                remarkGfm,
                                remarkMath,
                              ]}
                              rehypePlugins={[
                                rehypeKatex,
                              ]}
                              components={
                                markdownComponents
                              }
                            >
                              {
                                message.content
                              }
                            </ReactMarkdown>

                            {/* =================================================
                                SOURCES
                            ================================================= */}

                            {message.sources &&
                              message.sources.length >
                                0 && (
                                <div className="sources-container">

                                  <div className="sources-title">
                                    📚 Sources
                                  </div>

                                  {message.sources.map(
                                    (
                                      source,
                                      sourceIndex
                                    ) => (
                                      <div
                                        className="source-item"
                                        key={`${source.document}-${source.page}-${source.chunk}-${sourceIndex}`}
                                      >

                                        <div className="source-document">
                                          📄{" "}
                                          {
                                            source.document
                                          }
                                        </div>

                                        <div className="source-page">
                                          Page{" "}
                                          {
                                            source.page
                                          }
                                        </div>

                                      </div>
                                    )
                                  )}

                                </div>
                              )}

                          </>
                        ) : (
                          message.content
                        )}

                      </div>

                    </div>

                  </div>
                )
              )}

              {loading &&
                messages[
                  messages.length - 1
                ]?.role !==
                  "assistant" && (
                  <div className="typing">
                    Garuda AI is thinking...
                  </div>
                )}

            </div>
          )}

        </div>

        {/* =================================================
            INPUT
        ================================================= */}

        <div className="input-area">

          <div className="input-wrapper">

            <label
              className={`upload-button ${
                uploading
                  ? "disabled"
                  : ""
              }`}
              title={
                uploading
                  ? "Uploading..."
                  : "Attach PDF"
              }
            >

              📎

              <input
                type="file"
                accept=".pdf"
                onChange={
                  uploadPDF
                }
                disabled={
                  uploading
                }
                hidden
              />

            </label>

            <textarea
              value={input}
              onChange={(event) =>
                setInput(
                  event.target.value
                )
              }
              onKeyDown={
                handleKeyDown
              }
              placeholder={
                selectedDocument
                  ? `Ask about ${selectedDocument}...`
                  : "Message Garuda AI..."
              }
              rows={1}
              disabled={loading}
            />

            <button
              type="button"
              className="send-button"
              onClick={sendMessage}
              disabled={
                !input.trim() ||
                loading
              }
              title="Send message"
            >
              ➤
            </button>

          </div>

          <div className="input-disclaimer">
            Garuda AI can make
            mistakes. Verify
            important information.
          </div>

        </div>

      </main>

    </div>
  );
}

export default App;