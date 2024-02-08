from django.db import models

from django.db import models

class Analysis(models.Model):
    idAnalysis = models.BigAutoField(primary_key=True)
    idScenarios = models.ForeignKey('Scenarios', on_delete=models.RESTRICT)
    Heading = models.CharField(max_length=45)
    Component = models.CharField(max_length=45)
    Basis = models.CharField(max_length=45)
    Stage = models.CharField(max_length=45)
    Quantity = models.CharField(max_length=300)
    Units = models.CharField(max_length=10)

    class Meta:
        # Define the name of the database table explicitly
        db_table = 'Analysis'

    def __str__(self):
        return f"Setting for {self.Heading}: {self.Component} = {self.Stage}"

class constraints(models.Model):
    ID = models.BigAutoField(primary_key=True)
    ConstraintName = models.CharField(max_length=45)
    Image = models.CharField(max_length=50)
    Category = models.CharField(max_length=45)
    CapacityMax = models.IntegerField()
    CapacityMin = models.IntegerField()    
    DischargeLoss = models.IntegerField()
    DischargeMax = models.DecimalField(max_digits=5, decimal_places=2)
    ParasiticLoss = models.IntegerField()
    RampdownMax = models.IntegerField()
    RampupMax = models.IntegerField()
    RechargeLoss = models.IntegerField()
    RechargeMax = models.DecimalField(max_digits=5, decimal_places=2)
    Renewable = models.BooleanField()
    Description = models.CharField(max_length=500)

    class Meta:
        # Define the name of the database table explicitly
        db_table = 'constraints'

    def __str__(self):
        return f"constraints for {self.ConstraintName}: {self.Description}"

class Demand(models.Model):
    idDemand = models.BigAutoField(primary_key=True)
    ConstraintID = models.ForeignKey('constraints', on_delete=models.RESTRICT)
    hour = models.IntegerField()
    period = models.IntegerField()
    load = models.DecimalField(max_digits=9, decimal_places=2) 
    col = models.IntegerField()

    class Meta:
        # Define the name of the database table explicitly
        db_table = 'Demand'

    def __str__(self):
        return f"Demand"
    
class generators:
    ID = models.BigAutoField(primary_key=True) 
    Year = models.IntegerField()
    Name = models.CharField(max_length=45)
    Image = models.CharField(max_length=65)  
    Capacity = models.DecimalField(max_digits=7, decimal_places=2)
    Constr = models.IntegerField()
    Emissions = models.DecimalField(max_digits=5, decimal_places=3)
    Initial = models.DecimalField(max_digits=5, decimal_places=2)
    Ord = models.IntegerField()
    Dispatchable = models.BooleanField()
    mult = models.FloatField()
    Capex = models.DecimalField(max_digits=9, decimal_places=0)
    FOM = models.DecimalField(max_digits=9, decimal_places=0)
    VOM = models.DecimalField(max_digits=5, decimal_places=2)
    Fuel = models.DecimalField(max_digits=5, decimal_places=2)
    Lifetime = models.DecimalField(max_digits=3, decimal_places=0)
    DiscountRate = models.DecimalField(max_digits=5, decimal_places=2)
    class Meta:
        # Define the name of the database table explicitly
        db_table = 'generators'

    def __str__(self):
        return f"generators for {self.Name}"


class GeneratorAttributes:
    idGeneratorAttributes  = models.BigAutoField(primary_key=True)
    idTechnologies = models.ForeignKey('Technologies', on_delete=models.RESTRICT)
    year = models.IntegerField()
    capacity = models.DecimalField(max_digits=7, decimal_places=2)
    emissions = models.DecimalField(max_digits=5, decimal_places=3)
    initial = models.DecimalField(max_digits=5, decimal_places=2)  
    mult = models.FloatField() 
    fuel = models.CharField(max_length=50)
    
    class Meta:
        # Define the name of the database table explicitly
        db_table = 'GeneratorAttributes'

    def __str__(self):
        return f"Generator Attributes"
    
class Genetics:
    idGenetics = models.BigAutoField(primary_key=True) 
    Parameter = models.CharField(max_length=30)
    Weight = models.DecimalField(max_digits=5, decimal_places=2)  
    Better = models.DecimalField(max_digits=5, decimal_places=2)  
    Worse = models.DecimalField(max_digits=13, decimal_places=2)  
    MinValue = models.DecimalField(max_digits=5, decimal_places=2)  
    MaxValue = models.DecimalField(max_digits=5, decimal_places=2)  
    Step = models.DecimalField(max_digits=5, decimal_places=2)  
    BetterSpinner = models.BooleanField() 
    WorseSpinner = models.BooleanField()
    class Genetics:
        # Define the name of the database table explicitly
        db_table = 'Genetics'

    def __str__(self):
        return f"Genetics"

