# -*- coding: utf-8 -*-
"""MEP system classification constants.

Only SANITARY is actually used by slice 1 (ADR-0004). VENT is declared now
because a real sanitary appliance's own MEPModel commonly exposes both a
sanitary and a vent connector on the same fixture, and IFixtureReader needs
somewhere to put "this connector is a vent, ignore it for this slice" rather
than silently mis-reading it as a sanitary outlet - not a promise that vent
routing itself is being built yet.
"""

SANITARY = u"Sanitary"
VENT = u"Vent"
