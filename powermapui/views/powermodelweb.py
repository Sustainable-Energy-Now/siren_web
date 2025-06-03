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
from siren_web.siren.powermap.logic.powermodelbase import PowerModelBase
from siren_web.siren.powermatch.logic.superpowerbase import SuperPowerBase as SuperPower


class PowerModelWeb(PowerModelBase):

    def __init__(self, config, stations, year=None, scenario_settings=None):
        self.config = config
        self.stations = stations
        self.data_file = ''
        self.technologies = ''
        self.load_growth = 0.
        self.storage = [0., 0.]
        self.recharge = [0., 1.]
        self.discharge = [0., 1.]
        self.selected = None
        self.base_year = year
        self.load_file = scenario_settings.get('load', None)
        self.load_year = self.base_year
        self.load_growth = 0.
        self.storage = [0., 0.]
        self.recharge = [0., 1.]
        self.discharge = [0., 1.]
        try:
            self.discharge[0] = float(scenario_settings.get('discharge_max', None))
            self.discharge[1] = float(scenario_settings.get('discharge_eff', None))
            if self.discharge[1] < 0.5:
                self.discharge[1] = 1 - self.discharge[1]
            self.recharge[0] = float(scenario_settings.get('recharge_max', None))
            self.recharge[1] = float(scenario_settings.get('recharge_eff', None))
            if self.recharge[1] < 0.5:
                self.recharge[1] = 1 - self.recharge[1]
        except Exception as e:
            pass
        
        #
#       collect the data (once only)
#
        self.stn_outs = []
        self.model = SuperPower(self.config, stations, demand_year=self.base_year, scenario_settings=scenario_settings)
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
        elif len(self.ly) == 1:
                self.suffix = ' - ' + list(self.ly.keys())[0]
        do_financials = False
#
#       loop around processing plots
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

