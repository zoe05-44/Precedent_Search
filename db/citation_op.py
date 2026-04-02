"""Contains functions to feed the citation table in my database."""
import logging
from db.connection import conn 

def get_priority_missing_cases(limit=100):
    """Get most-cited missing cases to scrape"""
    cur = conn.cursor()
    cur.execute("""
        SELECT cited_case_name, COUNT(*) as refs
        FROM case_citations
        WHERE cited_case_id IS NULL
        GROUP BY cited_case_name
        ORDER BY refs DESC
        LIMIT %s
    """, (limit,))
    return cur.fetchall()




def fetch_unprocessed_links(batch_size: int=50):
    query = """
            SELECT case_id, url
            FROM cases
            WHERE neutral_extracted = FALSE
            OR citation_extracted = FALSE
            LIMIT %s;
        """

    with conn.cursor() as cur:
            cur.execute(query, (batch_size,))
            results = cur.fetchall()

    return results

def insert_citations(cur, citing_case_id, citations):
    for citation in citations:
        citation_text = citation["citation_text"]
        context = citation["context"]
        
        cur.execute("""
            SELECT case_id FROM cases 
            WHERE neutral_citation = %s
        """, (citation_text,))
        
        result = cur.fetchone()
        cited_case_id = result[0] if result else None
        
        cur.execute("""
            INSERT INTO case_citations 
                (citing_case_id, cited_case_id, cited_case_name, citation_context)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (citing_case_id, cited_case_id) DO NOTHING
        """, (citing_case_id, cited_case_id, citation_text, context))

def update_neutral_citation(cur, case_id, neutral_citation):
    cur.execute("""
        UPDATE cases 
        SET neutral_citation = %s,
            neutral_extracted = TRUE
        WHERE case_id = %s
    """, (neutral_citation, case_id))

def retry_unmatched_citations():
    """
    Find citations with cited_case_id = NULL and try matching again
    """
    cur = conn.cursor()
    
    cur.execute("""
        SELECT citation_id, citing_case_id, cited_case_name
        FROM case_citations
        WHERE cited_case_id IS NULL
    """)
    
    unmatched = cur.fetchall()
    matched_count = 0
    
    for citation_id, citing_case_id, citation_text in unmatched:
        # Try to match
        cur.execute("""
            SELECT case_id 
            FROM cases 
            WHERE neutral_citation = %s
        """, (citation_text,))
        
        result = cur.fetchone()
        
        if result:
            # Update with matched case_id
            cur.execute("""
                UPDATE case_citations
                SET cited_case_id = %s
                WHERE citation_id = %s
            """, (result[0], citation_id))
            matched_count += 1
    
    conn.commit()
    return matched_count

def get_citation_counter(cur, case_id):
    """Get the number of times a case has been cited."""
    query = "SELECT COUNT(*) FROM case_citations WHERE cited_case_id = %s;"
    cur.execute(query, (case_id,))
    count = cur.fetchone()[0]
    return count

def refresh_citation_stats():
    """Refresh the materialized view that aggregates citation counts."""
    cursor = conn.cursor()
    cursor.execute("REFRESH MATERIALIZED VIEW CONCURRENTLY case_citation_stats")
    conn.commit()