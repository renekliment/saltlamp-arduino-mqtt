#!/usr/bin/env python2
# -*- coding: utf-8 -*-

import yaml
import paho.mqtt.client as mqtt
import sys
import serial
import time
import sys
from socket import error as socket_error

with open(sys.argv[1], 'r') as stream:
	config = yaml.load(stream)

prefix = config['mqtt']['prefix']
devices = config['devices']
aliases = config['aliases']

def prefix_aliases():
	
	global aliases
	
	for item in aliases:
		item['originalTopic'] = prefix + item['originalTopic']
		item['newTopic'] = prefix + item['newTopic']

def generate_aliasesTopics(aliases):
	
	aliasesTopics = []
	for item in aliases:
		if not item['originalTopic'] in aliasesTopics:
			aliasesTopics.append(item['originalTopic'])
			
	return aliasesTopics

def generate_deviceList(devices):
	
	deviceList = []
	modules = ['DI', 'DO', 'AI', 'TEMP', 'IR', 'US', 'PWM', '433']
	
	for module in modules:
		if module in devices:
			for device in devices[module]:
				device['module'] = module
				deviceList.append(device)

	return deviceList

def generate_pin2device(deviceList):
	
	pin2device = {}
	for device in deviceList:
		pin2device[device['pin']] = device
	
	return pin2device

deviceList = generate_deviceList(devices)
pin2device = generate_pin2device(deviceList)

prefix_aliases()
aliasesTopics = generate_aliasesTopics(aliases)

ser = serial.Serial(config['serial']['port'], config['serial']['baudrate'], timeout=config['serial']['timeout'])

if (config['serial']['reset']):
	ser.setDTR(False)
	time.sleep(1)
	ser.flushInput()
	ser.setDTR(True)
	time.sleep(3)

def on_disconnect(mqttc, userdata, rc):

	print("# Called on_disconnect!")
	while True:
		try:
			if (mqttc.reconnect() == 0):
				print("# Reconnected successfully.")
				break
		except socket_error:
			pass

		time.sleep(1)

def on_message(mqttc, obj, msg):
	
	if (msg.topic in aliasesTopics):
		for item in aliases:
			if (item['originalTopic'] == msg.topic):
				if ('originalPayload' in item) and (msg.payload == item['originalPayload']):
					msg.topic = item['newTopic']
					msg.payload = item['newPayload']
					break
				elif ('originalPayload' not in item):
					msg.topic = item['newTopic']
					break

	if 'DO' in devices:
		for device in devices['DO']:
			
			if (msg.topic == prefix + device['mqtt_path'] + "/control"):
				if ( msg.payload in ("0", "1") ):
					cmd("DO_WRITE " + str(device['pin']) + " " + msg.payload)
					cmd("DO_GETSTATE " + str(device['pin']))

				return

			elif ( msg.topic == prefix + device['mqtt_path'] + "/getstate" ):
				cmd("DO_GETSTATE " + str(device['pin']))
				return

	if 'DI' in devices:
		for device in devices['DI']:
			if ( msg.topic == prefix + device['mqtt_path'] + "/read" ):
				cmd("DI_READ " + str(device['pin']))
				return

	if 'AI' in devices:
		for device in devices['AI']:
			if ( msg.topic == prefix + device['mqtt_path'] + "/read" ):
				cmd("AI_READ " + str(device['pin']))
				return

	if 'TEMP' in devices:
		for device in devices['TEMP']:
			if (device['submodule'] == 'DALLAS'):
				if ( msg.topic == prefix + device['mqtt_path'] + "/read" ):
					cmd("TEMP_READ " + str(device['pin']))
					return
	
			elif (device['submodule'] == 'DHT'): 
				if ( msg.topic == prefix + device['mqtt_path_temperature'] + "/read" ) or ( msg.topic == prefix + device['mqtt_path_humidity'] + "/read" ):
					cmd("TEMP_READ " + str(device['pin']))
					return
					
	if 'US' in devices:
		for device in devices['US']:
			if ( msg.topic == prefix + device['mqtt_path'] + "/read" ):
				cmd("US_READ " + str(device['pin_transmit']))
				return
			
	if 'PWM' in devices:
		for device in devices['PWM']:
			
			if (msg.topic == prefix + device['mqtt_path'] + "/control"):
				if (msg.payload.isdigit()) and (0 <= int(msg.payload)) and (int(msg.payload) <= 255):					
					cmd("PWM_WRITE " + str(device['pin']) + " " + msg.payload)
					cmd("PWM_GETSTATE " + str(device['pin']))

				return

			elif ( msg.topic == prefix + device['mqtt_path'] + "/getstate" ):
				cmd("PWM_GETSTATE " + str(device['pin']))
				return

	if '433' in devices:
		for device in devices['433']:
			if ( msg.topic == prefix + device['mqtt_path'] + "/send" ):
				cmd("433_SEND " + str(device['pin']) + " " + msg.payload)
				return

