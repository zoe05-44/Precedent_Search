import time
import requests
import xml.etree.ElementTree as ET
from lxml import etree
import logging
import re
import json

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

logging.getLogger("sentence_transformers").setLevel(logging.WARNING)
logging.getLogger("transformers").setLevel(logging.WARNING)
# Define XML namespaces for parsing
namespaces = {
    'atom': 'http://www.w3.org/2005/Atom',
    'tna': 'https://caselaw.nationalarchives.gov.uk',
    'akn': 'http://docs.oasis-open.org/legaldocml/ns/akn/3.0',
    'uk': 'https://caselaw.nationalarchives.gov.uk/akn'}
UK_NS = 'https://caselaw.nationalarchives.gov.uk/akn'

def build_case_url(citation): 
    pattern = r"""
    \[(?P<year>\d{4})\]                # year in square brackets
    \s+
    (?P<court>[A-Z]+)                 # court (EWHC, EWCA, UKFTT)
    (?:\s+(?P<division>[A-Za-z]+))?   # optional division (Civ, Crim)
    \s+
    (?P<number>\d+)                   # case number
    (?:\s+\((?P<subdivision>[^)]+)\))? # optional (Ch), (QB), etc.
    """
    match = re.search(pattern, citation, re.VERBOSE)
    if not match:
        return "No Citation Found"    #Filter out parts that are None 

    court = match.group('court').lower()
    year = match.group('year')
    number = match.group('number')
        
        # Determine the middle "branch" (subdivision or division)
    branch = (match.group('subdivision') or match.group('division') or "").lower()
            
        # Build the URL string
    if branch:
        return f"https://caselaw.nationalarchives.gov.uk/{court}/{branch}/{year}/{number}/data.xml"
    else:
        return f"https://caselaw.nationalarchives.gov.uk/{court}/{year}/{number}/data.xml"    


def extract_from_xml(url):
    doc = requests.get(url)
    logging.info(f"Fetched case file from {url} successfully")
    et_root = ET.fromstring(doc.text)      # for all existing functions
    lxml_root = etree.fromstring(doc.content)  # for context extraction
    return et_root, lxml_root

def normalize_citation(text: str) -> str:
    return re.sub(r"\s+", " ", text.strip())

def get_cited_cases(et_entry, lxml_entry):
    refs = et_entry.findall('.//akn:ref', namespaces)
    cases_cited = []
    seen = set()

    for ref in refs:
        if ref.get(f'{{{UK_NS}}}type') != 'case':
            continue
        if ref.get(f'{{{UK_NS}}}isNeutral') != 'true':
            continue

        citation_text = ref.get(f'{{{UK_NS}}}canonical')
        if not citation_text:
            continue

        citation_text = normalize_citation(citation_text)
        if citation_text in seen:
            continue
        seen.add(citation_text)

        # Get context using lxml
        lxml_refs = lxml_entry.xpath(
            f".//akn:ref[@uk:canonical='{citation_text}']",
            namespaces=namespaces
        )
        context = None
        if lxml_refs:
            para = lxml_refs[0].xpath("ancestor::*[local-name()='p'][1]")
            if para:
                context = para[0].xpath("string(.)").strip()[:300]

        cases_cited.append({
            "citation_text": citation_text,
            "context": context
        })
    return cases_cited

def get_nuetral_citation(entry): 
    cite_elem = entry.find('.//akn:proprietary/uk:cite', namespaces)
    if cite_elem is not None and cite_elem.text:
        return normalize_citation(cite_elem.text)
    fallback_elem = entry.find('.//akn:neutralCitation', namespaces)
    if fallback_elem is not None and fallback_elem.text:
        return normalize_citation(fallback_elem.text)

    court_elem = entry.find('.//uk:court', namespaces)
    year_elem = entry.find('.//uk:year', namespaces)
    number_elem = entry.find('.//uk:number', namespaces)

    if all(e is not None for e in [court_elem, year_elem, number_elem]):
        court_text = court_elem.text.strip()
        year_text = year_elem.text.strip()
        number_text = number_elem.text.strip()

        if "-" in court_text:
            main, division = court_text.split("-", 1)

            if division.lower() == "civil":
                division = "Civ"
            elif division.lower() == "criminal":
                division = "Crim"

            formatted_court = f"{main} {division}"
        else:
            formatted_court = court_text

        return f"[{year_text}] {formatted_court} {number_text}"
    return None

