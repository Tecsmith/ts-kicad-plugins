# Copyright 2026 Silvino R. (@silvinor)
# SPDX-License-Identifier: MIT

from __future__ import annotations

import math
import os

import pcbnew
import wx


def _unit_enum(*names):
    for name in names:
        if hasattr(pcbnew, name):
            return getattr(pcbnew, name)

    enum_type = getattr(pcbnew, "EDA_UNITS", None)
    if enum_type is not None:
        for name in names:
            if hasattr(enum_type, name):
                return getattr(enum_type, name)

    return object()


UNIT_MM = _unit_enum("EDA_UNITS_MM", "EDA_UNITS_MILLIMETRES", "MM")
UNIT_IN = _unit_enum("EDA_UNITS_INCH", "EDA_UNITS_INCHES", "INCH")
UNIT_MILS = _unit_enum("EDA_UNITS_MILS", "MILS")


def _board_units(board) -> int:
    if board is not None and hasattr(board, "GetUserUnits"):
        return board.GetUserUnits()
    return getattr(pcbnew, "GetUserUnits", lambda: UNIT_MM)()


def _unit_label(unit: int) -> str:
    if unit == UNIT_MILS:
        return "mil"
    if unit == UNIT_IN:
        return "in"
    return "mm"


def _from_user_units(value: float, unit: int) -> int:
    return int(round(pcbnew.FromUserUnit(pcbnew.pcbIUScale, unit, value)))


def _to_user_units(value: int, unit: int) -> float:
    return float(pcbnew.ToUserUnit(pcbnew.pcbIUScale, unit, value))


def _format_user_value(value: int, unit: int) -> str:
    return f"{_to_user_units(value, unit):g}"


def _point_xy(point):
    for x_name, y_name in (("x", "y"), ("X", "Y")):
        if hasattr(point, x_name) and hasattr(point, y_name):
            x_attr = getattr(point, x_name)
            y_attr = getattr(point, y_name)
            x = x_attr() if callable(x_attr) else x_attr
            y = y_attr() if callable(y_attr) else y_attr
            return int(x), int(y)

    if hasattr(point, "__getitem__"):
        try:
            return int(point[0]), int(point[1])
        except Exception:
            pass

    return 0, 0


def _pcb_frame():
    active = wx.GetActiveWindow()
    if active is not None and hasattr(active, "GetGridOrigin"):
        return active

    for window in wx.GetTopLevelWindows():
        if hasattr(window, "GetGridOrigin") and getattr(window, "IsActive", lambda: False)():
            return window

    for window in wx.GetTopLevelWindows():
        if hasattr(window, "GetGridOrigin"):
            return window

    return None


def _vector(x: int, y: int):
    if hasattr(pcbnew, "VECTOR2I"):
        return pcbnew.VECTOR2I(int(x), int(y))
    return pcbnew.wxPoint(int(x), int(y))


def _active_copper_layer(board) -> int:
    layer = getattr(board, "GetActiveLayer", lambda: pcbnew.F_Cu)()
    if getattr(board, "IsCopperLayer", lambda _layer: True)(layer):
        return layer
    return pcbnew.F_Cu


def _grid_origin(board, frame=None):
    if frame is not None and hasattr(frame, "GetGridOrigin"):
        return _point_xy(frame.GetGridOrigin())

    if hasattr(board, "GetDesignSettings"):
        settings = board.GetDesignSettings()
        if hasattr(settings, "GetGridOrigin"):
            return _point_xy(settings.GetGridOrigin())

    if hasattr(board, "GetGridOrigin"):
        return _point_xy(board.GetGridOrigin())

    return 0, 0


