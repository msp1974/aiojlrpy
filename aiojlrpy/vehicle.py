"""Class to represent a JLR vehicle"""


from datetime import datetime, timedelta
import logging
import uuid
from aiojlrpy.const import (
    ALERNATE_SERVICE_ID,
    NON_NOTIFICATION_SERVICES,
    HTTPContentType,
    HttpAccepts,
    JLRServices,
)
from aiojlrpy.utils import VehicleStatus, epoc_now, process_vhs_message


logger = logging.getLogger(__name__)


class Vehicle:
    """Vehicle class.

    You can request data or send commands to vehicle. Consult the JLR API documentation for details
    """

    def __init__(self, data: dict, connection):
        """Initialize the vehicle class."""
        self.connection = connection
        self.vin = data["vin"]
        self.role = data["role"]

    # Get vehicle data functions

    async def get_active_notification_target(self) -> dict | None:
        """Get notification target for this device id"""
        cf = await self.get_config()
        for n in cf.get("notificationTargets"):
            if self.connection.device_id in n.get("uri") and n.get("state") == "CONFIRMED":
                return n
        return None

    async def get_attributes(self) -> dict | None:
        """Get vehicle attributes"""
        headers = {"Accept": HttpAccepts.VEHICLE_ATTRIBUTES}
        return await self._get("attributes", headers)

    async def get_config(self) -> dict | None:
        """Get notification config"""
        return await self._get("config")

    async def get_contact_info(self, mcc: int) -> dict | None:
        """Get contact info for the specified mobile country code"""
        return await self._get(f"contactinfo/{mcc}")

    async def get_departure_timers(self) -> dict | None:
        """Get vehicle departure timers"""
        headers = {"Accept": HttpAccepts.DEPARTURE_TIMER_SETTINGS}
        return await self._get("departuretimers", headers)

    async def get_guardian_mode_alarms(self) -> dict | None:
        """Get Guardian Mode Alarms"""
        headers = {"Accept": HttpAccepts.GUARDIAN_STATUS}
        return await self._get("gm/alarms", headers)

    async def get_guardian_mode_alerts(self) -> dict | None:
        """Get Guardian Mode Alerts"""
        headers = {"Accept": HttpAccepts.GUARDIAN_ALERT}
        return await self._get("gm/alerts", headers)

    async def get_guardian_mode_status(self) -> dict | None:
        """Get Guardian Mode Status"""
        headers = {"Accept": HttpAccepts.GUARDIAN_STATUS}
        return await self._get("gm/status", headers)

    async def get_guardian_mode_settings_user(self) -> dict | None:
        """Get Guardian Mode User Settings"""
        headers = {"Accept": HttpAccepts.GUARDIAN_USER_SETTINGS}
        return await self._get("gm/settings/user", headers)

    async def get_guardian_mode_settings_system(self) -> dict | None:
        """Get Guardian Mode System Settings"""
        headers = {"Accept": HttpAccepts.GUARDIAN_SYSTEM_SETTINGS}
        return await self._get("gm/settings/system", headers)

    async def get_notification_available_services_list(self) -> list:
        """Get the services that can be registered for notifications"""
        services = []
        avs = (await self.get_attributes()).get("availableServices")
        for s in avs:
            if (
                s.get("vehicleCapable")
                and s.get("serviceEnabled")
                and s.get("serviceType") not in NON_NOTIFICATION_SERVICES
            ):
                service_id = s.get("serviceType")
                if service_id in ALERNATE_SERVICE_ID:
                    services.append(ALERNATE_SERVICE_ID[service_id])
                else:
                    services.append(s.get("serviceType"))
        return services

    async def get_position(self) -> dict | None:
        """Get current vehicle position"""
        return await self._get("position")

    async def get_rcc_target_value(self) -> dict | None:
        """Get Remote Climate Target Value"""
        return await self._get("settings/ClimateControlRccTargetTemp")

    async def get_service_status(self, service_id) -> dict | None:
        """Get status of called vehicle service"""
        headers = {"Accept": HttpAccepts.SERVICE_STATUS_V4}
        return await self._get(f"services/{service_id}", headers)

    async def get_services(self) -> dict | None:
        """Get services"""
        return await self._get("services")

    async def get_status(self) -> VehicleStatus | None:
        """Get vehicle status"""
        headers = {"Accept": HttpAccepts.HEALTH_STATUS}
        result = await self._get("status?includeInactive=true", headers)
        return process_vhs_message(result)

    async def get_subscription_packages(self) -> dict | None:
        """Get vehicle status"""
        headers = {"Accept": HttpAccepts.SUBSCRIPTION_PACKAGES}
        return await self._get("subscriptionpackages", headers)

    async def get_trip(self, trip_id, section=1) -> dict | None:
        """Get info on a specific trip"""
        return await self._get(f"trips/{trip_id}/route?pageSize=1000&page={section}")

    async def get_trips(self, count=1000) -> dict | None:
        """Get the last 1000 trips associated with vehicle"""
        headers = {"Accept": HttpAccepts.TRIPS}
        return await self._get(f"trips?count={count}", headers)

    async def get_waua_status(self) -> dict | None:
        """Get WAUA (doors unlocked notification) status."""
        headers = {"Accept": HttpAccepts.WUAU_STATUS}
        return await self._get("waua/status", headers)

    async def get_wakeup_time(self):
        """Get configured wakeup time for vehicle"""
        headers = {"Accept": HttpAccepts.WAKEUP_TIME}
        return await self._get("wakeuptime", headers)

    # Set vehicle parameter functions

    async def add_charging_period(
        self, index, schedule, hour_from, minute_from, hour_to, minute_to
    ):
        """Add charging period"""
        tariff_settings = {
            "tariffs": [
                {
                    "tariffIndex": index,
                    "tariffDefinition": {
                        "enabled": True,
                        "repeatSchedule": schedule,
                        "tariffZone": [
                            {
                                "zoneName": "TARIFF_ZONE_A",
                                "bandType": "PEAK",
                                "endTime": {"hour": hour_from, "minute": minute_from},
                            },
                            {
                                "zoneName": "TARIFF_ZONE_B",
                                "bandType": "OFFPEAK",
                                "endTime": {"hour": hour_to, "minute": minute_to},
                            },
                            {
                                "zoneName": "TARIFF_ZONE_C",
                                "bandType": "PEAK",
                                "endTime": {"hour": 0, "minute": 0},
                            },
                        ],
                    },
                }
            ]
        }

        return await self._charging_profile_control_command("tariffSettings", tariff_settings)

    async def add_departure_timer(self, index, year, month, day, hour, minute):
        """Add a single departure timer with the specified index"""
        departure_timer_setting = {
            "timers": [
                {
                    "departureTime": {"hour": hour, "minute": minute},
                    "timerIndex": index,
                    "timerTarget": {"singleDay": {"day": day, "month": month, "year": year}},
                    "timerType": {"key": "BOTHCHARGEANDPRECONDITION", "value": True},
                }
            ]
        }

        return await self._charging_profile_control_command(
            "departureTimerSetting", departure_timer_setting
        )

    async def add_repeated_departure_timer(self, index, schedule, hour, minute):
        """Add repeated departure timer."""
        departure_timer_setting = {
            "timers": [
                {
                    "departureTime": {"hour": hour, "minute": minute},
                    "timerIndex": index,
                    "timerTarget": {"repeatSchedule": schedule},
                    "timerType": {"key": "BOTHCHARGEANDPRECONDITION", "value": True},
                }
            ]
        }

        return await self._charging_profile_control_command(
            "departureTimerSetting", departure_timer_setting
        )

    async def delete_departure_timer(self, index):
        """Delete a single departure timer associated with the specified index"""
        departure_timer_setting = {"timers": [{"timerIndex": index}]}

        return await self._charging_profile_control_command(
            "departureTimerSetting", departure_timer_setting
        )

    async def delete_wakeup_time(self):
        """Stop the wakeup time"""
        swu_data = await self._authenticate_service("", JLRServices.WAKE_UP)
        swu_data["serviceCommand"] = "END"
        return await self._wakeup_timer_command(swu_data)

    async def set_attributes(self, nickname, registration_number) -> dict | None:
        """Set vehicle nickname and registration number"""
        attributes_data = {
            "nickname": nickname,
            "registrationNumber": registration_number,
        }
        return await self._post("attributes", data=attributes_data)

    async def request_vehicle_health_status_update(self) -> dict | None:
        """Get vehicle health status from vehicle"""
        headers = {
            "Accept": HttpAccepts.SERVICE_STATUS_V4,
            "Content-Type": HTTPContentType.SERVICE_CONFIG_V3,
        }
        vhs_data = await self._authenticate_service("", JLRServices.VEHICLE_HEALTH)
        return await self._post("healthstatus", headers, vhs_data)

    async def set_max_soc(self, max_charge_level):
        """Set max state of charge in percentage"""
        service_parameters = [{"key": "SET_PERMANENT_MAX_SOC", "value": max_charge_level}]

        return await self._charging_profile_control_command("serviceParameters", service_parameters)

    async def set_notification_target(self, services: list[str]) -> dict | None:
        """Set notifications for websockets"""
        headers = {"Content-Type": HTTPContentType.NOTIFICATION_TARGETS}
        uri = "pn:ws:{}:{}?APP=incontrol_jaguar_jlrdev_debug&SERVICE=APNS"
        data = {
            "expireAt": (datetime.utcnow() + timedelta(days=14)).strftime("%Y-%m-%dT%H:%M:00.000Z"),
            "name": "WebSocket Notifications",
            "services": services,
            "state": "CONFIRMED",
            "uri": uri.format(self.connection.device_id, str(uuid.uuid4())),
            "websocketVersion": 2,
        }
        return await self._post("config/notificationTargets", headers, data)

    async def set_one_off_max_soc(self, max_charge_level):
        """Set one off max state of charge in percentage"""
        service_parameters = [{"key": "SET_ONE_OFF_MAX_SOC", "value": max_charge_level}]
        return await self._charging_profile_control_command("serviceParameters", service_parameters)

    async def set_rcc_target_value(self, pin, target_value) -> dict | None:
        """Set Remote Climate Target Value (value between 31-57, 31 is LO 57 is HOT)"""
        await self.enable_provisioning_mode(pin)
        service_parameters = {
            "key": "ClimateControlRccTargetTemp",
            "value": str(target_value),
            "applied": 1,
        }
        return await self._post("settings", data=service_parameters)

    async def set_wakeup_time(self, wakeup_time):
        """Set the wakeup time for the specified time (epoch milliseconds)"""
        swu_data = await self._authenticate_service("", JLRServices.WAKE_UP)
        print(f"SWU DATA: {swu_data}")
        swu_data["serviceCommand"] = "START"
        swu_data["startTime"] = wakeup_time
        return await self._wakeup_timer_command(swu_data)

    # Vehicle actions

    async def charging_start(self):
        """Start charging"""
        service_parameters = [{"key": "CHARGE_NOW_SETTING", "value": "FORCE_ON"}]
        return await self._charging_profile_control_command("serviceParameters", service_parameters)

    async def charging_stop(self):
        """Stop charging"""
        service_parameters = [{"key": "CHARGE_NOW_SETTING", "value": "FORCE_OFF"}]
        return await self._charging_profile_control_command("serviceParameters", service_parameters)

    async def climate_prioritize(self, priority: str):
        """Optimize climate controls for comfort or range"""
        service_parameters = [{"key": "PRIORITY_SETTING", "value": priority}]
        return await self._preconditioning_control_command(service_parameters)

    async def disable_guardian_mode(self, pin: str):
        """Disable Guardian Mode"""
        return await self._gm_command(pin, 0, "DEACTIVATE")

    async def disable_privacy_mode(self, pin: str):
        """Disable privacy mode. Will enable journey logging"""
        return await self._prov_command(pin, None, "privacySwitch_off")

    async def disable_service_mode(self, pin: str):
        """Disable service mode."""
        return await self._prov_command(pin, epoc_now(), "protectionStrategy_serviceMode")

    async def disable_transport_mode(self, pin: str):
        """Disable transport mode"""
        return await self._prov_command(pin, epoc_now(), "protectionStrategy_transportMode")

    async def enable_guardian_mode(self, pin: str, expiration_time: int):
        """Enable Guardian Mode until the specified time (epoch millis)"""
        return await self._gm_command(pin, expiration_time, "ACTIVATE")

    async def enable_privacy_mode(self, pin: str):
        """Enable privacy mode. Will disable journey logging"""
        return await self._prov_command(pin, None, "privacySwitch_on")

    async def enable_provisioning_mode(self, pin: str):
        """Enable provisioning mode"""
        return self._prov_command(pin, None, "provisioning")

    async def enable_service_mode(self, pin: str, expiration_time: int):
        """Enable service mode. Will disable at the specified time (epoch millis)"""
        return await self._prov_command(pin, expiration_time, "protectionStrategy_serviceMode")

    async def enable_transport_mode(self, pin, expiration_time):
        """Enable transport mode. Will be disabled at the specified time (epoch millis)"""
        return await self._prov_command(pin, expiration_time, "protectionStrategy_transportMode")

    async def honk_blink(self):
        """Sound the horn and blink lights"""
        headers = {
            "Accept": HttpAccepts.SERVICE_STATUS_V4,
            "Content-Type": HTTPContentType.SERVICE_CONFIG_V3,
        }
        # Authenticates using last 4 digits of vin as pin
        hblf_data = await self._authenticate_service(self.vin[-4:], JLRServices.HONK_BLINK)
        return await self._post("honkBlink", headers, hblf_data)

    async def lock(self, pin: str):
        """Lock vehicle. Requires personal PIN for authentication"""
        headers = {"Content-Type": HTTPContentType.SERVICE_CONFIG_V3}
        rdl_data = await self._authenticate_service(pin, JLRServices.REMOTE_DOOR_LOCK)
        return await self._post("lock", headers, rdl_data)

    async def preconditioning_start(self, target_temp: int):
        """Start pre-conditioning for specified temperature (celsius)"""
        service_parameters = [
            {"key": "PRECONDITIONING", "value": "START"},
            {"key": "TARGET_TEMPERATURE_CELSIUS", "value": str(target_temp)},
        ]
        return await self._preconditioning_control_command(service_parameters)

    async def preconditioning_stop(self):
        """Stop climate preconditioning"""
        service_parameters = [{"key": "PRECONDITIONING", "value": "STOP"}]
        return await self._preconditioning_control_command(service_parameters)

    async def remote_engine_start(self, pin: str, target_value: int):
        """Start Remote Engine preconditioning"""
        headers = {"Content-Type": HTTPContentType.SERVICE_CONFIG_V2}
        await self.set_rcc_target_value(pin, target_value)
        reon_data = await self._authenticate_service(pin, JLRServices.REMOTE_ENGINE_ON)
        return await self._post("engineOn", headers, reon_data)

    async def remote_engine_stop(self, pin: str):
        """Stop Remote Engine preconditioning"""
        headers = {"Content-Type": HTTPContentType.SERVICE_CONFIG_V2}
        reoff_data = await self._authenticate_service(pin, JLRServices.REMOTE_ENGINE_OFF)

        return await self._post("engineOff", headers, reoff_data)

    async def reset_alarm(self, pin: str):
        """Reset vehicle alarm"""
        headers = {
            "Content-Type": HTTPContentType.SERVICE_CONFIG_V3,
            "Accept": HttpAccepts.SERVICE_STATUS_V4,
        }
        aloff_data = await self._authenticate_service(pin, JLRServices.ALARM_OFF)
        return await self._post("unlock", headers, aloff_data)

    async def unlock(self, pin: str):
        """Unlock vehicle. Requires personal PIN for authentication"""
        headers = {"Content-Type": HTTPContentType.SERVICE_CONFIG_V3}
        rdu_data = await self._authenticate_service(pin, JLRServices.REMOTE_DOOR_UNLOCK)
        return await self._post("unlock", headers, rdu_data)

    # Internal helper functions

    async def _charging_profile_control_command(
        self, service_parameter_key: str, service_parameters: list
    ):
        """Charging profile API"""
        headers = {
            "Accept": HttpAccepts.SERVICE_STATUS_V5,
            "Content-Type": HTTPContentType.PHEV_SERVICE,
        }
        # Authenticates using last 4 digits of vin as pin
        cp_data = await self._authenticate_service(self.vin[-4:], JLRServices.CHARGE_PROFILE)
        cp_data[service_parameter_key] = service_parameters
        return await self._post("chargeProfile", headers, cp_data)

    async def _gm_command(self, pin: str, expiration_time: int, action: str):
        """Send GM toggle command"""
        headers = {"Accept": HttpAccepts.GUARDIAN_ALARM_LIST}
        gm_data = await self._authenticate_service(pin, JLRServices.GUARDIAN_MODE)
        if action == "ACTIVATE":
            gm_data["endTime"] = expiration_time
            gm_data["status"] = "ACTIVE"
            return await self._post("gm/alarms", headers, gm_data)
        if action == "DEACTIVATE":
            headers.update({"X-servicetoken": gm_data.get("token")})
            return await self._delete("gm/alarms/INSTANT", headers)

    async def _preconditioning_control_command(self, service_parameters: list):
        """Control the climate preconditioning"""
        headers = {
            "Accept": HttpAccepts.SERVICE_STATUS_V5,
            "Content-Type": HTTPContentType.PHEV_SERVICE,
        }
        # Authenticates using last 4 digits of vin as pin
        ecc_data = await self._authenticate_service(
            self.vin[-4:], JLRServices.ELECTRIC_CLIMATE_CONTROL
        )
        ecc_data["serviceParameters"] = service_parameters
        return await self._post("preconditioning", headers, ecc_data)

    async def _prov_command(self, pin: str, expiration_time: int, mode: str):
        """Send prov endpoint commands. Used for service/transport/privacy mode"""
        headers = {"Content-Type": HTTPContentType.SERVICE_CONFIG_V3}
        prov_data = await self._authenticate_service(pin, JLRServices.PROVISIONING_MODE)
        prov_data.update({"serviceCommand": mode, "startTime": None, "endTime": expiration_time})
        return await self._post("prov", headers, prov_data)

    async def _wakeup_timer_command(self, swu_data: dict):
        """Set the wakeup time for the specified time (epoch milliseconds)"""
        headers = {
            "Accept": HttpAccepts.SERVICE_STATUS_V4,
            "Content-Type": HTTPContentType.SERVICE_CONFIG_V3,
        }
        return await self._post("swu", headers, swu_data)

    async def _authenticate_service(self, pin: str, service_name: str):
        """Authenticate to specified service with the provided PIN"""
        headers = {"Content-Type": HTTPContentType.AUTH_REQUEST}
        data = {"serviceName": service_name, "pin": str(pin)}
        return await self._post(f"users/{self.connection.user_id}/authenticate", headers, data)

    # Internal http method functions

    async def _get(self, command: str, headers: dict | None = None):
        """Utility command to get vehicle data from API"""
        return await self.connection.get(
            command, f"{self.connection.base.IF9}/vehicles/{self.vin}", headers
        )

    async def _post(self, command: str, headers: dict | None = None, data: dict | None = None):
        """Utility command to post data to VHS"""
        return await self.connection.post(
            command, f"{self.connection.base.IF9}/vehicles/{self.vin}", headers, data
        )

    async def _delete(self, command: str, headers: dict | None = None):
        """Utility command to delete active service entry"""
        return await self.connection.delete(
            command, f"{self.connection.base.IF9}/vehicles/{self.vin}", headers
        )
