📞 Listening to New York City
An Interactive Data Story & Predictive Analysis of NYC 311 Service Requests

Every complaint tells a story. Together, they reveal the heartbeat of New York City.

🌆 Project Overview

New York City’s 311 system is more than a non-emergency hotline — it is the city’s collective voice. Every day, residents report noise disruptions, heating failures, illegal parking, sanitation issues, and other quality-of-life concerns. Individually, these complaints may seem small. At scale, they form a powerful dataset that reflects human behavior, infrastructure stress, and service efficiency across neighborhoods.

This project transforms NYC 311 data into an interactive analytical dashboard that combines:

Exploratory data analysis (EDA)

Visual storytelling

Predictive modeling insights

A dynamic, narrative-driven web application

The goal is not only to explore what New Yorkers complain about, but also when, where, and how efficiently the city responds — and how data can help improve future decision-making.

🚀 Live Application

🔗 Streamlit App:
👉 https://311calls-in9r8rkywe2rjkpfzt5dvr.streamlit.app/

🧠 What This Dashboard Does

This application allows users to explore NYC 311 complaints interactively, with filters that dynamically update both visuals and narrative explanations.

🔍 Key Features

Smart Filters

Day of week

Hour range

Borough selection

Top N complaint categories

Dynamic KPIs

Total complaints (filtered)

Closure rate

Median resolution time

Most frequent complaint type

Visual Storytelling

Top complaint types with narrative summaries

Resolution time comparisons by complaint

Hour × Day heatmap revealing behavioral patterns

Animated complaint evolution through the day

Interactive geographic map of complaint hotspots

Narratives That Adapt

Every chart is paired with a short explanation that updates automatically based on the selected filters — turning raw numbers into insights.

🗺️ Interactive Map (Optimized for Performance)

The map visualizes complaint hotspots across NYC using:

Marker clustering for speed

Status-based color coding

Lightweight tooltips and popups

Sampling to ensure smooth interaction

This design balances performance, clarity, and insight, even on limited hardware.

📊 Example Questions You Can Answer

When do complaints peak during the day?

Which issues dominate winter vs summer?

How fast does the city resolve different complaint types?

Which neighborhoods report the most issues?

How does complaint behavior change by time and location?

🧪 Data

Source: NYC Open Data — 311 Service Requests

Scope: Sample dataset (≈600 rows) included directly in the repository

Fields Used:

Complaint type

Status

Created & closed timestamps

Borough

Geographic coordinates

The app is designed to scale easily to much larger datasets.

🛠️ Tech Stack

Python

Streamlit – interactive web app

Pandas / NumPy – data processing

Plotly – rich interactive charts

Folium – geographic visualization

📂 Repository Structure
📦 nyc-311-dashboard
 ┣ 📜 app.py
 ┣ 📜 requirements.txt
 ┣ 📜 nyc311_sample.csv
 ┗ 📜 README.md

⚙️ How to Run Locally
# Clone the repository
git clone https://github.com/your-username/nyc-311-dashboard.git
cd nyc-311-dashboard

# Install dependencies
pip install -r requirements.txt

# Run the app
streamlit run app.py

📌 Why This Project Matters

This project demonstrates how public service data can be transformed into:

Actionable insights

Transparent performance metrics

A clearer understanding of urban life

It bridges the gap between raw data and human experience, showing how analytics can support smarter, more responsive cities.

🔮 Future Improvements

Integrate weather data for deeper seasonal analysis

Add predictive response-time estimates

Expand neighborhood-level equity analysis

Deploy with real-time data updates

📚 References

NYC Open Data – 311 Service Requests

Kontokosta, C. E., & Hong, B. (2015). Using 311 data to understand neighborhood-level urban issues.

NYC Mayor’s Office of Data Analytics (2023)

👤 Author

Latifa Ait Ali
Data Science


✨ If cities are living systems, 311 data is their pulse. This project listens carefully.