def on_connect(mqttc, userdata, flags, rc):
	mqttc.subscribe(prefix + "+/read", config['mqtt']['default_qos'])
	mqttc.subscribe(prefix + "+/control", config['mqtt']['default_qos'])
	mqttc.subscribe(prefix + "+/getstate", config['mqtt']['default_qos'])
	mqttc.subscribe(prefix + "+/send", config['mqtt']['default_qos'])

mqttc = mqtt.Client(client_id=config['mqtt']['client_id'], protocol=3)
mqttc.on_message = on_message
mqttc.on_connect = on_connect
mqttc.on_disconnect = on_disconnect

mqttc.username_pw_set(config['mqtt']['user'], config['mqtt']['password'])
mqttc.connect(config['mqtt']['server'], config['mqtt']['port'], config['mqtt']['timeout'])

mqttc.loop_start()

def cmd(line):
	ser.write(line + "\n")
	time.sleep(0.1)

cmd("SYS_CONFIG 99")
line = ser.readline().strip().strip('\n')
if (line == "SYS_CONFIG 1"):
	print("### Configured already, skipping configuration!")

elif (line == "SYS_CONFIG 0"):
	print("### Not configured, running configuration ... ")

	owRegd = False
	for device in deviceList:

		if (device['module'] == 'DI'):
			pullup = device['pullup'] if ('pullup' in device) else False
			if (pullup):
				cmd("DI_REG_PULLUP " + str(device['pin']))
			else:
				cmd("DI_REG " + str(device['pin']))

		elif (device['module'] == 'DO'):
			inverted = device['inverted'] if ('inverted' in device) else False
			inverted = ' I' if inverted else ''
				
			cmd("DO_REG " + str(device['pin']) + inverted)
			
			security_interval = device['security_interval'] if ('security_interval' in device) else 0
			if (security_interval):
				cmd("DO_SETSECINTERVAL " + str(device['pin']) + " " + str(security_interval))
					
		elif (device['module'] == 'AI'):
			cmd("AI_REG " + str(device['pin']))
			
			threshold = device['threshold'] if ('threshold' in device) else 1
			if (threshold):
				cmd("AI_SET_DIFFTHRSHLD " + str(device['pin']) + " " + str(threshold))
				
			enabled = device['enabled'] if ('enabled' in device) else False
			if (enabled):
				cmd("AI_ENABLE " + str(device['pin']))

		elif (device['module'] == 'TEMP'):
			if (device['submodule'] == 'DALLAS'):
				
				if (not owRegd):
					cmd("OW_REG " + str(device['pin']))
					owRegd = True
				
				cmd("TEMP_REG_DALLAS " + str(device['pin']) + " " + device['address'])
			elif (device['submodule'] == 'DHT'): 
				cmd("TEMP_REG_DHT11 " + str(device['pin']))
			elif (device['submodule'] == 'AURIOL433'): 
				cmd("TEMP_REG_AURIOL433 " + str(device['pin']))

		elif (device['module'] == 'IR'):
			cmd("IR_REG " + str(device['pin']))

		elif (device['module'] == 'US'):
			cmd("US_REG " + str(device['pin_transmit']) + " " + str(device['pin_echo']))

		elif (device['module'] == 'PWM'):		
			inverted = device['inverted'] if ('inverted' in device) else False
			inverted = ' I' if inverted else ''
			
			cmd("PWM_REG " + str(device['pin']) + inverted)

			security_interval = device['security_interval'] if ('security_interval' in device) else 0
			if (security_interval):
				cmd("PWM_SETSECINTERVAL " + str(device['pin']) + " " + str(security_interval))

		elif (device['module'] == '433'):		
			protocol = device['protocol'] if ('protocol' in device) else 1
			
			cmd("433_REG " + str(device['pin']) + " " + str(protocol))

	cmd("SYS_CONFIG 99 1")

