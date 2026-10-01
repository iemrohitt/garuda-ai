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

  // -----------------------------------------------------
  // MESSAGE FEEDBACK
  // -----------------------------------------------------

  const [feedback, setFeedback] = useState({});
  const [feedbackModalOpen, setFeedbackModalOpen] =
    useState(false);
  const [feedbackMessageId, setFeedbackMessageId] =
    useState(null);
  const [feedbackInstruction, setFeedbackInstruction] =
    useState("");
  const [feedbackSubmitting, setFeedbackSubmitting] =
    useState(false);

  /*
   * =====================================================
   * SELECTED DOCUMENT
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
     LOAD FEEDBACK FOR EXISTING ASSISTANT MESSAGES
  ===================================================== */

  const hydrateFeedback = async (messageList) => {
    const assistantMessages =
      messageList.filter(
        (message) =>
          message.role === "assistant" &&
          message.id !== undefined &&
          message.id !== null
      );

    if (assistantMessages.length === 0) {
      setFeedback({});
      return;
    }

    try {
      const feedbackEntries =
        await Promise.all(
          assistantMessages.map(
            async (message) => {
              try {
                const response =
                  await fetch(
                    `${API_URL}/api/feedback/${message.id}`
                  );

                if (!response.ok) {
                  return null;
                }

                const data =
                  await response.json();

                if (!data.feedback) {
                  return null;
                }

                return [
                  String(message.id),
                  data.feedback,
                ];
              } catch (error) {
                console.error(
                  `Error loading feedback for message ${message.id}:`,
                  error
                );

                return null;
              }
            }
          )
        );

      const nextFeedback = {};

      feedbackEntries.forEach(
        (entry) => {
          if (entry) {
            const [
              messageId,
              feedbackData,
            ] = entry;

            nextFeedback[messageId] =
              feedbackData;
          }
        }
      );

      setFeedback(nextFeedback);
    } catch (error) {
      console.error(
        "Error loading message feedback:",
        error
      );
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

      let loadedMessages = [];

      if (Array.isArray(data)) {
        loadedMessages = data;
      } else if (
        Array.isArray(data.messages)
      ) {
        loadedMessages =
          data.messages;
      }

      setMessages(loadedMessages);

      await hydrateFeedback(
        loadedMessages
      );

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
    setFeedback({});

    setFeedbackModalOpen(false);
    setFeedbackMessageId(null);
    setFeedbackInstruction("");
    setFeedbackSubmitting(false);

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
     SUBMIT POSITIVE FEEDBACK
  ===================================================== */

  const submitPositiveFeedback = async (
    messageId
  ) => {
    if (
      messageId === undefined ||
      messageId === null ||
      feedback[String(messageId)]
    ) {
      return;
    }

    try {
      const response = await fetch(
        `${API_URL}/api/feedback`,
        {
          method: "POST",

          headers: {
            "Content-Type":
              "application/json",
          },

          body: JSON.stringify({
            message_id:
              Number(messageId),
            rating: "up",
            instruction: null,
          }),
        }
      );

      if (!response.ok) {
        const errorText =
          await response.text();

        console.error(
          "Positive feedback error:",
          errorText
        );

        throw new Error(
          `Feedback request failed: ${response.status}`
        );
      }

      const data =
        await response.json();

      setFeedback((prev) => ({
        ...prev,

        [String(messageId)]:
          data.feedback || {
            rating: "up",
            instruction: null,
          },
      }));
    } catch (error) {
      console.error(
        "Error submitting positive feedback:",
        error
      );
    }
  };

  /* =====================================================
     OPEN NEGATIVE FEEDBACK MODAL
  ===================================================== */

  const openNegativeFeedback = (
    messageId
  ) => {
    if (
      messageId === undefined ||
      messageId === null ||
      feedback[String(messageId)]
    ) {
      return;
    }

    setFeedbackMessageId(messageId);
    setFeedbackInstruction("");
    setFeedbackModalOpen(true);
  };

  /* =====================================================
     CLOSE NEGATIVE FEEDBACK MODAL
  ===================================================== */

  const closeFeedbackModal = () => {
    if (feedbackSubmitting) {
      return;
    }

    setFeedbackModalOpen(false);
    setFeedbackMessageId(null);
    setFeedbackInstruction("");
  };

  /* =====================================================
     SUBMIT NEGATIVE FEEDBACK + REGENERATE
  ===================================================== */

  const submitNegativeFeedback = async () => {
    const instruction =
      feedbackInstruction.trim();

    const messageId =
      feedbackMessageId;

    if (
      messageId === undefined ||
      messageId === null ||
      !instruction
    ) {
      return;
    }

    setFeedbackSubmitting(true);

    try {
      /* =================================================
         STEP 1
         SAVE NEGATIVE FEEDBACK
      ================================================= */

      const feedbackResponse =
        await fetch(
          `${API_URL}/api/feedback`,
          {
            method: "POST",

            headers: {
              "Content-Type":
                "application/json",
            },

            body: JSON.stringify({
              message_id:
                Number(messageId),
              rating: "down",
              instruction,
            }),
          }
        );

      if (!feedbackResponse.ok) {
        const errorText =
          await feedbackResponse.text();

        console.error(
          "Negative feedback error:",
          errorText
        );

        throw new Error(
          `Feedback request failed: ${feedbackResponse.status}`
        );
      }

      const feedbackData =
        await feedbackResponse.json();

      /* =================================================
         STEP 2
         MARK FEEDBACK AS SUBMITTED
      ================================================= */

      setFeedback((prev) => ({
        ...prev,

        [String(messageId)]:
          feedbackData.feedback || {
            rating: "down",
            instruction,
          },
      }));

      /* =================================================
         STEP 3
         SHOW REGENERATION STATUS
      ================================================= */

      setMessages((prev) =>
        prev.map((message) => {
          if (
            Number(message.id) ===
            Number(messageId)
          ) {
            return {
              ...message,

              content:
                "🔄 Regenerating response based on your feedback...",

              regenerating: true,
            };
          }

          return message;
        })
      );

      /* =================================================
         STEP 4
         CLOSE MODAL
      ================================================= */

      setFeedbackModalOpen(false);
      setFeedbackMessageId(null);
      setFeedbackInstruction("");

      /* =================================================
         STEP 5
         REGENERATE RESPONSE
      ================================================= */

      const regenerateResponse =
        await fetch(
          `${API_URL}/api/feedback/regenerate`,
          {
            method: "POST",

            headers: {
              "Content-Type":
                "application/json",
            },

            body: JSON.stringify({
              message_id:
                Number(messageId),
              instruction,
            }),
          }
        );

      if (!regenerateResponse.ok) {
        const errorText =
          await regenerateResponse.text();

        console.error(
          "Regeneration error:",
          errorText
        );

        throw new Error(
          `Regeneration request failed: ${regenerateResponse.status}`
        );
      }

      const regenerated =
        await regenerateResponse.json();

      /* =================================================
         STEP 6
         REPLACE ORIGINAL RESPONSE
      ================================================= */

      if (
        regenerated &&
        regenerated.content
      ) {
        setMessages((prev) =>
          prev.map((message) => {
            if (
              Number(message.id) ===
              Number(messageId)
            ) {
              return {
                ...message,

                content:
                  regenerated.content,

                regenerating: false,
              };
            }

            return message;
          })
        );
      } else {
        throw new Error(
          "Regeneration returned no content."
        );
      }

      /* =================================================
         STEP 7
         REFRESH CONVERSATION SIDEBAR
      ================================================= */

      await loadConversations();
    } catch (error) {
      console.error(
        "Error submitting negative feedback:",
        error
      );

      /* -----------------------------------------------
         If regeneration fails, show an error while
         keeping the original feedback stored.
      ----------------------------------------------- */

      setMessages((prev) =>
        prev.map((message) => {
          if (
            Number(message.id) ===
            Number(messageId)
          ) {
            return {
              ...message,

              content:
                "Sorry, I couldn't regenerate this response. Your feedback was saved.",

              regenerating: false,
            };
          }

          return message;
        })
      );
    } finally {
      setFeedbackSubmitting(false);
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
            "Content-Type":
              "application/json",
          },

          body: JSON.stringify({
            messages:
              updatedMessages,
            conversation_id:
              conversationId,
            document_name:
              selectedDocument,
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
          Number(newConversationId)
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
        id: null,
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
          const updated = [
            ...prev,
          ];

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

              content:
                assistantText,

              sources:
                retrievedSources,

              id:
                updated[
                  updated.length - 1
                ].id ?? null,
            };
          }

          return updated;
        });
      }

      /* =================================================
         RECOVER REAL ASSISTANT MESSAGE ID
      ================================================= */

      const effectiveConversationId =
        newConversationId ||
        conversationId;

      if (effectiveConversationId) {
        try {
          const messagesResponse =
            await fetch(
              `${API_URL}/api/conversations/${effectiveConversationId}/messages`
            );

          if (messagesResponse.ok) {
            const messagesData =
              await messagesResponse.json();

            const databaseMessages =
              Array.isArray(
                messagesData
              )
                ? messagesData
                : Array.isArray(
                    messagesData.messages
                  )
                ? messagesData.messages
                : [];

            const lastAssistantMessage =
              [
                ...databaseMessages,
              ]
                .reverse()
                .find(
                  (message) =>
                    message.role ===
                    "assistant"
                );

            if (
              lastAssistantMessage &&
              lastAssistantMessage.id !==
                undefined &&
              lastAssistantMessage.id !==
                null
            ) {
              const realAssistantMessageId =
                lastAssistantMessage.id;

              setMessages((prev) => {
                const updated = [
                  ...prev,
                ];

                for (
                  let i =
                    updated.length - 1;
                  i >= 0;
                  i -= 1
                ) {
                  if (
                    updated[i].role ===
                    "assistant"
                  ) {
                    updated[i] = {
                      ...updated[i],

                      id:
                        realAssistantMessageId,
                    };

                    break;
                  }
                }

                return updated;
              });

              try {
                const feedbackResponse =
                  await fetch(
                    `${API_URL}/api/feedback/${realAssistantMessageId}`
                  );

                if (
                  feedbackResponse.ok
                ) {
                  const feedbackData =
                    await feedbackResponse.json();

                  if (
                    feedbackData.feedback
                  ) {
                    setFeedback(
                      (prev) => ({
                        ...prev,

                        [String(
                          realAssistantMessageId
                        )]:
                          feedbackData.feedback,
                      })
                    );
                  }
                }
              } catch (error) {
                console.error(
                  "Error loading new message feedback:",
                  error
                );
              }
            } else {
              console.warn(
                "Assistant message was saved but no database ID was returned."
              );
            }
          }
        } catch (error) {
          console.error(
            "Error recovering assistant message ID:",
            error
          );
        }
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
          id: null,
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
    pre({ children }) {
      return children;
    },

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

    p({ children }) {
      return (
        <p className="markdown-paragraph">
          {children}
        </p>
      );
    },

    blockquote({ children }) {
      return (
        <blockquote className="markdown-blockquote">
          {children}
        </blockquote>
      );
    },

    table({ children }) {
      return (
        <div className="markdown-table-wrapper">
          <table className="markdown-table">
            {children}
          </table>
        </div>
      );
    },

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

        <header className="header">

          <div>

            <h2>
              Garuda AI
            </h2>

            <p>
              Your intelligent AI assistant
            </p>

          </div>

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

        {/* =================================================
            CHAT
        ================================================= */}

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
                    key={
                      message.id ??
                      index
                    }
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

                            {/* =================================================
                                MESSAGE FEEDBACK
                            ================================================= */}

                            {message.content &&
                              message.id !==
                                undefined &&
                              message.id !==
                                null &&
                              !message.regenerating && (
                                <div
                                  style={{
                                    display:
                                      "flex",
                                    gap: "8px",
                                    marginTop:
                                      "12px",
                                    alignItems:
                                      "center",
                                  }}
                                >

                                  {/* THUMBS UP */}

                                  <button
                                    type="button"
                                    onClick={() =>
                                      submitPositiveFeedback(
                                        message.id
                                      )
                                    }
                                    disabled={
                                      Boolean(
                                        feedback[
                                          String(
                                            message.id
                                          )
                                        ]
                                      )
                                    }
                                    title={
                                      feedback[
                                        String(
                                          message.id
                                        )
                                      ]?.rating ===
                                      "up"
                                        ? "You liked this response"
                                        : "Good response"
                                    }
                                    style={{
                                      border:
                                        "1px solid #d1d5db",

                                      background:
                                        feedback[
                                          String(
                                            message.id
                                          )
                                        ]?.rating ===
                                        "up"
                                          ? "#e8f5e9"
                                          : "#ffffff",

                                      borderRadius:
                                        "8px",

                                      padding:
                                        "5px 9px",

                                      cursor:
                                        feedback[
                                          String(
                                            message.id
                                          )
                                        ]
                                          ? "default"
                                          : "pointer",

                                      fontSize:
                                        "15px",

                                      opacity:
                                        feedback[
                                          String(
                                            message.id
                                          )
                                        ]?.rating ===
                                        "down"
                                          ? 0.5
                                          : 1,
                                    }}
                                  >
                                    👍
                                  </button>

                                  {/* THUMBS DOWN */}

                                  <button
                                    type="button"
                                    onClick={() =>
                                      openNegativeFeedback(
                                        message.id
                                      )
                                    }
                                    disabled={
                                      Boolean(
                                        feedback[
                                          String(
                                            message.id
                                          )
                                        ]
                                      )
                                    }
                                    title={
                                      feedback[
                                        String(
                                          message.id
                                        )
                                      ]?.rating ===
                                      "down"
                                        ? "Feedback submitted"
                                        : "Suggest an improvement"
                                    }
                                    style={{
                                      border:
                                        "1px solid #d1d5db",

                                      background:
                                        feedback[
                                          String(
                                            message.id
                                          )
                                        ]?.rating ===
                                        "down"
                                          ? "#ffebee"
                                          : "#ffffff",

                                      borderRadius:
                                        "8px",

                                      padding:
                                        "5px 9px",

                                      cursor:
                                        feedback[
                                          String(
                                            message.id
                                          )
                                        ]
                                          ? "default"
                                          : "pointer",

                                      fontSize:
                                        "15px",

                                      opacity:
                                        feedback[
                                          String(
                                            message.id
                                          )
                                        ]?.rating ===
                                        "up"
                                          ? 0.5
                                          : 1,
                                    }}
                                  >
                                    👎
                                  </button>

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

        {/* =================================================
            NEGATIVE FEEDBACK MODAL
        ================================================= */}

        {feedbackModalOpen && (
          <div
            role="dialog"
            aria-modal="true"
            aria-labelledby="feedback-title"
            onClick={(event) => {
              if (
                event.target ===
                event.currentTarget
              ) {
                closeFeedbackModal();
              }
            }}
            style={{
              position: "fixed",
              inset: 0,
              background:
                "rgba(0, 0, 0, 0.45)",
              display: "flex",
              alignItems: "center",
              justifyContent: "center",
              zIndex: 1000,
              padding: "20px",
            }}
          >

            <div
              style={{
                width:
                  "min(520px, 100%)",
                background:
                  "#ffffff",
                borderRadius:
                  "14px",
                boxShadow:
                  "0 20px 50px rgba(0, 0, 0, 0.2)",
                padding:
                  "24px",
              }}
            >

              <div
                style={{
                  display:
                    "flex",
                  justifyContent:
                    "space-between",
                  alignItems:
                    "center",
                  marginBottom:
                    "12px",
                }}
              >

                <h3
                  id="feedback-title"
                  style={{
                    margin: 0,
                    fontSize:
                      "18px",
                    color:
                      "#111827",
                  }}
                >
                  How could Garuda AI improve this response?
                </h3>

                <button
                  type="button"
                  onClick={
                    closeFeedbackModal
                  }
                  disabled={
                    feedbackSubmitting
                  }
                  aria-label="Close feedback dialog"
                  style={{
                    border:
                      "none",
                    background:
                      "transparent",
                    fontSize:
                      "22px",
                    cursor:
                      feedbackSubmitting
                        ? "default"
                        : "pointer",
                    color:
                      "#6b7280",
                  }}
                >
                  ×
                </button>

              </div>

              <p
                style={{
                  marginTop: 0,
                  marginBottom:
                    "14px",
                  color:
                    "#6b7280",
                  fontSize:
                    "14px",
                  lineHeight:
                    1.5,
                }}
              >
                Tell Garuda AI what
                you would have
                preferred. This
                feedback is saved
                with the specific
                response and is used
                to regenerate it.
              </p>

              <textarea
                value={
                  feedbackInstruction
                }
                onChange={(event) =>
                  setFeedbackInstruction(
                    event.target.value
                  )
                }
                placeholder="Example: Give shorter answers and include a simple example."
                rows={5}
                autoFocus
                disabled={
                  feedbackSubmitting
                }
                style={{
                  width:
                    "100%",
                  boxSizing:
                    "border-box",
                  resize:
                    "vertical",
                  border:
                    "1px solid #d1d5db",
                  borderRadius:
                    "10px",
                  padding:
                    "12px",
                  fontFamily:
                    "inherit",
                  fontSize:
                    "14px",
                  outline:
                    "none",
                }}
              />

              <div
                style={{
                  display:
                    "flex",
                  justifyContent:
                    "flex-end",
                  gap: "10px",
                  marginTop:
                    "16px",
                }}
              >

                <button
                  type="button"
                  onClick={
                    closeFeedbackModal
                  }
                  disabled={
                    feedbackSubmitting
                  }
                  style={{
                    border:
                      "1px solid #d1d5db",
                    background:
                      "#ffffff",
                    borderRadius:
                      "8px",
                    padding:
                      "9px 16px",
                    cursor:
                      feedbackSubmitting
                        ? "default"
                        : "pointer",
                    color:
                      "#374151",
                  }}
                >
                  Cancel
                </button>

                <button
                  type="button"
                  onClick={
                    submitNegativeFeedback
                  }
                  disabled={
                    feedbackSubmitting ||
                    !feedbackInstruction.trim()
                  }
                  style={{
                    border:
                      "1px solid #111827",
                    background:
                      feedbackSubmitting ||
                      !feedbackInstruction.trim()
                        ? "#d1d5db"
                        : "#111827",
                    color:
                      "#ffffff",
                    borderRadius:
                      "8px",
                    padding:
                      "9px 16px",
                    cursor:
                      feedbackSubmitting ||
                      !feedbackInstruction.trim()
                        ? "default"
                        : "pointer",
                  }}
                >
                  {feedbackSubmitting
                    ? "Regenerating..."
                    : "Submit & Regenerate"}
                </button>

              </div>

            </div>

          </div>
        )}

      </main>

    </div>
  );
}

export default App;