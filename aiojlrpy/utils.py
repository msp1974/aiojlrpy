"""Helper utils"""
from dataclasses import dataclass, field
from datetime import datetime, timezone
import time


@dataclass
class Alert:
    """Alert"""

    name: str
    value: str
    active: bool
    last_updated: datetime


@dataclass
class VehicleStatus:
    """Class to hold vehicle status"""

    data: dict = None
    core: dict = None
    ev: dict = None
    alerts: list[Alert] = field(default_factory=list)
    last_updated_time: datetime = None
    last_updated_time_vehicle_status: datetime = None
    last_updated_time_vehicle_alert: datetime = None


def process_vhs_message(data: dict) -> VehicleStatus:
    """Load status data into JLRVehicleStatus object"""
    s = VehicleStatus(data=data)
    for key in data:
        if key == "vehicleStatus":
            for status_type in data[key]:
                if status_type == "coreStatus":
                    s.core = {d["key"]: d["value"] for d in data[key][status_type]}
                if status_type == "evStatus":
                    s.ev = {d["key"]: d["value"] for d in data[key][status_type]}
        if key == "vehicleAlerts":
            s.alerts = [
                Alert(
                    d["key"],
                    d["value"],
                    d["active"],
                    _local_datetime_from_utc(d["lastUpdatedTime"]),
                )
                for d in data[key]
            ]
        if key == "lastUpdatedTime":
            s.last_updated_time = _local_datetime_from_utc(data[key])
        if key == "lastUpdatedTimeVehicleStatus":
            s.last_updated_time_vehicle_status = _local_datetime_from_utc(data[key])
        if key == "lastUpdatedTimeVehicleAlert":
            s.last_updated_time_vehicle_alert = _local_datetime_from_utc(data[key])
    return s


def epoc_now():
    """Returns now as epoc time"""
    return int(time.time() * 1000)


def epoc_from_datetime(dt: datetime) -> int:
    """Returns epoc of datetime"""
    return int(dt.strftime("%s"))


def _local_datetime_from_utc(dt_str: str) -> datetime | str:
    """Convert niave utc datetime to local datetime.  Return dt if fails"""
    if dt_str:
        try:
            dt_str = dt_str.replace("+0000", ".000Z")
            dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%S.%fZ")
            utc = dt.replace(tzinfo=timezone.utc)
            return utc
        except ValueError:
            return dt_str