else:
	sys.exit("### READING RUBBISH!")

lastRun = {
	'minute': 0,
	'second': 0
}

time.sleep(1);

if 'AI' in devices:
	for device in devices['AI']:
		cmd("AI_READ " + str(device['pin']))

if 'DO' in devices:
	for device in devices['DO']:
		cmd("DO_GETSTATE " + str(device['pin']))
	
if 'DI' in devices:
	for device in devices['DI']:
		cmd("DI_READ " + str(device['pin']))

while True:

	if ( lastRun['minute'] + 60 < time.time() ):
		lastRun['minute'] = time.time()

		if 'TEMP' in devices:
			for device in devices['TEMP']:
				cmd("TEMP_READ " + str(device['pin']))

		cmd("SYS_MEM 99")

	while ( ser.inWaiting() ):
		line = ser.readline().strip().strip('\n')
		print("# IN: " + line)
		
		module = None
		pin = None
		
		chunks = line.split(' ')
		if (len(chunks) > 0):
			module = chunks[0]
			
			if (len(chunks) > 1):
				pin = chunks[1]

		if (module in ["SYS_CONFIG", "SYS_MEM", "OK", "ERROR"]):
			break

		pin = int(pin)
		if (pin in pin2device) and (module == pin2device[pin]['module']):
			device = pin2device[pin]
			retain = device['retain'] if ('retain' in device) else False

			if ( module == "DI" ):
				mqttc.publish(prefix + device['mqtt_path'], chunks[2], config['mqtt']['default_qos'], retain)

			elif ( module == "DO" ):
				mqttc.publish(prefix + device['mqtt_path'], chunks[2], config['mqtt']['default_qos'], retain)
	
			elif ( module == "AI" ):
				mqttc.publish(prefix + device['mqtt_path'], chunks[2], config['mqtt']['default_qos'], retain)

			elif ( module == "TEMP" ):
									
				if (device['submodule'] == 'DALLAS'):
					mqttc.publish(prefix + device['mqtt_path'], chunks[2], config['mqtt']['default_qos'], retain)
				elif (device['submodule'] == 'DHT'): 
					if ( chunks[2] != "TIMEOUT" ) and ( chunks[2] != "CHECKSUM_ERROR" ):
						mqttc.publish(prefix + device['mqtt_path_temperature'], chunks[2], config['mqtt']['default_qos'], retain)
						mqttc.publish(prefix + device['mqtt_path_humidity'], chunks[3], config['mqtt']['default_qos'], retain)		
				elif (device['submodule'] == 'AURIOL433'):
					mqttc.publish(prefix + device['mqtt_path'], chunks[2], config['mqtt']['default_qos'], retain)
												
			elif ( module == "IR" ):
				mqttc.publish(prefix + device['mqtt_path'], chunks[2], config['mqtt']['default_qos'], retain)
						
			elif ( module == "US" ):
						
				if (chunks[2] == 'WAVE'):
					mqttc.publish(prefix + device['mqtt_path'] + "/wave", '', config['mqtt']['default_qos'], False)
				else:
					mqttc.publish(prefix + device['mqtt_path'], chunks[2], config['mqtt']['default_qos'], retain)
					
			elif ( module == "PWM" ):
				mqttc.publish(prefix + device['mqtt_path'], chunks[2], config['mqtt']['default_qos'], retain)
		else:
			print("Pin/module mismatch - this should never happen!")
			print("Module: " + module + "; Pin: " + pin + "; PinModule: " + pin2device[pin]['module'])
					
	time.sleep(0.1)
