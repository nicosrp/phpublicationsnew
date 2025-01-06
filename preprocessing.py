import os
import re
import requests
import pandas as pd
from io import BytesIO
from collections import defaultdict
from PyPDF2 import PdfReader
import sqlite3

# Paths and settings
input_excel_path = 'publications_list.xlsx'  # Path to the Excel file with URLs
stopwords_file_path = 'stop_words.txt'  # Path to your stopwords file
output_db_path = 'word_counts.db'  # SQLite database file
output_csv_path = 'word_counts.csv'  # CSV output file

# Load stopwords
with open(stopwords_file_path, 'r') as f:
    stopwords = set(word.strip().lower() for word in f)

# Load publication data from Excel
publications_data = pd.read_excel(input_excel_path)

# Connect to SQLite database (or create if it doesn't exist)
conn = sqlite3.connect(output_db_path)
cursor = conn.cursor()

# Create a table for word counts if it doesn't exist
cursor.execute('''
    CREATE TABLE IF NOT EXISTS WordCounts (
        Publication TEXT,
        Date TEXT,
        Project TEXT,
        Word TEXT,
        Count INTEGER
    )
''')

# Helper function to check if a publication already exists in the database
def publication_exists(title, date):
    cursor.execute('SELECT 1 FROM WordCounts WHERE Publication = ? AND Date = ? LIMIT 1', (title, date))
    return cursor.fetchone() is not None

# Function to extract text from PDF and count words
def count_words_in_pdf_from_url(url):
    try:
        response = requests.get(url)
        if response.status_code == 200:
            pdf_content = BytesIO(response.content)
            reader = PdfReader(pdf_content)
            text = ""
            for page in reader.pages:
                text += page.extract_text() if page.extract_text() else ""
            
            words = re.findall(r'\b\w+\b', text.lower())
            word_counts = defaultdict(int)
            
            # Count words, excluding stopwords
            for word in words:
                if word not in stopwords:
                    word_counts[word] += 1
            return word_counts
        else:
            print(f"Failed to retrieve PDF from URL: {url}")
            return None
    except Exception as e:
        print(f"Error processing PDF from URL {url}: {e}")
        return None

# Track the number of papers for progress updates
total_papers = len(publications_data)
new_records = 0

# List to collect data for CSV output
csv_data = []

# Process each URL in the Excel file
for index, row in publications_data.iterrows():
    publication_title = row["Publication Title"]
    publication_date = row["Publication Date"]
    project_name = row["Project Name"]
    pdf_url = row["Publication File"]

    # Skip processing if this publication is already in the database
    if publication_exists(publication_title, publication_date):
        print(f"Skipping already processed paper {index + 1}/{total_papers}: {publication_title}")
        continue
    
    # Print progress
    print(f"Processing paper {index + 1}/{total_papers}: {publication_title}")
    
    # Extract and count words
    word_counts = count_words_in_pdf_from_url(pdf_url)
    if word_counts:
        # Insert data into the database and prepare data for CSV
        for word, count in word_counts.items():
            cursor.execute('INSERT INTO WordCounts (Publication, Date, Project, Word, Count) VALUES (?, ?, ?, ?, ?)', 
                           (publication_title, publication_date, project_name, word, count))
            csv_data.append([publication_title, publication_date, project_name, word, count])
        
        # Check value: Print word with the highest occurrence for this paper
        max_word = max(word_counts, key=word_counts.get)
        max_count = word_counts[max_word]
        print(f"  Most frequent word in '{publication_title}': '{max_word}' (Count: {max_count})")
        
        new_records += 1

# Save data to CSV
csv_df = pd.DataFrame(csv_data, columns=["Publication", "Date", "Project", "Word", "Count"])
csv_df.to_csv(output_csv_path, index=False)

# Commit changes and close the database connection
conn.commit()
conn.close()

print(f"Data processing complete. {new_records} new records added to word_counts.db and word_counts.csv.")