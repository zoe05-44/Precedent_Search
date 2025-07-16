import db.check as db
import time
import json
from db.connection import conn
import utils.genai as llm
import utils.api as source
import logging 

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
gemini = llm.gemini_model()
gemini1 = llm.gemini_model1()

def log_missing_case(case_id):
    """
    Insert cases that couldn't be added to the database to a file for record
    """
    try:
        with open("missing_cases", "r") as file:
            missing_case = json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        missing_case = []
    missing_case.append(case_id)
    with open("missing_cases", "w") as f:
        json.dump(missing_case, f)

def main():
    #Loop through each case per page
    for entry in source.fetch_page(delay=200):
            #Extract case id
            case_id = source.get_caseid(entry)
            logging.info(case_id)

            if db.check_database(case_id):
                #Skip case if already inserted
                logging.info(f"Skipping {case_id}, already exists in DB.")
                continue
            else:
                title, date, court, xml_link = source.extract_case(entry)

            if xml_link is not None: 
                case_content = source.case_content(xml_link)

                #Generate case summary
                summary = llm.produce_summary(case_content, gemini1)

                time.sleep(30)

                if summary is not None: 
                    #Extract keywords from case content
                    keywords = llm.extract_keywords(case_content, gemini)
                    try: 
                        #Embed keywords
                        embedded_keywords = llm.generate_embeddings(keywords) 
                        #Insert metadata into database
                        db.insert_database(conn, case_id, title, date, court, xml_link, keywords, embedded_keywords, summary)
                        time.sleep(30)
                    except Exception as e: 
                        logging.error(f"case {case_id} failed during keyword embedding or DB insertion: {e}")
                        log_missing_case(case_id)
                        continue     
                            
                else: 
                    logging.error(f"[FAIL] No summary generated for case {case_id}. Not inserted")
                    log_missing_case(case_id)
                    continue 
            else: 
                logging.error(f"[FAIL] xml link not found")
                log_missing_case(case_id)
                continue

if __name__ == "__main__":
    main()     