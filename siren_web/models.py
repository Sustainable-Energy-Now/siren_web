# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


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
        
class capacities(models.Model):
    idcapacities = models.AutoField(db_column='idcapacities', primary_key=True)  
    idfacilities = models.ForeignKey('facilities', models.RESTRICT, db_column='idfacilities', blank=True, null=True)  
    year = models.PositiveIntegerField()
    hour = models.IntegerField(blank=True, null=True)
    quantum = models.FloatField(null=True) 

    class Meta:
        db_table = 'capacities'
        
class Demand(models.Model):
    iddemand = models.AutoField(db_column='idDemand', primary_key=True)
    idtechnologies = models.ForeignKey('Technologies', on_delete=models.CASCADE, db_column='idTechnologies')  
    idscenarios = models.ForeignKey('Scenarios', on_delete=models.CASCADE, db_column='idScenarios')
    year = models.PositiveIntegerField()
    hour = models.PositiveIntegerField()
    period = models.DateTimeField(blank=True, null=True)
    load = models.DecimalField(max_digits=9, decimal_places=2, blank=True, null=True)
    col = models.PositiveIntegerField(db_column='Col', blank=True, null=True)  

    class Meta:
        db_table = 'Demand'
        
class Scenarios(models.Model):
    idscenarios = models.AutoField(db_column='idScenarios', primary_key=True)  
    title = models.CharField(db_column='Title', unique=True, max_length=45, blank=True, null=True)  
    dateexported = models.DateField(db_column='DateExported', blank=True, null=True)  
    description = models.CharField(db_column='Description', max_length=500, blank=True, null=True)  

    class Meta:
        db_table = 'Scenarios'

class facilities(models.Model):
    idfacilities = models.AutoField(db_column='idfacilities', primary_key=True)
    facility_name = models.CharField(db_column='facility_name', unique=True, max_length=45, blank=True, null=True)
    facility_code = models.CharField(db_column='facility_code', unique=True, max_length=30, blank=True, null=True)
    participant_code = models.CharField(max_length=45, blank=True, null=True)
    registered_from = models.DateField(null=True)
    active = models.BooleanField(null=False)
    existing = models.BooleanField(null=False)
    idtechnologies = models.ForeignKey('Technologies', models.DO_NOTHING, db_column='idtechnologies')
    scenarios = models.ManyToManyField(Scenarios, through='ScenariosFacilities', blank=True)
    idzones = models.ForeignKey('Zones', models.DO_NOTHING, db_column='idzones', blank=True, null=True)
    capacity = models.FloatField(null=True)
    capacityfactor = models.FloatField(null=True)
    generation = models.FloatField(null=True)
    transmitted = models.FloatField(null=True)
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    turbine = models.CharField(db_column='turbine', max_length=70, blank=True, null=True)
    hub_height = models.FloatField(blank=True, null=True)
    no_turbines = models.IntegerField(null=True)
    tilt = models.IntegerField(null=True)
    storage_hours = models.FloatField(blank=True, null=True)
    power_file = models.CharField( max_length=45, blank=True, null=True)
    direction = models.CharField( max_length=28, blank=True, null=True)
    grid_connections = models.ManyToManyField('GridLines', through='FacilityGridConnections', 
                                            blank=True, related_name='connected_facilities')
    primary_grid_line = models.ForeignKey('GridLines', on_delete=models.SET_NULL, 
                                        null=True, blank=True, related_name='primary_facilities')

    class Meta:
        db_table = 'facilities'
    
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
        
        # Distribute power across connections (simplified - equal distribution)
        if connections:
            power_per_connection = power_output_mw / len(connections)
            
            for connection in connections:
                # Connection losses (facility to grid line)
                connection_losses = connection.calculate_connection_losses_mw(power_per_connection)
                
                # Grid line losses (simplified)
                grid_line_losses = connection.idgridlines.calculate_line_losses_mw(power_per_connection)
                
                total_losses += connection_losses + grid_line_losses
        
        return total_losses

class Generatorattributes(models.Model):
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
    
    # Additional attributes
    active = models.BooleanField(default=True)
    commissioned_date = models.DateField(null=True, blank=True)
    decommissioned_date = models.DateField(null=True, blank=True)
    owner = models.CharField(max_length=100, blank=True, null=True)
    
    # Text field to store KML geometry data as string
    kml_geometry = models.TextField(null=True, blank=True, help_text="KML geometry data (stored as text)")
    
    created_date = models.DateTimeField(auto_now_add=True)
    modified_date = models.DateTimeField(auto_now=True)
    
    class Meta:
        db_table = 'GridLines'
        ordering = ['line_name']
    
    def __str__(self):
        return f"{self.line_name} ({self.voltage_level}kV)"
    
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
    
class Storageattributes(models.Model):
    idstorageattributes = models.AutoField(db_column='idStorageAttributes', primary_key=True)  
    idtechnologies = models.ForeignKey('Technologies', models.CASCADE, db_column='idTechnologies', blank=True, null=True)  
    discharge_loss = models.IntegerField(blank=True, null=True)
    discharge_max = models.FloatField(null=True)
    parasitic_loss = models.IntegerField(blank=True, null=True)
    recharge_loss = models.IntegerField(blank=True, null=True)
    recharge_max = models.FloatField(null=True)
    class Meta:
        db_table = 'StorageAttributes'
               
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
    idtechnologies = models.AutoField(db_column='idTechnologies', primary_key=True)  
    technology_name = models.CharField(unique=True, max_length=45)
    technology_signature = models.CharField(unique=True, max_length=20)
    scenarios = models.ManyToManyField(Scenarios, through='ScenariosTechnologies', blank=True)
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

    class Meta:
        db_table = 'Technologies'

class TechnologyYears(models.Model):
    idtechnologyyears = models.AutoField(primary_key=True)
    idtechnologies = models.ForeignKey('Technologies', on_delete=models.RESTRICT)
    year = models.IntegerField(default=0, null=True)
    capex = models.FloatField(null=True)
    fom = models.FloatField(db_column='FOM', null=True)  
    vom = models.FloatField(db_column='VOM', null=True)  
    fuel = models.FloatField(null=True)

    class Meta:
        db_table = 'TechnologyYears'

class TradingPrice(models.Model):
    id = models.AutoField(db_column='idTechnologies', primary_key=True)
    trading_month = models.CharField(max_length=7, blank=True, null=True)
    trading_interval = models.IntegerField(blank=True, null=True)
    reference_price = models.FloatField()

    class Meta:
        db_table = 'tradingprice'

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
