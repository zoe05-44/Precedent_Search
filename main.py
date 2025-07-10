import requests
import sys 
import time
import re
import json
import xml.etree.ElementTree as ET
from lxml import etree
import os
import google.generativeai as genai
from db import conn
from sentence_transformers import SentenceTransformer

model = SentenceTransformer('all-MiniLM-L6-v2')
max_tries = 3

def extract_keywords(text):
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY")
    for attempt in range(max_tries):
        genai.configure(api_key=GEMINI_API_KEY)

        model = genai.GenerativeModel("gemini-1.5-flash")

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
        try:
            response = model.generate_content(prompt)
            raw_output = response.text.strip()

            cleaned = raw_output
            cleaned = re.sub(r"^```(?:python)?\n", "", cleaned)
            cleaned = re.sub(r"```$", "", cleaned)
            cleaned = re.sub(r"^\s*(\w+_)?keywords\s*=\s*", "", cleaned)

            last_brace_index = cleaned.rfind("}")
            if last_brace_index == -1:
                print("No closing brace found in Gemini output.")
                return None
            cleaned = cleaned[:last_brace_index+1]

            print("Cleaned output from Gemini:")
            
            keyword_dict = json.loads(cleaned) 
            keyword_json = json.dumps(keyword_dict)  # Convert to JSON string
            return keyword_json
         
        except json.JSONDecodeError as e:

            print(f"JSON parsing error on attempt {attempt+1}: {e}")
            time.sleep(30)

        except Exception as e:
            # Catch any Gemini API or network error
            if "quota" in str(e).lower():
                print(f"Gemini API quota limit reached. Exiting program: {e}")
                sys.exit()
            else:
                print(f"Unexpected error on attempt {attempt + 1}: {e}")
                time.sleep(30)
        
    print("Failed to parse keywords after multiple attempts.")
    return None  

def check_database(conn, case_id_value):
    cur = conn.cursor()
    query = "SELECT EXISTS(SELECT 1 FROM cases WHERE case_id = %s);"
    cur.execute(query,(case_id_value,))
    exists = cur.fetchone()[0]
    cur.close()
    return exists

def produce_summary(text):
    API = os.environ.get("API")

    genai.configure(api_key=API)
    
    gen_model = genai.GenerativeModel("gemini-1.5-flash")
    
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
    for attempt in range(max_tries):

        try: 
            response = gen_model.generate_content(prompt)
            summary = response.text.strip()
            return summary
        except Exception as e: 
            if "quota" in str(e).lower():
                print(f"Gemini API quota limit reached. Stopping script: {e}")
                sys.exit()
            else:
                print(f"Error on attempt {attempt + 1}: {e}")
                if attempt < max_tries - 1:
                    time.sleep(30)
                else: 
                    print("Could not generate summary")
                    return None

def insert_database(conn, id, name, date, court, url, keywords,embeddings,summary):
    cur = conn.cursor()
    query = """
    INSERT INTO cases(case_id, case_name, date, court, url, keywords, keyword_vectors, summary) 
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (case_id) DO NOTHING;
    """
    cur.execute(query, (id, name, date, court, url, keywords, embeddings, summary))
    conn.commit()
    cur.close()
    print("case inserted")

def generate_embeddings(text):
    return model.encode(text).tolist()  

def fetch_page(max_pages=40, delay = 120):
    base_url = "https://caselaw.nationalarchives.gov.uk/atom.xml"
    current_url = base_url
    page = 14
    while current_url and page < max_pages:
        print(f"\nFetching Page {page + 1}: {current_url}")
        response = requests.get(current_url)
        print("Status Code:", response.status_code) 

        if response.status_code != 200:
            print(f"Failed to fetch page: {response.status_code}")
            break
        root = ET.fromstring(response.text)
        entries = root.findall('atom:entry', namespaces)
        yield from entries #pass entries one by one

        next_link = root.find(".//atom:link[@rel='next']", namespaces)
        current_url = next_link.attrib['href'] if next_link is not None else None

        page += 1
        if page < max_pages and current_url:
            print(f"Waiting {delay // 60} minutes before next page...\n")
        time.sleep(delay)

def log_missing_case(case_id):
    try:
        with open("missing_cases", "r") as file:
            missing_case = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        missing_case = []
    missing_case.append(case_id)
    with open("missing_cases", "w") as f:
        json.dump(missing_case, f)

namespaces = {
        'atom': 'http://www.w3.org/2005/Atom',
        'tna': 'https://caselaw.nationalarchives.gov.uk',
        'akn': 'http://docs.oasis-open.org/legaldocml/ns/akn/3.0'
        }

for entry in fetch_page(max_pages= 20, delay=200):

        output = []

        tna_uri_elem = entry.find('tna:uri', namespaces)
        if tna_uri_elem is not None and tna_uri_elem.text:
            case_id = tna_uri_elem.text.strip()
        else:
            case_id = entry.find('atom:id', namespaces).text.strip()

        if check_database(conn, case_id):
            print(f"Skipping {case_id}, already exists in DB.")
            continue
        else:

            title = entry.find('atom:title', namespaces).text.strip()
            date = entry.find('atom:published', namespaces).text.strip()
            court = entry.find('atom:author/atom:name', namespaces).text.strip() 
            
            xml_link = None
            for link in entry.findall('atom:link', namespaces):
                if 'akn+xml' in link.attrib.get('type', ''):
                    xml_link = link.attrib['href']
                    break

            if not xml_link:
                print("No XML link found. Skipping.")
                log_missing_case(case_id)
                continue

            print(f"Fetching XML from: {xml_link}")
            case_text = requests.get(xml_link)
            print(f"Status: {case_text.status_code}")

            judgement_root = etree.fromstring(case_text.content) 

                #Get Case Judgement
            outcome = judgement_root.xpath(
                "//*[local-name()='decision']//*[local-name()='p']/text()"
            )
            output += outcome 

            paragraphs = []

            for para in judgement_root.xpath("//*[local-name()='paragraph']"):
                    number_nodes = para.xpath(".//*[local-name()='num']")
                    number = number_nodes[0] if number_nodes else None

                    content_nodes = para.xpath(".//*[local-name()='content']")
                    content = content_nodes[0] if content_nodes else None

                    text_elements = content.xpath(".//*[local-name()='p']//text()") if content is not None else []
                    text = ' '.join(text_elements).strip()

                    if text:
                        para_num = number.text.strip() if number is not None else ''
                        paragraphs.append((para_num, text))

            for i, (num, text) in enumerate(paragraphs[:10], 1):
                    output.append(f"{num}. {text}")

            if not output:
                print(f"[SKIP] No judgment text found for case {case_id}")
                log_missing_case(case_id)
                continue

            summary = produce_summary(output)

            time.sleep(30)

            if summary is not None: 
                keywords = extract_keywords(output)
                try: 
                    embedded_keywords = generate_embeddings(keywords) 
                    insert_database(conn, case_id, title, date, court, xml_link, keywords, embedded_keywords, summary)
                    time.sleep(40)
                except Exception as e: 
                    print(f"case {case_id} failed during keyword embedding or DB insertion: {e}")
                    log_missing_case(case_id)
                    continue     
                          
            else: 
                print(f"[FAIL] No summary generated for case {case_id}. Not inserted")
                log_missing_case(case_id)
                continue     