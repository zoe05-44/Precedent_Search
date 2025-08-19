import psycopg2
import streamlit as st
import os

DATABASE_URL = st.secrets("DATABASE_URL")
#connect to the supabase database
conn = psycopg2.connect(DATABASE_URL)