class Constraint:
    def __init__(self, name, category, capacity_min, capacity_max, rampup_max, rampdown_max,
                 recharge_max, recharge_loss, discharge_max, discharge_loss, parasitic_loss,
                 min_runtime, warm_time):
        self.name = name.strip()
        self.category = category
        try:
            self.capacity_min = float(capacity_min) # minimum run_rate for generator; don't drain below for storage
        except:
            self.capacity_min = 0.
        try:
            self.capacity_max = float(capacity_max) # maximum run_rate for generator; don't drain more than this for storage
        except:
            self.capacity_max = 1.
        try:
            self.recharge_max = float(recharge_max) # can't charge more than this per hour
        except:
            self.recharge_max = 1.
        try:
            self.recharge_loss = float(recharge_loss)
        except:
            self.recharge_loss = 0.
        try:
            self.discharge_max = float(discharge_max) # can't discharge more than this per hour
        except:
            self.discharge_max = 1.
        try:
            self.discharge_loss = float(discharge_loss)
        except:
            self.discharge_loss = 0.
        try:
            self.parasitic_loss = float(parasitic_loss) # daily parasitic loss / hourly ?
        except:
            self.parasitic_loss = 0.
        try:
            self.rampup_max = float(rampup_max)
        except:
            self.rampup_max = 1.
        try:
            self.rampdown_max = float(rampdown_max)
        except:
            self.rampdown_max = 1.
        try:
            self.min_runtime = int(min_runtime)
        except:
            self.min_runtime = 0
        try:
            self.warm_time = float(warm_time)
            if self.warm_time >= 1:
                self.warm_time = self.warm_time / 60
                if self.warm_time > 1:
                    self.warm_time = 1
            elif self.warm_time > 0:
                if self.warm_time <= 1 / 24.:
                    self.warm_time = self.warm_time * 24
        except:
            self.warm_time = 0

class Facility:
    def __init__(self, **kwargs):
        kwargs = {**kwargs}
      #  return
        self.name = ''
        self.constraint = ''
        self.order = 0
        self.lifetime = 20
        self.area = None
        for attr in ['capacity', 'lcoe', 'lcoe_cf', 'emissions', 'initial', 'capex',
                     'fixed_om', 'variable_om', 'fuel', 'disc_rate', 'lifetime', 'area']:
            setattr(self, attr, 0.)
        for key, value in kwargs.items():
            if value != '' and value is not None:
                if key == 'lifetime' and value == 0:
                    setattr(self, key, 20)
                else:
                    setattr(self, key, value)

class PM_Facility:
    def __init__(self, name, generator, capacity, tech_type, col, multiplier):
        self.name = name
        if name.find('.') > 0:
            self.zone = name[:name.find('.')]
        else:
            self.zone = ''
        self.generator = generator
        self.capacity = capacity
        self.tech_type = tech_type
        self.col = col
        self.multiplier = multiplier

class Optimisation:
    def __init__(self, name, approach, values): #capacity=None, cap_min=None, cap_max=None, cap_step=None, caps=None):
        self.name = name.strip()
        self.approach = approach
        if approach == 'Discrete':
            caps = values.split()
            self.capacities = []
            cap_max = 0.
            for cap in caps:
                try:
                    self.capacities.append(float(cap))
                    cap_max += float(cap)
                except:
                    pass
            self.capacity_min = 0
            self.capacity_max = round(cap_max, 3)
            self.capacity_step = None
        elif approach == 'Range':
            caps = values.split()
            try:
                self.capacity_min = float(caps[0])
            except:
                self.capacity_min = 0.
            try:
                self.capacity_max = float(caps[1])
            except:
                self.capacity_max = 0.
            try:
                self.capacity_step = float(caps[2])
            except:
                self.capacity_step = 0.
            self.capacities = None
        else:
            self.capacity_min = 0.
            self.capacity_max = 0.
            self.capacity_step = 0.
            self.capacities = None
        self.capacity = 0.
