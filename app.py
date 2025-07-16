import streamlit as st
import numpy as np 
import utils.genai as llm
import google.generativeai as genai
import google.generativeai as genai
import db.check as db

nlp = llm.load_nlp()
gemini = llm.gemini_model()
embedding_model = llm.load_model()

#Page Configuration
st.set_page_config(page_title="Precedence Search Tool",
                page_icon="⚖️",
                layout="centered")

#Style
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

#Title
st.markdown("<h1 style='text-align: center; font-size: 2.5em;'>Precedence Search Tool</h1>",
            unsafe_allow_html=True)
#User input
user_input = st.text_input("Describe your case",
                            placeholder="E.g., fraudulent misrepresentation under contract law...")
#Court Filter
court_options = ["Any"] + db.get_courts()
selected_court = st.selectbox("Filter by Court", court_options) 

#Search Logic
if(st.button("Find Precedence")):
    if not user_input.strip():
        st.warning("Please enter a case description.")
    else: 
        with st.spinner("Finding relevant precedent cases..."):
            #Filter user input
            redacted_input = llm.filter_input(user_input, nlp)
            #Extract keywords
            keywords = llm.extract_user_keywords(redacted_input, gemini).strip()
            #embed input
            embedding = llm.generate_embeddings(keywords, embedding_model)
            embedding = embedding / np.linalg.norm(embedding)
            embedded_keywords = ','.join(map(str, embedding.tolist()))

            #Fetch the top matching cases
            results = db.fetch_cases(embedded_keywords, selected_court)

            #Display Results
            st.subheader("Extracted Keywords")
            st.markdown(f"`{keywords}`")

            st.subheader("Top Matching Cases")
            #Convert cosine distance to confidence %
            for name, court, url, summary, score in results:
                if 0 <= score <= 2:
                    confidence = (1 - score / 2)  
                else:
                    confidence = 0  

                st.markdown(f"**{name}** ({court})  \n[View Case]({url})")
                st.markdown(f"**Confidence:** `{round(confidence * 100, 1)}%`  \n**Summary:** {summary}")                