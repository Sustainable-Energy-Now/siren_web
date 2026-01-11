#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.db import models
from django.urls import reverse
from django.core.exceptions import ValidationError
from django.utils import timezone

User = get_user_model()

class Analysis(models.Model):
    idanalysis = models.AutoField(db_column='idAnalysis', primary_key=True)
    idscenarios = models.ForeignKey('Scenarios', on_delete=models.CASCADE, db_column='idScenarios', blank=True, null=True)
    variation = models.CharField(max_length=45, blank=True, null=True) 
    heading = models.CharField(max_length=45, blank=True, null=True)
    component = models.CharField(max_length=45, blank=True, null=True)
    stage = models.IntegerField(null=True)
    quantity = models.FloatField(db_column='Quantity', blank=True, null=True)
    units = models.CharField(db_column='Units', max_length=10, blank=True, null=True)

    class Meta:
        db_table = 'Analysis'

class Scenarios(models.Model):
    idscenarios = models.AutoField(db_column='idScenarios', primary_key=True)  
    title = models.CharField(db_column='Title', unique=True, max_length=45, blank=True, null=True)  
    dateexported = models.DateField(db_column='DateExported', blank=True, null=True)  
    description = models.CharField(db_column='Description', max_length=500, blank=True, null=True)  

    class Meta:
        db_table = 'Scenarios'

class facilities(models.Model):
    """
    Energy facility that can contain multiple technology installations.
    
    RESTRUCTURED: A facility can now have:
    - Multiple wind turbine installations (different models, phases)
    - Multiple solar installations (fixed, tracking, different phases)
    - Multiple storage installations (batteries, PHES)
    
    The facility's total capacity and technology mix is computed from its installations.
    """
    idfacilities = models.AutoField(db_column='idfacilities', primary_key=True)
    facility_name = models.CharField(db_column='facility_name', unique=True, max_length=45, blank=True, null=True)
    facility_code = models.CharField(db_column='facility_code', unique=True, max_length=30, blank=True, null=True)
    participant_code = models.CharField(max_length=45, blank=True, null=True)
    registered_from = models.DateField(null=True)
    active = models.BooleanField(null=False)
    existing = models.BooleanField(null=False)

    # For backward compatibility during migration, keep as nullable
    idtechnologies = models.ForeignKey(
        'Technologies', 
        models.DO_NOTHING, 
        db_column='idtechnologies',
        blank=True, 
        null=True,
        related_name='legacy_facilities',
        help_text="DEPRECATED: Use installation models instead. Kept for migration."
    )
    
    scenarios = models.ManyToManyField('Scenarios', through='ScenariosFacilities', blank=True)
    idzones = models.ForeignKey('Zones', models.DO_NOTHING, db_column='idzones', blank=True, null=True)
    
    # Capacity can be set as override, otherwise computed from installations
    capacity = models.FloatField(
        null=True, 
        blank=True,
        help_text="Override total capacity (MW). If null, computed from installations."
    )
    capacityfactor = models.FloatField(null=True, blank=True)
    
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    
    # Storage hours - legacy field, now use FacilityStorage.duration
    storage_hours = models.FloatField(
        blank=True, 
        null=True,
        help_text="DEPRECATED: Use FacilityStorage installations instead."
    )
    
    power_file = models.CharField(max_length=45, blank=True, null=True)
    direction = models.CharField(max_length=28, blank=True, null=True)
    
    grid_connections = models.ManyToManyField(
        'GridLines', 
        through='FacilityGridConnections',
        blank=True, 
        related_name='connected_facilities'
    )
    primary_grid_line = models.ForeignKey(
        'GridLines', 
        on_delete=models.SET_NULL,
        null=True, 
        blank=True, 
        related_name='primary_facilities'
    )
    wind_turbines = models.ManyToManyField(
        'WindTurbines', 
        through='FacilityWindTurbines',
        blank=True, 
        related_name='connected_turbines'
    )
    emission_intensity = models.FloatField(null=True)

    class Meta:
        db_table = 'facilities'

    def __str__(self):
        return self.facility_name or f"Facility {self.idfacilities}"

    # =========================================================================
    # TECHNOLOGY AGGREGATION METHODS
    # =========================================================================
    
    @property
    def technologies(self):
        """Get all technology types at this facility as a QuerySet"""
        tech_ids = set()
        
        # From wind installations
        for inst in self.facilitywindturbines_set.filter(is_active=True):
            if inst.idtechnologies_id:
                tech_ids.add(inst.idtechnologies_id)
        
        # From solar installations
        for inst in self.solar_installations.filter(is_active=True):
            if inst.idtechnologies_id:
                tech_ids.add(inst.idtechnologies_id)
            
        # From storage installations
        for inst in self.storage_installations.filter(is_active=True):
            if inst.idtechnologies_id:
                tech_ids.add(inst.idtechnologies_id)
        
        # Fallback to legacy field if no installations
        if not tech_ids and self.idtechnologies_id:
            tech_ids.add(self.idtechnologies_id)
            
        return Technologies.objects.filter(idtechnologies__in=tech_ids)
    
    @property
    def technology_categories(self):
        """Get unique technology categories at this facility"""
        categories = set()
        for tech in self.technologies:
            if tech.category:
                categories.add(tech.category)
        return categories
    
    @property
    def primary_technology(self):
        """
        Get the primary/largest capacity technology.
        Returns the Technology object with the highest capacity at this facility.
        """
        tech_capacities = self.get_capacity_by_technology()
        if tech_capacities:
            max_tech = max(tech_capacities, key=tech_capacities.get)
            return max_tech
        # Fallback to legacy
        return self.idtechnologies_legacy
    
    def get_capacity_by_technology(self):
        """
        Returns dict of {Technology: capacity_mw} for all technologies at facility.
        """
        capacities = {}
        
        # Wind capacity by technology
        for inst in self.facilitywindturbines_set.filter(is_active=True):
            tech = inst.idtechnologies
            if tech:
                cap = inst.total_capacity or 0
                capacities[tech] = capacities.get(tech, 0) + cap
        
        # Solar capacity by technology (nameplate DC capacity)
        for inst in self.solar_installations.filter(is_active=True):
            tech = inst.idtechnologies
            if tech:
                cap = inst.nameplate_capacity or 0
                capacities[tech] = capacities.get(tech, 0) + cap
            
        # Storage capacity by technology (power capacity)
        for inst in self.storage_installations.filter(is_active=True):
            tech = inst.idtechnologies
            if tech:
                cap = inst.power_capacity or 0
                capacities[tech] = capacities.get(tech, 0) + cap
            
        return capacities
    
    def get_capacity_by_category(self):
        """
        Returns dict of {category: capacity_mw} aggregated by technology category.
        Example: {'Wind': 150.0, 'Solar': 80.0, 'Storage': 50.0}
        """
        category_capacities = {}
        for tech, cap in self.get_capacity_by_technology().items():
            category = tech.category or 'Unknown'
            category_capacities[category] = category_capacities.get(category, 0) + cap
        return category_capacities
    
    @property
    def total_capacity(self):
        """
        Get total capacity across all technologies.
        Uses override capacity if set, otherwise computes from installations.
        """
        if self.capacity:
            return self.capacity
        computed = sum(self.get_capacity_by_technology().values())
        return computed if computed > 0 else None
    
    # =========================================================================
    # FACILITY TYPE PROPERTIES
    # =========================================================================
    
    @property
    def is_hybrid(self):
        """Check if facility has multiple technology categories (e.g., Wind + Solar)"""
        return len(self.technology_categories) > 1
    
    @property
    def is_wind_farm(self):
        """Check if this facility has active wind turbine installations"""
        return self.facilitywindturbines_set.filter(is_active=True).exists()
    
    @property
    def is_solar_farm(self):
        """Check if this facility has active solar installations"""
        return self.solar_installations.filter(is_active=True).exists()
    
    @property
    def has_storage(self):
        """Check if this facility has active storage installations"""
        return self.storage_installations.filter(is_active=True).exists()
    
    @property
    def is_generator(self):
        """Check if facility has conventional generation (gas, coal, etc.)"""
        for tech in self.technologies:
            if tech.category in ('Generator', 'Thermal', 'Gas', 'Coal'):
                return True
        return False
    
    @property
    def is_renewable(self):
        """Check if all technologies at facility are renewable"""
        technologies = list(self.technologies)
        if not technologies:
            return False
        return all(tech.renewable for tech in technologies)
    
    # =========================================================================
    # WIND-SPECIFIC METHODS
    # =========================================================================
    
    def get_total_wind_capacity(self):
        """Calculate total wind capacity for this facility in MW"""
        total = 0
        for installation in self.facilitywindturbines_set.filter(is_active=True):
            if installation.total_capacity:
                total += installation.total_capacity
        return total
    
    def get_wind_turbine_summary(self):
        """Get summary of wind turbines at this facility"""
        installations = self.facilitywindturbines_set.filter(is_active=True)
        summary = []
        for installation in installations:
            summary.append({
                'technology': str(installation.idtechnologies) if installation.idtechnologies else None,
                'model': installation.wind_turbine.turbine_model,
                'manufacturer': installation.wind_turbine.manufacturer,
                'count': installation.no_turbines,
                'capacity_mw': installation.total_capacity,
                'hub_height': installation.hub_height,
                'installation_name': installation.installation_name,
                'commissioned': installation.commissioning_date,
            })
        return summary
    
    # =========================================================================
    # SOLAR-SPECIFIC METHODS
    # =========================================================================
    
    def get_total_solar_capacity(self):
        """Calculate total solar DC capacity for this facility in MW"""
        total = 0
        for installation in self.solar_installations.filter(is_active=True):
            if installation.nameplate_capacity:
                total += installation.nameplate_capacity
        return total
    
    def get_solar_installation_summary(self):
        """Get summary of solar installations at this facility"""
        installations = self.solar_installations.filter(is_active=True)
        summary = []
        for installation in installations:
            summary.append({
                'technology': str(installation.idtechnologies),
                'name': installation.installation_name,
                'capacity_dc_mw': installation.nameplate_capacity,
                'capacity_ac_mw': installation.ac_capacity,
                'tracking': installation.idtechnologies.solar_attributes.first().tracking_type if installation.idtechnologies.solar_attributes.exists() else None,
                'commissioned': installation.commissioning_date,
            })
        return summary
    
    # =========================================================================
    # STORAGE-SPECIFIC METHODS
    # =========================================================================
    
    def get_total_storage_power(self):
        """Calculate total storage power capacity for this facility in MW"""
        total = 0
        for installation in self.storage_installations.filter(is_active=True):
            if installation.power_capacity:
                total += installation.power_capacity
        return total
    
    def get_total_storage_energy(self):
        """Calculate total storage energy capacity for this facility in MWh"""
        total = 0
        for installation in self.storage_installations.filter(is_active=True):
            if installation.energy_capacity:
                total += installation.energy_capacity
        return total
    
    def get_storage_installation_summary(self):
        """Get summary of storage installations at this facility"""
        installations = self.storage_installations.filter(is_active=True)
        summary = []
        for installation in installations:
            summary.append({
                'technology': str(installation.idtechnologies),
                'name': installation.installation_name,
                'power_mw': installation.power_capacity,
                'energy_mwh': installation.energy_capacity,
                'duration_hours': installation.get_calculated_duration(),
                'commissioned': installation.commissioning_date,
            })
        return summary
    
    # =========================================================================
    # COMPREHENSIVE SUMMARY METHODS
    # =========================================================================
    
    def get_installation_summary(self):
        """Get a complete summary of all installations at this facility"""
        return {
            'wind': self.get_wind_turbine_summary(),
            'solar': self.get_solar_installation_summary(),
            'storage': self.get_storage_installation_summary(),
            'total_capacity_mw': self.total_capacity,
            'is_hybrid': self.is_hybrid,
            'categories': list(self.technology_categories),
        }
    
    def get_capacity_summary_string(self):
        """Get a formatted string summarizing facility capacity"""
        parts = []
        categories = self.get_capacity_by_category()
        
        if 'Wind' in categories:
            parts.append(f"{categories['Wind']:.1f} MW Wind")
        if 'Solar' in categories:
            parts.append(f"{categories['Solar']:.1f} MW Solar")
        if 'Storage' in categories:
            storage_energy = self.get_total_storage_energy()
            parts.append(f"{categories['Storage']:.1f} MW / {storage_energy:.1f} MWh Storage")
        
        if not parts:
            return f"{self.total_capacity or 0:.1f} MW"
        
        return " + ".join(parts)
    
    # =========================================================================
    # GRID CONNECTION METHODS
    # =========================================================================
    
    def get_primary_grid_connection(self):
        """Get the primary grid connection for this facility"""
        try:
            return self.facilitygridconnections_set.filter(is_primary=True).first()
        except:
            return None
    
    def get_all_grid_connections(self):
        """Get all grid connections for this facility"""
        return self.facilitygridconnections_set.filter(active=True)
    
    def calculate_total_grid_losses_mw(self, power_output_mw):
        """Calculate total losses from facility through all grid connections"""
        total_losses = 0
        connections = self.get_all_grid_connections()
        
        if connections:
            power_per_connection = power_output_mw / len(connections)
            
            for connection in connections:
                connection_losses = connection.calculate_connection_losses_mw(power_per_connection)
                grid_line_losses = connection.idgridlines.calculate_line_losses_mw(power_per_connection)
                total_losses += connection_losses + grid_line_losses
        
        return total_losses

class Generatorattributes(models.Model):
    """Technology-level attributes for conventional generators"""
    idgeneratorattributes = models.AutoField(db_column='idGeneratorAttributes', primary_key=True)
    idtechnologies = models.ForeignKey('Technologies', models.CASCADE, db_column='idTechnologies')
    capacity_max = models.FloatField(null=True)
    capacity_min = models.FloatField(null=True)
    rampdown_max = models.IntegerField(blank=True, null=True)
    rampup_max = models.IntegerField(blank=True, null=True)

    class Meta:
        db_table = 'GeneratorAttributes'

class Genetics(models.Model):
    idgenetics = models.AutoField(db_column='idGenetics', primary_key=True)  
    parameter = models.CharField(db_column='Parameter', max_length=30, blank=True, null=True)  
    weight = models.FloatField(db_column='Weight', null=True)  
    better = models.FloatField(db_column='Better', null=True)  
    worse = models.FloatField(db_column='Worse', null=True)  
    minvalue = models.FloatField(db_column='MinValue', null=True)  
    maxvalue = models.FloatField(db_column='MaxValue', null=True)  
    step = models.FloatField(db_column='Step', null=True)  
    betterspinner = models.IntegerField(db_column='BetterSpinner', blank=True, null=True)  
    worsespinner = models.IntegerField(db_column='WorseSpinner', blank=True, null=True)  

    class Meta:
        db_table = 'Genetics'
        db_table_comment = 'Parameters used for genetic optimisation'

