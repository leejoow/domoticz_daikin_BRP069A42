"""
<plugin key="BRP069A42" name="Daikin Airconditioning (BRP069A42)" author="leejoow" version="1.0.0" externallink="https://www.daikin.nl/nl_nl/products/BRP069A42.html">
    <params>
        <param field="Address" label="IP Address" width="200px" required="true" default=""/>
        <param field="Port" label="Port" width="30px" required="true" default="80"/>
        <param field="Mode1" label="Debug" width="75px">
            <options>
                <option label="True" value="Debug"/>
                <option label="False" value="Normal"  default="true" />
            </options>
        </param>
    </params>
</plugin>
"""
import Domoticz
import hmac
import hashlib
import time
import re
import base64
import http.client

class BasePlugin:
    powerOn = 0
    runCounter = 3
    httpConnSensorInfo = None
    httpConnControlInfo = None    
    httpConnSetControl = None  
    
    def __init__(self):
        return

    def onStart(self):
        if Parameters["Mode1"] == "Debug":
            Domoticz.Debugging(1)
            
        if (len(Devices) == 0):
            Domoticz.Device(Name="Power", Unit=1, Image=16, TypeName="Switch", Used=1).Create()
            Domoticz.Device(Name="Temp IN", Unit=2, TypeName="Temperature", Used=1).Create()
            Domoticz.Device(Name="Temp OUT", Unit=3, TypeName="Temperature",Used=1).Create()

            Options = {"LevelActions" : "|||||",
                       "LevelNames" : "|Auto|Cool|Heat|Fan|Dry",
                       "LevelOffHidden" : "true",
                       "SelectorStyle" : "1"}
            
            Domoticz.Device(Name="Mode", Unit=4, TypeName="Selector Switch", Image=16, Options=Options, Used=1).Create()
            
            Options = {"LevelActions" : "|||||||",
                       "LevelNames" : "|Auto|Silent|L1|L2|L3|L4|L5",
                       "LevelOffHidden" : "true",
                       "SelectorStyle" : "1"}
            
            Domoticz.Device(Name="Fan Rate", Unit=5, TypeName="Selector Switch", Image=16, Options=Options, Used=1).Create()
            Domoticz.Device(Name="Temp TARGET", Unit=6, Type=242, Subtype=1, Image=16, Used=1).Create()
            
            Domoticz.Log("Device created.")
            
        DumpConfigToLog()
        
        Domoticz.Heartbeat(10)
        
        self.httpConnSensorInfo = Domoticz.Connection(Name="Sensor Info", Transport="TCP/IP", Protocol="HTTP", Address=Parameters["Address"], Port=Parameters["Port"])
        self.httpConnSensorInfo.Connect()    

        self.httpConnControlInfo = Domoticz.Connection(Name="Control Info", Transport="TCP/IP", Protocol="HTTP", Address=Parameters["Address"], Port=Parameters["Port"])
        self.httpConnControlInfo.Connect() 
        
        self.httpConnSetControl = Domoticz.Connection(Name="Set Control", Transport="TCP/IP", Protocol="HTTP", Address=Parameters["Address"], Port=Parameters["Port"])

    def onStop(self):
        Domoticz.Log("Plugin is stopping.")

    def onConnect(self, Connection, Status, Description):
        if (Status == 0):
            Domoticz.Debug("Connection successful")
            
            data = ''
            headers = { 'Content-Type': 'text/xml; charset=utf-8', \
                        'Connection': 'keep-alive', \
                        'Accept': 'Content-Type: text/html; charset=UTF-8', \
                        'Host': Parameters["Address"]+":"+Parameters["Port"], \
                        'User-Agent':'Domoticz/1.0', \
                        'Content-Length' : "%d"%(len(data)) }

            if (Connection == self.httpConnSensorInfo):
                Domoticz.Debug("Sensor connection created")
                requestUrl = "/aircon/get_sensor_info"
            elif (Connection == self.httpConnControlInfo):
                Domoticz.Debug("Control connection created")
                requestUrl = "/aircon/get_control_info"
            elif (Connection == self.httpConnSetControl):
                Domoticz.Debug("Set connection created")
                requestUrl = self.buildCommandString()
                
            Connection.Send(data, 'GET', requestUrl, headers)
        else:
            Domoticz.Debug("Connection failed")
     
    def onMessage(self, Connection, Data, Status, Extra):
        dataDecoded = Data.decode("utf-8")
            
        Domoticz.Debug("Received data from connection " + Connection.Name + ": " + dataDecoded)
            
        if (Connection == self.httpConnControlInfo):       
            position = dataDecoded.find("pow=")
            power = dataDecoded[position + 4 : position + 5]
            
            position = dataDecoded.find("mode=")
            mode = dataDecoded[position + 5 : position + 6]
            
            position = dataDecoded.find("f_rate=")
            f_rate = dataDecoded[position + 7 : position + 8]
            
            position = dataDecoded.find("stemp=")
            stemp = dataDecoded[position + 6 : position + 8]
            
            Domoticz.Debug("Power: " + power + "; Mode: " + mode + "; FanRate: " + f_rate + "; Target temperature: " + stemp)
            
            self.powerOn = int(power)     
            
            if (power == "0"):
                Devices[1].Update(nValue = 0, sValue ="0") 
            else: 
                Devices[1].Update(nValue = 1, sValue ="100") 
            
            if (mode == "0"):
                Devices[4].Update(nValue = self.powerOn, sValue = "10") #Auto
            elif (mode == "2"):
                Devices[4].Update(nValue = self.powerOn, sValue = "50") #Dry
            elif (mode == "3"):
                Devices[4].Update(nValue = self.powerOn, sValue = "20") #Cool
            elif (mode == "4"):
                Devices[4].Update(nValue = self.powerOn, sValue = "30") #Warm
            
            if (f_rate == "A"):
                Devices[5].Update(nValue = self.powerOn, sValue = "10") # Auto
            elif (f_rate == "B"):
                Devices[5].Update(nValue = self.powerOn, sValue = "20") # Silent
            elif (f_rate == "3"):
                Devices[5].Update(nValue = self.powerOn, sValue = "30") # L1
            elif (f_rate == "4"):
                Devices[5].Update(nValue = self.powerOn, sValue = "40") # L2
            elif (f_rate == "5"):
                Devices[5].Update(nValue = self.powerOn, sValue = "50") # L3
            elif (f_rate == "6"):
                Devices[5].Update(nValue = self.powerOn, sValue = "60") # L4
            elif (f_rate == "7"):
                Devices[5].Update(nValue = self.powerOn, sValue = "70") # L5
            
            Devices[6].Update(nValue = self.powerOn, sValue = stemp)
        
        elif (Connection == self.httpConnSensorInfo):        
            position = dataDecoded.find("htemp=")
            htemp = dataDecoded[position + 6 : position + 10]
                        
            position = dataDecoded.find("otemp=")
            otemp = dataDecoded[position + 6 : position + 10]
            
            Domoticz.Debug("Internal temperature: " + htemp + "; Outside temperature: " + otemp)
            
            Devices[2].Update(nValue = 0, sValue = htemp)
            Devices[3].Update(nValue = 0, sValue = otemp)
            
    def onCommand(self, Unit, Command, Level, Hue):
        Domoticz.Debug("Command received U="+str(Unit)+" C="+str(Command)+" L= "+str(Level)+" H= "+str(Hue))
        
        if (Unit == 1):
            if(Command == "On"):
                self.powerOn = 1
                Devices[1].Update(nValue = 1, sValue ="100") 
            else:
                self.powerOn = 0
                Devices[1].Update(nValue = 0, sValue ="0") 
            
            #Update state of all other devices
            Devices[4].Update(nValue = self.powerOn, sValue = Devices[4].sValue)
            Devices[5].Update(nValue = self.powerOn, sValue = Devices[5].sValue)
            Devices[6].Update(nValue = self.powerOn, sValue = Devices[6].sValue)
        
        if (Unit == 4):
            Devices[4].Update(nValue = self.powerOn, sValue = str(Level))
            
        if (Unit == 5):
            Devices[5].Update(nValue = self.powerOn, sValue = str(Level))
        
        if (Unit == 6):
            Devices[6].Update(nValue = self.powerOn, sValue = str(Level))
            
        self.httpConnSetControl.Connect()
            
    def onDisconnect(self, Connection):
        Domoticz.Debug("Connection " + Connection.Name + " closed.")

    def onHeartbeat(self):
        self.runCounter = self.runCounter - 1
        if self.runCounter <= 0:
            Domoticz.Debug("Poll unit")
            self.runCounter = 3
            
            if (self.httpConnSensorInfo.Connected() == False):
                self.httpConnSensorInfo.Connect()
            
            if (self.httpConnControlInfo.Connected() == False):
                self.httpConnControlInfo.Connect()
            
        else:
            Domoticz.Debug("Polling unit in " + str(self.runCounter) + " heartbeats.")
        

    def buildCommandString(self):
        #Minimal string: pow=1&mode=1&stemp=26&shum=0&f_rate=B&f_dir=3
        
        requestUrl = "/aircon/set_control_info?shum=0&f_dir=0&pow="
    
        if (self.powerOn):
            requestUrl = requestUrl + "1"
        else:
            requestUrl = requestUrl + "0"
        
        requestUrl = requestUrl + "&mode="
        
        if (Devices[4].sValue == "10"):
            requestUrl = requestUrl + "0"
        elif (Devices[4].sValue == "20"):
            requestUrl = requestUrl + "3"
        elif (Devices[4].sValue == "30"):
            requestUrl = requestUrl + "4"
        elif (Devices[4].sValue == "50"):
            requestUrl = requestUrl + "2"
                
        requestUrl = requestUrl + "&f_rate="
        
        if (Devices[5].sValue == "10"):
            requestUrl = requestUrl + "A"
        elif (Devices[5].sValue == "20"):
            requestUrl = requestUrl + "B"
        else:
            requestUrl = requestUrl + str(int(int(Devices[5].sValue) / 10))
    
        requestUrl = requestUrl + "&stemp=" + Devices[6].sValue
    
        return requestUrl
        
