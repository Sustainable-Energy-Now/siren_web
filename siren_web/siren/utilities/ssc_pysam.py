#!/usr/bin/python3

"""
PySAM-based wrapper for SAM SSC functionality

This module provides a drop-in replacement for the original ctypes-based ssc.py,
using the official NREL PySAM package instead of direct DLL calls.

This approach:
- Eliminates DLL dependency issues
- Uses the officially supported NREL PySAM package
- Maintains backwards compatibility with existing code
- Provides access to the latest SAM modules and features

Usage:
    Replace imports from ssc.py with imports from ssc_pysam.py:

    Old: from siren_web.siren.utilities.ssc import Data, Module, API
    New: from siren_web.siren.utilities.ssc_pysam import Data, Module, API
"""

import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

# Try to import PySAM
try:
    import PySAM
    import PySAM.Windpower as Windpower
    import PySAM.Pvwattsv8 as Pvwattsv8
    import PySAM.Grid as Grid
    PYSAM_AVAILABLE = True
    logger.info(f"PySAM version {PySAM.__version__} loaded successfully")
except ImportError as e:
    PYSAM_AVAILABLE = False
    logger.error(f"PySAM not available: {e}. Install with: pip install nrel-pysam")


class API:
    """High-level API information class - compatible with original ssc.py"""

    # Constants for variable types (same as original)
    INPUT = 1
    OUTPUT = 2
    INOUT = 3

    # Constants for log message types
    NOTICE = 1
    WARNING = 2
    ERROR = 3

    # Constants for data types
    INVALID = 0
    STRING = 1
    NUMBER = 2
    ARRAY = 3
    MATRIX = 4
    TABLE = 5

    def __init__(self):
        if not PYSAM_AVAILABLE:
            raise ImportError("PySAM is not installed. Install with: pip install nrel-pysam")

    def version(self) -> int:
        """Return SSC version number"""
        try:
            # PySAM version string is like "7.1.0", convert to int
            version_str = PySAM.__version__
            parts = version_str.split('.')
            # Return as integer like 710 for 7.1.0
            return int(parts[0]) * 100 + int(parts[1]) * 10 + int(parts[2] if len(parts) > 2 else 0)
        except:
            return 0

    def build_info(self) -> bytes:
        """Return build information string"""
        try:
            return f"PySAM {PySAM.__version__}".encode('utf-8')
        except:
            return b"PySAM"

    def set_print(self, setprint: int) -> None:
        """Set print mode for module execution (compatibility stub)"""
        # PySAM handles logging differently
        pass


