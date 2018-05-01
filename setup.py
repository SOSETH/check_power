#!/usr/bin/env python3


from distutils.command.build import build
from setuptools import setup
import os

class CustomBuildCommand(build):
    def run(self):
        os.system("mibdump.py --mib-source=file://$(pwd) --mib-source http://mibs.snmplabs.com/asn1/@mib@ --destination-directory=check_power e3meter-ipm")
        build.run(self)

setup(name='check_power',
      version='0.1',
      description='Check E3Meter power strips via SNMP',
      author='Maximilian Falkenstein',
      author_email='mfalkenstein@sos.ethz.ch',
      url='https://github.com/SOSETH/check_power',
      packages=['check_power'],
      scripts=['bin/check_power'],
      install_requires=['pysnmp==4.3.2'],
      cmdclass={
          'build': CustomBuildCommand
      },
      zip_safe=False
     )
