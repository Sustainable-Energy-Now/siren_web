#!/usr/bin/python3
#
#  Copyright (C) 2015-2023 Sustainable Energy Now Inc., Angus King
#
#  station.py - This file is part of SIREN.
#
#  SIREN is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as
#  published by the Free Software Foundation, either version 3 of
#  the License, or (at your option) any later version.
#
#  SIREN is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General
#  Public License along with SIREN.  If not, see
#  <http://www.gnu.org/licenses/>.
#

import csv
import os
import sys
from math import radians, cos, sin, asin, sqrt, pow
from siren_web.siren.powermatch.logic.stationsbase import StationsBase
from siren_web.siren.powermatch.logic.station import Station
from siren_web.siren.utilities.senutils import techClean

def within_map(y, x, poly):
    n = len(poly)
    inside = False
    p1y, p1x = poly[0]
    for i in range(n + 1):
        p2y, p2x = poly[i % n]
        if x > min(p1x, p2x):
            if x <= max(p1x, p2x):
                if y <= max(p1y, p2y):
                    if p1x != p2x:
                        yints = (x - p1x) * (p2y - p1y) / (p2x - p1x) + p1y
                    if p1y == p2y or y <= yints:
                        inside = not inside
        p1y, p1x = p2y, p2x
    return inside

