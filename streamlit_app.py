import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from pymongo import MongoClient
from datetime import datetime

# MongoDB connection
client = MongoClient("mongodb+srv://nicosherpa:Alibaba1320!!@publications.2gdpx.mongodb.net/plasticheal?retryWrites=true&w=majority&tls=true&tlsAllowInvalidCertificates=true")  # Use Streamlit Secrets for secure URI storage
db = client["plasticheal"]  # Replace with your MongoDB database name
collection = db["word_counts"]  # Replace with your MongoDB collection name

# Load publication data for min and max dates
publication_data = pd.DataFrame(list(collection.find({}, {"Publication Title": 1, "Publication Date": 1, "Project Name": 1, "Publication File": 1})))
publication_data['Publication Date'] = pd.to_datetime(publication_data['Publication Date'], errors='coerce')
min_date = publication_data['Publication Date'].min().strftime('%d.%m.%Y')
max_date = publication_data['Publication Date'].max().strftime('%d.%m.%Y')

# General statistics
total_papers = collection.distinct("Publication")
total_projects = collection.distinct("Project")
total_words = collection.aggregate([{"$group": {"_id": None, "TotalWords": {"$sum": "$Count"}}}])
formatted_total_words = f"{list(total_words)[0]['TotalWords']:,}"

# Display title and general dataset statistics
st.title("Publication Word Frequency Analysis")
st.write("Analyze word frequency across different projects and publications.")
st.write("### Dataset Summary")
st.write(f"- **Total Papers Investigated**: {len(total_papers)}")
st.write(f"- **Number of Projects**: {len(total_projects)}")
st.write(f"- **Time Frame**: {min_date} to {max_date}")
st.write(f"- **Total Words Investigated**: {formatted_total_words}")

# Search bar for word input
word = st.text_input("Enter a word to analyze", "").strip().lower()

# If word is entered, proceed with the analysis
if word:
    # Query MongoDB for word count data
    word_data = pd.DataFrame(list(collection.aggregate([
        {"$match": {"Word": word}},
        {"$group": {"_id": "$Publication", "TotalCount": {"$sum": "$Count"}}}
    ])))
    word_data.rename(columns={"_id": "Publication"}, inplace=True)

    # Merge with publication data for additional details
    word_data = word_data.merge(publication_data, left_on="Publication", right_on="Publication Title", how="left")
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
        st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
        project_data = word_data.groupby('Project')['TotalCount'].sum().sort_values(ascending=False)
        st.write(project_data)
        st.markdown("</div>", unsafe_allow_html=True)

        # Display word count by individual publication with additional columns centered
        st.subheader("Occurrences by Publication")
        word_data['Link'] = word_data['Link'].apply(lambda url: f'<a href="{url}" target="_blank">View PDF</a>')
        publication_data_display = word_data[['Publication', 'PubDate', 'Project', 'TotalCount', 'Link']].sort_values(by='TotalCount', ascending=False)
        publication_data_display.rename(columns={
            'PubDate': 'Publication Date',
            'TotalCount': f"Total Count: {word}"
        }, inplace=True)
        st.markdown("<div style='text-align: center;'>", unsafe_allow_html=True)
        st.write(publication_data_display.to_html(escape=False, index=False), unsafe_allow_html=True)
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.write(f"No occurrences of '{word}' found in the database.")

# Combined Comparison and Accumulation section
st.write("### Comparison and Accumulation")
accumulation_input = st.text_input("Enter words to compare and accumulate, separated by semicolons (;) for groups, use ';;' to separate groups", "").strip().lower()

if accumulation_input:
    groups = [[w.strip() for w in g.split(";") if w.strip()] for g in accumulation_input.split(";;") if g.strip()]
    fig = go.Figure()

    for i, words in enumerate(groups):
        accumulation_data = pd.DataFrame()

        for word in words:
            word_data = pd.DataFrame(list(collection.aggregate([
                {"$match": {"Word": word}},
                {"$group": {"_id": "$Publication", "TotalCount": {"$sum": "$Count"}}}
            ])))
            word_data.rename(columns={"_id": "Publication"}, inplace=True)
            word_data = word_data.merge(publication_data[['Publication Title', 'Publication Date']],
                                        left_on='Publication', right_on='Publication Title', how='left')
            word_data['Year'] = pd.to_datetime(word_data['Publication Date'], errors='coerce').dt.year
            year_data = word_data.groupby('Year')['TotalCount'].sum().reset_index(name=word)

            if accumulation_data.empty:
                accumulation_data = year_data
            else:
                accumulation_data = accumulation_data.merge(year_data, on='Year', how='outer').fillna(0)

        accumulation_data[f'Accumulated_Group_{i+1}'] = accumulation_data[words].sum(axis=1)

        # Add the accumulated line for this group to the plot with hover data
        fig.add_trace(go.Scatter(
            x=accumulation_data['Year'],
            y=accumulation_data[f'Accumulated_Group_{i+1}'],
            mode='lines+markers',
            marker=dict(size=8),
            line=dict(width=2),
            name=f"Group {i + 1} ({', '.join(words)})",
            hovertemplate="<b>Year</b>: %{x}<br>" +
                          "".join([f"<b>{w}</b>: %{{customdata[{j}]}}<br>" for j, w in enumerate(words)]) +
                          f"<b>Total Accumulated</b>: %{{y}}<extra></extra>",
            customdata=accumulation_data[words].values
        ))

    fig.update_layout(
        title="Accumulated Word Count Over Time (Multiple Groups)",
        xaxis_title="Year",
        yaxis_title="Accumulated Word Count",
        plot_bgcolor='rgba(0,0,0,0)',
        paper_bgcolor='rgba(0,0,0,0)',
        showlegend=True
    )
    
    st.plotly_chart(fig, use_container_width=True)

# Close MongoDB connection
client.close()