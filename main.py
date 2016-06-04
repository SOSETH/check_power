from pysnmp.hlapi import *
import argparse
import os.path
import pickle


class Powerstrip:
    SNMP_DATA = [('power', 'e3IpmPowerP', 1), ('var', 'e3IpmPowerQ', 1), ('comp', 'e3IpmPowerS', 1), ('U', 'e3IpmUrms', 1000), ('I', 'e3IpmIrms', 1000), ('f', 'e3IpmFrequency', 1000), ('total', 'e3IpmEnergyP', 1)]

    def __init__(self, ip):
        self.engine = SnmpEngine()
        self.target = UdpTransportTarget((ip, 161))
        self.context = ContextData()
        self.community = CommunityData('public', mpModel=0)
        self.temp = 0
        self.channels = {0: {}, 1: {}, 2: {}}

    def print_result(self, res):
        errorIndication, errorStatus, errorIndex, varBinds = next(res)
        if errorIndication:
            print(errorIndication)
        elif errorStatus:
            print('%s at %s' % (errorStatus.prettyPrint(),
                                errorIndex and varBinds[int(errorIndex) - 1][0] or '?'))
        else:
            for varBind in varBinds:
                print(' = '.join([x.prettyPrint() for x in varBind]))

    def get_and_print(self, otype):
        res = getCmd(self.engine, self.community, self.target, self.context, otype)
        self.print_result(res)

    def get_val(self, res):
        errorIndication, errorStatus, errorIndex, varBinds = next(res)
        if errorIndication:
            raise ConnectionError(errorIndication)
        elif errorStatus:
            raise ConnectionError('%s at %s' % (errorStatus.prettyPrint(),
                                  errorIndex and varBinds[int(errorIndex) - 1][0] or '?'))
        return varBinds[0][1].getValue()._value

    def fetch(self):
        tempQuery = ObjectType(ObjectIdentity('NETTRACK-E3METER-SNMP-MIB', 'e3IpmSensorTemperatureCelsius', 0))
        tempRes = getCmd(self.engine, self.community, self.target, self.context, tempQuery)
        self.temp = float(self.get_val(tempRes)) / 10
        for (index, attribute, divisor) in self.SNMP_DATA:
            for x in range(0, 3):
                vQuery=ObjectType(ObjectIdentity('NETTRACK-E3METER-SNMP-MIB', attribute, x))
                vRes = getCmd(self.engine, self.community, self.target, self.context, vQuery)
                self.channels[x][index] = self.get_val(vRes) / divisor
        for x in range(0, 3):
            self.channels[x]['PF'] = self.channels[x]['power'] / self.channels[x]['comp']

    def get_result(self):
        return self.channels


class IcingaOutput:
    VAR_NAMES = {'power': 'Active', 'var': 'Reactive', 'comp': 'Complex', 'U': 'Voltage', 'I': 'Current', 'f': 'Frequency', 'total': 'Sum', 'PF': 'Power_factor'}

    def __init__(self, data):
        self.data = data

    def print_perf_data(self):
        for x in range(0, 3):
            for y in self.VAR_NAMES.keys():
                value = self.data[x][y]
                if isinstance(value, float):
                    value = "{0:.2f}".format(value)
                if isinstance(value, int):
                    value = str(value)
                print ('\''+ self.VAR_NAMES[y]+ '\'='+ value,end="",flush=True)
            print ('')

class Main:
    VAR_NAMES = ['power', 'var', 'comp', 'U', 'I', 'f', 'total', 'PF']

    def __init__(self):
        parser = argparse.ArgumentParser(description='Iciinga check for three-phase E3METER IPS power strips')
        parser.add_argument('IP')
        parser.add_argument('--statefile', '-s', dest='statefile')
        parser.add_argument('--debug', action="store_true")
        parser.set_defaults(statefile='/tmp/pwrstrstate')
        self.args = parser.parse_args()

    def __load_statefile__(self):
        if os.path.isfile(self.args.statefile):
            try:
                with open(self.args.statefile, 'rb') as pkl_file:
                    self.history = pickle.load(pkl_file)
            except IOError as err:
                if self.args.debug:
                    print ("IOError during statefile loading! History will not be available... {0}".format(err))
            self.__calculate_averages__()
        else:
            self.history=[]

    def __store_statefile__(self):
        try:
            with open(self.args.statefile, 'wb') as pkl_file:
                pkl_file.seek(0)
                pkl_file.truncate()
                pickle.dump(self.history, pkl_file, -1)
        except IOError as err:
            if self.args.debug:
                print ("IOError during statefile save! History will not be saved correctly, booo... {0}".format(err))

    def __calculate_averages__(self):
        accumulator = {}
        for i in range(0,3):
            accumulator[i] = {}
            for j in self.VAR_NAMES:
                accumulator[i][j] = 0
        if len(self.history) > 0:
            for i in range(0,3):
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
        if len(self.history)>10:
            self.history.pop(0)
        self.history.append(channels)

    def do_check(self):
        var = Powerstrip(self.args.IP)
        var.fetch()
        res = var.get_result()
        self.__load_statefile__()
        output = IcingaOutput(res)
        output.print_perf_data()
        self.add_measurement(res)
        self.__store_statefile__()


obj = Main()
obj.do_check()