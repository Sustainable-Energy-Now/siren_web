#!/usr/bin/python3
#
#  Copyright (C) 2015-2023 Sustainable Energy Now Inc., Angus King
#
#  powerclasses.py - This file is part of SIREN.
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

import numpy as np
import os
import sys
try:
    import utilities.ssc as ssc
except:
    pass

import configparser  # decode .ini file

from siren_web.siren.utilities.senutils import techClean, WorkBook
from siren_web.siren.powermap.logic.grid import Grid

the_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]

def split_array(array):
    arry = []
    varbl = array.replace('(', '[')
    varbl2 = varbl.replace(')', ']')
    varbl2 = varbl2.replace('[', '')
    varbl2 = varbl2.replace(']', '')
    if ',' in varbl2:
        bits = varbl2.split(',')
    else:
        bits = varbl2.split(';')
    if '.' in varbl:
        for bit in bits:
            if float(bit) == 0:
                try:
                    arry.append(int(bit[:bit.find('.')]))
                except:
                    arry.append(int(bit))
            else:
                arry.append(float(bit))
    else:
        for bit in bits:
            arry.append(int(bit))
    return arry

def split_matrix(matrix):
    mtrx = []
    varbl = matrix.replace('(', '[')
    varbl2 = varbl.replace(')', ']')
    varbl2 = varbl2.replace('[[', '')
    varbl2 = varbl2.replace(']]', '')
    if '],[' in varbl2:
        arrys = varbl2.split('],[')
    else:
        arrys = varbl2.split('][')
    for arr1 in arrys:
        arr2 = arr1.replace('[', '')
        arry = arr2.replace(']', '')
        mtrx.append([])
        if ',' in arry:
            bits = arry.split(',')
        else:
            bits = arry.split(';')
        if '.' in varbl:
            for bit in bits:
                if float(bit) == 0:
                    mtrx[-1].append(int(bit))
                else:
                    mtrx[-1].append(float(bit))
        else:
            for bit in bits:
                mtrx[-1].append(int(bit))
    return mtrx

def the_date(year, h):
    mm = 0
    dy, hr = divmod(h, 24)
    dy += 1
    while dy > the_days[mm]:
        dy -= the_days[mm]
        mm += 1
    return '%s-%s-%s %s:00' % (year, str(mm + 1).zfill(2), str(dy).zfill(2), str(hr).zfill(2))


class PowerSummary:
    def __init__(self, name, technology, generation, capacity, transmitted=None):
        self.name = name
        self.technology = technology
        try:
            self.generation = int(round(generation))
        except:
            self.generation = 0
        self.capacity = capacity
        try:
            self.cf = round(self.generation / (capacity * 8760), 2)
        except:
            pass
        if transmitted is not None:
            self.transmitted = int(round(transmitted))
        else:
            self.transmitted = None
        self.zone = None


class ColumnData:
    def __init__(self, hour, period, value, values=None):
        self.hour = hour
        self.period = period
        if isinstance(value, list):
            for i in range(len(value)):
                if values is not None:
                    setattr(self, values[i], round(value[i], 3))
                else:
                    setattr(self, 'value' + str(i + 1), round(value[i], 3))
        else:
            if values is not None:
                setattr(self, values, round(value, 3))
            else:
                setattr(self, 'value', round(value, 3))


class DailyData:
    def __init__(self, day, date, value, values=None):
        self.day = day
        self.date = date
        if isinstance(value, list):
            for i in range(len(value)):
                if values is not None:
                    setattr(self, values[i], round(value[i], 2))
                else:
                    setattr(self, 'value' + str(i + 1), round(value[i], 2))
        else:
            if values is not None:
                setattr(self, values, round(value, 2))
            else:
                setattr(self, 'value', round(value, 2))

class FinancialSummary:
    def __init__(self, name, technology, capacity, generation, cf, capital_cost, lcoe_real,
                 lcoe_nominal, npv, grid_cost):
        self.name = name
        self.technology = technology
        self.capacity = capacity
        self.generation = int(round(generation))
        try:
            self.cf = round(generation / (capacity * 8760), 2)
        except:
            self.cf = 0.
        self.capital_cost = int(round(capital_cost))
        self.lcoe_real = round(lcoe_real, 2)
        self.lcoe_nominal = round(lcoe_nominal, 2)
        self.npv = int(round(npv))
        self.grid_cost = int(round(grid_cost))


