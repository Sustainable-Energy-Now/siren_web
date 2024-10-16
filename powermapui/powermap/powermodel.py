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

from copy import copy
from math import asin, ceil, cos, fabs, floor, log10, pow, radians, sin, sqrt

import matplotlib

from matplotlib.font_manager import FontProperties
import matplotlib.pyplot as plt
import numpy as np
import openpyxl as oxl
import os
import sys
import ssc
import time
import xlwt

import configparser  # decode .ini file

from senutils import getParents, getUser, ssCol, techClean
from getmodels import getModelFile
from grid import Grid
from powerclasses import *
from superpower import SuperPower
from sirenicons import Icons
from turbine import Turbine
from zoompan import ZoomPanX

the_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]


class PowerModel():
#       __init__ for PowerModel
    def __init__(self, stations, year=None):
        self.something.power_signal = self
        self.stations = stations
        self.data_file = ''
        self.technologies = ''
        self.load_growth = 0.
        self.storage = [0., 0.]
        self.recharge = [0., 1.]
        self.discharge = [0., 1.]
        self.selected = None
#
#       collect the data (once only)
#
        self.stn_outs = []
        self.model = SuperPower(stations, self.plots, False, year=self.base_year,
                                selected=self.selected)
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
        elif self.plots['by_station']:
            if len(self.ly) == 1:
                self.suffix = ' - ' + list(self.ly.keys())[0]
            else:
                self.suffix = ' - Chosen Stations'
        if self.plots['save_zone']:
            self.stn_zone = self.model.getStnZones()
        if self.plots['save_data']:
            stnsh = {}
            # if load
            if self.plots['show_load']:
                stnsh['Load'] = self.load_data[:]
            for i in range(len(self.stn_outs)):
                stnsh[self.stn_outs[i]] = self.stn_pows[i][:]
            self.save_detail(data_file, stnsh)
            del stnsh
        if self.plots['summary']:
            fields = ['name', 'technology', 'capacity', 'cf', 'generation']
            sumfields = ['capacity', 'generation']
            decpts = [0, 0, 1, 1, 2, 0, 1]
            if getattr(self.power_summary[0], 'transmitted') != None:
                fields.append('transmitted')
                sumfields.append('transmitted')
                decpts.append([0, 1])
            if self.plots['save_zone']:
                fields.insert(1, 'zone')
                decpts.insert(1, 0)
            dialog = displaytable.Table(self.power_summary, sumfields=sumfields,
                     units='capacity=MW generation=MWh transmitted=MWh', sumby='technology',
                     decpts=decpts, fields=fields, save_folder=self.scenarios)
            dialog.exec_()
            del dialog
        if self.plots['financials']:
            do_financials = True
        else:
            do_financials = False
        if self.plots['save_data'] or self.plots['summary']:
            show_summ = True
        else:
            show_summ = False
        do_plots = True
