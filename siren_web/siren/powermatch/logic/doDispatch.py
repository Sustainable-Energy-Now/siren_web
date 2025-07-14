    def dispatch_technologies(
        self, year, option, sender_name, technology_attributes, load_and_supply, re_order, dispatch_order, pm_data_file, 
        data_file, files, sheets, title=None
        ):
        def calcLCOE(annual_output, capital_cost, annual_operating_cost, discount_rate, lifetime):
            # Compute levelised cost of electricity
            if discount_rate > 0:
                annual_cost_capital = capital_cost * discount_rate * pow(1 + discount_rate, lifetime) / \
                                      (pow(1 + discount_rate, lifetime) - 1)
            else:
                annual_cost_capital = capital_cost / lifetime
            total_annual_cost = annual_cost_capital + annual_operating_cost
            try:
                return total_annual_cost / annual_output
            except:
                return total_annual_cost

        def format_period(per):
            hr = per % 24
            day = int((per - hr) / 24)
            mth = 0
            while day > the_days[mth] - 1:
                day -= the_days[mth]
                mth += 1
            return '{}-{:02d}-{:02d} {:02d}:00'.format(year, mth+1, day+1, hr)

        def summary_totals(title=''):
            sp_d = [' '] * len(headers)
            sp_d[st_fac] = title + 'Total'
            sp_d[st_cap] = cap_sum
            sp_d[st_tml] = tml_sum
            sp_d[st_sub] = gen_sum
            sp_d[st_cst] = cost_sum
            sp_d[st_lcg] = gs
            sp_d[st_lco] = gsw
            sp_d[st_emi] = co2_sum
            sp_d[st_emc] = co2_cost_sum
            sp_d[st_lcc] = gswc
            sp_d[st_cac] = capex_sum
            sp_d[st_lic] = lifetime_sum
            sp_d[st_lie] = lifetime_co2_sum
            sp_d[st_lec] = lifetime_co2_cost
            sp_d[st_are] = total_area
            sp_data.append(sp_d)
            if (self.carbon_price > 0 or option == B or option == T):
                sp_d = [' '] * len(headers)
                cc = co2_sum * self.carbon_price
                cl = cc * max_lifetime
                if self.adjusted_lcoe and tml_sum > 0:
                    cs = (cost_sum + cc) / tml_sum
                else:
                    if gen_sum > 0:
                        cs = (cost_sum + cc) / gen_sum
                    else:
                        cs = ''
                sp_d[st_fac] = title + 'Total incl. Carbon Cost'
                sp_d[st_cst] = cost_sum + cc
                sp_d[st_lic] = lifetime_sum + cl
                sp_data.append(sp_d)
            if tml_sum > 0:
                sp_d = [' '] * len(headers)
             #   sp_d[st_fac] = 'RE Direct Contribution to ' + title + 'Load'
                sp_d[st_fac] = 'RE %age'
                re_pct = (tml_sum - sto_sum - ff_sum) / tml_sum
                sp_d[st_cap] = '{:.1f}%'.format(re_pct * 100.)
                sp_d[st_tml] = tml_sum - ff_sum - sto_sum
                sp_data.append(sp_d)
                if sto_sum > 0:
                    sp_d = [' '] * len(headers)
                 #   sp_d[st_fac] = 'RE Contribution to ' + title + 'Load via Storage'
                    sp_d[st_fac] = 'Storage %age'
                    sp_d[st_cap] = '{:.1f}%'.format(sto_sum * 100. / tml_sum)
                    sp_d[st_tml] = sto_sum
                    sp_data.append(sp_d)
            sp_data.append([' '])
            sp_data.append([title + 'Load Analysis'])
            if sp_load != 0:
                sp_d = [' '] * len(headers)
                sp_d[st_fac] = title + 'Load met'
                load_pct = (sp_load - sf_sums[0]) / sp_load
                sp_d[st_cap] = '{:.1f}%'.format(load_pct * 100)
                sp_d[st_tml] = sp_load - sf_sums[0]
                sp_data.append(sp_d)
                sp_d = [' '] * len(headers)
                sp_d[st_fac] = 'Shortfall'
                sp_d[st_cap] = '{:.1f}%'.format(sf_sums[0] * 100 / sp_load)
                sp_d[st_tml] = sf_sums[0]
                sp_data.append(sp_d)
                if option == B or option == T:
                    sp_d = [' '] * len(headers)
                    sp_d[st_fac] = title + 'Total Load'
                    sp_d[st_tml] = sp_load
                    if title == '':
                        sp_d[st_max] = load_max
                    sp_data.append(sp_d)
                else:
                    load_mult = ''
                    try:
                        mult = round(technology_attributes['Load'].multiplier, 3)
                        if mult != 1:
                            load_mult = ' x ' + str(mult)
                    except:
                        pass
                    sp_d = [' '] * len(headers)
                    sp_d[st_fac] = 'Total ' + title + 'Load - ' + year + load_mult
                    sp_d[st_tml] = sp_load
                    if title == '' or option == S:
                        sp_d[st_max] = load_max
                        sp_d[st_bal] = ' (' + format_period(load_hr)[5:] + ')'
                    sp_data.append(sp_d)
                sp_d = [' '] * len(headers)
                sp_d[st_fac] = 'RE %age of Total ' + title + 'Load'
                sp_d[st_cap] = '{:.1f}%'.format((sp_load - sf_sums[0] - ff_sum) * 100. / sp_load)
                sp_data.append(sp_d)
                sp_data.append(' ')
                if tot_sto_loss != 0:
                    sp_d = [' '] * len(headers)
                    sp_d[st_fac] = 'Storage losses'
                    sp_d[st_sub] = tot_sto_loss
                    sp_data.append(sp_d)
                sp_d = [' '] * len(headers)
                sp_d[st_fac] = title + 'Surplus'
                surp_pct = -sf_sums[1] / sp_load
                sp_d[st_cap] = '{:.1f}%'.format(surp_pct * 100)
                sp_d[st_sub] = -sf_sums[1]
                sp_data.append(sp_d)
            else:
                load_pct = 0
                surp_pct = 0
                re_pct = 0
            max_short = [0, 0]
            for h in range(len(shortfall)):
                if shortfall[h] > max_short[1]:
                    max_short[0] = h
                    max_short[1] = shortfall[h]
            if max_short[1] > 0:
                sp_d = [' '] * len(headers)
                sp_d[st_fac] = 'Largest Shortfall'
                sp_d[st_sub] = round(max_short[1], 2)
                sp_d[st_cfa] = ' (' + format_period(max_short[0])[5:] + ')'
                sp_data.append(sp_d)
            if option == O or option == O1:
                return load_pct, surp_pct, re_pct

        def do_detail(fac, col, ss_row):
            if fac in self.generators.keys():
                gen = fac
            else:
                gen = technology_attributes[fac].generator
            col += 1
            sp_cols.append(fac)
            sp_cap.append(technology_attributes[fac].capacity * technology_attributes[fac].multiplier)
            if do_zone and technology_attributes[fac].zone != '':
                ns.cell(row=zone_row, column=col).value = technology_attributes[fac].zone
                ns.cell(row=zone_row, column=col).alignment = oxl.styles.Alignment(wrap_text=True,
                    vertical='bottom', horizontal='center')
            try:
                ns.cell(row=what_row, column=col).value = fac[fac.find('.') + 1:]
            except:
                ns.cell(row=what_row, column=col).value = fac # gen
            ns.cell(row=what_row, column=col).alignment = oxl.styles.Alignment(wrap_text=True,
                    vertical='bottom', horizontal='center')
            ns.cell(row=cap_row, column=col).value = sp_cap[-1]
            ns.cell(row=cap_row, column=col).number_format = '#,##0.00'
            # capacity
            ns.cell(row=sum_row, column=col).value = '=SUM(' + ssCol(col) \
                    + str(hrows) + ':' + ssCol(col) + str(hrows + 8759) + ')'
            ns.cell(row=sum_row, column=col).number_format = '#,##0'
            # To meet load MWh
            ns.cell(row=tml_row, column=col).value = fac_tml[fac]
            ns.cell(row=tml_row, column=col).number_format = '#,##0'
            ns.cell(row=cf_row, column=col).value = '=IF(' + ssCol(col) + str(cap_row) + '>0,' + \
                    ssCol(col) + str(sum_row) + '/' + ssCol(col) + str(cap_row) + '/8760,"")'
            ns.cell(row=cf_row, column=col).number_format = '#,##0.0%'
            # subtotal MWh
            ns.cell(row=cf_row, column=col).value = '=IF(' + ssCol(col) + str(cap_row) + '>0,' + \
                    ssCol(col) + str(sum_row) +'/' + ssCol(col) + str(cap_row) + '/8760,"")'
            ns.cell(row=cf_row, column=col).number_format = '#,##0.0%'
            if gen not in self.generators.keys():
                return col
            if self.generators[gen].capex > 0 or self.generators[gen].fixed_om > 0 \
              or self.generators[gen].variable_om > 0 or self.generators[gen].fuel > 0:
                disc_rate = self.generators[gen].disc_rate
                if disc_rate == 0:
                    disc_rate = self.discount_rate
                if disc_rate == 0:
                    cst_calc = '/' + str(self.generators[gen].lifetime)
                else:
                    pwr_calc = 'POWER(1+' + str(disc_rate) + ',' + str(self.generators[gen].lifetime) + ')'
                    cst_calc = '*' + str(disc_rate) + '*' + pwr_calc + '/SUM(' + pwr_calc + ',-1)'
                ns.cell(row=cost_row, column=col).value = '=IF(' + ssCol(col) + str(cf_row) + \
                        '>0,' + ssCol(col) + str(cap_row) + '*' + str(self.generators[gen].capex) + \
                        cst_calc + '+' + ssCol(col) + str(cap_row) + '*' + \
                        str(self.generators[gen].fixed_om) + '+' + ssCol(col) + str(sum_row) + '*(' + \
                        str(self.generators[gen].variable_om) + '+' + str(self.generators[gen].fuel) + \
                        '),0)'
                ns.cell(row=cost_row, column=col).number_format = '$#,##0'
                ns.cell(row=lcoe_row, column=col).value = '=IF(AND(' + ssCol(col) + str(cf_row) + \
                        '>0,' + ssCol(col) + str(cap_row) + '>0),' + ssCol(col) + \
                        str(cost_row) + '/' + ssCol(col) + str(sum_row) + ',"")'
                ns.cell(row=lcoe_row, column=col).number_format = '$#,##0.00'
            elif self.generators[gen].lcoe > 0:
                if ss_row >= 0:
                    ns.cell(row=cost_row, column=col).value = '=IF(' + ssCol(col) + str(cf_row) + \
                            '>0,' + ssCol(col) + str(sum_row) + '*Summary!' + ssCol(st_rlc + 1) + str(ss_row) + \
                        '*Summary!' + ssCol(st_rcf + 1) + str(ss_row) + '/' + ssCol(col) + str(cf_row) + ',0)'
                    ns.cell(row=cost_row, column=col).number_format = '$#,##0'
                ns.cell(row=lcoe_row, column=col).value = '=IF(AND(' + ssCol(col) + str(cf_row) + '>0,' \
                        + ssCol(col) + str(cap_row) + '>0),' + ssCol(col) + str(cost_row) + '/8760/' \
                        + ssCol(col) + str(cf_row) +'/' + ssCol(col) + str(cap_row) + ',"")'
                ns.cell(row=lcoe_row, column=col).number_format = '$#,##0.00'
            elif self.generators[gen].lcoe_cf == 0: # no cost facility
                if ss_row >= 0:
                    ns.cell(row=cost_row, column=col).value = '=IF(' + ssCol(col) + str(cf_row) + \
                            '>0,' + ssCol(col) + str(sum_row) + '*Summary!' + ssCol(st_rlc + 1) + str(ss_row) + \
                        '*Summary!' + ssCol(st_rcf + 1) + str(ss_row) + '/' + ssCol(col) + str(cf_row) + ',0)'
                    ns.cell(row=cost_row, column=col).number_format = '$#,##0'
                ns.cell(row=lcoe_row, column=col).value = '=IF(AND(' + ssCol(col) + str(cf_row) + '>0,' \
                        + ssCol(col) + str(cap_row) + '>0),' + ssCol(col) + str(cost_row) + '/8760/' \
                        + ssCol(col) + str(cf_row) +'/' + ssCol(col) + str(cap_row) + ',"")'
                ns.cell(row=lcoe_row, column=col).number_format = '$#,##0.00'
            if self.generators[gen].emissions > 0:
                ns.cell(row=emi_row, column=col).value = '=' + ssCol(col) + str(sum_row) \
                        + '*' + str(self.generators[gen].emissions)
                ns.cell(row=emi_row, column=col).number_format = '#,##0'
            ns.cell(row=max_row, column=col).value = '=MAX(' + ssCol(col) + str(hrows) + \
                                           ':' + ssCol(col) + str(hrows + 8759) + ')'
            ns.cell(row=max_row, column=col).number_format = '#,##0.00'
            ns.cell(row=hrs_row, column=col).value = '=COUNTIF(' + ssCol(col) + str(hrows) + \
                                           ':' + ssCol(col) + str(hrows + 8759) + ',">0")'
            ns.cell(row=hrs_row, column=col).number_format = '#,##0'
            di = technology_attributes[fac].col
            if technology_attributes[fac].multiplier == 1:
                for row in range(hrows, 8760 + hrows):
                    ns.cell(row=row, column=col).value = load_and_supply[di][row - hrows]
                    ns.cell(row=row, column=col).number_format = '#,##0.00'
            else:
                for row in range(hrows, 8760 + hrows):
                    ns.cell(row=row, column=col).value = load_and_supply[di][row - hrows] * \
                                                         technology_attributes[fac].multiplier
                    ns.cell(row=row, column=col).number_format = '#,##0.00'
            return col

        def do_detail_summary(fac, col, ss_row, dd_tml_sum, dd_re_sum):
            if do_zone and technology_attributes[fac].zone != '':
                ss.cell(row=ss_row, column=st_fac+1).value = '=Detail!' + ssCol(col) + str(zone_row) + \
                                                      '&"."&Detail!' + ssCol(col) + str(what_row)
            else:
                ss.cell(row=ss_row, column=st_fac+1).value = '=Detail!' + ssCol(col) + str(what_row)
            if fac in self.generators.keys():
                gen = fac
            else:
                gen = technology_attributes[fac].generator
            # capacity
            ss.cell(row=ss_row, column=st_cap+1).value = '=Detail!' + ssCol(col) + str(cap_row)
            ss.cell(row=ss_row, column=st_cap+1).number_format = '#,##0.00'
            # To meet load MWh
            ss.cell(row=ss_row, column=st_tml+1).value = '=Detail!' + ssCol(col) + str(tml_row)
            ss.cell(row=ss_row, column=st_tml+1).number_format = '#,##0'
            dd_tml_sum += ssCol(st_tml+1) + str(ss_row) + '+'
            # subtotal MWh
            ss.cell(row=ss_row, column=st_sub+1).value = '=IF(Detail!' + ssCol(col) + str(sum_row) \
                                                  + '>0,Detail!' + ssCol(col) + str(sum_row) + ',"")'
            ss.cell(row=ss_row, column=st_sub+1).number_format = '#,##0'
            dd_re_sum += ssCol(st_sub+1) + str(ss_row) + '+'
            # CF
            ss.cell(row=ss_row, column=st_cfa+1).value = '=IF(Detail!' + ssCol(col) + str(cf_row) \
                                                  + '>0,Detail!' + ssCol(col) + str(cf_row) + ',"")'
            ss.cell(row=ss_row, column=st_cfa+1).number_format = '#,##0.0%'
            if gen not in self.generators.keys():
                return dd_tml_sum, dd_re_sum
            if self.generators[gen].capex > 0 or self.generators[gen].fixed_om > 0 \
              or self.generators[gen].variable_om > 0 or self.generators[gen].fuel > 0:
                disc_rate = self.generators[gen].disc_rate
                if disc_rate == 0:
                    disc_rate = self.discount_rate
                if disc_rate == 0:
                    cst_calc = '/' + str(self.generators[gen].lifetime)
                else:
                    pwr_calc = 'POWER(1+' + str(disc_rate) + ',' + str(self.generators[gen].lifetime) + ')'
                    cst_calc = '*' + str(disc_rate) + '*' + pwr_calc + '/SUM(' + pwr_calc + ',-1)'
                # cost / yr
                if self.remove_cost:
                    ss.cell(row=ss_row, column=st_cst+1).value = '=IF(Detail!' + ssCol(col) + str(sum_row) \
                            + '>0,Detail!' + ssCol(col) + str(cost_row) + ',"")'
                else:
                    ss.cell(row=ss_row, column=st_cst+1).value = '=Detail!' + ssCol(col) + str(cost_row)
                ss.cell(row=ss_row, column=st_cst+1).number_format = '$#,##0'
                # lcog
                ss.cell(row=ss_row, column=st_lcg+1).value = '=IF(Detail!' + ssCol(col) + str(lcoe_row) \
                                                      + '>0,Detail!' + ssCol(col) + str(lcoe_row) + ',"")'
                ss.cell(row=ss_row, column=st_lcg+1).number_format = '$#,##0.00'
                # capital cost
                ss.cell(row=ss_row, column=st_cac+1).value = '=IF(Detail!' + ssCol(col) + str(cap_row) \
                                                        + '>0,Detail!' + ssCol(col) + str(cap_row) + '*'  \
                                                        + str(self.generators[gen].capex) + ',"")'
                ss.cell(row=ss_row, column=st_cac+1).number_format = '$#,##0'
            elif self.generators[gen].lcoe > 0:
                # cost / yr
                if self.remove_cost:
                    ss.cell(row=ss_row, column=st_cst+1).value = '=IF(Detail!' + ssCol(col) + str(sum_row) \
                            + '>0,Detail!' + ssCol(col) + str(cost_row) + ',"")'
                else:
                    ss.cell(row=ss_row, column=st_cst+1).value = '=Detail!' + ssCol(col) + str(cost_row)
                ss.cell(row=ss_row, column=st_cst+1).number_format = '$#,##0'
                # lcog
                ss.cell(row=ss_row, column=st_lcg+1).value = '=Detail!' + ssCol(col) + str(lcoe_row)
                ss.cell(row=ss_row, column=st_lcg+1).number_format = '$#,##0.00'
                # ref lcoe
                ss.cell(row=ss_row, column=st_rlc+1).value = self.generators[gen].lcoe
                ss.cell(row=ss_row, column=st_rlc+1).number_format = '$#,##0.00'
                # ref cf
                ss.cell(row=ss_row, column=st_rcf+1).value = self.generators[gen].lcoe_cf
                ss.cell(row=ss_row, column=st_rcf+1).number_format = '#,##0.0%'
            elif self.generators[gen].lcoe_cf == 0: # no cost facility
                # cost / yr
                if self.remove_cost:
                    ss.cell(row=ss_row, column=st_cst+1).value = '=IF(Detail!' + ssCol(col) + str(sum_row) \
                            + '>0,Detail!' + ssCol(col) + str(cost_row) + ',"")'
                else:
                    ss.cell(row=ss_row, column=st_cst+1).value = '=Detail!' + ssCol(col) + str(cost_row)
                ss.cell(row=ss_row, column=st_cst+1).number_format = '$#,##0'
                # lcog
                ss.cell(row=ss_row, column=st_lcg+1).value = '=Detail!' + ssCol(col) + str(lcoe_row)
                ss.cell(row=ss_row, column=st_lcg+1).number_format = '$#,##0.00'
                # ref lcoe
                ss.cell(row=ss_row, column=st_rlc+1).value = self.generators[gen].lcoe
                ss.cell(row=ss_row, column=st_rlc+1).number_format = '$#,##0.00'
                # ref cf
                ss.cell(row=ss_row, column=st_rcf+1).value = self.generators[gen].lcoe_cf
                ss.cell(row=ss_row, column=st_rcf+1).number_format = '#,##0.0%'
            # lifetime cost
            ss.cell(row=ss_row, column=st_lic+1).value = '=IF(Detail!' + ssCol(col) + str(sum_row) \
                                                    + '>0,Detail!' + ssCol(col) + str(cost_row) + '*lifetime,"")'
            ss.cell(row=ss_row, column=st_lic+1).number_format = '$#,##0'
            # max mwh
            ss.cell(row=ss_row, column=st_max+1).value = '=IF(Detail!' + ssCol(col) + str(sum_row) \
                                                   + '>0,Detail!' + ssCol(col) + str(max_row) + ',"")'
            ss.cell(row=ss_row, column=st_max+1).number_format = '#,##0.00'
            if self.generators[gen].emissions > 0:
                if self.remove_cost:
                    ss.cell(row=ss_row, column=st_emi+1).value = '=IF(Detail!' + ssCol(col) + str(sum_row) \
                            + '>0,Detail!' + ssCol(col) + str(emi_row) + ',"")'
                else:
                    ss.cell(row=ss_row, column=st_emi+1).value = '=Detail!' + ssCol(col) + str(emi_row)
                ss.cell(row=ss_row, column=st_emi+1).number_format = '#,##0'
                if self.carbon_price > 0:
                    ss.cell(row=ss_row, column=st_emc+1).value = '=IF(AND(' + ssCol(st_emi+1) + str(ss_row) + '<>"",' + \
                                                                 ssCol(st_emi+1) + str(ss_row) + '>0),' + \
                                                                 ssCol(st_emi+1) + str(ss_row) + '*carbon_price,"")'
                    ss.cell(row=ss_row, column=st_emc+1).number_format = '$#,##0'
            ss.cell(row=ss_row, column=st_lie+1).value = '=IF(AND(' + ssCol(st_emi+1) + str(ss_row) + '<>"",' + \
                                                         ssCol(st_emi+1) + str(ss_row) + '>0),' + \
                                                         ssCol(st_emi+1) + str(ss_row) + '*lifetime,"")'
            ss.cell(row=ss_row, column=st_lie+1).number_format = '#,##0'
            ss.cell(row=ss_row, column=st_lec+1).value = '=IF(AND(' + ssCol(st_emi+1) + str(ss_row) + '<>"",' + \
                                                         ssCol(st_emi+1) + str(ss_row) + '>0),' + \
                                                         ssCol(st_emc+1) + str(ss_row) + '*lifetime,"")'
            ss.cell(row=ss_row, column=st_lec+1).number_format = '$#,##0'
            if self.generators[gen].area > 0:
                ss.cell(row=ss_row, column=st_are+1).value = '=Detail!' + ssCol(col) + str(cap_row) +\
                                                             '*' + str(self.generators[gen].area)
                ss.cell(row=ss_row, column=st_are+1).number_format = '#,##0.00'
            return dd_tml_sum, dd_re_sum

        def detail_summary_total(ss_row, title='', base_row='', back_row=''):
            ss_row += 1
            ss.cell(row=ss_row, column=1).value = title + 'Total'
            for col in range(1, len(headers) + 1):
                ss.cell(row=3, column=col).font = bold
                ss.cell(row=ss_row, column=col).font = bold
            for col in [st_cap, st_tml, st_sub, st_cst, st_emi, st_emc, st_cac, st_lic, st_lie, st_lec, st_are]:
                if back_row != '':
                    strt = ssCol(col, base=0) + back_row + '+'
                else:
                    strt = ''
                ss.cell(row=ss_row, column=col+1).value = '=' + strt + 'SUM(' + ssCol(col, base=0) + \
                        base_row + ':' + ssCol(col, base=0) + str(ss_row - 1) + ')'
                if col in [st_cap, st_are]:
                    ss.cell(row=ss_row, column=col+1).number_format = '#,##0.00'
                elif col in [st_tml, st_sub, st_emi, st_lie]:
                    ss.cell(row=ss_row, column=col+1).number_format = '#,##0'
                else:
                    ss.cell(row=ss_row, column=col+1).number_format = '$#,##0'
            ss.cell(row=ss_row, column=st_lcg+1).value = '=' + ssCol(st_cst+1) + str(ss_row) + \
                                                         '/' + ssCol(st_sub+1) + str(ss_row)
            ss.cell(row=ss_row, column=st_lcg+1).number_format = '$#,##0.00'
            ss.cell(row=ss_row, column=st_lco+1).value = '=' + ssCol(st_cst+1) + str(ss_row) + \
                                                         '/' + ssCol(st_tml+1) + str(ss_row)
            ss.cell(row=ss_row, column=st_lco+1).number_format = '$#,##0.00'
            if self.carbon_price > 0:
                ss.cell(row=ss_row, column=st_lcc+1).value = '=(' + ssCol(st_cst+1) + str(ss_row) + \
                    '+' + ssCol(st_emc+1) + str(ss_row) + ')/' + ssCol(st_tml+1) + str(ss_row)
                ss.cell(row=ss_row, column=st_lcc+1).number_format = '$#,##0.00'
                ss.cell(row=ss_row, column=st_lcc+1).font = bold
            last_col = ssCol(ns.max_column)
            r = 1
            if self.carbon_price > 0:
                ss_row += 1
                ss.cell(row=ss_row, column=1).value = title + 'Total incl. Carbon Cost'
                ss.cell(row=ss_row, column=st_cst+1).value = '=' + ssCol(st_cst+1) + str(ss_row - 1) + \
                        '+' + ssCol(st_emc+1) + str(ss_row - 1)
                ss.cell(row=ss_row, column=st_cst+1).number_format = '$#,##0'
                ss.cell(row=ss_row, column=st_lic+1).value = '=' + ssCol(st_lic+1) + str(ss_row - r) + \
                                                             '+' + ssCol(st_lec+1) + str(ss_row - 1)
                ss.cell(row=ss_row, column=st_lic+1).number_format = '$#,##0'
                r += 1
            ss_row += 1
            ss.cell(row=ss_row, column=1).value = title + 'RE %age'
            ss.cell(row=ss_row, column=st_tml+1).value = ns_tml_sum[:-1] + ')'
            ss.cell(row=ss_row, column=st_tml+1).number_format = '#,##0'
            ss.cell(row=ss_row, column=st_cap+1).value = '=' + ssCol(st_tml+1) + str(ss_row) + '/' +\
                                                         ssCol(st_tml+1) + str(ss_row - r)
            ss.cell(row=ss_row, column=st_cap+1).number_format = '#,##0.0%'
            ss_re_row = ss_row
            ss_sto_row = -1
            # if storage
            if ns_sto_sum != '':
                ss_row += 1
                ss.cell(row=ss_row, column=1).value = title + 'Storage %age'
                ss.cell(row=ss_row, column=st_tml+1).value = '=' + ns_sto_sum[1:]
                ss.cell(row=ss_row, column=st_tml+1).number_format = '#,##0'
                ss.cell(row=ss_row, column=st_cap+1).value = '=(' + ns_sto_sum[1:] + ')/' + ssCol(st_tml+1) + \
                                                             str(ss_row - r - 1)
                ss.cell(row=ss_row, column=st_cap+1).number_format = '#,##0.0%'
                ss_sto_row = ss_row
            # now do the LCOE and LCOE with CO2 stuff
            if base_row == '4':
                base_col = 'C'
                if ss_sto_row >= 0:
                    for rw in range(ss_re_fst_row, ss_re_lst_row + 1):
                        ss.cell(row=rw, column=st_lco+1).value = '=IF(AND(' + ssCol(st_lcg+1) + str(rw) + '<>"",' + \
                                ssCol(st_lcg+1) + str(rw) + '>0),' + \
                                ssCol(st_cst+1) + str(rw) + '/(' + ssCol(st_tml+1) + str(rw) + '+(' + \
                                ssCol(st_tml+1) + '$' + str(ss_sto_row) + '*' + ssCol(st_tml+1) + str(rw) + \
                                ')/' + ssCol(st_tml+1) + '$' + str(ss_re_row) + '),"")'
                        ss.cell(row=rw, column=st_lco+1).number_format = '$#,##0.00'
                        if self.carbon_price > 0:
                            ss.cell(row=rw, column=st_lcc+1).value = '=IF(AND(' + ssCol(st_emc+1) + str(rw) + '<>"",' + \
                                    ssCol(st_emc+1) + str(rw) + '>0),(' + \
                                    ssCol(st_cst+1) + str(rw) + '+' + ssCol(st_emc+1) + str(rw) + ')/(' + \
                                    ssCol(st_tml+1) + str(rw) + '+(' + ssCol(st_tml+1) + '$' + str(ss_sto_row) + \
                                    '*' + ssCol(st_tml+1) + str(rw) + ')/' + ssCol(st_tml+1) + '$' + \
                                    str(ss_re_row) + '),"")'
                            ss.cell(row=rw, column=st_lcc+1).number_format = '$#,##0.00'
                else:
                    for rw in range(ss_re_fst_row, ss_re_lst_row):
                        ss.cell(row=rw, column=st_lco+1).value = '=IF(' + ssCol(st_lcg+1) + str(rw) + '>0,' + \
                                ssCol(st_cst+1) + str(rw) + '/' + ssCol(st_tml+1) + str(rw) + '),"")'
                        ss.cell(row=rw, column=st_lco+1).number_format = '$#,##0.00'
                        if self.carbon_price > 0:
                            ss.cell(row=rw, column=st_lcc+1).value = '=IF(AND(' + ssCol(st_emc+1) + str(rw) + '<>"",' + \
                                    ssCol(st_emc+1) + str(rw) + '>0),(' + \
                                    ssCol(st_cst+1) + str(rw) + ssCol(st_emc+1) + str(rw) + ')/' + \
                                    ssCol(st_tml+1) + str(rw) + '),"")'
                            ss.cell(row=rw, column=st_lcc+1).number_format = '$#,##0.00'
                for rw in range(ss_re_lst_row + 1, ss_lst_row + 1):
                    ss.cell(row=rw, column=st_lco+1).value = '=IF(AND(' + ssCol(st_tml+1) + str(rw) + '<>"",' + \
                                    ssCol(st_tml+1) + str(rw) + '>0),' + ssCol(st_cst+1) + str(rw) + \
                                                             '/' + ssCol(st_tml+1) + str(rw) + ',"")'
                    ss.cell(row=rw, column=st_lco+1).number_format = '$#,##0.00'
                    if self.carbon_price > 0:
                        ss.cell(row=rw, column=st_lcc+1).value = '=IF(AND(' + ssCol(st_emc+1) + str(rw) + '<>"",' + \
                                    ssCol(st_emc+1) + str(rw) + '>0),(' + \
                                ssCol(st_cst+1) + str(rw) + '+' + ssCol(st_emc+1) + str(rw) + ')/' + \
                                ssCol(st_tml+1) + str(rw) + ',"")'
                        ss.cell(row=rw, column=st_lcc+1).number_format = '$#,##0.00'
            else:
                base_col = ssCol(next_col)
                for rw in range(ul_fst_row, ul_lst_row + 1):
                    ss.cell(row=rw, column=st_lco+1).value = '=' + ssCol(st_cst+1) + str(rw) + \
                                                             '/' + ssCol(st_tml+1) + str(rw)
                    ss.cell(row=rw, column=st_lco+1).number_format = '$#,##0.00'
                    if self.carbon_price > 0:
                        ss.cell(row=rw, column=st_lcc+1).value = '=(' + ssCol(st_cst+1) + str(rw) + \
                            '+' + ssCol(st_emc+1) + str(rw) + ')/' + ssCol(st_tml+1) + str(rw)
                        ss.cell(row=rw, column=st_lcc+1).number_format = '$#,##0.00'
            ss_row += 2
            ss.cell(row=ss_row, column=1).value = title + 'Load Analysis'
            ss.cell(row=ss_row, column=1).font = bold
            ss_row += 1
            ss.cell(row=ss_row, column=1).value = title + 'Load met'
      ##      lm_row = ss_row
      #      if self.surplus_sign < 0:
      #          addsub = ')+' + base_col
      #      else:
      #          addsub = ')-' + base_col
      #      ss.cell(row=ss_row, column=st_tml+1).value = '=SUMIF(Detail!' + last_col + str(hrows) + ':Detail!' \
      #          + last_col + str(hrows + 8759) + ',"' + sf_test[0] + '=0",Detail!C' + str(hrows) \
      #          + ':Detail!C' + str(hrows + 8759) + ')+SUMIF(Detail!' + last_col + str(hrows) + ':Detail!' \
      #          + last_col + str(hrows + 8759) + ',"' + sf_test[1] + '0",Detail!C' + str(hrows) + ':Detail!C' \
      #          + str(hrows + 8759) + addsub + str(ss_row + 1)
            ss.cell(row=ss_row, column=st_tml+1).value = '=Detail!' + base_col + str(sum_row) + '-' + base_col + str(ss_row + 1)
            ss.cell(row=ss_row, column=st_tml+1).number_format = '#,##0'
            ss.cell(row=ss_row, column=st_cap+1).value = '=' + ssCol(st_tml+1) + str(ss_row) + '/' + ssCol(st_tml+1) + \
                                                         str(ss_row + 2)
            ss.cell(row=ss_row, column=st_cap+1).number_format = '#,##0.0%'
            ss_row += 1
            ss.cell(row=ss_row, column=1).value = title + 'Shortfall'
            sf_text = 'SUMIF(Detail!' + last_col + str(hrows) + ':Detail!' + last_col \
                      + str(hrows + 8759) + ',"' + sf_test[0] + '0",Detail!' + last_col \
                      + str(hrows) + ':Detail!' + last_col + str(hrows + 8759) + ')'
            if self.surplus_sign > 0:
                ss.cell(row=ss_row, column=st_tml+1).value = '=-' + sf_text
            else:
                ss.cell(row=ss_row, column=st_tml+1).value = '=' + sf_text
            ss.cell(row=ss_row, column=st_tml+1).number_format = '#,##0'
            ss.cell(row=ss_row, column=st_cap+1).value = '=' + ssCol(st_tml+1) + str(ss_row) + '/' + ssCol(st_tml+1) + \
                                                         str(ss_row + 1)
            ss.cell(row=ss_row, column=st_cap+1).number_format = '#,##0.0%'
            ss_row += 1
            ld_row = ss_row
            load_mult = ''
            try:
                mult = round(technology_attributes['Load'].multiplier, 3)
                if mult != 1:
                    load_mult = ' x ' + str(mult)
            except:
                pass
            ss.cell(row=ss_row, column=1).value = 'Total ' + title + 'Load - ' + year + load_mult
            ss.cell(row=ss_row, column=1).font = bold
            ss.cell(row=ss_row, column=st_tml+1).value = '=SUM(' + ssCol(st_tml+1) + str(ss_row - 2) + ':' + \
                                                         ssCol(st_tml+1) + str(ss_row - 1) + ')'
            ss.cell(row=ss_row, column=st_tml+1).number_format = '#,##0'
            ss.cell(row=ss_row, column=st_tml+1).font = bold
            ss.cell(row=ss_row, column=st_max+1).value = '=Detail!' + base_col + str(max_row)
            ss.cell(row=ss_row, column=st_max+1).number_format = '#,##0.00'
            ss.cell(row=ss_row, column=st_max+1).font = bold
            ss.cell(row=ss_row, column=st_bal+1).value = '=" ("&OFFSET(Detail!B' + str(hrows - 1) + ',MATCH(Detail!' + \
                    base_col + str(max_row) + ',Detail!' + base_col + str(hrows) + ':Detail!' + base_col + \
                    str(hrows + 8759) + ',0),0)&")"'
            ss_row += 1
            ss.cell(row=ss_row, column=1).value = 'RE %age of Total ' + title + 'Load'
            ss.cell(row=ss_row, column=1).font = bold
            if ns_sto_sum == '':
                ss.cell(row=ss_row, column=st_cap+1).value = ssCol(st_tml+1) + str(ss_re_row - 1) + \
                                                             '/' + ssCol(st_tml+1) + str(ss_row - 1)
            else:
                ss.cell(row=ss_row, column=st_cap+1).value = '=(' + ssCol(st_tml+1) + str(ss_re_row) + '+' + \
                                                             ssCol(st_tml+1) + str(ss_sto_row) + ')/' + \
                                                             ssCol(st_tml+1) + str(ss_row - 1)
            ss.cell(row=ss_row, column=st_cap+1).number_format = '#,##0.0%'
            ss.cell(row=ss_row, column=st_cap+1).font = bold
            ss_row += 2
            if ns_loss_sum != '':
                ss.cell(row=ss_row, column=1).value = title + 'Storage Losses'
                ss.cell(row=ss_row, column=st_sub+1).value = '=' + ns_loss_sum[1:]
                ss.cell(row=ss_row, column=st_sub+1).number_format = '#,##0'
                ss_row += 1
            ss.cell(row=ss_row, column=1).value = title + 'Surplus'
            sf_text = 'SUMIF(Detail!' + last_col + str(hrows) + ':Detail!' + last_col \
                      + str(hrows + 8759) + ',"' + sf_test[1] + '0",Detail!' + last_col + str(hrows) \
                      + ':Detail!' + last_col + str(hrows + 8759) + ')'
            if self.surplus_sign < 0:
                ss.cell(row=ss_row, column=st_sub+1).value = '=-' + sf_text
            else:
                ss.cell(row=ss_row, column=st_sub+1).value = '=' + sf_text
            ss.cell(row=ss_row, column=st_sub+1).number_format = '#,##0'
            ss.cell(row=ss_row, column=st_cap+1).value = '=' + ssCol(st_sub+1) + str(ss_row) + '/' + ssCol(st_tml+1) + str(ld_row)
            ss.cell(row=ss_row, column=st_cap+1).number_format = '#,##0.0%'
            max_short = [0, 0]
            for h in range(len(shortfall)):
                if shortfall[h] > max_short[1]:
                    max_short[0] = h
                    max_short[1] = shortfall[h]
            if max_short[1] > 0:
                ss_row += 1
                ss.cell(row=ss_row, column=1).value = 'Largest ' + title + 'Shortfall:'
                ss.cell(row=ss_row, column=st_sub+1).value = '=Detail!' + last_col + str(hrows + max_short[0])
                ss.cell(row=ss_row, column=st_sub+1).number_format = '#,##0.00'
                ss.cell(row=ss_row, column=st_cfa+1).value = '=" ("&OFFSET(Detail!B' + str(hrows - 1) + \
                        ',MATCH(' + ssCol(st_sub+1) + str(ss_row) + ',Detail!' + last_col + str(hrows) + \
                        ':Detail!' + last_col + str(hrows + 8759) + ',0),0)&")"'
            return ss_row, ss_re_row

    # The "guts" of Powermatch processing. Have a single calculation algorithm
    # for Summary, Powermatch (detail), and Optimise. The detail makes it messy
    # Note: For Batch load_and_supply is reused so don't update it in matchSupplytoLoad
        self.files = files
        self.sheets = sheets
        the_days = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31]
        if self.surplus_sign < 0:
            sf_test = ['>', '<']
            sf_sign = ['+', '-']
        else:
            sf_test = ['<', '>']
            sf_sign = ['-', '+']
        sp_cols = []
        sp_cap = []
        shortfall = [0.] * 8760
        re_tml_sum = 0. # keep tabs on how much RE is used
        start_time = time.time()
        do_zone = False # could pass as a parameter
        max_lifetime = 0
        # find max. lifetime years for all technologies selected
        for key in technology_attributes.keys():
            if key == 'Load'or key == 'Total':
                continue
            if technology_attributes[key].capacity * technology_attributes[key].multiplier > 0:
             #   gen = key.split('.')[-1]
                gen = technology_attributes[key].generator
                max_lifetime = max(max_lifetime, self.generators[gen].lifetime)
        for key in technology_attributes.keys():
            if key.find('.') > 0:
                do_zone = True
                break
        underlying_facs = []
        undercol = [] * len(self.underlying)
        operational_facs = []
        fac_tml = {}
        for fac in re_order:
            if fac == 'Load':
                continue
            fac_tml[fac] = 0.
            if fac in self.operational:
              #  operational_facs.append(fac)
                continue
            if fac.find('.') > 0:
                if fac[fac.find('.') + 1:] in self.underlying:
                    underlying_facs.append(fac)
                    continue
            elif fac in self.underlying:
                underlying_facs.append(fac)
                continue
        load_col = technology_attributes['Load'].col
        for h in range(len(load_and_supply[load_col])):
            load_h = load_and_supply[load_col][h] * technology_attributes['Load'].multiplier
            shortfall[h] = load_h
            for fac in fac_tml.keys():
                if fac in underlying_facs:
                    continue
                shortfall[h] -= load_and_supply[technology_attributes[fac].col][h] * technology_attributes[fac].multiplier
            if shortfall[h] >= 0:
                alloc = 1.
            else:
                alloc = load_h / (load_h - shortfall[h])
            for fac in fac_tml.keys():
                if fac in underlying_facs:
                    fac_tml[fac] += load_and_supply[technology_attributes[fac].col][h] * technology_attributes[fac].multiplier
                else:
                    fac_tml[fac] += load_and_supply[technology_attributes[fac].col][h] * technology_attributes[fac].multiplier * alloc
            line = ''
        fac_tml_sum = 0
        for fac in fac_tml.keys():
            fac_tml_sum += fac_tml[fac]
        if self.show_correlation:
            col = technology_attributes['Load'].col
            if technology_attributes['Load'].multiplier == 1:
                df1 = load_and_supply[col]
            else:
                tgt = []
                for h in range(len(load_and_supply[col])):
                    tgt.append(load_and_supply[col][h] * technology_attributes['Load'].multiplier)
                df1 = tgt
            corr_src = []
            for h in range(len(shortfall)):
                if shortfall[h] < 0:
                    corr_src.append(load_and_supply[col][h])
                else:
                    corr_src.append(load_and_supply[col][h] - shortfall[h])
            try:
                corr = np.corrcoef(df1, corr_src)
                if np.isnan(corr.item((0, 1))):
                    corr = 0
                else:
                    corr = corr.item((0, 1))
            except:
                corr = 0
            corr_data = [['Correlation To Load']]
            corr_data.append(['RE Contribution', corr])
        else:
            corr_data = None
        if option == D:
            wb = oxl.Workbook()
            ns = wb.active
            ns.title = 'Detail'
            normal = oxl.styles.Font(name='Arial')
            bold = oxl.styles.Font(name='Arial', bold=True)
            ss = wb.create_sheet('Summary', 0)
            ns_re_sum = '=('
            ns_tml_sum = '=('
            ns_sto_sum = ''
            ns_loss_sum = ''
            ns_not_sum = ''
            cap_row = 1
            ns.cell(row=cap_row, column=2).value = 'Capacity (MW/MWh)' #headers[1].replace('\n', ' ')
            ss.row_dimensions[3].height = 40
            ss.cell(row=3, column=st_fac+1).value = headers[st_fac] # facility
            ss.cell(row=3, column=st_cap+1).value = headers[st_cap] # capacity
            ini_row = 2
            ns.cell(row=ini_row, column=2).value = 'Initial Capacity'
            tml_row = 3
            ns.cell(row=tml_row, column=2).value = headers[st_tml].replace('\n', ' ')
            ss.cell(row=3, column=st_tml+1).value = headers[st_tml] # to meet load
            sum_row = 4
            ns.cell(row=sum_row, column=2).value = headers[st_sub].replace('\n', ' ')
            ss.cell(row=3, column=st_sub+1).value = headers[st_sub] # subtotal MWh
            cf_row = 5
            ns.cell(row=cf_row, column=2).value = headers[st_cfa].replace('\n', ' ')
            ss.cell(row=3, column=st_cfa+1).value = headers[st_cfa] # CF
            cost_row = 6
            ns.cell(row=cost_row, column=2).value = headers[st_cst].replace('\n', ' ')
            ss.cell(row=3, column=st_cst+1).value = headers[st_cst] # Cost / yr
            lcoe_row = 7
            ns.cell(row=lcoe_row, column=2).value = headers[st_lcg].replace('\n', ' ')
            ss.cell(row=3, column=st_lcg+1).value = headers[st_lcg] # LCOG
            ss.cell(row=3, column=st_lco+1).value = headers[st_lco] # LCOE
            emi_row = 8
            ns.cell(row=emi_row, column=2).value = headers[st_emi].replace('\n', ' ')
            ss.cell(row=3, column=st_emi+1).value = headers[st_emi] # emissions
            ss.cell(row=3, column=st_emc+1).value = headers[st_emc] # emissions cost
            ss.cell(row=3, column=st_lcc+1).value = headers[st_lcc] # LCOE with CO2
            ss.cell(row=3, column=st_max+1).value = headers[st_max] # max. MWh
            ss.cell(row=3, column=st_bal+1).value = headers[st_bal] # max. balance
            ss.cell(row=3, column=st_cac+1).value = headers[st_cac] # capital cost
            ss.cell(row=3, column=st_lic+1).value = headers[st_lic] # lifetime cost
            ss.cell(row=3, column=st_lie+1).value = headers[st_lie] # lifetime emissions
            ss.cell(row=3, column=st_lec+1).value = headers[st_lec] # lifetime emissions cost
            ss.cell(row=3, column=st_are+1).value = headers[st_are] # area
            ss.cell(row=3, column=st_rlc+1).value = headers[st_rlc] # reference lcoe
            ss.cell(row=3, column=st_rcf+1).value = headers[st_rcf] # reference cf
            ss_row = 3
            ss_re_fst_row = 4
            fall_row = 9
            ns.cell(row=fall_row, column=2).value = 'Shortfall periods'
            max_row = 10
            ns.cell(row=max_row, column=2).value = 'Maximum (MW/MWh)'
            hrs_row = 11
            ns.cell(row=hrs_row, column=2).value = 'Hours of usage'
            if do_zone:
                zone_row = 12
                what_row = 13
                hrows = 14
                ns.cell(row=zone_row, column=1).value = 'Zone'
            else:
                what_row = 12
                hrows = 13
            ns.cell(row=what_row, column=1).value = 'Hour'
            ns.cell(row=what_row, column=2).value = 'Period'
            ns.cell(row=what_row, column=3).value = 'Load'
            ns.cell(row=sum_row, column=3).value = '=SUM(' + ssCol(3) + str(hrows) + \
                                                   ':' + ssCol(3) + str(hrows + 8759) + ')'
            ns.cell(row=sum_row, column=3).number_format = '#,##0'
            ns.cell(row=max_row, column=3).value = '=MAX(' + ssCol(3) + str(hrows) + \
                                                   ':' + ssCol(3) + str(hrows + 8759) + ')'
            ns.cell(row=max_row, column=3).number_format = '#,##0.00'
            o = 4
            col = 3
            # hour, period
            for row in range(hrows, 8760 + hrows):
                ns.cell(row=row, column=1).value = row - hrows + 1
                ns.cell(row=row, column=2).value = format_period(row - hrows)
            # and load
            load_col = technology_attributes['Load'].col
            if technology_attributes['Load'].multiplier == 1:
                for row in range(hrows, 8760 + hrows):
                    ns.cell(row=row, column=3).value = load_and_supply[load_col][row - hrows]
                    ns.cell(row=row, column=col).number_format = '#,##0.00'
            else:
                for row in range(hrows, 8760 + hrows):
                    ns.cell(row=row, column=3).value = load_and_supply[load_col][row - hrows] * \
                            technology_attributes['Load'].multiplier
                    ns.cell(row=row, column=col).number_format = '#,##0.00'
            # here we're processing renewables (so no storage)
            for fac in re_order:
                if fac == 'Load':
                    continue
                if fac in underlying_facs:
                    continue
                if technology_attributes[fac].col <= 0:
                    continue
                ss_row += 1
                col = do_detail(fac, col, ss_row)
                ns_tml_sum, ns_re_sum = do_detail_summary(fac, col, ss_row, ns_tml_sum, ns_re_sum)
            ss_re_lst_row = ss_row
            col += 1
            shrt_col = col
            ns.cell(row=fall_row, column=shrt_col).value = '=COUNTIF(' + ssCol(shrt_col) \
                            + str(hrows) + ':' + ssCol(shrt_col) + str(hrows + 8759) + \
                            ',"' + sf_test[0] + '0")'
            ns.cell(row=fall_row, column=shrt_col).number_format = '#,##0'
            ns.cell(row=what_row, column=shrt_col).value = 'Shortfall (' + sf_sign[0] \
                    + ') /\nSurplus (' + sf_sign[1] + ')'
            ns.cell(row=max_row, column=shrt_col).value = '=MAX(' + ssCol(shrt_col) + str(hrows) + \
                                           ':' + ssCol(shrt_col) + str(hrows + 8759) + ')'
            ns.cell(row=max_row, column=shrt_col).number_format = '#,##0.00'
            for col in range(3, shrt_col + 1):
                ns.cell(row=what_row, column=col).alignment = oxl.styles.Alignment(wrap_text=True,
                        vertical='bottom', horizontal='center')
                ns.cell(row=row, column=shrt_col).value = shortfall[row - hrows] * -self.surplus_sign
                for col in range(3, shrt_col + 1):
                    ns.cell(row=row, column=col).number_format = '#,##0.00'
            for row in range(hrows, 8760 + hrows):
                ns.cell(row=row, column=shrt_col).value = shortfall[row - hrows] * -self.surplus_sign
                ns.cell(row=row, column=col).number_format = '#,##0.00'
            col = shrt_col + 1
            ns.cell(row=tml_row, column=col).value = '=SUM(' + ssCol(col) + str(hrows) + \
                                                   ':' + ssCol(col) + str(hrows + 8759) + ')'
            ns.cell(row=tml_row, column=col).number_format = '#,##0'
            ns.cell(row=max_row, column=col).value = '=MAX(' + ssCol(col) + str(hrows) + \
                                           ':' + ssCol(col) + str(hrows + 8759) + ')'
            ns.cell(row=max_row, column=col).number_format = '#,##0.00'
            ns.cell(row=hrs_row, column=col).value = '=COUNTIF(' + ssCol(col) + str(hrows) + \
                                           ':' + ssCol(col) + str(hrows + 8759) + ',">0")'
            ns.cell(row=hrs_row, column=col).number_format = '#,##0'
            ns.cell(row=what_row, column=col).value = 'RE Contrib.\nto Load'
            ns.cell(row=what_row, column=col).alignment = oxl.styles.Alignment(wrap_text=True,
                    vertical='bottom', horizontal='center')
            for row in range(hrows, 8760 + hrows):
                if shortfall[row - hrows] < 0:
                    if technology_attributes['Load'].multiplier == 1:
                        rec = load_and_supply[load_col][row - hrows]
                    else:
                        rec = load_and_supply[load_col][row - hrows] * technology_attributes['Load'].multiplier
                else:
                    if technology_attributes['Load'].multiplier == 1:
                        rec = load_and_supply[load_col][row - hrows] - shortfall[row - hrows]
                    else:
                        rec = load_and_supply[load_col][row - hrows] * technology_attributes['Load'].multiplier - \
                              shortfall[row - hrows]
                ns.cell(row=row, column=col).value = rec
               # the following formula will do the same computation
               # ns.cell(row=row, column=col).value = '=IF(' + ssCol(shrt_col) + str(row) + '>0,' + \
               #                            ssCol(3) + str(row) + ',' + ssCol(3) + str(row) + \
               #                            '+' + ssCol(shrt_col) + str(row) + ')'
                ns.cell(row=row, column=col).number_format = '#,##0.00'
          #  shrt_col += 1
           # col = shrt_col + 1
            ul_re_sum = ns_re_sum
            ul_tml_sum = ns_tml_sum
            nsul_sums = ['C']
            nsul_sum_cols = [3]
            for fac in underlying_facs:
                if technology_attributes[fac].capacity * technology_attributes[fac].multiplier == 0:
                    continue
                col = do_detail(fac, col, -1)
                nsul_sums.append(ssCol(col))
                nsul_sum_cols.append(col)
            if col > shrt_col + 1: # underlying
                col += 1
                ns.cell(row=what_row, column=col).value = 'Underlying\nLoad'
                ns.cell(row=what_row, column=col).alignment = oxl.styles.Alignment(wrap_text=True,
                        vertical='bottom', horizontal='center')
                ns.cell(row=sum_row, column=col).value = '=SUM(' + ssCol(col) + str(hrows) + \
                                                         ':' + ssCol(col) + str(hrows + 8759) + ')'
                ns.cell(row=sum_row, column=col).number_format = '#,##0'
                ns.cell(row=max_row, column=col).value = '=MAX(' + ssCol(col) + str(hrows) + \
                                                         ':' + ssCol(col) + str(hrows + 8759) + ')'
                ns.cell(row=max_row, column=col).number_format = '#,##0.00'
                for row in range(hrows, 8760 + hrows):
                    txt = '='
                    for c in nsul_sums:
                        txt += c + str(row) + '+'
                    ns.cell(row=row, column=col).value = txt[:-1]
                    ns.cell(row=row, column=col).number_format = '#,##0.00'
            next_col = col
            col += 1
        else: # O, O1, B, T
            sp_data = []
            sp_load = 0. # load from load curve
            hrows = 10
            load_max = 0
            load_hr = 0
            tml = 0.
            try:
                load_col = technology_attributes['Load'].col
            except:
                load_col = 0
            if (option == B or option == T) and len(underlying_facs) > 0:
                load_facs = underlying_facs[:]
                load_facs.insert(0, 'Load')
                for h in range(len(load_and_supply[load_col])):
                    amt = 0
                    for fac in load_facs:
                        amt += load_and_supply[technology_attributes[fac].col][h] * technology_attributes[fac].multiplier
                    if amt > load_max:
                        load_max = amt
                        load_hr = h
                    sp_load += amt
                underlying_facs = []
            else:
                fac = 'Load'
                sp_load = sum(load_and_supply[load_col]) * technology_attributes[fac].multiplier
                for h in range(len(load_and_supply[load_col])):
                    amt = load_and_supply[load_col][h] * technology_attributes[fac].multiplier
                    if amt > load_max:
                        load_max = amt
                        load_hr = h
            for fac in re_order:
                if fac == 'Load' or fac in underlying_facs:
                    continue
                if technology_attributes[fac].capacity * technology_attributes[fac].multiplier == 0:
                    continue
                sp_d = [' '] * len(headers)
                sp_d[st_fac] = fac
                sp_d[st_cap] = technology_attributes[fac].capacity * technology_attributes[fac].multiplier
                try:
                    sp_d[st_tml] = fac_tml[fac]
                except:
                    pass
                sp_d[st_sub] = sum(load_and_supply[technology_attributes[fac].col]) * technology_attributes[fac].multiplier
                sp_d[st_max] = max(load_and_supply[technology_attributes[fac].col]) * technology_attributes[fac].multiplier
                sp_data.append(sp_d)
       #     for h in range(len(shortfall)):
        #        if shortfall[h] < 0:
         #           tml += load_and_supply[load_col][h] * technology_attributes['Load'].multiplier
          #      else:
           #         tml += load_and_supply[load_col][h] * technology_attributes['Load'].multiplier - shortfall[h]
        if option not in [O, O1, B, T]:
            self.listener.progress_bar.setValue(6)
            if self.event_callback:
                self.event_callback()
        storage_names = []
        # find any minimum generation for generators
        short_taken = {}
        short_taken_tot = 0
        for gen in dispatch_order:
            if technology_attributes[gen].tech_type == 'G': # generators
                try:
                    const = self.generators[gen].constraint
                except:
                    try:
                        g2 = gen[gen.find('.') + 1:]
                        const = self.generators[g2].constraint
                    except:
                        continue
                if self.constraints[const].capacity_min != 0:
                    try:
                        short_taken[gen] = technology_attributes[gen].capacity * technology_attributes[gen].multiplier * \
                            self.constraints[const].capacity_min
                    except:
                        short_taken[gen] = technology_attributes[gen].capacity * \
                            self.constraints[const].capacity_min
                    short_taken_tot += short_taken[gen]
                    for row in range(8760):
                        shortfall[row] = shortfall[row] - short_taken[gen]
        tot_sto_loss = 0.
        for gen in dispatch_order:
         #   min_after = [0, 0, -1, 0, 0, 0] # initial, low balance, period, final, low after, period
         #  Min_after is there to see if storage is as full at the end as at the beginning
            try:
                capacity = technology_attributes[gen].capacity * technology_attributes[gen].multiplier
            except:
                try:
                    capacity = technology_attributes[gen].capacity
                except:
                    continue
            if gen not in self.generators.keys():
                continue
            if self.generators[gen].constraint in self.constraints and \
              self.constraints[self.generators[gen].constraint].category == 'Storage': # storage
                storage_names.append(gen)
                storage = [0., 0., 0., 0.] # capacity, initial, min level, max drain
                storage[0] = capacity
                if option == D:
                    ns.cell(row=cap_row, column=col + 2).value = capacity
                    ns.cell(row=cap_row, column=col + 2).number_format = '#,##0.00'
                try:
                    storage[1] = self.generators[gen].initial * technology_attributes[gen].multiplier
                except:
                    storage[1] = self.generators[gen].initial
                if self.constraints[self.generators[gen].constraint].capacity_min > 0:
                    storage[2] = capacity * self.constraints[self.generators[gen].constraint].capacity_min
                if self.constraints[self.generators[gen].constraint].capacity_max > 0:
                    storage[3] = capacity * self.constraints[self.generators[gen].constraint].capacity_max
                else:
                    storage[3] = capacity
                recharge = [0., 0.] # cap, loss
                if self.constraints[self.generators[gen].constraint].recharge_max > 0:
                    recharge[0] = capacity * self.constraints[self.generators[gen].constraint].recharge_max
                else:
                    recharge[0] = capacity
                if self.constraints[self.generators[gen].constraint].recharge_loss > 0:
                    recharge[1] = self.constraints[self.generators[gen].constraint].recharge_loss
                discharge = [0., 0.] # cap, loss
                if self.constraints[self.generators[gen].constraint].discharge_max > 0:
                    discharge[0] = capacity * self.constraints[self.generators[gen].constraint].discharge_max
                if self.constraints[self.generators[gen].constraint].discharge_loss > 0:
                    discharge[1] = self.constraints[self.generators[gen].constraint].discharge_loss
                if self.constraints[self.generators[gen].constraint].parasitic_loss > 0:
                    parasite = self.constraints[self.generators[gen].constraint].parasitic_loss / 24.
                else:
                    parasite = 0.
                in_run = [False, False]
                min_runtime = self.constraints[self.generators[gen].constraint].min_runtime
                in_run[0] = True # start off in_run
                if min_runtime > 0 and self.generators[gen].initial == 0:
                    in_run[0] = False
                warm_time = self.constraints[self.generators[gen].constraint].warm_time
                storage_carry = storage[1] # self.generators[gen].initial
                if option == D:
                    ns.cell(row=ini_row, column=col + 2).value = storage_carry
                    ns.cell(row=ini_row, column=col + 2).number_format = '#,##0.00'
                storage_bal = []
                storage_can = 0.
                use_max = [0, None]
                sto_max = storage_carry
                for row in range(8760):
                    storage_loss = 0.
                    storage_losses = 0.
                    if storage_carry > 0:
                        loss = storage_carry * parasite
                        # for later: record parasitic loss
                        storage_carry = storage_carry - loss
                        storage_losses -= loss
                    if shortfall[row] < 0:  # excess generation
                        if min_runtime > 0:
                            in_run[0] = False
                        if warm_time > 0:
                            in_run[1] = False
                        can_use = - (storage[0] - storage_carry) * (1 / (1 - recharge[1]))
                        if can_use < 0: # can use some
                            if shortfall[row] > can_use:
                                can_use = shortfall[row]
                            if can_use < - recharge[0] * (1 / (1 - recharge[1])):
                                can_use = - recharge[0]
                        else:
                            can_use = 0.
                        # for later: record recharge loss
                        storage_losses += can_use * recharge[1]
                        storage_carry -= (can_use * (1 - recharge[1]))
                        shortfall[row] -= can_use
                        if corr_data is not None:
                            corr_src[row] += can_use
                    else: # shortfall
                        if min_runtime > 0 and shortfall[row] > 0:
                            if not in_run[0]:
                                if row + min_runtime <= 8759:
                                    for i in range(row + 1, row + min_runtime + 1):
                                        if shortfall[i] <= 0:
                                            break
                                    else:
                                        in_run[0] = True
                        if in_run[0]:
                            can_use = shortfall[row] * (1 / (1 - discharge[1]))
                            can_use = min(can_use, discharge[0])
                            if can_use > storage_carry - storage[2]:
                                can_use = storage_carry - storage[2]
                            if warm_time > 0 and not in_run[1]:
                                in_run[1] = True
                                can_use = can_use * (1 - warm_time)
                        else:
                            can_use = 0
                        if can_use > 0:
                            storage_loss = can_use * discharge[1]
                            storage_losses -= storage_loss
                            storage_carry -= can_use
                            can_use = can_use - storage_loss
                            shortfall[row] -= can_use
                            if corr_data is not None:
                                corr_src[row] += can_use
                            if storage_carry < 0:
                                storage_carry = 0
                        else:
                            can_use = 0.
                    if can_use < 0:
                        if use_max[1] is None or can_use < use_max[1]:
                            use_max[1] = can_use
                    elif can_use > use_max[0]:
                        use_max[0] = can_use
                    storage_bal.append(storage_carry)
                    if storage_bal[-1] > sto_max:
                        sto_max = storage_bal[-1]
                    if option == D:
                        if can_use > 0:
                            ns.cell(row=row + hrows, column=col).value = 0
                            ns.cell(row=row + hrows, column=col + 2).value = can_use * self.surplus_sign
                        else:
                            ns.cell(row=row + hrows, column=col).value = can_use * -self.surplus_sign
                            ns.cell(row=row + hrows, column=col + 2).value = 0
                        ns.cell(row=row + hrows, column=col + 1).value = storage_losses
                        ns.cell(row=row + hrows, column=col + 3).value = storage_carry
                        ns.cell(row=row + hrows, column=col + 4).value = (shortfall[row] + short_taken_tot) * -self.surplus_sign
                        for ac in range(5):
                            ns.cell(row=row + hrows, column=col + ac).number_format = '#,##0.00'
                            ns.cell(row=max_row, column=col + ac).value = '=MAX(' + ssCol(col + ac) + \
                                    str(hrows) + ':' + ssCol(col + ac) + str(hrows + 8759) + ')'
                            ns.cell(row=max_row, column=col + ac).number_format = '#,##0.00'
                    else:
                        tot_sto_loss += storage_losses
                        if can_use > 0:
                            storage_can += can_use
                if option == D:
                    ns.cell(row=sum_row, column=col).value = '=SUMIF(' + ssCol(col) + \
                            str(hrows) + ':' + ssCol(col) + str(hrows + 8759) + ',">0")'
                    ns.cell(row=sum_row, column=col).number_format = '#,##0'
                    ns.cell(row=sum_row, column=col + 1).value = '=SUMIF(' + ssCol(col + 1) + \
                            str(hrows) + ':' + ssCol(col + 1) + str(hrows + 8759) + ',"<0")'
                    ns.cell(row=sum_row, column=col + 1).number_format = '#,##0'
                    ns.cell(row=sum_row, column=col + 2).value = '=SUMIF(' + ssCol(col + 2) + \
                            str(hrows) + ':' + ssCol(col + 2) + str(hrows + 8759) + ',">0")'
                    ns.cell(row=sum_row, column=col + 2).number_format = '#,##0'
                    ns.cell(row=cf_row, column=col + 2).value = '=IF(' + ssCol(col + 2) + str(cap_row) + '>0,' + \
                            ssCol(col + 2) + str(sum_row) + '/' + ssCol(col + 2) + '1/8760,"")'
                    ns.cell(row=cf_row, column=col + 2).number_format = '#,##0.0%'
                    ns.cell(row=max_row, column=col).value = '=MAX(' + ssCol(col) + \
                            str(hrows) + ':' + ssCol(col) + str(hrows + 8759) + ')'
                    ns.cell(row=max_row, column=col).number_format = '#,##0.00'
                    ns.cell(row=hrs_row, column=col + 2).value = '=COUNTIF(' + ssCol(col + 2) + \
                            str(hrows) + ':' + ssCol(col + 2) + str(hrows + 8759) + ',">0")'
                    ns.cell(row=hrs_row, column=col + 2).number_format = '#,##0'
                    ns.cell(row=hrs_row, column=col + 3).value = '=' + ssCol(col + 2) + \
                            str(hrs_row) + '/8760'
                    ns.cell(row=hrs_row, column=col + 3).number_format = '#,##0.0%'
                    col += 5
                else:
                    if storage[0] == 0:
                        continue
               #     tml_tot += storage_can
                    sp_d = [' '] * len(headers)
                    sp_d[st_fac] = gen
                    sp_d[st_cap] = storage[0]
                    sp_d[st_tml] = storage_can
                    sp_d[st_max] = use_max[0]
                    sp_d[st_bal] = sto_max
                    sp_data.append(sp_d)
            else: # generator
                try:
                    if self.constraints[self.generators[gen].constraint].capacity_max > 0:
                        cap_capacity = capacity * self.constraints[self.generators[gen].constraint].capacity_max
                    else:
                        cap_capacity = capacity
                except:
                    cap_capacity = capacity
                if gen in short_taken.keys():
                    for row in range(8760):
                        shortfall[row] = shortfall[row] + short_taken[gen]
                    short_taken_tot -= short_taken[gen]
                    min_gen = short_taken[gen]
                else:
                    min_gen = 0
                if option == D:
                    ns.cell(row=cap_row, column=col).value = capacity
                    ns.cell(row=cap_row, column=col).number_format = '#,##0.00'
                    for row in range(8760):
                        if shortfall[row] >= 0: # shortfall?
                            if shortfall[row] >= cap_capacity:
                                shortfall[row] = shortfall[row] - cap_capacity
                                ns.cell(row=row + hrows, column=col).value = cap_capacity
                            elif shortfall[row] < min_gen:
                                ns.cell(row=row + hrows, column=col).value = min_gen
                                shortfall[row] -= min_gen
                            else:
                                ns.cell(row=row + hrows, column=col).value = shortfall[row]
                                shortfall[row] = 0
                        else:
                            shortfall[row] -= min_gen
                            ns.cell(row=row + hrows, column=col).value = min_gen
                        ns.cell(row=row + hrows, column=col + 1).value = (shortfall[row] + short_taken_tot) * -self.surplus_sign
                        ns.cell(row=row + hrows, column=col).number_format = '#,##0.00'
                        ns.cell(row=row + hrows, column=col + 1).number_format = '#,##0.00'
                    ns.cell(row=sum_row, column=col).value = '=SUM(' + ssCol(col) + str(hrows) + \
                            ':' + ssCol(col) + str(hrows + 8759) + ')'
                    ns.cell(row=sum_row, column=col).number_format = '#,##0'
                    ns.cell(row=cf_row, column=col).value = '=IF(' + ssCol(col) + str(cap_row) + '>0,' + \
                            ssCol(col) + str(sum_row) + '/' + ssCol(col) + str(cap_row) + '/8760,"")'
                    ns.cell(row=cf_row, column=col).number_format = '#,##0.0%'
                    ns.cell(row=max_row, column=col).value = '=MAX(' + ssCol(col) + \
                                str(hrows) + ':' + ssCol(col) + str(hrows + 8759) + ')'
                    ns.cell(row=max_row, column=col).number_format = '#,##0.00'
                    ns.cell(row=hrs_row, column=col).value = '=COUNTIF(' + ssCol(col) + \
                            str(hrows) + ':' + ssCol(col) + str(hrows + 8759) + ',">0")'
                    ns.cell(row=hrs_row, column=col).number_format = '#,##0'
                    ns.cell(row=hrs_row, column=col + 1).value = '=' + ssCol(col) + \
                            str(hrs_row) + '/8760'
                    ns.cell(row=hrs_row, column=col + 1).number_format = '#,##0.0%'
                    col += 2
                else:
                    gen_can = 0.
                    gen_max = 0
                    for row in range(8760):
                        if shortfall[row] >= 0: # shortfall?
                            if shortfall[row] >= cap_capacity:
                                shortfall[row] = shortfall[row] - cap_capacity
                                gen_can += cap_capacity
                                if cap_capacity > gen_max:
                                    gen_max = cap_capacity
                            elif shortfall[row] < min_gen:
                                gen_can += min_gen
                                if min_gen > gen_max:
                                    gen_max = min_gen
                                shortfall[row] -= min_gen
                            else:
                                gen_can += shortfall[row]
                                if shortfall[row] > gen_max:
                                    gen_max = shortfall[row]
                                shortfall[row] = 0
                        else:
                            if min_gen > gen_max:
                                gen_max = min_gen
                            gen_can += min_gen
                            shortfall[row] -= min_gen # ??
                    if capacity == 0:
                        continue
                    sp_d = [' '] * len(headers)
                    sp_d[st_fac] = gen
                    sp_d[st_cap] = capacity
                    sp_d[st_tml] = gen_can
                    sp_d[st_sub] = gen_can
                    sp_d[st_max] = gen_max
                    sp_data.append(sp_d)