class Data:
    """
    Data container class for SAM simulations

    This provides a compatible interface with the original ssc.py Data class,
    storing values in a dictionary that can be used with PySAM modules.
    """

    def __init__(self, data: Dict = None):
        """Initialize data container"""
        if data is None:
            self._data = {}
        else:
            self._data = dict(data)
        self._iter_keys = None
        self._iter_index = 0

    def clear(self) -> None:
        """Clear all data"""
        self._data = {}

    def first(self) -> Optional[bytes]:
        """Return first variable name (for iteration)"""
        self._iter_keys = list(self._data.keys())
        self._iter_index = 0
        if self._iter_keys:
            return self._iter_keys[0].encode('utf-8') if isinstance(self._iter_keys[0], str) else self._iter_keys[0]
        return None

    def __next__(self) -> Optional[bytes]:
        """Return next variable name (for iteration)"""
        if self._iter_keys is None:
            return None
        self._iter_index += 1
        if self._iter_index < len(self._iter_keys):
            key = self._iter_keys[self._iter_index]
            return key.encode('utf-8') if isinstance(key, str) else key
        return None

    def query(self, name: bytes) -> int:
        """Query data type of a variable"""
        key = name.decode('utf-8') if isinstance(name, bytes) else name
        if key not in self._data:
            return API.INVALID
        value = self._data[key]
        if isinstance(value, str):
            return API.STRING
        elif isinstance(value, (int, float)):
            return API.NUMBER
        elif isinstance(value, list):
            if value and isinstance(value[0], list):
                return API.MATRIX
            return API.ARRAY
        elif isinstance(value, dict):
            return API.TABLE
        return API.INVALID

    def set_number(self, name: bytes, value: float) -> None:
        """Set a numeric value"""
        key = name.decode('utf-8') if isinstance(name, bytes) else name
        self._data[key] = float(value)

    def get_number(self, name: bytes) -> float:
        """Get a numeric value"""
        key = name.decode('utf-8') if isinstance(name, bytes) else name
        return float(self._data.get(key, float('nan')))

    def set_string(self, name: bytes, value: bytes) -> None:
        """Set a string value"""
        key = name.decode('utf-8') if isinstance(name, bytes) else name
        val = value.decode('utf-8') if isinstance(value, bytes) else value
        self._data[key] = val

    def get_string(self, name: bytes) -> bytes:
        """Get a string value"""
        key = name.decode('utf-8') if isinstance(name, bytes) else name
        val = self._data.get(key, '')
        return val.encode('utf-8') if isinstance(val, str) else val

    def set_array(self, name: bytes, data: List[float]) -> None:
        """Set an array value"""
        key = name.decode('utf-8') if isinstance(name, bytes) else name
        self._data[key] = list(data)

    def get_array(self, name: bytes) -> List[float]:
        """Get an array value"""
        key = name.decode('utf-8') if isinstance(name, bytes) else name
        return list(self._data.get(key, []))

    def set_matrix(self, name: bytes, mat: List[List[float]]) -> None:
        """Set a matrix value"""
        key = name.decode('utf-8') if isinstance(name, bytes) else name
        self._data[key] = [list(row) for row in mat]

    def get_matrix(self, name: bytes) -> List[List[float]]:
        """Get a matrix value"""
        key = name.decode('utf-8') if isinstance(name, bytes) else name
        return self._data.get(key, [])

    def set_table(self, name: bytes, table: Dict) -> None:
        """Set a table (dictionary) value"""
        key = name.decode('utf-8') if isinstance(name, bytes) else name
        self._data[key] = dict(table) if table else {}

    def get_table(self, name: bytes) -> Dict:
        """Get a table (dictionary) value"""
        key = name.decode('utf-8') if isinstance(name, bytes) else name
        return self._data.get(key, {})

    def get_data_handle(self) -> Dict:
        """Return the underlying data dictionary (for module execution)"""
        return self._data


