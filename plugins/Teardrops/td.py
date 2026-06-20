#!/usr/bin/env python

# Teardrop for pcbnew using filled zones
# (c) Niluje 2019 thewireddoesntexist.org
#
# Based on Teardrops for PCBNEW by svofski, 2014 http://sensi.org/~svo
# Cubic Bezier upgrade by mitxela, 2021 mitxela.com
# KiCad 8-10 compatibility by silvinor, 2026

from math import cos, sin, asin, atan2, sqrt, pi
import pcbnew
from pcbnew import PCB_VIA, ToMM, PCB_TRACK, PCB_ARC, FromMM, GetBoard, ZONE, VECTOR2I, ZONE_FILLER

# wxPoint was removed in KiCad 8; VECTOR2I is the drop-in replacement.
# Always cast to int since VECTOR2I requires integral coordinates.
try:
    from pcbnew import wxPoint as _wxpt_orig
    wxPoint = lambda x, y: _wxpt_orig(int(x), int(y))
except ImportError:
    wxPoint = lambda x, y: VECTOR2I(int(x), int(y))

# PAD_ATTRIB_PTH/SMD moved inside PAD_ATTRIB enum in KiCad 8.
try:
    from pcbnew import PAD_ATTRIB_PTH, PAD_ATTRIB_SMD
except ImportError:
    PAD_ATTRIB_PTH = pcbnew.PAD_ATTRIB.PTH
    PAD_ATTRIB_SMD = pcbnew.PAD_ATTRIB.SMD

# STARTPOINT/ENDPOINT bit-flags for IsPointOnEnds.
try:
    from pcbnew import STARTPOINT, ENDPOINT
except ImportError:
    STARTPOINT = 1
    ENDPOINT = 2

# GetPriority/SetPriority renamed to GetAssignedPriority/SetAssignedPriority in KiCad 8.
def _zone_get_priority(zone):
    try:
        return zone.GetPriority()
    except AttributeError:
        return zone.GetAssignedPriority()

def _zone_set_priority(zone, p):
    try:
        zone.SetPriority(p)
    except AttributeError:
        zone.SetAssignedPriority(p)

# SHAPE_T_POLY was called S_POLYGON in KiCad 6.
try:
    _SHAPE_T_POLY = pcbnew.SHAPE_T_POLY
except AttributeError:
    _SHAPE_T_POLY = pcbnew.S_POLYGON

__version__ = "0.5.1"

ToUnits = ToMM
FromUnits = FromMM

MAGIC_TEARDROP_ZONE_ID = 0x4242


def _angle_tenths(a) -> float:
    """Return angle in tenths of a degree; handles both EDA_ANGLE and legacy int."""
    if hasattr(a, 'AsDegrees'):
        return float(a.AsDegrees()) * 10.0
    return float(a)


def __GetAllVias(board):
    vias = []
    vias_selected = []
    for item in board.GetTracks():
        if item.GetClass() == "PCB_VIA":
            pos = item.GetPosition()
            width = item.GetWidth()
            drill = PCB_VIA(item).GetDrillValue()
            layer = -1
            vias.append((pos, width, drill, layer))
            if item.IsSelected():
                vias_selected.append((pos, width, drill, layer))
    return vias, vias_selected


def __GetAllPads(board, filters=[]):
    pads = []
    pads_selected = []
    for pad in board.GetPads():
        if pad.GetAttribute() in filters:
            pos = pad.GetPosition()
            drill = min(pad.GetSize())
            if pad.GetAttribute() == PAD_ATTRIB_SMD:
                cu_stack = pad.GetLayerSet().CuStack()
                if len(cu_stack) == 0:
                    continue
                layer = cu_stack[0]
            else:
                layer = -1
            pads.append((pos, drill, 0, layer))
            if pad.IsSelected():
                pads_selected.append((pos, drill, 0, layer))
    return pads, pads_selected


def __GetAllTeardrops(board):
    teardrops_zones = {}
    for zone in board.Zones():
        if _zone_get_priority(zone) == MAGIC_TEARDROP_ZONE_ID:
            netname = zone.GetNetname()
            if netname not in teardrops_zones:
                teardrops_zones[netname] = []
            teardrops_zones[netname].append(zone)
    return teardrops_zones


def __DoesTeardropBelongTo(teardrop, track, via):
    if not teardrop.HitTest(via[0]):
        return False
    if not track.HitTest(teardrop.GetBoundingBox().GetCenter()):
        return False
    return True


