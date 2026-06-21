{
  "patcher": {
    "fileversion": 1,
    "appversion": {
      "major": 8,
      "minor": 1,
      "revision": 2,
      "architecture": "x64",
      "modernui": 1
    },
    "classnamespace": "box",
    "rect": [
      100.0,
      100.0,
      740.0,
      520.0
    ],
    "openrect": [
      0.0,
      0.0,
      0.0,
      169.0
    ],
    "bglocked": 0,
    "openinpresentation": 1,
    "default_fontsize": 10.0,
    "default_fontface": 0,
    "default_fontname": "Arial Bold",
    "gridonopen": 1,
    "gridsize": [
      8.0,
      8.0
    ],
    "gridsnaponopen": 1,
    "objectsnaponopen": 1,
    "statusbarvisible": 2,
    "toolbarvisible": 1,
    "lefttoolbarpinned": 0,
    "toptoolbarpinned": 0,
    "righttoolbarpinned": 0,
    "bottomtoolbarpinned": 0,
    "toolbars_unpinned_last_save": 0,
    "tallnewobj": 0,
    "boxanimatetime": 500,
    "enablehscroll": 1,
    "enablevscroll": 1,
    "devicewidth": 430.0,
    "description": "LivePilot Pitch Glide \u2014 monophonic MIDI pitch-bend glide for sparse lead lines.",
    "digest": "LivePilot Pitch Glide",
    "tags": "livepilot pitch glide mpe midi effect",
    "style": "",
    "subpatcher_template": "",
    "title": "Max MIDI Effect",
    "boxes": [
      {
        "box": {
          "id": "obj-panel",
          "maxclass": "panel",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            20.0,
            20.0,
            690.0,
            460.0
          ],
          "presentation": 1,
          "presentation_rect": [
            0.0,
            0.0,
            430.0,
            172.0
          ],
          "bgcolor": [
            0.11,
            0.11,
            0.12,
            1.0
          ],
          "bordercolor": [
            0.28,
            0.28,
            0.3,
            1.0
          ],
          "rounded": 4
        }
      },
      {
        "box": {
          "id": "obj-title",
          "maxclass": "comment",
          "text": "LivePilot Pitch Glide",
          "numinlets": 1,
          "numoutlets": 0,
          "fontsize": 10.0,
          "patching_rect": [
            40,
            42,
            220,
            22
          ],
          "presentation": 1,
          "presentation_rect": [
            20.0,
            22.0,
            220,
            22
          ]
        }
      },
      {
        "box": {
          "id": "obj-subtitle",
          "maxclass": "comment",
          "text": "Monophonic note-to-note pitch bend. Match Bend Range to the instrument.",
          "numinlets": 1,
          "numoutlets": 0,
          "fontsize": 10.0,
          "patching_rect": [
            40,
            68,
            430,
            20
          ],
          "presentation": 1,
          "presentation_rect": [
            20.0,
            48.0,
            430,
            20
          ]
        }
      },
      {
        "box": {
          "id": "obj-enabled-label",
          "maxclass": "comment",
          "text": "On",
          "numinlets": 1,
          "numoutlets": 0,
          "fontsize": 10.0,
          "patching_rect": [
            40,
            116,
            34,
            20
          ],
          "presentation": 1,
          "presentation_rect": [
            20.0,
            96.0,
            34,
            20
          ]
        }
      },
      {
        "box": {
          "id": "obj-enabled",
          "maxclass": "live.toggle",
          "numinlets": 1,
          "numoutlets": 1,
          "outlettype": [
            ""
          ],
          "parameter_enable": 1,
          "patching_rect": [
            74,
            116,
            20.0,
            20.0
          ],
          "presentation": 1,
          "presentation_rect": [
            54.0,
            96.0,
            20.0,
            20.0
          ],
          "saved_attribute_attributes": {
            "valueof": {
              "parameter_initial": [
                1
              ],
              "parameter_initial_enable": 1,
              "parameter_linknames": 0,
              "parameter_longname": "Enabled",
              "parameter_shortname": "Enabled",
              "parameter_mmin": 0,
              "parameter_mmax": 1,
              "parameter_modmin": 0,
              "parameter_modmax": 1,
              "parameter_type": 2,
              "parameter_unitstyle": 0
            }
          },
          "varname": "Enabled"
        }
      },
      {
        "box": {
          "id": "obj-enabled-load",
          "maxclass": "newobj",
          "text": "loadmess 1",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            74,
            84,
            70.0,
            22.0
          ]
        }
      },
      {
        "box": {
          "id": "obj-enabled-pre",
          "maxclass": "newobj",
          "text": "prepend enabled",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            74,
            146,
            105.0,
            22.0
          ]
        }
      },
      {
        "box": {
          "id": "obj-midiin",
          "maxclass": "newobj",
          "text": "midiin",
          "numinlets": 0,
          "numoutlets": 1,
          "patching_rect": [
            40,
            260,
            60.0,
            22.0
          ]
        }
      },
      {
        "box": {
          "id": "obj-js",
          "maxclass": "newobj",
          "text": "js livepilot_pitch_glide.js",
          "numinlets": 2,
          "numoutlets": 1,
          "patching_rect": [
            150,
            260,
            189.0,
            22.0
          ]
        }
      },
      {
        "box": {
          "id": "obj-midiout",
          "maxclass": "newobj",
          "text": "midiout",
          "numinlets": 1,
          "numoutlets": 0,
          "patching_rect": [
            330,
            260,
            60.0,
            22.0
          ]
        }
      },
      {
        "box": {
          "id": "obj-glide-ms-label",
          "maxclass": "comment",
          "text": "Glide ms",
          "numinlets": 1,
          "numoutlets": 0,
          "fontsize": 10.0,
          "patching_rect": [
            40,
            116,
            80,
            20
          ],
          "presentation": 1,
          "presentation_rect": [
            20.0,
            96.0,
            80,
            20
          ]
        }
      },
      {
        "box": {
          "id": "obj-glide-ms-load",
          "maxclass": "newobj",
          "text": "loadmess 140",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            40,
            132,
            84.0,
            22.0
          ]
        }
      },
      {
        "box": {
          "id": "obj-glide-ms",
          "maxclass": "live.numbox",
          "numinlets": 1,
          "numoutlets": 2,
          "outlettype": [
            "",
            "float"
          ],
          "parameter_enable": 1,
          "patching_rect": [
            40,
            164,
            58.0,
            20.0
          ],
          "presentation": 1,
          "presentation_rect": [
            20.0,
            144.0,
            58.0,
            20.0
          ],
          "saved_attribute_attributes": {
            "valueof": {
              "parameter_initial": [
                140
              ],
              "parameter_initial_enable": 1,
              "parameter_linknames": 0,
              "parameter_longname": "Glide ms",
              "parameter_shortname": "Glide ms",
              "parameter_mmin": 1,
              "parameter_mmax": 2000,
              "parameter_modmin": 1,
              "parameter_modmax": 2000,
              "parameter_type": 0,
              "parameter_unitstyle": 0
            }
          },
          "varname": "Glide_ms"
        }
      },
      {
        "box": {
          "id": "obj-glide-ms-pre",
          "maxclass": "newobj",
          "text": "prepend glide_ms",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            40,
            196,
            112.0,
            22.0
          ]
        }
      },
      {
        "box": {
          "id": "obj-bend-range-label",
          "maxclass": "comment",
          "text": "Bend Range",
          "numinlets": 1,
          "numoutlets": 0,
          "fontsize": 10.0,
          "patching_rect": [
            132,
            116,
            80,
            20
          ],
          "presentation": 1,
          "presentation_rect": [
            112.0,
            96.0,
            80,
            20
          ]
        }
      },
      {
        "box": {
          "id": "obj-bend-range-load",
          "maxclass": "newobj",
          "text": "loadmess 2",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            132,
            132,
            70.0,
            22.0
          ]
        }
      },
      {
        "box": {
          "id": "obj-bend-range",
          "maxclass": "live.numbox",
          "numinlets": 1,
          "numoutlets": 2,
          "outlettype": [
            "",
            "float"
          ],
          "parameter_enable": 1,
          "patching_rect": [
            132,
            164,
            58.0,
            20.0
          ],
          "presentation": 1,
          "presentation_rect": [
            112.0,
            144.0,
            58.0,
            20.0
          ],
          "saved_attribute_attributes": {
            "valueof": {
              "parameter_initial": [
                2
              ],
              "parameter_initial_enable": 1,
              "parameter_linknames": 0,
              "parameter_longname": "Bend Range",
              "parameter_shortname": "Bend Range",
              "parameter_mmin": 0.25,
              "parameter_mmax": 96,
              "parameter_modmin": 0.25,
              "parameter_modmax": 96,
              "parameter_type": 0,
              "parameter_unitstyle": 0
            }
          },
          "varname": "Bend_Range"
        }
      },
      {
        "box": {
          "id": "obj-bend-range-pre",
          "maxclass": "newobj",
          "text": "prepend bend_range",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            132,
            196,
            126.0,
            22.0
          ]
        }
      },
      {
        "box": {
          "id": "obj-curve-label",
          "maxclass": "comment",
          "text": "Curve",
          "numinlets": 1,
          "numoutlets": 0,
          "fontsize": 10.0,
          "patching_rect": [
            224,
            116,
            80,
            20
          ],
          "presentation": 1,
          "presentation_rect": [
            204.0,
            96.0,
            80,
            20
          ]
        }
      },
      {
        "box": {
          "id": "obj-curve-load",
          "maxclass": "newobj",
          "text": "loadmess 0.25",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            224,
            132,
            91.0,
            22.0
          ]
        }
      },
      {
        "box": {
          "id": "obj-curve",
          "maxclass": "live.numbox",
          "numinlets": 1,
          "numoutlets": 2,
          "outlettype": [
            "",
            "float"
          ],
          "parameter_enable": 1,
          "patching_rect": [
            224,
            164,
            58.0,
            20.0
          ],
          "presentation": 1,
          "presentation_rect": [
            204.0,
            144.0,
            58.0,
            20.0
          ],
          "saved_attribute_attributes": {
            "valueof": {
              "parameter_initial": [
                0.25
              ],
              "parameter_initial_enable": 1,
              "parameter_linknames": 0,
              "parameter_longname": "Curve",
              "parameter_shortname": "Curve",
              "parameter_mmin": -1,
              "parameter_mmax": 1,
              "parameter_modmin": -1,
              "parameter_modmax": 1,
              "parameter_type": 0,
              "parameter_unitstyle": 0
            }
          },
          "varname": "Curve"
        }
      },
      {
        "box": {
          "id": "obj-curve-pre",
          "maxclass": "newobj",
          "text": "prepend curve",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            224,
            196,
            91.0,
            22.0
          ]
        }
      },
      {
        "box": {
          "id": "obj-max-interval-label",
          "maxclass": "comment",
          "text": "Max Int",
          "numinlets": 1,
          "numoutlets": 0,
          "fontsize": 10.0,
          "patching_rect": [
            316,
            116,
            80,
            20
          ],
          "presentation": 1,
          "presentation_rect": [
            296.0,
            96.0,
            80,
            20
          ]
        }
      },
      {
        "box": {
          "id": "obj-max-interval-load",
          "maxclass": "newobj",
          "text": "loadmess 2",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            316,
            132,
            70.0,
            22.0
          ]
        }
      },
      {
        "box": {
          "id": "obj-max-interval",
          "maxclass": "live.numbox",
          "numinlets": 1,
          "numoutlets": 2,
          "outlettype": [
            "",
            "float"
          ],
          "parameter_enable": 1,
          "patching_rect": [
            316,
            164,
            58.0,
            20.0
          ],
          "presentation": 1,
          "presentation_rect": [
            296.0,
            144.0,
            58.0,
            20.0
          ],
          "saved_attribute_attributes": {
            "valueof": {
              "parameter_initial": [
                2
              ],
              "parameter_initial_enable": 1,
              "parameter_linknames": 0,
              "parameter_longname": "Max Int",
              "parameter_shortname": "Max Int",
              "parameter_mmin": 0.25,
              "parameter_mmax": 48,
              "parameter_modmin": 0.25,
              "parameter_modmax": 48,
              "parameter_type": 0,
              "parameter_unitstyle": 0
            }
          },
          "varname": "Max_Int"
        }
      },
      {
        "box": {
          "id": "obj-max-interval-pre",
          "maxclass": "newobj",
          "text": "prepend max_interval",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            316,
            196,
            140.0,
            22.0
          ]
        }
      },
      {
        "box": {
          "id": "obj-trigger-window-ms-label",
          "maxclass": "comment",
          "text": "Window ms",
          "numinlets": 1,
          "numoutlets": 0,
          "fontsize": 10.0,
          "patching_rect": [
            408,
            116,
            80,
            20
          ],
          "presentation": 1,
          "presentation_rect": [
            388.0,
            96.0,
            80,
            20
          ]
        }
      },
      {
        "box": {
          "id": "obj-trigger-window-ms-load",
          "maxclass": "newobj",
          "text": "loadmess 700",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            408,
            132,
            84.0,
            22.0
          ]
        }
      },
      {
        "box": {
          "id": "obj-trigger-window-ms",
          "maxclass": "live.numbox",
          "numinlets": 1,
          "numoutlets": 2,
          "outlettype": [
            "",
            "float"
          ],
          "parameter_enable": 1,
          "patching_rect": [
            408,
            164,
            58.0,
            20.0
          ],
          "presentation": 1,
          "presentation_rect": [
            388.0,
            144.0,
            58.0,
            20.0
          ],
          "saved_attribute_attributes": {
            "valueof": {
              "parameter_initial": [
                700
              ],
              "parameter_initial_enable": 1,
              "parameter_linknames": 0,
              "parameter_longname": "Window ms",
              "parameter_shortname": "Window ms",
              "parameter_mmin": 1,
              "parameter_mmax": 5000,
              "parameter_modmin": 1,
              "parameter_modmax": 5000,
              "parameter_type": 0,
              "parameter_unitstyle": 0
            }
          },
          "varname": "Window_ms"
        }
      },
      {
        "box": {
          "id": "obj-trigger-window-ms-pre",
          "maxclass": "newobj",
          "text": "prepend trigger_window_ms",
          "numinlets": 1,
          "numoutlets": 1,
          "patching_rect": [
            408,
            196,
            175.0,
            22.0
          ]
        }
      }
    ],
    "lines": [
      {
        "patchline": {
          "source": [
            "obj-enabled-load",
            0
          ],
          "destination": [
            "obj-enabled",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-enabled",
            0
          ],
          "destination": [
            "obj-enabled-pre",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-enabled-pre",
            0
          ],
          "destination": [
            "obj-js",
            1
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-midiin",
            0
          ],
          "destination": [
            "obj-js",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-js",
            0
          ],
          "destination": [
            "obj-midiout",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-glide-ms-load",
            0
          ],
          "destination": [
            "obj-glide-ms",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-glide-ms",
            0
          ],
          "destination": [
            "obj-glide-ms-pre",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-glide-ms-pre",
            0
          ],
          "destination": [
            "obj-js",
            1
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-bend-range-load",
            0
          ],
          "destination": [
            "obj-bend-range",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-bend-range",
            0
          ],
          "destination": [
            "obj-bend-range-pre",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-bend-range-pre",
            0
          ],
          "destination": [
            "obj-js",
            1
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-curve-load",
            0
          ],
          "destination": [
            "obj-curve",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-curve",
            0
          ],
          "destination": [
            "obj-curve-pre",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-curve-pre",
            0
          ],
          "destination": [
            "obj-js",
            1
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-max-interval-load",
            0
          ],
          "destination": [
            "obj-max-interval",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-max-interval",
            0
          ],
          "destination": [
            "obj-max-interval-pre",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-max-interval-pre",
            0
          ],
          "destination": [
            "obj-js",
            1
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-trigger-window-ms-load",
            0
          ],
          "destination": [
            "obj-trigger-window-ms",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-trigger-window-ms",
            0
          ],
          "destination": [
            "obj-trigger-window-ms-pre",
            0
          ]
        }
      },
      {
        "patchline": {
          "source": [
            "obj-trigger-window-ms-pre",
            0
          ],
          "destination": [
            "obj-js",
            1
          ]
        }
      }
    ],
    "dependency_cache": [],
    "latency": 0,
    "project": {
      "version": 1,
      "creationdate": 3590052786,
      "modificationdate": 3590052786,
      "viewrect": [
        0.0,
        0.0,
        300.0,
        500.0
      ],
      "autoorganize": 1,
      "hideprojectwindow": 1,
      "showdependencies": 1,
      "autolocalize": 0,
      "contents": {
        "patchers": {}
      },
      "layout": {},
      "searchpath": {},
      "detailsvisible": 0,
      "amxdtype": 1835887981,
      "readonly": 0,
      "devpathtype": 0,
      "devpath": ".",
      "sortmode": 0,
      "viewmode": 0
    },
    "autosave": 0,
    "is_mpe": 1
  }
}
