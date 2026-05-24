{
	"patcher": {
		"fileversion": 1,
		"appversion": {
			"major": 8,
			"minor": 6,
			"revision": 0,
			"architecture": "x64",
			"modernui": 1
		},
		"classnamespace": "box",
		"rect": [
			100.0,
			100.0,
			720.0,
			560.0
		],
		"openinpresentation": 1,
		"default_fontsize": 12.0,
		"default_fontface": 0,
		"default_fontname": "Arial",
		"gridonopen": 1,
		"gridsize": [
			15.0,
			15.0
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
		"boxanimatetime": 200,
		"enablehscroll": 1,
		"enablevscroll": 1,
		"devicewidth": 360.0,
		"description": "LivePilot Elektron Bridge — paced chunked SysEx out + SysEx capture in. UDP 9882 (M4L→server) / UDP 9883 (server→M4L).",
		"digest": "Live 12 MIDI bridge for Elektron hardware (MnM + MD UW MKII)",
		"tags": "livepilot elektron bridge sysex midi monomachine machinedrum",
		"style": "",
		"subpatcher_template": "",
		"assistshowspatchername": 0,
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
						680.0,
						520.0
					],
					"presentation": 1,
					"presentation_rect": [
						0.0,
						0.0,
						360.0,
						160.0
					],
					"bgcolor": [
						0.12,
						0.12,
						0.14,
						1.0
					],
					"bordercolor": [
						0.22,
						0.22,
						0.25,
						1.0
					],
					"border": 1,
					"rounded": 4
				}
			},
			{
				"box": {
					"id": "obj-title",
					"maxclass": "comment",
					"text": "LivePilot Elektron Bridge",
					"numinlets": 1,
					"numoutlets": 0,
					"fontsize": 16.0,
					"fontface": 1,
					"textcolor": [
						0.85,
						0.87,
						0.9,
						1.0
					],
					"patching_rect": [
						40.0,
						40.0,
						300.0,
						24.0
					],
					"presentation": 1,
					"presentation_rect": [
						12.0,
						10.0,
						300.0,
						24.0
					]
				}
			},
			{
				"box": {
					"id": "obj-subtitle",
					"maxclass": "comment",
					"text": "Paced SysEx out + SysEx capture in. Phase 1 MIDI I/O foundation.",
					"numinlets": 1,
					"numoutlets": 0,
					"fontsize": 11.0,
					"textcolor": [
						0.6,
						0.62,
						0.66,
						1.0
					],
					"patching_rect": [
						40.0,
						66.0,
						340.0,
						20.0
					],
					"presentation": 1,
					"presentation_rect": [
						12.0,
						34.0,
						340.0,
						20.0
					]
				}
			},
			{
				"box": {
					"id": "obj-status-label",
					"maxclass": "comment",
					"text": "Status:",
					"numinlets": 1,
					"numoutlets": 0,
					"fontsize": 11.0,
					"textcolor": [
						0.6,
						0.62,
						0.66,
						1.0
					],
					"patching_rect": [
						40.0,
						92.0,
						60.0,
						20.0
					],
					"presentation": 1,
					"presentation_rect": [
						12.0,
						66.0,
						60.0,
						20.0
					]
				}
			},
			{
				"box": {
					"id": "obj-status",
					"maxclass": "comment",
					"text": "Initialising…",
					"numinlets": 1,
					"numoutlets": 0,
					"fontsize": 11.0,
					"textcolor": [
						0.55,
						0.78,
						0.55,
						1.0
					],
					"patching_rect": [
						100.0,
						92.0,
						260.0,
						20.0
					],
					"presentation": 1,
					"presentation_rect": [
						78.0,
						66.0,
						260.0,
						20.0
					],
					"varname": "status_display"
				}
			},
			{
				"box": {
					"id": "obj-rx-label",
					"maxclass": "comment",
					"text": "RX from MnM/MD:",
					"numinlets": 1,
					"numoutlets": 0,
					"fontsize": 11.0,
					"textcolor": [
						0.6,
						0.62,
						0.66,
						1.0
					],
					"patching_rect": [
						40.0,
						112.0,
						120.0,
						20.0
					],
					"presentation": 1,
					"presentation_rect": [
						12.0,
						88.0,
						120.0,
						20.0
					]
				}
			},
			{
				"box": {
					"id": "obj-rx-count",
					"maxclass": "live.numbox",
					"numinlets": 1,
					"numoutlets": 2,
					"outlettype": [
						"",
						"float"
					],
					"parameter_enable": 0,
					"patching_rect": [
						140.0,
						112.0,
						60.0,
						20.0
					],
					"presentation": 1,
					"presentation_rect": [
						140.0,
						88.0,
						60.0,
						20.0
					],
					"varname": "rx_count"
				}
			},
			{
				"box": {
					"id": "obj-hint",
					"maxclass": "comment",
					"text": "Track MIDI Out → physical Elektron port. UDP 9882↑ / UDP 9883↓.",
					"numinlets": 1,
					"numoutlets": 0,
					"fontsize": 10.0,
					"textcolor": [
						0.5,
						0.52,
						0.56,
						1.0
					],
					"patching_rect": [
						40.0,
						132.0,
						340.0,
						20.0
					],
					"presentation": 1,
					"presentation_rect": [
						12.0,
						120.0,
						340.0,
						32.0
					]
				}
			},
			{
				"box": {
					"id": "obj-thisdevice",
					"maxclass": "newobj",
					"text": "live.thisdevice",
					"numinlets": 1,
					"numoutlets": 3,
					"outlettype": [
						"bang",
						"bang",
						""
					],
					"patching_rect": [
						520.0,
						180.0,
						110.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-init-msg",
					"maxclass": "message",
					"text": "set initialising",
					"numinlets": 2,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						520.0,
						220.0,
						110.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-sysexin",
					"maxclass": "newobj",
					"text": "sysexin",
					"numinlets": 0,
					"numoutlets": 1,
					"outlettype": [
						"int"
					],
					"patching_rect": [
						40.0,
						180.0,
						60.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-sxformat",
					"maxclass": "newobj",
					"text": "sxformat",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						40.0,
						220.0,
						60.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-prepend-sysex",
					"maxclass": "newobj",
					"text": "prepend sysex",
					"numinlets": 2,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						40.0,
						260.0,
						100.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-udpreceive",
					"maxclass": "newobj",
					"text": "udpreceive 9883",
					"numinlets": 0,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						200.0,
						180.0,
						120.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-metro-pump",
					"maxclass": "newobj",
					"text": "metro 50 @active 1",
					"numinlets": 2,
					"numoutlets": 1,
					"outlettype": [
						"bang"
					],
					"patching_rect": [
						340.0,
						180.0,
						140.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-js",
					"maxclass": "newobj",
					"text": "js livepilot_elektron_bridge.js",
					"numinlets": 1,
					"numoutlets": 4,
					"outlettype": [
						"",
						"",
						"",
						""
					],
					"patching_rect": [
						140.0,
						320.0,
						220.0,
						22.0
					],
					"fontsize": 11.0,
					"bgcolor": [
						0.18,
						0.22,
						0.28,
						1.0
					],
					"textcolor": [
						0.85,
						0.87,
						0.9,
						1.0
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
						140.0,
						440.0,
						60.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-udpsend",
					"maxclass": "newobj",
					"text": "udpsend 127.0.0.1 9882",
					"numinlets": 1,
					"numoutlets": 0,
					"patching_rect": [
						240.0,
						440.0,
						180.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-status-prepend",
					"maxclass": "newobj",
					"text": "prepend set",
					"numinlets": 2,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						440.0,
						440.0,
						90.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-online-msg",
					"maxclass": "message",
					"text": "set online",
					"numinlets": 2,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						440.0,
						400.0,
						80.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-rx-counter",
					"maxclass": "newobj",
					"text": "+ 1",
					"numinlets": 2,
					"numoutlets": 1,
					"outlettype": [
						"int"
					],
					"patching_rect": [
						380.0,
						390.0,
						40.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-label-sysexin",
					"maxclass": "comment",
					"text": "← SysEx from physical MIDI in (Elektron OUT → TM-1 IN → here)",
					"numinlets": 1,
					"numoutlets": 0,
					"fontsize": 10.0,
					"textcolor": [
						0.5,
						0.52,
						0.56,
						1.0
					],
					"patching_rect": [
						110.0,
						184.0,
						400.0,
						18.0
					]
				}
			},
			{
				"box": {
					"id": "obj-label-udprx",
					"maxclass": "comment",
					"text": "← UDP from Python server (chunked outbound MIDI)",
					"numinlets": 1,
					"numoutlets": 0,
					"fontsize": 10.0,
					"textcolor": [
						0.5,
						0.52,
						0.56,
						1.0
					],
					"patching_rect": [
						330.0,
						204.0,
						300.0,
						18.0
					]
				}
			},
			{
				"box": {
					"id": "obj-label-js",
					"maxclass": "comment",
					"text": "outlet 0 → midiout   outlet 1 → udpsend(9882)   outlet 2 → status   outlet 3 → rx_count",
					"numinlets": 1,
					"numoutlets": 0,
					"fontsize": 10.0,
					"textcolor": [
						0.5,
						0.52,
						0.56,
						1.0
					],
					"patching_rect": [
						140.0,
						348.0,
						500.0,
						18.0
					]
				}
			}
		],
		"lines": [
			{
				"patchline": {
					"source": [
						"obj-thisdevice",
						2
					],
					"destination": [
						"obj-init-msg",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-init-msg",
						0
					],
					"destination": [
						"obj-status",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-sysexin",
						0
					],
					"destination": [
						"obj-sxformat",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-sxformat",
						0
					],
					"destination": [
						"obj-prepend-sysex",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-prepend-sysex",
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
						"obj-udpreceive",
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
						"obj-metro-pump",
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
						"obj-js",
						1
					],
					"destination": [
						"obj-udpsend",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-js",
						1
					],
					"destination": [
						"obj-online-msg",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-online-msg",
						0
					],
					"destination": [
						"obj-status",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-js",
						1
					],
					"destination": [
						"obj-rx-counter",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-rx-counter",
						0
					],
					"destination": [
						"obj-rx-count",
						0
					]
				}
			}
		]
	}
}
