"""Domain enumerations shared by persistence and API layers."""
from enum import Enum


class StrEnum(str, Enum):
    pass


class ParticipantRole(StrEnum): ORGANISER = "ORGANISER"; PARTICIPANT = "PARTICIPANT"
class SessionStatus(StrEnum): ACTIVE = "ACTIVE"; CONFIRMED = "CONFIRMED"; CANCELLED = "CANCELLED"
class ResponseStatus(StrEnum): NOT_SUBMITTED = "NOT_SUBMITTED"; SUBMITTED = "SUBMITTED"; WITHDRAWN = "WITHDRAWN"
class TransportMode(StrEnum): WALK = "WALK"; DRIVE = "DRIVE"; PUBLIC_TRANSPORT = "PUBLIC_TRANSPORT"
class TravelObjective(StrEnum): MIN_TOTAL = "MIN_TOTAL"; MIN_MAX_INDIVIDUAL = "MIN_MAX_INDIVIDUAL"
class VenueCategory(StrEnum): SPORTS_FACILITY = "SPORTS_FACILITY"; PARK = "PARK"; MALL = "MALL"
class LocationInputType(StrEnum): ADDRESS = "ADDRESS"; POSTAL_CODE = "POSTAL_CODE"
class GeocodeStatus(StrEnum): PENDING = "PENDING"; VALID = "VALID"; INVALID = "INVALID"; UNAVAILABLE = "UNAVAILABLE"
class SubmissionSource(StrEnum): MANUAL = "MANUAL"; CALENDAR_ASSISTED = "CALENDAR_ASSISTED"
class RecordStatus(StrEnum): ACTIVE = "ACTIVE"; WITHDRAWN = "WITHDRAWN"
class IntervalType(StrEnum): AVAILABLE = "AVAILABLE"; BUSY = "BUSY"
class IntervalSource(StrEnum): MANUAL = "MANUAL"; GOOGLE_CALENDAR = "GOOGLE_CALENDAR"
class SupportStatus(StrEnum): SUPPORTED = "SUPPORTED"; UNAVAILABLE = "UNAVAILABLE"
class GenerationStatus(StrEnum): GENERATED = "GENERATED"; INVALIDATED = "INVALIDATED"
class AttendanceStatus(StrEnum): AVAILABLE = "AVAILABLE"; UNAVAILABLE = "UNAVAILABLE"; NO_RESPONSE = "NO_RESPONSE"; WITHDRAWN = "WITHDRAWN"
class AttendanceSource(StrEnum): MANUAL = "MANUAL"; CALENDAR = "CALENDAR"; NONE = "NONE"
class ShortlistStatus(StrEnum): CURRENT = "CURRENT"; INVALIDATED = "INVALIDATED"
class RoutingStatus(StrEnum): AVAILABLE = "AVAILABLE"; UNAVAILABLE = "UNAVAILABLE"; ERROR = "ERROR"
class FeasibilityStatus(StrEnum): FEASIBLE = "FEASIBLE"; EXCLUDED = "EXCLUDED"; DATA_UNAVAILABLE = "DATA_UNAVAILABLE"
class CombinationStatus(StrEnum): CANDIDATE = "CANDIDATE"; EXCLUDED = "EXCLUDED"; CONFIRMED = "CONFIRMED"
class CalendarProvider(StrEnum): GOOGLE = "GOOGLE"
class ConnectionStatus(StrEnum): CONNECTED = "CONNECTED"; DISCONNECTED = "DISCONNECTED"; DECLINED = "DECLINED"; EXPIRED = "EXPIRED"; ERROR = "ERROR"
class EventType(StrEnum): TENTATIVE_HOLD = "TENTATIVE_HOLD"; CONFIRMED_EVENT = "CONFIRMED_EVENT"
class EventStatus(StrEnum): PENDING = "PENDING"; ACTIVE = "ACTIVE"; DELETED = "DELETED"; ERROR = "ERROR"

