#!/usr/bin/python3
#
#  Copyright (C) 2015-2023 Sustainable Energy Now Inc., Angus King
#
#  wascenebase.py - This file is part of SIREN.
# It contains the UI independent logic
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
from abc import ABC, abstractmethod
import datetime
from math import sin, cos, pi, sqrt, degrees, radians, asin, atan2
import os

try:
    import mpl_toolkits.basemap.pyproj as pyproj   # Import the pyproj module
except:
    import pyproj
from siren_web.siren.utilities.senutils import WorkBook
from siren_web.siren.powermatch.logic.station import Station
from siren_web.siren.powermatch.logic.stationsbase import StationsBase as Stations

class WASceneBase(ABC):

    def get_config_file(self) -> str:
        pass
    
    def get_config(self):
        pass

    def destinationxy(self, lon1, lat1, bearing, distance):
        """
        Given a start point, initial bearing, and distance, calculate
        the destination point and final bearing travelling along a
        (shortest distance) great circle arc
        """
        radius = 6367.   # km is the radius of the Earth
     # convert decimal degrees to radians
        ln1, lt1, baring = list(map(radians, [lon1, lat1, bearing]))
     # "reverse" haversine formula
        lat2 = asin(sin(lt1) * cos(distance / radius) +
                                cos(lt1) * sin(distance / radius) * cos(baring))
        lon2 = ln1 + atan2(sin(baring) * sin(distance / radius) * cos(lt1),
                                            cos(distance / radius) - sin(lt1) * sin(lat2))
        return degrees(lon2), degrees(lat2)

    def __init__(self):
        self.get_config()

    def _setupCoordTransform(self):
        self._proj = pyproj.Proj(self.projection)   # LatLon with WGS84 datum used by GPS units and Google Earth
        x1, y1, lon1, lat1 = self.upper_left
        x2, y2, lon2, lat2 = self.lower_right
        ul = self._proj(lon1, lat1)
        lr = self._proj(lon2, lat2)
        self._lat_scale = y2 / (lr[1] - ul[1])
        self._lon_scale = x2 / (lr[0] - ul[0])
        self._orig_lat = ul[1]
        self._orig_lon = ul[0]

    def _setupCoordGrid(self):
        pass

    def _setupTowns(self):
        pass

    def _setupStations(self):
        pass

    def _setupScenario(self, scenario):
        i = scenario.rfind('/')
        if i > 0:
            scen_file = scenario
            scen_filter = scenario[i + 1:]
        else:
            scen_file = self.scenarios + scenario
            scen_filter = scenario
        if os.path.exists(scen_file):
            description = ''
            var = {}
            workbook = WorkBook()
            workbook.open_workbook(scen_file)
            worksheet = workbook.sheet_by_index(0)
            num_rows = worksheet.nrows - 1
            num_cols = worksheet.ncols - 1
            if worksheet.cell_value(0, 0) == 'Description:' or worksheet.cell_value(0, 0) == 'Comment:':
                curr_row = 1
                description = worksheet.cell_value(0, 1)
            else:
                curr_row = 0
#           get column names
            curr_col = -1
            while curr_col < num_cols:
                curr_col += 1
                var[worksheet.cell_value(curr_row, curr_col)] = curr_col
            while curr_row < num_rows:
                curr_row += 1
                try:
                    new_st = Station(str(worksheet.cell_value(curr_row, var['Station Name'])),
                                     str(worksheet.cell_value(curr_row, var['Technology'])),
                                     worksheet.cell_value(curr_row, var['Latitude']),
                                     worksheet.cell_value(curr_row, var['Longitude']),
                                     worksheet.cell_value(curr_row, var['Maximum Capacity (MW)']),
                                     str(worksheet.cell_value(curr_row, var['Turbine'])),
                                     worksheet.cell_value(curr_row, var['Rotor Diam']),
                                     worksheet.cell_value(curr_row, var['No. turbines']),
                                     worksheet.cell_value(curr_row, var['Area']),
                                     scen_filter)
                    name_ok = False
                    new_name = new_st.name
                    ctr = 0
                    while not name_ok:
                        for i in range(len(self._stations.stations)):
                            if self._stations.stations[i].name == new_name:
                                ctr += 1
                                new_name = new_st.name + ' ' + str(ctr)
                                break
                        else:
                            name_ok = True
                    if new_name != new_st.name:
                        new_st.name = new_name
                    if new_st.area == 0 or new_st.area == '':
                        if new_st.technology == 'Wind':
                            new_st.area = self.areas[new_st.technology] * float(new_st.no_turbines) * \
                                          pow((new_st.rotor * .001), 2)
                        else:
                            new_st.area = self.areas[new_st.technology] * float(new_st.capacity)
                    try:
                        hub_height = worksheet.cell_value(curr_row, var['Hub Height'])
                        if hub_height != '':
                            setattr(new_st, 'hub_height', hub_height)
                    except:
                        pass
                    try:
                        power_file = worksheet.cell_value(curr_row, var['Power File'])
                        if power_file != '':
                            new_st.power_file = power_file
                    except:
                        pass
                    try:
                        grid_line = worksheet.cell_value(curr_row, var['Grid Line'])
                        if grid_line != '':
                            new_st.grid_line = grid_line
                    except:
                        pass
                    try:
                        direction = worksheet.cell_value(curr_row, var['Direction'])
                        if direction != '':
                            new_st.direction = direction
                    except:
                        pass
                    try:
                        tilt = worksheet.cell_value(curr_row, var['Tilt'])
                        if tilt != '':
                            setattr(new_st, 'tilt', tilt)
                    except:
                        pass
                    try:
                        storage_hours = worksheet.cell_value(curr_row, var['Storage Hours'])
                        if storage_hours != '':
                            setattr(new_st, 'storage_hours', storage_hours)
                    except:
                        pass
                    self._stations.stations.append(new_st)
                    self.addStation(self._stations.stations[-1])
                except Exception as error:
                    print(error)
                    pass
            self._scenarios.append([scen_filter, False, description])

    def _setupGrid(self):
        pass

    def addStation(self, st):
        pass

    def addGeneration(self, st):
        pass

    def addLine(self, st):
        pass

    def refreshGrid(self):
        pass

    def changeDate(self, d):
        return
        d = datetime.date(d.year(), d.month(), d.day())
        for st in list(self._stations.values()):
            st.changeDate(d)
        self._power_tot.changeDate(d)

    def mapToLonLat(self, p, decpts=4):
        pass

    def mapFromLonLat(self, p):
        pass

    def positions(self):
        try:
            return self._positions
        except:
            return

    def stationPositions(self):
        return self._station_positions

    def toggleTotal(self, start):
        if self._power_tot.infoVisible():
            self._power_tot.hideInfo()
        else:
            self._power_tot.showInfo(0, start)

    def powerPlotImage(self, name):
        pass