class GridLines(models.Model):
    """Model to store grid line data for calculating losses and capacity"""
    idgridlines = models.AutoField(primary_key=True, db_column='idgridlines')
    line_name = models.CharField(max_length=100, unique=True, help_text="Unique identifier for the grid line")
    line_code = models.CharField(max_length=30, unique=True, help_text="Short code for the grid line")
    line_type = models.CharField(max_length=20, choices=[
        ('transmission', 'Transmission'),
        ('distribution', 'Distribution'),
        ('subtransmission', 'Sub-transmission')
    ], default='transmission')
    voltage_level = models.FloatField(help_text="Voltage level in kV")
    
    # Physical characteristics for loss calculations
    length_km = models.FloatField(help_text="Line length in kilometers")
    resistance_per_km = models.FloatField(help_text="Resistance per km (ohms/km)")
    reactance_per_km = models.FloatField(help_text="Reactance per km (ohms/km)")
    conductance_per_km = models.FloatField(default=0, help_text="Conductance per km (S/km)")
    susceptance_per_km = models.FloatField(default=0, help_text="Susceptance per km (S/km)")
    
    # Capacity constraints
    thermal_capacity_mw = models.FloatField(help_text="Thermal capacity in MW")
    emergency_capacity_mw = models.FloatField(null=True, blank=True, help_text="Emergency capacity in MW")
    
    # Geographic endpoints
    from_latitude = models.FloatField(help_text="Starting point latitude")
    from_longitude = models.FloatField(help_text="Starting point longitude")
    to_latitude = models.FloatField(help_text="Ending point latitude")
    to_longitude = models.FloatField(help_text="Ending point longitude")
    from_terminal = models.ForeignKey('Terminals', on_delete=models.SET_NULL, 
                                null=True, blank=True, related_name='outgoing_lines',
                                help_text="Terminal where this line originates")
    to_terminal = models.ForeignKey('Terminals', on_delete=models.SET_NULL, 
                              null=True, blank=True, related_name='incoming_lines',
                              help_text="Terminal where this line terminates")
    
    # Additional attributes
    active = models.BooleanField(default=True)
    commissioned_date = models.DateField(null=True, blank=True)
    decommissioned_date = models.DateField(null=True, blank=True)
    owner = models.CharField(max_length=100, blank=True, null=True)
    
    # Text field to store KML geometry data as string
    kml_geometry = models.TextField(null=True, blank=True, help_text="KML geometry data (stored as text)")
    
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
    ga_guid = models.CharField(max_length=40, unique=True, null=True, help_text="Unique identifier")
    is_aboveground = models.BooleanField(default=True)
    
    
    class Meta:
        db_table = 'GridLines'
        ordering = ['line_name']
    
    def __str__(self):
        return f"{self.line_name} ({self.voltage_level}kV)"
    
    def get_from_point(self):
        """Get starting point, preferring terminal location over lat/lng"""
        if self.from_terminal:
            return [self.from_terminal.latitude, self.from_terminal.longitude]
        return [self.from_latitude, self.from_longitude]

    def get_to_point(self):
        """Get ending point, preferring terminal location over lat/lng"""
        if self.to_terminal:
            return [self.to_terminal.latitude, self.to_terminal.longitude]
        return [self.to_latitude, self.to_longitude]

    def get_enhanced_line_coordinates(self):
        """Get line coordinates with terminal awareness"""
        # If we have detailed KML coordinates, use those
        kml_data = self.get_kml_geometry_data()
        if kml_data and 'coordinates' in kml_data:
            return [[coord[1], coord[0]] for coord in kml_data['coordinates']]
        
        # Otherwise, use terminal locations if available, fall back to lat/lng
        from_point = self.get_from_point()
        to_point = self.get_to_point()
        return [from_point, to_point]

    def calculate_resistance(self):
        """Calculate total resistance of the line"""
        return self.resistance_per_km * self.length_km
    
    def calculate_reactance(self):
        """Calculate total reactance of the line"""
        return self.reactance_per_km * self.length_km
    
    def calculate_impedance(self):
        """Calculate impedance magnitude"""
        r = self.calculate_resistance()
        x = self.calculate_reactance()
        return (r**2 + x**2)**0.5
    
    def calculate_line_losses_mw(self, power_flow_mw):
        """Calculate line losses for a given power flow"""
        if power_flow_mw == 0:
            return 0
        
        # Simplified loss calculation: P_loss = I²R = (P²R)/(V²cos²φ)
        # Assuming power factor of 0.95 and using line-to-line voltage
        voltage_kv = self.voltage_level
        resistance = self.calculate_resistance()
        power_factor = 0.95
        
        # Convert to per-unit system for calculation
        current_pu = power_flow_mw / (voltage_kv * (3**0.5) * power_factor)
        losses_mw = (current_pu**2) * resistance * (voltage_kv**2) / 1000  # Convert to MW
        
        return losses_mw
    
    def get_utilization_percent(self, current_flow_mw):
        """Get current utilization as percentage of thermal capacity"""
        if self.thermal_capacity_mw == 0:
            return 0
        return (abs(current_flow_mw) / self.thermal_capacity_mw) * 100
    
    def set_kml_geometry_data(self, geometry_dict):
        """Store geometry data as JSON string in the kml_geometry TextField"""
        import json
        if geometry_dict:
            self.kml_geometry = json.dumps(geometry_dict, separators=(',', ':'))
        else:
            self.kml_geometry = None
    
    def get_kml_geometry_data(self):
        """Retrieve geometry data as Python dict from kml_geometry TextField"""
        import json
        if self.kml_geometry:
            try:
                return json.loads(self.kml_geometry)
            except (json.JSONDecodeError, TypeError):
                return None
        return None
    
    def has_kml_geometry(self):
        """Check if this grid line has KML geometry data"""
        return bool(self.kml_geometry)
    
    def get_kml_coordinates_count(self):
        """Get the number of coordinate points in the KML geometry"""
        kml_data = self.get_kml_geometry_data()
        if kml_data and 'coordinates' in kml_data:
            return len(kml_data['coordinates'])
        return 0
    
    def validate_kml_geometry(self):
        """Validate the KML geometry data structure"""
        kml_data = self.get_kml_geometry_data()
        if not kml_data:
            return True, "No KML geometry data"
        
        # Check required fields
        if 'type' not in kml_data:
            return False, "Missing 'type' field in KML geometry"
        
        if 'coordinates' not in kml_data:
            return False, "Missing 'coordinates' field in KML geometry"
        
        coordinates = kml_data['coordinates']
        if not isinstance(coordinates, list) or len(coordinates) < 2:
            return False, "Invalid coordinates: must be a list with at least 2 points"
        
        # Validate coordinate format
        for i, coord in enumerate(coordinates):
            if not isinstance(coord, list) or len(coord) < 2:
                return False, f"Invalid coordinate at index {i}: must be [lon, lat] or [lon, lat, alt]"
            
            try:
                lon, lat = float(coord[0]), float(coord[1])
                if not (-180 <= lon <= 180) or not (-90 <= lat <= 90):
                    return False, f"Invalid coordinate at index {i}: longitude/latitude out of range"
            except (ValueError, TypeError):
                return False, f"Invalid coordinate at index {i}: non-numeric values"
        
        return True, "Valid KML geometry"

    def get_line_coordinates(self):
        """Get all coordinates for the line (for detailed rendering)"""
        kml_data = self.get_kml_geometry_data()
        if kml_data and 'coordinates' in kml_data:
            # Return as [lat, lng] pairs for Leaflet
            return [[coord[1], coord[0]] for coord in kml_data['coordinates']]
        else:
            # Fallback to simple from/to coordinates
            return [
                [self.from_latitude, self.from_longitude],
                [self.to_latitude, self.to_longitude]
            ]
    
    def get_line_style(self):
        """Get styling information for map rendering"""
        # Color based on voltage level
        if self.voltage_level >= 330:
            color = '#8B0000'  # Dark red for high voltage
        elif self.voltage_level >= 220:
            color = '#FF4500'  # Orange red
        elif self.voltage_level >= 132:
            color = '#FFA500'  # Orange
        elif self.voltage_level >= 66:
            color = '#FFD700'  # Gold
        else:
            color = '#FFFF00'  # Yellow for lower voltage
        
        # Line weight based on voltage
        weight = max(2, min(8, self.voltage_level / 50))
        
        return {
            'color': color,
            'weight': weight,
            'opacity': 0.8 if self.active else 0.4,
            'dashArray': None if self.active else '5, 5'
        }
    
    def get_popup_content(self):
        """Get HTML content for map popup"""
        status = "Active" if self.active else "Inactive"
        emergency_cap = f" / {self.emergency_capacity_mw} MW (Emergency)" if self.emergency_capacity_mw else ""
        
        return f"""
        <div class="grid-line-popup">
            <h4>{self.line_name}</h4>
            <table style="font-size: 12px;">
                <tr><td><strong>Code:</strong></td><td>{self.line_code}</td></tr>
                <tr><td><strong>Type:</strong></td><td>{self.line_type.title()}</td></tr>
                <tr><td><strong>Voltage:</strong></td><td>{self.voltage_level} kV</td></tr>
                <tr><td><strong>Length:</strong></td><td>{self.length_km} km</td></tr>
                <tr><td><strong>Capacity:</strong></td><td>{self.thermal_capacity_mw}{emergency_cap} MW</td></tr>
                <tr><td><strong>Status:</strong></td><td>{status}</td></tr>
                {f'<tr><td><strong>Owner:</strong></td><td>{self.owner}</td></tr>' if self.owner else ''}
            </table>
        </div>
        """
    
    def export_to_kml(self):
        """Export this grid line back to KML format"""
        coordinates = self.get_line_coordinates()
        # Convert back to KML coordinate format (lon,lat,alt)
        kml_coords = []
        for coord in coordinates:
            kml_coords.append(f"{coord[1]},{coord[0]},0")
        
        kml_content = f"""
        <Placemark>
            <name>{self.line_name}</name>
            <description>
                <![CDATA[
                Line Code: {self.line_code}<br/>
                Type: {self.line_type}<br/>
                Voltage: {self.voltage_level} kV<br/>
                Capacity: {self.thermal_capacity_mw} MW<br/>
                Length: {self.length_km} km<br/>
                Owner: {self.owner or 'Unknown'}
                ]]>
            </description>
            <LineString>
                <coordinates>
                    {' '.join(kml_coords)}
                </coordinates>
            </LineString>
        </Placemark>
        """
        return kml_content.strip()
    
    @classmethod
    def export_all_to_kml(cls, filename=None):
        """Export all active grid lines to a KML file"""
        if not filename:
            from django.conf import settings
            import os
            filename = os.path.join(settings.STATIC_ROOT or 'static', 'kml', 'Generated_GridLines.kml')
        
        kml_header = '''<?xml version="1.0" encoding="UTF-8"?>
<kml xmlns="http://www.opengis.net/kml/2.2">
  <Document>
    <name>Grid Lines</name>
    <description>Generated from GridLines database</description>
'''
        
        kml_footer = '''  </Document>
</kml>'''
        
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(kml_header)
            
            for grid_line in cls.objects.filter(active=True):
                f.write(grid_line.export_to_kml())
                f.write('\n')
            
            f.write(kml_footer)
        
        return filename

class FacilityGridConnections(models.Model):
    """Junction table to connect facilities to grid lines"""
    idfacilitygridconnections = models.AutoField(primary_key=True)
    idfacilities = models.ForeignKey('facilities', on_delete=models.CASCADE, db_column='idfacilities')
    idgridlines = models.ForeignKey('GridLines', on_delete=models.CASCADE, db_column='idgridlines')
    
    # Connection details
    connection_type = models.CharField(max_length=20, choices=[
        ('direct', 'Direct Connection'),
        ('substation', 'Via Substation'),
        ('transformer', 'Via Transformer')
    ], default='direct')
    
    connection_point_latitude = models.FloatField(help_text="Exact connection point latitude")
    connection_point_longitude = models.FloatField(help_text="Exact connection point longitude")
    
    # Technical connection data
    connection_voltage_kv = models.FloatField(help_text="Connection voltage in kV")
    transformer_capacity_mva = models.FloatField(null=True, blank=True, help_text="Transformer capacity if applicable")
    connection_capacity_mw = models.FloatField(help_text="Maximum connection capacity in MW")
    
    # Distance from facility to grid line
    connection_distance_km = models.FloatField(help_text="Distance from facility to grid connection point")
    
    # Administrative
    connection_date = models.DateField(null=True, blank=True)
    is_primary = models.BooleanField(default=True, help_text="Is this the primary grid connection for the facility?")
    active = models.BooleanField(default=True)
    
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'FacilityGridConnections'
        unique_together = [['idfacilities', 'idgridlines', 'is_primary']]  # Only one primary connection per facility-gridline pair
    
    def __str__(self):
        return f"{self.idfacilities.facility_name} -> {self.idgridlines.line_name}"
    
    def calculate_connection_losses_mw(self, power_output_mw):
        """Calculate losses from facility to grid connection point"""
        if self.connection_distance_km == 0 or power_output_mw == 0:
            return 0
        
        # Simplified calculation for connection losses
        # Assuming typical conductor characteristics for connection lines
        typical_resistance_per_km = 0.1  # ohms/km for typical HV connection
        connection_resistance = typical_resistance_per_km * self.connection_distance_km
        
        # Use connection voltage for loss calculation
        voltage_kv = self.connection_voltage_kv
        power_factor = 0.95
        
        current = power_output_mw / (voltage_kv * (3**0.5) * power_factor)
        connection_losses_mw = (current**2) * connection_resistance * (voltage_kv**2) / 1000
        
        return connection_losses_mw