def __Zone(board, points, track):
    z = ZONE(board)
    z.SetLayer(track.GetLayer())
    z.SetNetCode(track.GetNetCode())
    try:
        z.SetLocalClearance(track.GetLocalClearance(track.GetClass()))
    except Exception:
        try:
            z.SetLocalClearance(track.GetLocalClearance())
        except Exception:
            pass  # use board default clearance
    z.SetMinThickness(25400)  # minimum
    z.SetPadConnection(2)     # solid
    z.SetIsFilled(True)
    _zone_set_priority(z, MAGIC_TEARDROP_ZONE_ID)
    ol = z.Outline()
    ol.NewOutline()
    for p in points:
        ol.Append(p.x, p.y)
    return z


def __Polygon(board, points, layer):
    # ponytail: polygon teardrops carry no net code; DRC may flag copper on Cu layers
    shape = pcbnew.PCB_SHAPE(board)
    shape.SetShape(_SHAPE_T_POLY)
    shape.SetLayer(layer)
    shape.SetFilled(True)
    shape.SetWidth(0)
    poly = shape.GetPolyShape()
    poly.NewOutline()
    for p in points:
        poly.Append(p.x, p.y)
    return shape


def __GetAllPolyTeardrops(board):
    return [
        item for item in board.GetDrawings()
        if item.GetClass() == "PCB_SHAPE" and item.GetShape() == _SHAPE_T_POLY
    ]


def __Bezier(p1, p2, p3, p4, n=20.0):
    n = float(n)
    pts = []
    for i in range(int(n)+1):
        t = i/n
        a = (1.0 - t)**3
        b = 3.0 * t * (1.0-t)**2
        c = 3.0 * t**2 * (1.0-t)
        d = t**3
        x = int(a * p1[0] + b * p2[0] + c * p3[0] + d * p4[0])
        y = int(a * p1[1] + b * p2[1] + c * p3[1] + d * p4[1])
        pts.append(wxPoint(x, y))
    return pts


def __PointDistance(a, b):
    return sqrt((a[0]-b[0])*(a[0]-b[0]) + (a[1]-b[1])*(a[1]-b[1]))


def __ComputeCurved(vpercent, w, vec, via, pts, segs):
    radius = via[1]/2
    minVpercent = float(w*2) / float(via[1])
    weaken = (vpercent/100.0 - minVpercent) / (1-minVpercent) / radius

    biasBC = 0.5 * __PointDistance(pts[1], pts[2])
    biasAE = 0.5 * __PointDistance(pts[4], pts[0])

    vecC = pts[2] - via[0]
    tangentC = [pts[2][0] - vecC[1]*biasBC*weaken,
                pts[2][1] + vecC[0]*biasBC*weaken]
    vecE = pts[4] - via[0]
    tangentE = [pts[4][0] + vecE[1]*biasAE*weaken,
                pts[4][1] - vecE[0]*biasAE*weaken]

    tangentB = [pts[1][0] - vec[0]*biasBC, pts[1][1] - vec[1]*biasBC]
    tangentA = [pts[0][0] - vec[0]*biasAE, pts[0][1] - vec[1]*biasAE]

    curve1 = __Bezier(pts[1], tangentB, tangentC, pts[2], n=segs)
    curve2 = __Bezier(pts[4], tangentE, tangentA, pts[0], n=segs)

    return curve1 + [pts[3]] + curve2


def __FindTouchingTrack(t1, endpoint, trackLookup):
    match = 0
    matches = 0
    ret = False, False
    for t2 in trackLookup[t1.GetLayer()][t1.GetNetname()]:
        if t2.GetStart() == t1.GetStart() and t2.GetEnd() == t1.GetEnd():
            continue
        match = int(t2.IsPointOnEnds(endpoint, 10))
        if match:
            matches += 1
            if matches > 1:
                return False, False
            ret = match, t2
    return ret


def __NormalizeVector(pt):
    norm = sqrt(pt.x * pt.x + pt.y * pt.y)
    return [t / norm for t in pt]


