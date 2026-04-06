from utils import api
from db import citation_op as CT
from db.connection import conn 
import db.check as db
import time
import json
import utils.genai as llm
import logging
from utils.api import process_single_case, extract_case_metadata_from_xml  # Import the modular functions

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

    logger.info(f"Starting backfill processing for {len(missing)} cases.")

    for citation, occ in missing: 
        # Handle the 'None' citation before it hits the API function
        if citation is None:
            logger.error("Skipping a record: Citation is None (NULL in database).")
            continue

        try: 
            xml_link = api.build_case_url(citation)
            
            if not xml_link or xml_link == "No Citation Found":
                logging.warning(f"Could not construct URL for {citation}")
                continue
            
            # Extract metadata directly from the XML file (same way main.py does from Atom entry)
            title, date, court = extract_case_metadata_from_xml(xml_link)
            logger.info(f"Extracted metadata for {citation}: title={title}, date={date}, court={court}")
                
            # Use the modular processing function with extracted metadata
            success = process_single_case(
                case_id=citation,  # Use citation as case_id for backfill
                xml_link=xml_link,
                title=title,       # Extracted from XML
                date=date,         # Extracted from XML (valid database date)
                court=court,       # Extracted from XML
                extract_metadata_if_missing=False  # Metadata already extracted, don't re-extract
            )
            
            if success:
                logging.info(f"Successfully backfilled {citation}")
            else:
                logging.error(f"Failed to backfill {citation}")
                
        except Exception as e:
            logging.error(f"Error during backfill of {citation}: {e}")
            continue

    logger.info("Backfill processing complete.")

if __name__ == "__main__":
    bakfill_missing_metadata()