global _plugin
_plugin = BasePlugin()

def onStart():
    global _plugin
    _plugin.onStart()

def onStop():
    global _plugin
    _plugin.onStop()

def onConnect(Connection, Status, Description):
    global _plugin
    _plugin.onConnect(Connection, Status, Description)

def stringToBase64(s):
    global _plugin
    _plugin.stringToBase64(s)

def onMessage(Connection, Data, Status, Extra):
    global _plugin
    _plugin.onMessage(Connection, Data, Status, Extra)

def onCommand(Unit, Command, Level, Hue):
    global _plugin
    _plugin.onCommand(Unit, Command, Level, Hue)

def onDisconnect(Connection):
    global _plugin
    _plugin.onDisconnect(Connection)

def onHeartbeat():
    global _plugin
    _plugin.onHeartbeat()

# Generic helper functions

def DumpConfigToLog():
    for x in Parameters:
        if Parameters[x] != "":
            Domoticz.Debug( "'" + x + "':'" + str(Parameters[x]) + "'")
    Domoticz.Debug("Device count: " + str(len(Devices)))
    for x in Devices:
        Domoticz.Debug("Device:           " + str(x) + " - " + str(Devices[x]))
        Domoticz.Debug("Device ID:       '" + str(Devices[x].ID) + "'")
        Domoticz.Debug("Device Name:     '" + Devices[x].Name + "'")
        Domoticz.Debug("Device nValue:    " + str(Devices[x].nValue))
        Domoticz.Debug("Device sValue:   '" + Devices[x].sValue + "'")
        Domoticz.Debug("Device LastLevel: " + str(Devices[x].LastLevel))
    return

