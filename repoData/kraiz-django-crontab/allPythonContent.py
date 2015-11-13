__FILENAME__ = app_settings
from django.conf import settings
from django.utils.importlib import import_module
import os
import re
import sys

# default app settings
# @see: http://www.muhuk.com/2010/01/developing-reusable-django-apps-app-settings/

CRONJOBS = getattr(settings, 'CRONJOBS', [])

CRONTAB_EXECUTABLE = getattr(settings, 'CRONTAB_EXECUTABLE', '/usr/bin/crontab')

CRONTAB_LINE_REGEXP = re.compile(r'^\s*(([^#\s]+\s+){5})([^#\n]*)\s*(#\s*([^\n]*)|$)')

CRONTAB_LINE_PATTERN = '%(time)s %(command)s # %(comment)s\n'

DJANGO_PROJECT_NAME = getattr(settings, 'CRONTAB_DJANGO_PROJECT_NAME', os.environ['DJANGO_SETTINGS_MODULE'].split('.')[0])

if hasattr(settings, 'CRONTAB_DJANGO_MANAGE_PATH'):
    DJANGO_MANAGE_PATH = settings.CRONTAB_DJANGO_MANAGE_PATH
    # check if it's really there
    if not os.path.exists(DJANGO_MANAGE_PATH):
        print 'ERROR: No manage.py file found at "%s". Check settings.CRONTAB_DJANGO_MANAGE_PATH!' % DJANGO_MANAGE_PATH
else:
    def ext(fpath):
        return os.path.splitext(fpath)[0] + '.py'
    try:  # Django 1.3
        DJANGO_MANAGE_PATH = ext(import_module(DJANGO_PROJECT_NAME + '.manage').__file__)
    except ImportError:
        try:  # Django 1.4+
            DJANGO_MANAGE_PATH = ext(import_module('manage').__file__)
        except ImportError:
            print 'ERROR: Can\'t find your manage.py - please define settings.CRONTAB_DJANGO_MANAGE_PATH'

PYTHON_EXECUTABLE = getattr(settings, 'CRONTAB_PYTHON_EXECUTABLE', sys.executable)

CRONTAB_COMMENT = getattr(settings, 'CRONTAB_COMMENT', 'django-cronjobs for %s' % DJANGO_PROJECT_NAME)

COMMAND_PREFIX = getattr(settings, 'CRONTAB_COMMAND_PREFIX', '')
COMMAND_SUFFIX = getattr(settings, 'CRONTAB_COMMAND_SUFFIX', '')

LOCK_JOBS = getattr(settings, 'CRONTAB_LOCK_JOBS', False)

########NEW FILE########
__FILENAME__ = crontab
from django.core.management.base import BaseCommand
from django.utils.importlib import import_module
from django_crontab.app_settings import CRONTAB_EXECUTABLE, CRONJOBS, \
    CRONTAB_LINE_PATTERN, CRONTAB_COMMENT, PYTHON_EXECUTABLE, DJANGO_MANAGE_PATH, \
    CRONTAB_LINE_REGEXP, COMMAND_PREFIX, COMMAND_SUFFIX, LOCK_JOBS
import fcntl
import hashlib
import json
import logging
import os
import tempfile


logger = logging.getLogger(__name__)


