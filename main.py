#!/usr/bin/env python3

# Copyright (C) 2017  Maximilian Falkenstein <mfalkenstein@sos.ethz.ch>
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import sys
from pysnmp.hlapi import *
import argparse
import os.path
import pickle
from enum import Enum


class ReturnCode(Enum):
    OK = 0
    WARNING = 1
    CRITICAL = 2
    UNKNOWN = 3


class Powerstrip:
    # Format: Tuple (variable name, SNMP Attribute name, unit scale)
    SNMP_DATA = [('power', 'e3IpmPowerP', 1),
                 ('var', 'e3IpmPowerQ', 1),
                 ('comp', 'e3IpmPowerS', 1),
                 ('U', 'e3IpmUrms', 1000),
                 ('I', 'e3IpmIrms', 1000),
                 ('f', 'e3IpmFrequency', 1000),
                 ('total', 'e3IpmEnergyP', 1)]

    def __init__(self, ip):
        self.engine = SnmpEngine()
        self.target = UdpTransportTarget((ip, 161))
        self.context = ContextData()
        self.community = CommunityData('public', mpModel=0)
        self.temp = 0
        self.channels = {0: {}, 1: {}, 2: {}}

    def get_val(self, res):
        error_indication, error_status, error_index, vars = next(res)
        if error_indication:
            raise ConnectionError(error_indication)
        elif error_status:
            raise ConnectionError('%s at %s' % (error_status.prettyPrint(),
                                                error_index and vars[int(error_index) - 1][0] or '?'))
        return vars[0][1].getValue()._value

    def fetch(self):
        # Fetch temperature
        temp_query = ObjectType(ObjectIdentity('NETTRACK-E3METER-SNMP-MIB', 'e3IpmSensorTemperatureCelsius', 0)
                                .addMibSource("/etc/icinga2/mibs"))
        temp_result = getCmd(self.engine, self.community, self.target, self.context, temp_query)
        self.temp = float(self.get_val(temp_result)) / 10
        # Fetch all attributes from list
        for (index, attribute, divisor) in self.SNMP_DATA:
            for x in range(0, 3):
                val_query = ObjectType(ObjectIdentity('NETTRACK-E3METER-SNMP-MIB', attribute, x)
                                       .addMibSource("/etc/icinga2/mibs"))
                val_result = getCmd(self.engine, self.community, self.target, self.context, val_query)
                self.channels[x][index] = self.get_val(val_result) / divisor
        # Calculate power factor
        for x in range(0, 3):
            if self.channels[x]['comp'] <= 0.1 or \
               self.channels[x]['power'] <= 0.1:
                self.channels[x]['PF'] = 100
            else:
                self.channels[x]['PF'] = self.channels[x]['power'] / self.channels[x]['comp'] * 100

    def get_result(self):
        return self.channels


class IcingaOutput:
    # Mapping of variable names to (performance data field, unit of measurement)
    VAR_NAMES = {'power': ['active power', ''],
                 'var': ['reactive power', ''],
                 'comp': ['complex power', ''],
                 'U': ['voltage', ''],
                 'I': ['current', ''],
                 'f': ['frequency', ''],
                 'total': ['total power consumption', ''],
                 'PF': ['power factor', '%']}

    def __init__(self, data):
        self.data = data

    def print_perf_data(self):
        for x in range(0, 3):
            first = True
            for y in self.VAR_NAMES.keys():
                value = self.data[x][y]
                if isinstance(value, float):
                    value = "{0:.2f}".format(value)
                if isinstance(value, int):
                    value = str(value)
                if first:
                    print('\'channel {0} {1}\'={2}{3}'.format(x, self.VAR_NAMES[y][0], value, self.VAR_NAMES[y][1]), end="",
                          flush=True)
                    first = False
                else:
                    print(' \'channel {0} {1}\'={2}{3}'.format(x, self.VAR_NAMES[y][0], value, self.VAR_NAMES[y][1]), end="",
                          flush=True)
            print (' ', end="", flush=True)


