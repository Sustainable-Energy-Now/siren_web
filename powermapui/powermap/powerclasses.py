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
import sys
from . import ssc

from .senutils import getParents, getUser, WorkBook
from .getmodels import getModelFile
from .grid import Grid

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


class whatPlots():
    def __init__(self, plots, plot_order, hdrs, spacers, load_growth, base_year, load_year,
                 iterations, storage, discharge, recharge, initials=None, initial=False, helpfile=None):
        self.plots = plots
        self.plot_order = plot_order
        self.hdrs = hdrs
        self.spacers = spacers
        self.load_growth = load_growth * 100
        self.base_year = int(base_year)
        self.load_year = int(load_year)
        self.iterations = iterations
        self.storage = storage
        self.discharge = discharge
        self.recharge = recharge
        self.initial = initial
        self.helpfile = helpfile
        if self.initial:
            self.initials = None
        else:
            self.initials = initials
        super(whatPlots, self).__init__()
        self.initUI()

    def growthChanged(self, val):
        summ = pow(1 + self.percentSpin.value() / 100, (self.counterSpin.value() - self.base_year))
        summ = '{:0.1f}%'.format((summ - 1) * 100)
        self.totalOutput.setText(summ)
        self.totalOutput.adjustSize()

    def closeEvent(self, event):
        if not self.show_them:
            self.plots = None
        event.accept()

class whatStations():
    def __init__(self, stations, gross_load=False, actual=False, helpfile=None):
        self.stations = stations
        self.gross_load = gross_load
        self.actual = actual
        super(whatStations, self).__init__()

class whatFinancials():
    def __init__(self, parms=None, helpfile=None):
        super(whatFinancials, self).__init__()
        self.proceed = False
        self.helpfile = helpfile
        self.financials = [['analysis_period', 'Analysis period (years)', 0, 50, 30],
                      ['federal_tax_rate', 'Federal tax rate (%)', 0, 30., 30.],
                      ['real_discount_rate', 'Real discount rate (%)', 0, 20., 0],
                      ['inflation_rate', 'Inflation rate (%)', 0, 20., 0],
                      ['insurance_rate', 'Insurance rate (%)', 0, 15., 0],
                      ['loan_term', 'Loan term (years)', 0, 60., 0],
                      ['loan_rate', 'Loan rate (%)', 0, 30., 0],
                      ['debt_fraction', 'Debt percentage (%)', 0, 100, 0],
                      ['depr_fed_type', 'Federal depreciation type 2=straight line', 0, 2, 2],
                      ['depr_fed_sl_years', 'Depreciation straight-line term (years)', 0, 60, 20],
                      ['market', 'Commercial PPA (on), Utility IPP (off)', 0, 1, 0],
                   #   ['bid_price_esc', 'Bid Price escalation (%)', 0, 100., 0],
                      ['salvage_percentage', 'Salvage value percentage (%)', 0, 100., 0],
                      ['min_dscr_target', 'Minimum required DSCR (ratio)', 0, 5., 1.4],
                      ['min_irr_target', 'Minimum required IRR (%)', 0, 30., 15.],
                   #   ['ppa_escalation', 'PPA escalation (%)', 0, 100., 0.6],
                      ['min_dscr_required', 'Minimum DSCR required?', 0, 1, 1],
                      ['positive_cashflow_required', 'Positive cash flow required?', 0, 1, 1],
                      ['optimize_lcoe_wrt_debt_fraction', 'Optimize LCOE with respect to debt' +
                       ' percent?', 0, 1, 0],
                   #   ['optimize_lcoe_wrt_ppa_escalation', 'Optimize LCOE with respect to PPA' +
                   #    ' escalation?', 0, 1, 0],
                      ['grid_losses', 'Reduce power by Grid losses?', False, True, False],
                      ['grid_costs', 'Include Grid costs in LCOE?', False, True, False],
                      ['grid_path_costs', 'Include full grid path in LCOE?', False, True, False]]
        if parms is None:
            beans = []
            try:
                for key, value in beans:
                    for i in range(len(self.financials)):
                        if key == self.financials[i][0]:
                            if value[-1] == '%':
                                self.financials[i][4] = float(value[:-1])
                            elif '.' in value:
                                self.financials[i][4] = float(value)
                            elif isinstance(self.financials[i][4], bool):
                                if value == 'True':
                                    self.financials[i][4] = True
                                else:
                                    self.financials[i][4] = False
                            else:
                                self.financials[i][4] = int(value)
                            break
            except:
                pass
        else:
            self.financials = parms
        #
    def closeEvent(self, event):
        event.accept()