def extract_and_process_citations(case_id, xml_url):
    """
    Extract neutral citation and cited cases from a case XML file.
    
    Args:
        case_id: The unique case identifier
        xml_url: The URL to the case XML file
        
    Returns:
        Dictionary with keys:
            - 'case_id': The case identifier
            - 'neutral_citation': The neutral citation (str or None)
            - 'cited_cases': List of cited case dictionaries with 'citation_text' and 'context'
            - 'success': Boolean indicating if extraction was successful
            - 'error': Error message if unsuccessful (None if successful)
    """
    try:
        et_root, lxml_root = extract_from_xml(xml_url)
        
        # Extract neutral citation
        neutral_citation = get_nuetral_citation(et_root)
        
        # Extract cited cases
        cited_cases = get_cited_cases(et_root, lxml_root)
        
        return {
            'case_id': case_id,
            'neutral_citation': neutral_citation,
            'cited_cases': cited_cases,
            'success': True,
            'error': None
        }
    except Exception as e:
        logging.error(f"Failed to extract citations for case {case_id}: {e}")
        return {
            'case_id': case_id,
            'neutral_citation': None,
            'cited_cases': [],
            'success': False,
            'error': str(e)
        }

def fetch_page(delay=120):
    """
    Fetch page-by-page XML feed of legal cases.
    Waits for `delay` seconds between pages.
    """
    base_url = "https://caselaw.nationalarchives.gov.uk/atom.xml"
    current_url = base_url
    page = 0
    while current_url:
        logging.info(f"Fetching Page {page + 1}: {current_url}")
        response = requests.get(current_url)
        logging.info(f"Status Code: {response.status_code}")

        if response.status_code != 200:
            logging.error(f"Failed to fetch page: {response.status_code}")
            break

        root = ET.fromstring(response.text)

        # Extract <each> entry in the feed
        entries = root.findall('atom:entry', namespaces)
        yield from entries  # pass entries one by one

        #Find the next link
        next_link = root.find(".//atom:link[@rel='next']", namespaces)
        current_url = next_link.attrib['href'] if next_link is not None else None

        page += 1

        logging.info(f"Waiting {delay // 60} minutes before next page...")
        time.sleep(delay)

def get_caseid(entry):
    """
    Extract the unique case URI. Fallback to Atom <id> if <tna:uri> is missing.
    """
    tna_uri_elem = entry.find('tna:uri', namespaces)
    if tna_uri_elem is not None and tna_uri_elem.text:
        return tna_uri_elem.text.strip()
    else:
        return entry.find('atom:id', namespaces).text.strip()

def extract_case(entry):
    """
    Extract case metadata: title, date, name, and xml_link
    """
    title_tag= entry.find('atom:title', namespaces)
    if title_tag is not None: 
        title = title_tag.text.strip()
    else: 
        title = 'Unknown'

    date_tag = entry.find('atom:published', namespaces)
    if date_tag is None: 
        date_tag = entry.find('atom:updated', namespaces)
    if date_tag is not None: 
        date = date_tag.text.strip()
    else: 
        date = 'Unknown'

    court_tag = entry.find('atom:author/atom:name', namespaces)
    if court_tag is not None: 
        court = court_tag.text.strip()
    else: 
        court = 'Unknown'

    xml_link = None
    for link in entry.findall('atom:link', namespaces):
        if 'akn+xml' in link.attrib.get('type', ''):
            xml_link = link.attrib['href']
            break

    if not xml_link:
        #xml link remains None
        logging.warning("No XML link found. Skipping.")

    return title, date, court, xml_link

