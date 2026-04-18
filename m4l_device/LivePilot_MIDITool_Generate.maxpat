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
		"devicewidth": 350.0,
		"description": "LivePilot MIDI Tool (Generator) — creates notes from scratch over the clip selection. Pairs euclidean_rhythm / any generator from the server.",
		"digest": "Live 12 MIDI Generator — LivePilot bridge",
		"tags": "livepilot miditool bridge generator",
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
						350.0,
						140.0
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
					"text": "LivePilot MIDI Tool (Generate)",
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
						260.0,
						24.0
					],
					"presentation": 1,
					"presentation_rect": [
						12.0,
						10.0,
						260.0,
						24.0
					]
				}
			},
			{
				"box": {
					"id": "obj-subtitle",
					"maxclass": "comment",
					"text": "Generates new notes via LivePilot server",
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
						320.0,
						20.0
					],
					"presentation": 1,
					"presentation_rect": [
						12.0,
						34.0,
						320.0,
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
					"id": "obj-hint",
					"maxclass": "comment",
					"text": "Codex: set_miditool_target(tool_name='euclidean_rhythm', params={'steps':16,'pulses':5})",
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
						114.0,
						320.0,
						20.0
					],
					"presentation": 1,
					"presentation_rect": [
						12.0,
						100.0,
						330.0,
						32.0
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
					"outlettype": [
						"int"
					],
					"patching_rect": [
						40.0,
						160.0,
						50.0,
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
						40.0,
						200.0,
						55.0,
						22.0
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
						160.0,
						110.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-miditool-in",
					"maxclass": "newobj",
					"text": "live.miditool.in @mode generator",
					"numinlets": 1,
					"numoutlets": 2,
					"outlettype": [
						"",
						"dictionary"
					],
					"patching_rect": [
						140.0,
						240.0,
						215.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-udpreceive",
					"maxclass": "newobj",
					"text": "udpreceive 9881",
					"numinlets": 0,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						360.0,
						240.0,
						120.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-js",
					"maxclass": "newobj",
					"text": "js miditool_bridge.js",
					"numinlets": 3,
					"numoutlets": 2,
					"outlettype": [
						"",
						""
					],
					"patching_rect": [
						140.0,
						320.0,
						180.0,
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
					"id": "obj-status-prepend",
					"maxclass": "newobj",
					"text": "prepend set",
					"numinlets": 2,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						420.0,
						380.0,
						85.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-status-route",
					"maxclass": "newobj",
					"text": "route /miditool/status",
					"numinlets": 1,
					"numoutlets": 2,
					"outlettype": [
						"",
						""
					],
					"patching_rect": [
						420.0,
						340.0,
						160.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-udpsend",
					"maxclass": "newobj",
					"text": "udpsend 127.0.0.1 9880",
					"numinlets": 1,
					"numoutlets": 0,
					"patching_rect": [
						40.0,
						400.0,
						170.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-miditool-out",
					"maxclass": "newobj",
					"text": "live.miditool.out",
					"numinlets": 1,
					"numoutlets": 0,
					"patching_rect": [
						230.0,
						440.0,
						120.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-label-in",
					"maxclass": "comment",
					"text": "notes (left) / context (right)",
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
						260.0,
						244.0,
						200.0,
						18.0
					]
				}
			},
			{
				"box": {
					"id": "obj-label-js",
					"maxclass": "comment",
					"text": "inlet 0=OSC  1=ctx  2=notes  •  out 0→udpsend  out 1→miditool.out",
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
						420.0,
						18.0
					]
				}
			},
			{
				"box": {
					"id": "obj-label-ports",
					"maxclass": "comment",
					"text": "UDP 9881 ← server   •   UDP 9880 → server   (shared with Analyzer)",
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
						480.0,
						420.0,
						18.0
					]
				}
			}
		],
		"lines": [
			{
				"patchline": {
					"source": [
						"obj-midiin",
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
						"obj-thisdevice",
						2
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
						"obj-miditool-in",
						0
					],
					"destination": [
						"obj-js",
						2
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-miditool-in",
						1
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
						"obj-udpreceive",
						0
					],
					"destination": [
						"obj-status-route",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-status-route",
						0
					],
					"destination": [
						"obj-status-prepend",
						1
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-status-prepend",
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
						0
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
						"obj-miditool-out",
						0
					]
				}
			}
		]
	}
}