class FacilitySolar(models.Model):
    """
    Installation-specific solar PV system data.
    Links facilities to solar technologies with deployment details.
    
    A facility can have multiple solar installations with different:
    - Technology types (fixed tilt, single-axis tracking, etc.)
    - Commissioning dates (Phase 1, Phase 2)
    - Array configurations
    """
    idfacilitysolar = models.AutoField(db_column='idfacilitysolar', primary_key=True)
    idfacilities = models.ForeignKey(
        'facilities',
        on_delete=models.CASCADE,
        db_column='idfacilities',
        related_name='solar_installations'
    )
    idtechnologies = models.ForeignKey(
        'Technologies',
        on_delete=models.CASCADE,
        db_column='idtechnologies',
        related_name='solar_facility_installations',
        limit_choices_to={'category': 'Solar'}
    )
    
    # INSTALLATION-SPECIFIC CAPACITY
    nameplate_capacity = models.FloatField(
        null=True,
        blank=True,
        help_text='MW - DC nameplate capacity'
    )
    ac_capacity = models.FloatField(
        null=True,
        blank=True,
        help_text='MW - AC capacity (inverter rating)'
    )
    
    # PANEL ARRAY SPECIFICATIONS
    panel_count = models.IntegerField(
        null=True,
        blank=True,
        help_text='Total number of solar panels'
    )
    panel_wattage = models.FloatField(
        null=True,
        blank=True,
        help_text='Watts - Individual panel rating'
    )
    
    # INSTALLATION GEOMETRY
    tilt_angle = models.FloatField(
        null=True,
        blank=True,
        help_text='Degrees - Panel tilt angle from horizontal'
    )
    azimuth_angle = models.FloatField(
        null=True,
        blank=True,
        help_text='Degrees - Panel azimuth (0=North, 90=East, 180=South, 270=West)'
    )
    array_area = models.FloatField(
        null=True,
        blank=True,
        help_text='Square meters - Total panel array area'
    )
    
    # INSTALLATION METADATA
    installation_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text='Name for this solar installation (e.g., "East Array", "Phase 2")'
    )
    installation_date = models.DateField(
        blank=True,
        null=True,
        help_text='Date when solar system was installed'
    )
    commissioning_date = models.DateField(
        blank=True,
        null=True,
        help_text='Date when solar system began operations'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this solar installation is currently active'
    )

    # OPERATIONAL SETTINGS
    inverter_count = models.IntegerField(
        null=True,
        blank=True,
        help_text='Number of inverters'
    )
    inverter_capacity_each = models.FloatField(
        null=True,
        blank=True,
        help_text='kW - Capacity of each inverter'
    )

    # NOTES AND TRACKING
    notes = models.TextField(
        blank=True,
        null=True,
        help_text='Additional notes about this solar installation'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'FacilitySolar'
        verbose_name = 'Facility Solar Installation'
        verbose_name_plural = 'Facility Solar Installations'
        unique_together = [['idfacilities', 'idtechnologies', 'installation_name']]
        ordering = ['idfacilities', 'idtechnologies']

    def __str__(self):
        name = self.installation_name or "Solar"
        return f"{self.facility.facility_name} - {self.technology.technology_name} ({name})"
    
    @property
    def technology(self):
        """Get the solar technology for this installation"""
        return self.idtechnologies

    @property
    def facility(self):
        """Get the facility for this installation"""
        return self.idfacilities
    
    @property
    def solar_attrs(self):
        """Get the technology-level solar attributes"""
        return self.technology.solar_attributes.first()
    
    def get_calculated_dc_ac_ratio(self):
        """Calculate DC/AC ratio from nameplate and AC capacity"""
        if self.nameplate_capacity and self.ac_capacity and self.ac_capacity > 0:
            return self.nameplate_capacity / self.ac_capacity
        return None
    
    def get_panel_efficiency(self):
        """Get panel efficiency from solar attributes"""
        solar_attrs = self.solar_attrs
        if solar_attrs:
            return solar_attrs.module_efficiency
        return None
    
    def get_performance_ratio(self):
        """Get performance ratio from solar attributes"""
        solar_attrs = self.solar_attrs
        if solar_attrs:
            return solar_attrs.performance_ratio
        return None
    
    def get_calculated_panel_count(self):
        """Calculate panel count from capacity and panel wattage"""
        if self.nameplate_capacity and self.panel_wattage and self.panel_wattage > 0:
            # nameplate_capacity is in MW, panel_wattage is in W
            return int((self.nameplate_capacity * 1_000_000) / self.panel_wattage)
        return self.panel_count
    
    def get_calculated_array_area(self):
        """Estimate array area based on capacity and efficiency"""
        solar_attrs = self.solar_attrs
        if self.nameplate_capacity and solar_attrs and solar_attrs.module_efficiency:
            # Assuming ~1000 W/m² solar irradiance
            area_m2 = (self.nameplate_capacity * 1_000_000) / (1000 * solar_attrs.module_efficiency)
            return area_m2
        return self.array_area
    
    @property
    def capacity_summary(self):
        """Return a formatted string summarizing the capacity"""
        if self.nameplate_capacity and self.ac_capacity:
            dc_ac = self.get_calculated_dc_ac_ratio()
            return f"{self.nameplate_capacity:.1f} MW DC / {self.ac_capacity:.1f} MW AC (ratio: {dc_ac:.2f})"
        elif self.nameplate_capacity:
            return f"{self.nameplate_capacity:.1f} MW DC"
        elif self.ac_capacity:
            return f"{self.ac_capacity:.1f} MW AC"
        return "Not specified"
    
    def validate_capacity(self):
        """Validate that capacity values are logical"""
        if self.nameplate_capacity and self.nameplate_capacity <= 0:
            raise ValueError("Nameplate capacity must be positive")
        if self.ac_capacity and self.ac_capacity <= 0:
            raise ValueError("AC capacity must be positive")
        
        # DC capacity should typically be higher than AC capacity
        if self.nameplate_capacity and self.ac_capacity:
            if self.ac_capacity > self.nameplate_capacity:
                raise ValueError("AC capacity should not exceed DC nameplate capacity")
        
        return True
    
    def save(self, *args, **kwargs):
        """Override save to calculate derived values"""
        # Auto-calculate panel count if not provided
        if not self.panel_count and self.nameplate_capacity and self.panel_wattage:
            self.panel_count = self.get_calculated_panel_count()
        
        super().save(*args, **kwargs)


class FacilityStorage(models.Model):
    """
    Through model for many-to-many relationship between facilities and Storage Technologies.
    Contains installation-specific data for storage systems at each facility.
    
    A facility can have multiple storage installations with different:
    - Technology types (Battery, PHES, Flow Battery)
    - Durations (1hr, 4hr, 24hr)
    - Commissioning dates
    """
    idfacilitystorage = models.AutoField(db_column='idfacilitystorage', primary_key=True)
    idfacilities = models.ForeignKey(
        'facilities', 
        on_delete=models.CASCADE, 
        db_column='idfacilities',
        related_name='storage_installations'
    )
    idtechnologies = models.ForeignKey(
        'Technologies', 
        on_delete=models.CASCADE, 
        db_column='idtechnologies',
        related_name='facility_installations',
        limit_choices_to={'category': 'Storage'}
    )
    
    # INSTALLATION-SPECIFIC CAPACITY
    power_capacity = models.FloatField(
        null=True, 
        blank=True,
        help_text='MW - max charge/discharge rate at this facility'
    )
    energy_capacity = models.FloatField(
        null=True, 
        blank=True,
        help_text='MWh - total storage capacity at this facility'
    )
    duration = models.FloatField(
        null=True, 
        blank=True,
        help_text='Hours at rated power for this installation'
    )
    
    # INSTALLATION METADATA
    installation_name = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text='Name for this storage installation (e.g., "Main Battery Bank", "Phase 2")'
    )
    installation_date = models.DateField(
        blank=True, 
        null=True,
        help_text='Date when this storage system was installed'
    )
    commissioning_date = models.DateField(
        blank=True, 
        null=True,
        help_text='Date when storage system began operations'
    )
    is_active = models.BooleanField(
        default=True,
        help_text='Whether this storage installation is currently active'
    )
    
    # OPERATIONAL SETTINGS (can override technology defaults)
    initial_state_of_charge = models.FloatField(
        blank=True, 
        null=True,
        help_text='Initial SOC for this installation (0.0 to 1.0), overrides technology default if set'
    )
    
    # NOTES AND TRACKING
    notes = models.TextField(
        blank=True, 
        null=True,
        help_text='Additional notes about this storage installation'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'FacilityStorage'
        verbose_name = 'Facility Storage Installation'
        verbose_name_plural = 'Facility Storage Installations'
        unique_together = [['idfacilities', 'idtechnologies', 'installation_name']]
        ordering = ['idfacilities', 'idtechnologies']

    def __str__(self):
        name = self.installation_name or "Storage"
        return f"{self.facility.facility_name} - {self.technology.technology_name} ({name})"
    
    @property
    def technology(self):
        """Get the storage technology for this installation"""
        return self.idtechnologies

    @property
    def facility(self):
        """Get the facility for this installation"""
        return self.idfacilities
    
    @property
    def storage_attrs(self):
        """Get the technology-level storage attributes"""
        return self.technology.storageattributes_set.first()
    
    def get_calculated_duration(self):
        """Calculate duration from energy and power capacity"""
        if self.energy_capacity and self.power_capacity and self.power_capacity > 0:
            return self.energy_capacity / self.power_capacity
        return self.duration
    
    def get_usable_capacity(self):
        """Calculate usable energy capacity based on technology SOC constraints"""
        storage_attrs = self.storage_attrs
        if self.energy_capacity and storage_attrs:
            min_soc = storage_attrs.min_state_of_charge or 0.0
            max_soc = storage_attrs.max_state_of_charge or 1.0
            return self.energy_capacity * (max_soc - min_soc)
        return None
    
    def get_round_trip_efficiency(self):
        """Get round-trip efficiency from technology attributes"""
        storage_attrs = self.storage_attrs
        if storage_attrs:
            return storage_attrs.round_trip_efficiency
        return None
    
    def get_cycle_life(self):
        """Get cycle life from technology attributes"""
        storage_attrs = self.storage_attrs
        if storage_attrs:
            return storage_attrs.cycle_life
        return None
    
    @property
    def capacity_summary(self):
        """Return a formatted string summarizing the capacity"""
        if self.power_capacity and self.energy_capacity:
            duration = self.get_calculated_duration()
            return f"{self.power_capacity:.1f} MW / {self.energy_capacity:.1f} MWh ({duration:.1f}h)"
        elif self.power_capacity:
            return f"{self.power_capacity:.1f} MW"
        elif self.energy_capacity:
            return f"{self.energy_capacity:.1f} MWh"
        return "Not specified"
    
    def validate_capacity(self):
        """Validate that capacity values are logical"""
        if self.power_capacity and self.power_capacity <= 0:
            raise ValueError("Power capacity must be positive")
        if self.energy_capacity and self.energy_capacity <= 0:
            raise ValueError("Energy capacity must be positive")
        if self.duration and self.duration <= 0:
            raise ValueError("Duration must be positive")
        
        # Check consistency
        if self.power_capacity and self.energy_capacity and self.duration:
            calculated_duration = self.energy_capacity / self.power_capacity
            if abs(calculated_duration - self.duration) > 0.1:
                raise ValueError(
                    f"Duration ({self.duration}h) doesn't match calculated "
                    f"duration ({calculated_duration:.2f}h) from energy/power"
                )
        
        return True
    
    def save(self, *args, **kwargs):
        """Override save to validate before saving"""
        # Auto-calculate duration if not provided but power and energy are
        if not self.duration and self.power_capacity and self.energy_capacity:
            self.duration = self.energy_capacity / self.power_capacity
        
        super().save(*args, **kwargs)


class WindTurbines(models.Model):
    """
    Wind turbine model specifications.
    Contains technical data for turbine types that can be installed at facilities.
    """
    APPLICATION_CHOICES = [
        ('onshore', 'Onshore'),
        ('offshore', 'Offshore'),
        ('floating', 'Floating'),
    ]
    idwindturbines = models.AutoField(db_column='idwindturbines', primary_key=True)
    turbine_model = models.CharField(
        max_length=70, 
        unique=True,
        help_text="Wind turbine model/type (must be unique)"
    )
    manufacturer = models.CharField(
        max_length=50, 
        blank=True, 
        null=True,
        help_text="Turbine manufacturer"
    )
    application = models.CharField(
        max_length=20, 
        choices=APPLICATION_CHOICES,
        blank=True, 
        null=True,
        help_text="Turbine application type"
    )
    hub_height = models.FloatField(
        blank=True, 
        null=True,
        help_text="Standard hub height in meters"
    )
    rated_power = models.FloatField(
        blank=True, 
        null=True,
        help_text="Rated power output in kW"
    )
    rotor_diameter = models.FloatField(
        blank=True, 
        null=True,
        help_text="Rotor diameter in meters"
    )
    cut_in_speed = models.FloatField(
        blank=True, 
        null=True,
        help_text="Cut-in wind speed in m/s"
    )
    cut_out_speed = models.FloatField(
        blank=True, 
        null=True,
        help_text="Cut-out wind speed in m/s"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'WindTurbines'
        verbose_name = 'Wind Turbine Model'
        verbose_name_plural = 'Wind Turbine Models'

    def __str__(self):
        return f"{self.manufacturer} {self.turbine_model}" if self.manufacturer else self.turbine_model

    def get_total_installations(self):
        """Get total number of this turbine model installed across all facilities"""
        return sum(
            installation.no_turbines 
            for installation in self.facilitywindturbines_set.filter(is_active=True)
        )
    
    def get_facilities_using(self):
        """Get list of facilities using this turbine model"""
        return [
            installation.facility 
            for installation in self.facilitywindturbines_set.filter(is_active=True)
        ]
    
    def get_active_power_curve(self):
        """Get the currently active power curve for this turbine"""
        return self.power_curves.filter(is_active=True).first()
    
    @property
    def rated_power_mw(self):
        """Get rated power in MW"""
        if self.rated_power:
            return self.rated_power / 1000
        return None
    
    @property
    def swept_area(self):
        """Calculate swept area in m² from rotor diameter"""
        if self.rotor_diameter:
            import math
            return math.pi * (self.rotor_diameter / 2) ** 2
        return None
    
    @property
    def specific_power(self):
        """Calculate specific power (W/m²) - rated power per swept area"""
        if self.rated_power and self.swept_area:
            return (self.rated_power * 1000) / self.swept_area
        return None

class FacilityWindTurbines(models.Model):
    """
    Through model for many-to-many relationship between facilities and WindTurbines
    Contains installation-specific data for turbines at each facility
    """
    idfacilitywindturbines = models.AutoField(db_column='idfacilitywindturbines', primary_key=True)
    idfacilities = models.ForeignKey(
        facilities, 
        on_delete=models.CASCADE, 
        db_column='idfacilities'
    )
    idwindturbines = models.ForeignKey(
        WindTurbines, 
        on_delete=models.CASCADE, 
        db_column='idwindturbines'
    )
    
    # NEW: Link to technology type (e.g., "Onshore Wind", "Offshore Wind")
    idtechnologies = models.ForeignKey(
        'Technologies',
        on_delete=models.CASCADE,
        db_column='idtechnologies',
        related_name='wind_facility_installations',
        limit_choices_to={'category': 'Wind'},
        null=True,  # Nullable for migration compatibility
        blank=True,
        help_text="Wind technology type (e.g., Onshore Wind, Offshore Wind)"
    )
    
    no_turbines = models.IntegerField(
        help_text="Number of this turbine model in this installation"
    )
    
    # Capacity override - if not set, calculated from turbine count × rated power
    nameplate_capacity = models.FloatField(
        null=True, 
        blank=True,
        help_text="MW - Override capacity. If null, calculated from turbine count × rated power"
    )
    
    # Installation geometry
    tilt = models.IntegerField(
        blank=True, 
        null=True,
        help_text="Turbine tilt angle in degrees"
    )
    direction = models.CharField(
        max_length=28, 
        blank=True, 
        null=True,
        help_text="Primary wind direction or turbine orientation"
    )
    hub_height_override = models.FloatField(
        blank=True, 
        null=True,
        help_text="Override hub height (m) if different from turbine default"
    )
    
    # Installation metadata
    installation_name = models.CharField(
        max_length=100, 
        blank=True, 
        null=True,
        help_text="Name for this installation (e.g., 'Phase 1', 'North Array')"
    )
    installation_date = models.DateField(
        blank=True, 
        null=True,
        help_text="Date when these turbines were installed"
    )
    commissioning_date = models.DateField(
        blank=True, 
        null=True,
        help_text="Date when these turbines began operations"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether these turbines are currently active"
    )
    
    notes = models.TextField(
        blank=True, 
        null=True,
        help_text="Additional notes about this turbine installation"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'FacilityWindTurbines'
        verbose_name = 'Facility Wind Turbine Installation'
        verbose_name_plural = 'Facility Wind Turbine Installations'
        # Allow same turbine model multiple times with different installation names
        unique_together = [['idfacilities', 'idwindturbines', 'installation_name']]
        ordering = ['idfacilities', 'commissioning_date']

    def __str__(self):
        name = self.installation_name or "Wind"
        return f"{self.facility.facility_name} - {self.wind_turbine.turbine_model} ({self.no_turbines} units) [{name}]"
    
    @property
    def wind_turbine(self):
        """Get the wind turbine model"""
        return self.idwindturbines

    @property
    def facility(self):
        """Get the facility"""
        return self.idfacilities

    @property
    def technology(self):
        """Get the technology type"""
        return self.idtechnologies

    @property
    def total_capacity(self):
        """
        Calculate total capacity for this turbine installation in MW.
        Uses override if set, otherwise calculates from turbine count × rated power.
        """
        if self.nameplate_capacity:
            return self.nameplate_capacity
        if self.wind_turbine.rated_power and self.no_turbines:
            # rated_power is in kW, convert to MW
            return (self.wind_turbine.rated_power * self.no_turbines) / 1000
        return None

    @property
    def hub_height(self):
        """Get hub height, using installation override if set, otherwise from turbine model"""
        if self.hub_height_override:
            return self.hub_height_override
        if self.wind_turbine and hasattr(self.wind_turbine, 'hub_height'):
            return self.wind_turbine.hub_height
        return None

class DPVGeneration(models.Model):
    """Store AEMO DPV generation estimates"""
    trading_date = models.DateField(db_index=True)
    interval_number = models.IntegerField()
    trading_interval = models.DateTimeField(db_index=True)
    estimated_generation = models.DecimalField(
        max_digits=10, 
        decimal_places=4,
        help_text="Estimated DPV Generation in MW"
    )
    extracted_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'dpv_generation'
        unique_together = ['trading_date', 'interval_number']
        indexes = [
            models.Index(fields=['trading_date', 'interval_number']),
            models.Index(fields=['trading_interval']),
        ]
        ordering = ['-trading_date', 'interval_number']
    
    def __str__(self):
        return f"DPV {self.trading_date} #{self.interval_number}: {self.estimated_generation}MW"

class FacilityScada(models.Model):
    """Store AEMO facility SCADA data with normalized facility reference"""
    dispatch_interval = models.DateTimeField(db_index=True)
    facility = models.ForeignKey(
        'facilities',
        on_delete=models.CASCADE,        db_column='idfacilities',
        related_name='scada_records'
    )
    quantity = models.DecimalField(max_digits=12, decimal_places=6)  # MW
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'facility_scada'
        unique_together = ['dispatch_interval', 'facility']
        indexes = [
            models.Index(fields=['dispatch_interval', 'facility']),
            models.Index(fields=['dispatch_interval']),
            models.Index(fields=['facility', 'dispatch_interval']),
        ]
        ordering = ['-dispatch_interval', 'facility']
    
    def __str__(self):
        return f"{self.facility.facility_code} @ {self.dispatch_interval}: {self.quantity}MW"

class LoadAnalysisSummary(models.Model):
    """Store pre-calculated monthly/daily summaries"""
    period_date = models.DateField(unique=True, db_index=True)
    period_type = models.CharField(max_length=20, choices=[
        ('DAILY', 'Daily'),
        ('MONTHLY', 'Monthly'),
    ])
    
    # Demand metrics (GWh for monthly, MWh for daily)
    operational_demand = models.DecimalField(max_digits=12, decimal_places=3)
    underlying_demand = models.DecimalField(max_digits=12, decimal_places=3)
    dpv_generation = models.DecimalField(max_digits=12, decimal_places=3)
    
    # Generation by type (GWh/MWh)
    wind_generation = models.DecimalField(max_digits=12, decimal_places=3)
    solar_generation = models.DecimalField(max_digits=12, decimal_places=3)
    storage_discharge = models.DecimalField(max_digits=12, decimal_places=3)
    storage_charge = models.DecimalField(max_digits=12, decimal_places=3)
    fossil_generation = models.DecimalField(max_digits=12, decimal_places=3)
    
    # Percentages
    re_percentage_operational = models.DecimalField(max_digits=5, decimal_places=2)
    re_percentage_underlying = models.DecimalField(max_digits=5, decimal_places=2)
    dpv_percentage_underlying = models.DecimalField(max_digits=5, decimal_places=2)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'load_analysis_summary'
        ordering = ['-period_date']

class TurbinePowerCurves(models.Model):
    idturbinepowercurves = models.AutoField(db_column='idturbinepowercurves', primary_key=True)
    idwindturbines = models.ForeignKey(WindTurbines, on_delete=models.CASCADE, related_name='power_curves', db_column='idwindturbines')
    power_file_name = models.CharField(max_length=45, 
                                     help_text="Original .pow file name")
    power_curve_data = models.JSONField(
        help_text="JSON stored power curve data from .pow file"
    )
    file_upload_date = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True, 
                                  help_text="Whether this power curve is currently active")
    notes = models.TextField(blank=True, null=True,
                           help_text="Additional notes about this power curve")

    class Meta:
        db_table = 'TurbinePowerCurves'
        verbose_name = 'Turbine Power Curve'
        verbose_name_plural = 'Turbine Power Curves'
        ordering = ['-file_upload_date']
        unique_together = [['idwindturbines', 'power_file_name']]  # Prevent duplicate file uploads

    def __str__(self):
        return f"Power Curve - {self.wind_turbine.turbine_model} ({self.power_file_name})"

    @property
    def hub_height(self):
        """Get hub height, using installation override if set"""
        return self.hub_height_override or self.wind_turbine.hub_height
    
    @property
    def capacity_summary(self):
        """Return a formatted string summarizing the installation"""
        cap = self.total_capacity
        if cap:
            return f"{self.no_turbines}× {self.wind_turbine.turbine_model} = {cap:.1f} MW"
        return f"{self.no_turbines}× {self.wind_turbine.turbine_model}"
    
    def clean(self):
        """Validate the installation"""
        if self.no_turbines is not None and self.no_turbines <= 0:
            raise ValidationError("Number of turbines must be positive")
        if self.nameplate_capacity is not None and self.nameplate_capacity <= 0:
            raise ValidationError("Nameplate capacity must be positive")
    
class Optimisations(models.Model):
    idoptimisation = models.AutoField(db_column='idOptimisation', primary_key=True)
    idscenarios = models.ForeignKey('Scenarios', on_delete=models.CASCADE, db_column='idScenarios')
    idtechnologies = models.ForeignKey('Technologies', on_delete=models.RESTRICT, db_column='idTechnologies')
    name = models.CharField(db_column='Name', max_length=45, blank=True, null=True)  
    approach = models.CharField(db_column='Approach', max_length=45, blank=True, null=True)  
    capacity = models.FloatField(db_column='Capacity', null=True)  
    capacitymax = models.FloatField(db_column='CapacityMax', null=True)  
    capacitymin = models.FloatField(db_column='CapacityMin', null=True)  
    capacitystep = models.FloatField(db_column='CapacityStep', null=True)  

    class Meta:
        db_table = 'Optimisations'

class Reference(models.Model):
    """Data source references"""
    idreferences = models.AutoField( db_column='idreferences', primary_key=True)
    source = models.CharField(max_length=500, help_text="Source name, URL, or citation")
    title = models.CharField(max_length=300, blank=True, help_text="Title of the referenced work")
    author = models.CharField(max_length=200, blank=True, help_text="Author(s) of the referenced work")
    publication_date = models.DateTimeField(null=True, blank=True, help_text="When the source was published")
    accessed_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True, help_text="When this reference was last modified")
    location = models.CharField(max_length=500, blank=True, help_text="URL or physical location")
    section = models.CharField(max_length=250, blank=True, help_text="Specific section, page, or chapter")
    notes = models.TextField(blank=True, help_text="Additional notes about this reference")
    
    # Reference type categorization
    REFERENCE_TYPES = [
        ('web', 'Website'),
        ('book', 'Book'),
        ('journal', 'Journal Article'),
        ('newspaper', 'Newspaper'),
        ('report', 'Report'),
        ('other', 'Other'),
    ]
    
    reference_type = models.CharField(
        max_length=20,
        choices=REFERENCE_TYPES,
        default='web',
        help_text="Type of reference source"
    )
    
    # Metadata
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this reference is still valid/active"
    )
    
    tags = models.CharField(
        max_length=300,
        blank=True,
        help_text="Comma-separated tags for categorization"
    )

    class Meta:
        db_table = 'Reference'
        ordering = ['-accessed_date']
        verbose_name = 'Reference'
        verbose_name_plural = 'References'
        indexes = [
            models.Index(fields=['reference_type']),
            models.Index(fields=['accessed_date']),
            models.Index(fields=['is_active']),
        ]

    def __str__(self):
        return f"{self.source[:50]}..." if len(self.source) > 50 else self.source

    def get_absolute_url(self):
        return reverse('reference_detail', kwargs={'pk': self.pk})

    def clean(self):
        """Custom validation"""
        if self.publication_date and self.publication_date > timezone.now():
            raise ValidationError("Publication date cannot be in the future")
        
        if self.location and not (self.location.startswith('http') or self.location.startswith('/')):
            # Assume it's a URL if it doesn't start with http or /
            if not self.location.startswith('www.'):
                raise ValidationError("Location should be a valid URL or file path")

    def get_tags_list(self):
        """Return tags as a list"""
        return [tag.strip() for tag in self.tags.split(',') if tag.strip()]

    @property
    def is_web_source(self):
        """Check if this is a web-based source"""
        return self.reference_type == 'web' or (self.location and self.location.startswith('http'))

