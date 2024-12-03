#!/usr/bin/python3
#
#  Copyright (C) 2015-2023 Sustainable Energy Now Inc., Angus King
#
#  wascene.py - This file is part of SIREN.
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

import datetime
from math import sin, cos, pi, sqrt, degrees, radians, asin, atan2
import os
import sys
from .station import Station, Stations
print(sys.path)

class WAScene():

    def get_config(self):
        self.base_year = '2012'
        self.existing = True
        self.areas = {}
        self.show_generation = False
        self.show_capacity = False
        self.show_capacity_fill = False
        self.capacity_opacity = 1.
        self.show_fossil = False
        self.show_station_name = True
        self.show_legend = False
        self.show_ruler = False
        self.ruler = 100.
        self.ruler_ticks = 10.
        self.zone_opacity = 0.
        self.cost_existing = False
        self.trace_existing = False
        self.hide_map = False
        self.show_coord = False
        self.coord_grid = [0, 0, 'c']
        self.load_centre = None
        self.station_square = False
        self.station_opacity = 1.
        self.dispatchable = None
        self.line_loss = 0.
        self.line_width = 0
        self.cst_tshours = 0

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

    def __init__(self, facilities):
        self.get_config()
        self.last_locn = None
        self._scenarios = []
        self.facilities = facilities
        self._setupStations()
        self._plot_cache = {}

    def _setupStations(self):
        self._stations = []
        self._stationGroups = {}
        self._stationLabels = []
        self._stationCircles = {}
        if self.existing:
            self._stations = Stations(self.facilities)
            for st in self._stations.stations:
                self.addStation(st)
            self._scenarios.append(['Existing', False, 'Existing stations'])
        else:
            self._stations = Stations(self.facilities)

    def _setupScenario(self, scenario):
        i = scenario.rfind('/')
        if i > 0:
            scen_file = scenario
            scen_filter = scenario[i + 1:]
        else:
            scen_file = self.scenarios + scenario
            scen_filter = scenario

    def addStation(self, st):
        self._stationGroups[st.name] = []
        try:
            if len(self.linesz.lines) > 0:
                st.zone = self.linesz.getZone(st.lat, st.lon)
        except:
            pass
        size = -1
        return
