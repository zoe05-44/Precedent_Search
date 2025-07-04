**Precedence_Search** 
A legal precedent search tool that allows users to find relevant UK legal cases based on natural language input. It uses semantic search with sentence embeddings to retrieve similar cases and present summaries.

---

## Features

- **Semantic Search**: Uses `sentence-transformers` and cosine similarity to match user input to legal case summaries.
- **Streamlit UI**: Interactive front-end that lets users enter search queries in plain English.
- **Vector Database**: Stores case embeddings for fast and accurate similarity searches.
- **Case Metadata**: Includes case title, court, date, and summary.
- **.env Support**: Uses environment variables to protect API keys and database credentials.

---

## UI Preview

*UI is built in Streamlit but not yet deployed. Sample layout includes:*
- Text input for legal query
- Top similar cases displayed with titles and summaries
- Option to view full case metadata

---

## Setup Instructions

1. **Clone the repository**  
   ```bash
   git clone https://github.com/zoe05-44/Precedence_Search.git
   cd Precedence_Search

2. **Install Dependancies**
    pip install -r requirements.txt

3. **Set up environment variables**
    Create a .env file with your keys:
        OPENAI_API_KEY=your_key_here
        DB_URL=your_postgres_connection_string

4. **Run the app locally**
    streamlit run main.py


**Technologies Used**
- Python 3.11
- Streamlit
- Sentence Transformers
- spaCy (en_core_web_sm)
- Google Generative AI
- Supabase (PostgreSQL backend)
- LXML, Requests, dotenv

🛡️ Disclaimer
This tool is for educational and prototyping purposes only. It does not constitute legal advice and should not be relied upon for real-world legal decision-making

