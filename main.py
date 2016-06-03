from pysnmp.hlapi import *

class Powerstrip:
    def __init__(self, ip):
        self.engine = SnmpEngine()
        self.target = UdpTransportTarget((ip, 161))
        self.context = ContextData()
        self.community = CommunityData('public', mpModel=0)
        self.temp = 0
        self.channels = {0: {}, 1: {}, 2: {}}

    def printResult(self, res):
        errorIndication, errorStatus, errorIndex, varBinds = next(res)
        if errorIndication:
            print(errorIndication)
        elif errorStatus:
            print('%s at %s' % (errorStatus.prettyPrint(),
                                errorIndex and varBinds[int(errorIndex) - 1][0] or '?'))
        else:
            for varBind in varBinds:
                print(' = '.join([x.prettyPrint() for x in varBind]))

    def getAndPrint(self, otype):
        res = getCmd(self.engine, self.community, self.target, self.context, otype)
        self.printResult(res)

    def getVal(self, res):
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
        self.temp = float(self.getVal(tempRes)) / 10
        for (index, attribute, divisor) in [('power', 'e3IpmPowerP', 1), ('var', 'e3IpmPowerQ', 1), ('comp', 'e3IpmPowerS', 1), ('U', 'e3IpmUrms', 1000), ('I', 'e3IpmIrms', 1000), ('f', 'e3IpmFrequency', 1000), ('total', 'e3IpmEnergyP', 1)]:
            for x in range(0, 3):
                vQuery=ObjectType(ObjectIdentity('NETTRACK-E3METER-SNMP-MIB', attribute, x))
                vRes = getCmd(self.engine, self.community, self.target, self.context, vQuery)
                self.channels[x][index] = self.getVal(vRes) / divisor
        for x in range(0, 3):
            self.channels[x]['PF'] = self.channels[x]['power'] / self.channels[x]['comp']

        print (self.channels[0])


var = Powerstrip('172.31.0.219')
var.fetch()