class RenewableEnergyTarget(models.Model):
    """Store renewable energy targets for different years"""
    target_year = models.IntegerField(unique=True, db_index=True)
    target_percentage = models.FloatField(help_text="Target RE% for this year")
    target_emissions_tonnes = models.FloatField(null=True, blank=True, 
                                                help_text="Target emissions in tonnes CO2-e")
    description = models.CharField(max_length=500, blank=True, null=True)
    is_interim_target = models.BooleanField(default=False, 
                                           help_text="Is this an interim milestone?")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'renewable_energy_targets'
        ordering = ['target_year']
    
    def __str__(self):
        return f"{self.target_year}: {self.target_percentage}% RE Target"
    
    def get_monthly_target(self, month):
        """Calculate monthly target based on linear interpolation"""
        # Simplified - could be enhanced with seasonal adjustments
        return self.target_percentage

class MonthlyREPerformance(models.Model):
    """Store monthly renewable energy performance data"""
    year = models.IntegerField(db_index=True)
    month = models.IntegerField(db_index=True, 
                                help_text="Month number (1-12)")
    
    # Generation data (GWh)
    total_generation = models.FloatField(help_text="Total grid generation in GWh")
    operational_demand = models.FloatField(help_text="Operational demand in GWh")
    underlying_demand = models.FloatField(help_text="Underlying demand (includes rooftop) in GWh")
    
    # Renewable generation by technology (GWh)
    wind_generation = models.FloatField(default=0)
    solar_generation = models.FloatField(default=0)
    dpv_generation = models.FloatField(default=0)
    biomass_generation = models.FloatField(default=0)
    
    # Non-renewable generation (GWh)
    gas_generation = models.FloatField(default=0, help_text="Combined Cycle Gas Turbine")
    coal_generation = models.FloatField(default=0)
    
    # Storage (for information only - not counted in RE%)
    storage_discharge = models.FloatField(default=0)
    storage_charge = models.FloatField(default=0)
    
    # Emissions data
    total_emissions_tonnes = models.FloatField(help_text="Total emissions in tonnes CO2-e")
    emissions_intensity_kg_mwh = models.FloatField(help_text="Grid emissions intensity kg CO2-e/MWh")
    
    # Peak/minimum stats
    peak_demand_mw = models.FloatField(null=True, blank=True)
    peak_demand_datetime = models.DateTimeField(null=True, blank=True)
    minimum_demand_mw = models.FloatField(null=True, blank=True)
    minimum_demand_datetime = models.DateTimeField(null=True, blank=True)
    best_re_hour_percentage = models.FloatField(null=True, blank=True)
    best_re_hour_datetime = models.DateTimeField(null=True, blank=True)
    
    # Wholesale price statistics
    wholesale_price_max = models.FloatField(
        null=True, blank=True,
        help_text="Maximum wholesale price ($/MWh) for the month"
    )
    wholesale_price_max_datetime = models.DateTimeField(
        null=True, blank=True,
        help_text="Date/time of maximum wholesale price"
    )
    wholesale_price_min = models.FloatField(
        null=True, blank=True,
        help_text="Minimum wholesale price ($/MWh) for the month"
    )
    wholesale_price_min_datetime = models.DateTimeField(
        null=True, blank=True,
        help_text="Date/time of minimum wholesale price"
    )
    wholesale_price_avg = models.FloatField(
        null=True, blank=True,
        help_text="Average wholesale price ($/MWh) for the month"
    )
    wholesale_price_std_dev = models.FloatField(
        null=True, blank=True,
        help_text="Standard deviation of wholesale prices ($/MWh)"
    )
    wholesale_negative_count = models.IntegerField(
        null=True, blank=True,
        help_text="Number of trading intervals with negative prices"
    )
    wholesale_spike_count = models.IntegerField(
        null=True, blank=True,
        help_text="Number of trading intervals with prices > $300/MWh"
    )

    # Data quality
    data_complete = models.BooleanField(default=False)
    data_source = models.CharField(max_length=100, default='SCADA')
    notes = models.TextField(blank=True, null=True)
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'monthly_re_performance'
        unique_together = ['year', 'month']
        ordering = ['-year', '-month']
        indexes = [
            models.Index(fields=['year', 'month']),
            models.Index(fields=['-year', '-month']),
        ]
    
    def __str__(self):
        return f"{self.get_month_name()} {self.year}"
    
    # -------------------------------------------------------------------------
    # Renewable Generation Properties
    # -------------------------------------------------------------------------
    
    @property
    def renewable_gen_operational(self):
        """
        Renewable generation for operational demand basis.
        Excludes:
        - DPV (not grid-sent, behind-the-meter)
        - Hydro (pumped storage, like BESS)
        """
        return (self.wind_generation + 
                self.solar_generation + 
                self.biomass_generation)
    
    @property
    def total_renewable_generation(self):
        """
        Total renewable generation for underlying demand basis.
        Excludes storage discharge.
        """
        return (self.wind_generation + 
                self.solar_generation + 
                self.dpv_generation + 
                self.biomass_generation)
    
    # -------------------------------------------------------------------------
    # RE Percentage Properties
    # -------------------------------------------------------------------------
    
    @property
    def re_percentage_operational(self):
        """
        Calculate RE% based on operational demand.
        RE% = (wind + utility solar + biomass) / operational_demand
        
        Operational demand = grid-sent generation minus storage charging.
        """
        if self.operational_demand > 0:
            return (self.renewable_gen_operational / self.operational_demand) * 100
        return 0
    
    @property
    def re_percentage_underlying(self):
        """
        Calculate RE% based on underlying demand (PRIMARY METRIC).
        RE% = (wind + utility solar + biomass + DPV) / underlying_demand
        
        Underlying demand = operational demand + rooftop solar (DPV).
        """
        if self.underlying_demand > 0:
            return (self.total_renewable_generation / self.underlying_demand) * 100
        return 0
    
    @property
    def dpv_percentage_underlying(self):
        """Calculate distributed PV percentage of underlying demand"""
        if self.underlying_demand > 0:
            return (self.dpv_generation / self.underlying_demand) * 100
        return 0
    
    @property
    def storage_net_discharge(self):
        """Net storage discharge (positive = net discharge)"""
        return self.storage_discharge - self.storage_charge
    
    @property
    def wholesale_price_range(self):
        """Return the spread between max and min wholesale prices"""
        if self.wholesale_price_max is not None and self.wholesale_price_min is not None:
            return self.wholesale_price_max - self.wholesale_price_min
        return None
    
    @property
    def has_negative_pricing(self):
        """Check if there was negative pricing during the month"""
        return self.wholesale_negative_count is not None and self.wholesale_negative_count > 0
    
    @property
    def has_price_spikes(self):
        """Check if there were price spikes (>$300/MWh) during the month"""
        return self.wholesale_spike_count is not None and self.wholesale_spike_count > 0
    
    @property
    def wholesale_coefficient_of_variation(self):
        """
        Coefficient of variation (CV) for wholesale prices.
        CV = (std_dev / avg) * 100
        Useful for comparing volatility across months with different average prices.
        """
        if (self.wholesale_price_std_dev is not None and 
            self.wholesale_price_avg is not None and 
            self.wholesale_price_avg != 0):
            return (self.wholesale_price_std_dev / self.wholesale_price_avg) * 100
        return None
    
    @property
    def wholesale_total_intervals(self):
        """
        Approximate total trading intervals in the month.
        Based on 48 intervals per day (30-min intervals).
        """
        from calendar import monthrange
        _, days = monthrange(self.year, self.month)
        return days * 48
    
    @property
    def wholesale_negative_percentage(self):
        """Percentage of intervals with negative prices"""
        total = self.wholesale_total_intervals
        if self.wholesale_negative_count is not None and total > 0:
            return (self.wholesale_negative_count / total) * 100
        return None
    
    @property
    def wholesale_spike_percentage(self):
        """Percentage of intervals with price spikes (>$300/MWh)"""
        total = self.wholesale_total_intervals
        if self.wholesale_spike_count is not None and total > 0:
            return (self.wholesale_spike_count / total) * 100
        return None
    
    # -------------------------------------------------------------------------
    # Helper Methods
    # -------------------------------------------------------------------------
    
    def get_month_name(self):
        """Return month name"""
        months = ['', 'January', 'February', 'March', 'April', 'May', 'June',
                 'July', 'August', 'September', 'October', 'November', 'December']
        return months[self.month] if 1 <= self.month <= 12 else 'Unknown'
    
    # -------------------------------------------------------------------------
    # Target Methods
    # -------------------------------------------------------------------------
    
    def get_target_for_period(self):
        """Get the renewable energy target for this period"""
        try:
            target = RenewableEnergyTarget.objects.get(target_year=self.year)
            return target
        except RenewableEnergyTarget.DoesNotExist:
            # Interpolate if exact year not found
            return self.interpolate_target()
    
    def interpolate_target(self):
        """Interpolate target between known target years"""
        targets = RenewableEnergyTarget.objects.all().order_by('target_year')
        
        # Find surrounding targets
        before = targets.filter(target_year__lt=self.year).last()
        after = targets.filter(target_year__gt=self.year).first()
        
        if before and after:
            # Linear interpolation
            year_diff = after.target_year - before.target_year
            year_progress = self.year - before.target_year
            target_diff = after.target_percentage - before.target_percentage
            
            interpolated_percentage = before.target_percentage + (target_diff * year_progress / year_diff)
            
            # Create a temporary target object (not saved)
            from collections import namedtuple
            Target = namedtuple('Target', ['target_year', 'target_percentage'])
            return Target(self.year, interpolated_percentage)
        elif before:
            return before
        elif after:
            return after
        
        return None
    
    def get_status_vs_target(self):
        """Determine if performance is ahead/behind target"""
        target = self.get_target_for_period()
        if not target:
            return {'status': 'unknown', 'gap': 0, 'message': 'No target set'}
        
        gap = self.re_percentage_underlying - target.target_percentage
        
        if gap >= 0:
            return {
                'status': 'ahead',
                'gap': gap,
                'message': f'✓ {abs(gap):.1f} percentage points ahead'
            }
        else:
            return {
                'status': 'behind',
                'gap': gap,
                'message': f'⚠ {abs(gap):.1f} percentage points behind'
            }

    # -------------------------------------------------------------------------
    # Aggregate Summary Methods
    # -------------------------------------------------------------------------
    
    @classmethod
    def aggregate_summary(cls, queryset):
        """
        Calculate aggregate summary from a queryset of MonthlyREPerformance records.
        
        This is the SINGLE SOURCE OF TRUTH for RE% calculations.
        
        Storage policy:
        - BESS and Hydro (pumped storage) are EXCLUDED from:
          - Renewable generation totals
          - RE% calculations
          - Demand is already net of storage charging
        
        Args:
            queryset: QuerySet of MonthlyREPerformance records
            
        Returns:
            dict with aggregated values, or None if queryset is empty
        """
        if not queryset.exists():
            return None
        
        # Fetch all records once to avoid multiple queries
        records = list(queryset)
        
        # Sum generation fields
        wind = sum(r.wind_generation for r in records)
        solar = sum(r.solar_generation for r in records)
        dpv = sum(r.dpv_generation for r in records)
        biomass = sum(r.biomass_generation for r in records)
        gas = sum(r.gas_generation for r in records)
        coal = sum(r.coal_generation for r in records)
        
        # Sum demand fields
        total_generation = sum(r.total_generation for r in records)
        operational_demand = sum(r.operational_demand for r in records)
        underlying_demand = sum(r.underlying_demand for r in records)
        
        # Sum storage fields
        storage_discharge = sum(r.storage_discharge for r in records)
        storage_charge = sum(r.storage_charge for r in records)
        
        # Sum emissions
        total_emissions = sum(r.total_emissions_tonnes for r in records)
        
        # Wholesale price statistics
        # For multi-month aggregation:
        # - Averages: simple average of monthly averages
        # - Std dev: average of monthly std devs (approximation)
        # - Counts: sum of monthly counts
        # - Max/Min: overall max/min across months
        
        wholesale_avgs = [r.wholesale_price_avg for r in records if r.wholesale_price_avg is not None]
        wholesale_std_devs = [r.wholesale_price_std_dev for r in records if r.wholesale_price_std_dev is not None]
        negative_counts = [r.wholesale_negative_count for r in records if r.wholesale_negative_count is not None]
        spike_counts = [r.wholesale_spike_count for r in records if r.wholesale_spike_count is not None]
        
        if wholesale_avgs:
            avg_wholesale_price = sum(wholesale_avgs) / len(wholesale_avgs)
            max_wholesale = max((r.wholesale_price_max for r in records if r.wholesale_price_max is not None), default=None)
            min_wholesale = min((r.wholesale_price_min for r in records if r.wholesale_price_min is not None), default=None)
        else:
            avg_wholesale_price = None
            max_wholesale = None
            min_wholesale = None
        
        avg_std_dev = sum(wholesale_std_devs) / len(wholesale_std_devs) if wholesale_std_devs else None
        total_negative_count = sum(negative_counts) if negative_counts else None
        total_spike_count = sum(spike_counts) if spike_counts else None
            
        # Calculate renewable totals
        # Hydro (pumped storage) excluded - it's storage like BESS
        renewable_gen_operational = wind + solar + biomass
        renewable_gen_underlying = renewable_gen_operational + dpv
        
        # Calculate RE percentages
        if operational_demand > 0:
            re_pct_operational = (renewable_gen_operational / operational_demand) * 100
            emissions_intensity = (total_emissions * 1000) / operational_demand  # kg/MWh
        else:
            re_pct_operational = 0
            emissions_intensity = 0
        if underlying_demand > 0:
            re_pct_underlying = (renewable_gen_underlying / underlying_demand) * 100
        else:
            re_pct_underlying = 0

        return {
            # Generation totals
            'total_generation': total_generation,
            'operational_demand': operational_demand,
            'underlying_demand': underlying_demand,
            
            # Generation by technology
            'wind_generation': wind,
            'solar_generation': solar,
            'dpv_generation': dpv,
            'biomass_generation': biomass,
            'gas_generation': gas,
            'coal_generation': coal,
            
            # Storage (for display only)
            'storage_discharge': storage_discharge,
            'storage_charge': storage_charge,
            
            # Renewable totals
            'renewable_generation': renewable_gen_underlying,
            'renewable_gen_operational': renewable_gen_operational,
            'renewable_gen_underlying': renewable_gen_underlying,
            
            # RE percentages
            're_percentage_operational': re_pct_operational,
            're_percentage_underlying': re_pct_underlying,
            're_percentage': re_pct_underlying,  # Backwards compatibility alias
            
            # Emissions
            'total_emissions': total_emissions,
            'total_emissions_tonnes': total_emissions,
            'emissions_intensity': emissions_intensity,
            'emissions_intensity_kg_mwh': emissions_intensity,
            
            # Wholesale prices
            'wholesale_price_avg': avg_wholesale_price,
            'wholesale_price_max': max_wholesale,
            'wholesale_price_min': min_wholesale,
            'wholesale_price_std_dev': avg_std_dev,
            'wholesale_negative_count': total_negative_count,
            'wholesale_spike_count': total_spike_count,
        }
    
    def calculate_ytd_summary(self):
        """
        Calculate year-to-date summary up to and including this month.
        
        Returns:
            dict with YTD aggregated values
        """
        ytd_records = MonthlyREPerformance.objects.filter(
            year=self.year,
            month__lte=self.month
        )
        return MonthlyREPerformance.aggregate_summary(ytd_records)
    
