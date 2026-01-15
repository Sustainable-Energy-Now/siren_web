"""
SAM Resource Processor Module
Handles System Advisor Model (SAM) integration for wind and solar resource processing
"""

import logging
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass
import math
from pathlib import Path
import re

logger = logging.getLogger(__name__)

# Try to import PySAM-based wrapper first, fall back to original ctypes wrapper
try:
    from siren_web.siren.utilities.ssc_pysam import Entry, Data, Module, API
    logger.info("Using PySAM-based SAM integration")
except ImportError:
    from siren_web.siren.utilities.ssc import Entry, Data, Module, API
    logger.info("Using ctypes-based SAM integration (legacy)")

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

    # Supported file formats for each technology type
    # Format: (file_prefix, file_extension)
    WIND_FORMATS = [
        ('wind_weather', '.srz'),  # Legacy compressed format
        ('wind_weather', '.srw'),  # Legacy uncompressed format
        ('wind', '.csv'),          # New CSV format from ERA5
    ]

    SOLAR_FORMATS = [
        ('solar_weather', '.smz'),  # Legacy compressed format
        ('solar_weather', '.smw'),  # Legacy uncompressed format
        ('solar', '.csv'),          # New CSV format from ERA5
    ]

    def __init__(self, weather_data_dir: Path):
        self.weather_data_dir = Path(weather_data_dir)
        self._file_cache = {}  # Cache for parsed file coordinates

    def get_weather_file_path(self, latitude: float, longitude: float,
                            technology: str, weather_year: str) -> Optional[Path]:
        """
        Find the nearest weather file for given coordinates, technology and year

        Args:
            latitude: Facility latitude
            longitude: Facility longitude
            technology: 'wind' or 'solar'
            weather_year: Year string (e.g. '2024')

        Returns:
            Path to nearest weather file or None if not found
        """
        # Determine weather subdirectory and supported formats
        if technology.lower() in ['onshore wind', 'offshore wind', 'offshore wind floating']:
            weather_subdir = 'wind_weather'
            file_formats = self.WIND_FORMATS
        elif technology.lower() in ['fixed pv', 'single axis pv', 'rooftop pv']:
            weather_subdir = 'solar_weather'
            file_formats = self.SOLAR_FORMATS
        else:
            logger.warning(f"Unknown technology type: {technology}")
            return None

        # Build path to weather files
        weather_dir = self.weather_data_dir / weather_subdir / weather_year

        if not weather_dir.exists():
            logger.warning(f"Weather directory does not exist: {weather_dir}")
            return None

        # Find nearest weather file, trying all supported formats
        nearest_file = self._find_nearest_weather_file(
            weather_dir, latitude, longitude, file_formats, weather_year
        )

        if nearest_file:
            logger.info(f"Found weather file for {technology} at ({latitude}, {longitude}): {nearest_file}")
            return nearest_file
        else:
            logger.warning(f"No weather file found for {technology} at ({latitude}, {longitude}) for year {weather_year}")
            return None

    def _find_nearest_weather_file(self, weather_dir: Path, target_lat: float,
                                 target_lon: float, file_formats: List[Tuple[str, str]],
                                 weather_year: str) -> Optional[Path]:
        """
        Find the weather file with coordinates nearest to target coordinates

        Args:
            weather_dir: Directory containing weather files
            target_lat: Target latitude
            target_lon: Target longitude
            file_formats: List of (file_prefix, file_extension) tuples to search
            weather_year: Year string

        Returns:
            Path to nearest file or None
        """
        # Cache key for this directory
        cache_key = f"{weather_dir}_{weather_year}"

        if cache_key not in self._file_cache:
            # Parse all weather files in directory (all supported formats)
            self._file_cache[cache_key] = self._parse_weather_files(
                weather_dir, file_formats, weather_year
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

    def _parse_weather_files(self, weather_dir: Path, file_formats: List[Tuple[str, str]],
                           weather_year: str) -> Dict[Path, Tuple[float, float]]:
        """
        Parse all weather files in directory and extract coordinates

        Supports multiple file formats:
        - Legacy: solar_weather_-27.7500_114.0000_2024.smz
        - New CSV: solar_-27.7500_114.0000_2024.csv

        Returns:
            Dictionary mapping file paths to (latitude, longitude) tuples
        """
        weather_files = {}

        try:
            for file_path in weather_dir.iterdir():
                if not file_path.is_file():
                    continue

                # Try each supported format
                for file_prefix, file_extension in file_formats:
                    if not file_path.name.endswith(file_extension):
                        continue

                    # Pattern to match: prefix_lat_lon_year.ext
                    pattern = rf"{re.escape(file_prefix)}_(-?\d+\.?\d*)_(-?\d+\.?\d*)_{re.escape(weather_year)}{re.escape(file_extension)}"
                    match = re.match(pattern, file_path.name)

                    if match:
                        try:
                            latitude = float(match.group(1))
                            longitude = float(match.group(2))
                            weather_files[file_path] = (latitude, longitude)
                            break  # Found a match, no need to try other formats
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
        # self.debug_available_modules()
        
    def debug_available_modules(self):
        """
        Debug method to list all available SAM modules
        Call this to see what modules are actually available in your SAM installation
        """
        from siren_web.siren.utilities.ssc import Entry
        
        logger.info("=== Available SAM Modules ===")
        entry = Entry()
        while entry.get():
            name = entry.name()
            description = entry.description()
            version = entry.version()
            if name:
                logger.info(f"Module: {name.decode('utf-8') if isinstance(name, bytes) else name}")
                logger.info(f"  Description: {description.decode('utf-8') if isinstance(description, bytes) else description}")
                logger.info(f"  Version: {version}")
                logger.info("")

    def debug_solar_weather_loading(self, facility_obj, tech_name, weather_year):
        """
        Debug method to see what's happening with solar weather data loading
        """
        logger.info("=== DEBUGGING SOLAR WEATHER LOADING ===")
        
        # Check if we can find a weather file
        weather_file_path = self.get_weather_file_path(
            facility_obj.latitude, 
            facility_obj.longitude, 
            tech_name, 
            weather_year
        )
        
        if weather_file_path:
            logger.info(f"Found weather file: {weather_file_path}")
            logger.info(f"File exists: {weather_file_path.exists()}")
            logger.info(f"File size: {weather_file_path.stat().st_size if weather_file_path.exists() else 'N/A'} bytes")
            
            # Debug the file format
            if weather_file_path.exists():
                self.debug_weather_file_format(weather_file_path, 15)
                
                # Try to load and see what we get
                try:
                    weather_data = self.load_weather_data(weather_file_path)
                    logger.info("=== LOADED WEATHER DATA ===")
                    logger.info(f"GHI points: {len(weather_data.ghi) if weather_data.ghi else 0}")
                    logger.info(f"DNI points: {len(weather_data.dni) if weather_data.dni else 0}")
                    logger.info(f"DHI points: {len(weather_data.dhi) if weather_data.dhi else 0}")
                    logger.info(f"Temperature points: {len(weather_data.temperature) if weather_data.temperature else 0}")
                    logger.info(f"Wind speed points: {len(weather_data.wind_speed) if weather_data.wind_speed else 0}")
                    
                    if weather_data.ghi and len(weather_data.ghi) > 0:
                        logger.info(f"Sample GHI values (first 10): {weather_data.ghi[:10]}")
                        logger.info(f"GHI range: {min(weather_data.ghi):.1f} to {max(weather_data.ghi):.1f}")
                    else:
                        logger.error("NO GHI DATA FOUND!")
                        
                    return weather_data
                    
                except Exception as e:
                    logger.error(f"Failed to load weather data: {e}")
                    return None
        else:
            logger.error("No weather file found!")
            
            # Let's see what files are actually in the directory
            weather_subdir = 'solar_weather'
            weather_dir = self.weather_data_dir / weather_subdir / weather_year
            logger.info(f"Looking in directory: {weather_dir}")
            logger.info(f"Directory exists: {weather_dir.exists()}")
            
            if weather_dir.exists():
                files = list(weather_dir.iterdir())
                logger.info(f"Files in directory: {[f.name for f in files[:10]]}...")  # Show first 10
                logger.info(f"Total files: {len(files)}")
            
            return None
        
    def get_weather_file_path(self, latitude: float, longitude: float, 
                            technology: str, weather_year: str) -> Optional[Path]:
        """
        Find the nearest weather file for given coordinates, technology and year
        
        Args:
            latitude: Facility latitude
            longitude: Facility longitude
            technology: Technology type ('wind' or 'solar') 
            weather_year: Year string (e.g. '2024')
            
        Returns:
            Path to nearest weather file or None if not found
        """
        return self.weather_finder.get_weather_file_path(
            latitude, longitude, technology, weather_year
        )
        
    def get_power_curve_file_path(self, turbine_model: str) -> Path:
        """Generate power curve file path based on turbine model"""
        filename = f"{turbine_model}.pow"
        return self.power_curves_dir / filename
    
    def load_weather_data(self, weather_file_path: Path) -> WeatherData:
        """
        Load weather data from various file formats:
        - .smz/.smw: Legacy solar weather files
        - .srz/.srw: Legacy wind weather files
        - .csv: New SAM CSV format from ERA5
        """
        if not weather_file_path.exists():
            raise WeatherFileError(f"Weather file not found: {weather_file_path}")

        try:
            file_ext = weather_file_path.suffix.lower()

            if file_ext == '.csv':
                # New CSV format from ERA5 conversion
                weather_data = self._parse_sam_csv_file(weather_file_path)
            else:
                # Legacy .smz/.srz/.smw/.srw formats
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
    
    def process_wind_facility(self, facility, weather_year: str,
                            power_curve: Dict[float, float] = None,
                            wind_installation=None) -> SimulationResults:
        """
        Process wind facility using SAM wind power module with file-based approach
        
        Args:
            facility: Facility model instance
            weather_year: Year string for weather data
            power_curve: Optional power curve dictionary
            wind_installation: FacilityWindTurbines instance (optional, for turbine specs)
        """
        temp_weather_file = None
        try:
            logger.info(f"Starting wind simulation for {facility.facility_name}")
            
            # Get weather file and parse data
            weather_file_path = self.get_weather_file_path(
                facility.latitude, facility.longitude,
                facility.idtechnologies.technology_name,
                weather_year
            )
            
            if not weather_file_path or not weather_file_path.exists():
                raise SAMError(f"Weather file not found for {facility.facility_name}")
            
            # Load weather data
            weather_data = self.load_weather_data(weather_file_path)
            
            if not weather_data.wind_speed or len(weather_data.wind_speed) == 0:
                raise SAMError(f"No wind data found for {facility.facility_name}")
            
            # Create temporary SAM-compatible weather file
            temp_weather_file = self._create_sam_weather_file(weather_data, facility, weather_year)
            
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
            
            # REQUIRED: Turbine parameters - use wind_installation if available
            if wind_installation and wind_installation.wind_turbine:
                turbine = wind_installation.wind_turbine
                rotor_diameter = float(turbine.rotor_diameter) if turbine.rotor_diameter else 77.0
                hub_height = float(turbine.hub_height) if turbine.hub_height else 85.0
            else:
                # Fallback to facility attributes (legacy) or defaults
                rotor_diameter = 77.0
                hub_height = float(facility.hub_height) if facility.hub_height else 85.0
            
            data.set_number(b'wind_turbine_rotor_diameter', rotor_diameter)
            data.set_number(b'wind_turbine_hub_ht', hub_height)
            
            # REQUIRED: Power curve
            if power_curve and len(power_curve) > 0:
                wind_speeds = sorted(power_curve.keys())
                power_outputs = [power_curve[ws] for ws in wind_speeds]
                data.set_array(b'wind_turbine_powercurve_windspeeds', wind_speeds)
                data.set_array(b'wind_turbine_powercurve_powerout', power_outputs)
                
                # Get cut-in speed from turbine model if available, otherwise extract from power curve
                cutin_speed = 3.0  # default
                if wind_installation and wind_installation.wind_turbine and wind_installation.wind_turbine.cut_in_speed:
                    cutin_speed = float(wind_installation.wind_turbine.cut_in_speed)
                else:
                    # Extract from power curve (first non-zero power)
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
            
            # REQUIRED: Wind farm layout - get turbine count from wind_installation or facility
            if wind_installation and wind_installation.no_turbines:
                no_turbines = int(wind_installation.no_turbines)
            elif facility.no_turbines and facility.no_turbines > 0:
                # Fallback to facility attribute (legacy)
                no_turbines = int(facility.no_turbines)
            else:
                no_turbines = 1
            
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

    def _create_sam_weather_file(self, weather_data: WeatherData, facility, weather_year: str):
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
                f.write(f"Source,Location,{facility.latitude},{facility.longitude},100,10,1,{weather_year},8760\n")
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

    def _create_wind_resource_table(self, weather_data: WeatherData, facility, weather_year: str):
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
        wind_resource_table.set_number(b'year', int(weather_year))
        
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

    def _set_solar_weather_data(self, data: Data, weather_data: WeatherData, facility):
        """
        Set solar weather data - try multiple formats if needed
        """
        if not weather_data.ghi or len(weather_data.ghi) == 0:
            raise SAMError("No solar irradiance data available")
        
        # Prepare data arrays
        data_length = len(weather_data.ghi)
        expected_length = 8760
        
        def adjust_array(arr, target_length, default_value=0.0):
            if not arr:
                return [default_value] * target_length
            if len(arr) > target_length:
                return arr[:target_length]
            elif len(arr) < target_length:
                pad_value = arr[-1] if arr else default_value
                return arr + [pad_value] * (target_length - len(arr))
            return arr
        
        ghi_data = adjust_array(weather_data.ghi, expected_length, 0.0)
        dni_data = adjust_array(weather_data.dni if weather_data.dni else [], expected_length, 0.0)
        dhi_data = adjust_array(weather_data.dhi if weather_data.dhi else [], expected_length, 0.0)
        temp_data = adjust_array(weather_data.temperature if weather_data.temperature else [], expected_length, 20.0)
        wind_data = adjust_array(weather_data.wind_speed if weather_data.wind_speed else [], expected_length, 3.0)
        
        # Estimate DNI/DHI if not available
        if not any(dni_data):
            dni_data = [max(0, ghi * 0.8) for ghi in ghi_data]
        if not any(dhi_data):
            dhi_data = [max(0, ghi * 0.2) for ghi in ghi_data]
        
        logger.debug("Creating weather file for PVWatts v5")
        
        try:
            # Try the simple SAM CSV format first
            temp_weather_file = self._create_sam_csv_weather_file(
                ghi_data, dni_data, dhi_data, temp_data, wind_data, facility
            )
            
            # Set the weather file path
            data.set_string(b'solar_resource_file', str(temp_weather_file).encode('utf-8'))
            self._temp_solar_file = temp_weather_file
            
            logger.debug(f"Successfully set solar resource file: {temp_weather_file}")
            
        except Exception as e:
            logger.warning(f"CSV format failed: {e}")

    def _create_sam_csv_weather_file(self, ghi_data, dni_data, dhi_data, temp_data, wind_data, facility):
        """
        Create SAM CSV weather file using the EXACT format that SAM expects
        Based on the SAM documentation and forum posts
        """
        import tempfile
        import os
        import datetime
        
        temp_dir = tempfile.gettempdir()
        temp_filename = f"sam_solar_{facility.facility_code}_{os.getpid()}.csv"
        temp_path = Path(temp_dir) / temp_filename
        
        try:
            # Ensure we have exactly 8760 records
            hours_in_year = 8760
            
            with open(temp_path, 'w', newline='') as f:
                # SAM CSV header format (exactly as SAM expects)
                f.write("Source,Location ID,City,State,Country,Latitude,Longitude,Time Zone,Elevation\n")
                f.write(f"SIREN Generated,,{facility.facility_name},,Australia,{facility.latitude},{facility.longitude},8,0\n")
                
                # Data column headers (exact SAM format)
                f.write("Year,Month,Day,Hour,Minute,GHI,DNI,DHI,Tdry,Twet,Wspd,Wdir,Pres\n")
                
                # Write data for a complete year (use 2020 - not a leap year affecting 8760 hours)
                year = 2020  # Non-leap year
                hour = 0
                
                for month in range(1, 13):  # Months 1-12
                    days_in_month = [31, 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31][month-1]
                    
                    for day in range(1, days_in_month + 1):  # Days in month
                        for h in range(24):  # Hours 0-23
                            if hour >= hours_in_year:
                                break
                                
                            # Get data values, ensuring they exist and are valid
                            ghi = 0.0
                            dni = 0.0
                            dhi = 0.0
                            tdry = 20.0
                            wspd = 3.0
                            
                            if hour < len(ghi_data) and ghi_data[hour] is not None:
                                ghi = max(0.0, min(1500.0, float(ghi_data[hour])))
                            if hour < len(dni_data) and dni_data[hour] is not None:
                                dni = max(0.0, min(1200.0, float(dni_data[hour])))
                            if hour < len(dhi_data) and dhi_data[hour] is not None:
                                dhi = max(0.0, min(800.0, float(dhi_data[hour])))
                            if hour < len(temp_data) and temp_data[hour] is not None:
                                tdry = max(-50.0, min(60.0, float(temp_data[hour])))
                            if hour < len(wind_data) and wind_data[hour] is not None:
                                wspd = max(0.0, min(50.0, float(wind_data[hour])))
                            
                            # Calculate wet bulb (simple approximation)
                            twet = tdry - 5.0
                            
                            # Fixed values
                            minute = 0
                            wdir = 180
                            pres = 1013
                            
                            # Write record with simple integer formatting for time, float for data
                            f.write(f"{year},{month},{day},{h},{minute},"
                                f"{ghi:.1f},{dni:.1f},{dhi:.1f},"
                                f"{tdry:.1f},{twet:.1f},{wspd:.1f},"
                                f"{wdir},{pres}\n")
                            
                            hour += 1
                            
                        if hour >= hours_in_year:
                            break
                    if hour >= hours_in_year:
                        break
            
            # Verify we wrote exactly 8760 records
            with open(temp_path, 'r') as f:
                lines = f.readlines()
                data_lines = len(lines) - 3  # Subtract 3 header lines
                
            logger.debug(f"Created SAM CSV file with {data_lines} data records")
            
            if data_lines != 8760:
                logger.error(f"Expected 8760 records, got {data_lines}")
                
            return temp_path
            
        except Exception as e:
            raise WeatherFileError(f"Error creating SAM CSV file: {e}")
   
    def process_solar_facility(self, facility, weather_data: WeatherData) -> SimulationResults:
        """
        Process solar facility using SAM PV module with weather file
        """
        try:
            logger.info(f"Starting solar simulation for {facility.facility_name}")
            
            # Create SAM data container
            data = Data()
            
            # Set weather data using weather file approach
            self._set_solar_weather_data(data, weather_data, facility)
            
            # Set system parameters
            self._set_solar_system_parameters(data, facility)
            
            # Debug: Log some parameter values to confirm they're set
            logger.debug(f"System capacity: {data.get_number(b'system_capacity')} kW")
            logger.debug(f"Array type: {data.get_number(b'array_type')}")
            logger.debug(f"Tilt: {data.get_number(b'tilt')}°")
            logger.debug(f"Azimuth: {data.get_number(b'azimuth')}°")
            
            # Create PVWatts v5 module
            logger.debug("Creating PVWatts v5 module...")
            pv_module = Module(b'pvwattsv5')
            
            if not pv_module.is_ok():
                raise SAMError("Failed to create PVWatts v5 module")
            
            logger.info("Successfully created PVWatts v5 module")
                
            # Execute the module
            logger.debug("Executing solar simulation...")
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
            logger.error(f"Error in solar facility processing: {e}")
            import traceback
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise SAMError(f"Error in solar facility processing: {e}")
            
        finally:
            # Clean up temporary weather file
            if hasattr(self, '_temp_solar_file') and self._temp_solar_file and self._temp_solar_file.exists():
                try:
                    import os
                    os.remove(self._temp_solar_file)
                    logger.debug(f"Cleaned up temporary solar file: {self._temp_solar_file}")
                except:
                    pass
            
    def _parse_smz_file(self, file_path: Path) -> WeatherData:
        """
        Parse .smz solar weather files based on the actual SIREN file format
        
        Format analysis from debug output:
        - Line 0: Header with metadata: 'id,<city>,<state>,8,-29.0,115.0,0,3600.0,2024,0:30:00'
        - Lines 1+: Data: 'temp,?,?,?,wind_speed,wind_dir,pressure,ghi,dni,dhi,?,?,'
        
        Based on the sample data, the columns appear to be:
        0: Temperature (C)
        1: -999 (unknown/unused)
        2: -999 (unknown/unused) 
        3: -999 (unknown/unused)
        4: Wind speed (m/s)
        5: Wind direction (degrees)
        6: Pressure (mbar)
        7: GHI (Global Horizontal Irradiance) W/m2
        8: DNI (Direct Normal Irradiance) W/m2
        9: DHI (Diffuse Horizontal Irradiance) W/m2
        10: -999 (unknown/unused)
        11: -999 (unknown/unused)
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
                
                # Parse wind data (keep existing logic for .srz files)
                for line in lines[5:]:  # Skip headers
                    line = line.strip()
                    if not line:
                        continue
                        
                    try:
                        parts = [part.strip() for part in line.split(',')]
                        if len(parts) >= 6:
                            temperature = float(parts[0])
                            pressure = float(parts[1])
                            wind_direction_10m = float(parts[2])
                            wind_speed_10m = float(parts[3])
                            wind_direction_100m = float(parts[4])
                            wind_speed_100m = float(parts[5])
                            
                            # Use 100m wind data if available
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
                    
            elif file_ext == '.smz':  # Solar file - CORRECT PARSING FOR YOUR FORMAT
                weather_data.ghi = []
                weather_data.dni = []
                weather_data.dhi = []
                weather_data.temperature = []
                weather_data.wind_speed = []
                
                # Skip the first line (header with metadata)
                data_lines = lines[1:]
                
                logger.info(f"Parsing {len(data_lines)} data lines from {file_path}")
                
                for line_num, line in enumerate(data_lines, 1):
                    line = line.strip()
                    if not line:
                        continue
                        
                    try:
                        # Split by comma
                        parts = [part.strip() for part in line.split(',')]
                        
                        # Ensure we have enough columns
                        if len(parts) < 10:
                            logger.debug(f"Line {line_num}: insufficient columns ({len(parts)}), skipping")
                            continue
                        
                        # Parse according to the format you showed:
                        # 0: Temperature, 4: Wind speed, 5: Wind direction, 6: Pressure
                        # 7: GHI, 8: DNI, 9: DHI
                        
                        temperature = float(parts[0]) if parts[0] != '-999' else 20.0
                        wind_speed = float(parts[4]) if parts[4] != '-999' else 3.0
                        wind_direction = float(parts[5]) if parts[5] != '-999' else 180.0
                        pressure = float(parts[6]) if parts[6] != '-999' else 1013.25
                        
                        # Solar irradiance data (most important)
                        ghi = float(parts[7]) if parts[7] != '-999' else 0.0
                        dni = float(parts[8]) if parts[8] != '-999' else 0.0
                        dhi = float(parts[9]) if parts[9] != '-999' else 0.0
                        
                        # Ensure non-negative irradiance values
                        ghi = max(0.0, ghi)
                        dni = max(0.0, dni)
                        dhi = max(0.0, dhi)
                        
                        # Store the data
                        weather_data.temperature.append(temperature)
                        weather_data.wind_speed.append(wind_speed)
                        weather_data.ghi.append(ghi)
                        weather_data.dni.append(dni)
                        weather_data.dhi.append(dhi)
                        
                    except (ValueError, IndexError) as e:
                        logger.debug(f"Line {line_num}: error parsing '{line}' - {e}")
                        continue
                
                # Log parsing results
                total_records = len(weather_data.ghi)
                logger.info(f"Successfully parsed solar weather: {total_records} records from {file_path}")
                
                if total_records > 0:
                    avg_ghi = sum(weather_data.ghi) / total_records
                    max_ghi = max(weather_data.ghi)
                    avg_temp = sum(weather_data.temperature) / total_records
                    
                    logger.info(f"Solar data summary - Avg GHI: {avg_ghi:.1f} W/m2, Max GHI: {max_ghi:.1f} W/m2, Avg Temp: {avg_temp:.1f}°C")
                    
                    # Check for reasonable data ranges
                    if max_ghi > 1500:
                        logger.warning(f"Very high GHI values detected (max: {max_ghi}), check data quality")
                    if avg_ghi < 10:
                        logger.warning(f"Very low average GHI ({avg_ghi}), check data quality")
                else:
                    logger.error("No solar weather records were successfully parsed!")
            
        except Exception as e:
            raise WeatherFileError(f"Error parsing weather file {file_path}: {e}")

        return weather_data

    def _parse_sam_csv_file(self, file_path: Path) -> WeatherData:
        """
        Parse SAM CSV weather files (new format from ERA5 conversion)

        Solar CSV format (3 header rows):
        Row 1: Latitude,Longitude,Time Zone,Elevation
        Row 2: -29.0000,115.0000,8,0
        Row 3: Year,Month,Day,Hour,Minute,GHI,DNI,DHI,Tdry,Tdew,RH,Pres,Wspd,Wdir
        Row 4+: Data rows

        Wind CSV format (2 header rows):
        Row 1: SiteID,Grid_-29.00_115.00,Site Timezone,8,...
        Row 2: Temperature,Pressure,Speed,Direction,Speed,Direction
        Row 3+: Data rows
        """
        weather_data = WeatherData()

        try:
            content = self._read_weather_file(file_path)
            lines = content.strip().split('\n')

            if len(lines) < 4:
                raise WeatherFileError(f"CSV file too short: {len(lines)} lines")

            # Determine if this is a solar or wind file based on filename or header
            file_name = file_path.name.lower()
            is_solar = 'solar' in file_name or lines[2].startswith('Year,')
            is_wind = 'wind' in file_name or lines[1].startswith('Temperature,')

            if is_solar:
                # Parse solar CSV format
                weather_data.ghi = []
                weather_data.dni = []
                weather_data.dhi = []
                weather_data.temperature = []
                weather_data.wind_speed = []
                weather_data.wind_direction = []
                weather_data.pressure = []
                weather_data.humidity = []

                # Data starts at row 4 (index 3)
                data_lines = lines[3:]

                logger.info(f"Parsing {len(data_lines)} solar data lines from {file_path}")

                for line_num, line in enumerate(data_lines, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        parts = [part.strip() for part in line.split(',')]

                        # Expected columns: Year,Month,Day,Hour,Minute,GHI,DNI,DHI,Tdry,Tdew,RH,Pres,Wspd,Wdir
                        if len(parts) < 14:
                            logger.debug(f"Line {line_num}: insufficient columns ({len(parts)})")
                            continue

                        # Parse values (indices: 5=GHI, 6=DNI, 7=DHI, 8=Tdry, 9=Tdew, 10=RH, 11=Pres, 12=Wspd, 13=Wdir)
                        ghi = float(parts[5])
                        dni = float(parts[6])
                        dhi = float(parts[7])
                        temperature = float(parts[8])
                        # tdew = float(parts[9])  # Available if needed
                        humidity = float(parts[10])
                        pressure = float(parts[11])
                        wind_speed = float(parts[12])
                        wind_direction = float(parts[13])

                        # Ensure non-negative irradiance
                        ghi = max(0.0, ghi)
                        dni = max(0.0, dni)
                        dhi = max(0.0, dhi)

                        weather_data.ghi.append(ghi)
                        weather_data.dni.append(dni)
                        weather_data.dhi.append(dhi)
                        weather_data.temperature.append(temperature)
                        weather_data.humidity.append(humidity)
                        weather_data.pressure.append(pressure)
                        weather_data.wind_speed.append(wind_speed)
                        weather_data.wind_direction.append(wind_direction)

                    except (ValueError, IndexError) as e:
                        logger.debug(f"Line {line_num}: error parsing - {e}")
                        continue

                total_records = len(weather_data.ghi)
                logger.info(f"Successfully parsed solar CSV: {total_records} records")

                if total_records > 0:
                    avg_ghi = sum(weather_data.ghi) / total_records
                    max_ghi = max(weather_data.ghi)
                    avg_temp = sum(weather_data.temperature) / total_records
                    logger.info(f"Solar data summary - Avg GHI: {avg_ghi:.1f} W/m2, Max GHI: {max_ghi:.1f} W/m2, Avg Temp: {avg_temp:.1f}°C")

            elif is_wind:
                # Parse wind CSV format
                weather_data.wind_speed = []
                weather_data.wind_direction = []
                weather_data.temperature = []
                weather_data.pressure = []

                # Data starts at row 3 (index 2)
                data_lines = lines[2:]

                logger.info(f"Parsing {len(data_lines)} wind data lines from {file_path}")

                for line_num, line in enumerate(data_lines, 1):
                    line = line.strip()
                    if not line:
                        continue

                    try:
                        parts = [part.strip() for part in line.split(',')]

                        # Expected columns: Temperature,Pressure,Speed,Direction,Speed,Direction
                        # (10m and 100m wind data)
                        if len(parts) < 6:
                            logger.debug(f"Line {line_num}: insufficient columns ({len(parts)})")
                            continue

                        temperature = float(parts[0])
                        pressure = float(parts[1])
                        # wind_speed_10m = float(parts[2])
                        # wind_direction_10m = float(parts[3])
                        wind_speed_100m = float(parts[4])
                        wind_direction_100m = float(parts[5])

                        # Use 100m wind data (closer to turbine hub height)
                        weather_data.temperature.append(temperature)
                        weather_data.pressure.append(pressure)
                        weather_data.wind_speed.append(wind_speed_100m)
                        weather_data.wind_direction.append(wind_direction_100m)

                    except (ValueError, IndexError) as e:
                        logger.debug(f"Line {line_num}: error parsing - {e}")
                        continue

                total_records = len(weather_data.wind_speed)
                logger.info(f"Successfully parsed wind CSV: {total_records} records")

                if total_records > 0:
                    avg_speed = sum(weather_data.wind_speed) / total_records
                    max_speed = max(weather_data.wind_speed)
                    logger.info(f"Wind data summary - Avg Speed: {avg_speed:.1f} m/s, Max Speed: {max_speed:.1f} m/s")

            else:
                raise WeatherFileError(f"Could not determine CSV file type (solar/wind) for {file_path}")

        except Exception as e:
            raise WeatherFileError(f"Error parsing CSV weather file {file_path}: {e}")

        return weather_data

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
    
    def _set_solar_system_parameters(self, data: Data, facility):
        """
        Set solar system parameters for PVWatts v5 with correct parameter names
        """
        try:
            # Required parameters for PVWatts v5
            system_capacity = float(facility.capacity * 1000) if facility.capacity else 1000.0  # Convert MW to kW
            data.set_number(b'system_capacity', system_capacity)
            
            # Module type: 0=Standard, 1=Premium, 2=Thin film
            data.set_number(b'module_type', 0)
            
            # Array type: 0=Fixed open rack, 1=Fixed roof mount, 2=1-axis tracking, 3=1-axis backtracking, 4=2-axis tracking
            array_type = 0  # Default to fixed
            tech_name = facility.idtechnologies.technology_name.lower()
            if 'single axis' in tech_name or 'tracking' in tech_name:
                array_type = 2  # Single axis tracking
            elif 'rooftop' in tech_name:
                array_type = 1  # Roof mount
                
            data.set_number(b'array_type', array_type)
            
            # Tilt angle (degrees from horizontal)
            tilt = float(facility.tilt) if hasattr(facility, 'tilt') and facility.tilt else abs(float(facility.latitude))
            data.set_number(b'tilt', tilt)
            
            # Azimuth angle (degrees from north) - PVWatts v5 uses 'azimuth'
            azimuth = 180.0  # South-facing default
            if hasattr(facility, 'azimuth') and facility.azimuth:
                azimuth = float(facility.azimuth)
            data.set_number(b'azimuth', azimuth)
            
            # System losses (%) - PVWatts v5 uses 'losses'
            losses = 14.0  # Default system losses
            if hasattr(facility, 'losses') and facility.losses:
                losses = float(facility.losses)
            data.set_number(b'losses', losses)
            
            # DC to AC ratio - PVWatts v5 uses 'dc_ac_ratio'
            dc_ac_ratio = 1.2  # Default
            if hasattr(facility, 'dc_ac_ratio') and facility.dc_ac_ratio:
                dc_ac_ratio = float(facility.dc_ac_ratio)
            data.set_number(b'dc_ac_ratio', dc_ac_ratio)
            
            # Inverter efficiency (%) - PVWatts v5 uses 'inv_eff'
            inv_eff = 96.0  # Default
            if hasattr(facility, 'inverter_efficiency') and facility.inverter_efficiency:
                inv_eff = float(facility.inverter_efficiency)
            data.set_number(b'inv_eff', inv_eff)
            
            # Ground coverage ratio (for tracking systems) - PVWatts v5 uses 'gcr'
            if array_type in [2, 3, 4]:  # Tracking systems
                data.set_number(b'gcr', 0.4)  # Ground coverage ratio
                
            # Additional PVWatts v5 parameters
            data.set_number(b'adjust:constant', 0.0)  # No adjustment factors
            
            logger.debug(f"Set solar parameters for PVWatts v5: {system_capacity}kW, tilt={tilt}°, azimuth={azimuth}°, array_type={array_type}")
            
        except Exception as e:
            raise SAMError(f"Error setting solar system parameters: {e}")
    
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
        
