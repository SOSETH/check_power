#!/usr/bin/env python3

from distutils.command.build import build
from setuptools import setup
import os


class CustomBuildCommand(build):
    def run(self):
        # At this point, dependencies should already be installed, so import the compiler only now
        if os.path.isfile('check_power/NETTRACK-E3METER-SNMP-MIB.py'):
            print ("File already compiled, skipping...")
        else:
            from pysmi.reader import getReadersFromUrls
            from pysmi.parser import SmiV1CompatParser
            from pysmi.compiler import MibCompiler
            from pysmi.searcher.stub import StubSearcher
            from pysmi.writer.pyfile import PyFileWriter
            from pysmi.codegen.pysnmp import PySnmpCodeGen, baseMibs
            mibSources = [os.path.abspath(os.path.dirname('./e3meter-ipm.mib')), 'http://mibs.snmplabs.com/asn1/@mib@']
            mibCompiler = MibCompiler(SmiV1CompatParser(), PySnmpCodeGen(),
                                      PyFileWriter(os.path.join(os.path.abspath(os.path.dirname('./e3meter-ipm.mib')), "check_power")))

            mibCompiler.addSources(*getReadersFromUrls(*mibSources))
            mibCompiler.addSearchers(StubSearcher(*baseMibs))

            results = mibCompiler.compile(os.path.abspath('./e3meter-ipm.mib'))
            print(results)
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