class NewCapacityCommissioned(models.Model):
    """Track new renewable capacity commissioned"""
    facility = models.ForeignKey('facilities', on_delete=models.CASCADE, 
                                related_name='commissioning_records')
    commissioned_date = models.DateField()
    capacity_mw = models.FloatField(help_text="Capacity in MW")
    technology_type = models.CharField(max_length=50)
    
    # Monthly association for reporting
    report_year = models.IntegerField()
    report_month = models.IntegerField()
    
    status = models.CharField(max_length=20, choices=[
        ('commissioned', 'Commissioned'),
        ('under_construction', 'Under Construction'),
        ('planned', 'Planned'),
        ('probable', 'Probable'),
        ('possible', 'Possible'),
    ], default='commissioned')
    
    expected_commissioning_date = models.DateField(null=True, blank=True,
                                                   help_text="For future projects")
    
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'new_capacity_commissioned'
        ordering = ['-commissioned_date']
        indexes = [
            models.Index(fields=['commissioned_date']),
            models.Index(fields=['report_year', 'report_month']),
        ]
    
    def __str__(self):
        return f"{self.facility.facility_name} - {self.capacity_mw}MW ({self.commissioned_date})"

class ReportComment(models.Model):
    """
    Comments for RET dashboard reports (monthly, quarterly, annual).
    """
    REPORT_TYPE_CHOICES = [
        ('monthly', 'Monthly Dashboard'),
        ('quarterly', 'Quarterly Report'),
        ('annual', 'Annual Review'),
    ]
    
    # Report identification
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    year = models.IntegerField(validators=[MinValueValidator(2000), MaxValueValidator(2100)])
    month = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
        help_text="Required for monthly reports"
    )
    quarter = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(4)],
        help_text="Required for quarterly reports"
    )
    
    # Comment content
    author = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='ret_comments',
        db_constraint=False  # Avoids FK constraint issues with unmanaged auth_user table
    )
    author_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Stored separately in case user is deleted"
    )
    content = models.TextField()
    
    # Optional: categorise comments
    CATEGORY_CHOICES = [
        ('general', 'General'),
        ('observation', 'Observation'),
        ('question', 'Question'),
        ('action_item', 'Action Item'),
        ('correction', 'Correction'),
        ('executive_summary', 'Executive Summary'),
    ]
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='general'
    )
    
    # Metadata
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    is_pinned = models.BooleanField(default=False, help_text="Pinned comments appear at top")
    is_resolved = models.BooleanField(default=False, help_text="Mark action items/questions as resolved")
    
    class Meta:
        ordering = ['-is_pinned', '-created_at']
        indexes = [
            models.Index(fields=['report_type', 'year', 'month']),
            models.Index(fields=['report_type', 'year', 'quarter']),
            models.Index(fields=['report_type', 'year']),
        ]
    
    def save(self, *args, **kwargs):
        # Store author name separately for persistence
        if self.author and not self.author_name:
            self.author_name = self.author.get_full_name() or self.author.username
        super().save(*args, **kwargs)
    
    def __str__(self):
        return f"{self.get_report_type_display()} - {self.get_period_display()} by {self.author_name}"
    
    def get_period_display(self):
        """Return human-readable period string."""
        if self.report_type == 'monthly':
            from calendar import month_name
            return f"{month_name[self.month]} {self.year}"
        elif self.report_type == 'quarterly':
            return f"Q{self.quarter} {self.year}"
        else:
            return f"{self.year} Annual Review"
    
    @classmethod
    def get_comments_for_report(cls, report_type, year, month=None, quarter=None):
        """
        Retrieve all comments for a specific report.
        """
        queryset = cls.objects.filter(report_type=report_type, year=year)

        if report_type == 'monthly' and month:
            queryset = queryset.filter(month=month)
        elif report_type == 'quarterly' and quarter:
            queryset = queryset.filter(quarter=quarter)

        return queryset.select_related('author')


