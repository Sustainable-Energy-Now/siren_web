#!/usr/bin/python3
#
#  Copyright (C) 2015-2024 Sustainable Energy Now Inc., Angus King
#
#  powermap.py - This file is part of SIREN
#  (formerly named sirenm.py).
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

import sys
from functools import partial

from powermodel import PowerModel
from senutils import getParents, getUser, ssCol, techClean
from getmodels import getModelFile
from grid import dust

def p2str(p):
    return '(%.4f,%.4f)' % (p.y(), p.x())

def find_shortest(coords1, coords2):
#               dist,  lat, lon, itm, prev_item
    shortest = [99999, -1., -1., -1, -1]
    for i in range(len(coords2) - 1):
        dist = dust(coords1[0], coords1[1],
               coords2[i][0], coords2[i][1], coords2[i + 1][0], coords2[i + 1][1])
        if dist[0] >= 0 and dist[0] < shortest[0]:
            ls = shortest[-2]
            shortest = dist[:]
            shortest.append(i)
            shortest.append(ls)
    return shortest


    def delStation(self, st):  # remove stations graphic items
        for itm in self.scene()._stationGroups[st.name]:
            self.scene().removeItem(itm)
        del self.scene()._stationGroups[st.name]
        for i in range(len(self.scene().lines.lines) - 1, -1, -1):
            if self.scene().lines.lines[i].name == st.name:
                del self.scene().lines.lines[i]

    def clear_Trace(self):
        try:
            for i in range(len(self.trace_items)):
                self.scene().removeItem(self.trace_items[i])
            del self.trace_items
        except:
            pass

def main():
    def get_Power():
        power = PowerModel(self.view.scene()._stations.stations)
        generated = power.getValues()
        if generated is None:
            comment = 'Power plot aborted'
        else:
            for stn in generated:
                station = self.view.scene()._stations.Get_Station(stn.name)
                station.generation = stn.generation
                self.view.scene().addGeneration(station)
            comment = 'Power plot completed'
            pct = power.getPct()
            if pct is not None:
                comment += ' (generation meets ' + pct[2:]
        del power
    sys.exit()

if '__main__' == __name__:
    main()