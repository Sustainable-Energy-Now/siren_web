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
