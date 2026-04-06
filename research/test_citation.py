from utils import api
from db import citation_op as CT
from db.connection import conn 
import logging 

cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM cases WHERE neutral_extracted = FALSE OR citation_extracted = FALSE")
total = cur.fetchone()[0]
logging.info(f"Total unprocessed cases: {total}")

links = CT.fetch_unprocessed_links(total)
for case_id, url in links: 
    try:
        et_doc, lxml_doc = api.extract_from_xml(url)          # unpack tuple
        neutral = api.get_nuetral_citation(et_doc)            
        CT.update_neutral_citation(cur, case_id, neutral)
        conn.commit()

        citations = api.get_cited_cases(et_doc, lxml_doc)     # pass both
        CT.insert_citations(cur, case_id, citations)
        cur.execute("""
                UPDATE cases SET citation_extracted = TRUE 
                WHERE case_id = %s
            """, (case_id,))
        conn.commit()
        logging.info(f"Processed {case_id} — neutral: {neutral}, citations: {len(citations)}")

    except Exception as e:
        logging.error(f"Failed on {case_id}: {e}")
        conn.rollback()
        continue