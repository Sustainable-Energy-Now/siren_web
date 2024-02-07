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
    idSettings = models.BigAutoField(primary_key=True)
    context = models.CharField(max_length=20)
    parameter = models.CharField(max_length=45)
    value = models.CharField(max_length=300)

    class Meta:
        # Define the name of the database table explicitly
        db_table = 'Settings'

    def __str__(self):
        return f"Setting for {self.context}: {self.parameter} = {self.value}"