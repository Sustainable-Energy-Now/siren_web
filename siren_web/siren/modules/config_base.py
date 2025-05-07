# config_base.py
import configparser
import sys
from abc import ABC, abstractmethod
from typing import Optional, List, Tuple

class ConfigurationProvider(ABC):
    """Abstract base class for configuration providers"""
    @abstractmethod
    def get_config_file(self) -> str:
        """Get the configuration file path"""
        pass

class DesktopConfigProvider(ConfigurationProvider):
    """Desktop configuration provider using PyQt5"""
    def get_config_file(self) -> str:
        from siren_web.siren.modules.getmodels import getModelFile
        if len(sys.argv) > 1:
            return sys.argv[1]
        return getModelFile('SIREN.ini')

class WebConfigProvider(ConfigurationProvider):
    """Web configuration provider"""
    def __init__(self, config_file: str):
        self.config_file = config_file

    def get_config_file(self) -> str:
        return self.config_file

class BaseConfig:
    """Base configuration class with common configuration loading logic"""
    def __init__(self, config_provider: Optional[ConfigurationProvider] = None):
        self.config_provider = config_provider or DesktopConfigProvider()
        self.config = configparser.RawConfigParser()
        self.base_year = '2012'  # default value
        self.parents: List[Tuple[str, str]] = []

    def load_config(self) -> None:
        """Load configuration from file"""
        config_file = self.config_provider.get_config_file()
        self.config.read(config_file)
        self._load_base_config()
        self._load_parents()

    def _load_base_config(self) -> None:
        """Load basic configuration settings"""
        try:
            self.base_year = self.config.get('Base', 'year')
        except (configparser.NoSectionError, configparser.NoOptionError):
            pass  # keep default value

    def _load_parents(self) -> None:
        """Load parent configurations"""
        try:
            from utilities.senutils import getParents
            self.parents = getParents(self.config.items('Parents'))
        except:
            pass

    def get_config_value(self, section: str, option: str, default: str = '') -> str:
        """Get a configuration value with a default"""
        try:
            return self.config.get(section, option)
        except (configparser.NoSectionError, configparser.NoOptionError):
            return default

    def get_path_with_replacements(self, path: str) -> str:
        """Replace variables in path with actual values"""
        from utilities.senutils import getUser
        result = path
        for key, value in self.parents:
            result = result.replace(key, value)
        result = result.replace('$USER$', getUser())
        result = result.replace('$YEAR$', self.base_year)
        return result

class ConfigurableBase:
    """Base class for objects that need configuration"""
    def __init__(self, config_provider: Optional[ConfigurationProvider] = None):
        self.config = BaseConfig(config_provider)
        self.config.load_config()