class FinancialModel():

    def get_variables(self, xl_file, overrides=None):
        data = None
        data = ssc.Data()
        var = {}
        try:
            workbook = WorkBook()
            workbook.open_workbook(xl_file)
        except:
            return None, None
        worksheet = workbook.sheet_by_index(0)
        num_rows = worksheet.nrows - 1
        num_cols = worksheet.ncols - 1
   # get column names
        curr_col = -1
        while curr_col < num_cols:
            curr_col += 1
            var[worksheet.cell_value(0, curr_col)] = curr_col
        curr_row = 0
        output_variables = []
        while curr_row < num_rows:
            curr_row += 1
            if worksheet.cell_value(curr_row, var['TYPE']) == 'SSC_INPUT' and \
              worksheet.cell_value(curr_row, var['DEFAULT']) != '' and \
              str(worksheet.cell_value(curr_row, var['DEFAULT'])).lower() != 'input':
                if worksheet.cell_value(curr_row, var['DATA']) == 'SSC_STRING':
                    data.set_string(worksheet.cell_value(curr_row, var['NAME']).encode('utf-8'),
                    worksheet.cell_value(curr_row, var['DEFAULT']).encode('utf-8'))
                elif worksheet.cell_value(curr_row, var['DATA']) == 'SSC_ARRAY':
                    arry = split_array(worksheet.cell_value(curr_row, var['DEFAULT']))
                    data.set_array(worksheet.cell_value(curr_row, var['NAME']).encode('utf-8'), arry)
                elif worksheet.cell_value(curr_row, var['DATA']) == 'SSC_NUMBER':
                    if overrides is not None and worksheet.cell_value(curr_row, var['NAME']) \
                      in overrides:
                        if worksheet.cell_value(curr_row, var['DATA']) == 'SSC_ARRAY':
                            if type(overrides[worksheet.cell_value(curr_row, var['NAME'])]) is list:
                                data.set_array(worksheet.cell_value(curr_row, var['NAME']).encode('utf-8'),
                                  overrides[worksheet.cell_value(curr_row, var['NAME'])])
                            else:
                                data.set_array(worksheet.cell_value(curr_row, var['NAME']).encode('utf-8'),
                                  [overrides[worksheet.cell_value(curr_row, var['NAME'])]])
                        else:
                            data.set_number(worksheet.cell_value(curr_row, var['NAME']).encode('utf-8'),
                              overrides[worksheet.cell_value(curr_row, var['NAME'])])
                    else:
                        if isinstance(worksheet.cell_value(curr_row, var['DEFAULT']), float):
                            data.set_number(worksheet.cell_value(curr_row, var['NAME']).encode('utf-8'),
                              float(worksheet.cell_value(curr_row, var['DEFAULT'])))
                        else:
                            data.set_number(worksheet.cell_value(curr_row, var['NAME']).encode('utf-8'),
                              worksheet.cell_value(curr_row, int(var['DEFAULT'])))
                elif worksheet.cell_value(curr_row, var['DATA']) == 'SSC_MATRIX':
                    mtrx = split_matrix(worksheet.cell_value(curr_row, var['DEFAULT']))
                    data.set_matrix(worksheet.cell_value(curr_row, var['NAME']).encode('utf-8'), mtrx)
            elif worksheet.cell_value(curr_row, var['TYPE']) == 'SSC_OUTPUT':
                output_variables.append([worksheet.cell_value(curr_row, var['NAME']).encode('utf-8'),
                                        worksheet.cell_value(curr_row, var['DATA'])])
        return data, output_variables

    def __init__(self, name, technology, capacity, power, grid, path, year=None, status=None, parms=None):
        def set_grid_variables():
            self.dispatchable = None
            self.grid_line_loss = 0.
            self.subs_cost = 0.
            self.grid_subs_loss = 0.
            try:
                itm = config.get('Grid', 'dispatchable')
                self.dispatchable = techClean(itm)
                line_loss = config.get('Grid', 'line_loss')
                if line_loss[-1] == '%':
                    self.grid_line_loss = float(line_loss[:-1]) / 100000.
                else:
                    self.grid_line_loss = float(line_loss) / 1000.
                line_loss = config.get('Grid', 'substation_loss')
                if line_loss[-1] == '%':
                    self.grid_subs_loss = float(line_loss[:-1]) / 100.
                else:
                    self.grid_subs_loss = float(line_loss)
            except:
                pass

        def stn_costs():
            if technology[stn] not in costs:
                try:
                    cap_cost = config.get(technology[stn], 'capital_cost')
                    if cap_cost[-1] == 'K':
                        cap_cost = float(cap_cost[:-1]) * pow(10, 3)
                    elif cap_cost[-1] == 'M':
                        cap_cost = float(cap_cost[:-1]) * pow(10, 6)
                except:
                    cap_cost = 0.
                try:
                    o_m_cost = config.get(technology[stn], 'o_m_cost')
                    if o_m_cost[-1] == 'K':
                        o_m_cost = float(o_m_cost[:-1]) * pow(10, 3)
                    elif o_m_cost[-1] == 'M':
                        o_m_cost = float(o_m_cost[:-1]) * pow(10, 6)
                except:
                    o_m_cost = 0.
                o_m_cost = o_m_cost * pow(10, -3)
                try:
                    fuel_cost = config.get(technology[stn], 'fuel_cost')
                    if fuel_cost[-1] == 'K':
                        fuel_cost = float(fuel_cost[:-1]) * pow(10, 3)
                    elif fuel_cost[-1] == 'M':
                        fuel_cost = float(fuel_cost[:-1]) * pow(10, 6)
                    else:
                        fuel_cost = float(fuel_cost)
                except:
                    fuel_cost = 0.
                costs[technology[stn]] = [cap_cost, o_m_cost, fuel_cost]
            capital_cost = capacity[stn] * costs[technology[stn]][0]
            if do_grid_cost or do_grid_path_cost:
                if technology[stn] in self.dispatchable:
                    cost, line_table = self.grid.Line_Cost(capacity[stn], capacity[stn])
                else:
                    cost, line_table = self.grid.Line_Cost(capacity[stn], 0.)
                if do_grid_path_cost:
                    grid_cost = cost * path[stn]
                else:
                    grid_cost = cost * grid[stn]
                try:
                    grid_cost += self.grid.Substation_Cost(line_table)
                except:
                    pass
            else:
                grid_cost = 0
            return capital_cost, grid_cost

        def do_ippppa():
            capital_cost, grid_cost = stn_costs()
            ippppa_data.set_number(b'system_capacity', capacity[stn] * 1000)
            ippppa_data.set_array(b'gen', net_hourly)
            ippppa_data.set_number(b'construction_financing_cost', capital_cost + grid_cost)
            ippppa_data.set_number(b'total_installed_cost', capital_cost + grid_cost)
            ippppa_data.set_array(b'om_capacity', [costs[technology[stn]][1]])
            if technology[stn] == 'Biomass':
                ippppa_data.set_number(b'om_opt_fuel_1_usage', self.biomass_multiplier
                                       * capacity[stn] * 1000)
                ippppa_data.set_array(b'om_opt_fuel_1_cost', [costs[technology[stn]][2]])
                ippppa_data.set_number(b'om_opt_fuel_1_cost_escal',
                                       ippppa_data.get_number(b'inflation_rate'))
            module = ssc.Module(b'ippppa')
            if (module.exec_(ippppa_data)):
             # return the relevant outputs desired
                energy = ippppa_data.get_array(b'gen')
                generation = 0.
                for i in range(len(energy)):
                    generation += energy[i]
                generation = generation * pow(10, -3)
                lcoe_real = ippppa_data.get_number(b'lcoe_real')
                lcoe_nom = ippppa_data.get_number(b'lcoe_nom')
                npv = ippppa_data.get_number(b'npv')
                self.stations.append(FinancialSummary(name[stn], technology[stn], capacity[stn],
                  generation, 0, round(capital_cost), lcoe_real, lcoe_nom, npv, round(grid_cost)))
            else:
                if self.status:
                   self.status.log.emit('Errors encountered processing ' + name[stn])
                idx = 0
                msg = module.log(idx)
                while (msg is not None):
                    if self.status:
                       self.status.log.emit('ippppa error [' + str(idx) + ']: ' + msg.decode())
                    else:
                        print('ippppa error [', idx, ' ]: ', msg.decode())
                    idx += 1
                    msg = module.log(idx)
            del module

        self.stations = []
        self.status = status
        self.parms = parms
        self.expert = False
        try:
            expert = config.get('Base', 'expert_mode')
            if expert.lower() in ['true', 'on', 'yes']:
                self.expert = True
        except:
            pass
        if year is None:
            try:
                self.base_year = config.get('Base', 'year')
            except:
                self.base_year = '2012'
        else:
            self.base_year = year
        try:
            self.biomass_multiplier = float(config.get('Biomass', 'multiplier'))
        except:
            self.biomass_multiplier = 8.25
        try:
            variable_files = config.get('Files', 'variable_files')
            annual_file = config.get('SAM Modules', 'annualoutput_variables')
            annual_file = variable_files + '/' + annual_file
            ippppa_file = config.get('SAM Modules', 'ippppa_variables')
            ippppa_file = variable_files + '/' + ippppa_file
        except:
            annual_file = 'annualoutput_variables.xls'
            ippppa = 'ippppa_variables.xls'
        annual_data, annual_outputs = self.get_variables(annual_file)
        if annual_data is None:
            if self.status:
                self.status.log.emit('Error accessing ' + annual_file)
            else:
                print('Error accessing ' + annual_file)
            self.stations = None
            return
        what_beans = whatFinancials(parms=self.parms, helpfile=self.helpfile)
        what_beans.exec_()
        ippas = what_beans.getValues()
        self.parms = what_beans.getParms()
        if ippas is None:
            self.stations = None
            return
        ssc_api = ssc.API()
