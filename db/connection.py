import psycopg2
import os

DATABASE_URL = os.environ.get("DATABASE_URL")
#connect to the supabase database
conn = psycopg2.connect(DATABASE_URL)