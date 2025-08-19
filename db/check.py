from db.connection import conn
from .users_connection import anon_supabase
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
    response = anon_supabase.rpc("distinct_courts").execute()
    return sorted(response.data)

def fetch_cases(embedding, court = "Any", limit = 10):
        """
        Find similar cases using cosine distance between database keywords and input keywords
        """
        if isinstance(embedding, str):
            embedding = [float(x) for x in embedding.split(",")] 

        #Function match_cases exists in supabase 
        response = anon_supabase.rpc(
            "match_cases",
            {
                "query_embedding": embedding,
                "court_filter": court,
                "match_count": limit,
            },
        ).execute()

        results = []
        for row in response.data or []:
            results.append({
                "case_id": row.get("case_id"),
                "case_name": row.get("case_name", "Unknown"),
                "court": row.get("court", "Unknown"),
                "url": row.get("url", "#"),
                "summary": row.get("summary", "No summary available."),
                "similarity_score": row.get("distance", 1.0),  # use distance from your SQL
            })
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