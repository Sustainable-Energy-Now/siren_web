# technologies.py
from datetime import datetime
from io import BytesIO
import pandas as pd
from PIL import Image
from pymysql.err import OperationalError
import requests
import streamlit as st
from sqlalchemy.sql import text

# Initialize connection.
@st.cache_resource
def init_connection():
    try:
        # connect using the connections.mysql parameters from the secrets.toml file
        conn = st.connection('mysql', type='sql', autocommit=True, ttl=60)
    except OperationalError as e:
        st.write("Error connecting to database: {e}")
        exit(1)
    return conn

# Function to fetch data from the database
def fetch_data(load_year):
# Fetching data from the MySQL database
    conn = init_connection()
    technologies_df = \
        conn.query(
            f""" 
            WITH cte AS (
            SELECT t.*, 
            s.capacity_max, s.capacity_min, s.discharge_loss,
            s.discharge_max, s.parasitic_loss, s.rampdown_max,
            s.rampup_max, s.recharge_loss, s.recharge_max,
            g.capacity, g.emissions,
            g.initial,
            g.mult,
            g.fuel,
            ROW_NUMBER() OVER (PARTITION BY t.technology_name ORDER BY t.year DESC) AS row_num
            FROM senas316_pmdata.Technologies t
            LEFT JOIN senas316_pmdata.StorageAttributes s ON t.idTechnologies = s.idTechnologies 
                AND t.category = 'Storage' AND t.year = s.year
            LEFT JOIN senas316_pmdata.GeneratorAttributes g ON t.idTechnologies = g.idTechnologies 
                AND t.category = 'Generator' AND t.year = g.year
            WHERE t.year IN (0, {load_year})
            )
            SELECT *
            FROM cte
            WHERE row_num = 1;
            """, ttl=60)
    return technologies_df

def run_technologies(request):
    # Path to the SEN logo PNG file
    # Streamlit app
    st.set_page_config(
        page_title="Generation and Storage Technologies",
        page_icon="sen_icon32.ico",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    st.markdown(
        """
        These are the technologies that are relevent to modelling the decarbonisation of the SWIS.
        """
    )
    # Fetch data from the database and create DataFrame
    load_year=st.selectbox('**Load Year**',('0', '2022'), index = 1)
    data = fetch_data(load_year)
    # Allow user to select a technolgy to display
    technology_names = data['technology_name'].unique()
    st.subheader(f"**Select a technology:**")
    selected_technology = st.selectbox("Select a technology:", technology_names, label_visibility = "hidden")

    # Filter data for selected coluumns
    technology_details = data[data['technology_name'] == selected_technology].iloc[0]
    attribute_explain = {
        'capacity': 'The maxiumum storage capacity in mWhs.',
        'capacity_max':'The maximum capacity of the technology.',
        'capacity_min':'The minimum capacity of the technology.',
        'category':'The role it plays in the grid.',
        'capex':'The initial capital expenditure for the technology.',
        'discharge_loss':'The percentage capacity that is lost in discharging.',
        'discharge_max':'The maxiumum percentage of storage capacity that can be discharged.',
        'discount_rate':'The discount rate applied to the technology.',
        'dispatchable':'The technology can be dispatched at any time when required.',
        'emissions':'CO2 emmissions in kg/mWh',
        'fuel': 'The type of fuel consumed by the technology.',
        'FOM':'The fixed operating cost of the technology.',
        'initial': 'The initial value.',
        'lifetime':'The operational lifetime of the technology.',
        'mult':'The capacity multiplier.',
        'merit_order':'The merit order in which the technology is dispatched to meet load.',
        'parasitic_loss':'The percentage of storage capacity lost other than by charging or discharging.',
        'rampdown_max':'The maximum rampdown rate of the technology.',
        'rampup_max':'The maximum rampup rate of the technology.',
        'recharge_loss':'The percentage capacity that is lost in recharging.',
        'recharge_max':'The maximum recharge rate of the technology.',
        'renewable':'Whether the technology can be renewed.',
        'row_num':'sort field.',
        'VOM':'The variable operating cost of the technology.',
        'year':'The year of reference.',
        }
    exclude_attributes = [
        'caption', 'description', 'dispatchable', 'idGeneratorAttributes', 'image', 'renewable', 'idStorageAttributes', 'technology_name', 'idTechnologies',
        ]
    if not technology_details.empty:
        # Display technology details
        st.subheader(f"{technology_details.technology_name}")
        if technology_details.image:
            image_url = 'https://sen.asn.au/wp-content/uploads/' + technology_details.image
            image = Image.open(BytesIO(requests.get(image_url).content))
            st.image(image, caption=technology_details.caption, use_column_width=False)
        else:
            st.warning("No image available for this technology.")
        st.write(f"**Description:** {technology_details.description}")
        col1, col2= st.columns([1, 4])
        for column, value in technology_details.items():
            if (pd.notna(value)):
                with col1:
                    # Replace break characters with spaces
                    collabel = column.replace('_', ' ').title()
                    if column not in exclude_attributes:
                        st.write(f"**{collabel}**: {value}")
                    if (column == 'renewable' or column == 'dispatchable'):
                        st.write(f"**{collabel}**: {bool(value)}")
                with col2:
                    if (column not in exclude_attributes) or (column == 'renewable' or column == 'dispatchable'):
                        st.markdown(f'<p style="color:blue;">{attribute_explain[column]}</p>', unsafe_allow_html=True)
    else:
        st.warning("Selected technology not found in the database.")
        
if __name__ == "__main__":
    run_technologies()
