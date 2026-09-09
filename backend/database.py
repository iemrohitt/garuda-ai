import sqlite3


# =========================================================
# DATABASE CONFIGURATION
# =========================================================

DATABASE_NAME = "garuda.db"


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_connection():
    """
    Create and return a connection to the SQLite database.
    """

    connection = sqlite3.connect(
        DATABASE_NAME
    )

    connection.row_factory = sqlite3.Row

    return connection


# =========================================================
# CREATE TABLES
# =========================================================

def create_tables():
    """
    Create database tables if they do not already exist.
    """

    connection = get_connection()

    cursor = connection.cursor()

    # -----------------------------------------------------
    # Conversations table
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # -----------------------------------------------------
    # Messages table
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            role TEXT NOT NULL,
            content TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (conversation_id)
            REFERENCES conversations(id)
            ON DELETE CASCADE
        )
    """)

    connection.commit()

    connection.close()


# =========================================================
# CREATE CONVERSATION
# =========================================================

def create_conversation(title: str):
    """
    Create a new conversation and return its ID.
    """

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO conversations (title)
        VALUES (?)
        """,
        (title,)
    )

    conversation_id = cursor.lastrowid

    connection.commit()

    connection.close()

    return conversation_id


# =========================================================
# GET ALL CONVERSATIONS
# =========================================================

def get_conversations():
    """
    Return all conversations ordered by
    most recently updated.
    """

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id, title, created_at, updated_at
        FROM conversations
        ORDER BY updated_at DESC
        """
    )

    conversations = [
        dict(row)
        for row in cursor.fetchall()
    ]

    connection.close()

    return conversations


# =========================================================
# GET CONVERSATION MESSAGES
# =========================================================

def get_messages(conversation_id: int):
    """
    Return all messages belonging to a conversation.
    """

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT id, conversation_id, role, content, created_at
        FROM messages
        WHERE conversation_id = ?
        ORDER BY id ASC
        """,
        (conversation_id,)
    )

    messages = [
        dict(row)
        for row in cursor.fetchall()
    ]

    connection.close()

    return messages


# =========================================================
# SAVE MESSAGE
# =========================================================

def save_message(
    conversation_id: int,
    role: str,
    content: str
):
    """
    Save a message inside a conversation.
    """

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO messages (
            conversation_id,
            role,
            content
        )
        VALUES (?, ?, ?)
        """,
        (
            conversation_id,
            role,
            content
        )
    )

    # -----------------------------------------------------
    # Update conversation timestamp
    # -----------------------------------------------------

    cursor.execute(
        """
        UPDATE conversations
        SET updated_at = CURRENT_TIMESTAMP
        WHERE id = ?
        """,
        (conversation_id,)
    )

    connection.commit()

    connection.close()


# =========================================================
# DELETE CONVERSATION
# =========================================================

def delete_conversation(conversation_id: int):
    """
    Delete a conversation and its messages.
    """

    connection = get_connection()

    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM conversations
        WHERE id = ?
        """,
        (conversation_id,)
    )

    connection.commit()

    connection.close()


# =========================================================
# INITIALIZE DATABASE
# =========================================================

create_tables()