class Optimisation:
    idOptimisation = models.BigAutoField(primary_key=True) 
    Name = models.CharField(max_length=45) 
    Approach = models.CharField(max_length=45) 
    Capacity = models.DecimalField(max_digits=7, decimal_places=1)  
    CapacityMax = models.DecimalField(max_digits=7, decimal_places=1)  
    CapacityMin = models.DecimalField(max_digits=7, decimal_places=1)  
    CapacityStep = models.DecimalField(max_digits=7, decimal_places=1)
    class Optimisation:
        # Define the name of the database table explicitly
        db_table = 'Optimisation'

    def __str__(self):
        return f"Optimisation"

class Scenarios(models.Model):
    idScenarios = models.BigAutoField(primary_key=True)
    Title = models.CharField(max_length=45)
    DateExported = models.DateField()
    Year = models.IntegerField()
    Description = models.CharField(max_length=500)

    class Meta:
        # Define the name of the database table explicitly
        db_table = 'Scenarios'

    def __str__(self):
        return f"Scenario for {self.Title}: {self.Description}"
    
class Settings(models.Model):
    idSettings = models.AutoField(primary_key=True)
    context = models.CharField(max_length=20)
    parameter = models.CharField(max_length=45)
    value = models.CharField(max_length=300)

    class Meta:
        # Define the name of the database table explicitly
        db_table = 'Settings'

    def __str__(self):
        return f"Setting for {self.context}: {self.parameter} = {self.value}"

class stations:
    ID = models.BigAutoField(primary_key=True) 
    name = models.CharField(max_length=45) 
    technology = models.CharField(max_length=45) 
    capacity = models.DecimalField(max_digits=7, decimal_places=2)  
    capacityfactor = models.DecimalField(max_digits=5, decimal_places=2)  
    generation = models.DecimalField(max_digits=9, decimal_places=0) 
    transmitted = models.CharField(max_length=9)

    class Meta:
        # Define the name of the database table explicitly
        db_table = 'stations'

    def __str__(self):
        return f"station for {self.name}: {self.technology}"

class StorageAttributes:
    idStorageAttributes = models.BigAutoField(primary_key=True) 
    idTechnologies = models.ForeignKey('Technologies', on_delete=models.RESTRICT)
    capacity_max = models.IntegerField() 
    capacity_min = models.IntegerField() 
    discharge_loss = models.IntegerField() 
    discharge_max = models.DecimalField(max_digits=5, decimal_places=2)  
    parasitic_loss = models.IntegerField() 
    rampdown_max = models.IntegerField() 
    rampup_max = models.IntegerField() 
    recharge_loss = models.IntegerField() 
    recharge_max = models.DecimalField(max_digits=5, decimal_places=2)

    class Meta:
        # Define the name of the database table explicitly
        db_table = 'StorageAttributes'

    def __str__(self):
        return f"StorageAttributes"
    
class Technologies:
    idTechnologies = models.BigAutoField(primary_key=True) 
    technology_name = models.CharField(max_length=45) 
    image = models.CharField(max_length=50) 
    caption = models.CharField(max_length=50) 
    category = models.CharField(max_length=45) 
    renewable = models.BooleanField() 
    dispatchable = models.BooleanField() 
    merit_order = models.IntegerField() 
    capex = models.DecimalField(max_digits=9, decimal_places=0) 
    FOM = models.DecimalField(max_digits=9, decimal_places=0) 
    VOM = models.DecimalField(max_digits=5, decimal_places=2)  
    lifetime = models.DecimalField(max_digits=3, decimal_places=0) 
    discount_rate = models.DecimalField(max_digits=5, decimal_places=2)  
    description = models.CharField(max_length=1000)

    class Meta:
        # Define the name of the database table explicitly
        db_table = 'Technologies'

    def __str__(self):
        return f"Technologies {self.technology_name}"
    
class Zones:
	idZones = models.BigAutoField(primary_key=True) 
	idScenarios = models.ForeignKey('Scenarios', on_delete=models.RESTRICT) 
	ConstraintID = models.ForeignKey('Constraints', on_delete=models.RESTRICT) 
	existing = models.BooleanField() 
	Capacity = models.DecimalField(max_digits=11, decimal_places=2) 