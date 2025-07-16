import time
import requests
import xml.etree.ElementTree as ET
from lxml import etree
import logging

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)

# Define XML namespaces for parsing
namespaces = {
    'atom': 'http://www.w3.org/2005/Atom',
    'tna': 'https://caselaw.nationalarchives.gov.uk',
    'akn': 'http://docs.oasis-open.org/legaldocml/ns/akn/3.0'
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
    title = entry.find('atom:title', namespaces).text.strip()
    date = entry.find('atom:published', namespaces).text.strip()
    court = entry.find('atom:author/atom:name', namespaces).text.strip()

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
