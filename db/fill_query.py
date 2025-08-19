import json
import logging
from .connection import conn


def log_queries(cur, session_id, query_text, extracted_keywords, query_embedding, query_id,):
    """
    SQL Query to populate queries table in database
    """
 
    keywords_json = json.dumps(extracted_keywords)

    query = """
    INSERT INTO queries(session_id, query_text, extracted_keywords, query_embedding, query_id) 
    VALUES (%s, %s, %s, %s, %s)
    ON CONFLICT (query_id) DO NOTHING;
    """
    cur.execute(query, (session_id, query_text, keywords_json, query_embedding, query_id))
    logging.info("query inserted")

def log_query_results(cur, query_id, case_id, rank, similarity_score, feedback_score, query_result_id):
    """
    SQL Query to populate query_results table in database
    """

    query = """
    INSERT INTO query_results(query_id, case_id, rank, similarity_score, feedback_score, query_result_id) 
    VALUES (%s, %s, %s, %s, %s, %s);
    """
    cur.execute(query, (query_id, case_id, rank, similarity_score, feedback_score, query_result_id))
    logging.info("query inserted")

def log_search_transaction(query_data, results_data):
    """
    Logs a query and all its results in a single database transaction.
    
    :param query_data: A dictionary with all the data for the 'queries' table.
    :param results_data: A list of dictionaries, where each dict contains the data for one row in 'query_results'.
    """
    try:
        with conn.cursor() as cur:
            # Insert the main query
            log_queries(
                cur,
                query_data['session_id'],
                query_data['query_text'],
                query_data['extracted_keywords'],
                query_data['query_embedding'],
                query_data['query_id'],
            )
            
            # Loop through and insert all results
            for result in results_data:
                log_query_results(
                    cur,
                    result['query_id'],
                    result['case_id'],
                    result['rank'],
                    result['similarity_score'],
                    result['feedback_score'],
                    result['query_result_id']
                )

        # Commit the transaction ONCE after all operations succeed
        conn.commit()
        logging.info("Transaction successful: Query and all results have been logged.")

    except Exception as e:
        # If any step fails, roll back the entire transaction
        logging.error("Transaction failed: %s", e, exc_info=True)
        conn.rollback()


def update_feedback_score(query_result_id, feedback_score):
    """
    Updates the feedback score for a specific query result.
    """
    try:
        with conn.cursor() as cur:
            sql = """
            UPDATE query_results
            SET feedback_score = %s
            WHERE query_result_id = %s;
            """
            cur.execute(sql, (feedback_score, query_result_id))
        conn.commit()
        logging.info(f"Feedback updated for {query_result_id} with score {feedback_score}.")
        return True
    except Exception as e:
        logging.error(f"Failed to update feedback: {e}")
        conn.rollback()
        return False