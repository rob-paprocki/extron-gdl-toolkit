"""A stand-in for Extron's extronlib, strict where the real one is strict.

The generated program cannot run here for real - extronlib only exists on a
control processor. This fake lets tests import and drive it anyway, and it is
deliberately NOT a passive mock: it enforces the contracts the ControlScript
reference documents, so a generator that emits a wrong event name, a handler
with the wrong arity, or a page NUMBER where a name is required fails here
rather than on a panel.

Every call it sees is recorded in JOURNAL as (object label, method, args).

What it enforces, each from Extron's own reference (docs/behavior.md):
  * event names per class, and handler arity (Button 2, Slider 3, UIDevice 2)
  * one handler per (object, event) - the last assignment wins
  * Held / Repeated / Tapped only fire on a Button given holdTime
  * ShowPage / ShowPopup / HidePopup take a NAME here. The real API also
    accepts a number, but a page's number does not survive Build, so the
    generator must never emit one - and this fake refuses it.
"""
import inspect

JOURNAL = []
HANDLERS = {}


def reset():
    del JOURNAL[:]
    HANDLERS.clear()


def record(who, method, *args):
    JOURNAL.append((who, method) + args)


def Version():
    return 'fake-3.x'


def event(Object, EventName):
    objects = Object if isinstance(Object, list) else [Object]
    events = EventName if isinstance(EventName, list) else [EventName]

    def decorator(func):
        for obj in objects:
            for name in events:
                known = getattr(type(obj), 'EVENTS', {})
                if name not in known:
                    raise ValueError('{0} has no event {1!r}; it has {2}'.format(
                        type(obj).__name__, name, sorted(known)))
                n = len(inspect.signature(func).parameters)
                if n != known[name]:
                    raise TypeError('a {0} {1} handler takes {2} arguments, {3} takes {4}'.format(
                        type(obj).__name__, name, known[name], func.__name__, n))
                HANDLERS[(id(obj), name)] = func
        return func
    return decorator


def fire(obj, name, value):
    """Raise a device event: the callback gets (device, value), where value is
    the event's payload - 'Online', or the inactivity time in seconds - not the
    event's name. Controls raise theirs through their own fire()."""
    handler = HANDLERS.get((id(obj), name))
    if handler is None:
        return False
    handler(obj, value)
    return True
