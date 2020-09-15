from enum import Enum


class ErrorCode(Enum):
    MISSED_PARAS = 1000
    TIME_OUT = 1001
    CONNECTION_ERROR = 1002
    CHILLER_ERROR = 1003
    TOKEN_EXPIRED = 1010
    USER_UNPAID = 2001
    SUCCESS = 0
    UNKNOWN = -1

class ScbeEvent(Enum):
    SCBE_SESSION_DONE_PAYMENT = "scbe_session_done_payment"
    USER_DOOR_TIMED_OUT = "user_door_timed_out"
    USER_DOOR_LEFT_OPEN = "user_door_left_open"
    USER_SESSION_NOT_STARTED = "user_session_not_started"
    EXPIRED_TAGS_IN_ORDER = "expired_tags_in_order"
    STOCK_ALERT_NOTIFICATION = "stock_alert_notification"
    DOOR_CLOSED_NOTIFICATION = "door_closed_notification"
    TIMEOUT_PARTNER = "timeout_partner"
