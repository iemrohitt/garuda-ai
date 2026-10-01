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

    # Enable foreign key support.
    connection.execute(
        "PRAGMA foreign_keys = ON"
    )

    return connection


# =========================================================
# INITIALIZE DATABASE
# =========================================================

def initialize_database():
    """
    Create all required database tables if they do not
    already exist.
    """

    connection = get_connection()
    cursor = connection.cursor()

    # -----------------------------------------------------
    # CONVERSATIONS TABLE
    # -----------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    # -----------------------------------------------------
    # MESSAGES TABLE
    # -----------------------------------------------------

    cursor.execute(
        """
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
        """
    )

    # -----------------------------------------------------
    # MESSAGE FEEDBACK TABLE
    # -----------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS message_feedback (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            message_id INTEGER NOT NULL UNIQUE,

            rating TEXT NOT NULL,

            instruction TEXT,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,

            FOREIGN KEY (message_id)
            REFERENCES messages(id)
            ON DELETE CASCADE
        )
        """
    )

    # -----------------------------------------------------
    # USER PREFERENCES TABLE
    # -----------------------------------------------------
    #
    # This table stores response-style preferences that
    # Garuda AI learns from user feedback.
    #
    # Example:
    #
    # preference:
    # "Prefer concise explanations."
    #
    # source:
    # "feedback"
    #
    # confidence:
    # 0.7
    #
    # -----------------------------------------------------

    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS user_preferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,

            preference TEXT NOT NULL UNIQUE,

            source TEXT NOT NULL DEFAULT 'feedback',

            confidence REAL NOT NULL DEFAULT 0.5,

            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )

    connection.commit()
    connection.close()


# =========================================================
# CREATE CONVERSATION
# =========================================================

def create_conversation(
    title: str = "New Chat"
):
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
    Return all conversations ordered by newest first.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            title,
            created_at
        FROM conversations
        ORDER BY id DESC
        """
    )

    conversations = [
        dict(row)
        for row in cursor.fetchall()
    ]

    connection.close()

    return conversations


# =========================================================
# UPDATE CONVERSATION TITLE
# =========================================================

def update_conversation_title(
    conversation_id: int,
    title: str
):
    """
    Update the title of a conversation.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE conversations
        SET title = ?
        WHERE id = ?
        """,
        (
            title,
            conversation_id
        )
    )

    connection.commit()
    connection.close()


# =========================================================
# SAVE MESSAGE
# =========================================================

def save_message(
    conversation_id: int,
    role: str,
    content: str
):
    """
    Save a message to a conversation.

    Returns:
        int: ID of the newly created message.
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

    message_id = cursor.lastrowid

    connection.commit()
    connection.close()

    return message_id


# =========================================================
# GET MESSAGES
# =========================================================

def get_messages(
    conversation_id: int
):
    """
    Return all messages belonging to a conversation.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            conversation_id,
            role,
            content,
            created_at
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
# GET SINGLE MESSAGE
# =========================================================

def get_message(
    message_id: int
):
    """
    Return a single message by its ID.

    Returns:
        dict | None
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            conversation_id,
            role,
            content,
            created_at
        FROM messages
        WHERE id = ?
        """,
        (message_id,)
    )

    row = cursor.fetchone()

    connection.close()

    if row is None:
        return None

    return dict(row)


# =========================================================
# UPDATE MESSAGE
# =========================================================

def update_message(
    message_id: int,
    content: str
):
    """
    Update the content of an existing message.

    This is used when Garuda AI regenerates an assistant
    response after receiving negative feedback.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        UPDATE messages
        SET content = ?
        WHERE id = ?
        """,
        (
            content,
            message_id
        )
    )

    connection.commit()
    connection.close()


# =========================================================
# DELETE CONVERSATION
# =========================================================