class Main:
    VAR_NAMES = ['power', 'var', 'comp', 'U', 'I', 'f', 'total', 'PF']

    def __init__(self):
        parser = argparse.ArgumentParser(description='Icinga check for three-phase E3METER IPS power strips')
        parser.add_argument('IP')
        parser.add_argument('-s', '--statefile', dest='statefile')
        parser.add_argument('-w', dest='warn_thresh')
        parser.add_argument('-c', dest='crit_thresh')
        parser.add_argument('-i', type=int, dest='interval')
        parser.add_argument('--debug', action="store_true")
        parser.set_defaults(statefile='/tmp/pwrstrstate')
        parser.set_defaults(interval=10)
        parser.set_defaults(warn_thresh=5)
        parser.set_defaults(crit_thresh=25)
        self.avg = None
        self.args = parser.parse_args()

    def __load_statefile__(self):
        if os.path.isfile(self.args.statefile):
            try:
                with open(self.args.statefile, 'rb') as pkl_file:
                    self.history = pickle.load(pkl_file)
            except IOError as err:
                if self.args.debug:
                    print("IOError during statefile loading! History will not be available... {0}".format(err))
            self.__calculate_averages__()
        else:
            self.history = []

    def __store_statefile__(self):
        try:
            with open(self.args.statefile, 'wb') as pkl_file:
                pkl_file.seek(0)
                pkl_file.truncate()
                pickle.dump(self.history, pkl_file, -1)
        except IOError as err:
            if self.args.debug:
                print("IOError during statefile save! History will not be saved correctly, booo... {0}".format(err))

    def __calculate_averages__(self):
        accumulator = {}
        for i in range(0, 3):
            accumulator[i] = {}
            for j in self.VAR_NAMES:
                accumulator[i][j] = 0
        if len(self.history) > 0:
            for i in range(0, 3):
                for j in range(0, len(self.history)):
                    for k in self.VAR_NAMES:
                        accumulator[i][k] += self.history[j][i][k]
            for i in range(0, 3):
                for j in self.VAR_NAMES:
                    accumulator[i][j] /= len(self.history)
            self.avg = accumulator
        else:
            self.avg = None

    def add_measurement(self, channels):
        if len(self.history) > self.args.interval:
            self.history.pop(0)
        self.history.append(channels)

    def do_check(self):
        rc = ReturnCode.OK
        try:
            var = Powerstrip(self.args.IP)
            var.fetch()
            res = var.get_result()
            self.__load_statefile__()
            if self.avg:
                for i in range(0, 3):
                    if self.avg[i]['I'] <= 0.1:
                        continue
                    if res[i]['I'] <= self.avg[i]['I'] * (1 - self.args.crit_thresh) or \
                                    res[i]['I'] >= self.avg[i]['I'] * (1 + self.args.crit_thresh):
                        rc = ReturnCode.CRITICAL
                        print("CRITICAL - Channel {0} current is {1} but average is {2} | ".format(
                                i, res[i]['I'], self.avg[i]['I']), end="", flush=True)
                        break
                    elif res[i]['I'] <= self.avg[i]['I'] * (1 - self.args.warn_thresh) or \
                                    res[i]['I'] >= self.avg[i]['I'] * (1 + self.args.warn_thresh):
                        rc = ReturnCode.WARNING
                        print("WARNING - Channel {0} current is {1} but average is {2} | ".format(
                                i, res[i]['I'], self.avg[i]['I']), end="", flush=True)
                        break

            if rc is ReturnCode.OK:
                self.add_measurement(res)
                print("OK | ", end="", flush=True)

            output = IcingaOutput(res)
            output.print_perf_data()
            self.__store_statefile__()
            print('')
        except ConnectionError:
            rc = ReturnCode.UNKNOWN
            print('UNKNOWN - Couldn\'t connect to {0}!'.format(self.args.IP))
        except:
            if self.args.debug:
                raise
            rc = ReturnCode.UNKNOWN
        sys.exit(rc.value)


os.chdir("/tmp")
obj = Main()
obj.do_check()