class Adjustments():
    def __init__(self, keys, load_key=None, load=None, data=None, base_year=None):
        super(Adjustments, self).__init__()
        if len(sys.argv) > 1:
            config_file = sys.argv[1]
        else:
            config_file = getModelFile('SIREN.ini')
        config.read(config_file)
        self.seasons = []
        self.periods = []
        self.daily = True
        self.adjust_cap = 25
        self.opt_load = False
        try:
            items = config.items('Power')
            for item, values in items:
                if item[:6] == 'season':
                    if item == 'season':
                        continue
                    i = int(item[6:]) - 1
                    if i >= len(self.seasons):
                        self.seasons.append([])
                    self.seasons[i] = values.split(',')
                    for j in range(1, len(self.seasons[i])):
                        self.seasons[i][j] = int(self.seasons[i][j]) - 1
                elif item[:6] == 'period':
                    if item == 'period':
                        continue
                    i = int(item[6:]) - 1
                    if i >= len(self.periods):
                        self.periods.append([])
                    self.periods[i] = values.split(',')
                    for j in range(1, len(self.periods[i])):
                        self.periods[i][j] = int(self.periods[i][j]) - 1
                elif item == 'optimise':
                    if values[0].lower() == 'h': # hourly
                        self.daily = False
                elif item == 'optimise_load':
                    if values.lower() in ['true', 'yes', 'on']:
                        self.opt_load = True
                elif item == 'adjust_cap':
                    try:
                        self.adjust_cap = float(values)
                    except:
                        try:
                            self.adjust_cap = eval(values)
                        except:
                            pass
                    if self.adjust_cap < 0:
                        self.adjust_cap = pow(10, 12)
        except:
            pass
        if len(self.seasons) == 0:
            self.seasons = [['Summer', 11, 0, 1], ['Autumn', 2, 3, 4], ['Winter', 5, 6, 7], ['Spring', 8, 9, 10]]
        if len(self.periods) == 0:
            self.periods = [['Winter', 4, 5, 6, 7, 8, 9], ['Summer', 10, 11, 0, 1, 2, 3]]
        for i in range(len(self.periods)):
            for j in range(len(self.seasons)):
                if self.periods[i][0] == self.seasons[j][0]:
                    self.periods[i][0] += '2'
                    break
        self.adjusts = {}
        self.checkbox = {}
        self.results = None
        ctr = 0
        self.skeys = []
        self.lkey = load_key
        if len(keys) > 10:
            octr = 0
            ctr += 2
        else:
            octr = -1
        ctr += 1
        for key in sorted(keys):
            if key == 'Generation':
                continue
            if key[:4] == 'Load':
                self.lkey = key
                continue
            if type(keys) is dict:
                self.adjusts[key].setValue(keys[key])
            else:
                self.adjusts[key].setValue(1.)
            self.adjusts[key].setDecimals(2)
            self.adjusts[key].setSingleStep(.1)
            self.skeys.append(key)
            ctr += 1
        if octr >= 0:
            ctr = 0
        if load is not None:
            for key in list(data.keys()):
                if key[:4] == 'Load':
                    self.lkey = key
                    break
            self.load = load
            self.data = data

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

        try:
            self.helpfile = config.get('Files', 'help')
            for key, value in parents:
                self.helpfile = self.helpfile.replace(key, value)
            self.helpfile = self.helpfile.replace('$USER$', getUser())
            self.helpfile = self.helpfile.replace('$YEAR$', self.base_year)
        except:
            self.helpfile = ''
        try:
            self.biomass_multiplier = float(config.get('Biomass', 'multiplier'))
        except:
            self.biomass_multiplier = 8.25
        try:
            variable_files = config.get('Files', 'variable_files')
            for key, value in parents:
                variable_files = variable_files.replace(key, value)
            variable_files = variable_files.replace('$USER$', getUser())
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

    def getParms(self):
        return self.parms