def __FindPositionAndVectorAlongArc(track, pos, trackReversed):
    radius = track.GetRadius()
    length = track.GetLength()
    arcCenter = track.GetPosition()

    if trackReversed:
        angle = -_angle_tenths(track.GetAngle())
        startAngle = _angle_tenths(track.GetArcAngleEnd())
    else:
        angle = _angle_tenths(track.GetAngle())
        startAngle = _angle_tenths(track.GetArcAngleStart())

    posAngle = startAngle + angle * pos/length
    # posAngle is in tenths of a degree; pi/1800 converts to radians
    posAngle *= pi/1800
    pcos = cos(posAngle)
    psin = sin(posAngle)

    newX = arcCenter.x + pcos * radius
    newY = arcCenter.y + psin * radius

    if angle > 0:
        vec = [-psin, pcos]
    else:
        vec = [psin, -pcos]

    return (wxPoint(newX, newY), vec)


def __ComputePoints(track, via, hpercent, vpercent, segs, follow_tracks, trackLookup, noBulge):
    start = track.GetStart()
    end = track.GetEnd()
    radius = via[1]/2.0
    w = track.GetWidth()/2
    trackReversed = False

    if vpercent > 100:
        vpercent = 100

    if __PointDistance(start, via[0]) > radius:
        start, end = end, start
        trackReversed = True

    if type(track) == PCB_ARC:
        arcP, vecT = __FindPositionAndVectorAlongArc(track, radius/2, trackReversed)
    else:
        vecT = __NormalizeVector(end - start)

    bdelta = FromMM(0.01)
    backoff = 0
    while backoff < radius:
        np = start + wxPoint(vecT[0]*backoff, vecT[1]*backoff)
        if __PointDistance(np, via[0]) >= radius:
            break
        backoff += bdelta
    start = np

    vec = __NormalizeVector(start - via[0])

    targetLength = via[1]*(hpercent/100.0)
    n = min(targetLength, track.GetLength() - backoff)
    consumed = 0

    if follow_tracks:
        while n+consumed < targetLength:
            match, t = __FindTouchingTrack(track, end, trackLookup)
            if (match is False):
                break
            backoff = 0
            consumed += n
            n = min(targetLength-consumed, t.GetLength())
            track = t
            end = t.GetEnd()
            start = t.GetStart()
            if match != STARTPOINT:
                start, end = end, start
                trackReversed = True
            else:
                trackReversed = False
        vecT = __NormalizeVector(end - start)

    if n+consumed < targetLength:
        minVpercent = 100 * float(w) / float(radius)
        vpercent = vpercent*n/targetLength + minVpercent*(1-n/targetLength)

    if type(track) == PCB_ARC:
        start, vecT = __FindPositionAndVectorAlongArc(track, n + consumed + backoff, trackReversed)
        pointB = start + wxPoint( vecT[1]*w, -vecT[0]*w)
        pointA = start + wxPoint(-vecT[1]*w,  vecT[0]*w)
    else:
        pointB = start + wxPoint(vecT[0]*n + vecT[1]*w, vecT[1]*n - vecT[0]*w)
        pointA = start + wxPoint(vecT[0]*n - vecT[1]*w, vecT[1]*n + vecT[0]*w)

    if (__PointDistance(pointA, via[0]) < radius or
       __PointDistance(pointB, via[0]) < radius):
        return False

    dC = asin(vpercent/100.0)
    dE = -dC

    if noBulge:
        offAngle = atan2(vecT[1], vecT[0]) - atan2(vec[1], vec[0])
        if offAngle > pi:
            offAngle -= 2*pi
        if offAngle < -pi:
            offAngle += 2*pi
        if offAngle+dC > pi/2:
            dC = pi/2 - offAngle
        if offAngle+dE < -pi/2:
            dE = -pi/2 - offAngle

    vecC = [vec[0]*cos(dC)+vec[1]*sin(dC), -vec[0]*sin(dC)+vec[1]*cos(dC)]
    vecE = [vec[0]*cos(dE)+vec[1]*sin(dE), -vec[0]*sin(dE)+vec[1]*cos(dE)]

    pointC = via[0] + wxPoint(int(vecC[0] * radius), int(vecC[1] * radius))
    pointE = via[0] + wxPoint(int(vecE[0] * radius), int(vecE[1] * radius))
    pointD = via[0]

    pts = [pointA, pointB, pointC, pointD, pointE]
    if segs > 2:
        pts = __ComputeCurved(vpercent, w, vecT, via, pts, segs)

    return pts


