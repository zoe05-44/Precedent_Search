import db.check as db
import db.citation_op as CT
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

logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.WARNING)

gemini = llm.gemini_model()
gemini1 = llm.gemini_model1()
embed_model = llm.load_model()

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
                
            # Use the modular function
            success = source.process_single_case(case_id, xml_link, title, date, court)
            if not success:
                continue

if __name__ == "__main__":
    main()