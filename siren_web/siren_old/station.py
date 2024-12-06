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
from math import radians, cos, sin, asin, sqrt, pow

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

class Station:
    def __init__(self, name, technology, lat, lon, capacity, turbine, rotor, no_turbines, area, scenario,
                 direction=None, grid_line=None, hub_height=None, power_file=None, storage_hours=None, tilt=None, # extra file fields
                 generation=None, grid_len=None, grid_path_len=None, zone=None):
        self.name = name
        self.technology = technology
        self.lat = lat
        self.lon = lon
        self.capacity = capacity
        self.turbine = turbine
        self.rotor = rotor
        if hub_height is not None:
            try:
                self.hub_height = float(hub_height)
            except:
                pass
        self.no_turbines = no_turbines
        if area is None:
            self.area = 0
        else:
            self.area = area
        self.scenario = scenario
        self.generation = generation
        self.power_file = power_file
        self.grid_line = grid_line
        self.grid_len = grid_len
        self.grid_path_len = grid_path_len
        self.direction = direction
        self.storage_hours = storage_hours
        if tilt is not None:
            try:
                self.tilt = float(tilt)
            except:
                pass

        self.zone = zone

class Stations:
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
        self.sam_file = 'siren_web/static/siren_data/plant_data/Wind Turbines.csv'
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

    def Nearest(self, lat, lon, distance=False, fossil=False, ignore=None):
        hdr = ''
        distnce = 999999
        for station in self.stations:
            if station.technology[:6] == 'Fossil' and not fossil:
                continue
            dist = self.haversine(lat, lon, station.lat, station.lon)
            if dist < distnce:
                if ignore is not None and ignore == station.name:
                    continue
                hdr = station.name
                distnce = dist
        for station in self.stations:
            if station.name == hdr:
                if distance:
                    return station, distnce
                else:
                    return station
        return None

    def Stn_Location(self, name):
        for station in self.stations:
            if station.name == name:
                return str(station.lat) + ' ' + str(station.lon)
        return ''

    def Stn_Turbine(self, name):
        for station in self.stations:
            if station.name == name:
                return station.turbine
        return ''

    def Get_Station(self, name):
        for station in self.stations:
            if station.name == name:
                return station
        return None

    def Description(self):
        return self.description