class Module:
    """
    SAM simulation module wrapper

    Provides compatible interface with original ssc.py Module class,
    using PySAM modules for actual simulation execution.
    """

    # Map of module names to PySAM classes
    MODULE_MAP = {
        b'windpower': 'Windpower',
        b'pvwattsv5': 'Pvwattsv8',  # v5 -> v8 upgrade
        b'pvwattsv7': 'Pvwattsv8',
        b'pvwattsv8': 'Pvwattsv8',
        b'pvsamv1': 'Pvsam',
    }

    def __init__(self, name: bytes):
        """Create a simulation module"""
        self._name = name
        self._module = None
        self._errors = []
        self._ok = False

        if not PYSAM_AVAILABLE:
            self._errors.append("PySAM not installed")
            return

        module_name = self.MODULE_MAP.get(name.lower() if isinstance(name, bytes) else name.lower().encode())

        if module_name == 'Windpower':
            try:
                self._module = Windpower.new()
                self._ok = True
            except Exception as e:
                self._errors.append(f"Failed to create Windpower module: {e}")

        elif module_name == 'Pvwattsv8':
            try:
                self._module = Pvwattsv8.new()
                self._ok = True
            except Exception as e:
                self._errors.append(f"Failed to create PVWatts module: {e}")
        else:
            self._errors.append(f"Unknown module: {name}")

    def __del__(self):
        """Clean up module resources"""
        self._module = None

    def is_ok(self) -> bool:
        """Check if module was created successfully"""
        return self._ok and self._module is not None

    def get_module_handle(self):
        """Return the underlying PySAM module"""
        return self._module

    def exec_(self, data: Data) -> bool:
        """
        Execute the simulation with the provided data

        Args:
            data: Data object containing simulation inputs

        Returns:
            True if simulation succeeded, False otherwise
        """
        if not self.is_ok():
            return False

        self._errors = []
        data_dict = data.get_data_handle()

        try:
            module_name = self._name.lower() if isinstance(self._name, bytes) else self._name.lower().encode()

            if module_name == b'windpower':
                return self._exec_windpower(data_dict, data)
            elif module_name in [b'pvwattsv5', b'pvwattsv7', b'pvwattsv8']:
                return self._exec_pvwatts(data_dict, data)
            else:
                self._errors.append(f"Execution not implemented for module: {self._name}")
                return False

        except Exception as e:
            self._errors.append(str(e))
            logger.error(f"Module execution error: {e}")
            import traceback
            logger.error(traceback.format_exc())
            return False

    def _exec_windpower(self, data_dict: Dict, data: Data) -> bool:
        """Execute wind power simulation"""
        try:
            # Set Resource inputs
            if 'wind_resource_filename' in data_dict:
                self._module.Resource.wind_resource_filename = data_dict['wind_resource_filename']
            if 'wind_resource_model_choice' in data_dict:
                self._module.Resource.wind_resource_model_choice = int(data_dict['wind_resource_model_choice'])

            # Set Turbine inputs
            # Note: wind_resource_shear is under Turbine in PySAM, not Resource
            if 'wind_resource_shear' in data_dict:
                self._module.Turbine.wind_resource_shear = data_dict['wind_resource_shear']
            if 'wind_turbine_rotor_diameter' in data_dict:
                self._module.Turbine.wind_turbine_rotor_diameter = data_dict['wind_turbine_rotor_diameter']
            if 'wind_turbine_hub_ht' in data_dict:
                self._module.Turbine.wind_turbine_hub_ht = data_dict['wind_turbine_hub_ht']
            if 'wind_turbine_powercurve_windspeeds' in data_dict:
                self._module.Turbine.wind_turbine_powercurve_windspeeds = tuple(data_dict['wind_turbine_powercurve_windspeeds'])
            if 'wind_turbine_powercurve_powerout' in data_dict:
                self._module.Turbine.wind_turbine_powercurve_powerout = tuple(data_dict['wind_turbine_powercurve_powerout'])
            # Note: wind_turbine_cutin doesn't exist in PySAM - power curve defines cut-in implicitly

            # Set Farm inputs
            if 'system_capacity' in data_dict:
                self._module.Farm.system_capacity = data_dict['system_capacity']
            if 'wind_farm_xCoordinates' in data_dict:
                self._module.Farm.wind_farm_xCoordinates = tuple(data_dict['wind_farm_xCoordinates'])
            if 'wind_farm_yCoordinates' in data_dict:
                self._module.Farm.wind_farm_yCoordinates = tuple(data_dict['wind_farm_yCoordinates'])
            if 'wind_farm_wake_model' in data_dict:
                self._module.Farm.wind_farm_wake_model = int(data_dict['wind_farm_wake_model'])
            # Note: wind_resource_turbulence_coeff is under Farm in PySAM
            if 'wind_resource_turbulence_coeff' in data_dict:
                self._module.Farm.wind_resource_turbulence_coeff = data_dict['wind_resource_turbulence_coeff']

            # Set Losses (replaces wind_farm_losses_percent)
            if 'wind_farm_losses_percent' in data_dict:
                # Apply as generic turbine loss
                self._module.Losses.turb_generic_loss = data_dict['wind_farm_losses_percent']

            # Set adjustment factors (PySAM uses 'adjust_constant' not 'constant')
            if 'adjust:constant' in data_dict:
                self._module.AdjustmentFactors.adjust_constant = data_dict['adjust:constant']

            # Execute simulation
            self._module.execute()

            # Copy outputs back to data object
            try:
                data.set_number(b'annual_energy', self._module.Outputs.annual_energy)
            except:
                pass
            try:
                data.set_array(b'gen', list(self._module.Outputs.gen))
            except:
                pass
            try:
                data.set_number(b'capacity_factor', self._module.Outputs.capacity_factor)
            except:
                pass

            return True

        except Exception as e:
            self._errors.append(f"Windpower execution error: {e}")
            logger.error(f"Windpower execution error: {e}")
            return False

    def _exec_pvwatts(self, data_dict: Dict, data: Data) -> bool:
        """Execute PVWatts simulation"""
        try:
            # Set SolarResource inputs
            if 'solar_resource_file' in data_dict:
                self._module.SolarResource.solar_resource_file = data_dict['solar_resource_file']

            # Set SystemDesign inputs
            if 'system_capacity' in data_dict:
                self._module.SystemDesign.system_capacity = data_dict['system_capacity']
            if 'module_type' in data_dict:
                self._module.SystemDesign.module_type = int(data_dict['module_type'])
            if 'array_type' in data_dict:
                self._module.SystemDesign.array_type = int(data_dict['array_type'])
            if 'tilt' in data_dict:
                self._module.SystemDesign.tilt = data_dict['tilt']
            if 'azimuth' in data_dict:
                self._module.SystemDesign.azimuth = data_dict['azimuth']
            if 'dc_ac_ratio' in data_dict:
                self._module.SystemDesign.dc_ac_ratio = data_dict['dc_ac_ratio']
            if 'inv_eff' in data_dict:
                self._module.SystemDesign.inv_eff = data_dict['inv_eff']
            if 'losses' in data_dict:
                self._module.SystemDesign.losses = data_dict['losses']
            if 'gcr' in data_dict:
                self._module.SystemDesign.gcr = data_dict['gcr']

            # Set adjustment factors (PySAM uses 'adjust_constant' not 'constant')
            if 'adjust:constant' in data_dict:
                self._module.AdjustmentFactors.adjust_constant = data_dict['adjust:constant']

            # Execute simulation
            self._module.execute()

            # Copy outputs back to data object
            try:
                data.set_number(b'annual_energy', self._module.Outputs.annual_energy)
            except:
                pass
            try:
                data.set_array(b'gen', list(self._module.Outputs.gen))
            except:
                pass
            try:
                data.set_number(b'capacity_factor', self._module.Outputs.capacity_factor)
            except:
                pass
            try:
                data.set_array(b'ac', list(self._module.Outputs.ac))
            except:
                pass
            try:
                data.set_array(b'dc', list(self._module.Outputs.dc))
            except:
                pass

            return True

        except Exception as e:
            self._errors.append(f"PVWatts execution error: {e}")
            logger.error(f"PVWatts execution error: {e}")
            return False

    def log(self, idx: int) -> Optional[bytes]:
        """Get log/error message at index"""
        if idx < len(self._errors):
            return self._errors[idx].encode('utf-8')
        return None


