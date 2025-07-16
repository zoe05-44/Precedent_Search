from db.connection import conn
import logging 

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)


def check_database(case_id):
    """
    Check Database for unique case id to avoid duplicates
    """
    cur = conn.cursor()
    query = "SELECT EXISTS(SELECT 1 FROM cases WHERE case_id = %s);"
    cur.execute(query,(case_id,))
    exists = cur.fetchone()[0]
    cur.close()
    return exists


def get_courts():
    """
    Fetch all distinct court names from the 'cases' table.
    """
    cur = conn.cursor()

    cur.execute("SELECT DISTINCT court FROM cases ORDER BY court;")
    court_types = [row[0] for row in cur.fetchall()]
    cur.close()
    return court_types

def fetch_cases(embedded_keywords, court):
        """
        Find similar cases using cosine distance between database keywords and input keywords
        """
        cur = conn.cursor()
            
        query = """
        SELECT case_name, court, url, summary, keyword_vectors <=> %s::vector AS distance
        FROM cases 
        WHERE (%s = 'Any' OR court = %s)
        ORDER BY distance ASC
        LIMIT 10;
    """
        cur.execute(query, (f"[{embedded_keywords}]", court, court))
        results = cur.fetchall()
        cur.close()
        return results

def insert_database(conn, id, name, date, court, url, keywords,embeddings,summary):
    """
    Insert case metadata into the database
    """
    cur = conn.cursor()

    query = """
    INSERT INTO cases(case_id, case_name, date, court, url, keywords, keyword_vectors, summary) 
    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
    ON CONFLICT (case_id) DO NOTHING;
    """
    cur.execute(query, (id, name, date, court, url, keywords, embeddings, summary))
    conn.commit()
    cur.close()
    logging.info("case inserted")