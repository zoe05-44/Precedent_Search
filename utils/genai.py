import google.generativeai as genai
import spacy
import os
import re
import json 
import sys
import time
from sentence_transformers import SentenceTransformer
import logging 

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

max_tries = 3

def gemini_model1():
    """
    Fetch API and load model
    """
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")

    genai.configure(api_key=GEMINI_API_KEY)
    gen_model = genai.GenerativeModel("gemini-1.5-flash")
    return gen_model

def gemini_model():
    """
    Fetch API and load model
    """
    API = os.environ.get("API")

    genai.configure(api_key=API)    
    gen_model = genai.GenerativeModel("gemini-1.5-flash")
    return gen_model

def load_nlp():
    """
    Load and return NLP model.
    """
    nlp_model = spacy.load("en_core_web_sm")
    return nlp_model

def load_model():
    """
    Load and return embedding model.
    """
    embedding_model = SentenceTransformer('all-MiniLM-L6-v2', device='cpu')
    return embedding_model

def generate_embeddings(text, model):
    """
    Generate sentence embeddings for the given text.
    """
    return model.encode(text).tolist()

def produce_summary(text, model):
    """
    Use Gemini API to produce summary of each case 
    """
    
    prompt = f"""
    You are an expert legal assistant specialized in summarizing legal case documents. Your task is to provide a concise summary of the provided "Legal Case" text.

    Instructions:
    1.  Read the entire "Legal Case" text carefully.
    2.  Summarize the case in *exactly three sentences.
    3.  Your summary must include:
        * The main parties or subjects involved in the case (referencing "appellant," "respondent," etc., even if specific names are redacted).
        * The core legal dispute or main issue at hand.
        * The court's primary decision, ruling, or expected judgment as stated in the text.
    4.  Ensure the summary flows naturally and is easy to understand.    

    Legal case: {text}
    """

    #Try thrice to pass prompt to API
    for attempt in range(max_tries):

        try: 
            #produce response from gemini
            response = model.generate_content(prompt)
            summary = response.text.strip()
            return summary
        
        except Exception as e: 
            if "quota" in str(e).lower():
                #exit program if Gemini API daily quota reached
                logging.info(f"Gemini API quota limit reached. Stopping script: {e}")
                sys.exit()
            else:
                logging.error(f"Error on attempt {attempt + 1}: {e}")
                if attempt < max_tries - 1:
                    time.sleep(30)
                else: 
                    logging.error("Could not generate summary")
                    return None

def extract_keywords(text, model):
    """
    Use Gemini API to generate keywords and tags from case content
    """
        
    prompt = f"""
        You are a legal keyword extraction assistant. 

        Read the following UK legal case excerpt and extract keywords or short phrases into **three categories**:

        1) Legal Concepts: These are fundamental principles, doctrines, acts, sections, or established legal theories. Focus on the core legal ideas being discussed.
        2) Notice or Penalty Types and Actions: These refer to any mentioned legal notices, types of penalties, or specific actions taken or required by legal processes (e.g., rescission, breach, appeal, judgment, assessment of damages).
        3) Factual Circumstances and Arguments: These are the specific events, allegations, contentions, and the reasoning or points made by the parties involved in the dispute. Focus on the 'what happened' and 'what was argued.'

        Format the result as a python dictionary with keys being category names and values being lists of keywords.

        Case Excerpt:
        {text}
        """
    # Try thrice to generate keywords
    for attempt in range(max_tries):

        try:
            response = model.generate_content(prompt)
            raw_output = response.text.strip()

            cleaned = raw_output
            #Clean Gemini output to remove beginning triple backticks and the word python 
            cleaned = re.sub(r"^```(?:python)?\n", "", cleaned)
            #remove ending triple backticks
            cleaned = re.sub(r"```$", "", cleaned)
            #remove begging tags such as  keywords = {}
            cleaned = re.sub(r"^\s*(\w+_)?keywords\s*=\s*", "", cleaned)

            # Find last closing brace '}' to trim extra text
            last_brace_index = cleaned.rfind("}")
            if last_brace_index == -1:
                logging.error("No closing brace found in Gemini output.")
                return None
            #exclude reponse after last closing '}'
            cleaned = cleaned[:last_brace_index+1]

            logging.info("Cleaned output from Gemini:")
            
            keyword_dict = json.loads(cleaned) 
            keyword_json = json.dumps(keyword_dict)  # Convert to JSON string
            return keyword_json
         
        except json.JSONDecodeError as e:

            logging.error(f"JSON parsing error on attempt {attempt+1}: {e}")
            time.sleep(30)

        except Exception as e:
            # Catch any Gemini API or network error
            if "quota" in str(e).lower():
                logging.info(f"Gemini API quota limit reached. Exiting program: {e}")
                sys.exit()
            else:
                logging.error(f"Unexpected error on attempt {attempt + 1}: {e}")
                time.sleep(30)
        
    logging.error("Failed to parse keywords after multiple attempts.")
    return None

def extract_user_keywords(text, model):
    """
    extract keywords from the users' case description
    """

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
        response = model.generate_content(prompt)
        return response.text
    except Exception as e:
        logging.error(f"Error: {e}")

def filter_input(text, model):
    """
    Redact user input to remove personal information
    """
    doc = model(text)
    filtered = text
    for ent in reversed(list(doc.ents)):
        if ent.label_ == "PERSON":
            filtered = filtered[:ent.start_char] + "[NAME]" + filtered[ent.end_char:]
        elif ent.label_ == "GPE": #location
                filtered = filtered[:ent.start_char] + "[LOCATION]" + filtered[ent.end_char:]
        elif ent.label_ == "DATE":
                filtered = filtered[:ent.start_char] + "[DATE]" + filtered[ent.end_char:]
    return filtered
