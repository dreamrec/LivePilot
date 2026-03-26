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
			1200.0,
			800.0
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
		"description": "LivePilot Analyzer \u2014 real-time spectral analysis for AI mixing",
		"digest": "8-band spectrum, RMS, peak, pitch tracking, key detection, LiveAPI bridge",
		"tags": "livepilot analyzer spectrum",
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
						50.0,
						790.0,
						350.0,
						82.0
					],
					"presentation": 1,
					"presentation_rect": [
						0.0,
						0.0,
						350.0,
						170.0
					],
					"bgcolor": [
						0.12,
						0.12,
						0.12,
						1.0
					],
					"bordercolor": [
						0.2,
						0.2,
						0.2,
						1.0
					],
					"border": 1
				}
			},
			{
				"box": {
					"id": "obj-1",
					"maxclass": "newobj",
					"text": "plugin~",
					"numinlets": 0,
					"numoutlets": 2,
					"outlettype": [
						"signal",
						"signal"
					],
					"patching_rect": [
						50.0,
						30.0,
						65.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-2",
					"maxclass": "newobj",
					"text": "plugout~",
					"numinlets": 2,
					"numoutlets": 2,
					"outlettype": [
						"signal",
						"signal"
					],
					"patching_rect": [
						50.0,
						700.0,
						70.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-3",
					"maxclass": "newobj",
					"text": "+~",
					"numinlets": 2,
					"numoutlets": 1,
					"outlettype": [
						"signal"
					],
					"patching_rect": [
						300.0,
						80.0,
						35.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-4",
					"maxclass": "newobj",
					"text": "*~ 0.5",
					"numinlets": 2,
					"numoutlets": 1,
					"outlettype": [
						"signal"
					],
					"patching_rect": [
						300.0,
						115.0,
						50.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-5",
					"maxclass": "newobj",
					"text": "fffb~ 8",
					"numinlets": 2,
					"numoutlets": 8,
					"outlettype": [
						"signal",
						"signal",
						"signal",
						"signal",
						"signal",
						"signal",
						"signal",
						"signal"
					],
					"patching_rect": [
						300.0,
						180.0,
						300.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-6",
					"maxclass": "newobj",
					"text": "loadmess 40. 130. 350. 1000. 3000. 6000. 10000. 16000.",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						620.0,
						150.0,
						320.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-abs1",
					"maxclass": "newobj",
					"text": "abs~",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						"signal"
					],
					"patching_rect": [
						300.0,
						220.0,
						35.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-abs2",
					"maxclass": "newobj",
					"text": "abs~",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						"signal"
					],
					"patching_rect": [
						345.0,
						220.0,
						35.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-abs3",
					"maxclass": "newobj",
					"text": "abs~",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						"signal"
					],
					"patching_rect": [
						390.0,
						220.0,
						35.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-abs4",
					"maxclass": "newobj",
					"text": "abs~",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						"signal"
					],
					"patching_rect": [
						435.0,
						220.0,
						35.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-abs5",
					"maxclass": "newobj",
					"text": "abs~",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						"signal"
					],
					"patching_rect": [
						480.0,
						220.0,
						35.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-abs6",
					"maxclass": "newobj",
					"text": "abs~",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						"signal"
					],
					"patching_rect": [
						525.0,
						220.0,
						35.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-abs7",
					"maxclass": "newobj",
					"text": "abs~",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						"signal"
					],
					"patching_rect": [
						570.0,
						220.0,
						35.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-abs8",
					"maxclass": "newobj",
					"text": "abs~",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						"signal"
					],
					"patching_rect": [
						615.0,
						220.0,
						35.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-snap1",
					"maxclass": "newobj",
					"text": "snapshot~ 200",
					"numinlets": 2,
					"numoutlets": 1,
					"outlettype": [
						"float"
					],
					"patching_rect": [
						300.0,
						260.0,
						80.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-snap2",
					"maxclass": "newobj",
					"text": "snapshot~ 200",
					"numinlets": 2,
					"numoutlets": 1,
					"outlettype": [
						"float"
					],
					"patching_rect": [
						345.0,
						260.0,
						80.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-snap3",
					"maxclass": "newobj",
					"text": "snapshot~ 200",
					"numinlets": 2,
					"numoutlets": 1,
					"outlettype": [
						"float"
					],
					"patching_rect": [
						390.0,
						260.0,
						80.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-snap4",
					"maxclass": "newobj",
					"text": "snapshot~ 200",
					"numinlets": 2,
					"numoutlets": 1,
					"outlettype": [
						"float"
					],
					"patching_rect": [
						435.0,
						260.0,
						80.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-snap5",
					"maxclass": "newobj",
					"text": "snapshot~ 200",
					"numinlets": 2,
					"numoutlets": 1,
					"outlettype": [
						"float"
					],
					"patching_rect": [
						480.0,
						260.0,
						80.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-snap6",
					"maxclass": "newobj",
					"text": "snapshot~ 200",
					"numinlets": 2,
					"numoutlets": 1,
					"outlettype": [
						"float"
					],
					"patching_rect": [
						525.0,
						260.0,
						80.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-snap7",
					"maxclass": "newobj",
					"text": "snapshot~ 200",
					"numinlets": 2,
					"numoutlets": 1,
					"outlettype": [
						"float"
					],
					"patching_rect": [
						570.0,
						260.0,
						80.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-snap8",
					"maxclass": "newobj",
					"text": "snapshot~ 200",
					"numinlets": 2,
					"numoutlets": 1,
					"outlettype": [
						"float"
					],
					"patching_rect": [
						615.0,
						260.0,
						80.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-pack",
					"maxclass": "newobj",
					"text": "pack f f f f f f f f",
					"numinlets": 8,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						300.0,
						300.0,
						300.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-prepend-spec",
					"maxclass": "newobj",
					"text": "prepend /spectrum",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						300.0,
						340.0,
						105.0,
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
						300.0,
						650.0,
						145.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-peak",
					"maxclass": "newobj",
					"text": "peakamp~ 200",
					"numinlets": 2,
					"numoutlets": 1,
					"outlettype": [
						"float"
					],
					"patching_rect": [
						700.0,
						180.0,
						85.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-prepend-peak",
					"maxclass": "newobj",
					"text": "prepend /peak",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						700.0,
						220.0,
						85.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-rms",
					"maxclass": "newobj",
					"text": "average~ 200 rms",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						"signal"
					],
					"patching_rect": [
						820.0,
						180.0,
						105.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-rms-snap",
					"maxclass": "newobj",
					"text": "snapshot~ 200",
					"numinlets": 2,
					"numoutlets": 1,
					"outlettype": [
						"float"
					],
					"patching_rect": [
						820.0,
						220.0,
						80.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-prepend-rms",
					"maxclass": "newobj",
					"text": "prepend /rms",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						820.0,
						260.0,
						78.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-sigmund",
					"maxclass": "newobj",
					"text": "fzero~ 2048",
					"numinlets": 2,
					"numoutlets": 3,
					"outlettype": [
						"float",
						"float",
						"float"
					],
					"patching_rect": [
						300.0,
						420.0,
						185.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-pitch-pack",
					"maxclass": "newobj",
					"text": "pack f f",
					"numinlets": 2,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						300.0,
						460.0,
						55.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-prepend-pitch",
					"maxclass": "newobj",
					"text": "prepend /pitch",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						300.0,
						500.0,
						87.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-pitch-to-js",
					"maxclass": "newobj",
					"text": "prepend pitch_in",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						500.0,
						460.0,
						100.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-js",
					"maxclass": "newobj",
					"text": "js livepilot_bridge.js",
					"numinlets": 2,
					"numoutlets": 2,
					"outlettype": [
						"",
						""
					],
					"patching_rect": [
						500.0,
						550.0,
						130.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-udprecv",
					"maxclass": "newobj",
					"text": "udpreceive 9881",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						500.0,
						500.0,
						100.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-thisdevice",
					"maxclass": "newobj",
					"text": "live.thisdevice",
					"numinlets": 0,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						700.0,
						500.0,
						95.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-multislider",
					"maxclass": "multislider",
					"numinlets": 1,
					"numoutlets": 2,
					"outlettype": [
						"list",
						""
					],
					"patching_rect": [
						300.0,
						370.0,
						120.0,
						40.0
					],
					"presentation": 1,
					"presentation_rect": [
						6.0,
						28.0,
						262.0,
						136.0
					],
					"size": 8,
					"setminmax": [
						0.0,
						0.3
					],
					"orientation": 1,
					"setstyle": 1,
					"settype": 0,
					"slidercolor": [
						0.65,
						0.82,
						1.0,
						0.9
					],
					"bgcolor": [
						0.08,
						0.08,
						0.08,
						1.0
					],
					"candicane2": [
						0.55,
						0.75,
						1.0,
						0.9
					],
					"candicane3": [
						0.45,
						0.68,
						1.0,
						0.9
					],
					"candicane4": [
						0.4,
						0.62,
						0.95,
						0.9
					],
					"candicane5": [
						0.35,
						0.55,
						0.9,
						0.9
					],
					"candicane6": [
						0.3,
						0.5,
						0.85,
						0.9
					],
					"candicane7": [
						0.25,
						0.45,
						0.8,
						0.9
					],
					"candicane8": [
						0.2,
						0.4,
						0.75,
						0.9
					],
					"thickness": 4,
					"parameter_enable": 0
				}
			},
			{
				"box": {
					"id": "obj-title",
					"maxclass": "comment",
					"text": "LIVEPILOT",
					"numinlets": 1,
					"numoutlets": 0,
					"patching_rect": [
						50.0,
						750.0,
						120.0,
						20.0
					],
					"presentation": 1,
					"presentation_rect": [
						6.0,
						6.0,
						80.0,
						18.0
					],
					"fontname": "Arial Bold",
					"fontsize": 11.0,
					"textcolor": [
						1.0,
						1.0,
						1.0,
						1.0
					]
				}
			},
			{
				"box": {
					"id": "obj-subtitle",
					"maxclass": "comment",
					"text": "ANALYZER",
					"numinlets": 1,
					"numoutlets": 0,
					"patching_rect": [
						170.0,
						750.0,
						80.0,
						20.0
					],
					"presentation": 1,
					"presentation_rect": [
						84.0,
						7.0,
						65.0,
						16.0
					],
					"fontname": "Arial",
					"fontsize": 9.0,
					"textcolor": [
						0.45,
						0.45,
						0.45,
						1.0
					]
				}
			},
			{
				"box": {
					"id": "obj-key-label",
					"maxclass": "comment",
					"text": "KEY",
					"numinlets": 1,
					"numoutlets": 0,
					"patching_rect": [
						50.0,
						770.0,
						30.0,
						20.0
					],
					"presentation": 1,
					"presentation_rect": [
						276.0,
						28.0,
						30.0,
						14.0
					],
					"fontname": "Arial",
					"fontsize": 8.0,
					"textcolor": [
						0.4,
						0.4,
						0.4,
						1.0
					]
				}
			},
			{
				"box": {
					"id": "obj-key-display",
					"maxclass": "comment",
					"text": "\u2014",
					"numinlets": 1,
					"numoutlets": 0,
					"patching_rect": [
						80.0,
						770.0,
						60.0,
						20.0
					],
					"presentation": 1,
					"presentation_rect": [
						276.0,
						46.0,
						72.0,
						50.0
					],
					"fontname": "Arial Bold",
					"fontsize": 13.0,
					"textcolor": [
						0.65,
						0.82,
						1.0,
						1.0
					]
				}
			},
			{
				"box": {
					"id": "obj-status",
					"maxclass": "comment",
					"text": "...",
					"numinlets": 1,
					"numoutlets": 0,
					"patching_rect": [
						250.0,
						750.0,
						60.0,
						20.0
					],
					"presentation": 1,
					"presentation_rect": [
						276.0,
						148.0,
						60.0,
						14.0
					],
					"fontname": "Arial",
					"fontsize": 8.0,
					"textcolor": [
						0.35,
						0.65,
						0.35,
						1.0
					]
				}
			},
			{
				"box": {
					"id": "obj-route-status",
					"maxclass": "newobj",
					"text": "route status key",
					"numinlets": 1,
					"numoutlets": 3,
					"outlettype": [
						"",
						"",
						""
					],
					"patching_rect": [
						700.0,
						580.0,
						105.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-set-status",
					"maxclass": "newobj",
					"text": "prepend set",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						700.0,
						620.0,
						72.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-set-key",
					"maxclass": "newobj",
					"text": "prepend set",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						810.0,
						620.0,
						72.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-fc-spectralshape",
					"maxclass": "newobj",
					"text": "fluid.spectralshape~ @fftsettings 2048 512",
					"numinlets": 1,
					"numoutlets": 2,
					"outlettype": [
						"",
						""
					],
					"patching_rect": [
						50.0,
						880.0,
						260.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-fc-prepend-spectralshape",
					"maxclass": "newobj",
					"text": "prepend /spectral_shape",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						50.0,
						920.0,
						140.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-fc-melbands",
					"maxclass": "newobj",
					"text": "fluid.melbands~ 40 @fftsettings 2048 512",
					"numinlets": 1,
					"numoutlets": 2,
					"outlettype": [
						"",
						""
					],
					"patching_rect": [
						320.0,
						880.0,
						250.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-fc-prepend-melbands",
					"maxclass": "newobj",
					"text": "prepend /mel_bands",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						320.0,
						920.0,
						115.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-fc-chroma",
					"maxclass": "newobj",
					"text": "fluid.chroma~ @fftsettings 4096 1024",
					"numinlets": 1,
					"numoutlets": 2,
					"outlettype": [
						"",
						""
					],
					"patching_rect": [
						580.0,
						880.0,
						230.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-fc-prepend-chroma",
					"maxclass": "newobj",
					"text": "prepend /chroma",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						580.0,
						920.0,
						100.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-fc-loudness",
					"maxclass": "newobj",
					"text": "fluid.loudness~ @kweighting 1 @truepeak 1",
					"numinlets": 1,
					"numoutlets": 2,
					"outlettype": [
						"",
						""
					],
					"patching_rect": [
						820.0,
						880.0,
						260.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-fc-prepend-loudness",
					"maxclass": "newobj",
					"text": "prepend /loudness",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						820.0,
						920.0,
						108.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-fc-onsetfeature",
					"maxclass": "newobj",
					"text": "fluid.onsetfeature~",
					"numinlets": 1,
					"numoutlets": 2,
					"outlettype": [
						"",
						""
					],
					"patching_rect": [
						50.0,
						960.0,
						120.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-fc-prepend-onset",
					"maxclass": "newobj",
					"text": "prepend /onset",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						50.0,
						1000.0,
						90.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-fc-noveltyfeature",
					"maxclass": "newobj",
					"text": "fluid.noveltyfeature~ @kernelsize 21",
					"numinlets": 1,
					"numoutlets": 2,
					"outlettype": [
						"",
						""
					],
					"patching_rect": [
						320.0,
						960.0,
						220.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-fc-prepend-novelty",
					"maxclass": "newobj",
					"text": "prepend /novelty",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						320.0,
						1000.0,
						100.0,
						22.0
					]
				}
			},
			{
				"box": {
					"id": "obj-snap-init",
					"maxclass": "newobj",
					"text": "loadbang",
					"numinlets": 1,
					"numoutlets": 1,
					"outlettype": [
						"bang"
					],
					"patching_rect": [
						20,
						20,
						61,
						22
					]
				}
			},
			{
				"box": {
					"id": "obj-snap-start",
					"maxclass": "message",
					"text": "1",
					"numinlets": 2,
					"numoutlets": 1,
					"outlettype": [
						""
					],
					"patching_rect": [
						20,
						50,
						29,
						22
					]
				}
			}
		],
		"lines": [
			{
				"patchline": {
					"source": [
						"obj-1",
						0
					],
					"destination": [
						"obj-2",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-1",
						1
					],
					"destination": [
						"obj-2",
						1
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-1",
						0
					],
					"destination": [
						"obj-3",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-1",
						1
					],
					"destination": [
						"obj-3",
						1
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-3",
						0
					],
					"destination": [
						"obj-4",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-4",
						0
					],
					"destination": [
						"obj-5",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-6",
						0
					],
					"destination": [
						"obj-5",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-5",
						0
					],
					"destination": [
						"obj-abs1",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-5",
						1
					],
					"destination": [
						"obj-abs2",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-5",
						2
					],
					"destination": [
						"obj-abs3",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-5",
						3
					],
					"destination": [
						"obj-abs4",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-5",
						4
					],
					"destination": [
						"obj-abs5",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-5",
						5
					],
					"destination": [
						"obj-abs6",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-5",
						6
					],
					"destination": [
						"obj-abs7",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-5",
						7
					],
					"destination": [
						"obj-abs8",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-abs1",
						0
					],
					"destination": [
						"obj-snap1",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-abs2",
						0
					],
					"destination": [
						"obj-snap2",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-abs3",
						0
					],
					"destination": [
						"obj-snap3",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-abs4",
						0
					],
					"destination": [
						"obj-snap4",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-abs5",
						0
					],
					"destination": [
						"obj-snap5",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-abs6",
						0
					],
					"destination": [
						"obj-snap6",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-abs7",
						0
					],
					"destination": [
						"obj-snap7",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-abs8",
						0
					],
					"destination": [
						"obj-snap8",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-snap1",
						0
					],
					"destination": [
						"obj-pack",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-snap2",
						0
					],
					"destination": [
						"obj-pack",
						1
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-snap3",
						0
					],
					"destination": [
						"obj-pack",
						2
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-snap4",
						0
					],
					"destination": [
						"obj-pack",
						3
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-snap5",
						0
					],
					"destination": [
						"obj-pack",
						4
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-snap6",
						0
					],
					"destination": [
						"obj-pack",
						5
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-snap7",
						0
					],
					"destination": [
						"obj-pack",
						6
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-snap8",
						0
					],
					"destination": [
						"obj-pack",
						7
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-pack",
						0
					],
					"destination": [
						"obj-prepend-spec",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-prepend-spec",
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
						"obj-pack",
						0
					],
					"destination": [
						"obj-multislider",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-4",
						0
					],
					"destination": [
						"obj-peak",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-peak",
						0
					],
					"destination": [
						"obj-prepend-peak",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-prepend-peak",
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
						"obj-4",
						0
					],
					"destination": [
						"obj-rms",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-rms",
						0
					],
					"destination": [
						"obj-rms-snap",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-rms-snap",
						0
					],
					"destination": [
						"obj-prepend-rms",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-prepend-rms",
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
						"obj-4",
						0
					],
					"destination": [
						"obj-sigmund",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-sigmund",
						0
					],
					"destination": [
						"obj-pitch-pack",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-sigmund",
						1
					],
					"destination": [
						"obj-pitch-pack",
						1
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-pitch-pack",
						0
					],
					"destination": [
						"obj-prepend-pitch",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-prepend-pitch",
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
						"obj-pitch-pack",
						0
					],
					"destination": [
						"obj-pitch-to-js",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-pitch-to-js",
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
						"obj-udprecv",
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
						"obj-thisdevice",
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
						"obj-route-status",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-route-status",
						0
					],
					"destination": [
						"obj-set-status",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-set-status",
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
						"obj-route-status",
						1
					],
					"destination": [
						"obj-set-key",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-set-key",
						0
					],
					"destination": [
						"obj-key-display",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-4",
						0
					],
					"destination": [
						"obj-fc-spectralshape",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-fc-spectralshape",
						0
					],
					"destination": [
						"obj-fc-prepend-spectralshape",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-fc-prepend-spectralshape",
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
						"obj-4",
						0
					],
					"destination": [
						"obj-fc-melbands",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-fc-melbands",
						0
					],
					"destination": [
						"obj-fc-prepend-melbands",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-fc-prepend-melbands",
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
						"obj-4",
						0
					],
					"destination": [
						"obj-fc-chroma",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-fc-chroma",
						0
					],
					"destination": [
						"obj-fc-prepend-chroma",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-fc-prepend-chroma",
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
						"obj-4",
						0
					],
					"destination": [
						"obj-fc-loudness",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-fc-loudness",
						0
					],
					"destination": [
						"obj-fc-prepend-loudness",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-fc-prepend-loudness",
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
						"obj-4",
						0
					],
					"destination": [
						"obj-fc-onsetfeature",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-fc-onsetfeature",
						0
					],
					"destination": [
						"obj-fc-prepend-onset",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-fc-prepend-onset",
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
						"obj-4",
						0
					],
					"destination": [
						"obj-fc-noveltyfeature",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-fc-noveltyfeature",
						0
					],
					"destination": [
						"obj-fc-prepend-novelty",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-fc-prepend-novelty",
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
						"obj-snap-init",
						0
					],
					"destination": [
						"obj-snap-start",
						0
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-snap-start",
						0
					],
					"destination": [
						"obj-snap1",
						1
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-snap-start",
						0
					],
					"destination": [
						"obj-snap2",
						1
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-snap-start",
						0
					],
					"destination": [
						"obj-snap3",
						1
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-snap-start",
						0
					],
					"destination": [
						"obj-snap4",
						1
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-snap-start",
						0
					],
					"destination": [
						"obj-snap5",
						1
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-snap-start",
						0
					],
					"destination": [
						"obj-snap6",
						1
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-snap-start",
						0
					],
					"destination": [
						"obj-snap7",
						1
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-snap-start",
						0
					],
					"destination": [
						"obj-snap8",
						1
					]
				}
			},
			{
				"patchline": {
					"source": [
						"obj-snap-start",
						0
					],
					"destination": [
						"obj-rms-snap",
						1
					]
				}
			}
		],
		"dependency_cache": [
			{
				"name": "livepilot_bridge.js",
				"bootpath": ".",
				"type": "TEXT",
				"implicit": 1
			}
		],
		"autosave": 0
	}
}