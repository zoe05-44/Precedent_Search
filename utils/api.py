import time
import requests
import xml.etree.ElementTree as ET
from lxml import etree
import logging
import re

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

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
        
        # 2. Determine the middle "branch" (subdivision or division)
    branch = (match.group('subdivision') or match.group('division') or "").lower()
            
        # 3. Build the URL string
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