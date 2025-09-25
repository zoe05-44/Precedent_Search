import streamlit as st
import uuid
import numpy as np 
import utils.genai as llm
import google.generativeai as genai
import db.check as db
from db.fill_query import log_search_transaction, update_feedback_score

nlp = llm.load_nlp()
gemini = llm.gemini_model()
embedding_model = llm.load_model()

#Page Configuration
st.set_page_config(page_title="Precedence Search Tool",
                page_icon="⚖️",
                layout="centered")

#initialise session id 
if "session_id" not in st.session_state:
     st.session_state.session_id = str(uuid.uuid4())
if 'results' not in st.session_state:
    st.session_state.results = []

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
            keywords = (llm.extract_user_keywords(redacted_input, gemini) or redacted_input).strip()
            st.session_state.keywords = keywords  # Save to session_state
            #embed input
            embedding = llm.generate_embeddings(keywords, embedding_model)
            embedding = embedding / np.linalg.norm(embedding)
            embedded_keywords = ','.join(map(str, embedding.tolist()))

            #Fetch the top matching cases
            results = db.fetch_cases(embedded_keywords, selected_court)
            query_id = str(uuid.uuid4())

            #Store Query info
            query_info = {
                "session_id": st.session_state.session_id,
                "query_text": user_input,
                "extracted_keywords": {"keywords": keywords},
                "query_embedding": embedding.tolist(),
                "query_id": query_id,
            }
            st.session_state.query_info = query_info  # Save in session for later use

            #Store results in session state
            st.session_state.results = [
                {
                    "case_id": res["case_id"],
                    "name": res["case_name"],
                    "court": res["court"],
                    "url": res["url"],
                    "summary": res["summary"],
                    "similarity_score": res["similarity_score"],
                    "query_id": query_id,
                    "rank": i + 1,
                    "feedback_score": None,
                    "query_result_id": str(uuid.uuid4())
                }
                for i, res in enumerate(results)
            ]

            #log the search data into database
            log_search_transaction(query_info, st.session_state.results)

            
#Display Keywords
if "keywords" in st.session_state:
    st.subheader("Extracted Keywords")
    st.markdown(f"`{st.session_state.keywords}`")
#Display Results
if "results" in st.session_state and st.session_state.results:
    st.subheader("Top Matching Cases")
    for result in st.session_state.results:
        with st.container(border=True): 
            score = float(result['similarity_score'])
            confidence = max(0, (1 - score) * 100) # Convert similarity to % confidence

            #Displaay Case info
            st.markdown(f"#### {result['name']} ({result['court']})")
            st.markdown(f"**Similarity:** {confidence:.2f}% | [View Case]({result['url']})")
            st.markdown(f"**Summary:** {result['summary']}")

            #Display for user feedback on cases
            st.write("**Rate this result's relevance:**")
            cols = st.columns(5)
            for i in range(5):
                score_value = i + 1
                with cols[i]:
                    #Button has a unique key tied to the query_id
                    if st.button(f"{score_value} ⭐", key=f"score_{score_value}_{result['query_result_id']}"):
                        #Update Database 
                        success = update_feedback_score(
                            query_result_id=result['query_result_id'],
                            feedback_score=score_value
                        )
                        if success:
                            st.toast(f"Thanks! You rated '{result['name']}' as {score_value} ⭐.")
                        else:
                            st.error("Could not save feedback.")
              