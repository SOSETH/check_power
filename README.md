# check_power

Checks E3METER power strips via SNMP. We only do a simple average comparison at
the moment which should be improved at some point.

## Note
LICENSE (GPLv3) does not apply to `e3meter-ipm.mib` (file provided by manufacturer)

## How to use
To use this with Icinga2, you'll need to define a command:
```
object CheckCommand "power" {
  import "plugin-check-command"
  command = [PluginDir + "/check_power.py" ]

  arguments = {
    "-h" = {
      value = "$my_ip$"
      description = "Device to check"
      required = true
      skip_key = true
      order = 2
    }
    "-s" = {
      value = "$my_statefile$"
      description = "Path to state file for historical data"
      required = true
      order = 1
    }
    "--debug" = {
      value = "--debug"
      skip_key = true
    }
  }
  vars.my_ip = "$ip$"
  vars.my_statefile = "$statefile$"
}
```
and a matching template
```
apply Service "power " for (power => config in host.vars.power) {
  import "normal-service"
  check_command = "power"

  vars += config
  vars.datgroup = "power"
  vars.datitem = power
}
```
and finally annotate your hosts with:
```
  vars.power["Name for check"] = {
    ip = "192.168.0.1"
    statefile = "/tmp/pwr_name_for_check"
  }
```
