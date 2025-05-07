#!/usr/bin/python3
#
#  Copyright (C) 2015-2024 Sustainable Energy Now Inc., Angus King
#
#  powermodel.py - This file is part of SIREN.
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
from copy import copy
from math import asin, ceil, cos, fabs, floor, log10, pow, radians, sin, sqrt
from matplotlib.font_manager import FontProperties
import numpy as np
import openpyxl as oxl
import os
from siren_web.siren.powermatch.logic.powerclassesbase import *
from siren_web.siren.powermatch.logic.superpowerbase import SuperPowerBase


class PowerModelBase(ABC):
#       __init__ for PowerModel
    def __init__(self, stations, year=None, status=None, loadonly=False, progress=None):
        self.stations = stations
#
#       choose what power data to collect (once only)
        self.technologies = ''
        self.load_growth = 0.
        self.storage = [0., 0.]
        self.recharge = [0., 1.]
        self.discharge = [0., 1.]
#
#       collect the data (once only)
#
        self.stn_outs = []
        self.model = SuperPowerBase(stations, self.plots, False, year=self.base_year,
                                selected=self.selected, status=status)
        self.model.getPower()
        if len(self.model.power_summary) == 0:
            return
        self.power_summary = self.model.power_summary
        self.ly, self.x = self.model.getLy()
        self.suffix = ''
        if len(self.stations) == 1:
            self.suffix = ' - ' + self.stations[0].name
        elif len(self.stn_outs) == 1:
            self.suffix = ' - ' + self.stn_outs[0]

    def getValues(self):
        try:
            return self.power_summary
        except:
            return None

    def getPct(self):
        return self.gen_pct