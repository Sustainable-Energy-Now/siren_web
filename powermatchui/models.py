# This is an auto-generated Django model module.
# You'll have to do the following manually to clean this up:
#   * Rearrange models' order
#   * Make sure each model has one field with primary_key=True
#   * Make sure each ForeignKey and OneToOneField has `on_delete` set to the desired behavior
#   * Remove `managed = False` lines if you wish to allow Django to create, modify, and delete the table
# Feel free to rename the models, but don't rename db_table values or field names.
from django.db import models


class Analysis(models.Model):
    idanalysis = models.AutoField(db_column='idAnalysis', primary_key=True)  # Field name made lowercase.
    idscenarios = models.ForeignKey('Scenarios', models.DO_NOTHING, db_column='idScenarios', blank=True, null=True)  # Field name made lowercase.
    heading = models.CharField(db_column='Heading', max_length=45, blank=True, null=True)  # Field name made lowercase.
    basis = models.CharField(db_column='Basis', max_length=45, blank=True, null=True)  # Field name made lowercase.
    stage = models.CharField(db_column='Stage', max_length=45, blank=True, null=True)  # Field name made lowercase.
    quantity = models.FloatField(db_column='Quantity', blank=True, null=True)  # Field name made lowercase.
    units = models.CharField(db_column='Units', max_length=10, blank=True, null=True)  # Field name made lowercase.

    class Meta:
        db_table = 'Analysis'

