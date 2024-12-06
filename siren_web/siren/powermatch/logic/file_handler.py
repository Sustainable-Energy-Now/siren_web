import os
import sys
import glob

class FileHandler:
    @staticmethod
    def get_filename(filename):
        if filename.find('/') == 0: # full directory in non-Windows
            return filename
        elif (sys.platform == 'win32' or sys.platform == 'cygwin') \
          and filename[1:2] == ':/': # full directory for Windows
            return filename
        elif filename[:3] == '../': # directory upwards of scenarios
            ups = filename.split('../')
            scens = scenarios.split('/')
            scens = scens[: -(len(ups) - 1)]
            scens.append(ups[-1])
            return '/'.join(scens)
        else: # subdirectory of scenarios
            return scenarios + filename
        
    def get_load_years(self):
        load_years = ['n/a']
        i = self.load_files.find('$YEAR$')
        if i < 0:
            return load_years
        j = len(self.load_files) - i - 6
        files = glob.glob(self.load_files[:i] + '*' + self.load_files[i + 6:])
        for fil in files:
            load_years.append(fil[i:len(fil) - j])
        return sorted(load_years, reverse=True)
