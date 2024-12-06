import openpyxl as oxl
from PyQt5 import QtCore, QtGui, QtWidgets

class Location(QtWidgets.QDialog):
    def __init__(self, upper_left, lower_right, parent=None):
        super(Location, self).__init__(parent)
        self.lat = QtWidgets.QDoubleSpinBox()
        self.lat.setDecimals(4)
        self.lat.setSingleStep(.1)
        self.lat.setRange(lower_right[3], upper_left[3])
        self.lat.setValue(lower_right[3] + (upper_left[3] - lower_right[3]) / 2.)
        self.lon = QtWidgets.QDoubleSpinBox()
        self.lon.setDecimals(4)
        self.lon.setSingleStep(.1)
        self.lon.setRange(upper_left[2], lower_right[2])
        self.lon.setValue(upper_left[2] + (lower_right[2] - upper_left[2]) / 2.)
        grid = QtWidgets.QGridLayout(self)
        grid.addWidget(QtWidgets.QLabel('Lat:'), 1, 0)
        grid.addWidget(self.lat, 1, 1)
        lats =  QtWidgets.QLabel('(%s to %s)     ' % ('{:0.4f}'.format(lower_right[3]), \
                '{:0.4f}'.format(upper_left[3])))
        lats.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        grid.addWidget(lats, 2, 0, 1, 2)
        grid.addWidget(QtWidgets.QLabel('Lon:'), 3, 0)
        grid.addWidget(self.lon, 3, 1)
        lons =  QtWidgets.QLabel('(%s to %s)     ' % ('{:0.4f}'.format(upper_left[2]), \
                '{:0.4f}'.format(lower_right[2])))
        lons.setAlignment(QtCore.Qt.AlignRight | QtCore.Qt.AlignVCenter)
        grid.addWidget(lons, 4, 0, 1, 2)
         # OK and Cancel buttons
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            QtCore.Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        grid.addWidget(buttons, 5, 0, 1, 2)
        self.setWindowTitle('SIREN - Powermap - Go to Location')

    def location(self):
        return self.lat.value(), self.lon.value()

     # static method to create the dialog and return
    @staticmethod
    def getLocation(upper_left, lower_right, parent=None):
        dialog = Location(upper_left, lower_right, parent)
        result = dialog.exec_()
        return (dialog.location())

class Description(QtWidgets.QDialog):
    def __init__(self, who, desc='', parent=None):
        super(Description, self).__init__(parent)
        layout = QtWidgets.QVBoxLayout(self)
        layout.addWidget(QtWidgets.QLabel('Set Description for ' + who))
        self.text = QtWidgets.QPlainTextEdit()
        self.text.setPlainText(desc)
        layout.addWidget(self.text)
         # OK and Cancel buttons
        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.Ok | QtWidgets.QDialogButtonBox.Cancel,
            QtCore.Qt.Horizontal, self)
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)
        self.setWindowTitle('SIREN - Powermap - Save Scenario')

    def description(self):
        return self.text.toPlainText()

     # static method to create the dialog and return
    @staticmethod
    def getDescription(who, desc='', parent=None):
        dialog = Description(who, desc, parent)
        result = dialog.exec_()
        return (dialog.description())