class PublishedReport(models.Model):
    """
    Stores published PDF versions of RET reports (quarterly and annual).
    """
    REPORT_TYPE_CHOICES = [
        ('quarterly', 'Quarterly Report'),
        ('annual', 'Annual Review'),
    ]

    # Report identification
    report_type = models.CharField(max_length=20, choices=REPORT_TYPE_CHOICES)
    year = models.IntegerField(validators=[MinValueValidator(2000), MaxValueValidator(2100)])
    quarter = models.IntegerField(
        null=True, blank=True,
        validators=[MinValueValidator(1), MaxValueValidator(4)],
        help_text="Required for quarterly reports"
    )

    # File storage
    pdf_file = models.FileField(
        upload_to='published_reports/',
        help_text="PDF file of the published report"
    )
    html_file = models.FileField(
        upload_to='published_reports/',
        null=True,
        blank=True,
        help_text="HTML file with interactive Plotly charts"
    )

    # Metadata
    published_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='published_reports',
        db_constraint=False
    )
    published_by_name = models.CharField(
        max_length=100,
        blank=True,
        help_text="Stored separately in case user is deleted"
    )
    published_at = models.DateTimeField(auto_now_add=True)
    file_size = models.IntegerField(null=True, blank=True, help_text="PDF file size in bytes")
    html_file_size = models.IntegerField(null=True, blank=True, help_text="HTML file size in bytes")

    class Meta:
        ordering = ['-year', '-quarter', '-published_at']
        indexes = [
            models.Index(fields=['report_type', 'year', 'quarter']),
            models.Index(fields=['report_type', 'year']),
        ]
        # Ensure only one published report per period (latest one)
        unique_together = [['report_type', 'year', 'quarter']]

    def save(self, *args, **kwargs):
        # Store publisher name separately for persistence
        if self.published_by and not self.published_by_name:
            self.published_by_name = self.published_by.get_full_name() or self.published_by.username

        # Store file sizes if not already set
        if self.pdf_file and not self.file_size:
            self.file_size = self.pdf_file.size

        if self.html_file and not self.html_file_size:
            self.html_file_size = self.html_file.size

        super().save(*args, **kwargs)

    def __str__(self):
        return f"{self.get_report_type_display()} - {self.get_period_display()}"

    def get_period_display(self):
        """Return human-readable period string."""
        if self.report_type == 'quarterly':
            return f"Q{self.quarter} {self.year}"
        else:
            return f"{self.year} Annual Review"

    def get_filename(self):
        """Return suggested filename for PDF download."""
        if self.report_type == 'quarterly':
            return f"SWIS_Quarterly_Report_Q{self.quarter}_{self.year}.pdf"
        else:
            return f"SWIS_Annual_Review_{self.year}.pdf"

    def get_html_filename(self):
        """Return suggested filename for HTML download."""
        if self.report_type == 'quarterly':
            return f"SWIS_Quarterly_Report_Q{self.quarter}_{self.year}.html"
        else:
            return f"SWIS_Annual_Review_{self.year}.html"

    @property
    def file_size_mb(self):
        """Return PDF file size in MB."""
        if self.file_size:
            return round(self.file_size / (1024 * 1024), 2)
        return None

    @property
    def html_file_size_mb(self):
        """Return HTML file size in MB."""
        if self.html_file_size:
            return round(self.html_file_size / (1024 * 1024), 2)
        return None

class TargetScenario(models.Model):
    """
    Unified model for renewable energy targets and projection scenarios.
    Combines what was previously RenewableEnergyTarget and TargetScenario.
    """
    scenario_name = models.CharField(max_length=100, db_index=True)
    scenario_type = models.CharField(max_length=30, choices=[
        ('base_case', 'Base Case'),
        ('delayed_pipeline', 'Delayed Pipeline'),
        ('accelerated_pipeline', 'Accelerated Pipeline'),
    ])

    # Link to SIREN Scenarios model
    scenario = models.ForeignKey(
        'Scenarios',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='target_scenarios',
        help_text="Associated SIREN scenario"
    )

    description = models.TextField(blank=True, default='')

    # Year for this scenario/target
    year = models.IntegerField(
        db_index=True,
        help_text="Target or projection year"
    )

    # Target type: distinguishes between major targets, interim milestones, and ordinary years
    target_type = models.CharField(
        max_length=20,
        choices=[
            ('major', 'Major Target'),
            ('interim', 'Interim Target'),
            ('ordinary', 'Ordinary Year'),
        ],
        default='ordinary',
        help_text="Type of year: major target, interim milestone, or ordinary projection"
    )

    # Demand projections (GWh)
    operational_demand = models.FloatField(
        null=True,
        blank=True,
        help_text="Operational demand (GWh)"
    )
    underlying_demand = models.FloatField(
        null=True,
        blank=True,
        help_text="Underlying demand (GWh)"
    )

    # Storage capacity (MWh)
    storage = models.FloatField(
        null=True,
        blank=True,
        help_text="Storage capacity (MWh)"
    )

    # Target/Projected values (year-agnostic)
    target_re_percentage = models.FloatField(
        help_text="Target or projected RE percentage for this year"
    )
    target_emissions_tonnes = models.FloatField(
        null=True,
        blank=True,
        help_text="Target or projected emissions (tonnes CO2-e)"
    )

    # Generation mix projections (GWh)
    wind_generation = models.FloatField(
        default=0,
        help_text="Wind generation (GWh)"
    )
    solar_generation = models.FloatField(
        default=0,
        help_text="Utility-scale solar generation (GWh)"
    )
    dpv_generation = models.FloatField(
        default=0,
        help_text="Distributed rooftop solar generation (GWh)"
    )
    biomass_generation = models.FloatField(
        default=0,
        help_text="Biomass generation (GWh)"
    )
    gas_generation = models.FloatField(
        default=0,
        help_text="Gas generation (GWh)"
    )

    # Probability of achievement (for projection scenarios)
    probability_percentage = models.FloatField(
        null=True,
        blank=True,
        help_text="Monte Carlo probability of achieving this scenario (%)"
    )

    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'target_scenarios'
        ordering = ['year', 'scenario_type']
        unique_together = [['scenario_type', 'year']]
        indexes = [
            models.Index(fields=['year', 'target_type']),
            models.Index(fields=['scenario_type', 'year']),
        ]

    def __str__(self):
        return f"{self.scenario_name}: {self.target_re_percentage}% by {self.year}"

    @property
    def total_generation(self):
        """Calculate total generation"""
        return (self.wind_generation +
                self.solar_generation +
                self.dpv_generation +
                self.biomass_generation +
                self.gas_generation)

    @property
    def is_major_target(self):
        """Check if this is a major target year"""
        return self.target_type == 'major'

    @property
    def is_interim_target(self):
        """Check if this is an interim target"""
        return self.target_type == 'interim'

    def get_status_vs_target(self, comparison_year=None):
        """
        Check if scenario meets a specific target.
        If comparison_year is None, compares against major/interim targets for the same year.
        """
        if comparison_year is None:
            comparison_year = self.year

        try:
            # Find major or interim target for the comparison year
            target = TargetScenario.objects.filter(
                year=comparison_year,
                target_type__in=['major', 'interim']
            ).first()

            if not target:
                return {'meets_target': None, 'gap': 0, 'message': 'No target set'}

            gap = self.target_re_percentage - target.target_re_percentage

            return {
                'meets_target': gap >= 0,
                'gap': gap,
                'message': f"{'✓ Exceeds' if gap >= 0 else '✗ Below'} target by {abs(gap):.1f}pp"
            }
        except Exception:
            return {'meets_target': None, 'gap': 0, 'message': 'Error comparing to target'}

class ScenariosFacilities(models.Model):
    idscenariosfacilities = models.AutoField(primary_key=True)  
    idscenarios = models.ForeignKey('Scenarios', on_delete=models.CASCADE, db_column='idScenarios')
    idfacilities = models.ForeignKey('facilities', on_delete=models.CASCADE, db_column='idfacilities')

    class Meta:
        db_table = 'ScenariosFacilities'

class ScenariosTechnologies(models.Model):
    idscenariostechnologies = models.AutoField(primary_key=True)  
    idscenarios = models.ForeignKey('Scenarios', on_delete=models.CASCADE)
    idtechnologies = models.ForeignKey('Technologies', on_delete=models.CASCADE)
    merit_order = models.IntegerField(null=True)
    capacity = models.FloatField(null=True)
    mult = models.FloatField(null=True)
    col = models.PositiveIntegerField(null=True)  

    class Meta:
        db_table = 'ScenariosTechnologies'
        
    def update_capacity(self):
        """Calculate and update capacity from related facilities"""
        total_capacity = facilities.objects.filter(
            idtechnologies=self.idtechnologies,
            scenariosfacilities__idscenarios=self.idscenarios
        ).aggregate(total=models.Sum('capacity'))['total'] or 0
        
        self.capacity = total_capacity
        self.save(update_fields=['capacity'])
        return total_capacity

class ScenariosSettings(models.Model):
    idscenariossettings = models.AutoField(primary_key=True)
    idscenarios = models.ForeignKey('Scenarios', on_delete=models.CASCADE)
    sw_context = models.CharField(max_length=20, blank=True, null=True)
    parameter = models.CharField(max_length=45, blank=True, null=True)
    value = models.CharField(max_length=600, blank=True, null=True)
    units = models.CharField(max_length=10, blank=True, null=True) 

    class Meta:
        db_table = 'ScenariosSettings'
        
class Settings(models.Model):
    idsettings = models.AutoField(db_column='idSettings', primary_key=True)  
    sw_context = models.CharField(max_length=20, blank=True, null=True)
    parameter = models.CharField(max_length=45, blank=True, null=True)
    value = models.CharField(max_length=600, blank=True, null=True)

    class Meta:
        db_table = 'Settings'
        
class sirensystem(models.Model):
    name = models.CharField(max_length=30, primary_key=True)
    description = models.CharField(max_length=500, blank=True, null=True)
    
    class Meta:
        db_table = 'sirensystem'

class SolarAttributes(models.Model):
    """
    Technology-level attributes for solar PV systems
    Linked to Technologies with category='Solar'
    """
    idsolarattributes = models.AutoField(db_column='idSolarAttributes', primary_key=True)
    idtechnologies = models.ForeignKey(
        'Technologies', 
        models.CASCADE, 
        db_column='idTechnologies', 
        blank=True, 
        null=True,
        related_name='solar_attributes'
    )
    
    # Panel/Module Specifications
    module_efficiency = models.FloatField(
        null=True, 
        blank=True,
        help_text="Module efficiency as decimal (e.g., 0.20 for 20%)"
    )
    temperature_coefficient = models.FloatField(
        null=True, 
        blank=True,
        help_text="Temperature coefficient of power (%/°C, typically -0.3 to -0.5)"
    )
    nominal_operating_cell_temp = models.FloatField(
        null=True, 
        blank=True,
        help_text="NOCT in °C (typically 42-46°C)"
    )
    
    # System Specifications
    inverter_efficiency = models.FloatField(
        null=True, 
        blank=True,
        help_text="Inverter efficiency as decimal (e.g., 0.98)"
    )
    system_loss_factor = models.FloatField(
        null=True, 
        blank=True,
        help_text="Combined system losses as decimal (soiling, wiring, mismatch, etc.)"
    )
    dc_ac_ratio = models.FloatField(
        null=True, 
        blank=True,
        help_text="DC to AC ratio (typically 1.1 to 1.3)"
    )
    
    # Performance Metrics
    performance_ratio = models.FloatField(
        null=True, 
        blank=True,
        help_text="System performance ratio (PR) as decimal (typically 0.75-0.85)"
    )
    capacity_factor_typical = models.FloatField(
        null=True, 
        blank=True,
        help_text="Typical capacity factor for this technology (location-dependent)"
    )
    
    # Degradation
    degradation_rate = models.FloatField(
        null=True, 
        blank=True,
        help_text="Annual degradation rate as decimal (typically 0.005 = 0.5%/year)"
    )
    warranty_years = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Panel warranty period in years"
    )
    
    # Technology Type
    PANEL_TYPES = [
        ('monocrystalline', 'Monocrystalline Silicon'),
        ('polycrystalline', 'Polycrystalline Silicon'),
        ('thin_film', 'Thin Film'),
        ('cigs', 'CIGS'),
        ('cdte', 'CdTe'),
        ('perc', 'PERC'),
        ('bifacial', 'Bifacial'),
        ('tandem', 'Tandem/Multi-junction'),
    ]
    panel_technology = models.CharField(
        max_length=30,
        choices=PANEL_TYPES,
        blank=True,
        null=True,
        help_text="Type of solar panel technology"
    )
    
    # Tracking System
    TRACKING_TYPES = [
        ('fixed', 'Fixed Tilt'),
        ('single_axis', 'Single-Axis Tracking'),
        ('dual_axis', 'Dual-Axis Tracking'),
    ]
    tracking_type = models.CharField(
        max_length=20,
        choices=TRACKING_TYPES,
        default='fixed',
        help_text="Type of tracking system"
    )
    
    class Meta:
        db_table = 'SolarAttributes'
        verbose_name = 'Solar Attribute'
        verbose_name_plural = 'Solar Attributes'

    def __str__(self):
        tech_name = self.idtechnologies.technology_name if self.idtechnologies else "Unknown"
        return f"Solar Attributes for {tech_name}"
    
    def get_typical_values_by_type(self, panel_type):
        """Return typical values for different panel types"""
        typical_values = {
            'monocrystalline': {
                'module_efficiency': 0.20,
                'temperature_coefficient': -0.40,
                'degradation_rate': 0.005,
                'performance_ratio': 0.80,
            },
            'polycrystalline': {
                'module_efficiency': 0.17,
                'temperature_coefficient': -0.45,
                'degradation_rate': 0.006,
                'performance_ratio': 0.78,
            },
            'thin_film': {
                'module_efficiency': 0.12,
                'temperature_coefficient': -0.25,
                'degradation_rate': 0.007,
                'performance_ratio': 0.75,
            },
            'perc': {
                'module_efficiency': 0.21,
                'temperature_coefficient': -0.38,
                'degradation_rate': 0.004,
                'performance_ratio': 0.82,
            },
            'bifacial': {
                'module_efficiency': 0.21,
                'temperature_coefficient': -0.39,
                'degradation_rate': 0.005,
                'performance_ratio': 0.85,
            },
        }
        return typical_values.get(panel_type, {})

class Storageattributes(models.Model):
    """Technology-level attributes for energy storage systems"""
    idstorageattributes = models.AutoField(db_column='idStorageAttributes', primary_key=True)
    idtechnologies = models.ForeignKey(
        'Technologies', 
        models.CASCADE, 
        db_column='idTechnologies', 
        blank=True, 
        null=True,
        related_name='storage_attributes'
    )
    discharge_loss = models.IntegerField(blank=True, null=True)
    discharge_max = models.FloatField(null=True)
    parasitic_loss = models.IntegerField(blank=True, null=True)
    recharge_loss = models.IntegerField(blank=True, null=True)
    recharge_max = models.FloatField(null=True)

    # Efficiency
    round_trip_efficiency = models.FloatField(null=True, help_text="Decimal, e.g., 0.85")
    charge_efficiency = models.FloatField(null=True, help_text="Decimal, e.g., 0.92")
    discharge_efficiency = models.FloatField(null=True, help_text="Decimal, e.g., 0.92")
    
    # Operating Constraints
    min_state_of_charge = models.FloatField(default=0.0, help_text="Minimum SOC (0-1)")
    max_state_of_charge = models.FloatField(default=1.0, help_text="Maximum SOC (0-1)")
    initial_state_of_charge = models.FloatField(default=0.5, help_text="Starting SOC")
    
    # Degradation
    cycle_life = models.IntegerField(null=True, help_text="Full cycle equivalents")
    degradation_rate = models.FloatField(null=True, help_text="% per year")
    
    # Losses
    self_discharge_rate = models.FloatField(null=True, help_text="% per hour")
    auxiliary_load = models.FloatField(null=True, help_text="MW - parasitic load")
    
    class Meta:
        db_table = 'StorageAttributes'
        verbose_name = 'Storage Attribute'
        verbose_name_plural = 'Storage Attributes'

    def __str__(self):
        return f"Storage Attributes for {self.idtechnologies.technology_name}"
    
    def validate_soc_constraints(self):
        """Validate that SOC constraints are logical"""
        if self.min_state_of_charge is not None and self.max_state_of_charge is not None:
            if self.min_state_of_charge >= self.max_state_of_charge:
                raise ValueError("Minimum SOC must be less than Maximum SOC")
            if self.min_state_of_charge < 0 or self.max_state_of_charge > 1:
                raise ValueError("SOC values must be between 0.0 and 1.0")
        return True
    
    def get_typical_values_by_type(self, storage_type):
        """Return typical values for different storage types"""
        typical_values = {
            'Battery (1hr)': {
                'duration': 1.0,
                'round_trip_efficiency': 0.85,
                'cycle_life': 5000,
                'self_discharge_rate': 0.01,
            },
            'Battery (2hr)': {
                'duration': 2.0,
                'round_trip_efficiency': 0.85,
                'cycle_life': 5000,
                'self_discharge_rate': 0.01,
            },
            'Battery (4hr)': {
                'duration': 4.0,
                'round_trip_efficiency': 0.85,
                'cycle_life': 5000,
                'self_discharge_rate': 0.01,
            },
            'Battery (8hr)': {
                'duration': 8.0,
                'round_trip_efficiency': 0.85,
                'cycle_life': 5000,
                'self_discharge_rate': 0.01,
            },
            'PHES (24hr)': {
                'duration': 24.0,
                'round_trip_efficiency': 0.75,
                'cycle_life': 20000,
                'self_discharge_rate': 0.0,
            },
            'PHES (48hr)': {
                'duration': 48.0,
                'round_trip_efficiency': 0.75,
                'cycle_life': 20000,
                'self_discharge_rate': 0.0,
            },
            'Flow Battery': {
                'duration': 6.0,
                'round_trip_efficiency': 0.70,
                'cycle_life': 10000,
                'self_discharge_rate': 0.001,
            },
        }
        return typical_values.get(storage_type, {})