def _bbox_center(item):
    if not hasattr(item, "GetBoundingBox"):
        return None

    bbox = item.GetBoundingBox()
    if bbox is None:
        return None

    if hasattr(bbox, "GetCenter"):
        return _point_xy(bbox.GetCenter())

    left = bbox.GetLeft() if hasattr(bbox, "GetLeft") else bbox.GetX()
    top = bbox.GetTop() if hasattr(bbox, "GetTop") else bbox.GetY()
    width = bbox.GetWidth()
    height = bbox.GetHeight()
    return int(left + width // 2), int(top + height // 2)


def _bbox_edges(item):
    if not hasattr(item, "GetBoundingBox"):
        return None

    bbox = item.GetBoundingBox()
    if bbox is None:
        return None

    left = bbox.GetLeft() if hasattr(bbox, "GetLeft") else bbox.GetX()
    top = bbox.GetTop() if hasattr(bbox, "GetTop") else bbox.GetY()
    width = bbox.GetWidth()
    height = bbox.GetHeight()
    return int(left), int(top), int(left + width), int(top + height)


def _iter_board_items(board):
    for getter_name in ("GetDrawings", "GetFootprints", "Tracks", "Zones"):
        getter = getattr(board, getter_name, None)
        if getter is None:
            continue
        try:
            for item in getter():
                yield item
        except Exception:
            continue


def _iter_candidate_items(board):
    for item in _iter_board_items(board):
        yield item

        if hasattr(item, "GraphicalItems"):
            try:
                for child in item.GraphicalItems():
                    yield child
            except Exception:
                pass

        for child_getter_name in ("Reference", "Value"):
            child_getter = getattr(item, child_getter_name, None)
            if child_getter is None:
                continue
            try:
                yield child_getter()
            except Exception:
                pass


def _selection_bounds(board):
    bounds = None

    for item in _iter_candidate_items(board):
        if getattr(item, "IsSelected", lambda: False)():
            edges = _bbox_edges(item)
            if edges is None:
                continue

            if bounds is None:
                bounds = list(edges)
            else:
                bounds[0] = min(bounds[0], edges[0])
                bounds[1] = min(bounds[1], edges[1])
                bounds[2] = max(bounds[2], edges[2])
                bounds[3] = max(bounds[3], edges[3])

    return bounds


def _selection_center(board):
    bounds = _selection_bounds(board)
    if bounds is None:
        return None

    return (
        int((bounds[0] + bounds[2]) // 2),
        int((bounds[1] + bounds[3]) // 2),
    )


def _default_radius(board) -> int | None:
    bounds = _selection_bounds(board)
    if bounds is None:
        return None

    width = bounds[2] - bounds[0]
    height = bounds[3] - bounds[1]
    return int(math.ceil(min(width, height) / 2.0))


def _fallback_radius(unit: int) -> int:
    if unit == UNIT_MILS:
        return _from_user_units(200.0, unit)
    if unit == UNIT_IN:
        return _from_user_units(0.2, unit)
    return _from_user_units(10.0, unit)


def _default_center(board, frame=None):
    center = _selection_center(board)
    if center is not None:
        return center
    return _grid_origin(board, frame)


def _new_outline(outline):
    if hasattr(outline, "NewOutline"):
        return outline.NewOutline()
    if hasattr(outline, "AddOutline"):
        return outline.AddOutline()
    raise AttributeError("Unsupported polygon outline API")


def _append_point(outline, outline_index: int, x: int, y: int) -> None:
    if hasattr(outline, "Append"):
        try:
            outline.Append(int(x), int(y), outline_index)
            return
        except TypeError:
            try:
                outline.Append(_vector(x, y), outline_index)
                return
            except TypeError:
                outline.Append(_vector(x, y))
                return
    if hasattr(outline, "AppendCorner"):
        outline.AppendCorner(_vector(x, y))
        return
    raise AttributeError("Unsupported polygon append API")


class RoundZoneRuleDialog(wx.Dialog):
    def __init__(self, center_x: int, center_y: int, radius: int, unit: int, parent=None):
        super().__init__(parent, title="Round Zone Rule")

        self.unit = unit
        unit_label = _unit_label(unit)

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(4, 2, 8, 8)
        grid.AddGrowableCol(1, 1)

        self.x_ctrl = wx.TextCtrl(self, value=_format_user_value(center_x, unit))
        self.y_ctrl = wx.TextCtrl(self, value=_format_user_value(center_y, unit))
        self.radius_ctrl = wx.TextCtrl(self, value=_format_user_value(radius, unit))
        self.points_ctrl = wx.SpinCtrl(self, min=3, max=128, initial=64)

        fields = (
            (f"Center X ({unit_label})", self.x_ctrl),
            (f"Center Y ({unit_label})", self.y_ctrl),
            (f"Radius ({unit_label})", self.radius_ctrl),
            ("Points", self.points_ctrl),
        )

        for label, ctrl in fields:
            grid.Add(wx.StaticText(self, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(ctrl, 1, wx.EXPAND)

        main_sizer.Add(grid, 0, wx.ALL | wx.EXPAND, 12)
        main_sizer.Add(self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL), 0, wx.ALL | wx.EXPAND, 12)
        self.SetSizerAndFit(main_sizer)

    def get_values(self):
        x = _from_user_units(float(self.x_ctrl.GetValue()), self.unit)
        y = _from_user_units(float(self.y_ctrl.GetValue()), self.unit)
        radius = _from_user_units(float(self.radius_ctrl.GetValue()), self.unit)
        points = self.points_ctrl.GetValue()
        if radius <= 0:
            raise ValueError("Radius must be greater than zero.")
        return x, y, radius, points


class RoundZoneRule(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "Round Zone Rule"
        self.category = "Modify PCB"
        self.description = "Create a circular Zone Rule approximated by a polygon."
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(os.path.dirname(__file__), "RoundZoneRule.png")
        self.dark_icon_file_name = os.path.join(os.path.dirname(__file__), "RoundZoneRule.dark.png")

    def GetIconFileName(self, dark):
        return self.dark_icon_file_name if dark else self.icon_file_name

    def Run(self):
        board = pcbnew.GetBoard()
        if board is None:
            wx.MessageBox("No board is currently open.", "Round Zone Rule", wx.OK | wx.ICON_ERROR)
            return

        frame = _pcb_frame()
        unit = _board_units(board)
        dialog = RoundZoneRuleDialog(
            *_default_center(board, frame),
            _default_radius(board) or _fallback_radius(unit),
            unit,
            parent=frame,
        )
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return

            try:
                center_x, center_y, radius, points = dialog.get_values()
            except ValueError as exc:
                wx.MessageBox(str(exc), "Round Zone Rule", wx.OK | wx.ICON_ERROR)
                return

            zone = pcbnew.ZONE(board)
            zone.SetLayer(_active_copper_layer(board))

            if hasattr(zone, "SetIsRuleArea"):
                zone.SetIsRuleArea(True)

            if hasattr(zone, "SetIsFilled"):
                zone.SetIsFilled(False)

            if hasattr(zone, "SetNeedRefill"):
                zone.SetNeedRefill(False)

            outline = zone.Outline()
            outline_index = _new_outline(outline)

            step = (2.0 * math.pi) / points
            for i in range(points):
                angle = i * step
                x = center_x + int(round(radius * math.cos(angle)))
                y = center_y + int(round(radius * math.sin(angle)))
                _append_point(outline, outline_index, x, y)

            if hasattr(outline, "NormalizeAreaOutlines"):
                outline.NormalizeAreaOutlines()
            board.Add(zone)
            pcbnew.Refresh()
        finally:
            dialog.Destroy()