def case_content(xml_link):
    """
    Download case xml file and parse to extract:
    case judgement 
    first 10 paragraphs
    """
    output = []

    # Fetch XML
    case_text = requests.get(xml_link)
    logging.info(f"Status: {case_text.status_code}")

    judgement_root = etree.fromstring(case_text.content)

    # Get Case Judgement
    outcome = judgement_root.xpath(
        "//*[local-name()='decision']//*[local-name()='p']/text()"
    )
    output += outcome

    paragraphs = []

    # Extract paragraphs with numbering and content
    for para in judgement_root.xpath("//*[local-name()='paragraph']"):
        number_nodes = para.xpath(".//*[local-name()='num']")
        number = number_nodes[0] if number_nodes else None

        content_nodes = para.xpath(".//*[local-name()='content']")
        content = content_nodes[0] if content_nodes else None

        # Gather all text inside paragraph content
        text_elements = content.xpath(".//*[local-name()='p']//text()") if content is not None else []
        text = ' '.join(text_elements).strip()

        if text:
            para_num = number.text.strip() if number is not None else ''
            paragraphs.append((para_num, text))

    # Append the first 10 paragraphs in 'output'
    for i, (num, text) in enumerate(paragraphs[:10], 1):
        output.append(f"{num}. {text}")

    return output

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

def extract_date_from_citation(citation):
    """
    Extract year from legal citation and return as valid date string.
    Examples: "[2009] EWHC 339 (Ch)" -> "2009-01-01"
    """
    if not citation:
        # Return today's date as fallback
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")
    
    try:
        # Extract year from citation using regex
        year_match = re.search(r'\[(\d{4})\]', citation)
        if year_match:
            year = year_match.group(1)
            return f"{year}-01-01"  # Use first day of the year
        else:
            # Fallback to today's date
            from datetime import datetime
            return datetime.now().strftime("%Y-%m-%d")
    except Exception as e:
        logging.warning(f"Could not extract year from citation '{citation}': {e}")
        from datetime import datetime
        return datetime.now().strftime("%Y-%m-%d")

def extract_case_metadata_from_xml(xml_url):
    """
    Extract case metadata (title, date, court) directly from case XML file.
    Similar to extract_case() but works with XML URLs instead of Atom entries.
    
    Args:
        xml_url: URL to the case XML file
        
    Returns:
        tuple: (title, date, court) extracted from XML
    """
    try:
        et_root, _ = extract_from_xml(xml_url)
        
        # Try to extract title from neutral citation
        title = get_nuetral_citation(et_root)
        if not title:
            title = f"Case from {xml_url}"
        
        # Try to extract published date
        date = None
        date_elem = et_root.find('.//atom:published', namespaces)
        if date_elem is not None and date_elem.text:
            date = date_elem.text.strip()
        else:
            date_elem = et_root.find('.//atom:updated', namespaces)
            if date_elem is not None and date_elem.text:
                date = date_elem.text.strip()
        
        # If no date found in XML, extract from citation
        if not date:
            if title:
                date = extract_date_from_citation(title)
            else:
                from datetime import datetime
                date = datetime.now().strftime("%Y-%m-%d")
        
        # Try to extract court
        court = None
        court_elem = et_root.find('.//atom:author/atom:name', namespaces)
        if court_elem is not None and court_elem.text:
            court = court_elem.text.strip()
        else:
            court_elem = et_root.find('.//uk:court', namespaces)
            if court_elem is not None and court_elem.text:
                court = court_elem.text.strip()
        
        if not court:
            court = "Unknown"
        
        return title, date, court
        
    except Exception as e:
        logging.error(f"Failed to extract metadata from XML {xml_url}: {e}")
        # Return sensible defaults
        from datetime import datetime
        return f"Case from {xml_url}", datetime.now().strftime("%Y-%m-%d"), "Unknown"

