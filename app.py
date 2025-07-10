import streamlit as st
import numpy as np 
import spacy
from sentence_transformers import SentenceTransformer
import google.generativeai as genai
import os
from db import conn 


@st.cache_resource
def load_nlp():
    return spacy.load("en_core_web_sm")
@st.cache_resource
def load_model():
    return SentenceTransformer('all-MiniLM-L6-v2')

nlp = load_nlp()
model = load_model()

def filter_input(text):
    doc = nlp(text)
    filtered = text
    for ent in reversed(list(doc.ents)):
        if ent.label_ == "PERSON":
            filtered = filtered[:ent.start_char] + "[NAME]" + filtered[ent.end_char:]
        elif ent.label_ == "GPE": #location
                filtered = filtered[:ent.start_char] + "[LOCATION]" + filtered[ent.end_char:]
        elif ent.label_ == "DATE":
                filtered = filtered[:ent.start_char] + "[DATE]" + filtered[ent.end_char:]
    return filtered

def extract_keywords(text):
    API = os.environ.get("API")

    genai.configure(api_key=API)
    google_model = genai.GenerativeModel("gemini-1.5-flash")

    prompt = f"""
  Read the provided "Legal Text" carefully.
  Crucially, ignore any placeholders or redacted information, specifically text enclosed in square brackets like [NAME] or [DATE]. Do not include these placeholders or the common words surrounding them if they are not relevant to the categories below.
  Extract information into the following three distinct categories. For each category, list the relevant items as a bulleted list. If a category has no relevant information, state "None".
  1) Legal Concepts: These are fundamental principles, doctrines, acts, sections, or established legal theories. Focus on the core legal ideas being discussed.
  2) Notice or Penalty Types and Actions: These refer to any mentioned legal notices, types of penalties, or specific actions taken or required by legal processes (e.g., rescission, breach, appeal, judgment, assessment of damages).
  3) Factual Circumstances and Arguments: These are the specific events, allegations, contentions, and the reasoning or points made by the parties involved in the dispute. Focus on the 'what happened' and 'what was argued.

  Legal Text: 
  {text}
  """
    try:
        response = google_model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f"Error: {e}"

def get_courts():
    cur = conn.cursor()
    cur.execute("SELECT DISTINCT court FROM cases ORDER BY court;")
    court_types = [row[0] for row in cur.fetchall()]
    cur.close()
    return court_types

st.set_page_config(page_title="Precedence Search Tool", page_icon="⚖️", layout="centered")

st.markdown("""
    <style>
        html, body, [class*="css"]  {
            background-color: #0e1117;
            color: white;
        }
        .stTextInput input, .stSelectbox div[data-baseweb="select"] {
            background-color: #1c1f26 !important;
            color: white !important;
            border-radius: 10px;
            padding: 10px;
        }
        .stButton button {
            background-color: #2563eb;
            color: white;
            padding: 0.75rem 1.5rem;
            font-weight: 600;
            border-radius: 10px;
            border: none;
            transition: background-color 0.3s ease;
        }
        .stButton button:hover {
            background-color: #1e40af;
        }
    </style>
""", unsafe_allow_html=True)


st.markdown("<h1 style='text-align: center; font-size: 2.5em;'>Precedence Search Tool</h1>", unsafe_allow_html=True)
user_input = st.text_input("Describe your case", placeholder="E.g., fraudulent misrepresentation under contract law...")
court_options = ["Any"] + get_courts()
selected_court = st.selectbox("Filter by Court", court_options) 

if(st.button("Find Precedence")):
    if not user_input.strip():
        st.warning("Please enter a case description.")
    else: 
        with st.spinner("Finding relevant precedent cases..."):
            redacted_input = filter_input(user_input)
            print(redacted_input)
            keywords = extract_keywords(redacted_input).strip()
            #embed input
            embedding = model.encode(keywords)
            embedding = embedding / np.linalg.norm(embedding)
            embedding_str = ','.join(map(str, embedding.tolist()))
            cur = conn.cursor()
            
            query = """
        SELECT case_name, court, url, keyword_vectors, summary <=> %s::vector AS distance
        FROM cases 
        WHERE (%s = 'Any' OR court = %s)
        ORDER BY distance ASC
        LIMIT 10;
    """
            cur.execute(query, (f"[{embedding_str}]", selected_court, selected_court))
            results = cur.fetchall()
            cur.close()

            st.subheader("Extracted Keywords")
            st.markdown(f"`{keywords}`")

            st.subheader("Top Matching Cases")
            for name, court, url, summary, score in results:
                if 0 <= score <= 2:
                    confidence = (1 - score / 2)  
                else:
                    confidence = 0  

                st.markdown(f"**{name}** ({court})  \n[View Case]({url})")
                st.markdown(f"**Confidence:** `{round(confidence * 100, 1)}%`  \n**Summary:** {summary}")               