def delete_conversation(
    conversation_id: int
):
    """
    Delete a conversation and all of its messages.

    Message feedback is also deleted automatically because
    message_feedback has ON DELETE CASCADE.
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
# SAVE MESSAGE FEEDBACK
# =========================================================

def save_feedback(
    message_id: int,
    rating: str,
    instruction: str | None = None
):
    """
    Save or update feedback for an assistant message.

    rating:
        "up"   -> positive feedback
        "down" -> negative feedback

    instruction:
        Optional instruction supplied by the user when
        giving negative feedback.
    """

    if rating not in (
        "up",
        "down"
    ):
        raise ValueError(
            "Feedback rating must be 'up' or 'down'."
        )

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        INSERT INTO message_feedback (
            message_id,
            rating,
            instruction
        )
        VALUES (?, ?, ?)

        ON CONFLICT(message_id)
        DO UPDATE SET
            rating = excluded.rating,
            instruction = excluded.instruction,
            created_at = CURRENT_TIMESTAMP
        """,
        (
            message_id,
            rating,
            instruction
        )
    )

    connection.commit()
    connection.close()


# =========================================================
# GET FEEDBACK FOR MESSAGE
# =========================================================

def get_feedback_for_message(
    message_id: int
):
    """
    Return feedback associated with a message.

    Returns:
        dict | None
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            message_id,
            rating,
            instruction,
            created_at
        FROM message_feedback
        WHERE message_id = ?
        """,
        (message_id,)
    )

    row = cursor.fetchone()

    connection.close()

    if row is None:
        return None

    return dict(row)


# =========================================================
# DELETE FEEDBACK FOR MESSAGE
# =========================================================

def delete_feedback_for_message(
    message_id: int
):
    """
    Delete feedback associated with a message.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM message_feedback
        WHERE message_id = ?
        """,
        (message_id,)
    )

    connection.commit()
    connection.close()


# =========================================================
# SAVE USER PREFERENCE
# =========================================================

def save_user_preference(
    preference: str,
    source: str = "feedback",
    confidence: float = 0.5
):
    """
    Save a learned user preference.

    If the preference already exists, its confidence
    is increased instead of creating a duplicate.

    Example:

        save_user_preference(
            "Prefer concise explanations."
        )
    """

    preference = preference.strip()

    if not preference:
        return

    # Keep confidence between 0 and 1.
    confidence = max(
        0.0,
        min(1.0, float(confidence))
    )

    connection = get_connection()
    cursor = connection.cursor()

    # -----------------------------------------------------
    # Check whether this preference already exists.
    # -----------------------------------------------------

    cursor.execute(
        """
        SELECT
            id,
            confidence
        FROM user_preferences
        WHERE preference = ?
        """,
        (preference,)
    )

    existing = cursor.fetchone()

    if existing:

        # Increase confidence when the same preference
        # is learned again.
        new_confidence = min(
            1.0,
            float(existing["confidence"]) + 0.1
        )

        cursor.execute(
            """
            UPDATE user_preferences
            SET
                confidence = ?,
                source = ?
            WHERE id = ?
            """,
            (
                new_confidence,
                source,
                existing["id"]
            )
        )

    else:

        cursor.execute(
            """
            INSERT INTO user_preferences (
                preference,
                source,
                confidence
            )
            VALUES (?, ?, ?)
            """,
            (
                preference,
                source,
                confidence
            )
        )

    connection.commit()
    connection.close()


# =========================================================
# GET USER PREFERENCES
# =========================================================

def get_user_preferences():
    """
    Return all stored user preferences.

    Preferences are ordered by confidence so that the
    strongest preferences can be used first.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        SELECT
            id,
            preference,
            source,
            confidence,
            created_at
        FROM user_preferences
        ORDER BY confidence DESC, id DESC
        """
    )

    preferences = [
        dict(row)
        for row in cursor.fetchall()
    ]

    connection.close()

    return preferences


# =========================================================
# DELETE USER PREFERENCE
# =========================================================

def delete_user_preference(
    preference_id: int
):
    """
    Delete a stored user preference.
    """

    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute(
        """
        DELETE FROM user_preferences
        WHERE id = ?
        """,
        (preference_id,)
    )

    connection.commit()
    connection.close()


# =========================================================
# INITIALIZE DATABASE WHEN MODULE LOADS
# =========================================================

initialize_database()