#
#       loop around processing plots
#
        if do_plots:
            if matplotlib.__version__ <= '3.5.1':
                if matplotlib.get_backend() != 'TkAgg':
                    plt.switch_backend('TkAgg')
            self.gen_pct = None
            self.load_data = None
            self.load_key = ''
            self.adjustby = None
            while True:
                wrkly = {}
                summs = {}
                if self.load_key != '':
                    try:
                        del wrkly[self.load_key]
                    except:
                        pass
                    self.load_key = ''
                if (self.plots['show_load'] or self.plots['save_match'] or self.plots['shortfall'] \
                    or self.plots['shortfall_detail']) and self.can_do_load:
                    other_load_year = False
                    if self.load_year != self.base_year and self.load_growth == 0: # see if other load file
                        load_file = self.load_file.replace(self.base_year, self.load_year)
                        if os.path.exists(load_file):
                            self.load_file = load_file
                            other_load_year = True
                            self.load_data = None
                    if self.load_data is None:
                        tf = open(self.load_file, 'r')
                        lines = tf.readlines()
                        tf.close()
                        self.load_data = []
                        bit = lines[0].rstrip().split(',')
                        if len(bit) > 0: # multiple columns
                            for b in range(len(bit)):
                                if bit[b][:4].lower() == 'load':
                                    if bit[b].lower().find('kwh') > 0: # kWh not MWh
                                        for i in range(1, len(lines)):
                                            bit = lines[i].rstrip().split(',')
                                            self.load_data.append(float(bit[b]) * 0.001)
                                    else:
                                        for i in range(1, len(lines)):
                                            bit = lines[i].rstrip().split(',')
                                            self.load_data.append(float(bit[b]))
                        else:
                            for i in range(1, len(lines)):
                                self.load_data.append(float(lines[i].rstrip()))
                    if self.load_multiplier != 0 or other_load_year:
                        key = 'Load ' + self.load_year
                    else:
                        key = 'Load'  # lines[0].rstrip()
                    self.load_key = key
                    wrkly[key] = []
                    if self.load_multiplier != 0:
                        for i in range(len(self.load_data)):
                            wrkly[key].append(self.load_data[i] * (1 + self.load_multiplier))
                    else:
                        wrkly[key] = self.load_data[:]
                else:
                    self.plots['show_pct'] = False
                if self.plots['adjust']:
                    if self.load_key == '':
                        if self.adjustby is None:
                            adjust = Adjustments(list(self.ly.keys()))
                        else:
                            adjust = Adjustments(self.adjustby)
                    else:
                        if self.adjustby is None:
                            adjust = Adjustments(list(self.ly.keys()), self.load_key, wrkly[self.load_key], self.ly,
                                                 self.load_year)
                        else:
                            adjust = Adjustments(self.adjustby, self.load_key, wrkly[self.load_key], self.ly, self.load_year)
                    adjust.exec_()
                    self.adjustby = adjust.getValues()
                else:
                    self.adjustby = None
                for key in self.ly:
                    if self.adjustby is None:
                        wrkly[key] = self.ly[key][:]
                    else:
                        wrkly[key] = []
                        if key == 'Generation':
                            for i in range(len(self.ly[key])):
                                wrkly[key].append(self.ly[key][i])
                        else:
                            for i in range(len(self.ly[key])):
                                wrkly[key].append(self.ly[key][i] * self.adjustby[key])
                if self.plots['shortfall'] or self.plots['shortfall_detail'] or self.plots['save_match']:
                    self.plots['show_load'] = True
                    self.plots['cumulative'] = True
                try:
                    del wrkly['Storage']
                except:
                    pass
                if self.load_data is None:
                    self.do_load = False
                else:
                    self.do_load = True
                if self.plots['show_load']:
                    total_gen = []
                    for i in range(len(self.x)):
                        total_gen.append(0.)
                    for key, value in wrkly.items():
                        if key == 'Generation':
                            continue
                        if key == 'Storage' or key == 'Excess':
                            continue
                        elif key[:4] == 'Load':
                            pass
                        else:
                            for i in range(len(value)):
                                total_gen[i] += value[i]
                    if self.storage[0] > 0:
                        wrkly['Storage'] = []
                        wrkly['Excess'] = []
                        for i in range(len(self.x)):
                            wrkly['Storage'].append(0.)
                            wrkly['Excess'].append(0.)
                        storage_cap = self.storage[0] * 1000.
                        if self.storage[1] > self.storage[0]:
                            storage_carry = self.storage[0] * 1000.
                        else:
                            storage_carry = self.storage[1] * 1000.
                        storage_bal = []
                        storage_losses = []
                        for i in range(len(self.x)):
                            gap = gape = total_gen[i] - wrkly[self.load_key][i]
                            storage_loss = 0.
                            if gap >= 0:  # excess generation
                                if self.recharge[0] > 0 and gap > self.recharge[0]:
                                    gap = self.recharge[0]
                                if storage_carry >= storage_cap:
                                    wrkly['Excess'][i] = gape
                                else:
                                    if storage_carry + gap > storage_cap:
                                        gap = (storage_cap - storage_carry) * (1 / self.recharge[1])
                                    storage_loss = gap - gap * self.recharge[1]
                                    storage_carry += gap - storage_loss
                                    if gape - gap > 0:
                                        wrkly['Excess'][i] = gape - gap
                                    if storage_carry > storage_cap:
                                        storage_carry = storage_cap
                            else:
                                if self.discharge[0] > 0 and -gap > self.discharge[0]:
                                    gap = -self.discharge[0]
                                if storage_carry > -gap / self.discharge[1]:  # extra storage
                                    wrkly['Storage'][i] = -gap
                                    storage_loss = gap * self.discharge[1] - gap
                                    storage_carry += gap - storage_loss
                                else:  # not enough storage
                                    if self.discharge[0] > 0 and storage_carry > self.discharge[0]:
                                        storage_carry = self.discharge[0]
                                    wrkly['Storage'][i] = storage_carry * (1 / (2 - self.discharge[1]))
                                    storage_loss = storage_carry - wrkly['Storage'][i]
                                    storage_carry = 0 # ???? bug ???
                            storage_bal.append(storage_carry)
                            storage_losses.append(storage_loss)
                        if self.plots['shortfall_detail']:
                            shortstuff = []
                            for i in range(len(self.x)):
                                shortfall = total_gen[i] + wrkly['Storage'][i] - wrkly[self.load_key][i]
                                if shortfall > 0:
                                    shortfall = 0
                                shortstuff.append(ColumnData(i + 1, the_date(self.load_year, i),
                                                  [wrkly[self.load_key][i], total_gen[i],
                                                  wrkly['Storage'][i], storage_losses[i],
                                                  storage_bal[i], shortfall, wrkly['Excess'][i]],
                                                  values=['load', 'generation', 'storage_used',
                                                          'storage_loss', 'storage_balance',
                                                          'shortfall', 'excess']))
                            dialog = displaytable.Table(shortstuff, title='Storage',
                                                        save_folder=self.scenarios,
                                                        fields=['hour', 'period', 'load', 'generation',
                                                                'storage_used', 'storage_loss',
                                                                'storage_balance', 'shortfall', 'excess'])
                            dialog.exec_()
                            del dialog
                            del shortstuff
                        if show_summ:
                            summs['Shortfall'] = ['', '', 0., 0]
                            summs['Excess'] = ['', '', 0., 0]
                            for i in range(len(self.x)):
                                if total_gen[i] > wrkly[self.load_key][i]:
                                    summs['Excess'][2] += total_gen[i] - wrkly[self.load_key][i]
                                else:
                                    summs['Shortfall'][2] += total_gen[i]  - wrkly[self.load_key][i]
                            summs['Shortfall'][2] = round(summs['Shortfall'][2], 1)
                            summs['Excess'][2] = round(summs['Excess'][2], 1)
                    elif show_summ or self.plots['shortfall_detail']:
                        if self.plots['shortfall_detail']:
                            shortstuff = []
                            for i in range(len(self.x)):
                                if total_gen[i] > wrkly[self.load_key][i]:
                                    excess = total_gen[i] - wrkly[self.load_key][i]
                                    shortfall = 0
                                else:
                                    shortfall = total_gen[i]  - wrkly[self.load_key][i]
                                    excess = 0
                                shortstuff.append(ColumnData(i + 1, the_date(self.load_year, i),
                                                  [wrkly[self.load_key][i], total_gen[i],
                                                   shortfall, excess],
                                                  values=['load', 'generation',
                                                          'shortfall', 'excess']))
                            dialog = displaytable.Table(shortstuff, title='Hourly Shortfall',
                                                        save_folder=self.scenarios,
                                                        fields=['hour', 'period', 'load', 'generation',
                                                                'shortfall', 'excess'])
                            dialog.exec_()
                            del dialog
                            del shortstuff
                        else:
                            summs['Shortfall'] = ['', '', 0., 0]
                            summs['Excess'] = ['', '', 0., 0]
                            for i in range(len(self.x)):
                                if total_gen[i] > wrkly[self.load_key][i]:
                                    summs['Excess'][2] += total_gen[i] - wrkly[self.load_key][i]
                                else:
                                    summs['Shortfall'][2] += total_gen[i] - wrkly[self.load_key][i]
                            summs['Shortfall'][2] = round(summs['Shortfall'][2], 1)
                            summs['Excess'][2] = round(summs['Excess'][2], 1)
                if show_summ and self.adjustby is not None:
                    keys = []
                    for key in wrkly:
                        keys.append(key)
                        gen = 0.
                        for i in range(len(wrkly[key])):
                            gen += wrkly[key][i]
                        if key[:4] == 'Load':
                            incr = 1 + self.load_multiplier
                        else:
                            try:
                                incr = self.adjustby[key]
                            except:
                                incr = ''
                        try:
                            summs[key] = [0., round(incr, 2), round(gen, 1), 0]
                            if key[:4] == 'Load':
                                summs[key][0] = ''
                        except:
                            summs[key] = ['', '', round(gen, 1), 0]
                    keys.sort()
                    xtra = ['Generation', 'Load', 'Gen. - Load', 'Storage Capacity', 'Storage', 'Shortfall', 'Excess']
                    o = 0
                    gen = 0.
                    if self.storage[0] > 0:
                        summs['Storage Capacity'] = [self.storage[0] * 1000., '', '', 0]
                    for i in range(len(keys)):
                        if keys[i][:4] == 'Load':
                            xtra[1] = keys[i]
                        elif keys[i] in xtra:
                            continue
                        else:
                            o += 1
                            summs[keys[i]][3] = o
                            gen += summs[keys[i]][2]
                    if xtra[0] not in list(summs.keys()):
                        summs[xtra[0]] = ['', '', gen, 0]
                    if xtra[1] in list(summs.keys()):
                        summs[xtra[2]] = ['', '', round(gen - summs[xtra[1]][2], 1), 0]
                    for i in range(len(xtra)):
                        if xtra[i] in list(summs.keys()):
                            o += 1
                            summs[xtra[i]][3] = o
                    try:
                        summs['Storage Used'] = summs.pop('Storage')
                    except:
                        pass
                    try:
                        summs['Excess Gen.'] = summs.pop('Excess')
                    except:
                        pass
                    for it in self.power_summary:
                        if self.plots['by_station']:
                            try:
                                summs[it.name][0] = it.capacity
                            except:
                                pass
                        else:
                            try:
                                summs[it.technology][0] += it.capacity
                            except:
                                pass
                    for key, value in summs.items():
                        try:
                            value[0] = round(value[0], 2)
                        except:
                            pass
                    dialog = displaytable.Table(summs, title='Generation Summary',
                                                save_folder=self.scenarios,
                                                fields=['component', 'capacity', 'multiplier', 'generation', 'row'],
                                                units='generation=MWh', sortby='row')
                    dialog.exec_()
                    del dialog
                if self.plots['save_detail'] or self.plots['save_tech']:
                    dos = []
                    if self.plots['save_detail']:
                        dos.append('')
                    if self.plots['save_tech']:
                        dos.append('Technology_')
                    for l in range(len(dos)):
                        keys = []
                        keys2 = []
                        if dos[l] != '':
                            techs = {}
                            for key, value in iter(wrkly.items()):
                                try:
                                    i = self.stn_outs.index(key)
                                    if self.stn_tech[i] in list(techs.keys()):
                                        for j in range(len(value)):
                                            techs[self.stn_tech[i]][j] += value[j]
                                    else:
                                        techs[self.stn_tech[i]] = value[:]
                                        keys.append(self.stn_tech[i])
                                except:
                                    techs[key] = value[:]
                                    keys2.append(key)
                            keys.sort()
                            keys2.extend(keys) # put Load first
                            self.save_detail(data_file, techs, keys=keys2)
                            del techs
                        else:
                            for key in list(wrkly.keys()):
                                try:
                                    i = self.stn_outs.index(key)
                                    keys.append(self.stn_outs[i])
                                except:
                                    keys2.append(key)
                            keys.sort()
                            keys2.extend(keys) # put Load first
                            self.save_detail(data_file, wrkly, keys=keys2)
                self.showGraphs(wrkly, self.x)
                if __name__ == '__main__':
                    self.show_menu = True
                    self.plots['save_data'] = True
