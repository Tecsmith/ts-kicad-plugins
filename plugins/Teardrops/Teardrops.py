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
    def __init__(self, parent=None):
        super().__init__(parent, title="Teardrops")

        cfg = _load_config()

        main_sizer = wx.BoxSizer(wx.VERTICAL)

        self.action_radio = wx.RadioBox(
            self, label="Action",
            choices=["Add Teardrops", "Remove Teardrops"],
            majorDimension=1, style=wx.RA_SPECIFY_COLS,
        )
        self.action_radio.SetSelection(0)
        main_sizer.Add(self.action_radio, 0, wx.ALL | wx.EXPAND, 8)

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

    def _on_action(self, _event):
        removing = self.action_radio.GetSelection() == 1
        for ctrl in (self.hpct_ctrl, self.vpct_ctrl, self.segs_ctrl,
                     self.smd_check, self.zone_check, self.follow_check, self.bulge_check):
            ctrl.Enable(not removing)

    def get_values(self):
        remove = self.action_radio.GetSelection() == 1
        cfg = {
            "hpercent": self.hpct_ctrl.GetValue(),
            "vpercent": self.vpct_ctrl.GetValue(),
            "segs": self.segs_ctrl.GetValue(),
            "use_smd": self.smd_check.IsChecked(),
            "discard_in_same_zone": self.zone_check.IsChecked(),
            "follow_tracks": self.follow_check.IsChecked(),
            "no_bulge": self.bulge_check.IsChecked(),
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

        dialog = TeardropsDialog(parent=_pcb_frame())
        try:
            if dialog.ShowModal() != wx.ID_OK:
                return

            remove, cfg = dialog.get_values()

            if remove:
                count = RmTeardrops(pcb=board)
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
                )
                wx.MessageBox(
                    f"{count} teardrop(s) added in {time.time()-t0:.1f}s.",
                    "Teardrops", wx.OK | wx.ICON_INFORMATION,
                )

            pcbnew.Refresh()
        finally:
            dialog.Destroy()