class StationsWeb(StationsBase):
    def get_config(self, config):
        try:
            self.sam_file = config.get('Files', 'sam_turbines')
        except:
            self.sam_file = ''
        try:
            self.pow_dir = config.get('Files', 'pow_files')
        except:
            self.pow_dir = ''
        self.fac_files = []
        try:
            fac_file = config.get('Files', 'grid_stations')
        except:
            pass
        if self.stations2:
            try:
                fac_file = config.get('Files', 'grid_stations2')
            except:
                pass
        self.ignore_deleted = True
        try:
            if config.get('Grid', 'ignore_deleted_existing').lower() in ['false', 'off', 'no']:
                self.ignore_deleted = False
        except:
            pass
        self.technologies = ['']
        technologies = []
        self.areas = {}
        try:
            technologies = config.get('Power', 'technologies')
            for item in technologies.split():
                itm = techClean(item)
                self.technologies.append(itm)
                try:
                    self.areas[itm] = float(config.get(itm, 'area'))
                except:
                    self.areas[itm] = 0.
        except:
            pass
        self.tech_missing = []
        for tech in ['bess', 'biomass', 'fixed_pv', 'rooftop_pv', 'single_axis_pv', 'wind']:
            if tech not in technologies:
                itm = techClean(tech)
                self.tech_missing.append(itm + ' (' + tech + ')')
                self.technologies.append(itm)
                self.areas[itm] = 0.
        try:
            technologies = config.get('Power', 'fossil_technologies')
            for item in technologies.split():
                itm = techClean(item)
                try:
                    self.areas[itm] = float(config.get(itm, 'area'))
                except:
                    self.areas[itm] = 0.
        except:
            pass

    def haversine(self, lat1, lon1, lat2, lon2):
        """
        Calculate the great circle distance between two points
        on the earth (specified in decimal degrees)
        """
     # convert decimal degrees to radians
        lon1, lat1, lon2, lat2 = list(map(radians, [lon1, lat1, lon2, lat2]))

     # haversine formula
        dlon = lon2 - lon1
        dlat = lat2 - lat1
        a = sin(dlat / 2)**2 + cos(lat1) * cos(lat2) * sin(dlon / 2)**2
        c = 2 * asin(sqrt(a))

     # 6367 km is the radius of the Earth
        km = 6367 * c
        return km

    def __init__(self, facilities):
        self.stations = []
        self.sam_file = 'siren_web/siren_files/siren_data/plant_data/Wind Turbines.csv'
        self.areas = {}
        self.areas['Wind'] = 0.0
        self.areas['Onshore Wind'] = 0.0
        if os.path.exists(self.sam_file):
           sam = open(self.sam_file)
           sam_turbines = csv.DictReader(sam)
        else:
           sam = None
           sam_turbines = []
        for facility in facilities:
            bit = facility['facility_code'].split('_')
            rotor = 0.
            hub_height = 0.
            turbine = ''
            no_turbines = 0
            if 'Wind' in facility['technology_name']:
                tech = 'Wind'
                turbine = facility['turbine']
                if turbine[:7] == 'Enercon':
                    bit = turbine[9:].split(' _')
                    if len(bit) == 1:
                        rotor = bit[0].split('_')[0]
                    else:
                        bit = bit[0].split('_')
                        if len(bit) == 1:
                            rotor = bit[0]
                        else:
                            if bit[1][-1] == 'm':
                                rotor = bit[1][:-1]
                            else:
                                rotor = bit[0]
                else:
                    turb = turbine.split(';')
                    if len(turb) > 1:
                        turbine = turb[1]
                    else:
                        turbine = turb[0]
                    if sam is not None:
                        sam.seek(0)
                    for turb in sam_turbines:
                        if turb['Name'] == turbine:
                            rotor = turb['Rotor Diameter']
                            break
                    else: # try and find .pow file
                        pow_file = 'siren_web/static/siren_data/plant_data/' + turbine + '.pow'   
                        if os.path.exists(pow_file):
                            tf = open(pow_file, 'r')
                            lines = tf.readlines()
                            tf.close()
                            rotor = float(lines[1].strip('" \t\n\r'))
                            del lines
                no_turbines = int(facility['no_turbines'])
                try:
                    rotor = float(rotor)
                except:
                    pass
                area = facility['area'] * float(no_turbines) * pow((rotor * .001), 2)
                try:
                    hub_height = float(facility['Hub Height'])
                except:
                    pass
            else:
                tech = facility['technology_name']
                tech.removeprefix('Existing ').removeprefix('Proposed ')
                try:
                    area = facility['area'] * float(facility['capacity'])
                except:
                    area = 0

            nice_name = facility['facility_name']
            if nice_name == '':
                name_split = facility['facility_code'].split('_')
                if len(name_split) > 1:
                    nice_name = ''
                    for i in range(len(name_split) - 1):
                        nice_name += name_split[i].title() + '_'
                    nice_name += name_split[-1]
                else:
                    nice_name = facility['facility_code']
            stn = self.Get_Station(nice_name)
            if stn is None:   # new station?
                self.stations.append(Station(nice_name, tech,
                    float(facility['latitude']), float(facility['longitude']),
                    float(facility['capacity']), turbine, rotor, no_turbines, area, 'Existing'))
                if tech == 'Fixed PV':
                    try:
                        if facility['tilt'] != '':
                            self.stations[-1].tilt = float(facility['tilt'])
                    except:
                        pass
            else:   # additional generator in existing station
                if stn.technology != tech:
                    if stn.technology[:6] == 'Fossil' and tech[:6] == 'Fossil':
                        stn.technology = 'Fossil Mixed'
                stn.capacity = stn.capacity + float(facility['capacity'])
                stn.area += area
                stn.no_turbines = stn.no_turbines + no_turbines
            if tech == 'Wind' and hub_height > 0:
                stn.hub_height = hub_height

            self.stations.append(Station(facility['facility_name'],
                            facility['technology_name'],
                            float(facility['latitude']),
                            float(facility['longitude']),
                            float(facility['capacity']),
                            facility['turbine'],
                            rotor,
                            facility['no_turbines'],
                            float(facility['area']),
                            'Existing'))
            if 'Wind' in self.stations[-1].technology:
                if self.stations[-1].rotor == 0 or self.stations[-1].rotor == '':
                    rotor = 0
                    if self.stations[-1].turbine[:7] == 'Enercon':
                        bit = self.stations[-1].turbine[9:].split(' _')
                        if len(bit) == 1:
                            rotor = bit[0].split('_')[0]
                        else:
                            bit = bit[0].split('_')
                            if len(bit) == 1:
                                rotor = bit[0]
                            else:
                                if bit[1][-1] == 'm':
                                    rotor = bit[1][:-1]
                                else:
                                    rotor = bit[0]
                    else:
                        turb = self.stations[-1].turbine.split(';')
                        if len(turb) > 1:
                            sam.seek(0)
                            turbine = turb[1]
                            for turb in sam_turbines:
                                if turb['Name'] == turbine:
                                    rotor = turb['Rotor Diameter']
                try:
                    self.stations[-1].rotor = float(rotor)
                except:
                    pass
                try:
                    if float(facility['hub_height']) > 0:
                        self.stations[-1].hub_height = float(facility['hub_height'])
                except:
                    pass
                if self.stations[-1].area == 0 or self.stations[-1].area == '':
                    self.stations[-1].area = self.areas[self.stations[-1].technology] * \
                                                float(self.stations[-1].no_turbines) * \
                                                pow((self.stations[-1].rotor * .001), 2)
            
            try:
                if self.stations[-1].area == 0 or self.stations[-1].area == '':
                    if 'Wind' in self.stations[-1].technology:
                        self.stations[-1].area = self.areas[self.stations[-1].technology] * \
                                                    float(self.stations[-1].capacity)
                    else:
                        self.stations[-1].area = self.areas[self.stations[-1].technology] * \
                                                    float(self.stations[-1].capacity)
            except:
                self.stations[-1].area = 0.
            try:
                if facility['power_file'] != '':
                    self.stations[-1].power_file = facility['power_file']
            except:
                pass
            try:
                if facility['grid_line'] != '':
                    self.stations[-1].grid_line = facility['grid_line']
            except:
                pass
            if 'PV' in self.stations[-1].technology:
                try:
                    if facility['direction'] != '':
                        self.stations[-1].direction = facility['direction']
                except:
                    pass
                try:
                    if facility['tilt'] != '':
                        self.stations[-1].tilt = float(facility['tilt'])
                except:
                    pass
            if self.stations[-1].technology in ['CST', 'Solar Thermal']:
                try:
                    if facility['storage_hours']:
                        self.stations[-1].storage_hours = float(facility['storage_hours'])
                except:
                    pass
        if sam is not None:
            sam.close()
            