from utils import api
from db import citation_op as CT
from db.connection import conn 
import db.check as db
import time
import json
import utils.genai as llm
import logging

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

gemini = llm.gemini_model()
gemini1 = llm.gemini_model1()
embed_model = llm.load_model()

def bakfill_missing_metadata(): 
    missing = CT.get_priority_missing_cases()
    
    if not missing:
        logger.warning("No missing cases retrieved from the database.")
        return

    logger.info(f"Starting processing for {len(missing)} cases.")

    for citation, occ in missing: 
        # Handle the 'None' citation before it hits the API function
        if citation is None:
            logger.error("Skipping a record: Citation is None (NULL in database).")
            continue

        try: 
            xml_link = api.build_case_url(citation)
            
            if not xml_link:
                    logging.warning(f"Could not construct URL for {citation}")
                    continue
            #get case content
            case_content = api.cases_content(xml_link )
            if not case_content:
                logging.error(f"Could not fetch content from {xml_link}")
                continue
                #Get case summary
            summary = llm.produce_summary(case_content, gemini1)
            time.sleep(30) # Respect rate limits
            
            if summary:
                keywords = llm.extract_keywords(case_content, gemini)
                embedded_keywords = llm.generate_embeddings(keywords, embed_model)

                db.insert_database(
                    conn, 
                    citation, 
                    xml_link, 
                    keywords, 
                    embedded_keywords, 
                    summary
                )
                logging.info(f"Successfully backfilled {citation}")
                time.sleep(30)
            else:
                logging.error(f"Summary generation failed for {citation}")

        except Exception as e:
            logging.error(f"Error during backfill of {citation}: {e}")
            continue

    logger.info("Batch processing complete.")

if __name__ == "__main__":
    bakfill_missing_metadata()
