import configparser   # decode .ini file
import os
import sys
import time
from utilities.senutils import getParents
from modules.getmodels import getModelFile, commonprefix
from utilities.senutils import getUser

def load_settings():
    config = configparser.RawConfigParser()
    if len(sys.argv) > 1:
        config_file = sys.argv[1]
    else:
        config_file = getModelFile('SIREN.ini')
    config.read(config_file)
    parents = []
    settings = {}
    settings['config_file'] = config_file
    try:
        parents = getParents(config.items('Parents'))
    except:
        pass
    settings['parents'] = parents
    try:
        base_year = config.get('Base', 'year')
    except:
        base_year = '2012'
    settings['base_year'] = base_year
    try:
        scenario_prefix = config.get('Files', 'scenario_prefix')
    except:
        scenario_prefix = ''
    settings['scenario_prefix'] = scenario_prefix
    try:
        batch_template = config.get('Files', 'pmb_template')
        for key, value in parents:
            batch_template = batch_template.replace(key, value)
        batch_template = batch_template.replace('$USER$', getUser())
        if not os.path.exists(batch_template):
            batch_template = ''
    except:
        batch_template = ''
    settings['batch_template'] = batch_template
    try:
        scenarios = config.get('Files', 'scenarios')
        if scenario_prefix != '' :
            scenarios += '/' + scenario_prefix
        for key, value in parents:
            scenarios = scenarios.replace(key, value)
        scenarios = scenarios.replace('$USER$', getUser())
        scenarios = scenarios.replace('$YEAR$', base_year)
        scenarios = scenarios[: scenarios.rfind('/') + 1]
        if scenarios[:3] == '../':
            ups = scenarios.split('../')
            me = os.getcwd().split(os.sep)
            me = me[: -(len(ups) - 1)]
            me.append(ups[-1])
            scenarios = '/'.join(me)
    except:
        scenarios = ''
    settings['scenarios'] = scenarios
    try:
        load_files = config.get('Files', 'load')
        for key, value in parents:
            load_files = load_files.replace(key, value)
        load_files = load_files.replace('$USER$', getUser())
    except:
        load_files = ''
    settings['load_files'] = load_files
    try:
        _load_folder = load_files[:load_files.rfind('/')]
    except:
        _load_folder = ''
    settings['_load_folder'] = _load_folder
    log_status = True
    try:
        rw = config.get('Windows', 'log_status')
        if rw.lower() in ['false', 'no', 'off']:
            log_status = False
    except:
        pass
    settings['log_status'] = log_status
    return config, settings