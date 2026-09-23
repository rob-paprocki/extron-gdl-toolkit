"""extronlib.ui: Button, Label, Level, Slider - their documented surface only."""
from . import HANDLERS, record
from .device import UIDevice


def _host(h):
    if not isinstance(h, UIDevice):
        raise TypeError('UIHost must be a UIDevice')


def _id(v):
    if isinstance(v, bool) or not isinstance(v, int):
        raise TypeError('generated code addresses controls by int ID, got {0!r}'.format(v))


class _Control:
    def __init__(self, UIHost, ID):
        _host(UIHost)
        _id(ID)
        self.Host, self.ID = UIHost, ID
        self.Visible = True

    def __repr__(self):
        return '{0}({1})'.format(type(self).__name__, self.ID)

    def _label(self):
        return '{0}({1})'.format(type(self).__name__, self.ID)

    def SetVisible(self, visible):
        self.Visible = bool(visible)
        record(self._label(), 'SetVisible', visible)


class Button(_Control):
    EVENTS = {'Pressed': 2, 'Released': 2, 'Held': 2, 'Repeated': 2, 'Tapped': 2}

    def __init__(self, UIHost, ID, holdTime=None, repeatTime=None):
        _Control.__init__(self, UIHost, ID)
        for t in (holdTime, repeatTime):
            if t is not None and (isinstance(t, bool) or not isinstance(t, (int, float))):
                raise TypeError('holdTime / repeatTime are seconds')
        self.holdTime, self.repeatTime = holdTime, repeatTime
        self.State = 0
        self.Enabled = True

    def SetState(self, State):
        if isinstance(State, bool) or not isinstance(State, int):
            raise TypeError('SetState takes an int state')
        self.State = State
        record(self._label(), 'SetState', State)

    def SetText(self, text):
        if not isinstance(text, str):
            raise TypeError('SetText takes a string')
        record(self._label(), 'SetText', text)

    def SetEnable(self, enable):
        self.Enabled = bool(enable)
        record(self._label(), 'SetEnable', enable)

    def fire(self, name):
        # Held / Repeated / Tapped are timers inside the Button, defined
        # relative to holdTime (Repeated also on repeatTime). The panel itself
        # only ever sends Pressed and Released.
        if name in ('Held', 'Tapped') and self.holdTime is None:
            raise RuntimeError('{0} cannot fire on a Button with no holdTime'.format(name))
        if name == 'Repeated' and (self.holdTime is None or self.repeatTime is None):
            raise RuntimeError('Repeated needs holdTime and repeatTime')
        if name in ('Released', 'Tapped') and self.holdTime is not None:
            # Which one a release raises depends on how long it was held, so
            # firing either by name would hide the substitution below.
            raise RuntimeError('with holdTime set, use release(held) - a quick release is '
                               'Tapped, not Released')
        h = HANDLERS.get((id(self), name))
        if h:
            h(self, name)
        return h is not None

    def release(self, held):
        """Let go after `held` seconds. The reference: "If button is released
        before holdTime expires, a Tapped event is triggered instead of a
        Released event." Returns the event that fired."""
        name = 'Tapped' if self.holdTime is not None and held < self.holdTime else 'Released'
        h = HANDLERS.get((id(self), name))
        if h:
            h(self, name)
        return name


class Label(_Control):
    EVENTS = {}

    def SetText(self, text):
        if not isinstance(text, str):
            raise TypeError('Label.SetText takes a string')
        record(self._label(), 'SetText', text)


class Level(_Control):
    EVENTS = {}

    def __init__(self, UIHost, ID):
        _Control.__init__(self, UIHost, ID)
        self.Min, self.Max, self.Level = None, None, None

    def SetRange(self, Min, Max, Step=1):
        self.Min, self.Max = Min, Max
        record(self._label(), 'SetRange', Min, Max)

    def SetLevel(self, Level):
        if isinstance(Level, bool) or not isinstance(Level, (int, float)):
            raise TypeError('SetLevel takes a number')
        self.Level = Level
        record(self._label(), 'SetLevel', Level)


class Slider(_Control):
    EVENTS = {'Pressed': 3, 'Released': 3, 'Changed': 3}

    def __init__(self, UIHost, ID):
        _Control.__init__(self, UIHost, ID)
        self.Min, self.Max, self.Fill = 0, 100, 0

    def SetRange(self, Min, Max, Step=1):
        self.Min, self.Max = Min, Max
        record(self._label(), 'SetRange', Min, Max)

    def SetFill(self, Fill):
        if isinstance(Fill, bool) or not isinstance(Fill, (int, float)):
            raise TypeError('SetFill takes a number')
        self.Fill = Fill
        record(self._label(), 'SetFill', Fill)

    def SetEnable(self, enable):
        record(self._label(), 'SetEnable', enable)

    def fire(self, name, value):
        h = HANDLERS.get((id(self), name))
        if h:
            h(self, name, value)
        return h is not None