class Demand(models.Model):
    iddemand = models.PositiveIntegerField(db_column='idDemand', primary_key=True)  # Field name made lowercase. The composite primary key (idDemand, idtechnologies, hour) found, that is not supported. The first column is selected.
    idtechnologies = models.ForeignKey('Technologies', models.DO_NOTHING, db_column='idTechnologies')  # Field name made lowercase.
    idscenarios = models.ForeignKey('Scenarios', models.DO_NOTHING, db_column='idScenarios')  # Field name made lowercase.
    hour = models.PositiveIntegerField()
    period = models.DateTimeField(blank=True, null=True)
    load = models.DecimalField(max_digits=9, decimal_places=2, blank=True, null=True)
    col = models.PositiveIntegerField(db_column='Col', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        db_table = 'Demand'
        
class facilities(models.Model):
    idfacilities = models.PositiveIntegerField(db_column='idfacilities', primary_key=True)  # Field name made lowercase. 
    facility_name = models.CharField(db_column='facility_name', max_length=45, blank=True, null=True)  # Field name made lowercase.
    idtechnologies = models.ForeignKey('Technologies', models.DO_NOTHING, db_column='idtechnologies')  # Field name made lowercase.
    idzones = models.ForeignKey('Zones', models.DO_NOTHING, db_column='idzones', blank=True, null=True)  # Field name made lowercase.
    capacity = models.DecimalField(db_column='capacity', max_digits=7, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    capacityfactor = models.DecimalField(db_column='capacityfactor', max_digits=5, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    generation = models.DecimalField(db_column='generation', max_digits=9, decimal_places=0, blank=True, null=True)  # Field name made lowercase.
    transmitted = models.DecimalField(db_column='transmitted', max_digits=9, decimal_places=0, blank=True, null=True)  # Field name made lowercase.
    latitude = models.FloatField(blank=True, null=True)
    longitude = models.FloatField(blank=True, null=True)
    
    class Meta:
        db_table = 'facilities'

class Generators(models.Model):
    id = models.PositiveIntegerField(db_column='ID', primary_key=True)  # Field name made lowercase. The composite primary key (ID, Year) found, that is not supported. The first column is selected.
    year = models.IntegerField(db_column='Year')  # Field name made lowercase.
    name = models.CharField(db_column='Name', max_length=45, blank=True, null=True)  # Field name made lowercase.
    image = models.CharField(db_column='Image', max_length=65, blank=True, null=True)  # Field name made lowercase.
    capacity = models.DecimalField(db_column='Capacity', max_digits=7, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    emissions = models.DecimalField(db_column='Emissions', max_digits=5, decimal_places=3, blank=True, null=True)  # Field name made lowercase.
    initial = models.DecimalField(db_column='Initial', max_digits=5, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    ord = models.IntegerField(db_column='Ord', blank=True, null=True)  # Field name made lowercase.
    dispatchable = models.IntegerField(db_column='Dispatchable', blank=True, null=True)  # Field name made lowercase.
    mult = models.FloatField(blank=True, null=True)
    capex = models.DecimalField(db_column='Capex', max_digits=9, decimal_places=0, blank=True, null=True)  # Field name made lowercase.
    fom = models.DecimalField(db_column='FOM', max_digits=9, decimal_places=0, blank=True, null=True)  # Field name made lowercase.
    vom = models.DecimalField(db_column='VOM', max_digits=5, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    fuel = models.DecimalField(db_column='Fuel', max_digits=5, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    lifetime = models.DecimalField(db_column='Lifetime', max_digits=3, decimal_places=0, blank=True, null=True)  # Field name made lowercase.
    discountrate = models.DecimalField(db_column='DiscountRate', max_digits=5, decimal_places=2, blank=True, null=True)  # Field name made lowercase.

    class Meta:
        db_table = 'generators'
        unique_together = (('id', 'year'),)
        
class Generatorattributes(models.Model):
    idgeneratorattributes = models.AutoField(db_column='idGeneratorAttributes', primary_key=True)  # Field name made lowercase.
    idtechnologies = models.ForeignKey('Technologies', models.DO_NOTHING, db_column='idTechnologies')  # Field name made lowercase.
    year = models.IntegerField()
    fuel = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)

    class Meta:
        db_table = 'GeneratorAttributes'

class Genetics(models.Model):
    idgenetics = models.PositiveIntegerField(db_column='idGenetics', primary_key=True)  # Field name made lowercase.
    parameter = models.CharField(db_column='Parameter', max_length=30, blank=True, null=True)  # Field name made lowercase.
    weight = models.DecimalField(db_column='Weight', max_digits=5, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    better = models.DecimalField(db_column='Better', max_digits=5, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    worse = models.DecimalField(db_column='Worse', max_digits=13, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    minvalue = models.DecimalField(db_column='MinValue', max_digits=5, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    maxvalue = models.DecimalField(db_column='MaxValue', max_digits=5, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    step = models.DecimalField(db_column='Step', max_digits=5, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    betterspinner = models.IntegerField(db_column='BetterSpinner', blank=True, null=True)  # Field name made lowercase.
    worsespinner = models.IntegerField(db_column='WorseSpinner', blank=True, null=True)  # Field name made lowercase.

    class Meta:
        db_table = 'Genetics'
        db_table_comment = 'Parameters used for genetic optimisation'
        
class Optimisation(models.Model):
    idoptimisation = models.PositiveIntegerField(db_column='idOptimisation', primary_key=True)  # Field name made lowercase.
    name = models.CharField(db_column='Name', max_length=45, blank=True, null=True)  # Field name made lowercase.
    approach = models.CharField(db_column='Approach', max_length=45, blank=True, null=True)  # Field name made lowercase.
    capacity = models.DecimalField(db_column='Capacity', max_digits=7, decimal_places=1, blank=True, null=True)  # Field name made lowercase.
    capacitymax = models.DecimalField(db_column='CapacityMax', max_digits=7, decimal_places=1, blank=True, null=True)  # Field name made lowercase.
    capacitymin = models.DecimalField(db_column='CapacityMin', max_digits=7, decimal_places=1, blank=True, null=True)  # Field name made lowercase.
    capacitystep = models.DecimalField(db_column='CapacityStep', max_digits=7, decimal_places=1, blank=True, null=True)  # Field name made lowercase.

    class Meta:
        db_table = 'Optimisation'
        
class Scenarios(models.Model):
    idscenarios = models.AutoField(db_column='idScenarios', primary_key=True)  # Field name made lowercase.
    title = models.CharField(db_column='Title', max_length=45, blank=True, null=True)  # Field name made lowercase.
    dateexported = models.DateField(db_column='DateExported', blank=True, null=True)  # Field name made lowercase.
    description = models.CharField(db_column='Description', max_length=500, blank=True, null=True)  # Field name made lowercase.

    class Meta:
        db_table = 'Scenarios'

class Settings(models.Model):
    idsettings = models.PositiveIntegerField(db_column='idSettings', primary_key=True)  # Field name made lowercase.
    context = models.CharField(max_length=20, blank=True, null=True)
    parameter = models.CharField(max_length=45, blank=True, null=True)
    value = models.CharField(max_length=300, blank=True, null=True)

    class Meta:
        db_table = 'Settings'
        
class sirensystem(models.Model):
    name = models.CharField(max_length=30, primary_key=True)
    description = models.CharField(max_length=500, blank=True, null=True)
    
    class Meta:
        db_table = 'sirensystem'
    
class Stations(models.Model):
    id = models.PositiveIntegerField(db_column='ID', primary_key=True)  # Field name made lowercase.
    name = models.CharField(max_length=45, blank=True, null=True)
    technology = models.CharField(max_length=45, blank=True, null=True)
    capacity = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)
    capacityfactor = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    generation = models.DecimalField(max_digits=9, decimal_places=0, blank=True, null=True)
    transmitted = models.CharField(max_length=9, blank=True, null=True)

    class Meta:
        db_table = 'stations'

class Storageattributes(models.Model):
    idstorageattributes = models.AutoField(db_column='idStorageAttributes', primary_key=True)  # Field name made lowercase.
    idtechnologies = models.ForeignKey('Technologies', models.DO_NOTHING, db_column='idTechnologies', blank=True, null=True)  # Field name made lowercase.
    discharge_loss = models.IntegerField(blank=True, null=True)
    discharge_max = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    parasitic_loss = models.IntegerField(blank=True, null=True)
    rampdown_max = models.IntegerField(blank=True, null=True)
    rampup_max = models.IntegerField(blank=True, null=True)
    recharge_loss = models.IntegerField(blank=True, null=True)
    recharge_max = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    min_runtime = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    warm_time = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    class Meta:
        db_table = 'StorageAttributes'

class supplyfactors(models.Model):
    idsupplyfactors = models.AutoField(db_column='idsupplyfactors', primary_key=True)  # Field name made lowercase.
    idscenarios = models.ForeignKey('Scenarios', models.DO_NOTHING, db_column='idscenarios', blank=True, null=True)  # Field name made lowercase.
    idtechnologies = models.ForeignKey('Technologies', models.DO_NOTHING, db_column='idtechnologies', blank=True, null=True)  # Field name made lowercase.
    idzones = models.ForeignKey('Zones', models.DO_NOTHING, db_column='idzones', blank=True, null=True)  # Field name made lowercase.
    hour = models.IntegerField(blank=True, null=True)
    supply = models.IntegerField(blank=True, null=True)
    quantum = models.DecimalField(max_digits=9, decimal_places=2, blank=True, null=True)

    class Meta:
        db_table = 'supplyfactors'
        
class Technologies(models.Model):
    idtechnologies = models.AutoField(db_column='idTechnologies', primary_key=True)  # Field name made lowercase.
    technology_name = models.CharField(max_length=45, blank=True, null=True)
    year = models.IntegerField(default=0, null=True)
    image = models.CharField(max_length=50, blank=True, null=True)
    caption = models.CharField(max_length=50, blank=True, null=True)
    category = models.CharField(max_length=45, blank=True, null=True)
    renewable = models.IntegerField(blank=True, null=True)
    dispatchable = models.IntegerField(blank=True, null=True)
    merit_order = models.IntegerField(blank=True, null=True)
    capex = models.DecimalField(max_digits=9, decimal_places=2, blank=True, null=True)
    fom = models.DecimalField(db_column='FOM', max_digits=9, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    vom = models.DecimalField(db_column='VOM', max_digits=7, decimal_places=2, blank=True, null=True)  # Field name made lowercase.
    lifetime = models.DecimalField(max_digits=3, decimal_places=0, blank=True, null=True)
    discount_rate = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    description = models.CharField(max_length=1000, db_collation='utf8mb4_0900_ai_ci', blank=True, null=True)
    capacity = models.DecimalField(max_digits=9, decimal_places=2, blank=True, null=True)
    mult = models.DecimalField(max_digits=5, decimal_places=2, blank=True, null=True)
    capacity_max = models.DecimalField(max_digits=9, decimal_places=2, blank=True, null=True)
    capacity_min = models.DecimalField(max_digits=9, decimal_places=2, blank=True, null=True)
    emissions = models.DecimalField(max_digits=7, decimal_places=3, blank=True, null=True)
    initial = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)
    lcoe = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)
    lcoe_cf = models.DecimalField(max_digits=7, decimal_places=2, blank=True, null=True)

    class Meta:
        db_table = 'Technologies'

class Zones(models.Model):
    idzones = models.PositiveIntegerField(db_column='idZones', primary_key=True)  # Field name made lowercase.
    name = models.CharField(max_length=45, db_collation='utf8mb4_0900_ai_ci', blank=True, null=True)
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
