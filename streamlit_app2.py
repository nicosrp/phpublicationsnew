import streamlit as st
import sqlite3
import pandas as pd
import plotly.graph_objects as go

# Connect to the SQLite database
db_path = 'word_counts.db'
conn = sqlite3.connect(db_path)

# Load publication data to get the correct min and max publication dates and PDF links
publication_data = pd.read_excel("publications_list.xlsx")
publication_data['Publication Date'] = pd.to_datetime(publication_data['Publication Date'], errors='coerce')
publication_data['Project Start Date'] = pd.to_datetime(publication_data['Project Start Date'], errors='coerce')
min_date = publication_data['Publication Date'].min().strftime('%d.%m.%Y')
max_date = publication_data['Publication Date'].max().strftime('%d.%m.%Y')

# General statistics from the database
query_total_papers = "SELECT COUNT(DISTINCT Publication) as TotalPapers FROM WordCounts"
query_total_projects = "SELECT COUNT(DISTINCT Project) as TotalProjects FROM WordCounts"
query_total_words = "SELECT SUM(Count) as TotalWords FROM WordCounts"

total_papers = pd.read_sql_query(query_total_papers, conn).iloc[0, 0]
total_projects = pd.read_sql_query(query_total_projects, conn).iloc[0, 0]
total_words = pd.read_sql_query(query_total_words, conn).iloc[0, 0]

# Format word count with commas for readability
formatted_total_words = f"{total_words:,}"

# Display title and general dataset statistics
st.title("Publication Word Frequency Analysis")
st.write("Analyze word frequency across different projects and publications.")
st.write("### Dataset Summary")
st.write(f"- **Total Papers Investigated**: {total_papers}")
st.write(f"- **Number of Projects**: {total_projects}")
st.write(f"- **Time Frame**: {min_date} to {max_date}")
st.write(f"- **Total Words Investigated**: {formatted_total_words}")

# Search bar for word input
word = st.text_input("Enter a word to analyze", "").strip().lower()

# If word is entered, proceed with the analysis
if word:
    # Query word count data
    query = '''
        SELECT Publication, SUM(Count) as TotalCount
        FROM WordCounts 
        WHERE Word = ? 
        GROUP BY Publication
        ORDER BY Publication
    '''
    word_data = pd.read_sql_query(query, conn, params=(word,))

    # Merge word_data with publication_data to ensure we use Publication Date and Project Name
    word_data = word_data.merge(
        publication_data[['Publication Title', 'Publication Date', 'Project Name', 'Publication File', 'Project Start Date']],
        left_on='Publication', right_on='Publication Title', how='left'
    )
    word_data.rename(columns={'Publication Date': 'PubDate', 'Publication File': 'Link', 'Project Name': 'Project'}, inplace=True)

    if not word_data.empty:
        # Extract year from the actual publication date
        word_data['Year'] = pd.to_datetime(word_data['PubDate'], errors='coerce').dt.year
        word_data.dropna(subset=['Year'], inplace=True)
        
        # Format the "Publication Date" column to DD.MM.YYYY
        word_data['PubDate'] = word_data['PubDate'].dt.strftime('%d.%m.%Y')

        # Group data by Year for time-series analysis based on publication date
        year_data = word_data.groupby('Year')['TotalCount'].sum().reset_index()

        # Plotting the time-series graph of word occurrences over the years with Plotly
        st.subheader(f"Word count over the years for '{word}'")
        fig = go.Figure()
        fig.add_trace(go.Scatter(
            x=year_data['Year'],
            y=year_data['TotalCount'],
            mode='lines+markers',
            marker=dict(size=8),
            line=dict(width=2, color="#1f77b4"),
            hovertemplate="<b>Year</b>: %{x}<br><b>Word Count</b>: %{y}<extra></extra>"
        ))
        fig.update_layout(
            title=f"Occurrences of '{word}' Over Time",
            xaxis_title="Year",
            yaxis_title="Word Count",
            plot_bgcolor='rgba(0,0,0,0)',
            paper_bgcolor='rgba(0,0,0,0)'
        )
        st.plotly_chart(fig, use_container_width=True)

        # Display word count by project centered
        st.subheader("Occurrences by Project")
        project_data = word_data.groupby('Project')['TotalCount'].sum().sort_values(ascending=False).reset_index()

        # Create project links
        def generate_project_link(row):
            if pd.notnull(row['Project Start Date']):
                year = row['Project Start Date'].year
                month = row['Project Start Date'].strftime('%b').lower()
                project_name = ''.join(e for e in row['Project'].replace(' ', '-').lower() if e.isalnum() or e == '-')
                return f"https://plasticheal.dk/projects/{year}/{month}/{project_name}/"
            return None

        project_data = project_data.merge(publication_data[['Project Name', 'Project Start Date']].drop_duplicates(),
                                          left_on='Project', right_on='Project Name', how='left')
        project_data['Project Link'] = project_data.apply(generate_project_link, axis=1)
        project_data.drop(columns=['Project Name', 'Project Start Date'], inplace=True)

        # Display the table with links
        project_data_display = project_data[['Project', 'Project Link', 'TotalCount']]
        project_data_display.rename(columns={'Project': 'Project Name', 'TotalCount': f"Total Count: {word}"}, inplace=True)

        # Render table with clickable links
        def make_clickable(link):
            if pd.notnull(link):
                return f'<a href="{link}" target="_blank">{link}</a>'
            return ''

        project_data_display['Project Link'] = project_data_display['Project Link'].apply(make_clickable)
        st.markdown(project_data_display.to_html(escape=False, index=False), unsafe_allow_html=True)

        # Display word count by individual publication with additional columns centered
        st.subheader("Occurrences by Publication")
        word_data['Link'] = word_data['Link'].apply(lambda url: f'<a href="{url}" target="_blank">View PDF</a>')
        publication_data_display = word_data[['Publication', 'PubDate', 'Project', 'TotalCount', 'Link']].sort_values(by='TotalCount', ascending=False)
        publication_data_display.rename(columns={
            'PubDate': 'Publication Date',
            'TotalCount': f"Total Count: {word}"
        }, inplace=True)
        st.markdown(publication_data_display.to_html(escape=False, index=False), unsafe_allow_html=True)
    else:
        st.write(f"No occurrences of '{word}' found in the database.")

# Close database connection
conn.close()