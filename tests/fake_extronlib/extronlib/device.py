"""extronlib.device, as far as a panel program uses it."""
from . import record


def _name(kind, v):
    if not isinstance(v, str):
        raise TypeError('{0} addressed by {1!r}: this toolkit addresses pages and popups by '
                        'NAME, because Build does not keep their numbers'.format(kind, v))


class UIDevice:
    EVENTS = {'Online': 2, 'Offline': 2, 'InactivityChanged': 2, 'SleepChanged': 2,
              'BrightnessChanged': 2, 'LidChanged': 2, 'LightChanged': 2,
              'MotionDetected': 2, 'HDCPStatusChanged': 2, 'InputPresenceChanged': 2}

    def __init__(self, DeviceAlias, PartNumber=None):
        if not isinstance(DeviceAlias, str) or not DeviceAlias:
            raise TypeError('UIDevice needs a DeviceAlias string')
        self.DeviceAlias = DeviceAlias
        self.page = None
        self.popups = []
        self.InactivityTime = []

    def __repr__(self):
        return 'UIDevice({0!r})'.format(self.DeviceAlias)

    def ShowPage(self, page):
        _name('page', page)
        self.page = page
        record(self.DeviceAlias, 'ShowPage', page)

    def ShowPopup(self, popup, duration=0):
        _name('popup', popup)
        if isinstance(duration, bool) or not isinstance(duration, (int, float)) or duration < 0:
            raise ValueError('duration must be a non-negative number of seconds')
        if popup not in self.popups:
            self.popups.append(popup)
        record(self.DeviceAlias, 'ShowPopup', popup, duration)

    def HidePopup(self, popup):
        _name('popup', popup)
        if popup in self.popups:
            self.popups.remove(popup)
        record(self.DeviceAlias, 'HidePopup', popup)

    def HideAllPopups(self):
        del self.popups[:]
        record(self.DeviceAlias, 'HideAllPopups')

    def HidePopupGroup(self, group):
        if not isinstance(group, int):
            raise TypeError('HidePopupGroup takes a group NUMBER')
        record(self.DeviceAlias, 'HidePopupGroup', group)

    def SetInactivityTime(self, times):
        if not isinstance(times, list) or not all(
                isinstance(t, (int, float)) and not isinstance(t, bool) and t > 0
                for t in times):
            raise TypeError('SetInactivityTime takes a list of positive seconds')
        self.InactivityTime = list(times)
        record(self.DeviceAlias, 'SetInactivityTime', list(times))
