# Install venv if not already installed
sudo apt update
sudo apt install python3-venv -y

# Create virtual environment
python3 -m venv venv

# Activate it
source venv/bin/activate

# Install BeautifulSoup
pip install beautifulsoup4

# install playwright
pip install playwright
playwright install chromium

# Install Pandas
pip install pandas


# Run scraper File:
python3 scraper.py



## Additional Development

# separate report-generation script
python3 analytics.py

# Install Streamlit:
pip install streamlit plotly

# Run the dashboard:
streamlit run dashboard.py


# To Export .db into CSV file
python3 -c "
import sqlite3, pandas as pd
con = sqlite3.connect('blablacar_data.db')
df = pd.read_sql('SELECT * FROM rides ORDER BY travel_date, from_city, departure', con)
df.to_csv('blablacar_7day_report.csv', index=False)
print(f'Exported {len(df)} rides to blablacar_7day_report.csv')
con.close()
"
