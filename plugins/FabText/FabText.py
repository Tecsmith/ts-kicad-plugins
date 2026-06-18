# Copyright 2026 Silvino R. (@silvinor)
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
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


def _from_mm(mm: float) -> int:
    return int(round(pcbnew.FromMM(mm)))


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


FAB_LAYERS = frozenset((pcbnew.F_Fab, pcbnew.B_Fab))


def _is_text_item(item) -> bool:
    return hasattr(item, "SetTextSize") and hasattr(item, "GetLayer")


def _iter_fab_texts(board):
    for fp in board.GetFootprints():
        for getter_name in ("Reference", "Value"):
            getter = getattr(fp, getter_name, None)
            if getter is None:
                continue
            try:
                text = getter()
                if _is_text_item(text) and text.GetLayer() in FAB_LAYERS:
                    yield text
            except Exception:
                pass

        if hasattr(fp, "GraphicalItems"):
            try:
                for item in fp.GraphicalItems():
                    if _is_text_item(item) and item.GetLayer() in FAB_LAYERS:
                        yield item
            except Exception:
                pass


def _set_text_size(text, width: int, height: int) -> None:
    if hasattr(text, "SetTextSize"):
        try:
            text.SetTextSize(pcbnew.VECTOR2I(width, height))
            return
        except Exception:
            pass
        try:
            text.SetTextSize(pcbnew.wxSize(width, height))
            return
        except Exception:
            pass
    if hasattr(text, "SetTextWidth"):
        text.SetTextWidth(width)
    if hasattr(text, "SetTextHeight"):
        text.SetTextHeight(height)


def _set_text_thickness(text, thickness: int, auto: bool) -> None:
    # thickness == 0 signals auto — KiCad renders it proportional to the font size
    t = 0 if auto else thickness
    if hasattr(text, "SetTextThickness"):
        text.SetTextThickness(t)


def _local_offset(text) -> tuple[int, int] | None:
    """Return the text's offset in footprint-local coordinates."""
    # FP_TEXT (KiCad 6 / Reference / Value) stores an explicit local offset
    if hasattr(text, "GetOffset"):
        try:
            return _point_xy(text.GetOffset())
        except Exception:
            pass
    # PCB_TEXT graphical items store absolute board position; derive local offset
    parent = getattr(text, "GetParent", lambda: None)()
    if parent is not None and hasattr(parent, "GetPosition"):
        try:
            tx, ty = _point_xy(text.GetPosition())
            px, py = _point_xy(parent.GetPosition())
            return tx - px, ty - py
        except Exception:
            pass
    return None


def _set_local_offset(text, ox: int, oy: int) -> None:
    """Set the text's offset in footprint-local coordinates."""
    if hasattr(text, "SetOffset"):
        try:
            text.SetOffset(_vector(ox, oy))
            return
        except Exception:
            pass
    # Fallback: update absolute position relative to parent
    parent = getattr(text, "GetParent", lambda: None)()
    if parent is not None and hasattr(parent, "GetPosition"):
        try:
            px, py = _point_xy(parent.GetPosition())
            text.SetPosition(_vector(px + ox, py + oy))
        except Exception:
            pass


def _text_angle_deg(text) -> float:
    """Return the text's local angle in degrees [0, 360)."""
    for method_name in ("GetTextAngle", "GetOrientation"):
        method = getattr(text, method_name, None)
        if method is None:
            continue
        try:
            angle = method()
            if hasattr(angle, "AsDegrees"):
                return float(angle.AsDegrees()) % 360.0
            # KiCad 6: raw decidegrees
            return (float(angle) / 10.0) % 360.0
        except Exception:
            pass
    return 0.0


def _is_vertical_text(text) -> bool:
    angle = _text_angle_deg(text)
    return min(abs(angle - 90.0), abs(angle - 270.0)) < 45.0


def _apply_decenter(text, width: int, height: int) -> bool:
    local = _local_offset(text)
    if local is None:
        return False
    ox, oy = local

    # Only move text whose offset sits inside the -width:-height:width:height zone
    if abs(ox) > width or abs(oy) > height:
        return False

    if _is_vertical_text(text):
        new_ox = (-width if ox < 0 else width)
        _set_local_offset(text, new_ox, oy)
    else:
        new_oy = (-height if oy < 0 else height)
        _set_local_offset(text, ox, new_oy)
    return True


_CONFIG_FILE = os.path.join(pcbnew.SETTINGS_MANAGER.GetUserSettingsPath(), "FabText.json")