# to suppress messages
        if not self.expert:
            ssc_api.set_print(0)
        ippppa_data, ippppa_outputs = self.get_variables(ippppa_file, overrides=ippas)
        if ippppa_data is None:
            if self.status:
                self.status.log.emit('Error accessing ' + ippppa_file)
            else:
                print('Error accessing ' + ippppa_file)
            self.stations = None
            return
        costs = {}
        do_grid_loss = False
        do_grid_cost = False
        do_grid_path_cost = False
        if 'grid_losses' in ippas or 'grid_costs' in ippas or 'grid_path_costs' in ippas:
            set_grid_variables()
            try:
                if ippas['grid_losses']:
                    do_grid_loss = True
            except:
                pass
            if 'grid_costs' in ippas or 'grid_path_costs' in ippas:
                self.grid = Grid()  # open grid here to access cost table
                try:
                    if ippas['grid_costs']:
                        do_grid_cost = True
                except:
                    pass
                try:
                    if ippas['grid_path_costs']:
                        do_grid_path_cost = True
                except:
                    pass
        for stn in range(len(name)):
            if len(power[stn]) != 8760:
                capital_cost, grid_cost = stn_costs()
                self.stations.append(FinancialSummary(name[stn], technology[stn], capacity[stn],
                  0., 0, round(capital_cost), 0., 0., 0., round(grid_cost)))
                continue
            energy = []
            if do_grid_loss and grid[stn] != 0:
                if do_grid_path_cost:
                    for hr in range(len(power[stn])):
                        energy.append(power[stn][hr] * 1000 * (1 - self.grid_line_loss * path[stn] -
                                      self.grid_subs_loss))
                else:
                    for hr in range(len(power[stn])):
                        energy.append(power[stn][hr] * 1000 * (1 - self.grid_line_loss * grid[stn] -
                                      self.grid_subs_loss))
            else:
                for hr in range(len(power[stn])):
                    energy.append(power[stn][hr] * 1000)
            annual_data.set_array(b'system_hourly_energy', energy)
            net_hourly = None
            module = ssc.Module(b'annualoutput')
            if (module.exec_(annual_data)):
             # return the relevant outputs desired
                net_hourly = annual_data.get_array(b'hourly_energy')
                net_annual = annual_data.get_array(b'annual_energy')
                degradation = annual_data.get_array(b'annual_degradation')
                del module
                do_ippppa()
            else:
                if self.status:
                   self.status.log.emit('Errors encountered processing ' + name[stn])
                idx = 0
                msg = module.log(idx)
                while (msg is not None):
                    if self.status:
                       self.status.log.emit('annualoutput error [' + str(idx) + ']: ' + msg.decode())
                    else:
                        print('annualoutput error [', idx, ' ]: ', msg.decode())
                    idx += 1
                    msg = module.log(idx)
                del module

    def getValues(self):
        return self.stations

    def getParms(self):
        return self.parms