#        if option == D: # Currently calculated elsewhere
#            if self.surplus_sign > 0:
#                maxmin = 'MIN'
#            else:
#                maxmin = 'MAX'
#            ns.cell(row=max_row, column=col-1).value = '=' + maxmin + '(' + \
#                    ssCol(col-1) + str(hrows) + ':' + ssCol(col - 1) + str(hrows + 8759) + ')'
#            ns.cell(row=max_row, column=col-1).number_format = '#,##0.00'
        if option not in [O, O1, B, T]:
            self.listener.progress_bar.setValue(8)
            if self.event_callback:
                self.event_callback()
        if corr_data is not None:
            try:
                corr = np.corrcoef(df1, corr_src)
                if np.isnan(corr.item((0, 1))):
                    corr = 0
                else:
                    corr = corr.item((0, 1))
            except:
                corr = 0
            corr_data.append(['RE plus Storage', corr])
            col = technology_attributes['Load'].col
            corr_src = []
            for h in range(len(shortfall)):
                if shortfall[h] < 0:
                    corr_src.append(load_and_supply[col][h])
                else:
                    corr_src.append(load_and_supply[col][h] - shortfall[h])
            try:
                corr = np.corrcoef(df1, corr_src)
                if np.isnan(corr.item((0, 1))):
                    corr = 0
                else:
                    corr = corr.item((0, 1))
            except:
                corr = 0
            corr_data.append(['To Meet Load', corr])
            for c in range(1, len(corr_data)):
                if abs(corr_data[c][1]) < 0.1:
                    corr_data[c].append('None')
                elif abs(corr_data[c][1]) < 0.3:
                    corr_data[c].append('Little if any')
                elif abs(corr_data[c][1]) < 0.5:
                    corr_data[c].append('Low')
                elif abs(corr_data[c][1]) < 0.7:
                    corr_data[c].append('Moderate')
                elif abs(corr_data[c][1]) < 0.9:
                    corr_data[c].append('High')
                else:
                    corr_data[c].append('Very high')
        if option != D:
            load_col = technology_attributes['Load'].col
            cap_sum = 0.
            gen_sum = 0.
            re_sum = 0.
            tml_sum = 0.
            ff_sum = 0.
            sto_sum = 0.
            cost_sum = 0.
            co2_sum = 0.
            co2_cost_sum = 0.
            capex_sum = 0.
            lifetime_sum = 0.
            lifetime_co2_sum = 0.
            lifetime_co2_cost = 0.
            total_area = 0.
            for sp in range(len(sp_data)):
                gen = sp_data[sp][st_fac]
                if gen in storage_names:
                    sto_sum += sp_data[sp][2]
                else:
                    try:
                        gen2 = gen[gen.find('.') + 1:]
                    except:
                        gen2 = gen
                    if gen in tech_names or gen2 in tech_names:
                        re_sum += sp_data[sp][st_sub]
            for sp in range(len(sp_data)):
                gen = sp_data[sp][st_fac]
                if gen in storage_names:
                    ndx = 2
                else:
                    if gen in self.generators.keys():
                        pass
                    else:
                        try:
                            gen = gen[gen.find('.') + 1:]
                        except:
                            pass
                    ndx = 3
                try:
                    if sp_data[sp][st_cap] > 0:
                        cap_sum += sp_data[sp][st_cap]
                        if self.generators[gen].lcoe > 0:
                            sp_data[sp][st_cfa] = sp_data[sp][ndx] / sp_data[sp][st_cap] / 8760 # need number for now
                        else:
                            sp_data[sp][st_cfa] = '{:.1f}%'.format(sp_data[sp][ndx] / sp_data[sp][st_cap] / 8760 * 100)
                    gen_sum += sp_data[sp][st_sub]
                except:
                    pass
                try:
                    tml_sum += sp_data[sp][st_tml]
                except:
                    pass
                if gen not in self.generators.keys():
                    continue
                ndx = 3
                if gen in storage_names:
                    ndx = 2
                else:
                    try:
                        gen2 = gen[gen.find('.') + 1:]
                    except:
                        gen2 = gen
                    if gen not in tech_names and gen2 not in tech_names:
                        ff_sum += sp_data[sp][ndx]
                if self.generators[gen].capex > 0 or self.generators[gen].fixed_om > 0 \
                  or self.generators[gen].variable_om > 0 or self.generators[gen].fuel > 0:
                    if option != T and self.remove_cost and sp_data[sp][ndx] == 0:
                        sp_data[sp][st_cst] = 0
                        continue
                    capex = sp_data[sp][st_cap] * self.generators[gen].capex
                    capex_sum += capex
                    opex = sp_data[sp][st_cap] * self.generators[gen].fixed_om \
                           + sp_data[sp][ndx] * self.generators[gen].variable_om \
                           + sp_data[sp][ndx] * self.generators[gen].fuel
                    disc_rate = self.generators[gen].disc_rate
                    if disc_rate == 0:
                        disc_rate = self.discount_rate
                    lifetime = self.generators[gen].lifetime
                    sp_data[sp][st_lcg] = calcLCOE(sp_data[sp][ndx], capex, opex, disc_rate, lifetime)
                    sp_data[sp][st_cst] = sp_data[sp][ndx] * sp_data[sp][st_lcg]
                    # To prevent ZeroDivisionError
                    if (gen in tech_names or gen2 in tech_names) and (fac_tml_sum > 0):
                        sp_data[sp][st_lco] = sp_data[sp][st_cst] / (sp_data[sp][st_tml] + (sto_sum * sp_data[sp][st_tml] / fac_tml_sum))
                    else:
                        sp_data[sp][st_lco] = sp_data[sp][st_lcg]
                    cost_sum += sp_data[sp][st_cst]
                    sp_data[sp][st_cac] = capex
                elif self.generators[gen].lcoe > 0:
                    if option != T and self.remove_cost and sp_data[sp][ndx] == 0:
                        sp_data[sp][st_cst] = 0
                        continue
                    if self.generators[gen].lcoe_cf > 0:
                        lcoe_cf = self.generators[gen].lcoe_cf
                    else:
                        lcoe_cf = sp_data[sp][st_cfa]
                    sp_data[sp][st_cst] = self.generators[gen].lcoe * lcoe_cf * 8760 * sp_data[sp][st_cap]
                    if sp_data[sp][st_cfa] > 0:
                        sp_data[sp][st_lcg] = sp_data[sp][st_cst] / sp_data[sp][ndx]
                        sp_data[sp][st_lco] = sp_data[sp][st_lcg]
                    sp_data[sp][st_cfa] = '{:.1f}%'.format(sp_data[sp][st_cfa] * 100.)
                    cost_sum += sp_data[sp][st_cst]
                    sp_data[sp][st_rlc] = self.generators[gen].lcoe
                    sp_data[sp][st_rcf] = '{:.1f}%'.format(lcoe_cf * 100.)
                elif self.generators[gen].lcoe_cf == 0: # no cost facility
                    if option != T and self.remove_cost and sp_data[sp][ndx] == 0:
                        sp_data[sp][st_cst] = 0
                        continue
                    lcoe_cf = sp_data[sp][st_cfa]
                    sp_data[sp][st_cst] = 0
                    cost_sum += sp_data[sp][st_cst]
                sp_data[sp][st_lic] = sp_data[sp][st_cst] * max_lifetime
                lifetime_sum += sp_data[sp][st_lic]
                if self.generators[gen].emissions > 0 and sp_data[sp][st_tml]> 0:
                    sp_data[sp][st_emi] = sp_data[sp][ndx] * self.generators[gen].emissions
                    co2_sum += sp_data[sp][st_emi]
                    sp_data[sp][st_emc] = sp_data[sp][st_emi] * self.carbon_price
                    if sp_data[sp][st_cst] == 0:
                        sp_data[sp][st_lcc] = sp_data[sp][st_emc] / sp_data[sp][st_tml]
                    else:
                        sp_data[sp][st_lcc] = sp_data[sp][st_lco] * ((sp_data[sp][st_cst] + sp_data[sp][st_emc]) / sp_data[sp][st_cst])
                    co2_cost_sum += sp_data[sp][st_emc]
                    sp_data[sp][st_lie] = sp_data[sp][st_emi] * max_lifetime
                    lifetime_co2_sum += sp_data[sp][st_lie]
                    sp_data[sp][st_lec] = sp_data[sp][st_lie] * self.carbon_price
                    lifetime_co2_cost += sp_data[sp][st_lec]
                else:
                    sp_data[sp][st_lcc] = sp_data[sp][st_lco]
                if self.generators[gen].area > 0:
                    sp_data[sp][st_are] = sp_data[sp][st_cap] * self.generators[gen].area
                    total_area += sp_data[sp][st_are]
            sf_sums = [0., 0., 0.]
            for sf in range(len(shortfall)):
                if shortfall[sf] > 0:
                    sf_sums[0] += shortfall[sf]
                    sf_sums[2] += load_and_supply[load_col][sf] * technology_attributes['Load'].multiplier
                else:
                    sf_sums[1] += shortfall[sf]
                    sf_sums[2] += load_and_supply[load_col][sf] * technology_attributes['Load'].multiplier
            if gen_sum > 0:
                gs = cost_sum / gen_sum
            else:
                gs = ''
            if tml_sum > 0:
                gsw = cost_sum / tml_sum # LCOE
                gswc = (cost_sum + co2_cost_sum) / tml_sum
            else:
                gsw = ''
                gswc = ''
            if option == O or option == O1:
                load_pct, surp_pct, re_pct = summary_totals()
            else:
                summary_totals()
            do_underlying = False
            if len(underlying_facs) > 0:
                for fac in underlying_facs:
                    if technology_attributes[fac].capacity * technology_attributes[fac].multiplier > 0:
                        do_underlying = True
                        break
            if do_underlying:
                sp_data.append(' ')
                sp_data.append('Additional Underlying Load')
                for fac in underlying_facs:
                    if technology_attributes[fac].capacity * technology_attributes[fac].multiplier == 0:
                        continue
                    if fac in self.generators.keys():
                        gen = fac
                    else:
                        gen = technology_attributes[fac].generator
                    col = technology_attributes[fac].col
                    sp_d = [' '] * len(headers)
                    sp_d[st_fac] = fac
                    sp_d[st_cap] = technology_attributes[fac].capacity * technology_attributes[fac].multiplier
                    cap_sum += sp_d[st_cap]
                    sp_d[st_tml] = sum(load_and_supply[technology_attributes[fac].col]) * technology_attributes[fac].multiplier
                    tml_sum += sp_d[st_tml]
                    sp_d[st_sub] = sp_d[st_tml]
                    gen_sum += sp_d[st_tml]
                    sp_load += sp_d[st_tml]
                    sp_d[st_cfa] = '{:.1f}%'.format(sp_d[st_sub] / sp_d[st_cap] / 8760 * 100.)
                    sp_d[st_max] = max(load_and_supply[technology_attributes[fac].col]) * technology_attributes[fac].multiplier
                    if self.generators[gen].capex > 0 or self.generators[gen].fixed_om > 0 \
                      or self.generators[gen].variable_om > 0 or self.generators[gen].fuel > 0:
                        capex = sp_d[st_cap] * self.generators[gen].capex
                        capex_sum += capex
                        opex = sp_d[st_cap] * self.generators[gen].fixed_om \
                               + sp_d[st_tml] * self.generators[gen].variable_om \
                               + sp_d[st_tml] * self.generators[gen].fuel
                        disc_rate = self.generators[gen].disc_rate
                        if disc_rate == 0:
                            disc_rate = self.discount_rate
                        lifetime = self.generators[gen].lifetime
                        sp_d[st_lcg] = calcLCOE(sp_d[st_tml], capex, opex, disc_rate, lifetime)
                        sp_d[st_cst] = sp_d[st_tml] * sp_d[st_lcg]
                        cost_sum += sp_d[st_cst]
                        sp_d[st_lco] = sp_d[st_lcg]
                        sp_d[st_cac] = capex
                    elif self.generators[gen].lcoe > 0:
                        if self.generators[gen].lcoe_cf > 0:
                            lcoe_cf = self.generators[gen].lcoe_cf
                        else:
                            lcoe_cf = sp_d[st_cfa]
                        sp_d[st_cst] = self.generators[gen].lcoe * lcoe_cf * 8760 * sp_d[st_cap]
                        cost_sum += sp_d[st_cst]
                        if sp_d[st_cfa] > 0:
                            sp_d[st_lcg] = sp_d[st_cst] / sp_d[st_tml]
                            sp_d[st_lco] = sp_d[st_lcg]
                        sp_d[st_cfa] = '{:.1f}%'.format(sp_d[st_cfa] * 100.)
                        sp_d[st_rlc] = self.generators[gen].lcoe
                        sp_d[st_rcf] = '{:.1f}%'.format(lcoe_cf * 100.)
                    elif self.generators[gen].lcoe_cf == 0: # no cost facility
                        sp_d[st_cst] = 0
                        sp_d[st_lcg] = 0
                        sp_d[st_lco] = 0
                        sp_d[st_rlc] = self.generators[gen].lcoe
                    sp_d[st_lic] = sp_d[st_cst] * max_lifetime
                    lifetime_sum += sp_d[st_lic]
                    if self.generators[gen].emissions > 0:
                        sp_d[st_emi] = sp_d[st_tml] * self.generators[gen].emissions
                        co2_sum += sp_d[st_emi]
                        sp_d[st_emc] = sp_d[st_emi] * self.carbon_price
                        if sp_d[st_cst] > 0:
                            sp_d[st_lcc] = sp_d[st_lco] * ((sp_d[st_cst] + sp_d[st_emc]) / sp_d[st_cst])
                        else:
                            sp_d[st_lcc] = sp_d[st_emc] / sp_d[st_tml]
                        co2_cost_sum += sp_d[st_emc]
                        sp_d[st_lie] = sp_d[st_emi] * max_lifetime
                        lifetime_co2_sum += sp_d[st_lie]
                        sp_d[st_lec] = sp_d[st_lie] * self.carbon_price
                        lifetime_co2_cost += sp_d[st_lec]
                    else:
                        sp_d[st_lcc] = sp_d[st_lco]
                    if self.generators[gen].area > 0:
                        sp_d[st_are] = sp_d[st_cap] * self.generators[gen].area
                    sp_data.append(sp_d)
                if gen_sum > 0:
                    gs = cost_sum / gen_sum
                else:
                    gs = ''
                if tml_sum > 0:
                    gsw = cost_sum / tml_sum # LCOE
                    gswc = (cost_sum + co2_cost_sum) / tml_sum
                else:
                    gsw = ''
                    gswc = ''
                # find maximum underlying load
                if option == S:
                    load_max = 0
                    load_hr = 0
                    load_col = technology_attributes['Load'].col
                    for h in range(len(load_and_supply[load_col])):
                        amt = load_and_supply[load_col][h] * technology_attributes['Load'].multiplier
                        for fac in underlying_facs:
                            amt += load_and_supply[technology_attributes[fac].col][h] * technology_attributes[fac].multiplier
                        if amt > load_max:
                            load_max = amt
                            load_hr = h
                summary_totals('Underlying ')
            if corr_data is not None:
                sp_data.append(' ')
                sp_data = sp_data + corr_data
            sp_data.append(' ')
            sp_data.append(['Static Variables'])
            if self.carbon_price > 0:
                sp_d = [' '] * len(headers)
                sp_d[st_fac] = 'Carbon Price ($/tCO2e)'
                sp_d[st_cap] = self.carbon_price
                sp_data.append(sp_d)
            sp_d = [' '] * len(headers)
            sp_d[st_fac] = 'Lifetime (years)'
            sp_d[st_cap] = max_lifetime
            sp_data.append(sp_d)
            sp_d = [' '] * len(headers)
            sp_d[st_fac] = 'Discount Rate'
            sp_d[st_cap] = '{:.2%}'.format(self.discount_rate)
            sp_data.append(sp_d)
            if option == B or option == T:
                if self.optimise_debug:
                    sp_pts = [0] * len(headers)
                    for p in [st_cap, st_lcg, st_lco, st_lcc, st_max, st_bal, st_rlc, st_are]:
                        sp_pts[p] = 2
                    if corr_data is not None:
                        sp_pts[st_cap] = 3 # compromise between capacity (2) and correlation (4)
                return sp_data, corr_data
            if option == O or option == O1:
                op_load_tot = technology_attributes['Load'].capacity * technology_attributes['Load'].multiplier
                if gswc != '':
                    lcoe = gswc
                elif self.adjusted_lcoe:
                    lcoe = gsw # target is lcoe
                else:
                    lcoe = gs
                if gen_sum == 0:
                    re_pct = 0
                    load_pct = 0
                    re_pct = 0
                multi_value = {'lcoe': lcoe, #lcoe. lower better
                    'load_pct': load_pct, #load met. 100% better
                    'surplus_pct': surp_pct, #surplus. lower better
                    're_pct': re_pct, # RE pct. higher better
                    'cost': cost_sum, # cost. lower better
                    'co2': co2_sum} # CO2. lower better
                if option == O:
                    if multi_value['lcoe'] == '':
                        multi_value['lcoe'] = 0
                    return multi_value, sp_data, None
                else:
                    extra = [gsw, op_load_tot, sto_sum, re_sum, re_pct, sf_sums]
                    return multi_value, sp_data, extra
        #    list(map(list, list(zip(*sp_data))))
            span = None
            sp_pts = [0] * len(headers)
            for p in [st_cap, st_lcg, st_lco, st_lcc, st_max, st_bal, st_rlc, st_are]:
                sp_pts[p] = 2
            if corr_data is not None:
                sp_pts[st_cap] = 3 # compromise between capacity (2) and correlation (4)
            self.setStatus(sender_name + ' completed')
            if title is not None:
                atitle = title
            elif self.results_prefix != '':
                atitle = self.results_prefix + '_' + sender_name
            else:
                atitle = sender_name
            return sp_data, corr_data # finish if not detailed spreadsheet
        col = next_col + 1
        is_storage = False
        ss_sto_rows = []
        ss_st_row = -1
        for gen in dispatch_order:
            ss_row += 1
            try:
                if self.constraints[self.generators[gen].constraint].category == 'Storage':
                    ss_sto_rows.append(ss_row)
                    nc = 2
                    ns.cell(row=what_row, column=col).value = 'Charge\n' + gen
                    ns.cell(row=what_row, column=col).alignment = oxl.styles.Alignment(wrap_text=True,
                            vertical='bottom', horizontal='center')
                    ns.cell(row=what_row, column=col + 1).value = gen + '\nLosses'
                    ns.cell(row=what_row, column=col + 1).alignment = oxl.styles.Alignment(wrap_text=True,
                            vertical='bottom', horizontal='center')
                    is_storage = True
                    ns_sto_sum += '+' + ssCol(st_tml+1) + str(ss_row)
                    ns_loss_sum += '+Detail!' + ssCol(col + 1) + str(sum_row)
                else:
                    nc = 0
                    is_storage = False
                    ns_not_sum += '-' + ssCol(st_tml+1) + str(ss_row)
            except KeyError as err:
                msg = 'Key Error: No Constraint for ' + gen
                if title is not None:
                    msg += ' (model ' + title + ')'
                self.setStatus(msg)
                nc = 0
                is_storage = False
                ns_not_sum += '-' + ssCol(st_tml+1) + str(ss_row)
            ns.cell(row=what_row, column=col + nc).value = gen
            ss.cell(row=ss_row, column=st_fac+1).value = '=Detail!' + ssCol(col + nc) + str(what_row)
            # facility
            ss.cell(row=ss_row, column=st_cap+1).value = '=Detail!' + ssCol(col + nc) + str(cap_row)
            # capacity
            ss.cell(row=ss_row, column=st_cap+1).number_format = '#,##0.00'
            # tml
            ss.cell(row=ss_row, column=st_tml+1).value = '=Detail!' + ssCol(col + nc) + str(sum_row)
            ss.cell(row=ss_row, column=st_tml+1).number_format = '#,##0'
            # subtotal
            try:
                if self.constraints[self.generators[gen].constraint].category != 'Storage':
                    ss.cell(row=ss_row, column=st_sub+1).value = '=Detail!' + ssCol(col + nc) + str(sum_row)
                    ss.cell(row=ss_row, column=st_sub+1).number_format = '#,##0'
            except KeyError as err:
                ss.cell(row=ss_row, column=st_sub+1).value = '=Detail!' + ssCol(col + nc) + str(sum_row)
                ss.cell(row=ss_row, column=st_sub+1).number_format = '#,##0'
            # cf
            ss.cell(row=ss_row, column=st_cfa+1).value = '=Detail!' + ssCol(col + nc) + str(cf_row)
            ss.cell(row=ss_row, column=st_cfa+1).number_format = '#,##0.0%'
            if self.generators[gen].capex > 0 or self.generators[gen].fixed_om > 0 \
              or self.generators[gen].variable_om > 0 or self.generators[gen].fuel > 0:
                disc_rate = self.generators[gen].disc_rate
                if disc_rate == 0:
                    disc_rate = self.discount_rate
                if disc_rate == 0:
                    cst_calc = '/' + str(self.generators[gen].lifetime)
                else:
                    pwr_calc = 'POWER(1+' + str(disc_rate) + ',' + str(self.generators[gen].lifetime) + ')'
                    cst_calc = '*' + str(disc_rate) + '*' + pwr_calc + '/SUM(' + pwr_calc + ',-1)'
                ns.cell(row=cost_row, column=col + nc).value = '=IF(' + ssCol(col + nc) + str(cf_row) + \
                        '>0,' + ssCol(col + nc) + str(cap_row) + '*' + str(self.generators[gen].capex) + \
                        cst_calc + '+' + ssCol(col + nc) + str(cap_row) + '*' + \
                        str(self.generators[gen].fixed_om) + '+' + ssCol(col + nc) + str(sum_row) + '*(' + \
                        str(self.generators[gen].variable_om) + '+' + str(self.generators[gen].fuel) + \
                        '),0)'
                ns.cell(row=cost_row, column=col + nc).number_format = '$#,##0'
                # cost / yr
                if self.remove_cost:
                    ss.cell(row=ss_row, column=st_cst+1).value = '=IF(Detail!' + ssCol(col + nc) + str(sum_row) \
                            + '>0,Detail!' + ssCol(col + nc) + str(cost_row) + ',"")'
                else:
                    ss.cell(row=ss_row, column=st_cst+1).value = '=Detail!' + ssCol(col + nc) + str(cost_row)
                ss.cell(row=ss_row, column=st_cst+1).number_format = '$#,##0'
                ns.cell(row=lcoe_row, column=col + nc).value = '=IF(AND(' + ssCol(col + nc) + str(cf_row) + \
                        '>0,' + ssCol(col + nc) + str(cap_row) + '>0),' + ssCol(col + nc) + \
                        str(cost_row) + '/' + ssCol(col + nc) + str(sum_row) + ',"")'
                ns.cell(row=lcoe_row, column=col + nc).number_format = '$#,##0.00'
                # lcog
                ss.cell(row=ss_row, column=st_lcg+1).value = '=Detail!' + ssCol(col + nc) + str(lcoe_row)
                ss.cell(row=ss_row, column=st_lcg+1).number_format = '$#,##0.00'
                # lcoe
                ss.cell(row=ss_row, column=st_lco+1).value = '=Detail!' + ssCol(col + nc) + str(lcoe_row)
                ss.cell(row=ss_row, column=st_lco+1).number_format = '$#,##0.00'
                # capital cost
                ss.cell(row=ss_row, column=st_cac+1).value = '=IF(Detail!' + ssCol(col + nc) + str(cap_row) \
                                                            + '>0,Detail!' + ssCol(col + nc) + str(cap_row) + '*'  \
                                                            + str(self.generators[gen].capex) + ',"")'
                ss.cell(row=ss_row, column=st_cac+1).number_format = '$#,##0'
            elif self.generators[gen].lcoe > 0:
                ns.cell(row=cost_row, column=col + nc).value = '=IF(' + ssCol(col + nc) + str(cf_row) + \
                        '>0,' + ssCol(col + nc) + str(sum_row) + '*Summary!' + ssCol(st_rlc + 1) + str(ss_row) + \
                        '*Summary!' + ssCol(st_rcf + 1) + str(ss_row) + '/' + ssCol(col + nc) + str(cf_row) + ',0)'
                ns.cell(row=cost_row, column=col + nc).number_format = '$#,##0'
                # cost / yr
                if self.remove_cost:
                    ss.cell(row=ss_row, column=st_cst+1).value = '=IF(Detail!' + ssCol(col + nc) + str(sum_row) \
                            + '>0,Detail!' + ssCol(col + nc) + str(cost_row) + ',"")'
                else:
                    ss.cell(row=ss_row, column=st_cst+1).value = '=Detail!' + ssCol(col + nc) + str(cost_row)
                ss.cell(row=ss_row, column=st_cst+1).number_format = '$#,##0'
                ns.cell(row=lcoe_row, column=col + nc).value = '=IF(AND(' + ssCol(col + nc) + str(cf_row) + '>0,' \
                            + ssCol(col + nc) + str(cap_row) + '>0),' + ssCol(col + nc) + str(cost_row) + '/8760/' \
                            + ssCol(col + nc) + str(cf_row) + '/' + ssCol(col + nc) + str(cap_row)+  ',"")'
                ns.cell(row=lcoe_row, column=col + nc).number_format = '$#,##0.00'
                # lcog
                ss.cell(row=ss_row, column=st_lcg+1).value = '=Detail!' + ssCol(col + nc) + str(lcoe_row)
                ss.cell(row=ss_row, column=st_lcg+1).number_format = '$#,##0.00'
                # lcoe
                ss.cell(row=ss_row, column=st_lco+1).value = '=Detail!' + ssCol(col + nc) + str(lcoe_row)
                ss.cell(row=ss_row, column=st_lco+1).number_format = '$#,##0.00'
                # ref lcoe
                ss.cell(row=ss_row, column=st_rlc+1).value = self.generators[gen].lcoe
                ss.cell(row=ss_row, column=st_rlc+1).number_format = '$#,##0.00'
                # ref cf
                if self.generators[gen].lcoe_cf == 0:
                    ss.cell(row=ss_row, column=st_rcf+1).value = '=' + ssCol(st_cfa+1) + str(ss_row)
                else:
                    ss.cell(row=ss_row, column=st_rcf+1).value = self.generators[gen].lcoe_cf
                ss.cell(row=ss_row, column=st_rcf+1).number_format = '#,##0.0%'
            elif self.generators[gen].lcoe_cf == 0: # no cost facility
                ns.cell(row=cost_row, column=col + nc).value = '=IF(' + ssCol(col + nc) + str(cf_row) + \
                        '>0,' + ssCol(col + nc) + str(sum_row) + '*Summary!' + ssCol(st_rlc + 1) + str(ss_row) + \
                        '*Summary!' + ssCol(st_rcf + 1) + str(ss_row) + '/' + ssCol(col + nc) + str(cf_row) + ',0)'
                ns.cell(row=cost_row, column=col + nc).number_format = '$#,##0'
                # cost / yr
                if self.remove_cost:
                    ss.cell(row=ss_row, column=st_cst+1).value = '=IF(Detail!' + ssCol(col + nc) + str(sum_row) \
                            + '>0,Detail!' + ssCol(col + nc) + str(cost_row) + ',"")'
                else:
                    ss.cell(row=ss_row, column=st_cst+1).value = '=Detail!' + ssCol(col + nc) + str(cost_row)
                ss.cell(row=ss_row, column=st_cst+1).number_format = '$#,##0'
                ns.cell(row=lcoe_row, column=col + nc).value = '=IF(AND(' + ssCol(col + nc) + str(cf_row) + '>0,' \
                            + ssCol(col + nc) + str(cap_row) + '>0),' + ssCol(col + nc) + str(cost_row) + '/8760/' \
                            + ssCol(col + nc) + str(cf_row) + '/' + ssCol(col + nc) + str(cap_row)+  ',"")'
                ns.cell(row=lcoe_row, column=col + nc).number_format = '$#,##0.00'
                # lcog
                ss.cell(row=ss_row, column=st_lcg+1).value = '=Detail!' + ssCol(col + nc) + str(lcoe_row)
                ss.cell(row=ss_row, column=st_lcg+1).number_format = '$#,##0.00'
                # lcoe
                ss.cell(row=ss_row, column=st_lco+1).value = '=Detail!' + ssCol(col + nc) + str(lcoe_row)
                ss.cell(row=ss_row, column=st_lco+1).number_format = '$#,##0.00'
                # ref lcoe
                ss.cell(row=ss_row, column=st_rlc+1).value = self.generators[gen].lcoe
                ss.cell(row=ss_row, column=st_rlc+1).number_format = '$#,##0.00'
                # ref cf
                if self.generators[gen].lcoe_cf == 0:
                    ss.cell(row=ss_row, column=st_rcf+1).value = '=' + ssCol(st_cfa+1) + str(ss_row)
                else:
                    ss.cell(row=ss_row, column=st_rcf+1).value = self.generators[gen].lcoe_cf
                ss.cell(row=ss_row, column=st_rcf+1).number_format = '#,##0.0%'
            if self.generators[gen].emissions > 0:
                ns.cell(row=emi_row, column=col + nc).value = '=' + ssCol(col + nc) + str(sum_row) \
                        + '*' + str(self.generators[gen].emissions)
                ns.cell(row=emi_row, column=col + nc).number_format = '#,##0'
                # emissions
                if self.remove_cost:
                    ss.cell(row=ss_row, column=st_emi+1).value = '=IF(Detail!' + ssCol(col + nc) + str(sum_row) \
                            + '>0,Detail!' + ssCol(col + nc) + str(emi_row) + ',"")'
                else:
                    ss.cell(row=ss_row, column=st_emi+1).value = '=Detail!' + ssCol(col + nc) + str(emi_row)
                ss.cell(row=ss_row, column=st_emi+1).number_format = '#,##0'
                if self.carbon_price > 0:
                    ss.cell(row=ss_row, column=st_emc+1).value = '=IF(AND(' + ssCol(st_emi+1) + str(ss_row) + '<>"",' + \
                                                                 ssCol(st_emi+1) + str(ss_row) + '>0),' + \
                                                                 ssCol(st_emi+1) + str(ss_row) + '*carbon_price,"")'
                    ss.cell(row=ss_row, column=st_emc+1).number_format = '$#,##0'
            # max mwh
            ss.cell(row=ss_row, column=st_max+1).value = '=Detail!' + ssCol(col + nc) + str(max_row)
            ss.cell(row=ss_row, column=st_max+1).number_format = '#,##0.00'
            # max balance
            if nc > 0: # storage
                ss.cell(row=ss_row, column=st_bal+1).value = '=Detail!' + ssCol(col + nc + 1) + str(max_row)
                ss.cell(row=ss_row, column=st_bal+1).number_format = '#,##0.00'
            ns.cell(row=what_row, column=col + nc).alignment = oxl.styles.Alignment(wrap_text=True,
                    vertical='bottom', horizontal='center')
            ns.cell(row=what_row, column=col + nc + 1).alignment = oxl.styles.Alignment(wrap_text=True,
                    vertical='bottom', horizontal='center')
            if is_storage:
                # lifetime cost
                ss.cell(row=ss_row, column=st_lic+1).value = '=IF(Detail!' + ssCol(col + 2) + str(sum_row) \
                                                        + '>0,Detail!' + ssCol(col + 2) + str(cost_row) + '*lifetime,"")'
                ss.cell(row=ss_row, column=st_lic+1).number_format = '$#,##0'
                # ns.cell(row=what_row, column=col + 1).value = gen
                ns.cell(row=what_row, column=col + 3).value = gen + '\nBalance'
                ns.cell(row=what_row, column=col + 3).alignment = oxl.styles.Alignment(wrap_text=True,
                        vertical='bottom', horizontal='center')
                ns.cell(row=what_row, column=col + 4).value = 'After\n' + gen
                ns.cell(row=what_row, column=col + 4).alignment = oxl.styles.Alignment(wrap_text=True,
                        vertical='bottom', horizontal='center')
                ns.cell(row=fall_row, column=col + 4).value = '=COUNTIF(' + ssCol(col + 4) \
                        + str(hrows) + ':' + ssCol(col + 4) + str(hrows + 8759) + \
                        ',"' + sf_test[0] + '0")'
                ns.cell(row=fall_row, column=col + 4).number_format = '#,##0'
                col += 5
            else:
                # lifetime cost
                ss.cell(row=ss_row, column=st_lic+1).value = '=IF(Detail!' + ssCol(col) + str(sum_row) \
                                                        + '>0,Detail!' + ssCol(col) + str(cost_row) + '*lifetime,"")'
                ss.cell(row=ss_row, column=st_lic+1).number_format = '$#,##0'
                ns.cell(row=what_row, column=col + 1).value = 'After\n' + gen
                ns.cell(row=fall_row, column=col + 1).value = '=COUNTIF(' + ssCol(col + 1) \
                        + str(hrows) + ':' + ssCol(col + 1) + str(hrows + 8759) + \
                        ',"' + sf_test[0] + '0")'
                ns.cell(row=fall_row, column=col + 1).number_format = '#,##0'
                col += 2
            ss.cell(row=ss_row, column=st_lie+1).value = '=IF(AND(' + ssCol(st_emi+1) + str(ss_row) + '<>"",' + \
                                                         ssCol(st_emi+1) + str(ss_row) + '>0),' + \
                                                         ssCol(st_emi+1) + str(ss_row) + '*lifetime,"")'
            ss.cell(row=ss_row, column=st_lie+1).number_format = '#,##0'
            ss.cell(row=ss_row, column=st_lec+1).value = '=IF(AND(' + ssCol(st_emi+1) + str(ss_row) + '<>"",' + \
                                                         ssCol(st_emi+1) + str(ss_row) + '>0),' + \
                                                         ssCol(st_emc+1) + str(ss_row) + '*lifetime,"")'
            ss.cell(row=ss_row, column=st_lec+1).number_format = '$#,##0'
        if is_storage:
            ns.cell(row=emi_row, column=col - 2).value = '=MIN(' + ssCol(col - 2) + str(hrows) + \
                    ':' + ssCol(col - 2) + str(hrows + 8759) + ')'
            ns.cell(row=emi_row, column=col - 2).number_format = '#,##0.00'
        for column_cells in ns.columns:
            length = 0
            value = ''
            row = 0
            sum_value = 0
            do_sum = False
            do_cost = False
            for cell in column_cells:
                if cell.row >= hrows:
                    if do_sum:
                        try:
                            sum_value += abs(cell.value)
                        except:
                            pass
                    else:
                        try:
                            value = str(round(cell.value, 2))
                            if len(value) > length:
                                length = len(value) + 2
                        except:
                            pass
                elif cell.row > 0:
                    if str(cell.value)[0] != '=':
                        values = str(cell.value).split('\n')
                        for value in values:
                            if cell.row == cost_row:
                                valf = value.split('.')
                                alen = int(len(valf[0]) * 1.6)
                            else:
                                alen = len(value) + 2
                            if alen > length:
                                length = alen
                    else:
                        if cell.row == cost_row:
                            do_cost = True
                        if cell.value[1:4] == 'SUM':
                            do_sum = True
            if sum_value > 0:
                alen = len(str(int(sum_value))) * 1.5
                if do_cost:
                    alen = int(alen * 1.5)
                if alen > length:
                    length = alen
            if isinstance(cell.column, int):
                cel = ssCol(cell.column)
            else:
                cel = cell.column
            ns.column_dimensions[cel].width = max(length, 10)
        ns.column_dimensions['A'].width = 6
        ns.column_dimensions['B'].width = 21
        st_row = hrows + 8760
        st_col = col
        for row in range(1, st_row):
            for col in range(1, st_col):
                try:
                    ns.cell(row=row, column=col).font = normal
                except:
                    pass
        self.listener.progress_bar.setValue(12)
        if self.event_callback:
            self.event_callback()
        ns.row_dimensions[what_row].height = 30
        ns.freeze_panes = 'C' + str(hrows)
        ns.activeCell = 'C' + str(hrows)
        if self.results_prefix != '':
            ss.cell(row=1, column=1).value = 'Powermatch - ' + self.results_prefix + ' Summary'
        else:
            ss.cell(row=1, column=1).value = 'Powermatch - Summary'
        ss.cell(row=1, column=1).font = bold
        ss_lst_row = ss_row + 1
        ss_row, ss_re_row = detail_summary_total(ss_row, base_row='4')
        if len(nsul_sum_cols) > 1: # if we have underlying there'll be more than one column
            ss_row += 2
            ss.cell(row=ss_row, column=1).value = 'Additional Underlying Load'
            ss.cell(row=ss_row, column=1).font = bold
            base_row = str(ss_row + 1)
            for col in nsul_sum_cols[1:]:
                ss_row += 1
                ul_tml_sum, ul_re_sum = do_detail_summary(fac, col, ss_row, ul_tml_sum, ul_re_sum)
            ul_fst_row = int(base_row)
            ul_lst_row = ss_row
            ns_re_sum = ul_re_sum
            ns_tml_sum = ul_tml_sum
            ss_row, ss_re_row = detail_summary_total(ss_row, title='Underlying ', base_row=base_row,
                                          back_row=str(ss_lst_row))
        wider = [ssCol(st_cac + 1), ssCol(st_lic + 1)]
        for column_cells in ss.columns:
            length = 0
            value = ''
            for cell in column_cells:
                if str(cell.value)[0] != '=':
                    values = str(cell.value).split('\n')
                    for value in values:
                        if len(value) + 1 > length:
                            length = len(value) + 1
            if isinstance(cell.column, int):
                cel = ssCol(cell.column)
            else:
                cel = cell.column
            if cel in wider:
                ss.column_dimensions[cel].width = max(length, 10) * 1.5
            else:
                ss.column_dimensions[cel].width = max(length, 10) * 1.2

        if corr_data is not None:
            ss_row += 2
            for corr in corr_data:
                ss.cell(row=ss_row, column=1).value = corr[0]
                if len(corr) > 1:
                    ss.cell(row=ss_row, column=2).value = corr[1]
                    ss.cell(row=ss_row, column=2).number_format = '#0.0000'
                    ss.cell(row=ss_row, column=3).value = corr[2]
                ss_row += 1
        ss_row += 2
        ss.cell(row=ss_row, column=1).value = 'Static Variables'
        ss.cell(row=ss_row, column=1).font = bold
        if self.carbon_price > 0:
            ss_row += 1
            ss.cell(row=ss_row, column=1).value = 'Carbon Price ($/tCO2e)'
            ss.cell(row=ss_row, column=st_cap+1).value = self.carbon_price
            ss.cell(row=ss_row, column=st_cap+1).number_format = '$#,##0.00'
            attr_text = 'Summary!$' + ssCol(st_cap+1) + '$' + str(ss_row)
            carbon_cell = oxl.workbook.defined_name.DefinedName('carbon_price', attr_text=attr_text)
            wb.defined_names.append(carbon_cell)
        ss_row += 1
        attr_text = 'Summary!$' + ssCol(st_cap+1) + '$' + str(ss_row)
        lifetime_cell = oxl.workbook.defined_name.DefinedName('lifetime', attr_text=attr_text)
        wb.defined_names.append(lifetime_cell)
        ss.cell(row=ss_row, column=1).value = 'Lifetime (years)'
        ss.cell(row=ss_row, column=st_cap+1).value = max_lifetime
        ss.cell(row=ss_row, column=st_cap+1).number_format = '#,##0'
        ss_row += 1
        ss.cell(row=ss_row, column=1).value = 'Discount Rate'
        ss.cell(row=ss_row, column=st_cap+1).value = self.discount_rate
        ss.cell(row=ss_row, column=st_cap+1).number_format = '#,##0.00%'
        ss_row += 2
        ss_row = self.data_sources(ss, ss_row, pm_data_file, option)
        self.listener.progress_bar.setValue(14)
        if self.event_callback:
            self.event_callback()
        for row in range(1, ss_row + 1):
            for col in range(1, len(headers) + 1):
                try:
                    if ss.cell(row=row, column=col).font.name != 'Arial':
                        ss.cell(row=row, column=col).font = normal
                except:
                    pass
        ss.freeze_panes = 'B4'
        ss.activeCell = 'B4'
        if self.save_tables:
            gens = []
            cons = []
            for fac in re_order:
                if fac == 'Load':
                    continue
                if technology_attributes[fac].multiplier <= 0:
                    continue
                if fac.find('.') > 0:
                    gens.append(fac[fac.find('.') + 1:])
                else:
                    gens.append(fac)
                cons.append(self.generators[technology_attributes[fac].generator].constraint)
            for gen in dispatch_order:
                gens.append(gen)
                cons.append(self.generators[gen].constraint)
            gs = wb.create_sheet(self.sheets[G].currentText())
            fields = []
            col = 1
            row = 1
            if hasattr(self.generators[list(self.generators.keys())[0]], 'name'):
                fields.append('name')
                gs.cell(row=row, column=col).value = 'Name'
                col += 1
            for prop in dir(self.generators[list(self.generators.keys())[0]]):
                if prop[:2] != '__' and prop[-2:] != '__':
                    if prop != 'name':
                        fields.append(prop)
                        txt = prop.replace('_', ' ').title()
                        txt = txt.replace('Cf', 'CF')
                        txt = txt.replace('Lcoe', 'LCOE')
                        txt = txt.replace('Om', 'OM')
                        gs.cell(row=row, column=col).value = txt
                        if prop == 'capex':
                            txt = txt + txt
                        gs.column_dimensions[ssCol(col)].width = max(len(txt) * 1.4, 10)
                        col += 1
            nme_width = 4
            con_width = 4
            for key, value in self.generators.items():
                if key in gens:
                    row += 1
                    col = 1
                    for field in fields:
                        gs.cell(row=row, column=col).value = getattr(value, field)
                        if field in ['name', 'constraint']:
                            txt = getattr(value, field)
                            if field == 'name':
                                if len(txt) > nme_width:
                                    nme_width = len(txt)
                                    gs.column_dimensions[ssCol(col)].width = nme_width * 1.4
                            else:
                                if len(txt) > con_width:
                                    con_width = len(txt)
                                    gs.column_dimensions[ssCol(col)].width = con_width * 1.4
                        elif field in ['capex', 'fixed_om']:
                            gs.cell(row=row, column=col).number_format = '$#,##0'
                        elif field in ['lcoe', 'variable_om', 'fuel']:
                            gs.cell(row=row, column=col).number_format = '$#,##0.00'
                        elif field in ['disc_rate']:
                            gs.cell(row=row, column=col).number_format = '#,##0.00%'
                        elif field in ['capacity', 'lcoe_cf', 'initial']:
                            gs.cell(row=row, column=col).number_format = '#,##0.00'
                        elif field in ['emissions']:
                            gs.cell(row=row, column=col).number_format = '#,##0.000'
                        elif field in ['lifetime', 'order']:
                            gs.cell(row=row, column=col).number_format = '#,##0'
                        col += 1
            for row in range(1, row + 1):
                for col in range(1, len(fields) + 1):
                    gs.cell(row=row, column=col).font = normal
            gs.freeze_panes = 'B2'
            gs.activeCell = 'B2'
            fields = []
            col = 1
            row = 1
            cs = wb.create_sheet(self.sheets[C].currentText())
            if hasattr(self.constraints[list(self.constraints.keys())[0]], 'name'):
                fields.append('name')
                cs.cell(row=row, column=col).value = 'Name'
                col += 1
            for prop in dir(self.constraints[list(self.constraints.keys())[0]]):
                if prop[:2] != '__' and prop[-2:] != '__':
                    if prop != 'name':
                        fields.append(prop)
                        if prop == 'warm_time':
                            cs.cell(row=row, column=col).value = 'Warmup Time'
                        else:
                            cs.cell(row=row, column=col).value = prop.replace('_', ' ').title()
                        cs.column_dimensions[ssCol(col)].width = max(len(prop) * 1.4, 10)
                        col += 1
            nme_width = 4
            cat_width = 4
            for key, value in self.constraints.items():
                if key in cons:
                    row += 1
                    col = 1
                    for field in fields:
                        cs.cell(row=row, column=col).value = getattr(value, field)
                        if field in ['name', 'category']:
                            txt = getattr(value, field)
                            if field == 'name':
                                if len(txt) > nme_width:
                                    nme_width = len(txt)
                                    cs.column_dimensions[ssCol(col)].width = nme_width * 1.4
                            else:
                                if len(txt) > cat_width:
                                    cat_width = len(txt)
                                    cs.column_dimensions[ssCol(col)].width = cat_width * 1.4
                        elif field == 'warm_time':
                            cs.cell(row=row, column=col).number_format = '#0.00'
                        elif field != 'category':
                            cs.cell(row=row, column=col).number_format = '#,##0%'
                        col += 1
            for row in range(1, row + 1):
                for col in range(1, len(fields) + 1):
                    try:
                        cs.cell(row=row, column=col).font = normal
                    except:
                        pass
            cs.freeze_panes = 'B2'
            cs.activeCell = 'B2'
        wb.save(data_file)
        self.listener.progress_bar.setValue(20)
        if self.event_callback:
            self.event_callback()
        j = data_file.rfind('/')
        data_file = data_file[j + 1:]
        msg = '%s created (%.2f seconds)' % (data_file, time.time() - start_time)
        msg = '%s created.' % data_file
        self.setStatus(msg)
        self.listener.progress_bar.setHidden(True)
        self.listener.progress_bar.setValue(0)