def process_single_case(case_id, xml_link, title=None, date=None, court=None, extract_metadata_if_missing=True):
    """
    Process a single case: extract content, generate summary, keywords, embeddings,
    and citations, then insert/update database.
    
    Args:
        case_id: Unique case identifier
        xml_link: URL to the case XML file
        title: Case title (optional, will extract if None and extract_metadata_if_missing=True)
        date: Case date (optional, will extract if None and extract_metadata_if_missing=True) 
        court: Case court (optional, will extract if None and extract_metadata_if_missing=True)
        extract_metadata_if_missing: If True, extract missing metadata from XML
    
    Returns:
        bool: True if successful, False if failed
    """
    import db.check as db
    import db.citation_op as CT
    from db.connection import conn
    import utils.genai as llm
    
    # Initialize AI models
    gemini = llm.gemini_model()
    gemini1 = llm.gemini_model1()
    embed_model = llm.load_model()
    
    try:
        # Rate limiting: longer sleep between cases to avoid AI quota limits (20 requests per period)
        time.sleep(15)  # Increased from 5 to 15 seconds
        
        # If metadata not provided and we should extract it, we need to get it from somewhere
        # For backfill cases, we might need to extract metadata from the XML
        if (title is None or date is None or court is None) and extract_metadata_if_missing:
            # For backfill, we might need to extract metadata from the XML content
            # This is a simplified approach - in practice you might need more sophisticated extraction
            try:
                # Try to extract basic metadata from XML
                et_root, _ = extract_from_xml(xml_link)
                if title is None:
                    title_elem = et_root.find('.//atom:title', namespaces)
                    title = title_elem.text.strip() if title_elem is not None else f"Case {case_id}"
                if date is None:
                    date_elem = et_root.find('.//atom:published', namespaces)
                    if date_elem is None:
                        date_elem = et_root.find('.//atom:updated', namespaces)
                    date = date_elem.text.strip() if date_elem is not None else None
                if court is None:
                    court_elem = et_root.find('.//atom:author/atom:name', namespaces)
                    court = court_elem.text.strip() if court_elem is not None else "Unknown"
            except Exception as e:
                logging.warning(f"Could not extract metadata for {case_id}, using defaults: {e}")
                if title is None: title = f"Case {case_id}"
                if date is None: date = None  # Will be extracted from citation later
                if court is None: court = "Unknown"
            
            # If date is still None, extract from citation (for backfill cases)
            if date is None:
                date = extract_date_from_citation(case_id)
            
        if xml_link is not None: 
            content_data = case_content(xml_link)

            #Generate case summary (first AI call)
            summary = llm.produce_summary(content_data, gemini1)
            time.sleep(45)  # Increased from 30 to 45 seconds between AI calls

            if summary is not None: 
                #Extract keywords from case content (second AI call)
                keywords = llm.extract_keywords(content_data, gemini)
                try: 
                    #Embed keywords
                    embedded_keywords = llm.generate_embeddings(keywords, embed_model) 
                    #Insert metadata into database
                    db.insert_database(conn, case_id, title, date, court, xml_link, keywords, embedded_keywords, summary)
                    time.sleep(60)  # Increased from 30 to 60 seconds after database operations
                    
                    #Extract and process citations
                    citation_data = extract_and_process_citations(case_id, xml_link)
                    if citation_data['success']:
                        cur = conn.cursor()
                        try:
                            # Update neutral citation
                            if citation_data['neutral_citation']:
                                CT.update_neutral_citation(cur, case_id, citation_data['neutral_citation'])
                                logging.info(f"Updated neutral citation for {case_id}: {citation_data['neutral_citation']}")
                            
                            # Insert cited cases
                            if citation_data['cited_cases']:
                                CT.insert_citations(cur, case_id, citation_data['cited_cases'])
                                logging.info(f"Inserted {len(citation_data['cited_cases'])} citations for {case_id}")
                            
                            conn.commit()
                        except Exception as e:
                            logging.error(f"Failed to insert citations for case {case_id}: {e}")
                            conn.rollback()
                        finally:
                            cur.close()
                    else:
                        logging.warning(f"Citation extraction failed for {case_id}: {citation_data['error']}")
                    
                    return True
                    
                except Exception as e: 
                    logging.error(f"case {case_id} failed during keyword embedding or DB insertion: {e}")
                    # Rollback transaction to prevent "transaction aborted" errors on subsequent operations
                    try:
                        conn.rollback()
                        logging.info(f"Rolled back transaction for failed case {case_id}")
                    except Exception as rollback_error:
                        logging.warning(f"Could not rollback transaction: {rollback_error}")
                    log_missing_case(case_id)
                    return False     
                        
            else: 
                logging.error(f"[FAIL] No summary generated for case {case_id}. Not inserted")
                log_missing_case(case_id)
                return False 
        else: 
            logging.error(f"[FAIL] xml link not found for {case_id}")
            log_missing_case(case_id)
            return False
            
    except Exception as e:
        logging.error(f"Unexpected error processing case {case_id}: {e}")
        log_missing_case(case_id)
        return False