class Entry:
    """
    Iterator for available SSC modules

    Note: PySAM doesn't provide the same module enumeration as the SSC API,
    so this returns a fixed list of commonly used modules.
    """

    MODULES = [
        (b'windpower', b'Wind power simulation', 1),
        (b'pvwattsv8', b'PVWatts photovoltaic system model', 8),
        (b'pvsamv1', b'Detailed photovoltaic system model', 1),
    ]

    def __init__(self):
        self._idx = 0
        self._entry = None

    def reset(self):
        self._idx = 0

    def get(self) -> bool:
        if self._idx < len(self.MODULES):
            self._entry = self.MODULES[self._idx]
            self._idx += 1
            return True
        else:
            self.reset()
            return False

    def name(self) -> Optional[bytes]:
        if self._entry:
            return self._entry[0]
        return None

    def description(self) -> Optional[bytes]:
        if self._entry:
            return self._entry[1]
        return None

    def version(self) -> int:
        if self._entry:
            return self._entry[2]
        return -1


class Info:
    """
    Iterator for module variable information

    Note: PySAM provides variable information differently than the SSC API.
    This is a compatibility stub.
    """

    def __init__(self, module: Module):
        self._module = module
        self._idx = 0
        self._vars = []
        self._current = None

    def reset(self):
        self._idx = 0

    def get(self) -> bool:
        # PySAM doesn't provide the same variable enumeration
        # This is a stub for compatibility
        return False

    def name(self) -> Optional[bytes]:
        return None

    def var_type(self) -> int:
        return -1

    def data_type(self) -> int:
        return -1

    def label(self) -> Optional[bytes]:
        return None

    def units(self) -> Optional[bytes]:
        return None

    def meta(self) -> Optional[bytes]:
        return None

    def group(self) -> Optional[bytes]:
        return None

    def required(self) -> Optional[bytes]:
        return None

    def constraints(self) -> Optional[bytes]:
        return None