def _load_config() -> dict:
    try:
        with open(_CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_config(data: dict) -> None:
    try:
        with open(_CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


class FabTextDialog(wx.Dialog):
    def __init__(self, unit: int, parent=None):
        super().__init__(parent, title="Fab Text")

        self.unit = unit
        unit_label = _unit_label(unit)

        cfg = _load_config()
        width_mm = cfg.get("width_mm", 1.0)
        height_mm = cfg.get("height_mm", 1.0)
        thickness_mm = cfg.get("thickness_mm", 0.125)
        auto = cfg.get("auto_thickness", True)
        decenter = cfg.get("decenter", True)

        main_sizer = wx.BoxSizer(wx.VERTICAL)
        grid = wx.FlexGridSizer(3, 2, 8, 8)
        grid.AddGrowableCol(1, 1)

        self.width_ctrl = wx.TextCtrl(self, value=_format_user_value(_from_mm(width_mm), unit))
        self.height_ctrl = wx.TextCtrl(self, value=_format_user_value(_from_mm(height_mm), unit))

        self.thickness_ctrl = wx.TextCtrl(
            self, value=_format_user_value(_from_mm(thickness_mm), unit)
        )
        self.auto_check = wx.CheckBox(self, label="Auto")
        self.auto_check.SetValue(auto)
        self.thickness_ctrl.Enable(not auto)

        thickness_row = wx.BoxSizer(wx.HORIZONTAL)
        thickness_row.Add(self.thickness_ctrl, 1, wx.EXPAND | wx.RIGHT, 6)
        thickness_row.Add(self.auto_check, 0, wx.ALIGN_CENTER_VERTICAL)

        fields = (
            (f"Width ({unit_label})", self.width_ctrl),
            (f"Height ({unit_label})", self.height_ctrl),
            (f"Thickness ({unit_label})", thickness_row),
        )

        for label, ctrl in fields:
            grid.Add(wx.StaticText(self, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            if isinstance(ctrl, wx.Sizer):
                grid.Add(ctrl, 1, wx.EXPAND)
            else:
                grid.Add(ctrl, 1, wx.EXPAND)

        self.decenter_check = wx.CheckBox(
            self, label="De-center  (push text outside W×H zone; Y if horizontal, X if vertical)"
        )
        self.decenter_check.SetValue(decenter)

        main_sizer.Add(grid, 0, wx.ALL | wx.EXPAND, 12)
        main_sizer.Add(wx.StaticLine(self), 0, wx.EXPAND | wx.LEFT | wx.RIGHT, 12)
        main_sizer.Add(self.decenter_check, 0, wx.ALL, 12)
        main_sizer.Add(
            self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL), 0, wx.ALL | wx.EXPAND, 12
        )
        self.SetSizerAndFit(main_sizer)

        self.auto_check.Bind(wx.EVT_CHECKBOX, self._on_auto_toggle)

    def _on_auto_toggle(self, _event):
        self.thickness_ctrl.Enable(not self.auto_check.GetValue())

    def get_values(self):
        width = _from_user_units(float(self.width_ctrl.GetValue()), self.unit)
        height = _from_user_units(float(self.height_ctrl.GetValue()), self.unit)
        auto = self.auto_check.GetValue()
        thickness = 0 if auto else _from_user_units(float(self.thickness_ctrl.GetValue()), self.unit)
        decenter = self.decenter_check.GetValue()
        if width <= 0 or height <= 0:
            raise ValueError("Width and Height must be greater than zero.")
        if not auto and thickness <= 0:
            raise ValueError("Thickness must be greater than zero.")
        _save_config({
            "width_mm": float(pcbnew.ToMM(width)),
            "height_mm": float(pcbnew.ToMM(height)),
            "thickness_mm": float(pcbnew.ToMM(thickness)) if not auto else float(self.thickness_ctrl.GetValue()),
            "auto_thickness": auto,
            "decenter": decenter,
        })
        return width, height, thickness, auto, decenter


class FabText(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "Fab Text"
        self.category = "Modify PCB"
        self.description = "Normalize text size and offset on F.Fab and B.Fab layers."
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(os.path.dirname(__file__), "FabText.png")
        self.dark_icon_file_name = os.path.join(os.path.dirname(__file__), "FabText.dark.png")

    def GetIconFileName(self, dark):
        return self.dark_icon_file_name if dark else self.icon_file_name

    def Run(self):
        board = pcbnew.GetBoard()
        if board is None:
            wx.MessageBox("No board is currently open.", "Fab Text", wx.OK | wx.ICON_ERROR)
            return

        frame = _pcb_frame()
        unit = _board_units(board)
        dialog = FabTextDialog(unit, parent=frame)
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return

            try:
                width, height, thickness, auto, decenter = dialog.get_values()
            except ValueError as exc:
                wx.MessageBox(str(exc), "Fab Text", wx.OK | wx.ICON_ERROR)
                return

            count = 0
            changed = 0
            target_t = 0 if auto else thickness
            for text in _iter_fab_texts(board):
                item_changed = False

                try:
                    cw, ch = _point_xy(text.GetTextSize())
                    if cw != width or ch != height:
                        item_changed = True
                except Exception:
                    item_changed = True
                _set_text_size(text, width, height)

                try:
                    if hasattr(text, "GetTextThickness") and text.GetTextThickness() != target_t:
                        item_changed = True
                except Exception:
                    item_changed = True
                _set_text_thickness(text, thickness, auto)

                if decenter and _apply_decenter(text, width, height):
                    item_changed = True

                if item_changed:
                    changed += 1
                count += 1

            pcbnew.Refresh()
            wx.MessageBox(
                f"Found {count} text item(s) on F.Fab / B.Fab; {changed} changed.",
                "Fab Text",
                wx.OK | wx.ICON_INFORMATION,
            )
        finally:
            dialog.Destroy()
