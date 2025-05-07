from django.db import models

class Scenarios(models.Model):
    idscenarios = models.AutoField(db_column='idScenarios', primary_key=True)  
    title = models.CharField(db_column='Title', max_length=45, blank=True, null=True)  
    dateexported = models.DateField(db_column='DateExported', blank=True, null=True)  
    description = models.CharField(db_column='Description', max_length=500, blank=True, null=True)  

    class Meta:
        db_table = 'Scenarios'
        
class facilities(models.Model):
    idfacilities = models.AutoField(db_column='idfacilities', primary_key=True)
    facility_name = models.CharField(db_column='facility_name', max_length=45, blank=True, null=True)
    facility_code = models.CharField(db_column='facility_code', max_length=20, blank=True, null=True)
    participant_code = models.CharField(max_length=45, blank=True, null=True)
    registered_from = models.DateField(null=True)
    active = models.BooleanField(null=False)
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
    grid_line = models.CharField( max_length=45, blank=True, null=True)
    direction = models.CharField( max_length=20, blank=True, null=True)

    class Meta:
        db_table = 'facilities'
 
class Generatorattributes(models.Model):
    idgeneratorattributes = models.AutoField(db_column='idGeneratorAttributes', primary_key=True)  
    idtechnologies = models.ForeignKey('Technologies', models.CASCADE, db_column='idTechnologies')  
    year = models.IntegerField()
    fuel = models.FloatField(null=True)
    generated = models.FloatField(null=True)
    area = models.FloatField(null=True)

    class Meta:
        db_table = 'GeneratorAttributes'

class ScenariosFacilities(models.Model):
    idscenariosfacilities = models.AutoField(primary_key=True)  
    idscenarios = models.ForeignKey('Scenarios', on_delete=models.RESTRICT, db_column='idScenarios')
    idfacilities = models.ForeignKey('facilities', on_delete=models.RESTRICT, db_column='idfacilities')

    class Meta:
        db_table = 'ScenariosFacilities'
        
class ScenariosTechnologies(models.Model):
    idscenariostechnologies = models.AutoField(primary_key=True)  
    idscenarios = models.ForeignKey('Scenarios', on_delete=models.RESTRICT)
    idtechnologies = models.ForeignKey('Technologies', on_delete=models.RESTRICT)
    merit_order = models.IntegerField(null=True)

    class Meta:
        db_table = 'ScenariosTechnologies'
        
class Storageattributes(models.Model):
    idstorageattributes = models.AutoField(db_column='idStorageAttributes', primary_key=True)  
    idtechnologies = models.ForeignKey('Technologies', models.CASCADE, db_column='idTechnologies', blank=True, null=True)  
    year = models.IntegerField()
    discharge_loss = models.IntegerField(blank=True, null=True)
    discharge_max = models.FloatField(null=True)
    parasitic_loss = models.IntegerField(blank=True, null=True)
    rampdown_max = models.IntegerField(blank=True, null=True)
    rampup_max = models.IntegerField(blank=True, null=True)
    recharge_loss = models.IntegerField(blank=True, null=True)
    recharge_max = models.FloatField(null=True)
    min_runtime = models.FloatField(null=True)
    warm_time = models.FloatField( null=True)
    class Meta:
        db_table = 'StorageAttributes'
               
class Technologies(models.Model):
    idtechnologies = models.AutoField(db_column='idTechnologies', primary_key=True)  
    technology_name = models.CharField(max_length=45)
    technology_signature = models.CharField(max_length=20)
    year = models.IntegerField(default=0, null=True)
    scenarios = models.ManyToManyField(Scenarios, through='ScenariosTechnologies', blank=True)
    image = models.CharField(max_length=50, blank=True, null=True)
    caption = models.CharField(max_length=50, blank=True, null=True)
    category = models.CharField(max_length=45, blank=True, null=True)
    renewable = models.IntegerField(blank=True, null=True)
    dispatchable = models.IntegerField(blank=True, null=True)
    capex = models.FloatField(null=True)
    fom = models.FloatField(db_column='FOM', null=True)  
    vom = models.FloatField(db_column='VOM', null=True)  
    lifetime = models.FloatField(null=True)
    discount_rate = models.FloatField(null=True)
    description = models.CharField(max_length=1000, db_collation='utf8mb4_0900_ai_ci', blank=True, null=True)
    capacity = models.FloatField(null=True)
    capacity_factor = models.FloatField(null=True)
    mult = models.FloatField(null=True)
    approach = models.CharField(max_length=45, blank=True, null=True)
    capacity_max = models.FloatField(null=True)
    capacity_min = models.FloatField(null=True)
    capacity_step = models.FloatField(null=True)
    capacities = models.CharField(max_length=50, blank=True, null=True)
    emissions = models.FloatField(null=True)
    initial = models.FloatField(null=True)
    lcoe = models.FloatField(null=True)
    lcoe_cf = models.FloatField(null=True)
    area = models.FloatField(blank=True, null=True)

    class Meta:
        db_table = 'Technologies'
