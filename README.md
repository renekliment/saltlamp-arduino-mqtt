saltlamp-arduino-mqtt
=====================

This is a relay that connects an Arduino on the serial port (loaded with the saltlamp-arduino) to an MQTT broker.
In a way, it works like MySensors, but requires the Arduino with the sensors to be connected via serial cable connection.

It is supposed to be run like `./saltlamp-arduino-mqtt.py configuration.yaml`. You can write a simple service (for example systemd) file to run it for you on system boot. Just make sure you use absolute paths to be sure that the configuration file will be found correctly.

To run this, you need to:
* have respective python modules installed (see the head of the .py file)
* have an Arduino (or a similar board) loaded with saltlamp-arduino and connected via serial port (USB)
* have a proper configuration file - the template is pretty self-explanatory, for saltlamp-arduino specific options, see the project's documentation

It has been tested and works great on OpenWRT routers (RouterStation Pro, Turris, TP-Link TL-WDR4300) and small computers (Cubieboard).
