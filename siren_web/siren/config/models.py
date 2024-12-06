import configparser   # decode .ini file
import os
import sys
import time
from modules.getmodels import getModelFile, commonprefix
from utilities.senutils import getUser

def load_settings():
    models_dir = '.'
    models_dirs = []
    if len(sys.argv) > 1:
        if os.path.isdir(sys.argv[1]):
            models_dir = sys.argv[1]
        else:
            ini_dir = sys.argv[1].replace('$USER$', getUser())
            if os.path.isdir(ini_dir):
                models_dir = ini_dir
        if sys.platform == 'win32' or sys.platform == 'cygwin':
            if models_dir[-1] != '\\' and models_dir[-1] != '/':
                models_dir += '\\'
        elif models_dir[-1] != '/':
            models_dir += '/'
    else:
        models_dirs = getModelFile()
    if len(models_dirs) == 0:
        models_dirs = [models_dir]
    entries = []
    for models_dir in models_dirs:
        fils = os.listdir(models_dir)
        help = 'help.html'
        about = 'about.html'
        config = configparser.RawConfigParser()
        ignore = ['flexiplot.ini', 'powerplot.ini', 'siren_default.ini']
        errors = ''
        for fil in sorted(fils):
            if fil[-4:] == '.ini':
                if fil in ignore:
                    continue
                mod_time = time.strftime('%Y-%m-%d %H:%M:%S',
                            time.localtime(os.path.getmtime(models_dir + fil)))
                ok, model_name, errors = check_file(models_dir, fil, errors)
                if len(models_dirs) > 1:
                    entries.append([fil, model_name, mod_time, models_dir, ok])
                else:
                    entries.append([fil, model_name, mod_time, ok])
    if len(errors) > 0:
        dialog = displayobject.AnObject(QtWidgets.QDialog(), errors,
                    title='SIREN (' + fileVersion() + ') - Preferences file errors')
        dialog.exec_()
    return {
        "config_file": os.getenv("POWERMAP_CONFIG", "SIREN.ini"),
        "default_zoom": 0.8,
    }
