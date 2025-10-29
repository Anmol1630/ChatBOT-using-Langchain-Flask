from flask import Flask, render_template, request, redirect, url_for
from langchain_google_genai import ChatGoogleGenerativeAI
from dotenv import load_dotenv
import os, sqlite3, datetime

app = Flask(__name__)

# Load environment variables
load_dotenv()

# Initialize Gemini model
llm = ChatGoogleGenerativeAI(
    model='gemini-2.5-flash',
    google_api_key=os.getenv('GOOGLE_API_KEY')
)

DB_FILE = "chatbot.db"

# ---- Database Setup ----
def init_db():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute('''CREATE TABLE IF NOT EXISTS chats (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    title TEXT,
                    created_at TEXT
                )''')
    c.execute('''CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    chat_id INTEGER,
                    sender TEXT,
                    text TEXT,
                    created_at TEXT,
                    FOREIGN KEY(chat_id) REFERENCES chats(id)
                )''')
    conn.commit()
    conn.close()

init_db()

# ---- Helper Functions ----
def get_all_chats():
    """Fetch all chats ordered by creation time"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("SELECT id, title FROM chats ORDER BY created_at DESC")
    chats = c.fetchall()
    conn.close()
    return chats

def delete_chat_from_db(chat_id):
    """Delete a chat and all its messages"""
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    c.execute("DELETE FROM messages WHERE chat_id=?", (chat_id,))
    c.execute("DELETE FROM chats WHERE id=?", (chat_id,))
    conn.commit()
    conn.close()

def get_ai_response(user_message):
    """Get response from Gemini AI with better formatting"""
    try:
        prompt = f"""
        You are a friendly, polite, and highly intelligent AI assistant.
        Keep responses short, conversational, and well-formatted.
        Use proper spacing, line breaks, and formatting where appropriate.
        Make your responses engaging and helpful.
        
        User: {user_message}
        """
        ai_response = llm.invoke(prompt)
        return ai_response.content.strip()
    except Exception as e:
        return f"Sorry, I encountered an error: {str(e)}"

# ---- Routes ----
@app.route("/")
def home():
    chats = get_all_chats()
    if chats:
        return redirect(url_for("view_chat", chat_id=chats[0][0]))
    else:
        return redirect(url_for("new_chat"))

@app.route("/chat/<int:chat_id>")
def view_chat(chat_id):
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    
    # Verify chat exists
    c.execute("SELECT id FROM chats WHERE id=?", (chat_id,))
    if not c.fetchone():
        conn.close()
        return redirect(url_for("home"))
    
    # Get chat history
    c.execute("SELECT sender, text FROM messages WHERE chat_id=? ORDER BY created_at ASC", (chat_id,))
    chat_history = [{"sender": row[0], "text": row[1]} for row in c.fetchall()]
    conn.close()

    all_chats = get_all_chats()
    return render_template("index.html", chats=all_chats, chat_history=chat_history, current_chat=chat_id)

@app.route("/new_chat")
def new_chat():
    conn = sqlite3.connect(DB_FILE)
    c = conn.cursor()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # Create a new chat with a beautiful title
    default_title = f"Chat • {datetime.datetime.now().strftime('%b %d, %I:%M %p')}"
    c.execute("INSERT INTO chats (title, created_at) VALUES (?, ?)", (default_title, now))
    chat_id = c.lastrowid
    
    # Add greeting message
    greeting = "Hey there! 👋 I'm your AI assistant. Ask me anything and I'll do my best to help! 🚀"
    c.execute("INSERT INTO messages (chat_id, sender, text, created_at) VALUES (?, ?, ?, ?)",
              (chat_id, "ai", greeting, now))
    conn.commit()
    conn.close()
    
    return redirect(url_for("view_chat", chat_id=chat_id))

@app.route("/send/<int:chat_id>", methods=["POST"])
def send_message(chat_id):
    user_message = request.form.get("message", "").strip()
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    if not user_message:
        return redirect(url_for("view_chat", chat_id=chat_id))

    # Save user message
    with sqlite3.connect(DB_FILE, timeout=10, check_same_thread=False) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO messages (chat_id, sender, text, created_at) VALUES (?, ?, ?, ?)",
                  (chat_id, "user", user_message, now))
        conn.commit()

    # Get AI response
    ai_reply = get_ai_response(user_message)

    # Save AI response
    with sqlite3.connect(DB_FILE, timeout=10, check_same_thread=False) as conn:
        c = conn.cursor()
        c.execute("INSERT INTO messages (chat_id, sender, text, created_at) VALUES (?, ?, ?, ?)",
                  (chat_id, "ai", ai_reply, now))
        
        # Update chat title based on first user message
        c.execute("SELECT title FROM chats WHERE id=?", (chat_id,))
        current_title = c.fetchone()[0]
        if current_title.startswith("Chat"):
            new_title = user_message[:35] + ("..." if len(user_message) > 35 else "")
            c.execute("UPDATE chats SET title=? WHERE id=?", (new_title, chat_id))
        
        conn.commit()

    return redirect(url_for("view_chat", chat_id=chat_id))

@app.route("/delete/<int:chat_id>", methods=["POST"])
def delete_chat(chat_id):
    """Delete a chat and redirect to home or first remaining chat"""
    delete_chat_from_db(chat_id)
    chats = get_all_chats()
    
    if chats:
        return redirect(url_for("view_chat", chat_id=chats[0][0]))
    else:
        return redirect(url_for("new_chat"))


if __name__ == "__main__":
    app.run(debug=True)