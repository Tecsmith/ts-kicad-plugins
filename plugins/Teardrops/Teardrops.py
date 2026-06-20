# Copyright 2026 Silvino R. (@silvinor)
# SPDX-License-Identifier: MIT
# Core algorithm originally by Niluje 2019 (thewireddoesntexist.org)
# Cubic Bezier by mitxela, 2021 (mitxela.com)

from __future__ import annotations

import json
import os
import time

import pcbnew
import wx

from .td import SetTeardrops, RmTeardrops


_CONFIG_FILE = os.path.join(pcbnew.SETTINGS_MANAGER.GetUserSettingsPath(), "Teardrops.json")


def _load_config() -> dict:
    try:
        with open(_CONFIG_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_config(data: dict) -> None:
    try:
        with open(_CONFIG_FILE, "w") as f:
            json.dump(data, f, indent=2)
    except Exception:
        pass


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


class TeardropsDialog(wx.Dialog):
    def __init__(self, parent=None, board=None):
        super().__init__(parent, title="Teardrops")

        cfg = _load_config()
        self._layer_ids = []

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        self.action_radio = wx.RadioBox(
            self, label="Action",
            choices=["Add Teardrops", "Remove Teardrops"],
            majorDimension=1, style=wx.RA_SPECIFY_COLS,
        )
        self.action_radio.SetSelection(0)
        main_sizer.Add(self.action_radio, 0, wx.ALL | wx.EXPAND, 8)

        # Draw mode
        mode_box = wx.StaticBoxSizer(wx.StaticBox(self, label="Draw mode"), wx.VERTICAL)

        self.mode_zone = wx.RadioButton(self, label="Fill zone (copper)", style=wx.RB_GROUP)
        mode_box.Add(self.mode_zone, 0, wx.ALL, 4)

        poly_row = wx.BoxSizer(wx.HORIZONTAL)
        self.mode_poly = wx.RadioButton(self, label="Polygon on layer:")
        poly_row.Add(self.mode_poly, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 6)

        layer_names = []
        saved_layer = cfg.get("polygon_layer")
        default_sel = 0
        if board is not None:
            frame = _pcb_frame()
            active_layer = (frame.GetActiveLayer()
                            if frame and hasattr(frame, 'GetActiveLayer')
                            else pcbnew.F_Cu)
            enabled = board.GetEnabledLayers()
            _max_layer = getattr(pcbnew, 'PCB_LAYER_ID_COUNT', 100)
            for lid in range(_max_layer):
                try:
                    if enabled.Contains(lid):
                        self._layer_ids.append(lid)
                        layer_names.append(board.GetLayerName(lid))
                except Exception:
                    break
            for candidate in ([saved_layer] if saved_layer is not None else []) + [active_layer]:
                if candidate in self._layer_ids:
                    default_sel = self._layer_ids.index(candidate)
                    break
        else:
            self._layer_ids = [pcbnew.F_Cu, pcbnew.B_Cu]
            layer_names = ["F.Cu", "B.Cu"]

        self.layer_choice = wx.Choice(self, choices=layer_names)
        self.layer_choice.SetSelection(default_sel)
        poly_row.Add(self.layer_choice, 1, wx.ALIGN_CENTER_VERTICAL)
        mode_box.Add(poly_row, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 4)

        main_sizer.Add(mode_box, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

        use_polygon = cfg.get("draw_mode") == "polygon"
        self.mode_poly.SetValue(use_polygon)
        self.mode_zone.SetValue(not use_polygon)
        self.layer_choice.Enable(use_polygon)

        # Parameter grid
        grid = wx.FlexGridSizer(3, 2, 6, 8)
        grid.AddGrowableCol(1, 1)

        self.hpct_ctrl = wx.SpinCtrl(self, min=10, max=100, initial=cfg.get("hpercent", 50))
        self.vpct_ctrl = wx.SpinCtrl(self, min=10, max=100, initial=cfg.get("vpercent", 90))
        self.segs_ctrl = wx.SpinCtrl(self, min=2, max=30, initial=cfg.get("segs", 10))

        for label, ctrl in (
            ("H% (teardrop length, % of via dia)", self.hpct_ctrl),
            ("V% (teardrop width, % of via dia)", self.vpct_ctrl),
            ("Curve segments", self.segs_ctrl),
        ):
            grid.Add(wx.StaticText(self, label=label), 0, wx.ALIGN_CENTER_VERTICAL)
            grid.Add(ctrl, 1, wx.EXPAND)

        main_sizer.Add(grid, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM | wx.EXPAND, 8)

        self.smd_check = wx.CheckBox(self, label="Include SMD pads")
        self.zone_check = wx.CheckBox(self, label="Skip pads/vias already inside same-net fill zone")
        self.follow_check = wx.CheckBox(self, label="Follow connecting tracks (extend teardrop along adjacent tracks)")
        self.bulge_check = wx.CheckBox(self, label="No bulge (clamp teardrop to via hemisphere)")

        self.smd_check.SetValue(cfg.get("use_smd", False))
        self.zone_check.SetValue(cfg.get("discard_in_same_zone", True))
        self.follow_check.SetValue(cfg.get("follow_tracks", True))
        self.bulge_check.SetValue(cfg.get("no_bulge", True))

        for cb in (self.smd_check, self.zone_check, self.follow_check, self.bulge_check):
            main_sizer.Add(cb, 0, wx.LEFT | wx.RIGHT | wx.BOTTOM, 8)

        main_sizer.Add(self.CreateSeparatedButtonSizer(wx.OK | wx.CANCEL), 0, wx.ALL | wx.EXPAND, 8)
        self.SetSizerAndFit(main_sizer)

        self.action_radio.Bind(wx.EVT_RADIOBOX, self._on_action)
        self.mode_zone.Bind(wx.EVT_RADIOBUTTON, self._on_mode)
        self.mode_poly.Bind(wx.EVT_RADIOBUTTON, self._on_mode)

    def _on_mode(self, _event):
        self.layer_choice.Enable(self.mode_poly.GetValue())

    def _on_action(self, _event):
        removing = self.action_radio.GetSelection() == 1
        for ctrl in (self.hpct_ctrl, self.vpct_ctrl, self.segs_ctrl,
                     self.smd_check, self.zone_check, self.follow_check, self.bulge_check,
                     self.mode_zone, self.mode_poly):
            ctrl.Enable(not removing)
        self.layer_choice.Enable(not removing and self.mode_poly.GetValue())

    def get_values(self):
        remove = self.action_radio.GetSelection() == 1
        use_polygon = self.mode_poly.GetValue()
        sel = self.layer_choice.GetSelection()
        polygon_layer = self._layer_ids[sel] if 0 <= sel < len(self._layer_ids) else pcbnew.F_Cu
        cfg = {
            "hpercent": self.hpct_ctrl.GetValue(),
            "vpercent": self.vpct_ctrl.GetValue(),
            "segs": self.segs_ctrl.GetValue(),
            "use_smd": self.smd_check.IsChecked(),
            "discard_in_same_zone": self.zone_check.IsChecked(),
            "follow_tracks": self.follow_check.IsChecked(),
            "no_bulge": self.bulge_check.IsChecked(),
            "draw_mode": "polygon" if use_polygon else "zone",
            "polygon_layer": polygon_layer,
        }
        _save_config(cfg)
        return remove, cfg


class Teardrops(pcbnew.ActionPlugin):
    def defaults(self):
        self.name = "Teardrops"
        self.category = "Modify PCB"
        self.description = "Add or remove bezier teardrops on vias and pads using fill zones."
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(os.path.dirname(__file__), "Teardrops.png")
        self.dark_icon_file_name = os.path.join(os.path.dirname(__file__), "Teardrops.dark.png")

    def GetIconFileName(self, dark):
        return self.dark_icon_file_name if dark else self.icon_file_name

    def Run(self):
        board = pcbnew.GetBoard()
        if board is None:
            wx.MessageBox("No board is currently open.", "Teardrops", wx.OK | wx.ICON_ERROR)
            return

        dialog = TeardropsDialog(parent=_pcb_frame(), board=board)
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return

            remove, cfg = dialog.get_values()
            use_polygon = cfg.get("draw_mode") == "polygon"
            polygon_layer = cfg.get("polygon_layer")

            if remove:
                count = RmTeardrops(pcb=board, use_polygon=use_polygon, polygon_layer=polygon_layer)
                wx.MessageBox(
                    f"{count} teardrop(s) removed.",
                    "Teardrops", wx.OK | wx.ICON_INFORMATION,
                )
            else:
                t0 = time.time()
                count = SetTeardrops(
                    hpercent=cfg["hpercent"],
                    vpercent=cfg["vpercent"],
                    segs=cfg["segs"],
                    pcb=board,
                    use_smd=cfg["use_smd"],
                    discard_in_same_zone=cfg["discard_in_same_zone"],
                    follow_tracks=cfg["follow_tracks"],
                    noBulge=cfg["no_bulge"],
                    use_polygon=use_polygon,
                    polygon_layer=polygon_layer,
                )
                wx.MessageBox(
                    f"{count} teardrop(s) added in {time.time()-t0:.1f}s.",
                    "Teardrops", wx.OK | wx.ICON_INFORMATION,
                )

            pcbnew.Refresh()
        finally:
            dialog.Destroy()
