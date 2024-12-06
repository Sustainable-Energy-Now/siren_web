from logic import Constraint, ExcelProcessor

class PowermatchAPI:
    def __init__(self):
        self.constraints = []

    def add_constraint(self, name, capacity_min, capacity_max, recharge_loss, discharge_loss):
        constraint = Constraint(name, capacity_min, capacity_max, recharge_loss, discharge_loss)
        self.constraints.append(constraint)

    def load_constraints_from_file(self, file_path, sheet_name):
        processor = ExcelProcessor(file_path)
        data = processor.read_sheet(sheet_name)
        # Parse and populate constraints
