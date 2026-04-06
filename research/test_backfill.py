from utils import api
from db import citation_op as CT
from db.connection import conn 
import logging 

def extract_neutral_cases():
    """
    Extract case neutral citataion and ulr to test if url creayting function works 
    """
    cur = conn.cursor()
    query= """
    SELECT neutral_citation, url 
    FROM public.cases
    WHERE cases. neutral_extracted is True AND neutral_citation IS NOT NULL 
    LIMIT 300;
    """
    try:
        cur.execute(query)
        # This returns the data as a list of tuples
        results = cur.fetchall()
        return results
    except Exception as e:
        print(f"Database error: {e}")
        return []
    finally:
        cur.close()

def main(): 
    failed_citations=[]
    test_data = extract_neutral_cases()
    for case_citation, true_url in test_data: 
        test_url = api.build_case_url(case_citation)
        if test_url == true_url: 
            print(f"Test passed for {case_citation}")
        else: 
            print(f"Test not passed for {case_citation}")
            failed_citations.append((test_url, true_url, case_citation))
    print(failed_citations)
main()


