"""extronlib.system: MESet and ProgramLog - the two a panel program leans on."""
from . import record


def ProgramLog(Entry, Severity='error'):
    if Severity not in ('info', 'warning', 'error'):
        raise ValueError('ProgramLog severity is info, warning or error')
    record('ProgramLog', Severity, str(Entry))


class MESet:
    """Mutually exclusive set: SetCurrent turns one member On and the rest Off."""

    def __init__(self, Objects):
        for o in Objects:
            if not hasattr(o, 'SetState'):
                raise TypeError('MESet members need SetState')
        self.Objects = list(Objects)
        self._current = None
        self._states = {}

    def SetStates(self, obj, offState, onState):
        self._states[id(obj)] = (offState, onState)

    def GetCurrent(self):
        return self._current

    def SetCurrent(self, obj):
        if isinstance(obj, int) and not isinstance(obj, bool):
            obj = self.Objects[obj]
        if obj is not None and obj not in self.Objects:
            raise ValueError('{0!r} is not in this MESet'.format(obj))
        self._current = obj
        for o in self.Objects:
            off, on = self._states.get(id(o), (0, 1))
            o.SetState(on if o is obj else off)
        record('MESet', 'SetCurrent', getattr(obj, 'ID', None))
