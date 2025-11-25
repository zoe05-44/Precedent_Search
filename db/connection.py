import psycopg2
import streamlit as st
from dotenv import load_dotenv
import os

load_dotenv()

try: 
    DATABASE_URL = st.secrets["DATABASE_URL"]
except Exception as e:
    print(f"Could not load from Streamlit secrets: {e}")
    DATABASE_URL = os.environ.get("DATABASE_URL")

if not DATABASE_URL:
    raise ValueError("DATABASE_URL is not set. Please check your .env file or Streamlit secrets.")

print(f"Connecting with DATABASE_URL: {DATABASE_URL[:20]}...")  

# Connect to the supabase database
conn = psycopg2.connect(DATABASE_URL)