class supplyfactors(models.Model):
    idsupplyfactors = models.AutoField(db_column='idsupplyfactors', primary_key=True)  
    idfacilities = models.ForeignKey('facilities', on_delete=models.CASCADE, db_column='idfacilities', blank=True, null=True)
    year = models.PositiveIntegerField()
    hour = models.IntegerField(blank=True, null=True)
    supply = models.IntegerField(blank=True, null=True)
    quantum = models.FloatField(null=True)

    class Meta:
        db_table = 'supplyfactors'

class Technologies(models.Model):
    """
    Technology types for energy generation and storage.
    Categories include: Wind, Solar, Storage, Generator, etc.
    """
    idtechnologies = models.AutoField(db_column='idTechnologies', primary_key=True)
    technology_name = models.CharField(unique=True, max_length=45)
    technology_signature = models.CharField(unique=True, max_length=20)
    scenarios = models.ManyToManyField('Scenarios', through='ScenariosTechnologies', blank=True)
    image = models.CharField(max_length=50, blank=True, null=True)
    caption = models.CharField(max_length=50, blank=True, null=True)
    category = models.CharField(max_length=45, blank=True, null=True)
    renewable = models.IntegerField(blank=True, null=True)
    dispatchable = models.IntegerField(blank=True, null=True)
    lifetime = models.FloatField(null=True)
    discount_rate = models.FloatField(null=True)
    emissions = models.FloatField(null=True)
    description = models.CharField(max_length=1000, db_collation='utf8mb4_0900_ai_ci', blank=True, null=True)
    area = models.FloatField(blank=True, null=True)
    water_usage = models.FloatField(blank=True, null=True)
    fuel_type = models.CharField(blank=True, null=True, max_length=30, choices=[
        ('WIND', 'Wind'),
        ('SOLAR', 'Solar'),
        ('GAS', 'Gas'),
        ('COAL', 'Coal'),
        ('HYDRO', 'Hydro'),
        ('BIOMASS', 'Biomass'),
        ('OTHER', 'Other'),
    ])

    class Meta:
        db_table = 'Technologies'

    def __str__(self):
        return self.technology_name

    @property
    def storage_attrs(self):
        """
        Helper property to easily access storage attributes.
        Returns the first (and typically only) storage attribute record.
        Usage: technology.storage_attrs.discharge_max
        """
        try:
            return self.storage_attributes.first()
        except:
            return None
        
class TechnologyYears(models.Model):
    """Year-specific cost data for technologies"""
    idtechnologyyears = models.AutoField(primary_key=True)
    idtechnologies = models.ForeignKey('Technologies', on_delete=models.RESTRICT)
    year = models.IntegerField(default=0, null=True)
    capex = models.FloatField(null=True)
    fom = models.FloatField(db_column='FOM', null=True)  
    vom = models.FloatField(db_column='VOM', null=True)  
    fuel = models.FloatField(null=True)

    class Meta:
        db_table = 'TechnologyYears'

class Terminals(models.Model):
    """Model to store terminal/substation data for grid infrastructure"""
    TERMINAL_TYPES = [
        ('substation', 'Substation'),
        ('switching_station', 'Switching Station'),
        ('distribution_substation', 'Distribution Substation'),
        ('transmission_substation', 'Transmission Substation'),
        ('converter_station', 'Converter Station'),
        ('terminal_station', 'Terminal Station'),
    ]
    
    VOLTAGE_CLASSES = [
        ('low', 'Low Voltage (< 1kV)'),
        ('medium', 'Medium Voltage (1-35kV)'),
        ('high', 'High Voltage (35-138kV)'),
        ('extra_high', 'Extra High Voltage (138-800kV)'),
        ('ultra_high', 'Ultra High Voltage (> 800kV)'),
    ]
    
    idterminals = models.AutoField(primary_key=True, db_column='idterminals')
    terminal_name = models.CharField(max_length=100, unique=True, help_text="Unique name for the terminal")
    terminal_code = models.CharField(max_length=30, unique=True, help_text="Short code for the terminal")
    terminal_type = models.CharField(max_length=30, choices=TERMINAL_TYPES, default='substation')
    
    # Location
    latitude = models.FloatField(help_text="Terminal latitude")
    longitude = models.FloatField(help_text="Terminal longitude")
    elevation = models.FloatField(null=True, blank=True, help_text="Elevation above sea level in meters")
    
    # Technical specifications
    primary_voltage_kv = models.FloatField(help_text="Primary voltage level in kV")
    secondary_voltage_kv = models.FloatField(null=True, blank=True, help_text="Secondary voltage level in kV")
    voltage_class = models.CharField(max_length=20, choices=VOLTAGE_CLASSES, default='high')
    
    # Capacity and ratings
    transformer_capacity_mva = models.FloatField(null=True, blank=True, help_text="Total transformer capacity in MVA")
    short_circuit_capacity_mva = models.FloatField(null=True, blank=True, help_text="Short circuit capacity in MVA")
    bay_count = models.IntegerField(null=True, blank=True, help_text="Number of bays/feeders")
    
    # Operational data
    commissioned_date = models.DateField(null=True, blank=True)
    decommissioned_date = models.DateField(null=True, blank=True)
    active = models.BooleanField(default=True)
    
    # Ownership and maintenance
    owner = models.CharField(max_length=100, blank=True, null=True)
    operator = models.CharField(max_length=100, blank=True, null=True)
    maintenance_zone = models.CharField(max_length=50, blank=True, null=True)
    
    # Additional attributes
    description = models.TextField(blank=True, null=True)
    control_center = models.CharField(max_length=100, blank=True, null=True)
    scada_id = models.CharField(max_length=50, blank=True, null=True, help_text="SCADA system identifier")
    
    # Metadata
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'Terminals'
        ordering = ['terminal_name']
        verbose_name = 'Terminal'
        verbose_name_plural = 'Terminals'
    
    def __str__(self):
        return f"{self.terminal_name} ({self.primary_voltage_kv}kV)"
    
    def get_connected_grid_lines(self):
        """Get all grid lines connected to this terminal"""
        return GridLines.objects.filter(
            models.Q(from_terminal=self) | models.Q(to_terminal=self),
            active=True
        )
    
    def get_outgoing_lines(self):
        """Get grid lines originating from this terminal"""
        return self.outgoing_lines.filter(active=True)
    
    def get_incoming_lines(self):
        """Get grid lines terminating at this terminal"""
        return self.incoming_lines.filter(active=True)
    
    def get_connected_facilities_count(self):
        """Count facilities connected through grid lines from this terminal"""
        connected_lines = self.get_connected_grid_lines()
        facility_count = 0
        for line in connected_lines:
            facility_count += line.connected_facilities.count()
        return facility_count
    
    def calculate_total_connected_capacity(self):
        """Calculate total capacity of facilities connected through this terminal"""
        connected_lines = self.get_connected_grid_lines()
        total_capacity = 0
        for line in connected_lines:
            for facility in line.connected_facilities.all():
                if facility.capacity:
                    total_capacity += facility.capacity
        return total_capacity
    
    def get_utilization_percent(self):
        """Get utilization as percentage of transformer capacity"""
        if not self.transformer_capacity_mva:
            return 0
        connected_capacity = self.calculate_total_connected_capacity()
        # Convert MW to MVA (assuming power factor of 0.95)
        connected_mva = connected_capacity / 0.95
        return (connected_mva / self.transformer_capacity_mva) * 100 if self.transformer_capacity_mva > 0 else 0
    
    def get_terminal_icon_type(self):
        """Get icon type based on terminal characteristics"""
        if self.primary_voltage_kv >= 330:
            return 'terminal_extra_high'
        elif self.primary_voltage_kv >= 132:
            return 'terminal_high'
        elif self.primary_voltage_kv >= 66:
            return 'terminal_medium'
        else:
            return 'terminal_low'
    
    def get_popup_content(self):
        """Get HTML content for map popup"""
        utilization = self.get_utilization_percent()
        connected_lines = self.get_connected_grid_lines().count()
        connected_facilities = self.get_connected_facilities_count()
        
        return f"""
        <div class="terminal-popup">
            <h4>{self.terminal_name}</h4>
            <table style="font-size: 12px;">
                <tr><td><strong>Code:</strong></td><td>{self.terminal_code}</td></tr>
                <tr><td><strong>Type:</strong></td><td>{self.get_terminal_type_display()}</td></tr>
                <tr><td><strong>Primary Voltage:</strong></td><td>{self.primary_voltage_kv} kV</td></tr>
                {f'<tr><td><strong>Secondary Voltage:</strong></td><td>{self.secondary_voltage_kv} kV</td></tr>' if self.secondary_voltage_kv else ''}
                {f'<tr><td><strong>Transformer Capacity:</strong></td><td>{self.transformer_capacity_mva} MVA</td></tr>' if self.transformer_capacity_mva else ''}
                <tr><td><strong>Connected Lines:</strong></td><td>{connected_lines}</td></tr>
                <tr><td><strong>Connected Facilities:</strong></td><td>{connected_facilities}</td></tr>
                <tr><td><strong>Utilization:</strong></td><td>{utilization:.1f}%</td></tr>
                <tr><td><strong>Status:</strong></td><td>{'Active' if self.active else 'Inactive'}</td></tr>
                {f'<tr><td><strong>Owner:</strong></td><td>{self.owner}</td></tr>' if self.owner else ''}
            </table>
        </div>
        """
    
    def validate_voltage_levels(self):
        """Validate that voltage levels are consistent"""
        if self.secondary_voltage_kv and self.secondary_voltage_kv >= self.primary_voltage_kv:
            raise ValidationError("Secondary voltage must be less than primary voltage")
    
    def clean(self):
        """Custom validation"""
        super().clean()
        self.validate_voltage_levels()
        
        if self.commissioned_date and self.decommissioned_date:
            if self.decommissioned_date <= self.commissioned_date:
                raise ValidationError("Decommission date must be after commission date")

class WholesalePrice(models.Model):
    """Store AEMO Interval wholesale prices """
    trading_date = models.DateField(db_index=True)
    interval_number = models.IntegerField()
    trading_interval = models.DateTimeField(db_index=True)
    wholesale_price = models.FloatField()
    extracted_at = models.DateTimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        db_table = 'WholesalePrice'
        unique_together = ['trading_date', 'interval_number']
        indexes = [
            models.Index(fields=['trading_date', 'interval_number']),
            models.Index(fields=['trading_interval']),
        ]
        ordering = ['-trading_date', 'interval_number']
    
    def __str__(self):
        return f"Wolesale Price {self.trading_date} #{self.interval_number}: {self.wholesale_price}$/MW"

class variations(models.Model):
    idvariations = models.AutoField(db_column='idvariations', primary_key=True)  
    idscenarios = models.ForeignKey('Scenarios', models.CASCADE, db_column='idScenarios', null=True)
    idtechnologies = models.ForeignKey('Technologies', models.RESTRICT, db_column='idTechnologies')
    variation_name = models.CharField(max_length=45, blank=True, null=True)
    variation_description = models.CharField(max_length=250, blank=True, null=True)
    dimension = models.CharField(max_length=30, blank=True, null=True)
    startval = models.FloatField(null=True)  
    step = models.FloatField(null=True)
    stages = models.IntegerField(blank=True, null=True)
    endval = models.FloatField(null=True)  

    class Meta:
        db_table = 'variations'
        
class Zones(models.Model):
    idzones = models.PositiveIntegerField(db_column='idZones', primary_key=True)  
    name = models.CharField(unique=True, max_length=45, db_collation='utf8mb4_0900_ai_ci', blank=True, null=True)
    description = models.CharField(max_length=500, db_collation='utf8mb4_0900_ai_ci', blank=True, null=True)

    class Meta:
        db_table = 'Zones'

class AuthGroup(models.Model):
    name = models.CharField(unique=True, max_length=150)

    class Meta:
        managed = False
        db_table = 'auth_group'

class AuthGroupPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    group_id = models.IntegerField()
    permission_id = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'auth_group_permissions'
        unique_together = (('group_id', 'permission_id'),)

class AuthPermission(models.Model):
    name = models.CharField(max_length=255)
    content_type_id = models.IntegerField()
    codename = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'auth_permission'
        unique_together = (('content_type_id', 'codename'),)

class AuthUser(models.Model):
    password = models.CharField(max_length=128)
    last_login = models.DateTimeField(blank=True, null=True)
    is_superuser = models.IntegerField()
    username = models.CharField(unique=True, max_length=150)
    first_name = models.CharField(max_length=150)
    last_name = models.CharField(max_length=150)
    email = models.CharField(max_length=254)
    is_staff = models.IntegerField()
    is_active = models.IntegerField()
    date_joined = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'auth_user'

class AuthUserGroups(models.Model):
    id = models.BigAutoField(primary_key=True)
    user_id = models.IntegerField()
    group_id = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'auth_user_groups'
        unique_together = (('user_id', 'group_id'),)

class AuthUserUserPermissions(models.Model):
    id = models.BigAutoField(primary_key=True)
    user_id = models.IntegerField()
    permission_id = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'auth_user_user_permissions'
        unique_together = (('user_id', 'permission_id'),)

class DjangoAdminLog(models.Model):
    action_time = models.DateTimeField()
    object_id = models.TextField(blank=True, null=True)
    object_repr = models.CharField(max_length=200)
    action_flag = models.PositiveSmallIntegerField()
    change_message = models.TextField()
    content_type_id = models.IntegerField(blank=True, null=True)
    user_id = models.IntegerField()

    class Meta:
        managed = False
        db_table = 'django_admin_log'

class DjangoContentType(models.Model):
    app_label = models.CharField(max_length=100)
    model = models.CharField(max_length=100)

    class Meta:
        managed = False
        db_table = 'django_content_type'
        unique_together = (('app_label', 'model'),)

# ============================================================================
# DEMAND PROJECTION MODELS
# ============================================================================

