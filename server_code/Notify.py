# Notify — Server Module. Emails about reservations (guest confirmations, staff approval alerts).
# Every caller wraps this in try/except: a failed email must never break a booking.


def reservation_event(res, event, before=None):
    """event: created | changed | cancelled | confirmed | declined. Phase 1 sends nothing."""
    return None
