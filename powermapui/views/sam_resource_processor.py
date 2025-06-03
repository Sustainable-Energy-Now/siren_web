"""
SAM Resource Processor Module
Handles System Advisor Model (SAM) integration for wind and solar resource processing
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
from pathlib import Path
import re
import math
import gzip
import zipfile

# Import SAM SSC module
from siren_web.siren.utilities.ssc import Data, Module, API

logger = logging.getLogger(__name__)

@dataclass
class WeatherData:
    """Container for weather data"""
    wind_speed: List[float] = None
    wind_direction: List[float] = None
    temperature: List[float] = None
    pressure: List[float] = None
    ghi: List[float] = None  # Global Horizontal Irradiance
    dni: List[float] = None  # Direct Normal Irradiance
    dhi: List[float] = None  # Diffuse Horizontal Irradiance
    humidity: List[float] = None

class WeatherFileFinder:
    """Helper class for finding nearest weather files"""
    
    def __init__(self, weather_data_dir: Path):
        self.weather_data_dir = Path(weather_data_dir)
        self._file_cache = {}  # Cache for parsed file coordinates
        
    def get_weather_file_path(self, latitude: float, longitude: float, 
                            technology: str, demand_year: str) -> Optional[Path]:
        """
        Find the nearest weather file for given coordinates, technology and year
        
        Args:
            latitude: Facility latitude
            longitude: Facility longitude  
            technology: 'wind' or 'solar'
            demand_year: Year string (e.g. '2024')
            
        Returns:
            Path to nearest weather file or None if not found
        """
        # Determine weather subdirectory and file extension
        if technology.lower() in ['onshore wind', 'offshore wind', 'offshore wind floating']:
            weather_subdir = 'wind_weather'
            file_extension = '.srz'
            file_prefix = 'wind_weather'
        elif technology.lower() in ['fixed pv', 'single axis pv', 'rooftop pv']:
            weather_subdir = 'solar_weather'
            file_extension = '.smz'
            file_prefix = 'solar_weather'
        else:
            logger.warning(f"Unknown technology type: {technology}")
            return None
        
        # Build path to weather files
        weather_dir = self.weather_data_dir / weather_subdir / demand_year
        
        if not weather_dir.exists():
            logger.warning(f"Weather directory does not exist: {weather_dir}")
            return None
        
        # Find nearest weather file
        nearest_file = self._find_nearest_weather_file(
            weather_dir, latitude, longitude, file_prefix, file_extension, demand_year
        )
        
        if nearest_file:
            logger.info(f"Found weather file for {technology} at ({latitude}, {longitude}): {nearest_file}")
            return nearest_file
        else:
            logger.warning(f"No weather file found for {technology} at ({latitude}, {longitude}) for year {demand_year}")
            return None

    def _find_nearest_weather_file(self, weather_dir: Path, target_lat: float, 
                                 target_lon: float, file_prefix: str, 
                                 file_extension: str, demand_year: str) -> Optional[Path]:
        """
        Find the weather file with coordinates nearest to target coordinates
        
        Args:
            weather_dir: Directory containing weather files
            target_lat: Target latitude
            target_lon: Target longitude
            file_prefix: File prefix ('wind_weather' or 'solar_weather')
            file_extension: File extension ('.srz' or '.smz')
            demand_year: Year string
            
        Returns:
            Path to nearest file or None
        """
        # Cache key for this directory
        cache_key = f"{weather_dir}_{file_prefix}_{file_extension}_{demand_year}"
        
        if cache_key not in self._file_cache:
            # Parse all weather files in directory
            self._file_cache[cache_key] = self._parse_weather_files(
                weather_dir, file_prefix, file_extension, demand_year
            )
        
        weather_files = self._file_cache[cache_key]
        
        if not weather_files:
            return None
        
        # Find nearest file by calculating distances
        nearest_file = None
        min_distance = float('inf')
        
        for file_path, (file_lat, file_lon) in weather_files.items():
            distance = self._calculate_distance(target_lat, target_lon, file_lat, file_lon)
            
            if distance < min_distance:
                min_distance = distance
                nearest_file = file_path
        
        logger.debug(f"Nearest weather file distance: {min_distance:.2f} km")
        return nearest_file

    def _parse_smz_file(self, file_path: Path) -> WeatherData:
        """
        Parse .smz/.srz weather files using the new encoding-safe file reader
        """
        weather_data = WeatherData()
        
        try:
            # Use the new encoding-safe file reader
            content = self._read_weather_file(file_path)
            
            # Simple parsing - adjust column indices based on your file format
            lines = content.strip().split('\n')
            
            # Initialize lists based on file extension
            file_ext = file_path.suffix.lower()
            
            if file_ext == '.srz':  # Wind file
                weather_data.wind_speed = []
                weather_data.wind_direction = []
                weather_data.temperature = []
                weather_data.pressure = []
            elif file_ext == '.smz':  # Solar file
                weather_data.ghi = []
                weather_data.dni = []
                weather_data.dhi = []
                weather_data.temperature = []
                weather_data.wind_speed = []
            
            # Parse data lines (skip headers)
            for line in lines:
                line = line.strip()
                if not line or line.startswith('#') or line.startswith('Year'):
                    continue
                    
                try:
                    # Try different delimiters
                    parts = None
                    for delimiter in [',', '\t', ' ', ';']:
                        test_parts = [part.strip() for part in line.split(delimiter) if part.strip()]
                        if len(test_parts) >= 4:  # Reasonable number of columns
                            parts = test_parts
                            break
                    
                    if not parts:
                        continue
                    
                    # Parse based on file type - ADJUST THESE INDICES FOR YOUR FILE FORMAT
                    if file_ext == '.srz' and len(parts) >= 4:  # Wind file
                        # Assuming format: wind_speed, wind_direction, temperature, pressure
                        # ADJUST these indices based on your actual .srz file format
                        wind_speed = float(parts[0])
                        wind_direction = float(parts[1])
                        temperature = float(parts[2])
                        pressure = float(parts[3]) if len(parts) > 3 else 1013.25
                        
                        weather_data.wind_speed.append(wind_speed)
                        weather_data.wind_direction.append(wind_direction)
                        weather_data.temperature.append(temperature)
                        weather_data.pressure.append(pressure)
                        
                    elif file_ext == '.smz' and len(parts) >= 5:  # Solar file
                        # Assuming format: GHI, DNI, DHI, temperature, wind_speed
                        # ADJUST these indices based on your actual .smz file format
                        ghi = float(parts[0])
                        dni = float(parts[1])
                        dhi = float(parts[2])
                        temperature = float(parts[3])
                        wind_speed = float(parts[4]) if len(parts) > 4 else 3.0
                        
                        weather_data.ghi.append(ghi)
                        weather_data.dni.append(dni)
                        weather_data.dhi.append(dhi)
                        weather_data.temperature.append(temperature)
                        weather_data.wind_speed.append(wind_speed)
                        
                except (ValueError, IndexError) as e:
                    logger.debug(f"Skipping invalid line in {file_path}: {line}")
                    continue
            
            # Log success
            if file_ext == '.srz':
                logger.info(f"Parsed wind weather: {len(weather_data.wind_speed)} records from {file_path}")
            else:
                logger.info(f"Parsed solar weather: {len(weather_data.ghi)} records from {file_path}")
                
        except Exception as e:
            raise WeatherFileError(f"Error parsing weather file {file_path}: {e}")
            
        return weather_data

    def _parse_weather_files(self, weather_dir: Path, file_prefix: str, 
                           file_extension: str, demand_year: str) -> Dict[Path, Tuple[float, float]]:
        """
        Parse all weather files in directory and extract coordinates
        
        Returns:
            Dictionary mapping file paths to (latitude, longitude) tuples
        """
        weather_files = {}
        
        # Pattern to match weather files: solar_weather_-27.7500_114.0000_2024.smz
        pattern = rf"{re.escape(file_prefix)}_(-?\d+\.?\d*)_(-?\d+\.?\d*)_{re.escape(demand_year)}{re.escape(file_extension)}"
        
        try:
            for file_path in weather_dir.iterdir():
                if file_path.is_file():
                    match = re.match(pattern, file_path.name)
                    if match:
                        try:
                            latitude = float(match.group(1))
                            longitude = float(match.group(2))
                            weather_files[file_path] = (latitude, longitude)
                            # logger.debug(f"Parsed weather file: {file_path.name} -> ({latitude}, {longitude})")
                        except ValueError as e:
                            logger.warning(f"Could not parse coordinates from {file_path.name}: {e}")
                            
        except Exception as e:
            logger.error(f"Error reading weather directory {weather_dir}: {e}")
        
        logger.info(f"Found {len(weather_files)} weather files in {weather_dir}")
        return weather_files
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """
        Calculate the great circle distance between two points on Earth
        Uses the Haversine formula
        
        Args:
            lat1, lon1: Latitude and longitude of first point (degrees)
            lat2, lon2: Latitude and longitude of second point (degrees)
            
        Returns:
            Distance in kilometers
        """
        # Convert latitude and longitude from degrees to radians
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        # Haversine formula
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = (math.sin(dlat / 2) ** 2 + 
             math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon / 2) ** 2)
        c = 2 * math.asin(math.sqrt(a))
        
        # Radius of Earth in kilometers
        r = 6371
        
        # Calculate distance
        distance = r * c
        return distance
    
    def clear_cache(self):
        """Clear the file coordinate cache"""
        self._file_cache.clear()

@dataclass
class SimulationResults:
    """Container for simulation results"""
    annual_energy: float
    hourly_generation: List[float]
    capacity_factor: float
    additional_metrics: Dict[str, Any] = None

class SAMError(Exception):
    """Custom exception for SAM-related errors"""
    pass

class WeatherFileError(Exception):
    """Custom exception for weather file-related errors"""
    pass

class SAMResourceProcessor:
    """
    Handles SAM SSC integration for wind and solar resource processing
    """
    
    def __init__(self, config_settings: Dict = None, weather_data_dir: str = "weather_data", 
                 power_curves_dir: str = "power_curves"):
        """
        Initialize SAM Resource Processor
        
        Args:
            config_settings: Configuration dictionary
            weather_data_dir: Directory containing weather files
            power_curves_dir: Directory containing power curve files
        """
        self.config = config_settings or {}
        self.weather_data_dir = Path(weather_data_dir)
        # Use Django settings if no explicit paths provided
        from django.conf import settings
        self.weather_data_dir = Path(weather_data_dir or settings.WEATHER_DATA_DIR)
        self.power_curves_dir = Path(power_curves_dir or getattr(settings, 'POWER_CURVES_DIR', 'power_curves'))
        
        # Initialize weather file finder
        self.weather_finder = WeatherFileFinder(self.weather_data_dir)
        
        # Ensure directories exist
        if not self.weather_data_dir.exists():
            logger.warning(f"Weather data directory does not exist: {self.weather_data_dir}")
        self.api = API()
        
        logger.info(f"SAM API Version: {self.api.version()}")
        logger.info(f"SAM Build Info: {self.api.build_info()}")

    def get_weather_file_path(self, latitude: float, longitude: float, 
                            technology: str, demand_year: str) -> Optional[Path]:
        """
        Find the nearest weather file for given coordinates, technology and year
        
        Args:
            latitude: Facility latitude
            longitude: Facility longitude
            technology: Technology type ('wind' or 'solar') 
            demand_year: Year string (e.g. '2024')
            
        Returns:
            Path to nearest weather file or None if not found
        """
        return self.weather_finder.get_weather_file_path(
            latitude, longitude, technology, demand_year
        )
        
    def get_power_curve_file_path(self, turbine_model: str) -> Path:
        """Generate power curve file path based on turbine model"""
        filename = f"{turbine_model}.pow"
        return self.power_curves_dir / filename
    
    def load_weather_data(self, weather_file_path: Path) -> WeatherData:
        """
        Load weather data from .smz files
        
        Args:
            weather_file_path: Path to weather file
            
        Returns:
            WeatherData object
            
        Raises:
            WeatherFileError: If file cannot be loaded or parsed
        """
        if not weather_file_path.exists():
            raise WeatherFileError(f"Weather file not found: {weather_file_path}")
            
        try:
            weather_data = self._parse_smz_file(weather_file_path)
            logger.info(f"Loaded weather data from {weather_file_path}")
            return weather_data
        except Exception as e:
            raise WeatherFileError(f"Error parsing weather file {weather_file_path}: {e}")
    
    def load_power_curve(self, pow_file_path: Path) -> Dict[float, float]:
        """
        Load turbine power curve from .pow files
        
        Args:
            pow_file_path: Path to power curve file
            
        Returns:
            Dictionary mapping wind speeds to power outputs
        """
        power_curve = {}
        
        if not pow_file_path.exists():
            logger.warning(f"Power curve file not found: {pow_file_path}")
            return power_curve
            
        try:
            with open(pow_file_path, 'r') as f:
                lines = f.readlines()
                
            # Skip header lines and parse power values
            power_values = []
            for line_num, line in enumerate(lines, 1):
                line = line.strip()
                if not line or line.startswith('#'):
                    continue
                    
                # Remove quotes if present
                line = line.strip('"')
                
                try:
                    # Try to parse as a number
                    power_value = float(line)
                    power_values.append(power_value)
                except ValueError:
                    # Skip non-numeric lines (like turbine name, etc.)
                    logger.debug(f"Skipping non-numeric line {line_num} in {pow_file_path}: {line}")
                    continue
            
            # Create wind speed to power mapping
            # Assuming standard wind speeds from 0 to (number of power values - 1) m/s
            if power_values:
                for wind_speed, power in enumerate(power_values):
                    power_curve[float(wind_speed)] = power
                    
                logger.info(f"Loaded power curve with {len(power_curve)} points from {pow_file_path}")
                logger.debug(f"Power curve range: 0-{len(power_values)-1} m/s, {min(power_values)}-{max(power_values)} kW")
            else:
                logger.warning(f"No valid power values found in {pow_file_path}")
                
        except Exception as e:
            logger.error(f"Error loading power curve {pow_file_path}: {e}")
            return {}
            
        return power_curve
    
    def process_wind_facility(self, facility, demand_year: str,
                            power_curve: Dict[float, float] = None) -> SimulationResults:
        """
        Process wind facility using SAM wind power module with file-based approach
        """
        temp_weather_file = None
        try:
            logger.info(f"Starting wind simulation for {facility.facility_name}")
            
            # Get weather file and parse data
            weather_file_path = self.get_weather_file_path(
                facility.latitude, facility.longitude,
                facility.idtechnologies.technology_name,
                demand_year
            )
            
            if not weather_file_path or not weather_file_path.exists():
                raise SAMError(f"Weather file not found for {facility.facility_name}")
            
            # Load weather data
            weather_data = self.load_weather_data(weather_file_path)
            
            if not weather_data.wind_speed or len(weather_data.wind_speed) == 0:
                raise SAMError(f"No wind data found for {facility.facility_name}")
            
            # Create temporary SAM-compatible weather file
            temp_weather_file = self._create_sam_weather_file(weather_data, facility, demand_year)
            
            # Create SAM data container
            data = Data()
            
            # Use the temporary weather file (like SIREN does)
            data.set_string(b'wind_resource_filename', str(temp_weather_file).encode('utf-8'))
            
            # REQUIRED: Wind resource parameters
            data.set_number(b'wind_resource_shear', 0.14)
            data.set_number(b'wind_resource_turbulence_coeff', 0.1)
            data.set_number(b'wind_resource_model_choice', 0)  # Use hourly data
            
            # REQUIRED: System capacity in kW
            data.set_number(b'system_capacity', float(facility.capacity * 1000))
            
            # REQUIRED: Turbine parameters
            rotor_diameter = 77.0  # Default, could be from turbine specs
            data.set_number(b'wind_turbine_rotor_diameter', rotor_diameter)
            data.set_number(b'wind_turbine_hub_ht', float(facility.hub_height or 85))
            
            # REQUIRED: Power curve
            if power_curve and len(power_curve) > 0:
                wind_speeds = sorted(power_curve.keys())
                power_outputs = [power_curve[ws] for ws in wind_speeds]
                data.set_array(b'wind_turbine_powercurve_windspeeds', wind_speeds)
                data.set_array(b'wind_turbine_powercurve_powerout', power_outputs)
                
                # Extract cut-in speed from power curve (first non-zero power)
                cutin_speed = 3.0  # default
                for ws, power in power_curve.items():
                    if power > 0:
                        cutin_speed = ws
                        break
                data.set_number(b'wind_turbine_cutin', cutin_speed)
                
                logger.debug(f"Using custom power curve: {len(power_curve)} points, cut-in: {cutin_speed} m/s")
            else:
                # Use default power curve based on typical 1.87MW turbine
                default_speeds = list(range(26))  # 0-25 m/s
                default_powers = [0, 0, 50, 150, 300, 500, 750, 900, 1100, 1300, 1500, 1650, 1750, 1800, 1850, 1870, 1870, 1870, 1870, 1870, 1870, 1870, 1870, 1870, 1870, 0]
                data.set_array(b'wind_turbine_powercurve_windspeeds', default_speeds)
                data.set_array(b'wind_turbine_powercurve_powerout', default_powers)
                data.set_number(b'wind_turbine_cutin', 3.0)
                
                logger.debug("Using default power curve")
            
            # REQUIRED: Wind farm layout
            no_turbines = int(facility.no_turbines) if facility.no_turbines and facility.no_turbines > 0 else 1
            
            # Calculate turbine coordinates in a grid (SIREN approach)
            import math
            t_rows = int(math.ceil(math.sqrt(no_turbines)))
            
            # Spacing in rotor diameters (like SIREN)
            turbine_spacing = 8  # rotor diameters
            row_spacing = 8      # rotor diameters
            offset_spacing = 4   # rotor diameters
            
            wt_x = []
            wt_y = []
            ctr = no_turbines
            
            for r in range(t_rows):
                for c in range(t_rows):
                    x_coord = r * row_spacing * rotor_diameter
                    y_coord = (c * turbine_spacing * rotor_diameter + 
                            (r % 2) * offset_spacing * rotor_diameter)
                    wt_x.append(x_coord)
                    wt_y.append(y_coord)
                    ctr -= 1
                    if ctr < 1:
                        break
                if ctr < 1:
                    break
            
            data.set_array(b'wind_farm_xCoordinates', wt_x)
            data.set_array(b'wind_farm_yCoordinates', wt_y)
            
            logger.debug(f"Wind farm layout: {no_turbines} turbines in {t_rows}x{t_rows} grid")
            
            # REQUIRED: Wind farm parameters
            data.set_number(b'wind_farm_losses_percent', 2.0)  # Default 2% losses
            data.set_number(b'wind_farm_wake_model', 0)  # No wake model
            
            # REQUIRED: Adjustment factors
            data.set_number(b'adjust:constant', 0.0)  # No constant adjustment
            
            logger.debug(f"Set all required parameters for {facility.facility_name}")
            logger.debug(f"Using temporary weather file: {temp_weather_file}")
            
            # Create and execute wind power module
            wind_module = Module(b'windpower')
            
            if not wind_module.is_ok():
                raise SAMError("Failed to create wind power module")
            
            logger.debug("Executing wind simulation...")
            success = wind_module.exec_(data)
            
            if not success:
                error_msg = self._get_module_errors(wind_module)
                raise SAMError(f"Wind simulation failed: {error_msg}")
            
            # Extract results
            annual_energy = data.get_number(b'annual_energy')
            hourly_generation = data.get_array(b'gen')
            capacity_factor = data.get_number(b'capacity_factor')
            
            results = SimulationResults(
                annual_energy=annual_energy,
                hourly_generation=hourly_generation,
                capacity_factor=capacity_factor
            )
            
            logger.info(f"Wind simulation completed for {facility.facility_name}: "
                    f"{results.capacity_factor:.1f}% CF, {results.annual_energy:.0f} kWh/year")
            
            return results
            
        except Exception as e:
            if isinstance(e, SAMError):
                raise
            logger.error(f"Error in wind facility processing: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise SAMError(f"Error in wind facility processing: {e}")
            
        finally:
            # Clean up temporary file
            if temp_weather_file and temp_weather_file.exists():
                try:
                    import os
                    os.remove(temp_weather_file)
                    logger.debug(f"Cleaned up temporary file: {temp_weather_file}")
                except:
                    pass

    def _create_sam_weather_file(self, weather_data: WeatherData, facility, demand_year: str):
        """
        Create a temporary weather file in SAM's expected format
        """
        import tempfile
        import os
        
        # Create temporary file
        temp_dir = tempfile.gettempdir()
        temp_filename = f"sam_wind_{facility.facility_code}_{os.getpid()}.srw"
        temp_path = Path(temp_dir) / temp_filename
        
        try:
            with open(temp_path, 'w', newline='') as f:
                # Write header information (based on SAM wind file format)
                f.write(f"Source,Location,{facility.latitude},{facility.longitude},100,10,1,{demand_year},8760\n")
                f.write(f"Generated from SIREN weather data\n")
                f.write("Temperature,Pressure,Speed,Direction\n")
                f.write("C,atm,m/s,degrees\n")
                f.write("100,100,100,100\n")
                
                # Write weather data
                for i in range(len(weather_data.wind_speed)):
                    temp = weather_data.temperature[i] if i < len(weather_data.temperature) else 20.0
                    pres = weather_data.pressure[i] if i < len(weather_data.pressure) else 1.0
                    speed = weather_data.wind_speed[i]
                    direction = weather_data.wind_direction[i] if i < len(weather_data.wind_direction) else 0.0
                    
                    f.write(f"{temp},{pres},{speed},{direction}\n")
            
            logger.debug(f"Created temporary SAM weather file: {temp_path}")
            return temp_path
            
        except Exception as e:
            raise WeatherFileError(f"Error creating temporary weather file: {e}")

    def _create_wind_resource_table(self, weather_data: WeatherData, facility, demand_year: str):
        """
        Create wind resource table in the format SAM expects
        
        SAM wants a table with:
        - Numbers: lat, lon, elev, year
        - Arrays: heights, fields (temp=1,pres=2,speed=3,dir=4)
        - Matrix: data (nstep x Nheights)
        """
        # Create a new data table for wind resource
        wind_resource_table = Data()
        
        # Set location and year info - ALL WITH BYTE STRINGS
        wind_resource_table.set_number(b'lat', float(facility.latitude))
        wind_resource_table.set_number(b'lon', float(facility.longitude))
        wind_resource_table.set_number(b'elev', 0.0)  # Elevation - use 0 if unknown
        wind_resource_table.set_number(b'year', int(demand_year))
        
        # Set measurement heights - we have data at 10m and 100m based on your file format
        heights = [10.0, 100.0]  # Measurement heights in meters
        wind_resource_table.set_array(b'heights', heights)
        
        # Set field codes: temp=1, pres=2, speed=3, dir=4
        fields = [1, 2, 3, 4]  # Temperature, Pressure, Speed, Direction
        wind_resource_table.set_array(b'fields', fields)
        
        # Create data matrix: nstep x Nheights
        # We need to organize data as [temp_10m, pres_10m, speed_10m, dir_10m, temp_100m, pres_100m, speed_100m, dir_100m]
        nstep = len(weather_data.wind_speed)
        nheights = len(heights)
        nfields = len(fields)
        
        # Matrix dimensions: nstep rows x (nheights * nfields) columns
        # Each row represents one time step
        # Columns are organized as: [field1_height1, field2_height1, field3_height1, field4_height1, field1_height2, ...]
        
        data_matrix = []
        
        for step in range(nstep):
            row = []
            
            # For each height
            for height_idx in range(nheights):
                # For each field (temp=1, pres=2, speed=3, dir=4)
                for field in fields:
                    if field == 1:  # Temperature
                        value = weather_data.temperature[step] if step < len(weather_data.temperature) else 20.0
                    elif field == 2:  # Pressure  
                        value = weather_data.pressure[step] if step < len(weather_data.pressure) else 1.0
                    elif field == 3:  # Wind Speed
                        if height_idx == 0:  # 10m height
                            # For 10m, we might need to extrapolate from 100m or use available data
                            value = weather_data.wind_speed[step] * 0.8  # Rough scaling from 100m to 10m
                        else:  # 100m height
                            value = weather_data.wind_speed[step]
                    elif field == 4:  # Wind Direction
                        value = weather_data.wind_direction[step] if step < len(weather_data.wind_direction) else 0.0
                    else:
                        value = 0.0
                    
                    row.append(float(value))
            
            data_matrix.append(row)
        
        # Set the data matrix - WITH BYTE STRING
        wind_resource_table.set_matrix(b'data', data_matrix)
        
        logger.debug(f"Created wind resource table: {nstep} time steps, {nheights} heights, {nfields} fields")
        logger.debug(f"Matrix dimensions: {len(data_matrix)} x {len(data_matrix[0]) if data_matrix else 0}")
        
        return wind_resource_table.get_data_handle()

    def process_solar_facility(self, facility, weather_data: WeatherData) -> SimulationResults:
        """
        Process solar facility using SAM PV module
        
        Args:
            facility: Facility model instance
            weather_data: WeatherData object
            
        Returns:
            SimulationResults object
            
        Raises:
            SAMError: If simulation fails
        """
        try:
            # Create SAM data container
            data = Data()
            
            # Set weather data
            self._set_solar_weather_data(data, weather_data)
            
            # Set system parameters
            self._set_solar_system_parameters(data, facility)
            
            # Create and execute PV module
            pv_module = Module(b'pvwattsv7')
            
            if not pv_module.is_ok():
                raise SAMError("Failed to create PV module")
                
            success = pv_module.exec_(data)
            
            if not success:
                error_msg = self._get_module_errors(pv_module)
                raise SAMError(f"Solar simulation failed: {error_msg}")
            
            # Extract results
            results = self._extract_solar_results(data)
            
            logger.info(f"Solar simulation completed for {facility.facility_name}: "
                    f"{results.capacity_factor:.1f}% CF, {results.annual_energy:.0f} kWh/year")
            
            return results
            
        except Exception as e:
            if isinstance(e, SAMError):
                raise
            raise SAMError(f"Error in solar facility processing: {e}")
    
    def _parse_smz_file(self, file_path: Path) -> WeatherData:
        """
        Parse .smz/.srz weather files based on actual SIREN file format
        """
        weather_data = WeatherData()
        
        try:
            # Use the encoding-safe file reader
            content = self._read_weather_file(file_path)
            lines = content.strip().split('\n')
            
            file_ext = file_path.suffix.lower()
            
            if file_ext == '.srz':  # Wind file
                weather_data.wind_speed = []
                weather_data.wind_direction = []
                weather_data.temperature = []
                weather_data.pressure = []
                
                # Based on your file format:
                # Line 0: header with metadata
                # Line 1: data source info
                # Line 2: column headers - "Temperature,Pressure,Direction,Speed,Direction,Speed"
                # Line 3: units - "C,atm,degrees,m/s,degrees,m/s"
                # Line 4: heights - "2,0,10,10,100,100" (measurement heights in meters)
                # Line 5+: actual data
                
                # Start parsing from line 5 (data starts after headers)
                for line in lines[5:]:
                    line = line.strip()
                    if not line:
                        continue
                        
                    try:
                        parts = [part.strip() for part in line.split(',')]
                        if len(parts) >= 6:
                            # Format: Temperature,Pressure,Direction@10m,Speed@10m,Direction@100m,Speed@100m
                            temperature = float(parts[0])  # Temperature in C
                            pressure = float(parts[1])     # Pressure in atm
                            # Wind direction at 10m height
                            wind_direction_10m = float(parts[2])  # degrees
                            # Wind speed at 10m height  
                            wind_speed_10m = float(parts[3])      # m/s
                            # Wind direction at 100m height
                            wind_direction_100m = float(parts[4]) # degrees
                            # Wind speed at 100m height
                            wind_speed_100m = float(parts[5])     # m/s
                            
                            # Use 100m wind data if available (better for wind turbines)
                            # or 10m data as fallback
                            wind_speed = wind_speed_100m if wind_speed_100m > 0 else wind_speed_10m
                            wind_direction = wind_direction_100m if wind_speed_100m > 0 else wind_direction_10m
                            
                            weather_data.temperature.append(temperature)
                            weather_data.pressure.append(pressure)
                            weather_data.wind_speed.append(wind_speed)
                            weather_data.wind_direction.append(wind_direction)
                            
                    except (ValueError, IndexError) as e:
                        logger.debug(f"Skipping invalid wind data line: {line} - {e}")
                        continue
                
                logger.info(f"Parsed wind weather: {len(weather_data.wind_speed)} records from {file_path}")
                
            elif file_ext == '.smz':  # Solar file - similar format expected
                weather_data.ghi = []
                weather_data.dni = []
                weather_data.dhi = []
                weather_data.temperature = []
                weather_data.wind_speed = []
                
                # Parse solar data (adjust based on actual .smz format when you see it)
                for line in lines[5:]:  # Assuming similar header structure
                    line = line.strip()
                    if not line:
                        continue
                        
                    try:
                        parts = [part.strip() for part in line.split(',')]
                        if len(parts) >= 5:
                            # Adjust these based on actual .smz file format
                            # This is a placeholder - you'll need to debug a .smz file
                            ghi = float(parts[0])
                            dni = float(parts[1])
                            dhi = float(parts[2])
                            temperature = float(parts[3])
                            wind_speed = float(parts[4])
                            
                            weather_data.ghi.append(ghi)
                            weather_data.dni.append(dni)
                            weather_data.dhi.append(dhi)
                            weather_data.temperature.append(temperature)
                            weather_data.wind_speed.append(wind_speed)
                            
                    except (ValueError, IndexError) as e:
                        logger.debug(f"Skipping invalid solar data line: {line} - {e}")
                        continue
                
                logger.info(f"Parsed solar weather: {len(weather_data.ghi)} records from {file_path}")
            
        except Exception as e:
            raise WeatherFileError(f"Error parsing weather file {file_path}: {e}")
            
        return weather_data
    
    def _set_wind_weather_data(self, data: Data, weather_data: WeatherData):
        """Set wind-specific weather data in SAM Data object"""
        if weather_data.wind_speed:
            data.set_array(b'wind_resource_data', weather_data.wind_speed)
        if weather_data.wind_direction:
            data.set_array(b'wind_resource_dir', weather_data.wind_direction)
        if weather_data.temperature:
            data.set_array(b'wind_resource_temp', weather_data.temperature)
        if weather_data.pressure:
            data.set_array(b'wind_resource_pres', weather_data.pressure)
    
    def _set_wind_turbine_parameters(self, data: Data, facility, power_curve: Dict[float, float]):
        """Set wind turbine parameters in SAM Data object"""
        data.set_number(b'wind_resource_model_choice', 0)  # Use wind resource data
        data.set_number(b'wind_turbine_hub_ht', facility.hub_height or 80)
        data.set_number(b'system_capacity', facility.capacity or 1000)  # kW
        
        # Set power curve if available
        if power_curve:
            wind_speeds = sorted(power_curve.keys())
            power_outputs = [power_curve[ws] for ws in wind_speeds]
            data.set_array(b'wind_turbine_powercurve_windspeeds', wind_speeds)
            data.set_array(b'wind_turbine_powercurve_powerout', power_outputs)
        
        # Set number of turbines
        if facility.no_turbines:
            data.set_number(b'wind_farm_wake_model', 0)  # No wake model for simplicity
    
    def _set_solar_weather_data(self, data: Data, weather_data: WeatherData):
        """Set solar-specific weather data in SAM Data object"""
        # SAM expects weather data in a specific format for PVWatts
        if weather_data.ghi:
            data.set_array(b'solar_resource_data', weather_data.ghi)
        if weather_data.dni:
            data.set_array(b'solar_resource_data', weather_data.dni)
        if weather_data.dhi:
            data.set_array(b'solar_resource_data', weather_data.dhi)
        if weather_data.temperature:
            data.set_array(b'solar_resource_data', weather_data.temperature)
        if weather_data.wind_speed:
            data.set_array(b'solar_resource_data', weather_data.wind_speed)
    
    def _set_solar_system_parameters(self, data: Data, facility):
        """Set solar system parameters in SAM Data object"""
        data.set_number(b'system_capacity', float(facility.capacity or 1000))  # kW
        data.set_number(b'module_type', 0)  # Standard module
        data.set_number(b'array_type', 0)  # Fixed tilt
        data.set_number(b'tilt', float(facility.tilt or 25))  # degrees
        data.set_number(b'azimuth', 180)  # South-facing
        data.set_number(b'dc_ac_ratio', 1.2)
        data.set_number(b'losses', 14.0)  # System losses %
        data.set_number(b'inv_eff', 96.0)  # Inverter efficiency %
    
    def _extract_wind_results(self, data: Data) -> SimulationResults:
        """Extract results from wind simulation"""
        annual_energy = data.get_number(b'annual_energy')  # kWh
        hourly_generation = data.get_array(b'gen')  # kW for each hour
        capacity_factor = data.get_number(b'capacity_factor')  # %
        
        return SimulationResults(
            annual_energy=annual_energy,
            hourly_generation=hourly_generation,
            capacity_factor=capacity_factor
        )
    
    def _extract_solar_results(self, data: Data) -> SimulationResults:
        """Extract results from solar simulation"""
        annual_energy = data.get_number(b'annual_energy')  # kWh
        hourly_generation = data.get_array(b'gen')  # kW for each hour
        capacity_factor = data.get_number(b'capacity_factor')  # %
        
        return SimulationResults(
            annual_energy=annual_energy,
            hourly_generation=hourly_generation,
            capacity_factor=capacity_factor
        )

    def _get_module_errors(self, module: Module) -> str:
        """Extract error messages from SAM module"""
        error_msg = ""
        idx = 0
        while True:
            msg = module.log(idx)
            if msg is None:
                break
            error_msg += msg.decode('utf-8') + "\n"
            idx += 1
        return error_msg
    
    def debug_weather_file_format(self, file_path: Path, num_lines: int = 10):
        """
        Debug method to examine the actual format of your weather files
        Call this to see what your files look like before adjusting the parsing
        """
        try:
            content = self._read_weather_file(file_path)
            lines = content.split('\n')
            
            logger.info(f"\n=== DEBUG: {file_path} ===")
            logger.info(f"Total lines: {len(lines)}")
            logger.info(f"First {num_lines} lines:")
            
            for i, line in enumerate(lines[:num_lines]):
                logger.info(f"Line {i:2d}: {repr(line)}")
                
            # Try to parse a sample line
            for line in lines[:20]:  # Check first 20 lines
                line = line.strip()
                if line and not line.startswith('#') and not line.startswith('Year'):
                    logger.info(f"\nSample data line: {repr(line)}")
                    
                    # Show how it splits with different delimiters
                    for delimiter in [',', '\t', ' ', ';']:
                        parts = [part.strip() for part in line.split(delimiter) if part.strip()]
                        if len(parts) > 1:
                            logger.info(f"  Split by '{delimiter}': {parts[:8]}...")  # Show first 8 parts
                    break
                    
        except Exception as e:
            logger.error(f"Error examining file {file_path}: {e}")
    
    def _read_weather_file(self, file_path: Path) -> str:
        """
        Read weather file with multiple encoding attempts and compression detection
        """
        import gzip
        import zipfile
        
        # Try to determine if file is compressed
        content = None
        
        # First, try to detect if it's a compressed file
        try:
            # Check if it's a gzip file
            with gzip.open(file_path, 'rt', encoding='utf-8') as f:
                content = f.read()
                logger.debug(f"Successfully read {file_path} as gzip file")
                return content
        except:
            pass
            
        try:
            # Check if it's a zip file
            with zipfile.ZipFile(file_path, 'r') as zip_file:
                # Assume there's one file in the zip
                names = zip_file.namelist()
                if names:
                    with zip_file.open(names[0]) as f:
                        content = f.read().decode('utf-8')
                        logger.debug(f"Successfully read {file_path} as zip file")
                        return content
        except:
            pass
        
        # Try reading as plain text with different encodings
        encodings_to_try = ['utf-8', 'latin-1', 'cp1252', 'iso-8859-1', 'ascii']
        
        for encoding in encodings_to_try:
            try:
                with open(file_path, 'r', encoding=encoding) as f:
                    content = f.read()
                    logger.debug(f"Successfully read {file_path} with {encoding} encoding")
                    return content
            except UnicodeDecodeError:
                continue
            except Exception as e:
                logger.debug(f"Failed to read {file_path} with {encoding}: {e}")
                continue
        
        # If all text encodings fail, try binary mode and convert
        try:
            with open(file_path, 'rb') as f:
                raw_data = f.read()
                # Try to decode as utf-8, replacing errors
                content = raw_data.decode('utf-8', errors='replace')
                logger.warning(f"Read {file_path} in binary mode with error replacement")
                return content
        except Exception as e:
            raise WeatherFileError(f"Could not read file {file_path} with any method: {e}")
        