class DemandFactorType(models.Model):
    """
    Defines a type of demand growth factor (e.g., EV Adoption, Industrial Electrification).
    These are the categories of demand drivers that can be modeled.
    """
    iddemandfactortype = models.AutoField(db_column='iddemandfactortype', primary_key=True)
    name = models.CharField(max_length=100, unique=True, help_text="Factor name (e.g., 'EV Adoption')")
    description = models.TextField(blank=True, help_text="Detailed description of this demand factor")

    CATEGORY_CHOICES = [
        ('operational', 'Operational Demand Only'),
        ('underlying', 'Underlying Demand Only'),
        ('both', 'Both Operational and Underlying'),
    ]
    category = models.CharField(
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='both',
        help_text="Which demand type this factor applies to"
    )

    is_system_default = models.BooleanField(
        default=False,
        help_text="True if this is a system-provided factor type"
    )
    display_order = models.IntegerField(
        default=0,
        help_text="Order for displaying in UI (lower numbers first)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'demandfactortype'
        ordering = ['display_order', 'name']
        verbose_name = 'Demand Factor Type'
        verbose_name_plural = 'Demand Factor Types'

    def __str__(self):
        return self.name


class DemandFactor(models.Model):
    """
    Specific instance of a demand factor with growth parameters.
    Each factor represents a portion of base demand that grows independently.
    Multiple factors can be assigned to a scenario.
    """
    iddemandfactor = models.AutoField(db_column='iddemandfactor', primary_key=True)

    factor_type = models.ForeignKey(
        DemandFactorType,
        on_delete=models.CASCADE,
        db_column='iddemandfactortype',
        related_name='factor_instances',
        help_text="The type of demand factor"
    )

    scenario = models.ForeignKey(
        'Scenarios',
        on_delete=models.CASCADE,
        db_column='idscenarios',
        null=True,
        blank=True,
        related_name='demand_factors',
        help_text="Scenario this factor belongs to (null = default/template)"
    )

    # Base year configuration
    base_year = models.IntegerField(
        default=2024,
        help_text="Starting year for projections"
    )

    base_percentage_operational = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Percentage of total operational demand in base year (0-100)"
    )

    base_percentage_underlying = models.FloatField(
        default=0.0,
        validators=[MinValueValidator(0.0), MaxValueValidator(100.0)],
        help_text="Percentage of total underlying demand in base year (0-100)"
    )

    # Growth configuration
    GROWTH_TYPE_CHOICES = [
        ('linear', 'Linear Growth'),
        ('exponential', 'Exponential Growth'),
        ('s_curve', 'S-Curve (Logistic)'),
        ('compound', 'Compound Annual Growth'),
    ]

    growth_rate = models.FloatField(
        default=0.02,
        validators=[MinValueValidator(-1.0), MaxValueValidator(10.0)],
        help_text="Annual growth rate (e.g., 0.03 for 3% growth)"
    )

    growth_type = models.CharField(
        max_length=20,
        choices=GROWTH_TYPE_CHOICES,
        default='exponential',
        help_text="Mathematical model for growth"
    )

    # S-curve specific parameters
    saturation_multiplier = models.FloatField(
        default=2.0,
        validators=[MinValueValidator(1.0), MaxValueValidator(10.0)],
        help_text="Maximum growth multiplier for S-curve (e.g., 2.0 = doubles at saturation)"
    )

    midpoint_year = models.IntegerField(
        default=2035,
        help_text="Year where S-curve reaches 50% of saturation"
    )

    # Advanced: Time-varying growth rates
    time_varying_config = models.JSONField(
        null=True,
        blank=True,
        help_text='Time-varying rates as JSON: {"2025": 0.03, "2030": 0.05}. Year keys must be strings.'
    )

    # Status
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this factor is included in projections"
    )

    # Metadata
    notes = models.TextField(
        blank=True,
        help_text="Additional notes about this factor configuration"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'demandfactor'
        ordering = ['scenario', 'factor_type__display_order', 'factor_type__name']
        verbose_name = 'Demand Factor'
        verbose_name_plural = 'Demand Factors'
        unique_together = [['scenario', 'factor_type']]

    def __str__(self):
        scenario_name = self.scenario.title if self.scenario else "Default"
        return f"{self.factor_type.name} ({scenario_name})"

    def get_growth_rate_for_year(self, year):
        """
        Get the growth rate for a specific year.
        Supports time-varying rates via JSON config.

        Args:
            year: Target year (int)

        Returns:
            float: Growth rate for that year
        """
        if self.time_varying_config:
            # Find the most recent year <= target year in config
            years = sorted([int(y) for y in self.time_varying_config.keys()])
            applicable_years = [y for y in years if y <= year]

            if applicable_years:
                most_recent_year = max(applicable_years)
                return float(self.time_varying_config[str(most_recent_year)])

        # Fall back to fixed growth rate
        return self.growth_rate

    def validate_percentages(self):
        """
        Validate that this factor's percentages are reasonable.
        Note: Total across all factors in a scenario should sum to ~100%,
        but that's validated at the scenario level.
        """
        if self.base_percentage_operational < 0 or self.base_percentage_operational > 100:
            raise ValidationError("Operational percentage must be between 0 and 100")
        if self.base_percentage_underlying < 0 or self.base_percentage_underlying > 100:
            raise ValidationError("Underlying percentage must be between 0 and 100")

    def clean(self):
        """Django model validation"""
        super().clean()
        self.validate_percentages()


class DemandProjectionScenario(models.Model):
    """
    Enhanced scenario model specifically for demand projections.
    Links to Scenarios model for integration with existing system.
    """
    iddemandprojectionscenario = models.AutoField(db_column='iddemandprojectionscenario', primary_key=True)

    scenario = models.OneToOneField(
        'Scenarios',
        on_delete=models.CASCADE,
        db_column='idscenarios',
        related_name='demand_projection_config',
        help_text="Link to main scenario"
    )

    base_year = models.IntegerField(
        default=2024,
        help_text="Base year for demand projections"
    )

    projection_end_year = models.IntegerField(
        default=2050,
        help_text="Final year of projection"
    )

    # Factor-based projection settings
    use_factor_breakdown = models.BooleanField(
        default=True,
        help_text="Use factor-based projections (vs legacy simple rates)"
    )

    # Legacy compatibility - simple growth rates (deprecated)
    simple_operational_rate = models.FloatField(
        null=True,
        blank=True,
        help_text="DEPRECATED: Simple operational growth rate (use factors instead)"
    )

    simple_underlying_rate = models.FloatField(
        null=True,
        blank=True,
        help_text="DEPRECATED: Simple underlying growth rate (use factors instead)"
    )

    # Validation and quality checks
    require_100_percent = models.BooleanField(
        default=False,
        help_text="Require factor percentages to sum to exactly 100%"
    )

    # Metadata
    description = models.TextField(
        blank=True,
        help_text="Description of this projection configuration"
    )

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'demandprojectionscenario'
        ordering = ['-created_at']
        verbose_name = 'Demand Projection Scenario'
        verbose_name_plural = 'Demand Projection Scenarios'

    def __str__(self):
        return f"Projection Config: {self.scenario.title}"

    def get_total_operational_percentage(self):
        """Calculate total % of operational demand covered by factors"""
        factors = self.scenario.demand_factors.filter(is_active=True)
        return sum(f.base_percentage_operational for f in factors)

    def get_total_underlying_percentage(self):
        """Calculate total % of underlying demand covered by factors"""
        factors = self.scenario.demand_factors.filter(is_active=True)
        return sum(f.base_percentage_underlying for f in factors)

    def validate_factor_percentages(self):
        """Validate that factor percentages sum appropriately"""
        operational_total = self.get_total_operational_percentage()
        underlying_total = self.get_total_underlying_percentage()

        if self.require_100_percent:
            if abs(operational_total - 100.0) > 0.01:
                raise ValidationError(
                    f"Operational factor percentages must sum to 100% (currently {operational_total:.1f}%)"
                )
            if abs(underlying_total - 100.0) > 0.01:
                raise ValidationError(
                    f"Underlying factor percentages must sum to 100% (currently {underlying_total:.1f}%)"
                )

        # Warn if significantly over 100%
        if operational_total > 105.0 or underlying_total > 105.0:
            raise ValidationError(
                f"Factor percentages exceed 100% (Operational: {operational_total:.1f}%, "
                f"Underlying: {underlying_total:.1f}%)"
            )

    def clean(self):
        """Django model validation"""
        super().clean()
        if self.use_factor_breakdown:
            self.validate_factor_percentages()


class MonteCarloSimulation(models.Model):
    """
    Track Monte Carlo simulation runs for renewable energy target probability analysis.
    Each simulation calculates probability of achieving targets by 2040.
    """
    # Run identification
    simulation_id = models.AutoField(primary_key=True)
    run_date = models.DateTimeField(auto_now_add=True, db_index=True)

    # Scenario linkage
    target_scenario = models.ForeignKey(
        'TargetScenario',
        on_delete=models.CASCADE,
        related_name='monte_carlo_runs',
        help_text="Scenario this simulation evaluates"
    )

    # Simulation parameters
    num_iterations = models.IntegerField(
        default=100000,
        help_text="Number of Monte Carlo iterations"
    )
    target_year = models.IntegerField(
        default=2040,
        help_text="Year to project to"
    )

    # Probability levels used
    probability_profile = models.CharField(
        max_length=20,
        choices=[
            ('optimistic', 'Optimistic'),
            ('balanced', 'Balanced'),
            ('conservative', 'Conservative'),
        ],
        default='optimistic',
        help_text="Commissioning probability profile"
    )

    # Results summary
    mean_re_percentage = models.FloatField(
        null=True,
        help_text="Mean RE% across all iterations"
    )
    median_re_percentage = models.FloatField(
        null=True,
        help_text="Median RE% (50th percentile)"
    )
    p10_re_percentage = models.FloatField(
        null=True,
        help_text="P10 RE% (pessimistic - 10th percentile)"
    )
    p90_re_percentage = models.FloatField(
        null=True,
        help_text="P90 RE% (optimistic - 90th percentile)"
    )
    std_dev_re_percentage = models.FloatField(
        null=True,
        help_text="Standard deviation of RE%"
    )

    # Target achievement probabilities
    probability_75_percent = models.FloatField(
        null=True,
        help_text="Probability of achieving 75% RE target"
    )
    probability_85_percent = models.FloatField(
        null=True,
        help_text="Probability of achieving 85% RE target"
    )

    # Execution metadata
    execution_time_seconds = models.FloatField(
        null=True,
        help_text="Total execution time in seconds"
    )
    status = models.CharField(
        max_length=20,
        choices=[
            ('pending', 'Pending'),
            ('running', 'Running'),
            ('completed', 'Completed'),
            ('failed', 'Failed'),
        ],
        default='pending',
        db_index=True
    )
    error_message = models.TextField(
        null=True,
        blank=True,
        help_text="Error details if failed"
    )

    # Audit fields
    created_by = models.CharField(
        max_length=100,
        default='system',
        help_text="User or system that triggered run"
    )
    notes = models.TextField(
        blank=True,
        null=True
    )

    class Meta:
        db_table = 'monte_carlo_simulations'
        ordering = ['-run_date']
        indexes = [
            models.Index(fields=['-run_date', 'status']),
            models.Index(fields=['target_scenario', '-run_date']),
        ]

    def __str__(self):
        return f"MC Run {self.simulation_id}: {self.target_scenario.scenario_name} ({self.run_date.strftime('%Y-%m-%d')})"

    @property
    def confidence_interval_90(self):
        """Return 90% confidence interval (P10 to P90)"""
        if self.p10_re_percentage and self.p90_re_percentage:
            return (self.p10_re_percentage, self.p90_re_percentage)
        return None


class MonteCarloParameter(models.Model):
    """
    Store input parameters and assumptions for each Monte Carlo simulation run.
    Tracks what assumptions were used for reproducibility and auditing.
    """
    parameter_id = models.AutoField(primary_key=True)
    simulation = models.ForeignKey(
        'MonteCarloSimulation',
        on_delete=models.CASCADE,
        related_name='parameters'
    )

    # Parameter identification
    parameter_category = models.CharField(
        max_length=50,
        choices=[
            ('commissioning_probability', 'Commissioning Probability'),
            ('delay_distribution', 'Delay Distribution'),
            ('capacity_factor', 'Capacity Factor'),
            ('demand_growth', 'Demand Growth'),
            ('general', 'General'),
        ],
        db_index=True
    )
    parameter_name = models.CharField(
        max_length=100,
        help_text="e.g., 'commissioned_probability', 'wind_cf_mean'"
    )

    # Parameter values (stored as JSON for flexibility)
    parameter_value = models.JSONField(
        help_text="Parameter value (can be scalar, array, or object)"
    )

    # Metadata
    description = models.CharField(
        max_length=500,
        blank=True,
        null=True
    )
    source = models.CharField(
        max_length=200,
        blank=True,
        null=True,
        help_text="Data source or methodology"
    )

    class Meta:
        db_table = 'monte_carlo_parameters'
        unique_together = ['simulation', 'parameter_name']
        indexes = [
            models.Index(fields=['simulation', 'parameter_category']),
        ]

    def __str__(self):
        return f"{self.parameter_name}: {self.parameter_value}"


class MonteCarloResult(models.Model):
    """
    Store detailed distribution results from Monte Carlo simulation.
    Stores histogram bins and percentile data for visualization.
    """
    result_id = models.AutoField(primary_key=True)
    simulation = models.OneToOneField(
        'MonteCarloSimulation',
        on_delete=models.CASCADE,
        related_name='detailed_results'
    )

    # Distribution data (stored as JSON)
    re_percentage_distribution = models.JSONField(
        help_text="Histogram of RE% results: {bins: [...], counts: [...]}"
    )

    # Percentile data for plotting
    percentiles = models.JSONField(
        help_text="Percentile values: {p1: X, p5: Y, p10: Z, ..., p99: W}"
    )

    # Component contributions (mean across iterations)
    mean_wind_generation_2040 = models.FloatField(null=True)
    mean_solar_generation_2040 = models.FloatField(null=True)
    mean_dpv_generation_2040 = models.FloatField(null=True)
    mean_biomass_generation_2040 = models.FloatField(null=True)
    mean_total_demand_2040 = models.FloatField(null=True)

    # Uncertainty contributions (variance decomposition)
    variance_contribution = models.JSONField(
        null=True,
        blank=True,
        help_text="Variance contribution by factor: {commissioning: 0.4, cf: 0.3, demand: 0.2, delay: 0.1}"
    )

    # Raw iteration results (sample for debugging - store first 1000)
    sample_iterations = models.JSONField(
        null=True,
        blank=True,
        help_text="First 1000 iteration results for debugging"
    )

    class Meta:
        db_table = 'monte_carlo_results'

    def __str__(self):
        return f"Results for {self.simulation}"


class DjangoMigrations(models.Model):
    id = models.BigAutoField(primary_key=True)
    app = models.CharField(max_length=255)
    name = models.CharField(max_length=255)
    applied = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_migrations'

class DjangoSession(models.Model):
    session_key = models.CharField(primary_key=True, max_length=40)
    session_data = models.TextField()
    expire_date = models.DateTimeField()

    class Meta:
        managed = False
        db_table = 'django_session'