def __IsViaAndTrackInSameNetZone(pcb, via, track):
    for zone in pcb.Zones():
        if _zone_get_priority(zone) == MAGIC_TEARDROP_ZONE_ID:
            continue
        if not zone.IsOnLayer(track.GetLayer()):
            continue
        if zone.GetNetname() == track.GetNetname():
            if zone.Outline().Contains(VECTOR2I(*via[0])):
                return True
    return False


def RebuildAllZones(pcb):
    filler = ZONE_FILLER(pcb)
    filler.Fill(pcb.Zones())


def SetTeardrops(hpercent=50, vpercent=90, segs=10, pcb=None, use_smd=False,
                 discard_in_same_zone=True, follow_tracks=True, noBulge=True,
                 use_polygon=False, polygon_layer=None):
    """Set teardrops on a teardrop-free board; returns count of teardrops added."""
    if pcb is None:
        pcb = GetBoard()
    if use_polygon and polygon_layer is None:
        polygon_layer = pcbnew.F_Cu

    pad_types = [PAD_ATTRIB_PTH] + [PAD_ATTRIB_SMD]*use_smd
    vias = __GetAllVias(pcb)[0] + __GetAllPads(pcb, pad_types)[0]
    vias_selected = __GetAllVias(pcb)[1] + __GetAllPads(pcb, pad_types)[1]
    if len(vias_selected) > 0:
        vias = vias_selected

    trackLookup = {}
    if follow_tracks:
        for t in pcb.GetTracks():
            if isinstance(t, PCB_TRACK):
                net = t.GetNetname()
                layer = t.GetLayer()
                if layer not in trackLookup:
                    trackLookup[layer] = {}
                if net not in trackLookup[layer]:
                    trackLookup[layer][net] = []
                trackLookup[layer][net].append(t)

    if use_polygon:
        existing = __GetAllPolyTeardrops(pcb)
    else:
        teardrops = __GetAllTeardrops(pcb)
    count = 0

    for track in [t for t in pcb.GetTracks() if isinstance(t, PCB_TRACK)]:
        for via in [v for v in vias if track.IsPointOnEnds(v[0], int(v[1]/2))]:
            if track.GetWidth() >= via[1] * vpercent / 100:
                continue
            if int(track.IsPointOnEnds(via[0], int(via[1]/2))) == (STARTPOINT | ENDPOINT):
                continue

            if use_polygon:
                found = any(__DoesTeardropBelongTo(td, track, via) for td in existing)
            else:
                found = False
                if track.GetNetname() in teardrops:
                    for teardrop in teardrops[track.GetNetname()]:
                        if __DoesTeardropBelongTo(teardrop, track, via):
                            found = True
                            break

            if (via[3] != -1) and (via[3] != track.GetLayer()):
                continue

            # ponytail: discard_in_same_zone can be slow on large boards (O(tracks*zones))
            if discard_in_same_zone and __IsViaAndTrackInSameNetZone(pcb, via, track):
                continue

            if not found:
                coor = __ComputePoints(track, via, hpercent, vpercent, segs,
                                       follow_tracks, trackLookup, noBulge)
                if coor:
                    if use_polygon:
                        pcb.Add(__Polygon(pcb, coor, polygon_layer))
                    else:
                        pcb.Add(__Zone(pcb, coor, track))
                    count += 1

    if not use_polygon:
        RebuildAllZones(pcb)
    return count


def RmTeardrops(pcb=None, use_polygon=False, polygon_layer=None):
    """Remove all teardrops; returns count removed."""
    if pcb is None:
        pcb = GetBoard()

    count = 0
    if use_polygon:
        all_vias = (__GetAllVias(pcb)[0] +
                    __GetAllPads(pcb, [PAD_ATTRIB_PTH, PAD_ATTRIB_SMD])[0])
        to_remove = []
        for item in pcb.GetDrawings():
            if item.GetClass() != "PCB_SHAPE" or item.GetShape() != _SHAPE_T_POLY:
                continue
            if polygon_layer is not None and item.GetLayer() != polygon_layer:
                continue
            if any(item.HitTest(via[0]) for via in all_vias):
                to_remove.append(item)
        for item in to_remove:
            pcb.Remove(item)
            count += 1
    else:
        teardrops = __GetAllTeardrops(pcb)
        for netname in teardrops:
            for teardrop in teardrops[netname]:
                pcb.Remove(teardrop)
                count += 1
        RebuildAllZones(pcb)

    return count