#
#       loop around doing financials
#
         # run the financials model
        if do_financials:
            self.financial_parms = None
            while True:
                self.financials = FinancialModel(self.stn_outs, self.stn_tech, self.stn_size,
                                  self.stn_pows, self.stn_grid, self.stn_path, year=self.base_year,
                                  parms=self.financial_parms)
                if self.financials.stations is None:
                    break
                self.financial_parms = self.financials.getParms()
                fin_fields = ['name', 'technology', 'capacity', 'generation', 'cf',
                              'capital_cost', 'lcoe_real', 'lcoe_nominal', 'npv']
                fin_sumfields = ['capacity', 'generation', 'capital_cost', 'npv']
                fin_units = 'capacity=MW generation=MWh capital_cost=$ lcoe_real=c/kWh' + \
                            ' lcoe_nominal=c/kWh npv=$'
                tot_capital = 0.
                tot_capacity = 0.
                tot_generation = 0.
                tot_lcoe_real = [0., 0.]
                tot_lcoe_nom = [0., 0.]
                for stn in self.financials.stations:
                    tot_capital += stn.capital_cost
                    tot_capacity += stn.capacity
                    tot_generation += stn.generation
                for stn in self.financials.stations:
                    tot_lcoe_real[0] += stn.lcoe_real * (stn.generation / tot_generation)
                    tot_lcoe_nom[0] += stn.lcoe_nominal * (stn.generation / tot_generation)
                    tot_lcoe_real[1] += stn.lcoe_real * (stn.capacity / tot_capacity)
                    tot_lcoe_nom[1] += stn.lcoe_nominal * (stn.capacity / tot_capacity)
                    if stn.grid_cost > 0:
                        i = fin_fields.index('capital_cost')
                        fin_fields.insert(i + 1, 'grid_cost')
                        fin_sumfields.append('grid_cost')
                        fin_units += ' grid_cost=$'
                        break
                tot_fields = [['cf', tot_generation / tot_capacity / 8760],
                              ['lcoe_real', tot_lcoe_real[0]],
                              ['lcoe_nominal', tot_lcoe_nom[0]]]
                dialog = displaytable.Table(self.financials.stations, fields=fin_fields,
                         sumfields=fin_sumfields, units=fin_units, sumby='technology',
                         save_folder=self.scenarios, title='Financials', totfields=tot_fields)
                dialog.exec_()
                del dialog
        self.something.power_signal = None

    def getValues(self):
        try:
            return self.power_summary
        except:
            return None

    def getPct(self):
        return self.gen_pct

    def exit(self):
        self.something.power_signal = None
        return #exit()
