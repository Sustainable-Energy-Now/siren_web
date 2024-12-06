import configparser
import os

class ConfigManager:
    def __init__(self, config_file):
        self.config = configparser.RawConfigParser()
        self.config.read(config_file)
    
    def get_value(self, section, key, default=None):
        try:
            return self.config.get(section, key)
        except:
            return default

    def get_parents(self, section='Parents'):
        try:
            return dict(self.config.items(section))
        except:
            return {}

    def get_scenarios_folder(self, base_year='2012', scenario_prefix='', parents=None):
        try:
            scenarios = self.get_value('Files', 'scenarios', '')
            if scenario_prefix:
                scenarios += '/' + scenario_prefix
            for key, value in parents.items():
                scenarios = scenarios.replace(key, value)
            scenarios = scenarios.replace('$YEAR$', base_year)
            return os.path.join(scenarios[:scenarios.rfind('/') + 1])
        except:
            return ''
