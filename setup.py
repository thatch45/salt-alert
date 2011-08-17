#!/usr/bin/python2
'''
The setup script for salt
'''
import os
import sys
from distutils import log
from distutils.core import setup
from distutils.sysconfig import get_python_lib, PREFIX

NAME = 'salt-alert'
VER = '0.1.0'
DESC = 'An alert delivery system that extends the salt core'

doc_path = os.path.join(PREFIX, 'share/doc/', NAME + '-' + VER)
if os.environ.has_key('SYSCONFDIR'):
    etc_path = os.environ['SYSCONFDIR']
else:
    etc_path = os.path.join(os.path.dirname(PREFIX), 'etc')

setup(
      name=NAME,
      version=VER,
      description=DESC,
      author='Thomas S Hatch',
      author_email='thatch45@gmail.com',
      url='https://github.com/thatch45/salt-monitor',
      classifiers = [
          'Programming Language :: Python',
          'Programming Language :: Cython',
          'Programming Language :: Python :: 2.5',
          'Development Status :: 4 - Beta',
          'Environment :: Console',
          'Intended Audience :: Developers',
          'Intended Audience :: Information Technology',
          'Intended Audience :: System Administrators',
          'License :: OSI Approved :: Apache Software License',
          'Operating System :: POSIX :: Linux',
          'Topic :: System :: Monitoring',
          'Topic :: System :: Clustering',
          'Topic :: System :: Distributed Computing',
          ],
      packages=['salt.ext.alert',
                ],
      scripts=['scripts/salt-alert'],
      data_files=[(os.path.join(etc_path, 'salt'),
                    ['conf/alert']),
                ('share/man/man1',
                    ['doc/man/salt-alert.1',
                    ]),
                (doc_path,
                    ['LICENSE'
                    ]),
                 ],
     )
