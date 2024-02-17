"""Constants to support aiojlrpy"""
from enum import StrEnum

TIMEOUT = 15


class BaseURLs:
    """Rest Of World Base URLs"""

    IFAS = "https://ifas.prod-row.jlrmotor.com/ifas/jlr"
    IFOP = "https://ifop.prod-row.jlrmotor.com/ifop/jlr"
    IF9 = "https://if9.prod-row.jlrmotor.com/if9/jlr"


class ChinaBaseURLs:
    """China Base URLs"""

    IFAS = "https://ifas.prod-chn.jlrmotor.com/ifas/jlr"
    IFOP = "https://ifop.prod-chn.jlrmotor.com/ifop/jlr"
    IF9 = "https://ifoa.prod-chn.jlrmotor.com/if9/jlr"


WS_DESTINATION_DEVICE = "/user/topic/DEVICE.{}"
WS_DESTINATION_VIN = "/user/topic/VIN.{}"

NON_NOTIFICATION_SERVICES = ["CI", "ECALL", "JL", "TNS5", "VHC"]
ALERNATE_SERVICE_ID = {"GMCC": "GM"}


class JLRServices(StrEnum):
    """Service codes"""

    ALARM_OFF = "ALOFF"
    CHARGE_PROFILE = "CP"
    ELECTRIC_CLIMATE_CONTROL = "ECC"
    GUARDIAN_MODE = "GM"
    HONK_BLINK = "HBLF"
    PROVISIONING_MODE = "PROV"
    REMOTE_DOOR_LOCK = "RDL"
    REMOTE_DOOR_UNLOCK = "RDU"
    REMOTE_ENGINE_ON = "REON"
    REMOTE_ENGINE_OFF = "REOFF"
    WAKE_UP = "SWU"
    VEHICLE_HEALTH = "VHS"


class HttpAccepts(StrEnum):
    """Accept strings for headers"""

    JSON = "application/json"
    TEXT = "text/plain"
    DEPARTURE_TIMER_SETTINGS = "application/vnd.wirelesscar.ngtp.if9.DepartureTimerSettings-v1+json"
    GUARDIAN_ALARM_LIST = "application/vnd.wirelesscar.ngtp.if9.GuardianAlarmList-v1+json"
    GUARDIAN_ALERT = "application/wirelesscar.GuardianAlert-v1+json"
    GUARDIAN_USER_SETTINGS = "application/vnd.wirelesscar.ngtp.if9.GuardianUserSettings-v1+json"
    GUARDIAN_STATUS = "application/vnd.wirelesscar.ngtp.if9.GuardianStatus-v1+json"
    GUARDIAN_SYSTEM_SETTINGS = "application/vnd.wirelesscar.ngtp.if9.GuardianSystemSettings-v1+json"
    HEALTH_STATUS = "application/vnd.ngtp.org.if9.healthstatus-v4+json"
    SERVICE_STATUS_V4 = "application/vnd.wirelesscar.ngtp.if9.ServiceStatus-v4+json"
    SERVICE_STATUS_V5 = "application/vnd.wirelesscar.ngtp.if9.ServiceStatus-v5+json"
    SUBSCRIPTION_PACKAGES = "application/vnd.wirelesscar.ngtp.if9.SubscriptionPackages-v2+json"
    TRIPS = "application/vnd.ngtp.org.triplist-v2+json"
    USER = "application/vnd.wirelesscar.ngtp.if9.User-v3+json"
    VEHICLE_ATTRIBUTES = "application/vnd.ngtp.org.VehicleAttributes-v8+json"
    WAKEUP_TIME = "application/vnd.wirelesscar.ngtp.if9.VehicleWakeupTime-v2+json"
    WUAU_STATUS = "application/wirelesscar.WauaStatus-v1+json"


class HTTPContentType(StrEnum):
    """Content-Type strings for headers"""

    JSON = "application/json"
    AUTH_REQUEST = "application/vnd.wirelesscar.ngtp.if9.AuthenticateRequest-v2+json; charset=utf-8"
    NOTIFICATION_TARGETS = "application/vnd.wirelesscar.ngtp.if9.NotificationTargets-v2+json"
    PHEV_SERVICE = "application/vnd.wirelesscar.ngtp.if9.PhevService-v1+json; charset=utf-8"
    SERVICE_CONFIG_V2 = "application/vnd.wirelesscar.ngtp.if9.StartServiceConfiguration-v2+json"
    SERVICE_CONFIG_V3 = (
        "application/vnd.wirelesscar.ngtp.if9.StartServiceConfiguration-v3+json; charset=utf-8"
    )
    USER = "application/vnd.wirelesscar.ngtp.if9.User-v3+json; charset=utf-8"
