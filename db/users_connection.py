import psycopg2
import os
from supabase import create_client
import streamlit as st

try: 
    SUPABASE_URL = st.secrets("SUPABASE_URL")
    PUBLIC_KEY = st.secrets("PUBLIC_ROLE")
except:
    SUPABASE_URL = os.environ.get("SUPABASE_URL")
    PUBLIC_KEY = os.environ.get("PUBLIC_ROLE")

anon_supabase = create_client(SUPABASE_URL, PUBLIC_KEY)