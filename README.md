# 📊 GenAI SQL Assistant
🚀 A conversational AI-powered data analytics app that converts natural language into SQL queries and interactive insights.
---
## 🌐 Live Demo
👉 **Streamlit App:**
https://genai-sql-assistant-g2pwvuzvexzedzysr4vezo.streamlit.app

👉 **GitHub Repository:**
https://github.com/saikirankonda99/genai-sql-assistant

👉 **LinkedIn Profile:**
https://www.linkedin.com/in/sai-kiran-konda/

---
## 🚀 Features
* 💬 Ask questions in plain English
* 🧠 AI converts natural language → SQL queries
* 🔒 Safe execution (only SELECT queries allowed)
* 📊 Interactive dashboards (Bar, Line, Area charts)
* 📁 Upload CSV for custom data analysis
* 🧠 AI-powered explanations of query results
* ⚡ Fast performance with caching
* 🧠 Chat memory for contextual queries
---
## 🛠 Tech Stack
| Layer      | Technology          |
| ---------- | ------------------- |
| Frontend   | Streamlit           |
| Backend    | Python              |
| AI Engine  | OpenAI API          |
| Database   | SQLite (Chinook DB) |
| Data Layer | Pandas              |
---
## 🧠 How It Works
1. User enters a natural language question
2. LLM converts it into SQL using schema context
3. Query is validated using guardrails
4. SQL executes on database
5. Results are displayed with charts
6. AI explains insights in simple terms
---
## 📊 Example Queries
* List all customers
* Top 10 customers by spending
* Revenue by country
* Tracks with album and artist
---
## 📸 Screenshots
<img width="2868" height="1628" alt="Screenshot 2026-04-29 021100" src="https://github.com/user-attachments/assets/9ac15767-a0ad-413a-a444-1fd81176b98f" />
<img width="1112" height="795" alt="Screenshot 2026-04-29 021214" src="https://github.com/user-attachments/assets/2ffb4407-dd73-4bb6-96f0-fd1d27b8162b" />
<img width="2866" height="1635" alt="Screenshot 2026-04-29 021141" src="https://github.com/user-attachments/assets/ef0673d3-c0de-4d6d-a646-8d253609d46d" />
<img width="2864" height="1626" alt="image" src="https://github.com/user-attachments/assets/35d500c9-9b7b-4768-828c-bc83fa277785" />
```
---
## ⚙️ Run Locally
```bash
git clone https://github.com/saikirankonda99/genai-sql-assistant.git
cd genai-sql-assistant
pip install -r requirements.txt
streamlit run app.py
```
---
## 🔐 Setup
Create a `.streamlit/secrets.toml` file:
```toml
OPENAI_API_KEY = "your_api_key_here"
```

You can also use an environment variable instead:
```bash
export OPENAI_API_KEY="your_api_key_here"
```

---
## 🐳 Run With Docker
Build the image:
```bash
docker build -t genai-sql-assistant .
```

Run the app:
```bash
docker run --rm -p 8501:8501 -e OPENAI_API_KEY=your_api_key_here genai-sql-assistant
```

Then open:
```text
http://localhost:8501
```

The bundled SQLite database in `data/chinook.db` is copied into the image automatically.

To persist generated telemetry/history data outside the container, mount the `data` directory:
```bash
docker run --rm -p 8501:8501 -e OPENAI_API_KEY=your_api_key_here -v "$(pwd)/data:/app/data" genai-sql-assistant
```
---
## ⚠️ Security
* Only **SELECT queries** are allowed
* Prevents destructive operations (DROP, DELETE, UPDATE)
* LLM-based query correction for invalid SQL
---
## 🚧 Challenges Solved
* Handling incorrect AI-generated SQL
* Preventing unsafe queries
* Managing database paths in deployment
* Ensuring smooth UI/UX for non-technical users
---
## 🚀 Future Improvements
* Multi-database support (PostgreSQL, MySQL)
* Authentication & user sessions
* Query optimization layer
* Streaming responses (real-time UX)
* Role-based access control
---
## 👨‍💻 Author
**Sai Kiran Konda**
🔗 LinkedIn:
https://www.linkedin.com/in/sai-kiran-konda/
