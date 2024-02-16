# aiojlrpy

Python 3 Async library for interacting with the JLR Remote car rest and websocket APIs.

## Installation

Either check out this repository directly or install through pip (for Python3).

`pip install aiojlrpy`

## Usage

NOTE:  This is an async library, therefore must be run in a running event loop.

To get started, instantiate a `Connection` object and pass along the email address and password associated with your Jaguar InControl account.

There are two ways to authenticate to InControl. Using the user name and password or with a valid refresh token.

The JLR API requires a device ID to be registered (UUID4 formatted). If you do not specify one when instantiating the `Connection` object it will generate a new one for your automatically. However, it is highly recommended to provide a consistant device ID for your connection, especially if using the websocket function.

InControl provides 2 different APIs.

REST API
The main api to get vehicle data and perform actions on your account/vehicle

Websocket API
A push api that provides messages when things happen on your vehicle for service calls and things which update status attributes and alerts.  A status message is formatted from the library into a strucutred StatusMessage class object.

```python
from aiojlrpy import Connection, Vehicle, StatusMessage

# Authenticate just the rest api using the username, password.
c = Connection(
    EMAIL,
    PWD,
    device_id=DEVICEID,
)
await c.connect()
v = c.vehicles[0]

# Authenticate and enable the websocket connection (highly recommended to provide a fixed device id here).
# on_message is a callback function in your code to receive websocket messages
c = Connection(
        EMAIL,
        PWD,
        device_id=DEVICE_ID,
        ws_message_callback=on_message,
    )
    await c.connect()

async def on_message(message: StatusMessage):
    print(message)

# Authenticate using a refresh token (username must still be specified)
c = Connection(email='my@email.com', refresh_token='124c3f21-42ds-2e4d-86f8-221v32392a1d')
await c.connect()

```

`Connection.vehicles` will list all vehicles associated with your account.

```python
# Get user information
await c.get_user_info()
# Update user information.
p = await c.get_user_info()
p['contact']['userPreferences']['unitsOfMeasurement'] = "Km Litre Celsius VolPerDist Wh DistPerkWh"
await c.update_user_info(p)
# Refresh access token
await c.refresh_tokens()
# Get attributes associated with vehicle
await v.get_attributes()
# Get current status of vehicle
await v.get_status()
# Get current active services
await v.get_services()
# Optionally, you can also specify a status value key
await v.get_status("EV_STATE_OF_CHARGE")
# Get subscription packes
await v.get_subscription_packages()
# Get trip data (last 1000 trips).
await v.get_trips()
# Get data for a single trip (specified with trip id)
await v.get_trip(121655021)
# Get vehicle health status
await v.request_health_status()
# Get departure timers
await v.get_departure_timers()
# Get configured wakeup time
await v.get_wakeup_time()
# Honk horn and blink lights
await v.honk_blink()
# Get current position of vehicle
await v.get_position()
# Start preconditioning at 21.0C
await v.preconditioning_start("210")
# Stop preconditioning
await v.precenditioning_stop()
# Set vehicle nickname and registration number
await v.set_attributes("Name", "reg-number")
# Lock vehicle
await v.lock(pin) # pin being the personal master pin
# Unlock vehicle
await v.unlock(pin)
# Reset alarm
await v.reset_alarm(pin)
# Start charging
await v.charging_start()
# Stop charging
await v.charging_stop()
# Set max soc at 80% (Requires upcoming OTA update)
await v.set_max_soc(80)
# Set max soc for current charging session to 90% (Requires upcoming OTA update)
await v.set_one_off_max_soc(90)
# Add single departure timer (index, year, month, day, hour, minute)
await v.add_departure_timer(10, 2019, 1, 30, 20, 30)
# Delete a single departure timer index.
await v.delete_departure_timer(10)
# Schedule repeated departure timer.
schedule = {"friday":False,"monday":True,"saturday":False,"sunday":False,"thursday":False,"tuesday":True,"wednesday":True}
await v.add_repeated_departure_timer(10, 20, 30, schedule)
# Set wakeup timer (epoch millis)
await v.set_wakeup_time(1547845200000)
# Cancel wakeup timer
await v.delete_wakeup_time()
# Enable service mode (requires personal PIN)
await v.enable_service_mode("1234", 1547551847000)
# Enable transport mode (requires personal PIN)
await v.enable_transport_mode("1234", 1547551847000)
# Enable privacy mode
await v.enable_privacy_mode("1234")
# Disable privacy mode
await v.disable_privacy_mode("1234")
# Add charging period with specified index identifier value.
await v.add_charging_period(1, schedule, 0, 30, 8, 45)
# Reverse geocode
await c.reverse_geocode(59.915475,10.733054)
```

## Examples

The examples directory contains example scripts that put aiojlrpy to good use. #TODO

### Credits

Huge shout out to @ardedv for his tremendous work in jlypy which this library uses as a base.
