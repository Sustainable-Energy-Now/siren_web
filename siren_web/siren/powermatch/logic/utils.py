import os

def get_filename(base_path, relative_path):
    return os.path.join(base_path, relative_path)

TECH_NAMES = ['Load', 'Onshore Wind', 'Offshore Wind', 'Rooftop PV', 'Fixed PV']
