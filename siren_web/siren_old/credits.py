#!/usr/bin/python3
#
#  Copyright (C) 2015-2022 Sustainable Energy Now Inc., Angus King
#
#  credits.py - This file is part of SIREN.
#
#  SIREN is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as
#  published by the Free Software Foundation, either version 3 of
#  the License, or (at your option) any later version.
#
#  SIREN is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General
#  Public License along with SIREN.  If not, see
#  <http://www.gnu.org/licenses/>.
#
from datetime import datetime
import os
import sys
from getmodels import getModelFile
if sys.platform == 'win32' or sys.platform == 'cygwin':
    from win32api import GetFileVersionInfo, LOWORD, HIWORD


def fileVersion(program=None, year=False):
    ver = '?'
    ver_yr = '????'
    if program == None:
        check = sys.argv[0]
    else:
        s = program.rfind('.')
        if s < 0:
            check = program + sys.argv[0][sys.argv[0].rfind('.'):]
        else:
            check = program
    if check[-3:] == '.py':
        try:
            modtime = datetime.fromtimestamp(os.path.getmtime(check))
            ver = '4.0.%04d.%d%02d' % (modtime.year, modtime.month, modtime.day)
            ver_yr = '%04d' % modtime.year
        except:
            pass
    elif check[-4:] != '.exe':
        try:
            modtime = datetime.fromtimestamp(os.path.getmtime(check))
            ver = '4.0.%04d.%d%02d' % (modtime.year, modtime.month, modtime.day)
            ver_yr = '%04d' % modtime.year
        except:
            pass
    else:
        if sys.platform == 'win32' or sys.platform == 'cygwin':
            try:
                if check.find('\\') >= 0:  # if full path
                    info = GetFileVersionInfo(check, '\\')
                else:
                    info = GetFileVersionInfo(os.getcwd() + '\\' + check, '\\')
                ms = info['ProductVersionMS']
              #  ls = info['FileVersionLS']
                ls = info['ProductVersionLS']
                ver = str(HIWORD(ms)) + '.' + str(LOWORD(ms)) + '.' + str(HIWORD(ls)) + '.' + str(LOWORD(ls))
                ver_yr = str(HIWORD(ls))
            except:
                try:
                    info = os.path.getmtime(os.getcwd() + '\\' + check)
                    ver = '4.0.' + datetime.fromtimestamp(info).strftime('%Y.%m%d')
                    ver_yr = datetime.fromtimestamp(info).strftime('%Y')
                    if ver[9] == '0':
                        ver = ver[:9] + ver[10:]
                except:
                    pass
    if year:
        return ver_yr
    else:
        return ver


class Credits(QtWidgets.QDialog):
    procStart = QtCore.pyqtSignal(str)

    def __init__(self, initial=False):
        super(Credits, self).__init__()
        self.initial = initial
        self.initUI()

    def closeEvent(self, event):
        if self.be_open:
            reply = QtWidgets.QMessageBox.question(self, 'SIREN Credits',
                    'Do you want to close Credits window?', QtWidgets.QMessageBox.Yes |
                    QtWidgets.QMessageBox.No, QtWidgets.QMessageBox.No)
            if reply == QtWidgets.QMessageBox.Yes:
                pass
            else:
                event.ignore()
                return
        if self.restorewindows:
            updates = {}
            lines = []
            add = int((self.frameSize().width() - self.size().width()) / 2)  # need to account for border
            lines.append('credits_pos=%s,%s' % (str(self.pos().x() + add), str(self.pos().y() + add)))
            lines.append('credits_size=%s,%s' % (str(self.width()), str(self.height())))
            updates['Windows'] = lines

        if self.be_open:
            self.procStart.emit('goodbye')
        event.accept()
