import openpyxl as oxl

class ExcelProcessor:
    def __init__(self, file_path):
        self.file_path = file_path
        self.workbook = oxl.load_workbook(self.file_path)
    
    def get_worksheet(self, index=0):
        """Retrieve a worksheet by index."""
        return self.workbook.worksheets[index]

    def sheet_by_name(self, name):
        """Retrieve a worksheet by name."""
        return self.workbook[name]

    def get_font(self, name, bold=False):
        """Retrieve a font style."""
        return oxl.styles.Font(name=name, bold=bold)

    def save(self):
        """Save changes to the workbook."""
        self.workbook.save(self.file_path)