class Command(BaseCommand):
    args = '<add|show|remove>'
    help = 'run this command to add, show or remove the jobs defined in CRONJOBS setting from/to crontab'
    crontab_lines = []

    def handle(self, *args, **options):
        """dispatches by given subcommand"""
        if len(args) > 0:
            if args[0] == 'add':
                self.__read_crontab(**options)
                self.__remove_cronjobs(*args, **options)
                self.__add_cronjobs(*args, **options)
                self.__write_crontab(**options)
                return
            elif args[0] == 'show':
                self.__read_crontab(**options)
                self.__show_cronjobs(*args, **options)
                return
            elif args[0] == 'remove':
                self.__read_crontab(**options)
                self.__remove_cronjobs(*args, **options)
                self.__write_crontab(**options)
                return
            elif args[0] == 'run':
                self.__run_cronjob(args[1])
                return
        print help

    def __read_crontab(self, **options):
        """reads the crontab into internal buffer"""
        if options.get('verbosity') == '2':
            print 'reading from crontab...',
        self.crontab_lines = os.popen('%s -l' % CRONTAB_EXECUTABLE).readlines()
        if options.get('verbosity') == '2':
            print 'done'

    def __write_crontab(self, **options):
        """writes internal buffer back to crontab"""
        if options.get('verbosity') == '2':
            print 'writing to crontab...',
        fd, path = tempfile.mkstemp()
        tmp = os.fdopen(fd, 'w')
        for line in self.crontab_lines:
            tmp.write(line)
        tmp.close()
        os.system('%s %s' % (CRONTAB_EXECUTABLE, path))
        os.unlink(path)
        if options.get('verbosity') == '2':
            print 'done'

    def __add_cronjobs(self, *args, **options):
        """adds all jobs defined in CRONJOBS setting to internal buffer"""
        for job in CRONJOBS:
            # differ format and find job's suffix
            if len(job) > 2 and isinstance(job[2], (basestring, unicode)):
                # format 1 job
                job_suffix = job[2]
            elif len(job) > 4:
                job_suffix = job[4]
            else:
                job_suffix = ''

            self.crontab_lines.append(CRONTAB_LINE_PATTERN % {
                'time': job[0],
                'comment': CRONTAB_COMMENT,
                'command': (
                    '%(global_prefix)s %(exec)s %(manage)s crontab run '
                    '%(jobname)s %(job_suffix)s %(global_suffix)s'
                ) % {
                    'global_prefix': COMMAND_PREFIX,
                    'exec': PYTHON_EXECUTABLE,
                    'manage': DJANGO_MANAGE_PATH,
                    'jobname': self.__hash_job(job),
                    'job_suffix': job_suffix,
                    'global_suffix': COMMAND_SUFFIX
                }
            })
            if options.get('verbosity') >= '1':
                print '  adding cronjob: (%s) -> %s' % (self.__hash_job(job), job)

    def __show_cronjobs(self, *args, **options):
        """print the jobs from from crontab"""
        print "Currently active jobs in crontab:"
        for line in self.crontab_lines[:]:
            job = CRONTAB_LINE_REGEXP.findall(line)
            if job and job[0][4] == CRONTAB_COMMENT:
                if options.get('verbosity') >= '1':
                    print '%s -> %s' % (
                        job[0][2].split()[4],
                        self.__get_job_by_hash(job[0][2][job[0][2].find('run') + 4:].split()[0])
                    )

    def __remove_cronjobs(self, *args, **options):
        """removes all jobs defined in CRONJOBS setting from internal buffer"""
        for line in self.crontab_lines[:]:
            job = CRONTAB_LINE_REGEXP.findall(line)
            if job and job[0][4] == CRONTAB_COMMENT:
                self.crontab_lines.remove(line)
                if options.get('verbosity') >= '1':
                    print 'removing cronjob: (%s) -> %s' % (
                        job[0][2].split()[4],
                        self.__get_job_by_hash(job[0][2][job[0][2].find('run') + 4:].split()[0])
                    )

    def __hash_job(self, job):
        """build a md5 hash representing the job"""
        return hashlib.md5(json.dumps(job)).hexdigest()

    def __get_job_by_hash(self, job_hash):
        """find the job by given hash"""
        for job in CRONJOBS:
            if self.__hash_job(job) == job_hash:
                return job
        return None

    # noinspection PyBroadException
    def __run_cronjob(self, job_hash):
        """executes the corresponding function defined in CRONJOBS"""
        job = self.__get_job_by_hash(job_hash)
        job_name = job[1]
        job_args = job[2] if len(job) > 2 else []
        job_kwargs = job[3] if len(job) > 3 else {}

        lock_file_name = None
        if LOCK_JOBS:
            lock_file = open(os.path.join(tempfile.gettempdir(), 'django_crontab_%s.lock' % job_hash), 'w')
            lock_file_name = lock_file.name
            try:
                fcntl.lockf(lock_file, fcntl.LOCK_EX | fcntl.LOCK_NB)
            except:
                logger.warning('Tried to start cron job %s that is already running.', job)
                return

        module_path, function_name = job_name.rsplit('.', 1)
        module = import_module(module_path)
        func = getattr(module, function_name)
        try:
            func(*job_args, **job_kwargs)
        except:
            logger.exception('Failed to complete cronjob at %s', job)

        if LOCK_JOBS:
            try:
                os.remove(lock_file_name)
            except:
                logger.exception('Error deleting lockfile %s of job %s', lock_file_name, job)

########NEW FILE########
